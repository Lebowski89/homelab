"""Exercise the real permission entry point and pinned modules against synthetic HTTPS."""

import copy
import http.server
import json
import os
import re
import ssl
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
HOST = yaml.safe_load((ROOT / "ansible/host_vars/pve1.yml").read_text())
ROLE = ROOT / "ansible/roles/opentofu"
TOKENS = ["root@pam!molecule-controller-bootstrap", "root@pam!molecule-vm-acceptance"]
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def certificate(tmp_path_factory):
    directory = tmp_path_factory.mktemp("molecule-permission-tls")
    key, cert = directory / "key.pem", directory / "cert.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=IP:127.0.0.1,DNS:localhost",
            "-keyout",
            str(key),
            "-out",
            str(cert),
        ],
        check=True,
        capture_output=True,
    )
    return key, cert


@pytest.fixture
def permission_api(tmp_path, certificate):
    roles = {
        name: set(privs)
        for name, privs in HOST["opentofu_pve_molecule_roles"].items()
        if name not in ["MoleculeLocalConfig", "MoleculeImageDownload", "MoleculePoolAudit"]
    }
    general_tasks = yaml.safe_load((ROLE / "tasks/sub_tasks/pve_user.yml").read_text())
    general = next(
        task["community.proxmox.proxmox_role"]["privs"]
        for parent in general_tasks
        for task in parent.get("block", [])
        if "community.proxmox.proxmox_role" in task
    )
    roles.update(terraform=set(general), UnrelatedRole={"VM.Audit"})
    acls = [
        dict(path=a["path"], roleid=a["role"], type="token", ugid=a["token"], propagate=1)
        for a in HOST["opentofu_pve_molecule_token_acls"]
        if a["role"] not in ["MoleculeLocalConfig", "MoleculeImageDownload"]
        and a["path"] != "/sdn/zones/localnetwork/vmbr0"
        and not a["path"].startswith("/pool/")
    ]
    acls += [
        dict(path="/", roleid="terraform", type="user", ugid="terraform@pve", propagate=1),
        dict(path="/storage/local", roleid="UnrelatedRole", type="user", ugid="unrelated@pve", propagate=1),
        dict(path="/vms/980000", roleid="MoleculeVM", type="token", ugid=TOKENS[1], propagate=1),
        dict(path="/vms/980000", roleid="MoleculeClone", type="token", ugid=TOKENS[1], propagate=1),
        dict(path="/vms/980001", roleid="MoleculeVM", type="token", ugid=TOKENS[1], propagate=1),
    ]
    state = {
        "roles": roles,
        "acls": acls,
        "tokens": [dict(tokenid=t.split("!")[1], privsep=1) for t in TOKENS],
        "token_secrets": {t: "fixture-only-existing-token" for t in TOKENS},
        "requests": [],
        "mutations": [],
        "pools": {},
    }

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def handle_request(self):
            parsed = urlsplit(self.path)
            path = unquote(parsed.path.removeprefix("/api2/json"))
            data = {
                key: values[0] for key, values in parse_qs(self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode()).items()
            }
            state["requests"].append((self.command, path))
            result, status, reason = None, 200, None
            if path == "/access/ticket" and self.command == "POST":
                assert data == {"username": "fixture@pam", "password": "fixture-only-password"}
                result = dict(ticket="fixture-ticket", CSRFPreventionToken="fixture-csrf", username="fixture@pam")
            elif self.command == "GET" and path == "/version":
                result = {"version": "9.1"}
            elif self.command == "GET" and path == "/access/users/root@pam":
                result = dict(
                    enable=1,
                    tokens={
                        token["tokenid"]: {key: value for key, value in token.items() if key != "tokenid"} for token in state["tokens"]
                    },
                )
            elif self.command == "GET" and path == "/access/users/terraform@pve":
                result = dict(enable=1, comment="OpenTofu automation user")
            elif self.command == "GET" and path == "/access/roles":
                status = state.get("role_index_status", 200)
                result = [dict(roleid=name, privs=",".join(sorted(privs))) for name, privs in state["roles"].items()]
            elif self.command == "GET" and path.startswith("/access/roles/"):
                name = path.rsplit("/", 1)[1]
                if name not in state["roles"]:
                    status, reason = 500, f"role '{name}' does not exist"
                elif state.get("role_detail_status") and name == "MoleculeVM":
                    status = state["role_detail_status"]
                else:
                    # Zero-valued API flags are not granted privileges.
                    result = {"Sys.Modify": 0} | {privilege: 1 for privilege in state["roles"][name]}
            elif (self.command == "POST" and path == "/access/roles") or (self.command == "PUT" and path.startswith("/access/roles/")):
                name = data.get("roleid", path.rsplit("/", 1)[1])
                state["roles"][name] = set(data["privs"].split(","))
                state["mutations"].append((self.command, path, copy.deepcopy(data)))
            elif self.command == "GET" and path == "/access/acl":
                result = copy.deepcopy(state["acls"])
            elif self.command == "GET" and path == "/pools":
                poolid = parse_qs(parsed.query).get("poolid", [None])[0]
                if poolid is None:
                    result = [dict(poolid=key, comment=value["comment"]) for key, value in state["pools"].items()]
                elif "pool_response" in state:
                    result = copy.deepcopy(state["pool_response"])
                elif poolid not in state["pools"]:
                    status, reason = 500, f"pool '{poolid}' does not exist"
                else:
                    result = [dict(poolid=poolid, **state["pools"][poolid])]
            elif self.command == "POST" and path == "/pools":
                assert data["poolid"] not in state["pools"]
                state["pools"][data["poolid"]] = dict(comment=data["comment"], members=[])
                state["mutations"].append((self.command, path, copy.deepcopy(data)))
            elif self.command == "PUT" and path == "/access/acl" and "delete" not in data:
                kind = "token" if "tokens" in data else "user"
                ace = dict(path=data["path"], roleid=data["roles"], type=kind, ugid=data[kind + "s"], propagate=int(data["propagate"]))
                state["acls"] = [
                    old for old in state["acls"] if any(old[key] != ace[key] for key in ["path", "roleid", "type", "ugid"])
                ] + [ace]
                state["mutations"].append((self.command, path, copy.deepcopy(data)))
            elif self.command == "PUT" and path == "/access/acl" and data.get("delete") == "1":
                state["acls"] = [
                    ace
                    for ace in state["acls"]
                    if (ace["path"], ace["roleid"], ace["ugid"], ace["type"]) != (data["path"], data["roles"], data["tokens"], "token")
                ]
                state["mutations"].append((self.command, path, copy.deepcopy(data)))
            else:
                status = 405
            self.send_response(
                status,
                reason or {403: "Permission check failed", 405: "unsupported operation", 500: "Internal Server Error"}.get(status, "OK"),
            )
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"data": result}).encode())

        do_GET = do_POST = do_PUT = do_DELETE = handle_request

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certificate[1], certificate[0])
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    original = copy.deepcopy(state)

    def run(*, check=False, enabled=True, overrides=None, general=False, configured=True, verify_cleanup=False):
        variables = copy.deepcopy(HOST)
        if not configured:
            variables = {key: value for key, value in variables.items() if not key.startswith("opentofu_pve_molecule_")}
        else:
            variables["opentofu_pve_molecule_permissions_enabled"] = False if enabled is True else enabled
        variables.update(
            ansible_host=f"127.0.0.1:{server.server_port}",
            ansible_connection="local",
            ansible_become=False,
            opentofu_pve_host="pve1",
            opentofu_primary_manager="localhost",
            proxmox_api_bootstrap_user="fixture@pam",
            proxmox_api_bootstrap_password="fixture-only-password",
        )
        variables.update(overrides or {})
        if not general:
            variables.pop("opentofu_api_user", None)
            variables.pop("opentofu_api_token_name", None)
        inventory = tmp_path / "inventory.yml"
        inventory.write_text(
            yaml.safe_dump(
                {
                    "all": {
                        "vars": {"ansible_python_interpreter": sys.executable},
                        "children": {"tags_opentofu": {"children": {"tags_opentofu_pve_user": {"hosts": {"pve1": variables}}}}},
                        "hosts": {"localhost": {"ansible_connection": "local"}},
                    }
                }
            )
        )
        plays = yaml.safe_load((ROOT / "ansible/playbook.yml").read_text())
        entry = next(
            t for play in plays for t in play.get("tasks", []) if t.get("ansible.builtin.include_role", {}).get("name") == "opentofu"
        )
        play = tmp_path / "play.yml"
        tasks = [entry]
        if verify_cleanup:
            tasks = [
                dict(
                    block=tasks,
                    rescue=[
                        {
                            "ansible.builtin.assert": {
                                "that": [
                                    f"{name} == {{}}"
                                    for name in [
                                        "opentofu_pve_molecule_pool_session",
                                        "opentofu_pve_molecule_roles_index",
                                        "opentofu_pve_molecule_pool_roles_info",
                                        "opentofu_pve_molecule_pools_info",
                                        "opentofu_pve_molecule_pool_info",
                                        "opentofu_pve_molecule_selected_pool",
                                    ]
                                ]
                            },
                            "no_log": True,
                            "diff": False,
                            "tags": ["opentofu_molecule_permissions"],
                        },
                        {
                            "ansible.builtin.fail": {"msg": "Fixture confirmed credential cleanup and preserves the original failure"},
                            "tags": ["opentofu_molecule_permissions"],
                        },
                    ],
                )
            ]
        play.write_text(yaml.safe_dump([dict(hosts="pve1", gather_facts=False, tasks=tasks)]))
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(exist_ok=True)
        pveum = bin_dir / "pveum"
        pveum.write_text(
            '#!/bin/sh\n[ "$*" = \'user token list terraform@pve --output-format json\' ] || exit 91\nprintf \'%s\\n\' \'[{"tokenid":"terraform-token","privsep":0}]\'\n'
        )
        pveum.chmod(0o700)
        environment = {key: value for key, value in os.environ.items() if not key.startswith(("PROXMOX_", "INFISICAL_"))}
        environment.update(
            ANSIBLE_CONFIG=str(ROOT / "ansible/ansible.cfg"),
            ANSIBLE_ROLES_PATH=str(ROOT / "ansible/roles"),
            ANSIBLE_LOCAL_TEMP=str(tmp_path / "ansible-local"),
            ANSIBLE_HOME=str(tmp_path / "ansible-home"),
            ANSIBLE_LOG_PATH=str(tmp_path / "ansible.log"),
            REQUESTS_CA_BUNDLE=str(certificate[1]),
            PROXMOX_CA_PATH=str(certificate[1]),
            PATH=str(bin_dir) + ":" + os.environ["PATH"],
        )
        command = [
            str(Path(sys.executable).with_name("ansible-playbook")),
            "-i",
            str(inventory),
            str(play),
            "--tags",
            "opentofu_pve_user" if general else "opentofu_molecule_permissions",
        ]
        if configured and enabled is True and "opentofu_pve_molecule_permissions_enabled" not in (overrides or {}):
            command += ["-e", json.dumps({"opentofu_pve_molecule_permissions_enabled": True})]
        if check:
            command.append("--check")
        result = subprocess.run(command, cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=120)
        assert "fixture-only-password" not in result.stdout + result.stderr
        assert "fixture-only-existing-token" not in result.stdout + result.stderr
        assert "fixture-ticket" not in result.stdout + result.stderr
        return result

    try:
        yield state, original, run
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_real_entry_adds_only_approved_access_and_rerun_is_idempotent(permission_api):
    state, before, run = permission_api
    assert "MoleculePoolAudit" not in state["roles"]
    result = run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert state["roles"] == before["roles"] | {
        "MoleculeLocalConfig": {"Datastore.Allocate"},
        "MoleculeImageDownload": {"Sys.AccessNetwork"},
        "MoleculePoolAudit": {"Pool.Audit"},
    }
    additional = [ace for ace in state["acls"] if ace not in before["acls"]]
    assert {(ace["ugid"], ace["path"], ace["roleid"]) for ace in additional} == {
        *((token, "/storage/local", "MoleculeLocalConfig") for token in TOKENS),
        (TOKENS[0], "/sdn/zones/localnetwork/vmbr0", "MoleculeBridge"),
        (TOKENS[1], "/nodes/pve1", "MoleculeImageDownload"),
        *((TOKENS[1], "/pool/molecule-acceptance", role) for role in ["MoleculeVM", "MoleculeClone", "MoleculePoolAudit"]),
    }
    assert state["roles"]["MoleculeBridge"] == {"SDN.Use"}
    assert not any(ace["ugid"] == TOKENS[1] and ace["path"] == "/sdn/zones/localnetwork/vmbr0" for ace in state["acls"])
    superseded = [ace for ace in before["acls"] if ace["ugid"] == TOKENS[1] and ace["path"] in ["/vms/980000", "/vms/980001"]]
    assert len(superseded) == 3 and all(ace not in state["acls"] for ace in superseded)
    assert all(ace in state["acls"] for ace in before["acls"] if ace not in superseded)
    assert state["pools"] == {"molecule-acceptance": {"comment": "homelab-molecule:acceptance-pool", "members": []}}
    assert state["tokens"] == before["tokens"] and state["token_secrets"] == before["token_secrets"]
    previous = copy.deepcopy(state["mutations"])
    # A later permission invocation may encounter the owned disposable members.
    members = [
        dict(type="qemu", vmid=vmid, node="pve1", name="molecule-" + "a" * 32 + "-" + role)
        for vmid, role in [(980000, "template"), (980001, "subject")]
    ]
    state["pools"]["molecule-acceptance"]["members"] = copy.deepcopy(members)
    result = run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert re.search(r"changed=0\b", result.stdout)
    assert state["mutations"] == previous
    assert state["pools"]["molecule-acceptance"]["members"] == members


