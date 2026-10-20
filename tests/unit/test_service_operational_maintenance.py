"""Managed maintenance uses current installed protection, not historical flags."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from ansible.errors import AnsibleFilterError

ROOT = Path(__file__).resolve().parents[2]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIXTURE = load("tests/unit/test_mgt_podman_migration.py", "maintenance_real_catalog")
CHECK = load("ansible/action_plugins/service_operational_check.py", "maintenance_action")
COMMON = FIXTURE.COMMON


def metadata(name):
    cfg = FIXTURE.resolve(FIXTURE.CATALOG.service_catalog_merge_target(FIXTURE.catalog()[name], None), FIXTURE.context())
    return COMMON.service_common_requirements_metadata(cfg, name)


def worker_fixture():
    cfg = metadata("whisparr")
    variables = FIXTURE.context()
    policy = {
        "schema": 1,
        "backend": "legacy",
        "inventory_host": "unraid",
        "inventory_address": variables["hostvars"]["unraid"]["local_ip"],
        "sources": [variables["hostvars"]["mgt"]["local_ip"]],
        "sources_verified": True,
        "ports": [cfg["ports"]["web_backend"]["published"]],
    }
    observed = {
        "Spec": {
            "Name": "whisparr_whisparr",
            "Labels": {"com.docker.stack.namespace": "whisparr"},
            "TaskTemplate": {"Placement": {"Constraints": cfg["deploy"]["constraints"]}},
        },
        "ports": [
            {
                "PublishedPort": policy["ports"][0],
                "TargetPort": cfg["ports"]["web_backend"]["target"],
                "Protocol": "tcp",
                "PublishMode": "host",
            }
        ],
    }
    return cfg, variables, policy, observed


def test_real_whisparr_endpoint_and_placement_changes_require_explicit_reconciliation():
    cfg, variables, policy, observed = worker_fixture()
    assert CHECK.docker_contract(cfg, observed)["managed"]
    plan = CHECK.WORKER.build_plan({"whisparr": cfg}, ["unraid", "plex"], variables["hostvars"]["mgt"]["local_ip"], lambda value: value)
    CHECK.worker_contract(policy, plan, "unraid", policy["inventory_address"], policy["sources"])
    for field in ["published", "target"]:
        changed = deepcopy(cfg)
        changed["ports"]["web_backend"][field] += 1
        with pytest.raises(ValueError, match="publication changed"):
            CHECK.docker_contract(changed, observed)
    changed = deepcopy(cfg)
    changed["deploy"]["constraints"] = ["node.hostname == other"]
    with pytest.raises(ValueError, match="placement changed"):
        CHECK.docker_contract(changed, observed)
    for mutation in [{"ports": []}, {"inventory_host": "plex"}, {"sources": ["192.0.2.199"]}]:
        with pytest.raises(ValueError):
            CHECK.worker_contract(policy | mutation, plan, "unraid", policy["inventory_address"], policy["sources"])


def test_real_rootless_mapping_mounts_and_caller_contract_are_independent_of_images():
    cfg = metadata("wallos")
    normalized = CHECK.PODMAN.podman_service_normalize(cfg, "wallos")
    body = FIXTURE.render_container(normalized)
    assert CHECK.quadlet_contract(normalized, body)
    changed = deepcopy(cfg)
    changed["deploy"]["execution"]["userns"]["uid"] = "83"
    assert not CHECK.quadlet_contract(CHECK.PODMAN.podman_service_normalize(changed, "wallos"), body)
    changed = deepcopy(cfg)
    changed["volumes"]["db"]["source"] += "-new"
    changed["paths"][1]["path"] += "-new"
    assert not CHECK.quadlet_contract(CHECK.PODMAN.podman_service_normalize(changed, "wallos"), body)
    changed = deepcopy(cfg)
    changed["image"] = "registry.example.invalid/nonproduction:2"
    assert CHECK.quadlet_contract(CHECK.PODMAN.podman_service_normalize(changed, "wallos"), body)
    plan = CHECK.MGT.build_plan({"wallos": cfg}, "mgt", lambda value, defaults: value, [])
    policy = {
        "schema": 1,
        "backend": "nf_tables",
        "inputs_verified": True,
        "inventory_host": "mgt",
        "inventory_address": "192.0.2.10",
        "endpoints": deepcopy(plan["endpoints"]),
        "principals": deepcopy(plan["principals"]),
        "callers": {
            "traefik": [
                {"kind": "local", "phase": "podman", "account": "podman-traefik", "uid": 2001, "verified": True, "restart_verified": True}
            ]
        },
    }
    CHECK.mgt_contract(cfg, policy, plan, "mgt", "192.0.2.10")
    for change in ["port", "callers", "principal"]:
        bad = deepcopy(policy)
        if change == "port":
            bad["endpoints"][0]["port"] += 1
        elif change == "callers":
            bad["endpoints"][0]["callers"].append("recovery")
        else:
            bad["principals"]["wallos"]["future_account"] = "podman-other"
        with pytest.raises(ValueError):
            CHECK.mgt_contract(cfg, bad, plan, "mgt", "192.0.2.10")


def test_managed_rootless_runtime_uses_owned_state_marker_and_unchanged_quadlet():
    cfg = metadata("wallos")
    normalized = CHECK.PODMAN.podman_service_normalize(cfg, "wallos")
    state = {
        "version": 2,
        "managed_by": "podman_services",
        "service": "wallos",
        "unit_name": "wallos.service",
        "mode": "rootless",
        "host_user": "podman-wallos",
        "uid": "2019",
        "gid": "2019",
        "home": "/var/lib/podman-wallos",
        "quadlet_dir": "/var/lib/podman-wallos/.config/containers/systemd",
    }
    marker = {key: state[key] for key in ["managed_by", "service", "host_user", "uid", "gid", "home"]}
    files = {
        "/var/lib/podman-services/wallos.yml": yaml.safe_dump(state),
        "/var/lib/podman-services/accounts/podman-wallos.yml": yaml.safe_dump(marker),
        state["quadlet_dir"] + "/wallos.container": FIXTURE.render_container(normalized),
    }
    action = object.__new__(CHECK.ActionModule)
    action.variables = {}
    action.module = lambda *args, **kwargs: {"stat": {"isdir": True, "islnk": False}}
    action.read = lambda path, *args, **kwargs: files.get(path)
    action.command = lambda argv: "podman-wallos:x:2019:2019::/var/lib/podman-wallos:/usr/sbin/nologin"
    assert action.runtime(cfg) == {"managed": True, "ownership_transition": True}
    action.module = lambda *args, **kwargs: {"stat": {"exists": False}}
    with pytest.raises(ValueError, match="data bind is absent"):
        action.runtime(cfg)
    action.module = lambda *args, **kwargs: {"stat": {"isdir": True, "islnk": False}}
    changed = deepcopy(cfg)
    changed["deploy"]["execution"]["userns"]["uid"] = "83"
    assert action.runtime(changed) == {"managed": True, "ownership_transition": False}
    files["/var/lib/podman-services/accounts/podman-wallos.yml"] = yaml.safe_dump(marker | {"uid": "2020"})
    with pytest.raises(ValueError, match="ownership marker"):
        action.runtime(cfg)
    del files["/var/lib/podman-services/wallos.yml"]
    assert action.runtime(cfg) == {"managed": False}


def test_all_effective_mgt_metadata_normalizes_without_secret_values():
    services, variables = FIXTURE.catalog(), FIXTURE.context()
    for entry in FIXTURE.mgt_entries(services):
        cfg = FIXTURE.resolve(FIXTURE.CATALOG.service_catalog_merge_target(services[entry["name"]], entry.get("target")), variables)
        value = COMMON.service_common_requirements_metadata(cfg, cfg.get("name", entry["name"]))
        CHECK.PODMAN.podman_service_normalize(value, value["name"])
        assert not {"environment", "infisical", "secrets", "command"} & value.keys()


def test_initial_cutover_and_changed_ownership_keep_strict_actual_service_acknowledgements():
    cfg = metadata("wallos")
    for value in [None, False, "true", 1]:
        with pytest.raises(AnsibleFilterError):
            COMMON.service_common_requirements_validate(cfg, "wallos", "deploy", {"services_mgt_backend_acl_ready": value})
    proof = {"metadata": cfg, "acl": ["mgt_backends"], "ownership_transition": True}
    for action in ["deploy", "update", "recreate", "bootstrap"]:
        assert COMMON.service_common_requirements_validate(cfg, "wallos", action, {}, proof=proof)
    bad = proof | {"ownership_transition": False}
    with pytest.raises(AnsibleFilterError, match="services_rootless_data_ready"):
        COMMON.service_common_requirements_validate(cfg, "wallos", "recreate", {}, proof=bad)
    assert COMMON.service_common_requirements_validate(
        cfg, "wallos", "recreate", {"services_rootless_data_ready": {"wallos": True}}, proof=bad
    )
    for change in [{"name": "other"}, {"deploy": {"host": "other"}}]:
        with pytest.raises(AnsibleFilterError):
            COMMON.service_common_requirements_validate(cfg | change, "wallos", "deploy", {}, proof=proof)
    for action in ["remove", "drift"]:
        assert COMMON.service_common_requirements_validate(cfg, "wallos", action, {})
    assert COMMON.service_common_requirements_validate(cfg, "wallos", "deploy", {}, check_mode=True)
    assert COMMON.service_common_requirements_validate(cfg, "wallos", "deploy", {}, execution_only=True)


@pytest.mark.parametrize("mode", ["accepted", "missing-policy", "stale-port", "noncompliant", "initial", "initial-authorized"])
def test_actual_role_precedes_stop_and_caches_only_this_service_operation(tmp_path, mode):
    cfg, variables, policy, observed = worker_fixture()
    if mode == "stale-port":
        policy["ports"] = [cfg["ports"]["web_backend"]["published"] - 1]
    if mode == "initial-authorized":
        variables["services_worker_backend_acl_ready"] = True
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({"policy": policy, "observed": observed, "mode": mode}))
    events = tmp_path / "events"
    stopped = tmp_path / "stopped"
    actions = tmp_path / "actions"
    actions.mkdir()
    # Execute the production action and role, replacing only remote module I/O.
    (actions / "service_operational_check.py").write_text(f"""
