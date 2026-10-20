"""Execute the real batch/helper with synthetic evidence and kernel-enforced isolation."""

from __future__ import annotations

import importlib.util
import json
import os
import select
import shlex
import shutil
import subprocess
import time
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/haproxy_operator"
CALLERS = ["autobrr", "gotify", "vaultwarden", "infisical", "authelia", "seerr", "prometheus", "forgejo"]
CANDIDATE = "haproxy-candidate-04-20261008T150348Z-1717643.json"
NATIVE = "native-hooks-20261008T145711Z-1717643.log"


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


@pytest.fixture(scope="module")
def restrictor(tmp_path_factory):
    root = tmp_path_factory.mktemp("haproxy-isolation-build")
    compiler = shutil.which("cc")
    if not compiler:
        pytest.skip("C compiler unavailable for mandatory kernel isolation")
    result = subprocess.run(
        [compiler, "-O2", "-Wall", "-Werror", str(FIXTURES / "restrict.c"), "-o", str(root / "restrict")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return root / "restrict"


class Workflow:
    @classmethod
    def prepared_copy(cls, source, root):
        result = cls.__new__(cls)
        shutil.copytree(source.root, root, symlinks=True)
        # Rebase only our public fixture text, never a production path/file.
        for path in root.rglob("*"):
            if path.is_file() and not path.is_symlink() and path.suffix in {"", ".json", ".jsonl", ".yml", ".sh", ".py", ".log", ".cfg"}:
                data = path.read_bytes()
                if str(source.root).encode() in data:
                    path.write_bytes(data.replace(str(source.root).encode(), str(root).encode()))
        result.root, result.restrictor = root, source.restrictor
        result.repo = root / "repo"
        result.handoff = root / "handoff"
        result.batch = result.handoff / "cutover-batch-04-tested"
        result.env = {k: v.replace(str(source.root), str(root)) for k, v in source.env.items()}
        result.original_config = source.original_config
        return result

    def __init__(self, root, restrictor):
        self.root, self.restrictor = root, restrictor
        root.mkdir(mode=0o700)
        self.repo = root / "repo"
        self.handoff = root / "handoff"
        self.handoff.mkdir(mode=0o700)
        (root / "forgejo").mkdir(mode=0o700)
        (root / "haproxy").mkdir(mode=0o700)
        self.batch = self.handoff / "cutover-batch-04-tested"
        for name in [
            "ansible/operator/haproxy-cutover-batch.sh",
            "ansible/operator/haproxy-cutover.py",
            "ansible/operator/haproxy-policy-rollback.sh",
            "ansible/operator/mgt-operator.py",
            "ansible/operator/prepare-native-operator.sh",
            "ansible/operator/skynet_pg_prepare.slice",
            "ansible/operator/skynet_pg_recovery.slice",
            "ansible/roles/service_firewall/files/transactions.py",
            "ansible/roles/service_firewall/files/mgt-firewall.py",
            "ansible/roles/service_firewall/files/haproxy-preflight.py",
            "ansible/roles/service_firewall/files/worker-backend-firewall.py",
            "ansible/roles/service_common/templates/configs/haproxy.cfg.j2",
            "migrator/guides/haproxy.md",
            "docs/mgt-native-operator.md",
        ]:
            dest = self.repo / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, dest)
        bindir = root / "bin"
        bindir.mkdir()
        for name in [
            "sudo",
            "docker",
            "podman",
            "skynet",
            "getent",
            "systemctl",
            "systemd-run",
            "ip",
            "nsenter",
            "runuser",
            "iptables",
            "iptables-save",
            "ss",
            "sleep",
        ]:
            shutil.copyfile(FIXTURES / "commands.py", bindir / name)
            (bindir / name).chmod(0o755)
        packages = root / "packages"
        packages.mkdir()
        shutil.copyfile(FIXTURES / "sitecustomize.py", packages / "sitecustomize.py")
        for name in ["jinja2", "yaml", "markupsafe"]:
            spec = importlib.util.find_spec(name)
            shutil.copytree(Path(spec.origin).parent, packages / name, ignore=shutil.ignore_patterns("__pycache__"))
        envdir = root / "venv/bin"
        envdir.mkdir(parents=True)
        (envdir / "python").symlink_to("/usr/bin/python3")
        self.env = {
            "PATH": str(bindir) + ":/usr/bin:/bin",
            "FIXTURE_ROOT": str(root),
            "PYTHONPATH": str(packages),
            "VIRTUAL_ENV": str(root / "venv"),
            "PLAYBOOK": str(self.repo / "ansible/playbook.yml"),
            "LANG": "C.UTF-8",
            "HOME": str(root / "home"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        self.state = {
            "excluded": False,
            "original_listener": True,
            "policy": "homepage",
            "probe": False,
            "unit": False,
            "unit_active": False,
            "container": False,
            "generation": dict.fromkeys(CALLERS, 0),
            "rules": [],
        }
        dump(root / "state.json", self.state)
        proxy = [
            "/usr/bin/docker-proxy",
            "-proto",
            "tcp",
            "-host-ip",
            "0.0.0.0",
            "-host-port",
            "5432",
            "-container-ip",
            "198.51.100.200",
            "-container-port",
            "5432",
            "",
        ]
        (root / "proxy-argv").write_bytes("\0".join(proxy).encode())
        (root / "proxy-comm").write_text("docker-proxy\n")
        cfg = root / "apps/haproxy"
        cfg.mkdir(parents=True)
        (cfg / "haproxy.cfg").write_text("original native-independent config\n")
        self.original_config = (cfg / "haproxy.cfg").read_bytes()
        (root / "untouched").write_text("unrelated fixture\n")
        definition = yaml.safe_load((ROOT / "ansible/group_vars/all/services/haproxy.yml").read_text())["haproxy"]
        self.provider = {
            "id": "fixture-provider",
            "name": "haproxy_haproxy",
            "image": definition["image"] + "@sha256:" + "0" * 64,
            "configs": [{"ConfigName": "haproxy_cfg-3b164cbae242"}],
            "ports": [{"PublishedPort": 5432, "TargetPort": 5432, "Protocol": "tcp", "PublishMode": "host"}],
            "vips": [{"NetworkID": "fixture-overlay", "Addr": "198.51.100.144/24"}],
            "constraints": ["node.labels.haproxy == true"],
        }
        dump(root / "provider.json", self.provider)
        self.home = {
            "kind": "container",
            "runtime": "docker",
            "phase": "docker",
            "path": "bridge",
            "selector": "observed_traefik",
            "verified": True,
            "restart_verified": True,
            "physdev_verified": True,
        }
        accepted = {
            "mgt_firewall_active_endpoints": ["homepage/backend"],
            "mgt_firewall_callers": {"traefik": [self.home]},
            "mgt_firewall_inputs_verified": True,
        }
        dump(root / "accepted.json", accepted)
        (self.handoff / "homepage-inputs.yml").write_text(yaml.safe_dump(accepted))
        dump(
            self.handoff / "homepage-policy.json",
            {
                "schema": 1,
                "backend": "nf_tables",
                "endpoints": [{"ids": ["homepage/backend"], "port": 13000, "purpose": "backend", "callers": ["traefik"]}],
                "callers": accepted["mgt_firewall_callers"],
                "inputs_verified": True,
                "inventory_host": "manager",
                "inventory_address": "192.0.2.48",
            },
        )
        shutil.copyfile(self.handoff / "homepage-policy.json", root / "installed-policy.json")
        (self.handoff / "homepage-policy.py").write_text("# fixture accepted helper bytes\n")
        lines = []
        for context in ["controller", "recovery"]:
            parent = "skynet_pg_" + ("prepare" if context == "controller" else "recovery") + ".slice"
            for hook in ["mangle", "filter"]:
                lines.append(f"{context} ordinary root: {hook} OUTPUT=0 (expected 0)")
            for attempt in [1, 2]:
                lines.append(
                    json.dumps({"binding_cgroup": parent, "cgroup": f"{parent}/child-{attempt}.service", "process_uid": 0, "socket_uid": 0})
                )
                lines.append(f"{context} attempt {attempt}: mangle OUTPUT=3; filter OUTPUT=6")
        (self.handoff / NATIVE).write_text("\n".join(lines))
        pg = [n for n in CALLERS if n != "prometheus"] + ["romm", "controller", "recovery"]
        principals = {
            n: {
                "inventory_hosts": "worker" if n == "romm" else "manager",
                "future_runtime": "docker",
                "future_account": "podman-forgejo" if n == "forgejo" else None,
            }
            for n in pg + ["prometheus", "traefik"]
        }
        endpoints = [
            {"ids": ["homepage/backend"], "port": 13000, "purpose": "backend", "callers": ["traefik"]},
            {"ids": ["haproxy/postgres"], "port": 5432, "purpose": "declared PostgreSQL applications and recovery", "callers": pg},
            {"ids": ["haproxy/metrics"], "port": 18405, "purpose": "metrics", "callers": ["prometheus"]},
        ]
        policy = {
            "schema": 1,
            "backend": "nf_tables",
            "inventory_host": "manager",
            "inventory_address": "192.0.2.48",
            "inputs_verified": False,
            "callers": {},
            "principals": principals,
            "endpoints": endpoints,
        }
        stage = {
            "controller": "manager",
            "workers": ["worker", "media"],
            "plan": {"principals": principals, "endpoints": endpoints},
            "policy": policy,
            "definition": {"image": definition["image"], "settings": definition["settings"], "paths": [{"path": str(cfg)}]},
            "render": {"groups": {"tags_postgres": ["pg-fixture"]}, "hostvars": {"pg-fixture": {"local_ip": "192.0.2.101"}}},
        }
        dump(root / "stage.json", stage)
        reports = []
        for host, address in [("manager", "192.0.2.48"), ("worker", "192.0.2.20"), ("media", "192.0.2.59")]:
            reports.append(
                {
                    "host": host,
                    "identity": {"hostname": "fixture-" + host, "boot_id": "fixture-" + host + "-boot"},
                    "addresses": [address],
                    "containers": [],
                    "accounts": {},
                    "providers": [self.provider] if host == "manager" else [],
                    "pending": [],
                    "topology": {
                        "swarm": {"node_id": host},
                        "services": [
                            {
                                "name": "haproxy_haproxy",
                                "vips": self.provider["vips"],
                                "tasks": [{"node_id": node, "state": "running", "networks": []} for node in ["manager", "worker", "media"]],
                            }
                        ]
                        if host == "manager"
                        else [],
                        "networks": [],
                    },
                }
            )
        for name in CALLERS[:-1]:
            binding = {
                "kind": "container",
                "runtime": "docker",
                "phase": "docker",
                "path": "bridge",
                "verified": False,
                "restart_verified": False,
                "physdev_verified": False,
            }
            binding.update(
                {"compose": {"project": "observed-project", "service": "infisical"}} if name == "infisical" else {"selector": "app_" + name}
            )
            reports[0]["containers"].append(
                {
                    "name": name,
                    "swarm": None if name == "infisical" else "app_" + name,
                    "project": "observed-project" if name == "infisical" else None,
                    "service": "infisical" if name == "infisical" else None,
                    "binding": binding,
                    "identities": [{"kind": "container", "address": "198.51.100.10"}],
                    "pending": [],
                    "destinations": [] if name == "prometheus" else [{"destination": "198.51.100.144", "port": 5432}],
                }
            )
        reports[0]["accounts"] = {
            "podman-forgejo": {"uid": 1004, "containers": [{"destinations": [{"destination": "192.0.2.48", "port": 5432}]}]}
        }
        reports[1]["containers"] = [
            {"name": "romm", "swarm": "app_romm", "service": None, "destinations": [{"destination": "198.51.100.144", "port": 5432}]}
        ]
        dump(root / "reports.json", reports)
        # Supplied evidence layout is real, but every value is a non-production fixture.
        dump(self.handoff / CANDIDATE, accepted)
        dump(self.handoff / (CANDIDATE + ".metadata.json"), reports)
        dump(self.handoff / (CANDIDATE + ".pending.json"), [])

    def events(self):
        return [json.loads(line) for line in (self.root / "journal.jsonl").read_text().splitlines()]

    def operator(self, operation, prompt, scenario):
        if operation == "prepare" and prompt == 2:
            path = self.batch / "working-policy.json"
            v = json.loads(path.read_text())
            for name in CALLERS:
                for binding in v["mgt_firewall_callers"][name]:
                    for key in binding:
                        if key.endswith("verified"):
                            binding[key] = True
            dump(path, v)
            path = self.batch / "deployment-inputs.json"
            v = json.loads(path.read_text())
            v["services_rootless_data_ready"]["haproxy"] = True
            dump(path, v)
        if operation == "maintenance" and prompt == 2:
            path = self.batch / "working-policy.json"
            v = json.loads((self.batch / "worker-route-proposal.json").read_text())
            for binding in v["mgt_firewall_callers"]["romm"]:
                for key in ["route_verified", "verified", "restart_verified"]:
                    binding[key] = True
            v["mgt_firewall_inputs_verified"] = True
            dump(path, v)
        if operation == "maintenance" and prompt == 3:
            if scenario == "probe-expired-review":
                state = json.loads((self.root / "state.json").read_text())
                state["probe"] = False
                dump(self.root / "state.json", state)
            if scenario != "acl-not-accepted":
                path = self.batch / "deployment-inputs.json"
                v = json.loads(path.read_text())
                v["services_mgt_backend_acl_ready"] = True
                dump(path, v)
        with (self.root / "journal.jsonl").open("a") as stream:
            stream.write(json.dumps({"kind": "operator_fixture_evidence", "operation": operation, "prompt": prompt}) + "\n")

    def run(self, operation, scenario="success"):
        script = (
            self.repo / "ansible/operator/haproxy-cutover-batch.sh"
            if operation in {"prepare", "resume", "continue"}
            else self.batch / "haproxy-cutover-batch.sh"
        )
        command = [
            str(self.restrictor),
            str(self.root),
            "/bin/bash",
            str(script),
            operation,
            str(self.handoff if operation == "prepare" else self.batch),
        ]
        proc = subprocess.Popen(
            command,
            env={**self.env, "SCENARIO": scenario},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            close_fds=True,
        )
        collected = b""
        seen = 0
        deadline = time.monotonic() + 50
        marker = b"Type ACCEPT only after the stated evidence is recorded; anything else stops: "
        while True:
            if time.monotonic() > deadline:
                proc.kill()
                raise AssertionError("isolated runner timeout: " + collected.decode())
            readable, _, _ = select.select([proc.stdout], [], [], 0.1)
            if readable:
                chunk = os.read(proc.stdout.fileno(), 65536)
                if not chunk:
                    break
                collected += chunk
                # EXIT reprints the log, including prompts, after stdin is no
                # longer consumed. Never mistake those for new operator work.
                count = collected.count(marker)
                while seen < count and proc.poll() is None:
                    seen += 1
                    if seen > (2 if operation == "prepare" else 5):
                        break
                    self.operator(operation, seen, scenario)
                    try:
                        proc.stdin.write(b"ACCEPT\n")
                        proc.stdin.flush()
                    except BrokenPipeError:
                        break
            if proc.poll() is not None:
                collected += proc.stdout.read()
                break
        status = proc.wait(timeout=5)
        proc.stdin.close()
        proc.stdout.close()
        output = collected.decode()
        assert "Private output log:" in output, output
        logs = list(self.batch.glob(operation + "-*.log"))
        assert logs and all(p.stat().st_mode & 0o077 == 0 for p in logs)
        return status, output


@pytest.fixture
def workflow(tmp_path, restrictor):
    return Workflow(tmp_path / "isolated", restrictor)


@pytest.fixture(scope="module")
def prepared_template(tmp_path_factory, restrictor):
    source = Workflow(tmp_path_factory.mktemp("haproxy-prepared") / "isolated", restrictor)
    status, output = source.run("prepare")
    assert status == 0, output
    return source


@pytest.fixture
def prepared_workflow(tmp_path, prepared_template):
    return Workflow.prepared_copy(prepared_template, tmp_path / "isolated")


@pytest.fixture
def interrupted_workflow(prepared_workflow):
    w = prepared_workflow
    state = json.loads((w.root / "state.json").read_text())
    state.update(excluded=True, original_listener=False, policy="complete", probe=True)
    dump(w.root / "state.json", state)
    values = json.loads((w.batch / "working-policy.json").read_text())
    for bindings in values["mgt_firewall_callers"].values():
        for binding in bindings:
            for key in binding:
                if key.endswith("verified"):
                    binding[key] = True
    values["mgt_firewall_inputs_verified"] = True
    values["mgt_firewall_callers"]["romm"] = [
        {
            "kind": "elsewhere",
            "phase": "docker",
            "inventory_host": "worker",
            "verified": True,
            "restart_verified": True,
            "route_verified": True,
        }
    ]
    dump(w.batch / "working-policy.json", values)
    inputs = json.loads((w.batch / "deployment-inputs.json").read_text())
    inputs["services_mgt_backend_acl_ready"] = True
    dump(w.batch / "deployment-inputs.json", inputs)
    (w.batch / "rollback-state.sh").write_text(
        'declare -- exclusion_started="true"\ndeclare -- policy_started="true"\n'
        'declare -- deployment_started="false"\ndeclare -- probe_unit="skynet-haproxy-acceptance-fixture.service"\n'
    )
    return w


@pytest.mark.parametrize(
    "invalid",
    ["state", "duplicate", "acl", "policy", "endpoints", "stopped-container", "provider", "image", "probe-owner", "ipv6-listener"],
)
def test_continuation_rejects_incompatible_stage_without_lifecycle_replay(interrupted_workflow, invalid):
    w = interrupted_workflow
    scenario = "success"
    if invalid == "state":
        path = w.batch / "rollback-state.sh"
        path.write_text(path.read_text().replace('deployment_started="false"', 'deployment_started="true"'))
    elif invalid == "duplicate":
        path = w.batch / "rollback-state.sh"
        path.write_text(path.read_text() + 'declare -- policy_started="true"\n')
    elif invalid == "acl":
        values = json.loads((w.batch / "deployment-inputs.json").read_text())
        values["services_mgt_backend_acl_ready"] = "true"
        dump(w.batch / "deployment-inputs.json", values)
    elif invalid == "policy":
        state = json.loads((w.root / "state.json").read_text())
        state["policy"] = "homepage"
        dump(w.root / "state.json", state)
    elif invalid == "endpoints":
        values = json.loads((w.batch / "working-policy.json").read_text())
        values["mgt_firewall_active_endpoints"] = ["homepage/backend"]
        dump(w.batch / "working-policy.json", values)
    elif invalid == "stopped-container":
        scenario = "continue-stopped-container"
    elif invalid == "provider":
        provider = json.loads((w.root / "provider.json").read_text())
        provider["image"] = "incompatible-fixture-image"
        dump(w.root / "provider.json", provider)
    elif invalid == "image":
        scenario = "image-query-error"
    elif invalid == "probe-owner":
        scenario = "probe-owner-mismatch"
    elif invalid == "ipv6-listener":
        scenario = "continue-ipv6-listener"
    before = len(w.events())
    code, output = w.run("continue", scenario)
    assert code != 0, output
    kinds = [e["kind"] for e in w.events()[before:]]
    assert not set(kinds) & {"constraint_add", "constraint_remove", "policy_apply", "restore_homepage", "deployment"}
    assert kinds.count("probe_stop") == (1 if invalid == "ipv6-listener" else 0)


@pytest.mark.parametrize(
    "scenario,status",
    [
        ("success", 0),
        ("expired", 0),
        ("deployment-before-write", 35),
        ("deployment-after-write", 36),
        ("acceptance-failed", 1),
        ("rollback-unit", 36),
        ("continue-interrupt", 143),
        ("continue-terminal-error", 1),
        ("continue-final-output-error", 1),
    ],
)
def test_continuation_real_tail_exit_trap_and_scoped_rollback(interrupted_workflow, scenario, status):
    w = interrupted_workflow
    if scenario == "expired":
        state = json.loads((w.root / "state.json").read_text())
        state["probe"] = False
        dump(w.root / "state.json", state)
    if scenario == "continue-terminal-error":
        script = w.repo / "ansible/operator/haproxy-cutover-batch.sh"
        text = script.read_text()
        script.write_text(
            text.replace(
                "announce() {", 'announce() { if [[ "$operation" == continue && "$deployment_started" == true ]]; then exec 3>&-; fi;'
            )
        )
    if scenario == "continue-final-output-error":
        script = w.repo / "ansible/operator/haproxy-cutover-batch.sh"
        text = script.read_text()
        script.write_text(
            text.replace(
                "printf '%s\\n' \"$*\" >&3; }",
                "printf '%s\\n' \"$*\" >&3; if [[ \"$*\" == 'Maintenance sequence completed;'* ]]; then exec 3>&-; fi; }",
            )
        )
    before = len(w.events())
    inputs = (w.batch / "deployment-inputs.json").read_bytes()
    policy = (w.batch / "working-policy.json").read_bytes()
    code, output = w.run("continue", "success" if scenario == "expired" else scenario)
    assert code == status, output
    events = w.events()[before:]
    kinds = [e["kind"] for e in events]
    assert not set(kinds) & {"constraint_add", "policy_apply", "image_pull", "caller_replace", "native_probe", "probe_start"}
    assert (w.batch / "deployment-inputs.json").read_bytes() == inputs
    assert (w.batch / "working-policy.json").read_bytes() == policy
    state = json.loads((w.root / "state.json").read_text())
    assert state["rules"] == []
    assert kinds.count("deployment") == 1
    assert kinds.count("probe_stop") == (0 if scenario == "expired" else 1)
    free_checks = [e for e in events if e["kind"] == "command" and e["name"] == "ss" and "-lnt" in e["argv"]]
    assert {arg for e in free_checks for arg in e["argv"] if arg in {"-4", "-6"}} == {"-4", "-6"}
    if status == 0:
        assert state["excluded"] and state["policy"] == "complete" and state["unit_active"]
        assert kinds.count("haproxy_restart") == 1
        assert len([e for e in events if e.get("operation") == "continue" and e.get("kind") == "operator_fixture_evidence"]) == 2
    else:
        assert list(w.batch.glob("rollback-*.log"))
        if scenario == "rollback-unit":
            assert state["excluded"] and "constraint_remove" not in kinds
        else:
            assert not state["excluded"] and state["policy"] == "homepage" and not state["unit_active"]
            assert kinds.index("restore_homepage") < kinds.index("constraint_remove")
            assert (w.root / "apps/haproxy/haproxy.cfg").read_bytes() == w.original_config
        log = next(w.batch.glob("continue-*.log")).read_text()
        assert f"Maintenance failed (status {status})" in log


def test_kernel_denies_production_paths_and_all_runtime_sockets(workflow):
    code = """import errno,os,socket
for path in ['/opt/homelab/AGENTS.md','/opt/homelab/ansible/netbox.yml','/opt/ansible/.secrets','/run/docker.sock','/var/run/docker.sock']:
 try: os.open(path,os.O_RDONLY)
 except PermissionError: pass
 except FileNotFoundError: pass
 else: raise AssertionError('production path accessible: '+path)
for family in [socket.AF_UNIX,socket.AF_INET,socket.AF_INET6]:
 try: socket.socket(family)
 except PermissionError: pass
 else: raise AssertionError('socket creation permitted')
print('inherited kernel isolation passed')
"""
    result = subprocess.run(
        [str(workflow.restrictor), str(workflow.root), "/usr/bin/python3", "-c", code],
        env=workflow.env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("account", ["haproxy", "forgejo"])
@pytest.mark.parametrize("failure", [None, "child", "home"])
def test_account_wrapper_changes_private_operator_cwd_before_real_child(workflow, account, failure):
    home = workflow.root / account
    uid = 1011 if account == "haproxy" else 1004
    arguments = ["two words", "", "$(touch must-not-exist)", "*", "--option=value", "line\nbreak"]
    probe = [
        "/usr/bin/python3",
        "-c",
        "import json,os,sys; print(json.dumps({'cwd':os.getcwd(), 'home':os.environ['HOME'], "
        "'runtime':os.environ['XDG_RUNTIME_DIR'], 'bus':os.environ['DBUS_SESSION_BUS_ADDRESS'], "
        "'arguments':sys.argv[2:]})); sys.exit(int(sys.argv[1]))",
        "37" if failure == "child" else "0",
        *arguments,
    ]
    if account == "haproxy":
        source = (workflow.repo / "ansible/operator/haproxy-cutover-batch.sh").read_text()
        start = source.index("haproxy_account() {")
        wrapper = source[start : source.index("\n}\n", start) + 3]
        script = workflow.root / "account-wrapper.sh"
        script.write_text(f"set -eu\nHAPROXY_HOME={shlex.quote(str(home))}\nHAPROXY_UID={uid}\n" + wrapper + '\nhaproxy_account "$@"\n')
        command = ["/bin/bash", str(script), *probe]
    else:
        command = [
            "/usr/bin/python3",
            "-c",
            "import importlib.util,subprocess,sys; "
            "s=importlib.util.spec_from_file_location('actual_cutover',sys.argv[1]); "
            "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
            "sys.exit(subprocess.run(m.account_command('podman-forgejo')+sys.argv[2:],check=False).returncode)",
            str(workflow.repo / "ansible/operator/haproxy-cutover.py"),
            *probe,
        ]
    if failure == "home":
        home.rmdir()
    result = subprocess.run(
        [
            str(workflow.restrictor),
            str(workflow.root),
            "/bin/sh",
            "-c",
            'cd "$1" || exit; shift; exec "$@"',
            "private-operator",
            str(workflow.handoff),
            *command,
        ],
        env=workflow.env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert workflow.handoff.stat().st_mode & 0o777 == 0o700
    assert not (home / "must-not-exist").exists()
    if failure == "home":
        assert result.returncode != 0 and not result.stdout
        assert "cd:" in result.stderr
    else:
        assert result.returncode == (37 if failure == "child" else 0), result.stderr
        assert json.loads(result.stdout) == {
            "cwd": str(home),
            "home": str(home),
            "runtime": f"/run/user/{uid}",
            "bus": f"unix:path=/run/user/{uid}/bus",
            "arguments": arguments,
        }


@pytest.mark.parametrize("scenario", ["mount-writable-root", "mount-missing-rw", "mount-direct-config"])
def test_mount_guard_stops_real_preparation_before_pull_or_caller_replacement(workflow, scenario):
    status, output = workflow.run("prepare", scenario)
    assert status != 0 and "HAProxy handoff:" in output
    kinds = [event["kind"] for event in workflow.events()]
    assert "image_pull" not in kinds and "caller_replace" not in kinds and "constraint_add" not in kinds


@pytest.mark.parametrize(
    "scenario,status",
    [
        ("success", 0),
        ("placement-no-write", 31),
        ("placement-partial-drained", 32),
        ("placement-partial-old", 32),
        ("placement-partial-new", 32),
        ("placement-partial-wrong-target", 32),
        ("placement-partial-extra-port", 32),
        ("policy-before-write", 33),
        ("policy-after-write", 34),
        ("deployment-before-write", 35),
        ("deployment-after-write", 36),
        ("deployment-after-config", 36),
        ("deployment-after-unit", 36),
        ("probe-expired", 3),
        ("probe-expired-review", 3),
        ("acceptance-failed", 1),
        ("acl-not-accepted", 1),
        ("rollback-policy", 34),
        ("rollback-unit", 36),
    ],
)
def test_actual_shell_exit_trap_and_rollback_subprocess(prepared_workflow, scenario, status):
    workflow = prepared_workflow
    before_events = len(workflow.events())
    if scenario == "placement-partial-new":
        (workflow.root / "proxy-comm").write_text("unrelated-listener\n")
    if scenario == "placement-partial-wrong-target":
        path = workflow.root / "proxy-argv"
        path.write_bytes(path.read_bytes().replace(b"198.51.100.200", b"198.51.100.201"))
    code, out = workflow.run("maintenance", scenario)
    assert code == status, out
    events = workflow.events()
    window = events[before_events:]
    kinds = [e["kind"] for e in window]
    state = json.loads((workflow.root / "state.json").read_text())
    assert state["rules"] == [], out
    assert (workflow.root / "untouched").read_text() == "unrelated fixture\n"
    assert [e["caller"] for e in events if e["kind"] == "caller_replace"] == CALLERS
    assert all(e["caller"] in CALLERS for e in events if e["kind"] == "caller_replace")
    assert out.index("Private output log:") < out.index("Maintenance") if "Maintenance" in out else True
    if scenario == "success":
        assert state["excluded"] and state["policy"] == "complete" and state["unit_active"]
        assert "constraint_remove" not in kinds and kinds.index("constraint_add") < kinds.index("policy_apply") < kinds.index("deployment")
        assert kinds.count("haproxy_restart") == 1
    else:
        assert "Maintenance failed" in out and "Private output log:" in out
        assert "constraint_remove" in kinds or scenario in [
            "placement-no-write",
            "placement-partial-new",
            "placement-partial-wrong-target",
            "placement-partial-extra-port",
            "rollback-policy",
            "rollback-unit",
        ]
        if scenario in [
            "placement-partial-new",
            "placement-partial-wrong-target",
            "placement-partial-extra-port",
            "rollback-policy",
            "rollback-unit",
        ]:
            assert "ROLLBACK INCOMPLETE" in out and state["excluded"] and "constraint_remove" not in kinds
        else:
            assert not state["excluded"] and state["policy"] == "homepage" and not state["unit_active"]
            assert (workflow.root / "apps/haproxy/haproxy.cfg").read_bytes() == workflow.original_config
        if scenario == "placement-no-write":
            assert state["original_listener"] and "restore_homepage" not in kinds and "constraint_remove" not in kinds
        if scenario.startswith("placement-"):
            assert "policy_apply" not in kinds and "deployment" not in kinds
        if scenario.startswith("policy-") or scenario in [
            "probe-expired",
            "probe-expired-review",
            "acceptance-failed",
            "acl-not-accepted",
            "rollback-policy",
        ]:
            assert "deployment" not in kinds
        if "restore_homepage" in kinds and "constraint_remove" in kinds:
            assert kinds.index("restore_homepage") < kinds.index("constraint_remove")
    inserts = [e["rule"] for e in events if e["kind"] == "rule_insert"]
    deletes = [e["rule"] for e in events if e["kind"] == "rule_delete"]
    assert sorted(inserts) == sorted(deletes)
    assert all('"-j"' not in rule and '"-g"' not in rule for rule in inserts)


@pytest.mark.parametrize("missing", [True, False, "true"])
def test_missing_false_or_typed_mgt_confirmation_stops_before_placement(prepared_workflow, missing):
    workflow = prepared_workflow
    path = workflow.batch / "working-policy.json"
    values = json.loads(path.read_text())
    if missing is True:
        values["mgt_firewall_callers"]["autobrr"][0].pop("verified")
    else:
        values["mgt_firewall_callers"]["autobrr"][0]["verified"] = missing
    dump(path, values)
    start = len(workflow.events())
    code, out = workflow.run("maintenance")
    assert code == 1, out
    assert not any(e["kind"] == "constraint_add" for e in workflow.events()[start:])


@pytest.mark.parametrize(
    "scenario,status",
    [
        ("bad-producer", 1),
        ("partial-producer", 1),
        ("rule-insert-error", 1),
        ("ss-query-error", 1),
        ("probe-client-error", 1),
        ("node-query-error", 45),
    ],
)
def test_prepare_producer_and_observation_failures_are_not_masked(workflow, scenario, status):
    code, out = workflow.run("prepare", scenario)
    assert code == status, out
    events = workflow.events()
    state = json.loads((workflow.root / "state.json").read_text())
    assert not state["rules"] and not state["excluded"]
    assert not any(e["kind"] == "constraint_add" for e in events)
    if scenario in ["bad-producer", "partial-producer"]:
        assert ("catalog/current image mismatch" if scenario == "bad-producer" else "TypeError") in out
        assert not any(e["kind"] in ["image_pull", "caller_replace"] for e in events)
    if scenario == "rule-insert-error":
        assert not any(e["kind"] == "caller_replace" for e in events)
        assert sum(e["kind"] == "rule_insert" for e in events) == sum(e["kind"] == "rule_delete" for e in events) == 1


def test_exact_manual_cleanup_is_usable_after_observation_delete_failure(workflow):
    status, out = workflow.run("prepare", "rule-delete-error")
    assert status == 1 and "exact observation cleanup failed" in out
    state = json.loads((workflow.root / "state.json").read_text())
    assert len(state["rules"]) == 1 and not any(e["kind"] == "caller_replace" for e in workflow.events())
    log = next(workflow.batch.glob("prepare-*.log")).read_text()
    cleanup = [json.loads(line)["exact_cleanup"] for line in log.splitlines() if line.startswith('{"exact_cleanup":')]
    exact = next(line for line in cleanup if "-t filter" in line)
    result = subprocess.run(
        [str(workflow.restrictor), str(workflow.root), *shlex.split(exact)], env=workflow.env, text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert not json.loads((workflow.root / "state.json").read_text())["rules"]


@pytest.mark.parametrize(
    "field,value", [("ownership", None), ("ownership", False), ("ownership", "true"), ("context", False), ("metrics", None)]
)
def test_deployment_inputs_and_endpoint_scope_stop_before_placement(prepared_workflow, field, value):
    w = prepared_workflow
    path = w.batch / ("working-policy.json" if field == "metrics" else "deployment-inputs.json")
    values = json.loads(path.read_text())
    if field == "ownership":
        if value is None:
            values["services_rootless_data_ready"].pop("haproxy")
        else:
            values["services_rootless_data_ready"]["haproxy"] = value
    elif field == "context":
        values["service_common_postgres_operator_context"] = value
    else:
        values["mgt_firewall_active_endpoints"].remove("haproxy/metrics")
    dump(path, values)
    before = len(w.events())
    status, out = w.run("maintenance")
    assert status == 1, out
    assert not any(e["kind"] == "constraint_add" for e in w.events()[before:])


@pytest.mark.parametrize("scope", [CALLERS + ["unrelated"], CALLERS[:-1] + ["unrelated"]])
def test_real_hook_cli_rejects_any_replacement_outside_exact_eight(prepared_workflow, scope):
    w = prepared_workflow
    before = len(w.events())
    result = subprocess.run(
        [
            str(w.restrictor),
            str(w.root),
            str(w.root / "venv/bin/python"),
            str(w.batch / "haproxy-cutover.py"),
            "hooks",
            str(w.batch / "working-policy.json"),
            str(w.batch / "stage.json"),
            *scope,
        ],
        env=w.env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode in [1, 2] and len(w.events()) == before


def test_actual_preparation_replaces_all_callers_with_fresh_identities(prepared_workflow):
    w = prepared_workflow
    events = w.events()
    assert [e["caller"] for e in events if e["kind"] == "caller_replace"] == CALLERS
    log = next(w.batch.glob("prepare-*.log")).read_text()
    evidence = [json.loads(line) for line in log.splitlines() if line.startswith('{"caller":')]
    for name in CALLERS:
        records = [e for e in evidence if e["caller"] == name]
        assert [e["attempt"] for e in records] == [1, 2]
        assert all(all(counter["packets"] > 0 for counter in e["counters"]) for e in records)
        if name != "forgejo":
            assert records[0]["identity"] != records[1]["identity"]
    before = json.loads((w.batch / "homepage-policy.json").read_text())["callers"]
    accepted = json.loads((w.batch / "working-policy.json").read_text())["mgt_firewall_callers"]
    assert all(accepted[name] == bindings for name, bindings in before.items())
    assert [(accepted[n][0]["uid"], accepted[n][0]["cgroup"]) for n in ["controller", "recovery"]] == [
        (0, "skynet_pg_prepare.slice"),
        (0, "skynet_pg_recovery.slice"),
    ]
    assert not json.loads((w.batch / "working-policy.json").read_text())["mgt_firewall_inputs_verified"]


def test_fresh_changed_labels_stop_before_placement(prepared_workflow):
    w = prepared_workflow
    path = w.root / "reports.json"
    reports = json.loads(path.read_text())
    caller = next(c for c in reports[0]["containers"] if c["name"] == "autobrr")
    caller["swarm"] = "changed_autobrr"
    caller["binding"]["selector"] = "changed_autobrr"
    dump(path, reports)
    before = len(w.events())
    status, out = w.run("maintenance")
    assert status == 1 and "fresh exact caller labels changed" in out
    assert not any(e["kind"] == "constraint_add" for e in w.events()[before:])


def test_failed_image_query_with_valid_partial_output_stops_before_placement(prepared_workflow):
    w = prepared_workflow
    before = len(w.events())
    status, out = w.run("maintenance", "image-query-error")
    assert status == 44, out
    assert not any(e["kind"] == "constraint_add" for e in w.events()[before:])


@pytest.mark.parametrize("scenario", ["deployment-after-write", "rollback-placement-no-write", "rollback-placement-after-write"])
def test_rollback_replay_uses_recorded_completed_transitions(prepared_workflow, scenario):
    w = prepared_workflow
    status, out = w.run("maintenance", scenario)
    assert status == 36, out
    state = json.loads((w.root / "state.json").read_text())
    assert state["policy"] == "homepage" and not state["unit_active"]
    before = len(w.events())
    status, out = w.run("rollback")
    assert status == 0, out
    after = w.events()[before:]
    state = json.loads((w.root / "state.json").read_text())
    assert not state["excluded"] and state["original_listener"]
    assert not any(e["kind"] in ["restore_homepage", "new_unit_stop", "new_container_stop"] for e in after)
    assert sum(e["kind"] == "constraint_remove" for e in after) == (1 if scenario == "rollback-placement-no-write" else 0)


@pytest.mark.parametrize("scenario,status", [("success", 0), ("capture-idle", 1), ("capture-command-error", 53)])
def test_actual_resume_preserves_completed_preparation_and_failure_status(prepared_workflow, scenario, status):
    w = prepared_workflow
    names = [
        "working-policy.json",
        "deployment-inputs.json",
        "image-id",
        "haproxy.cfg",
        "after.json.metadata.json",
        "stage.json",
        "recovery-env.sh",
        "provider-before.json",
        "homepage-inputs.yml",
        NATIVE,
    ]
    before = {name: (w.batch / name).read_bytes() for name in names}
    events_before = len(w.events())
    code, output = w.run("resume", scenario)
    assert code == status, output
    assert {name: (w.batch / name).read_bytes() for name in names} == before
    events = w.events()[events_before:]
    assert not any(
        e["kind"] in {"replace", "constraint_add", "constraint_remove", "restore_homepage", "deploy", "policy_write"} for e in events
    )
    assert not any(e.get("name") == "podman" for e in events)
    assert not any("--force" in e.get("argv", []) or "restart" in e.get("argv", []) for e in events)
    assert "Route capture running" in output
    if status == 0:
        assert "Resume gates passed" in output and "HAPROXY_ROUTE_CAPTURE_FILE=" in output
        assert any(e["kind"] == "capture_window" for e in events)
        assert list(w.batch.glob("resume-*.json"))
        assert any(e.get("name") == "skynet" and "--check" in e.get("argv", []) for e in events)
    elif scenario == "capture-idle":
        assert "romm: actual declared PostgreSQL destination still unresolved/idle" in output
        assert list(w.batch.glob("route-capture-*.json.metadata.json"))
        assert not list(w.batch.glob("resume-*.json"))
    else:
        assert "fixture bounded capture failed" in output
        assert not list(w.batch.glob("resume-*.json"))


@pytest.mark.parametrize("scenario,status", [("success", 0), ("capture-command-error", 53)])
def test_operator_resume_command_logs_early_and_preserves_status(prepared_workflow, scenario, status):
    import re

    w = prepared_workflow
    blocks = re.findall(r"```bash\n(.*?)\n```", (ROOT / "migrator/guides/haproxy.md").read_text(), re.S)
    snippet = next(block for block in blocks if 'resume "$batch"' in block and "PIPESTATUS" in block)
    snippet = snippet.replace("/opt/homelab", str(w.repo)).replace("/opt/ansible/ansible-venv", str(w.root / "venv"))
    result = subprocess.run(
        [str(w.restrictor), str(w.root), "/bin/bash", "-c", snippet],
        env={**w.env, "SCENARIO": scenario, "HAPROXY_BATCH": str(w.batch)},
        text=True,
        capture_output=True,
        timeout=50,
    )
    assert result.returncode == status, result.stdout + result.stderr
    assert result.stdout.index("Private runner log:") < result.stdout.index("Starting simultaneous")
    logs = list(w.batch.glob("resume-runner-*.log"))
    assert len(logs) == 1 and logs[0].stat().st_mode & 0o777 == 0o600
    assert "Starting simultaneous" in logs[0].read_text()
    assert f"exited with status {status}" in result.stdout


@pytest.mark.parametrize("replacement", [False, True])
def test_resume_capture_is_reused_only_with_unchanged_callers_before_maintenance(prepared_workflow, replacement):
    w = prepared_workflow
    status, output = w.run("resume")
    assert status == 0, output
    capture = next(w.batch.glob("route-capture-*.json.metadata.json"))
    w.env["HAPROXY_ROUTE_CAPTURE_FILE"] = str(capture)
    reports = json.loads((w.root / "reports.json").read_text())
    # Live snapshot is idle again: only the bounded, attributable capture supplies routes.
    for report in reports:
        for record in report["containers"]:
            if record.get("service") == "infisical" or record.get("swarm") in {"app_seerr", "app_romm"}:
                record["destinations"] = []
    dump(w.root / "reports.json", reports)
    if replacement:
        state = json.loads((w.root / "state.json").read_text())
        state["generation"]["infisical"] += 1
        dump(w.root / "state.json", state)
    start = len(w.events())
    status, output = w.run("maintenance")
    events = w.events()[start:]
    if replacement:
        assert status != 0 and "captured caller replaced or identity changed" in output
        assert not any(e["kind"] == "constraint_add" for e in events)
    else:
        assert status == 0, output
        assert any(e["kind"] == "constraint_add" for e in events)
        assert "Maintenance sequence completed" in output
        assert not any(e["kind"] == "replace" for e in events)


@pytest.mark.parametrize("change", [None, "replacement", "incomplete", "invalid-selection"])
def test_actual_targeted_resume_keeps_other_windows_and_accepted_inputs(prepared_workflow, change):
    w = prepared_workflow
    assert w.run("resume")[0] == 0
    capture = next(w.batch.glob("route-capture-*.json.metadata.json"))
    old = json.loads(capture.read_text())
    # Reproduce the operator's completed window: ONLY Authelia was idle.
    for report in old:
        for record in report["containers"]:
            if record.get("swarm") == "app_authelia":
                record["destinations"] = []
        if change == "incomplete":
            report["capture"]["complete"] = False
    dump(capture, old)
    accepted = {
        name: (w.batch / name).read_bytes() for name in ["working-policy.json", "deployment-inputs.json", "after.json.metadata.json"]
    }
    w.env["HAPROXY_ROUTE_CAPTURE_FILE"] = str(capture)
    w.env["HAPROXY_ROUTE_CAPTURE_CALLERS"] = '"authelia"' if change == "invalid-selection" else '["authelia"]'
    if change == "replacement":
        state = json.loads((w.root / "state.json").read_text())
        state["generation"]["infisical"] += 1
        dump(w.root / "state.json", state)
    start = len(w.events())
    status, output = w.run("resume")
    assert {name: (w.batch / name).read_bytes() for name in accepted} == accepted
    events = w.events()[start:]
    assert not any(e["kind"] in {"replace", "constraint_add", "deploy", "policy_write"} or e.get("name") == "podman" for e in events)
    if change:
        assert status != 0, output
        assert not any(e.get("name") == "skynet" and "--check" in e.get("argv", []) for e in events)
        return
    assert status == 0 and "Resume gates passed" in output, output
    assert [e["callers"] for e in events if e["kind"] == "capture_window"] == [["authelia"]]
    new = next(p for p in w.batch.glob("route-capture-*.json.metadata.json") if p != capture)
    reports = json.loads(new.read_text())
    assert all(r["capture"]["callers"] == ["authelia"] for r in reports)
    for report in reports:
        for record in report["containers"]:
            if record.get("swarm") in {"app_romm", "app_seerr"} or record.get("service") == "infisical":
                assert record["destinations"]
                assert record["destinations"][0]["observations"][0]["source"]["path"] == str(capture)
    assert "HAPROXY_ROUTE_CAPTURE_FILE=" in output


def test_full_installed_forgejo_endpoint_survives_real_prepare_and_maintenance(workflow):
    endpoint = {"ids": ["forgejo/backend"], "port": 13001, "purpose": "backend", "callers": ["traefik"]}
    installed = json.loads((workflow.root / "installed-policy.json").read_text())
    installed["endpoints"].append(endpoint)
    dump(workflow.root / "installed-policy.json", installed)
    stage = json.loads((workflow.root / "stage.json").read_text())
    for name in ["plan", "policy"]:
        stage[name]["endpoints"].append(endpoint)
    dump(workflow.root / "stage.json", stage)
    status, output = workflow.run("prepare")
    assert status == 0, output
    assert json.loads((workflow.batch / "policy-before.json").read_text()) == installed
    values = json.loads((workflow.batch / "working-policy.json").read_text())
    assert "forgejo/backend" in values["mgt_firewall_active_endpoints"]
    assert values["mgt_firewall_callers"]["traefik"] == installed["callers"]["traefik"]
    status, output = workflow.run("maintenance")
    assert status == 0, output
    assert "forgejo/backend" in json.loads((workflow.batch / "working-policy.json").read_text())["mgt_firewall_active_endpoints"]


def test_concurrent_endpoint_addition_stops_before_policy_write(prepared_workflow):
    w = prepared_workflow
    status, output = w.run("maintenance", "baseline-after-route")
    assert status != 0, output
    assert not any(e["kind"] == "policy_apply" for e in w.events())
    assert json.loads((w.root / "state.json").read_text())["excluded"] is False