def test_existing_role_and_partial_grant_are_reconciled_without_replacing_other_acls(permission_api):
    state, before, run = permission_api
    state["roles"]["MoleculeLocalConfig"] = {"Datastore.Allocate", "Datastore.Audit"}
    existing = dict(path="/storage/local", roleid="MoleculeLocalConfig", type="token", ugid=TOKENS[0], propagate=1)
    state["acls"].append(existing)
    result = run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert state["roles"]["MoleculeLocalConfig"] == {"Datastore.Allocate"}
    assert existing in state["acls"]
    assert all(ace in state["acls"] for ace in before["acls"] if ace["path"] not in ["/vms/980000", "/vms/980001"])
    writes = [data for _, path, data in state["mutations"] if path == "/access/acl" and not data.get("delete")]
    assert {(data["tokens"], data["path"], data["roles"]) for data in writes} == {
        (TOKENS[1], "/storage/local", "MoleculeLocalConfig"),
        (TOKENS[0], "/sdn/zones/localnetwork/vmbr0", "MoleculeBridge"),
        (TOKENS[1], "/nodes/pve1", "MoleculeImageDownload"),
        *((TOKENS[1], "/pool/molecule-acceptance", role) for role in ["MoleculeVM", "MoleculeClone", "MoleculePoolAudit"]),
    }