import base64, importlib.util, json
from pathlib import Path
spec=importlib.util.spec_from_file_location('actual_check', {str(ROOT / "ansible/action_plugins/service_operational_check.py")!r})
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
fixture=json.loads(Path({str(fixture)!r}).read_text())
class ActionModule(m.ActionModule):
    def _execute_module(self, module_name=None, module_args=None, **kwargs):
        args=module_args
        if module_name=='ansible.builtin.stat':
            exists=fixture['mode']!='missing-policy'
            path=args['path']
            return {{'stat':{{'exists':exists,'isreg':True,'isdir':True,'isblk':True,'islnk':False,
                             'uid':0,'gid':0,'mode':'0644','dev':2049,'device_type':2049}}}}
        if module_name=='ansible.builtin.slurp':
            value='21 1 8:1 / /boot rw - vfat /dev/fixture rw,uid=0,gid=0' if args['src']=='/proc/self/mountinfo' else json.dumps(fixture['policy'])
            return {{'content':base64.b64encode(value.encode()).decode()}}
        if module_name=='ansible.builtin.command':
            argv=args['argv']
            assert not Path({str(stopped)!r}).exists(), 'late audit/runtime probe after stop'
            with Path({str(events)!r}).open('a') as out:out.write(json.dumps(argv)+chr(10))
            if argv[0]=='docker':
                if fixture['mode'].startswith('initial'):return {{'rc':1,'stderr':'no such service: NONPRODUCTION'}}
                return {{'rc':0,'stdout':json.dumps(fixture['observed'])}}
            if argv[0]=='ip':return {{'rc':0,'stdout':json.dumps([{{'addr_info':[{{'local':'192.0.2.11'}}]}}])}}
            if 'check' in argv:return {{'rc':0,'stdout':json.dumps({{'compliant':fixture['mode']!='noncompliant','families':[4,6],'watch_running':True}})}}
        raise AssertionError('Unexpected remote operation: '+module_name)