def test_allocation_reuse_restores_deleted_vm_acls_without_changing_the_permission_boundary(permission_api):
    state, _, run = permission_api
    # Retain the legacy optional operator-reconciliation contract separately.
    legacy_acls = [a for a in HOST["opentofu_pve_molecule_token_acls"] if not a["path"].startswith("/pool/")]
    legacy_acls += [
        dict(token=TOKENS[1], path=path, role=role)
        for path, role in [("/vms/980000", "MoleculeVM"), ("/vms/980001", "MoleculeVM"), ("/vms/980000", "MoleculeClone")]
    ]
    options = dict(overrides={"opentofu_pve_molecule_pool": {}, "opentofu_pve_molecule_token_acls": legacy_acls})
    result = run(**options)
    assert result.returncode == 0, result.stdout + result.stderr
    approved = copy.deepcopy(state)
    removed = [ace for ace in state["acls"] if ace["path"] in ["/vms/980000", "/vms/980001"]]
    # The installed Proxmox VM-delete path removes ACLs even without purge.
    state["acls"] = [ace for ace in state["acls"] if ace not in removed]
    state["mutations"].clear()
    result = run(check=True, **options)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not state["mutations"] and all(ace not in state["acls"] for ace in removed)
    result = run(**options)
    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(state["acls"], key=str) == sorted(approved["acls"], key=str)
    assert state["roles"] == approved["roles"] and state["tokens"] == approved["tokens"]
    assert state["token_secrets"] == approved["token_secrets"]
    assert {(data["tokens"], data["path"], data["roles"]) for _, path, data in state["mutations"] if path == "/access/acl"} == {
        (ace["ugid"], ace["path"], ace["roleid"]) for ace in removed
    }
    writes = copy.deepcopy(state["mutations"])
    result = run(**options)
    assert result.returncode == 0, result.stdout + result.stderr
    assert re.search(r"changed=0\b", result.stdout) and state["mutations"] == writes


def test_check_mode_does_not_mutate_permissions_or_tokens(permission_api):
    state, before, run = permission_api
    result = run(check=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert state["roles"] == before["roles"] and state["acls"] == before["acls"]
    assert state["tokens"] == before["tokens"] and state["token_secrets"] == before["token_secrets"]
    assert not state["mutations"]
    assert state["pools"] == before["pools"]
    assert "Would ensure MoleculeLocalConfig" in result.stdout


@pytest.mark.parametrize("configured", [False, True])
def test_optional_path_needs_no_molecule_identities_or_authentication_when_disabled(permission_api, configured):
    state, _, run = permission_api
    state["tokens"] = []
    result = run(enabled=False, configured=configured, overrides={"proxmox_api_bootstrap_password": None})
    assert result.returncode == 0, result.stdout + result.stderr
    assert not state["requests"]


@pytest.mark.parametrize("invalid", ["missing", "unseparated"])
def test_existing_token_separation_is_required_before_any_permission_mutation(permission_api, invalid):
    state, _, run = permission_api
    if invalid == "missing":
        state["tokens"].pop()
    else:
        state["tokens"][0]["privsep"] = 0
    result = run()
    assert result.returncode != 0 and "privilege separation enabled" in result.stdout
    assert not state["mutations"]


@pytest.mark.parametrize(
    "invalid",
    [
        "root",
        "other_storage",
        "other_token",
        "extra_privilege",
        "truthy_string",
        "acceptance_source_bridge",
        "wrong_bridge_role",
        "broader_bridge_role",
        "bootstrap_download",
        "other_download_node",
        "broader_download_role",
        "download_in_other_role",
        "bootstrap_pool",
        "wrong_pool",
        "production_vm_acl",
        "pool_administration",
        "broader_vm_role",
        "broader_clone_role",
    ],
)
def test_invalid_scope_is_rejected_before_api_access(permission_api, invalid):
    state, _, run = permission_api
    overrides = {}
    acls = copy.deepcopy(HOST["opentofu_pve_molecule_token_acls"])
    local = next(ace for ace in acls if ace["role"] == "MoleculeLocalConfig")
    if invalid == "root":
        local["path"] = "/"
    elif invalid == "other_storage":
        local["path"] = "/storage/local-zfs"
    elif invalid == "other_token":
        local["token"] = "unrelated@pve!token"
    elif invalid == "extra_privilege":
        roles = copy.deepcopy(HOST["opentofu_pve_molecule_roles"])
        roles["MoleculeLocalConfig"].append("Datastore.AllocateSpace")
        overrides["opentofu_pve_molecule_roles"] = roles
    elif invalid in ["acceptance_source_bridge", "wrong_bridge_role"]:
        bridge = next(ace for ace in acls if ace["path"] == "/sdn/zones/localnetwork/vmbr0")
        if invalid == "acceptance_source_bridge":
            bridge["token"] = TOKENS[1]
        else:
            bridge["role"] = "MoleculeVM"
    elif invalid == "broader_bridge_role":
        roles = copy.deepcopy(HOST["opentofu_pve_molecule_roles"])
        roles["MoleculeBridge"].append("SDN.Audit")
        overrides["opentofu_pve_molecule_roles"] = roles
    elif invalid in ["bootstrap_download", "other_download_node"]:
        download = next(ace for ace in acls if ace["role"] == "MoleculeImageDownload")
        if invalid == "bootstrap_download":
            download["token"] = TOKENS[0]
        else:
            download["path"] = "/nodes/other-node"
    elif invalid in ["broader_download_role", "download_in_other_role"]:
        roles = copy.deepcopy(HOST["opentofu_pve_molecule_roles"])
        if invalid == "broader_download_role":
            roles["MoleculeImageDownload"].append("Sys.Modify")
        else:
            roles["MoleculeNode"].append("Sys.AccessNetwork")
        overrides["opentofu_pve_molecule_roles"] = roles
    elif invalid in ["bootstrap_pool", "wrong_pool", "production_vm_acl"]:
        pool = next(ace for ace in acls if ace["path"].startswith("/pool/"))
        if invalid == "bootstrap_pool":
            pool["token"] = TOKENS[0]
        elif invalid == "wrong_pool":
            pool["path"] = "/pool/production"
        else:
            pool["path"] = "/vms/104"
    elif invalid in ["pool_administration", "broader_vm_role", "broader_clone_role"]:
        roles = copy.deepcopy(HOST["opentofu_pve_molecule_roles"])
        role, privilege = {
            "pool_administration": ("MoleculePoolAudit", "Pool.Allocate"),
            "broader_vm_role": ("MoleculeVM", "VM.GuestAgent.Unrestricted"),
            "broader_clone_role": ("MoleculeClone", "Permissions.Modify"),
        }[invalid]
        roles[role].append(privilege)
        overrides["opentofu_pve_molecule_roles"] = roles
    else:
        overrides["opentofu_pve_molecule_permissions_enabled"] = "true"
    overrides["opentofu_pve_molecule_token_acls"] = acls
    result = run(overrides=overrides)
    assert result.returncode != 0
    assert not state["requests"]


@pytest.mark.parametrize("foreign", ["pool_owner", "storage", "controller", "production", "actual_vm_role", "actual_clone_role"])
def test_pool_preflight_rejects_foreign_members_and_actual_role_expansion_before_mutation(permission_api, foreign):
    state, _, run = permission_api
    pool = dict(comment="homelab-molecule:acceptance-pool", members=[])
    state["pools"]["molecule-acceptance"] = pool
    if foreign == "pool_owner":
        pool["comment"] = "another installation"
    elif foreign == "storage":
        pool["members"].append(dict(type="storage", storage="local-zfs"))
    elif foreign in ["controller", "production"]:
        pool["members"].append(dict(type="qemu", vmid=9300 if foreign == "controller" else 104, name="production"))
    else:
        state["roles"]["MoleculeVM" if foreign == "actual_vm_role" else "MoleculeClone"].add("Permissions.Modify")
    result = run()
    assert result.returncode != 0
    assert not state["mutations"]
    assert "fixture-ticket" not in result.stdout + result.stderr


@pytest.mark.parametrize("invalid", ["object", "empty", "duplicate", "malformed_entry", "mismatched", "missing_poolid"])
def test_selected_pool_response_must_contain_one_matching_object_before_mutation(permission_api, invalid):
    state, _, run = permission_api
    pool = dict(comment="homelab-molecule:acceptance-pool", members=[])
    state["pools"]["molecule-acceptance"] = pool
    valid = dict(poolid="molecule-acceptance", **pool)
    state["pool_response"] = {
        "object": valid,
        "empty": [],
        "duplicate": [valid, valid],
        "malformed_entry": [None],
        "mismatched": [valid | {"poolid": "production"}],
        "missing_poolid": [pool],
    }[invalid]
    before = copy.deepcopy(state)
    result = run()
    assert result.returncode != 0
    assert not state["mutations"]
    assert state["pools"] == before["pools"] and state["roles"] == before["roles"]
    assert state["acls"] == before["acls"] and state["tokens"] == before["tokens"]


@pytest.mark.parametrize("endpoint,status", [("role_index_status", 403), ("role_index_status", 500), ("role_detail_status", 500)])
def test_role_discovery_failure_is_fatal_and_clears_private_state(permission_api, endpoint, status):
    state, _, run = permission_api
    # Proxmox role IDs are case-sensitive; unrelated names must not block discovery.
    state["roles"]["unrelatedrole"] = {"VM.Audit"}
    state[endpoint] = status
    result = run(verify_cleanup=True)
    assert result.returncode != 0
    assert "Fixture confirmed credential cleanup and preserves the original failure" in result.stdout
    assert not state["mutations"]
    if endpoint == "role_detail_status":
        assert ("GET", "/access/roles/MoleculeVM") in state["requests"]


def test_general_setup_remains_independent_of_molecule_tokens(permission_api):
    state, before, run = permission_api
    state["tokens"] = []
    result = run(enabled=False, configured=False, general=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert state["roles"] == before["roles"] and state["acls"] == before["acls"]
    assert not state["mutations"]
    assert ("GET", "/access/users/root@pam") not in state["requests"]