""")
    variables = {k: variables[k] for k in ["services_controller_host", "services_storage_host", "services_plex_host"]}
    variables.update(
        service_common_service=cfg,
        service_common_name="whisparr",
        service_common_action="recreate",
        service_common_execution_only=False,
        service_common_preflight_proof={},
    )
    if mode == "initial-authorized":
        variables["services_worker_backend_acl_ready"] = True
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(
        yaml.safe_dump(
            {
                "all": {
                    "hosts": {
                        "mgt": {"ansible_connection": "local", "local_ip": "192.0.2.10"},
                        "unraid": {"ansible_connection": "local", "local_ip": "192.0.2.11"},
                        "plex": {"ansible_connection": "local", "local_ip": "192.0.2.12"},
                    }
                }
            }
        )
    )
    tasks = [
        {"ansible.builtin.include_role": {"name": "service_common", "tasks_from": "operational_requirements"}},
        {"ansible.builtin.set_fact": {"saved_before_stop": "{{ service_common_prerequisite_proof }}"}},
        {"ansible.builtin.copy": {"dest": str(stopped), "content": "NONPRODUCTION simulated stop", "mode": "0600"}},
    ]
    if mode == "accepted":
        tasks.append(
            {
                "ansible.builtin.include_role": {"name": "service_common", "tasks_from": "operational_requirements"},
                "vars": {"service_common_preflight_proof": "{{ saved_before_stop }}"},
            }
        )
    play = tmp_path / "play.yml"
    play.write_text(yaml.safe_dump([{"hosts": "mgt", "gather_facts": False, "vars": variables, "tasks": tasks}]))
    config = tmp_path / "ansible.cfg"
    config.write_text(
        f"[defaults]\ninventory={inventory}\nroles_path={ROOT}/ansible/roles\naction_plugins={actions}\nlibrary={ROOT}/ansible/library\nvars_plugins_enabled=\nstdout_callback=default\n"
    )
    result = subprocess.run(
        [str(Path(sys.executable).with_name("ansible-playbook")), "-i", str(inventory), str(play)],
        env={
            **os.environ,
            "ANSIBLE_CONFIG": str(config),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
            "ANSIBLE_REMOTE_TEMP": str(tmp_path / "remote"),
        },
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    passed = mode in {"accepted", "initial-authorized"}
    assert (result.returncode == 0) == passed, output
    assert stopped.exists() == passed
    rows = [json.loads(row) for row in events.read_text().splitlines()] if events.exists() else []
    assert sum("service" in row and "inspect" in row for row in rows) == 1
    assert sum("check" in row for row in rows) == (0 if mode in {"initial", "initial-authorized", "missing-policy", "stale-port"} else 1)
    if mode == "initial":
        assert "services_worker_backend_acl_ready" in output


@pytest.mark.parametrize("bootstrap", [False, True])
def test_actual_mgt_audit_and_static_bootstrap_need_no_provider_or_replacement(tmp_path, bootstrap):
    defaults = yaml.safe_load((ROOT / "ansible/roles/netbox/defaults/main.yml").read_text())
    cfg = metadata("wallos")
    if bootstrap:
        raw = defaults["netbox_podman_services"][1]
        variables = {
            **defaults,
            "inventory_hostname": "localhost",
            "local_ip": "192.0.2.10",
            "container_host_appdata_root": "/opt",
            "container_host_puid": "1000",
            "container_host_pgid": "1000",
        }
        cfg = COMMON.service_common_requirements_metadata(raw | {"runtime": "podman"}, "netbox-redis")
        for _ in range(6):
            cfg = FIXTURE.resolve(cfg, variables)
    unit = cfg["name"]
    account = cfg["deploy"]["execution"]["host_user"]
    norm = CHECK.PODMAN.podman_service_normalize(cfg, unit)
    state = {
        "version": 2,
        "managed_by": "podman_services",
        "service": unit,
        "unit_name": unit + ".service",
        "mode": "rootless",
        "host_user": account,
        "uid": "2019",
        "gid": "2019",
        "home": "/var/lib/" + account,
        "quadlet_dir": "/var/lib/" + account + "/.config/containers/systemd",
    }
    if bootstrap:
        records = [
            {"name": unit, "ports": cfg["ports"], "host": "mgt", "account": account, "bootstrap": "netbox"},
            {
                "name": "netbox",
                "ports": {"recovery": {"published": 8000, "target": 8080}},
                "host": "mgt",
                "account": "podman-netbox",
                "bootstrap": "netbox",
            },
        ]
        plan = CHECK.MGT.build_plan({}, "mgt", lambda value, defaults: value, records)
        plan["endpoints"] = [e for e in plan["endpoints"] if e["service"] == unit]
    else:
        plan = CHECK.MGT.build_plan({unit: cfg}, "mgt", lambda value, defaults: value, [])
    caller = "netbox" if bootstrap else "traefik"
    policy = {
        "schema": 1,
        "backend": "nf_tables",
        "inventory_host": "mgt",
        "inventory_address": "192.0.2.10",
        "inputs_verified": True,
        "endpoints": plan["endpoints"],
        "principals": plan["principals"],
        "callers": {
            caller: [
                {"kind": "local", "phase": "podman", "account": "podman-" + caller, "uid": 2018, "verified": True, "restart_verified": True}
            ]
        },
    }
    marker = {key: state[key] for key in ["managed_by", "service", "host_user", "uid", "gid", "home"]}
    files = {
        "/var/lib/podman-services/" + unit + ".yml": [0, yaml.safe_dump(state)],
        "/var/lib/podman-services/accounts/" + account + ".yml": [0, yaml.safe_dump(marker)],
        state["quadlet_dir"] + "/" + unit + ".container": [2019, FIXTURE.render_container(norm)],
        "/etc/skynet-mgt-firewall/policy.json": [0, json.dumps(policy)],
        "/etc/skynet-mgt-firewall/policy.py": [0, "# NONPRODUCTION helper fixture"],
    }
    for mount in norm["container"].get("mounts", []):
        files[mount["source"]] = [2019, None]
    fixture = tmp_path / "files.json"
    fixture.write_text(json.dumps(files))
    events = tmp_path / "events"
    actions = tmp_path / "actions"
    actions.mkdir()
    (actions / "service_operational_check.py").write_text(f"""
import base64,importlib.util,json
from pathlib import Path
spec=importlib.util.spec_from_file_location('actual_check',{str(ROOT / "ansible/action_plugins/service_operational_check.py")!r})
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
files=json.loads(Path({str(fixture)!r}).read_text())
class ActionModule(m.ActionModule):
    def _execute_module(self,module_name=None,module_args=None,**kwargs):
        a=module_args
        if module_name=='ansible.builtin.stat':
            p=a['path'];v=files.get(p)
            return {{'stat':{{'exists':v is not None,'uid':v[0] if v else 0,'isreg':v is not None and v[1] is not None,'isdir':v is not None and v[1] is None,'islnk':False,'mode':'0644'}}}}
        if module_name=='ansible.builtin.slurp':return {{'content':base64.b64encode(files[a['src']][1].encode()).decode()}}
        argv=a['argv']
        with Path({str(events)!r}).open('a') as f:f.write(json.dumps(argv)+chr(10))
        if argv[0]=='getent':return {{'rc':0,'stdout':{(account + ":x:2019:2019::/var/lib/" + account + ":/usr/sbin/nologin")!r}}}
        if argv[0]=='ip':return {{'rc':0,'stdout':'[{{"addr_info":[{{"local":"192.0.2.10"}}]}}]'}}
        if 'check' in argv:return {{'rc':0,'stdout':'{{"compliant":true,"pending":[],"families":[4,6]}}'}}
        if argv[0]=='systemctl':return {{'rc':0,'stdout':'active'}}
        raise AssertionError('Unexpected runtime I/O')
""")
    variables = {
        "service_common_service": cfg,
        "service_common_name": unit,
        "service_common_action": "recreate",
        "service_common_execution_only": False,
        "local_ip": "192.0.2.10",
    }
    host = "localhost" if bootstrap else "mgt"
    if not bootstrap:
        variables["services_controller_host"] = "mgt"
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(yaml.safe_dump({"all": {"hosts": {host: {"ansible_connection": "local", "local_ip": "192.0.2.10"}}}}))
    config = tmp_path / "ansible.cfg"
    config.write_text(
        f"[defaults]\ninventory={inventory}\nroles_path={ROOT}/ansible/roles\naction_plugins={actions}\nlibrary={ROOT}/ansible/library\nvars_plugins_enabled=\nstdout_callback=default\n"
    )
    play = tmp_path / "play.yml"
    play.write_text(
        yaml.safe_dump(
            [
                {
                    "hosts": host,
                    "gather_facts": False,
                    "vars": variables,
                    "tasks": [{"ansible.builtin.include_role": {"name": "service_common", "tasks_from": "operational_requirements"}}],
                }
            ]
        )
    )
    result = subprocess.run(
        [str(Path(sys.executable).with_name("ansible-playbook")), "-i", str(inventory), str(play)],
        env={
            **os.environ,
            "ANSIBLE_CONFIG": str(config),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
            "ANSIBLE_REMOTE_TEMP": str(tmp_path / "remote"),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    rows = [json.loads(row) for row in events.read_text().splitlines()]
    assert sum("check" in row for row in rows) == 1
    assert not any(row[0] in {"docker", "podman"} for row in rows)


@pytest.mark.parametrize("case", ["vfat", "posix", "nested", "bind", "owner", "device", "symlink", "path", "ubuntu", "mgt"])
def test_installed_metadata_trust_is_scoped_to_the_unraid_flash_mount(case):
    import base64

    action = object.__new__(CHECK.ActionModule)
    mount = "21 1 8:1 / /boot rw - vfat /dev/fixture rw,uid=0,gid=0"
    if case == "posix":
        mount = mount.replace("vfat", "ext4")
    elif case == "nested":
        mount += "\n22 21 8:2 / /boot/config rw - ext4 /dev/other rw"
    elif case == "bind":
        mount = mount.replace("8:1 / /boot", "8:1 /elsewhere /boot")
    elif case == "owner":
        mount = mount.replace("uid=0", "uid=1000")

    def module(name, args):
        if name.endswith("slurp"):
            assert args["src"] == "/proc/self/mountinfo"
            return {"content": base64.b64encode(mount.encode()).decode()}
        path = args["path"]
        flash = path.startswith("/boot")
        return {
            "stat": {
                "exists": True,
                "isreg": True,
                "isdir": True,
                "isblk": True,
                "islnk": case == "symlink" and path == "/boot/config",
                "uid": 0,
                "gid": 0,
                "mode": "0777" if flash or case in {"ubuntu", "mgt"} else "0644",
                "dev": 2050 if case == "device" else 2049,
                "device_type": 2049,
            }
        }

    action.module = module
    if case in {"ubuntu", "mgt"}:
        path = "/etc/skynet-worker-backend-firewall/policy.json" if case == "ubuntu" else "/etc/skynet-mgt-firewall/policy.json"
        with pytest.raises(ValueError, match="ownership/mode"):
            action.owned(path)
    elif case == "vfat":
        device = action.unraid_flash_device()
        for path in CHECK.UNRAID_FILES:
            assert action.owned(path, flash_device=device)["mode"] == "0777"
        # A regular POSIX metadata check is still strict, even on Unraid.
        with pytest.raises(ValueError, match="ownership/mode"):
            action.owned(next(iter(CHECK.UNRAID_FILES)))
    else:
        with pytest.raises(ValueError):
            device = action.unraid_flash_device()
            action.owned("/boot/config/unexpected/policy.json" if case == "path" else next(iter(CHECK.UNRAID_FILES)), flash_device=device)
