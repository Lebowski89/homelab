"""Run scoped policy transactions against the real two-family rule planner."""

import importlib.util
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from threading import RLock
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ENGINE = load("ansible/roles/service_firewall/files/lifecycle.py", "lifecycle_engine_test")
DECL = load("ansible/roles/service_firewall/files/declarations.py", "lifecycle_declarations_test")
REMOTE = load("ansible/roles/service_firewall/files/lifecycle_remote.py", "lifecycle_remote_test")
REMOTE.policy_engine = ENGINE
MGT = load("tests/unit/test_mgt_firewall.py", "lifecycle_mgt_test")
REAL = load("tests/unit/test_mgt_podman_migration.py", "lifecycle_real_test")
ACTION = load("ansible/action_plugins/service_firewall_lifecycle.py", "lifecycle_action_test")
CONTAIN = load("ansible/roles/docker_services/files/contain.py", "docker_containment_test")
CONTAIN_ACTION = load("ansible/action_plugins/docker_services_contain.py", "docker_containment_action_test")


def identity(name):
    return {
        "service": name,
        "hosts": ["manager"],
        "binding": {
            "kind": "service",
            "runtime": "podman",
            "phase": "podman",
            "mode": "rootless",
            "account": "podman-" + name,
            "selector": name,
        },
        "network_mode": None,
        "image": "registry.invalid/nonproduction:1",
        "publications": [],
    }


def request(name="utility", port=18010):
    return {
        "profile": "mgt",
        "host": "manager",
        "address": "192.0.2.48",
        "service": name,
        "runtime": identity(name),
        "action": "deploy",
        "endpoints": [
            {
                "ids": [name + "/backend"],
                "service": name,
                "port": port,
                "destination": 8080,
                "callers": ["proxy"],
                "purpose": "test backend",
            }
        ],
        "callers": {"proxy": identity("proxy")},
    }


class Store:
    def __init__(self, path, monkeypatch):
        self.path = path
        self.kernel = MGT.Kernel()
        self.mutex = RLock()
        self.events = []
        self.fail = None
        self.current = {
            "schema": 1,
            "backend": "nf_tables",
            "lifecycle": True,
            "inputs_verified": False,
            "inventory_host": "manager",
            "inventory_address": "192.0.2.48",
            "endpoints": [],
            "callers": {},
        }
        monkeypatch.setattr(MGT.FW, "SYSTEMD", path.parent / "systemd")

    @contextmanager
    def lock(self):
        with self.mutex:
            yield

    def read(self):
        return deepcopy(self.current)

    def validate(self, policy):
        MGT.FW.validate_policy(policy)

    def audit(self, policy, recovering=False):
        if policy["endpoints"] and not recovering and not any(v.get("failed_stage") for v in policy.get("managed_services", {}).values()):
            assert MGT.FW.reconcile(policy, "check", run=self.kernel.run, account_lookup=lambda _: SimpleNamespace(pw_uid=2222))[
                "compliant"
            ]
        self.events.append("audit")

    def test(self, policy, request, phase):
        self.events.append("both-family-test")
        MGT.FW.reconcile(policy, dry_run=True, run=self.kernel.run, account_lookup=lambda _: SimpleNamespace(pw_uid=2222))
        if self.fail == "test":
            raise RuntimeError("test failure")

    def prepare(self, policy):
        self.events.append("persistence")

    def write(self, policy):
        self.current = deepcopy(policy)
        REMOTE.atomic(self.path, json.dumps(policy), 0o600)
        self.events.append("write")

    def apply(self, policy, request, phase):
        if self.fail == "apply":
            raise RuntimeError("apply failure")
        MGT.FW.reconcile(policy, run=self.kernel.run, account_lookup=lambda _: SimpleNamespace(pw_uid=2222))
        self.events.append("apply")


def test_fresh_unchanged_changed_and_remove_preserve_union_and_both_families(tmp_path, monkeypatch):
    store = Store(tmp_path / "policy.json", monkeypatch)
    first, other = request(), request("other", 18020)
    for desired in [first, other]:
        ENGINE.transact(store, desired, "stage", desired["service"], lambda phase: store.events.append(phase))
        ENGINE.transact(store, desired, "finish", desired["service"], lambda phase: store.events.append(phase))
    unrelated = deepcopy(store.current["endpoints"][1])
    for desired in [first, first | {"endpoints": [first["endpoints"][0] | {"port": 18011}]}]:
        staged = ENGINE.transact(store, desired, "stage", "next", lambda _: None)
        ENGINE.transact(store, desired, "finish", "next", lambda _: None)
        if desired == first:
            assert not staged["changed"]
    assert {e["port"] for e in store.current["endpoints"]} == {18011, 18020}
    assert unrelated in store.current["endpoints"]
    removed = request() | {"action": "remove"}
    ENGINE.transact(store, removed, "prepare_remove", "remove", lambda _: None)
    with pytest.raises(RuntimeError, match="writer remains"):
        ENGINE.transact(store, removed, "remove", "remove", lambda _: (_ for _ in ()).throw(RuntimeError("writer remains")))
    assert len(store.current["endpoints"]) >= 2
    ENGINE.transact(store, removed, "remove", "remove", lambda phase: store.events.append(phase))
    assert store.current["endpoints"] == [unrelated]
    assert store.events.index("both-family-test") < store.events.index("write") < store.events.index("apply")
    assert "healthy" in store.events and "absent" in store.events
    assert {c[0][0] for c in store.kernel.calls if "--test" in c[0]} == {"iptables-restore", "ip6tables-restore"}


def test_failures_before_and_after_writes_do_not_restore_an_old_union(tmp_path, monkeypatch):
    store = Store(tmp_path / "policy.json", monkeypatch)
    store.fail = "test"
    with pytest.raises(RuntimeError, match="test failure"):
        ENGINE.transact(store, request(), "stage", "a", lambda _: None)
    assert not store.path.exists()
    store.fail = "apply"
    with pytest.raises(RuntimeError, match="apply failure"):
        ENGINE.transact(store, request(), "stage", "a", lambda _: None)
    assert store.path.exists() and store.current["managed_services"]["utility"]["failed_stage"]
    assert store.current["endpoints"][0]["port"] == 18010
    # The failed pre-start stage retained protection and released its token.
    # Reconciliation always rereads the latest union, never an old snapshot.
    store.fail = None
    ENGINE.transact(store, request(), "stage", "a", lambda _: None)
    ENGINE.transact(store, request(), "finish", "a", lambda _: None)


def test_concurrent_services_merge_current_policy_under_one_lock(tmp_path, monkeypatch):
    store = Store(tmp_path / "policy.json", monkeypatch)

    def deploy(index):
        desired = request("service" + str(index), 18100 + index)
        ENGINE.transact(store, desired, "stage", str(index), lambda _: None)
        ENGINE.transact(store, desired, "finish", str(index), lambda _: None)

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(deploy, range(3)))
    assert {e["port"] for e in json.loads(store.path.read_text())["endpoints"]} == {18100, 18101, 18102}


@pytest.mark.parametrize("service,host", [("wallos", "mgt"), ("whisparr", "unraid")])
def test_real_canonical_endpoint_declarations_resolve_without_migration_flags(service, host):
    context = REAL.context()
    catalog = REAL.catalog()
    values = {}
    for name in [service, "traefik"]:
        raw = REAL.CATALOG.service_catalog_merge_target(catalog[name], None)
        metadata = REAL.COMMON.service_common_requirements_metadata(raw, name)
        values[name] = REAL.resolve(metadata, context)
    plan = DECL.plan(service, values, "mgt", ["unraid", "plex"], context["hostvars"])
    assert plan["managed"] and plan["endpoints"][0]["host"] == host
    assert plan["endpoints"][0]["callers"] == ["traefik"]
    assert plan["callers"]["traefik"]["binding"]["account"] == "podman-traefik"


def test_target_callers_collisions_and_unsupported_exposure_fail_before_a_transaction():
    values = {
        "utility": {
            "runtime": "podman",
            "image": "nonproduction:1",
            "deploy": {"host": "manager", "execution": {"mode": "rootless", "host_user": "podman-utility"}},
            "ports": {"web": {"exposure": "private", "callers": ["proxy:mgt"], "published": 18010, "target": 8080}},
        },
        "proxy:mgt": {
            "name": "proxy",
            "runtime": "podman",
            "deploy": {"host": "manager", "execution": {"mode": "rootless", "host_user": "podman-proxy"}},
        },
    }
    hosts = {"manager": {"local_ip": "192.0.2.48"}}
    assert DECL.plan("utility", values, "manager", [], hosts)["callers"]["proxy"]["binding"]["account"] == "podman-proxy"
    for change in [{"callers": []}, {"exposure": "unknown"}, {"protocol": "udp"}, {"mode": "ingress"}]:
        candidate = deepcopy(values)
        candidate["utility"]["ports"]["web"].update(change)
        with pytest.raises(ValueError):
            DECL.plan("utility", candidate, "manager", [], hosts)
    values["conflict"] = deepcopy(values["utility"])
    values["conflict"]["deploy"]["execution"]["host_user"] = "podman-conflict"
    with pytest.raises(ValueError, match="collision"):
        DECL.plan("utility", values, "manager", [], hosts)


@pytest.mark.parametrize("runtime,mode", [("docker", None), ("podman", "rootful"), ("podman", "rootless")])
def test_supported_identity_models_use_exact_selectors(runtime, mode):
    cfg = {"name": "utility", "runtime": runtime, "deploy": {"host": "manager", "type": "container"}}
    if mode:
        cfg["deploy"]["execution"] = {"mode": mode, "host_user": "podman-utility"}
    binding = DECL.identity("utility", cfg, "manager")["binding"]
    if runtime == "docker":
        assert binding["compose"] == {"project": "utility-manager", "service": "utility"}
    else:
        assert binding["mode"] == mode
    cfg["deploy"]["type"] = "swarm"
    if runtime == "docker":
        assert DECL.identity("utility", cfg, "manager")["binding"]["selector"] == "utility_utility"


def test_bundled_remote_entrypoint_imports_without_accessing_the_host():
    for profile in ["mgt", "workers"]:
        _, source = ACTION.remote_source(profile)
        definitions = source[: source.index("\nimport json, sys\ntry:")]
        namespace = {}
        exec(compile(definitions, "<isolated-bundle>", "exec"), namespace)
        assert callable(namespace["helper"].reconcile)
        assert callable(namespace["engine"].transact)


def test_cleanup_failure_can_be_retried_after_the_runtime_is_already_absent(tmp_path, monkeypatch):
    store = Store(tmp_path / "policy.json", monkeypatch)
    desired = request()
    ENGINE.transact(store, desired, "stage", "a", lambda _: None)
    ENGINE.transact(store, desired, "finish", "a", lambda _: None)
    removing = desired | {"action": "remove"}
    ENGINE.transact(store, removing, "prepare_remove", "remove-a", lambda _: None)
    store.fail = "apply"
    with pytest.raises(RuntimeError):
        ENGINE.transact(store, removing, "remove", "remove-a", lambda phase: None)
    assert store.current["managed_services"]["utility"]["removing"]
    assert store.current["endpoints"] == []
    store.fail = None
    ENGINE.transact(store, removing, "prepare_remove", "remove-b", lambda _: None)
    ENGINE.transact(store, removing, "remove", "remove-b", lambda _: None)
    assert store.current["managed_services"] == {} and store.current["endpoints"] == []


def test_failed_start_retains_protection_and_releases_only_a_stopped_writer(tmp_path, monkeypatch):
    store = Store(tmp_path / "policy.json", monkeypatch)
    desired = request()
    ENGINE.transact(store, desired, "stage", "start", lambda _: None)
    before = deepcopy(store.current["endpoints"])
    with pytest.raises(RuntimeError, match="still running"):
        ENGINE.transact(store, desired, "abort", "start", lambda _: (_ for _ in ()).throw(RuntimeError("still running")))
    assert store.current["managed_services"]["utility"]["pending"]
    ENGINE.transact(store, desired, "abort", "start", lambda _: None)
    assert store.current["endpoints"] == before
    assert not store.current["managed_services"]["utility"]["pending"]
    ENGINE.transact(store, desired, "stage", "new-attempt", lambda _: None)
    ENGINE.transact(store, desired, "finish", "new-attempt", lambda _: None)


def test_administrative_installs_preserve_unrelated_entries_and_reject_stale_overwrites(tmp_path, monkeypatch):
    store = Store(tmp_path / "policy.json", monkeypatch)
    first = request()
    ENGINE.transact(store, first, "stage", "first", lambda _: None)
    with pytest.raises(ValueError, match="unfinished"):
        ENGINE.install_union(store.current, store.current, "mgt")
    ENGINE.transact(store, first, "finish", "first", lambda _: None)
    stale = deepcopy(store.current)
    stale["endpoints"] = []
    stale["callers"] = {}
    assert ENGINE.install_union(store.current, stale, "mgt") == store.current
    stale = deepcopy(store.current)
    stale["endpoints"][0]["callers"] = ["unexpected"]
    with pytest.raises(ValueError, match="existing endpoint differs"):
        ENGINE.install_union(store.current, stale, "mgt")


def test_current_container_replacement_reconciles_veth_and_rejects_old_identity(tmp_path, monkeypatch):
    store = Store(tmp_path / "policy.json", monkeypatch)
    desired = request()
    desired["callers"]["proxy"]["binding"] = {"kind": "service", "runtime": "docker", "phase": "docker", "selector": "proxy_proxy"}
    ENGINE.transact(store, desired, "stage", "a", lambda _: None)
    old_peer = store.kernel.peer
    store.kernel.peer = "vethreplacement"
    ENGINE.transact(store, desired, "finish", "a", lambda _: None)
    for family, source in [(4, store.kernel.source), (6, "2001:db8:1::2")]:
        packet = MGT.packet(**{"--dport": "18010", "-s": source, "-i": "docker0", "--physdev-in": store.kernel.peer})
        assert MGT.verdict(store.kernel.state[family]["mangle"], "PREROUTING", packet, store.kernel.addresses) == "ACCEPT"
        assert (
            MGT.verdict(store.kernel.state[family]["mangle"], "PREROUTING", packet | {"--physdev-in": old_peer}, store.kernel.addresses)
            == "DROP"
        )


def test_remote_runtime_status_uses_correct_template_and_dedicated_home(monkeypatch):
    record = identity("utility")
    record["publications"] = [(18010, 8080, "tcp")]
    monkeypatch.setattr(
        REMOTE.pwd,
        "getpwnam",
        lambda _: SimpleNamespace(pw_name="podman-utility", pw_uid=2222, pw_dir="/nonproduction/home", pw_shell="/usr/sbin/nologin"),
    )
    calls = []

    def run(argv):
        calls.append(argv)
        assert "HOME=/nonproduction/home" in argv
        assert 'cd "$HOME" || exit; exec "$@"' in argv
        if "ps" in argv:
            return "a" * 64
        template = argv[argv.index("--format") + 1]
        assert ".ID" in template and ".Id" not in template
        assert argv[argv.index("/usr/bin/podman") + 2 :][:2] == ["container", "inspect"]
        return json.dumps(
            {
                "id": "a" * 64,
                "running": True,
                "pid": 321,
                "image": record["image"],
                "state": {"Health": {"Status": "healthy"}},
                "ports": {"8080/tcp": [{"HostPort": "18010"}]},
            }
        )

    REMOTE.runtime_check(record, "healthy", run)
    assert len(calls) == 3
    with pytest.raises(ValueError, match="running writer"):
        REMOTE.runtime_check(record, "absent", run)


def test_qualified_probe_rejects_namespace_or_pid_replacement(monkeypatch):
    record = identity("proxy")
    record["binding"] = {"kind": "service", "runtime": "docker", "phase": "docker", "selector": "proxy_proxy"}
    req = request()
    req["callers"] = {"proxy": record}
    req["endpoints"][0]["address"] = "192.0.2.48"
    snapshots = iter(["net:[1]", "net:[2]"])

    def run(argv, **kwargs):
        if "ps" in argv:
            assert "label=com.docker.swarm.service.name=proxy_proxy" in argv
            return "a" * 64
        if "inspect" in argv:
            return "1234"
        if argv[0] == "cat":
            return "1234 (nonproduction) " + " ".join(["0"] * 20)
        if argv[0] == "readlink":
            return next(snapshots)
        assert argv[:5] == ["nsenter", "--target", "1234", "--net", "--"]
        return json.dumps({"namespace_source": "192.0.2.48", "connected": True})

    monkeypatch.setattr(REMOTE, "command", run)
    with pytest.raises(ValueError, match="replaced during"):
        REMOTE.qualified_probes(req)


@pytest.mark.integration
@pytest.mark.parametrize(
    "failure",
    [
        None,
        "test",
        "startup",
        "apply",
        "post-start-test",
        "check-mode",
        "remove-delayed",
        "provider",
        "provider-startup",
        "provider-partial",
    ],
)
def test_actual_role_lifecycle_uses_real_rule_transactions_and_keeps_failure_status(tmp_path, failure):
    """Execute the role's stage/probe/finish/abort tasks with isolated kernel I/O."""
    import os
    import subprocess
    import sys

    import yaml

    action_dir = tmp_path / "action_plugins"
    action_dir.mkdir()
    fixture_module = Path(__file__).resolve()
    # Override the transport boundary only. Production action serialization,
    # transaction planning and the production rule helper still execute.
    (action_dir / "service_firewall_lifecycle.py").write_text(f"""
import importlib.util, json
from pathlib import Path
from types import SimpleNamespace
spec = importlib.util.spec_from_file_location('isolated_firewall_fixture', {str(fixture_module)!r})
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)

class ActionModule(fixture.ACTION.ActionModule):
    def _execute_module(self, module_name, module_args, task_vars):
        assert module_name == 'ansible.builtin.command'
        data = json.loads(module_args['stdin'])
        request, phase = data['request'], data['phase']
        root = Path(task_vars['fixture_root'])
        monkeypatch = SimpleNamespace(setattr=lambda obj, name, value: setattr(obj, name, value))
        store = fixture.Store(root / 'policy.json', monkeypatch)
        if store.path.exists():
            store.current = json.loads(store.path.read_text())
        state = root / 'kernel.json'
        if state.exists():
            store.kernel.state = {{int(k): v for k, v in json.loads(state.read_text()).items()}}
        counter_file = root / 'counters.json'
        counts = json.loads(counter_file.read_text()) if counter_file.exists() else {{}}
        with (root / 'events').open('a') as output:
            output.write(phase + '\\n')
        def runtime(expected):
            if expected == 'healthy':
                assert (root / 'writer').exists(), 'verification ran before startup'
            if expected == 'absent':
                if phase == 'remove' and task_vars.get('fixture_failure') == 'remove-delayed':
                    marker = root / 'delayed-exit'
                    if not marker.exists():
                        marker.touch()
                        assert store.current['endpoints'], 'protection disappeared before writer exit'
                        raise RuntimeError('selected runtime is still exiting')
                assert not (root / 'writer').exists(), 'cleanup ran before writer removal'
        try:
            if phase == 'counters':
                result = {{'changed': False, 'counters': counts}}
            elif phase == 'probe':
                assert (root / 'writer').exists()
                for endpoint in request['endpoints']:
                    for caller in endpoint['callers']:
                        packet = fixture.MGT.packet(**{{'--dport': str(endpoint['port']), '--uid-owner': '2222'}})
                        assert fixture.MGT.verdict(store.kernel.state[4]['mangle'], 'OUTPUT', packet, store.kernel.addresses) == 'ACCEPT'
                        assert fixture.MGT.verdict(store.kernel.state[4]['mangle'], 'OUTPUT', packet | {{'--uid-owner': '0'}}, store.kernel.addresses) == 'DROP'
                        key = '4:' + str(endpoint['port'])
                        counts[key] = counts.get(key, 0) + 1
                result = {{'changed': False, 'handshakes': [{{'connected': True, 'port': request['endpoints'][0]['port']}}]}}
            elif phase.startswith('access_'):
                result = fixture.ENGINE.access_transact(store, request, phase, data['token'], runtime)
            else:
                selected_failure = task_vars.get('fixture_failure')
                store.fail = ('test' if (selected_failure == 'test' and phase == 'stage') or (selected_failure == 'post-start-test' and phase == 'finish') else
                              'apply' if selected_failure == 'apply' and phase == 'finish' else None)
                result = fixture.ENGINE.transact(store, request, phase, data['token'], runtime)
            return {{'rc': 0, 'stdout': json.dumps(result)}}
        except (AssertionError, RuntimeError, ValueError) as error:
            return {{'rc': 1, 'stderr': str(error)}}
        finally:
            state.write_text(json.dumps(store.kernel.state))
            counter_file.write_text(json.dumps(counts))
""")
    desired = request()
    plan = {
        "managed": True,
        "service": desired["service"],
        "runtime": desired["runtime"],
        "action": "deploy",
        "endpoints": [e | {"host": "manager"} for e in desired["endpoints"]],
        "callers": desired["callers"],
        "hosts": ["manager"],
        "controller": "manager",
        "inventory": {"manager": "192.0.2.48"},
        "profile": {"manager": "mgt"},
        "token": "isolated-operation",
    }

    if failure in {"provider", "provider-startup", "provider-partial"}:
        store = Store(tmp_path / "policy.json", SimpleNamespace(setattr=lambda obj, name, value: setattr(obj, name, value)))
        client = provider_request(store, "utility")
        (tmp_path / "kernel.json").write_text(json.dumps(store.kernel.state))
        plan["providers"] = [p | {"endpoints": [e | {"host": "manager"} for e in p["endpoints"]]} for p in client["providers"]]
        plan["access_hosts"] = ["manager"]
        if failure == "provider-partial":
            plan["access_hosts"].append("worker")
            plan["profile"]["worker"] = "workers"
            plan["inventory"]["worker"] = "192.0.2.20"

    def role(phase):
        selected_plan = plan | {"action": "remove", "token": "isolated-remove"} if phase in {"prepare_remove", "remove"} else plan
        return {
            "ansible.builtin.include_role": {"name": "service_firewall", "tasks_from": "lifecycle", "apply": {"tags": ["deploy"]}},
            "vars": {"service_firewall_adapter_plan": selected_plan, "service_firewall_lifecycle_phase": phase},
        }

    stop = {"ansible.builtin.file": {"path": str(tmp_path / "writer"), "state": "absent"}}
    tail = [role("stage"), {"ansible.builtin.copy": {"dest": str(tmp_path / "writer"), "content": "NONPRODUCTION writer", "mode": "0600"}}]
    if failure in {"provider", "provider-startup", "provider-partial"}:
        tail.insert(
            0,
            {
                "ansible.builtin.include_role": {"name": "service_firewall", "tasks_from": "access"},
                "vars": {"service_firewall_access_plan": plan, "service_firewall_access_phase": "access_stage"},
            },
        )
    if failure in {"startup", "provider-startup"}:
        tail.append({"ansible.builtin.fail": {"msg": "NONPRODUCTION startup failed"}})
    tail.append(role("finish"))
    if failure == "remove-delayed":
        tail.extend([role("prepare_remove"), stop, role("remove")])
    tasks = [
        {
            "block": tail,
            "rescue": [
                stop,
                {
                    "ansible.builtin.include_role": {
                        "name": "service_firewall",
                        "tasks_from": "lifecycle",
                        "apply": {"ignore_errors": True},
                    },
                    "vars": {"service_firewall_adapter_plan": plan, "service_firewall_lifecycle_phase": "abort"},
                },
                {"ansible.builtin.fail": {"msg": "NONPRODUCTION original failure retained"}},
            ],
        }
    ]
    playbook = tmp_path / "lifecycle.yml"
    playbook.write_text(
        yaml.safe_dump(
            [
                {
                    "hosts": "manager",
                    "connection": "local",
                    "gather_facts": False,
                    "become": False,
                    "vars": {"fixture_root": str(tmp_path), "fixture_failure": failure, "services_storage_host": "storage"},
                    "tasks": tasks,
                }
            ],
            sort_keys=False,
        )
    )
    config = tmp_path / "ansible.cfg"
    config.write_text(
        f"[defaults]\nroles_path={ROOT / 'ansible/roles'}\naction_plugins={action_dir}\nstdout_callback=default\nvars_plugins_enabled=\n[inventory]\nenable_plugins=host_list\n"
    )
    argv = [sys.executable, str(ROOT / "tests/fixtures/ansible/retry_playbook.py"), "-i", "manager,", str(playbook)]
    if failure == "check-mode":
        argv.append("--check")
    result = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=110 if failure == "post-start-test" else 45,
        env={
            **os.environ,
            "ANSIBLE_CONFIG": str(config),
            "ANSIBLE_LOG_PATH": str(tmp_path / "ansible.log"),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
            "ANSIBLE_TEST_RETRY_LOG": str(tmp_path / "retry-sleeps.jsonl"),
        },
    )
    output = result.stdout + result.stderr
    assert "SUBPROCESS_TEST_SECRET" not in output
    if failure == "check-mode":
        assert result.returncode == 0, output
        assert not (tmp_path / "events").exists() and not (tmp_path / "writer").exists()
    elif failure == "apply":
        # The first apply fails after writing an already-converged policy.
        # A retry may succeed only after a fresh healthy runtime/kernel audit.
        assert result.returncode == 0, output
        assert (tmp_path / "events").read_text().splitlines().count("finish") == 2
        assert (tmp_path / "writer").exists()
        assert not json.loads((tmp_path / "policy.json").read_text())["managed_services"]["utility"]["pending"]
    elif failure == "remove-delayed":
        assert result.returncode == 0, output
        assert (tmp_path / "events").read_text().splitlines().count("remove") == 2
        assert not (tmp_path / "writer").exists()
        policy = json.loads((tmp_path / "policy.json").read_text())
        assert not policy["endpoints"] and not policy["managed_services"]
    elif failure == "provider-partial":
        assert result.returncode != 0 and "original failure retained" in output, output
        policy = json.loads((tmp_path / "policy.json").read_text())
        assert "utility" in policy["endpoints"][0]["callers"]
        assert policy["managed_services"]["utility"]["access"]["failed"]
        assert not policy["managed_services"]["utility"]["access"]["pending"]
        assert not (tmp_path / "writer").exists()
    elif failure == "provider":
        assert result.returncode == 0, output
        policy = json.loads((tmp_path / "policy.json").read_text())
        assert "utility" in next(e for e in policy["endpoints"] if e["port"] == 5432)["callers"]
        assert not policy["managed_services"]["utility"]["access"]["pending"]
        events = (tmp_path / "events").read_text().splitlines()
        assert (
            events.index("access_stage")
            < events.index("stage")
            < events.index("access_activate")
            < events.index("finish")
            < events.index("access_finish")
        )
    elif failure:
        assert result.returncode != 0 and "original failure retained" in output, output
        assert not (tmp_path / "writer").exists()
        if failure != "test":
            policy = json.loads((tmp_path / "policy.json").read_text())
            assert policy["endpoints"] and policy["managed_services"]["utility"]["failed"]
    else:
        assert result.returncode == 0, output
        events = (tmp_path / "events").read_text().splitlines()
        assert events == ["stage", "activate", "finish", "counters", "probe", "counters"]
        assert not json.loads((tmp_path / "policy.json").read_text())["managed_services"]["utility"]["pending"]

    if failure in {"apply", "remove-delayed", "post-start-test"}:
        sleeps = [json.loads(line) for line in (tmp_path / "retry-sleeps.jsonl").read_text().splitlines()]
        events = (tmp_path / "events").read_text().splitlines()
        phase = "remove" if failure == "remove-delayed" else "finish"
        assert len(sleeps) == events.count(phase) - 1
        assert all(seconds > 0 for seconds in sleeps)


def test_all_real_mgt_targets_plan_without_templating_environments(monkeypatch):
    from ansible.plugins.action import ActionBase

    planner = load("ansible/action_plugins/service_firewall_plan.py", "lifecycle_catalog_test")
    catalog, context = REAL.catalog(), REAL.context()
    for service in catalog.values():
        service["environment"] = {"NEVER_EVALUATE": "{{ lookup('must_not_run') }}"}
        if service.get("runtime") == "podman" and not any(t.get("runtime") == "docker" for t in service.get("targets", {}).values()):
            service.setdefault("systemd", {})["service_add"] = ["{{ lookup('must_not_run') }}"]
    monkeypatch.setattr(ActionBase, "run", lambda *args: {})
    catalog["newapp"] = {
        "enabled": True,
        "runtime": "podman",
        "image": "registry.invalid/nonproduction:1",
        "named_networks": {"newapp": {"driver": "bridge", "external": False}},
        "postgres": {"enable": True},
        "deploy": {"type": "container", "host": "mgt", "execution": {"mode": "rootless", "host_user": "podman-newapp"}},
    }
    planned = []
    entries = REAL.mgt_entries(catalog)
    for entry in entries:
        raw = REAL.CATALOG.service_catalog_merge_target(catalog[entry["name"]], entry.get("target"))
        actual = raw.get("name", entry["name"] + ("-" + entry["target"] if entry.get("target") else ""))
        cfg = REAL.resolve(REAL.COMMON.service_common_requirements_metadata(raw, actual), context)
        action = object.__new__(planner.ActionModule)
        action._task = SimpleNamespace(args={"entry": entry | {"config": cfg}, "action": "deploy"})

        class Templar:
            def __init__(self, scope):
                self.scope = scope

            def template(self, value, **kwargs):
                for _ in range(8):
                    resolved = REAL.resolve(value, self.scope)
                    if resolved == value:
                        return resolved
                    value = resolved
                return value

            def copy_with_new_env(self, available_variables):
                return Templar(available_variables)

        action._templar = Templar(context)
        import yaml

        action._loader = SimpleNamespace(load_from_file=lambda path, **kwargs: yaml.safe_load(Path(path).read_text()))
        plan = action.run(task_vars=context | {"svcfiles": catalog})["ansible_facts"]["service_firewall_lifecycle_plan"]
        assert "must_not_run" not in json.dumps(plan)
        for caller in plan.get("callers", {}).values():
            if "metadata" in caller:
                REAL.PODMAN.podman_service_normalize(caller["metadata"], caller["service"])
        planned.append(plan)
    assert len(planned) == len(entries)
    pg = next(plan for plan in planned if plan["service"] == "haproxy:mgt")
    assert "infisical" in next(e for e in pg["endpoints"] if e["port"] == 5432)["callers"]
    assert any(plan.get("legacy_publications") and plan["managed"] for plan in planned)
    fresh = next(plan for plan in planned if plan["service"] == "newapp")
    assert not fresh["legacy_publications"]
    assert fresh["managed"] and fresh["callers"]["newapp"]["binding"]["account"] == "podman-newapp"
    assert any(p["runtime"]["name"] == "haproxy:mgt" and p["endpoints"][0]["port"] == 5432 for p in fresh["providers"])


def test_future_clients_do_not_create_a_provider_startup_cycle():
    policy = {"callers": {"future": [{"kind": "service", "runtime": "docker"}]}, "managed_services": {}}
    message = "future: no local running caller for docker:future_future"
    assert ENGINE.deferred_caller(policy, message)
    assert not ENGINE.deferred_caller(policy, "future: docker inspect failed (1)")
    policy["managed_services"]["future:mgt"] = {"runtime": {"service": "future"}}
    assert not ENGINE.deferred_caller(policy, message)
    policy["managed_services"] = {}
    policy["callers"]["future"].append({"kind": "container", "verified": True})
    assert not ENGINE.deferred_caller(policy, message)


def test_cancelled_preparation_keeps_an_existing_writer_and_all_protection(tmp_path, monkeypatch):
    store = Store(tmp_path / "policy.json", monkeypatch)
    desired = request()
    ENGINE.transact(store, desired, "stage", "stage", lambda _: None)
    protected = deepcopy(store.current["endpoints"])

    def must_not_stop_or_test_absence(phase):
        raise AssertionError("preparation cancellation must not stop an old writer")

    ENGINE.transact(store, desired, "cancel", "stage", must_not_stop_or_test_absence)
    assert store.current["endpoints"] == protected
    assert store.current["managed_services"]["utility"]["failed_stage"]
    ENGINE.transact(store, desired, "stage", "retry", lambda _: None)


@pytest.mark.parametrize("backend", ["legacy", "nf_tables"])
def test_worker_transactions_adopt_only_the_selected_ports_and_preserve_sources(tmp_path, monkeypatch, backend):
    workers = load("tests/unit/test_worker_backend_firewall.py", "lifecycle_worker_fixture")
    helper = workers.HELPER if hasattr(workers, "HELPER") else workers.FW

    class WorkerStore(Store):
        def __init__(self):
            super().__init__(tmp_path / "policy.json", monkeypatch)
            self.kernel = workers.Kernel(backend)
            self.current = {
                "schema": 1,
                "backend": backend,
                "inventory_host": "storage",
                "inventory_address": "192.0.2.20",
                "sources": ["192.0.2.48"],
                "sources_verified": True,
                "ports": [22601, 22602],
            }
            helper.reconcile(self.current, run=self.kernel.run)

        def validate(self, policy):
            helper.validate_policy(policy)

        def audit(self, policy, recovering=False):
            assert helper.reconcile(policy, "check", run=self.kernel.run)["compliant"]

        def test(self, policy, request, phase):
            helper.reconcile(policy, "validate", run=self.kernel.run)

        def apply(self, policy, request, phase):
            return helper.reconcile(policy, run=self.kernel.run)

    store = WorkerStore()
    desired = request() | {"profile": "workers", "host": "storage", "address": "192.0.2.20", "sources": None}
    desired["endpoints"][0]["port"] = 22601

    def baseline(phase):
        return {"baseline_ports": [22601]} if phase == "dependencies" else None

    ENGINE.transact(store, desired, "stage", "one", baseline)
    ENGINE.transact(store, desired, "finish", "one", baseline)
    changed = deepcopy(desired)
    changed["endpoints"][0]["port"] = 18510
    ENGINE.transact(store, changed, "stage", "two", baseline)
    assert store.current["ports"] == [18510, 22601, 22602]
    ENGINE.transact(store, changed, "finish", "two", baseline)
    assert store.current["ports"] == [18510, 22602]
    assert store.current["sources"] == ["192.0.2.48"] and store.current["sources_verified"] is True
    invalid = deepcopy(changed) | {"sources": ["192.0.2.99"]}
    before = store.path.read_bytes()
    with pytest.raises(ValueError, match="source declaration changed"):
        ENGINE.transact(store, invalid, "stage", "bad", baseline)
    assert store.path.read_bytes() == before


def test_nat_collision_projection_is_read_only_and_rejects_opaque_rules():
    calls = []
    native = {
        "nftables": [
            {"table": {"family": "ip", "name": "nat"}},
            {
                "rule": {
                    "table": "netavark",
                    "expr": [
                        {"match": {"op": "==", "left": {"payload": {"protocol": "tcp", "field": "dport"}}, "right": 18500}},
                        {"dnat": {"addr": "198.51.100.2", "port": 8080}},
                    ],
                }
            },
        ]
    }

    def read(argv):
        calls.append(argv)
        return "-A DOCKER -p tcp --dport 18501 -j DNAT --to-destination 198.51.100.3:80\n"

    assert REMOTE.nat_publications(native, read) == {18500, 18501}
    assert calls == [["iptables-save", "-t", "nat"]]  # No absent ip6 table initialization.
    native["nftables"][1]["rule"]["expr"][0]["match"]["right"] = "@opaque-map"
    with pytest.raises(ValueError, match="native DNAT map"):
        REMOTE.nat_publications(native, read)


def test_removal_reserves_existing_ports_without_adding_changed_declarations(tmp_path, monkeypatch):
    store = Store(tmp_path / "policy.json", monkeypatch)
    original = request()
    ENGINE.transact(store, original, "stage", "first", lambda _: None)
    ENGINE.transact(store, original, "finish", "first", lambda _: None)
    protected = deepcopy(store.current["endpoints"])
    events = len(store.events)
    changed = request(port=18099) | {"action": "remove"}
    ENGINE.transact(store, changed, "prepare_remove", "remove", lambda _: None)
    assert store.current["endpoints"] == protected
    assert store.events[events:] == ["audit", "write"]
    observed = []
    ENGINE.transact(store, changed, "remove", "remove", observed.append)
    assert ("obsolete_absent", [18010]) in observed
    assert store.current["endpoints"] == []


def test_removing_client_preserves_provider_and_retained_binding_without_allowing_missing_identity(tmp_path, monkeypatch):
    store = Store(tmp_path / "policy.json", monkeypatch)
    client = request("client", 18030)
    client["runtime"]["binding"] = {"kind": "service", "runtime": "docker", "phase": "docker", "selector": "client_client"}
    provider = request("provider", 18040)
    provider["endpoints"][0]["callers"] = ["client"]
    provider["callers"] = {"client": client["runtime"]}
    for desired in [client, provider]:
        ENGINE.transact(store, desired, "stage", desired["service"], lambda _: None)
        ENGINE.transact(store, desired, "finish", desired["service"], lambda _: None)
    preserved = deepcopy(next(e for e in store.current["endpoints"] if e["service"] == "provider"))
    removing = client | {"action": "remove"}
    ENGINE.transact(store, removing, "prepare_remove", "remove", lambda _: None)
    ENGINE.transact(store, removing, "remove", "remove", lambda _: None)
    assert store.current["endpoints"] == [preserved]
    assert store.current["callers"]["client"] == [client["runtime"]["binding"]]
    assert store.current["managed_services"]["client"]["removed"]
    original_resolver = MGT.FW.container_identities

    def missing(binding, run):
        raise MGT.FW.MissingRuntimeCaller("no local running caller for docker:client_client")

    monkeypatch.setattr(MGT.FW, "container_identities", missing)
    resolved, pending = MGT.FW.resolve_callers(store.current, store.kernel.run, account_lookup=lambda _: SimpleNamespace(pw_uid=2222))
    assert not resolved["client"] and not pending

    def failed(binding, run):
        raise RuntimeError("inspect failed")

    monkeypatch.setattr(MGT.FW, "container_identities", failed)
    with pytest.raises(ValueError, match="inspect failed"):
        MGT.FW.resolve_callers(store.current, store.kernel.run, account_lookup=lambda _: SimpleNamespace(pw_uid=2222))
    monkeypatch.setattr(MGT.FW, "container_identities", original_resolver)


def test_remove_runtime_dependency_guard_uses_declared_dependencies_not_acl_callers(tmp_path, monkeypatch):
    desired = request() | {"action": "remove", "root": str(tmp_path)}
    policy_path = tmp_path / "policy.json"
    policy_path.write_text("NONPRODUCTION")
    store = SimpleNamespace(root=tmp_path, policy_path=policy_path, profile="mgt", flash=False)
    monkeypatch.setattr(REMOTE, "Store", lambda *args: store)

    def transaction(store, request, phase, token, runtime):
        runtime("dependencies")
        return {"changed": False}

    engine = SimpleNamespace(transact=transaction)
    calls = []

    def inspect(record, expected):
        calls.append(record["service"])
        return {"running": True, "ports": {}}

    monkeypatch.setattr(REMOTE, "runtime_check", inspect)
    data = {"request": desired, "phase": "prepare_remove", "token": "remove", "helper": "", "units": {}}
    REMOTE.run_lifecycle(engine, None, data)
    assert calls == []  # proxy is an allowed caller, not a runtime dependent
    desired["dependents"] = [identity("dependent")]
    with pytest.raises(ValueError, match="active dependent.*dependent"):
        REMOTE.run_lifecycle(engine, None, data)
    monkeypatch.setattr(REMOTE, "runtime_check", lambda *args: {"ports": {}})
    REMOTE.run_lifecycle(engine, None, data)
    desired["dependents"][0]["hosts"] = ["another-host"]
    with pytest.raises(ValueError, match="another host"):
        REMOTE.run_lifecycle(engine, None, data)


@pytest.mark.parametrize("storage,matched,ready", [("bind", 0, True), ("bind", 1, False), ("volume", 0, False)])
def test_only_inspected_empty_bind_storage_avoids_an_existing_data_transition(monkeypatch, storage, matched, ready):
    from ansible.plugins.action import ActionBase

    check = load("ansible/action_plugins/service_operational_check.py", "lifecycle_storage_test")
    monkeypatch.setattr(ActionBase, "run", lambda *args: {})
    action = object.__new__(check.ActionModule)
    metadata = {"name": "new-service", "volumes": {"data": {"type": storage, "source": "/nonproduction/data"}}}
    action._task = SimpleNamespace(check_mode=False, args={"phase": "ownership", "metadata": metadata})
    action.runtime = lambda *args: {"managed": False}
    calls = []

    def module(name, args):
        calls.append(name)
        return {"stat": {"exists": True, "isdir": True}, "matched": matched, "skipped_paths": {}}

    action.module = module
    result = action.run(task_vars={})
    assert result["ownership_transition"] is ready
    if storage == "volume":
        assert not calls


def test_new_rootful_podman_caller_can_wait_without_inventing_a_container_identity():
    binding = {"kind": "service", "runtime": "podman", "phase": "podman", "mode": "rootful", "selector": "future"}
    with pytest.raises(MGT.FW.MissingRuntimeCaller):
        MGT.FW.container_identities(binding, lambda argv: "" if "ps" in argv else (_ for _ in ()).throw(AssertionError("unexpected read")))
    policy = {"callers": {"future": [binding]}, "managed_services": {}}
    assert ENGINE.deferred_caller(policy, "future: no local running caller for podman:future")
    policy["managed_services"]["future"] = {"runtime": {"service": "future"}}
    assert not ENGINE.deferred_caller(policy, "future: no local running caller for podman:future")


@pytest.mark.parametrize("standalone", [False, True])
def test_unlisted_docker_project_members_are_rejected_before_lifecycle_mutation(monkeypatch, standalone):
    from ansible.errors import AnsibleActionFail
    from ansible.plugins.action import ActionBase

    check = load("ansible/action_plugins/service_operational_check.py", "lifecycle_membership_test")
    monkeypatch.setattr(ActionBase, "run", lambda *args: {})
    action = object.__new__(check.ActionModule)
    metadata = {"name": "utility", "runtime": "docker", "deploy": {"host": "manager", "type": "container" if standalone else "swarm"}}
    action._task = SimpleNamespace(check_mode=False, args={"phase": "placement", "metadata": metadata})
    calls = []

    def unexpected_runtime(*args):
        calls.append("runtime")
        return {"managed": False}

    action.runtime = unexpected_runtime
    action.command = lambda argv: "unlisted-id\tother-service" if standalone else "utility_other-service"
    with pytest.raises(AnsibleActionFail, match="other"):
        action.run(task_vars={})
    assert calls == []
    action.command = lambda argv: "selected-id\tutility" if standalone else "utility_utility"
    assert action.run(task_vars={})["managed"] is False
    assert calls == ["runtime"]


def test_changed_retry_retires_ports_from_a_failed_prior_stage(tmp_path, monkeypatch):
    store = Store(tmp_path / "policy.json", monkeypatch)
    original, changed = request(port=18010), request(port=18011)
    store.fail = "apply"
    with pytest.raises(RuntimeError, match="apply failure"):
        ENGINE.transact(store, original, "stage", "failed", lambda _: None)
    store.fail = None
    ENGINE.transact(store, changed, "stage", "retry", lambda _: None)
    observed = []
    ENGINE.transact(store, changed, "finish", "retry", observed.append)
    assert ("obsolete_absent", [18010]) in observed
    assert [e["port"] for e in store.current["endpoints"]] == [18011]
    worker = {"sources_verified": True, "sources": ["192.0.2.48"], "ports": []}
    original["profile"] = changed["profile"] = "workers"
    stage = ENGINE.merge(worker, original, "stage", "failed")
    stage["managed_services"]["utility"]["pending"] = False
    retried = ENGINE.merge(stage, changed, "stage", "retry")
    final = ENGINE.merge(retried, changed, "finish", "retry")
    assert final["ports"] == [18011]


def test_new_rootless_client_without_a_manager_does_not_block_its_provider(monkeypatch):
    desired = request()
    policy = {"callers": {"proxy": [desired["callers"]["proxy"]["binding"]]}, "managed_services": {}}
    monkeypatch.setattr(REMOTE.pwd, "getpwnam", lambda _: SimpleNamespace(pw_uid=2147483000))
    original_is_dir = Path.is_dir
    monkeypatch.setattr(Path, "is_dir", lambda path: False if str(path) == "/run/user/2147483000" else original_is_dir(path))

    def no_runtime_query(argv):
        raise AssertionError("inactive future caller must not activate/query a runtime")

    monkeypatch.setattr(REMOTE, "command", no_runtime_query)
    result = REMOTE.qualified_probes(desired, policy)
    assert result["handshakes"][0]["pending_activation"] is True
    assert "connected" not in result["handshakes"][0]
    assert not ENGINE.future_caller({}, "unknown")


def provider_request(store, name="newapp"):
    provider = request("database", 5432)
    provider["endpoints"][0]["ids"] = ["database/postgres"]
    provider["endpoints"][0]["destination"] = 5432
    provider["endpoints"][0]["callers"] = ["oldapp"]
    provider["callers"] = {"oldapp": identity("oldapp")}
    if not store.current["endpoints"]:
        ENGINE.transact(store, provider, "stage", "provider", lambda _: None)
        ENGINE.transact(store, provider, "finish", "provider", lambda _: None)
    client = request(name)
    client["endpoints"] = []
    client["providers"] = [{"runtime": provider["runtime"], "endpoints": [provider["endpoints"][0] | {"callers": [name]}]}]
    return client


def test_client_access_uses_existing_provider_and_cleans_only_owned_contributions(tmp_path, monkeypatch):
    store = Store(tmp_path / "policy.json", monkeypatch)
    client = provider_request(store)
    original = deepcopy(store.current)
    events = []
    ENGINE.access_transact(store, client, "access_stage", "new", events.append)
    endpoint = store.current["endpoints"][0]
    assert endpoint["callers"] == ["newapp", "oldapp"]
    assert store.current["callers"]["newapp"] == [client["runtime"]["binding"]]
    assert events == [("provider", client["providers"][0]["runtime"])]
    assert store.current["managed_services"]["newapp"]["access"]["pending"]
    with pytest.raises(ValueError, match="unfinished provider/service operation"):
        ENGINE.access_transact(store, client, "access_stage", "competing-operation", lambda _: None)
    assert store.current["managed_services"]["newapp"]["access"]["token"] == "new"
    ENGINE.transact(store, client, "stage", "new", lambda _: None)
    ENGINE.access_transact(store, client, "access_activate", "new", lambda _: None)
    ENGINE.transact(store, client, "finish", "new", lambda _: None)
    ENGINE.access_transact(store, client, "access_finish", "new", lambda _: None)
    # Recreate reuses the same ownership rather than claiming the baseline ACL.
    ENGINE.access_transact(store, client, "access_stage", "recreate", lambda _: None)
    ENGINE.access_transact(store, client, "access_finish", "recreate", lambda _: None)
    ENGINE.access_transact(store, client | {"providers": []}, "access_remove", "remove", events.append)
    assert store.current["endpoints"] == original["endpoints"]
    assert store.current["callers"] == original["callers"]
    assert events[-1] == "absent"


def test_failed_client_access_and_concurrent_provider_changes_retain_current_union(tmp_path, monkeypatch):
    store = Store(tmp_path / "policy.json", monkeypatch)
    a, b = provider_request(store), provider_request(store, "second")

    def stage(client):
        ENGINE.access_transact(store, client, "access_stage", client["service"], lambda _: None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(stage, [a, b]))
    store.fail = "apply"
    with pytest.raises(RuntimeError, match="apply failure"):
        ENGINE.access_transact(store, a, "access_activate", a["service"], lambda _: None)
    assert store.current["managed_services"][a["service"]]["access"]["failed"]
    assert set(store.current["endpoints"][0]["callers"]) == {"oldapp", "newapp", "second"}
    store.fail = None
    # A concurrent provider deployment cannot erase a client's contribution.
    provider = request("database", 5432)
    provider["endpoints"][0].update(ids=["database/postgres"], destination=5432, callers=["oldapp"])
    provider["callers"] = {"oldapp": identity("oldapp")}
    ENGINE.transact(store, provider, "stage", "provider-update", lambda _: None)
    ENGINE.transact(store, provider, "finish", "provider-update", lambda _: None)
    assert set(store.current["endpoints"][0]["callers"]) == {"oldapp", "newapp", "second"}
    ENGINE.access_transact(store, a, "access_abort", a["service"], lambda _: None)
    ENGINE.access_transact(store, a, "access_stage", "retry", lambda _: None)
    ENGINE.access_transact(store, a, "access_finish", "retry", lambda _: None)
    ENGINE.access_transact(store, a, "access_remove", "remove", lambda _: None)
    assert set(store.current["endpoints"][0]["callers"]) == {"oldapp", "second"}


def test_provider_access_rejects_changed_or_missing_provider_and_preserves_rollback_bindings(tmp_path, monkeypatch):
    store = Store(tmp_path / "policy.json", monkeypatch)
    client = provider_request(store)
    old = deepcopy(store.current)
    changed = deepcopy(client)
    changed["providers"][0]["endpoints"][0]["destination"] = 5433
    with pytest.raises(ValueError, match="missing or changed"):
        ENGINE.access_transact(store, changed, "access_stage", "x", lambda _: None)
    with pytest.raises(RuntimeError, match="provider unavailable"):
        ENGINE.access_transact(store, client, "access_stage", "x", lambda _: (_ for _ in ()).throw(RuntimeError("provider unavailable")))
    assert store.current == old
    # An accepted baseline binding must survive removal of a new contribution.
    baseline = {"kind": "local", "phase": "podman", "account": "podman-newapp", "uid": 2222, "verified": True, "restart_verified": True}
    store.current["callers"]["newapp"] = [baseline]
    ENGINE.access_transact(store, client, "access_stage", "x", lambda _: None)
    ENGINE.access_transact(store, client, "access_remove", "remove", lambda _: None)
    assert baseline in store.current["callers"]["newapp"]
    assert "newapp" not in store.current["endpoints"][0]["callers"]


def test_inverse_provider_planner_selects_only_declared_client_access():
    catalog = {
        name: {
            "name": name,
            "runtime": "podman",
            "image": "nonproduction:1",
            "deploy": {"host": "manager", "execution": {"mode": "rootless", "host_user": "podman-" + name}},
        }
        for name in ["database", "oldapp", "newapp", "irc"]
    }
    catalog["database"]["ports"] = {"postgres": {"published": 5432, "target": 5432}}
    catalog["newapp"]["postgres"] = {"enable": True}
    catalog["irc"]["ports"] = {"irc": {"published": 16502, "target": 6502, "exposure": "private", "callers": ["newapp"]}}
    planner = load("ansible/action_plugins/mgt_firewall_plan.py", "provider_postgres_planner")
    for cfg in catalog.values():
        cfg["operational_requirements"] = {"acl": ["mgt_backends"]}
    legacy = planner.build_plan(catalog, "manager", lambda value, _: value, [])
    plan = DECL.plan(
        "newapp",
        catalog,
        "manager",
        [],
        {"manager": {"local_ip": "192.0.2.48"}},
        [],
        [e | {"host": "manager"} for e in legacy["endpoints"]],
    )
    assert {p["runtime"]["service"] for p in plan["providers"]} == {"database", "irc"}
    assert all(e["callers"] == ["newapp"] for p in plan["providers"] for e in p["endpoints"])


@pytest.mark.parametrize("mode,failure", [("global", None), ("global", "stop"), ("global", "wait"), ("replicated", None)])
def test_swarm_failure_containment_is_mode_aware_scoped_and_retryable(mode, failure):
    record = identity("selected") | {"binding": {"runtime": "docker", "selector": "selected_selected"}, "swarm_mode": mode}
    calls = []
    attempts = 0

    def run(argv):
        nonlocal attempts
        calls.append(argv)
        cmd = argv[3:]
        if cmd[:2] == ["service", "inspect"]:
            return json.dumps(
                {"id": "immutable-id", "name": "selected_selected", "mode": {"Global" if mode == "global" else "Replicated": {}}}
            )
        if cmd[:2] == ["service", "ps"]:
            return "exact-task"
        if cmd[:2] == ["node", "ls"]:
            return "actual-node-id"
        if cmd[:2] in [["service", "update"], ["service", "rm"], ["service", "scale"]]:
            if failure == "stop":
                raise RuntimeError("contained command failed")
            return ""
        if cmd[:3] == ["inspect", "--type", "task"]:
            attempts += 1
            return json.dumps("running" if failure == "wait" or attempts == 1 else "shutdown")
        raise AssertionError(argv)

    if failure:
        with pytest.raises((ValueError, RuntimeError), match="did not stop|command failed"):
            CONTAIN.contain_swarm(record, run, sleep=lambda _: None)
        failure = None
    result = CONTAIN.contain_swarm(record, run, sleep=lambda _: None)
    assert result["contained"]
    mutations = [a for a in calls if a[3:5] in [["service", "rm"], ["service", "scale"]]]
    assert all(a[-1] == ("immutable-id" if mode == "global" else "immutable-id=0") for a in mutations)
    assert all(a[4] == ("rm" if mode == "global" else "scale") for a in mutations)


@pytest.mark.integration
@pytest.mark.parametrize("mode,stop_fails", [("global", False), ("global", True), ("global", "after-stop"), ("replicated", False)])
def test_production_stack_rescue_contains_exact_service_and_retains_original_failure(tmp_path, mode, stop_fails):
    import os
    import subprocess
    import sys

    import yaml
    from ansible_task_cases import walk_tasks

    plugins = tmp_path / "actions"
    plugins.mkdir()
    # Resolve the unselected Compose module without installed collections. Any
    # accidental execution fails instead of contacting a runtime.
    module = tmp_path / "collections/ansible_collections/community/docker/plugins/modules/docker_compose_v2.py"
    module.parent.mkdir(parents=True)
    module.write_text("raise AssertionError('unselected Compose runtime is inaccessible')\n")
    (plugins / "service_firewall_lifecycle.py").write_text(f"""
import importlib.util, json
from pathlib import Path
from types import SimpleNamespace
spec = importlib.util.spec_from_file_location('fixture', {str(Path(__file__).resolve())!r})
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
class ActionModule(f.ACTION.ActionModule):
    def _execute_module(self, module_name, module_args, task_vars):
        data = json.loads(module_args['stdin'])
        root = Path(task_vars['fixture_root'])
        with (root / 'events').open('a') as log:
            log.write(data['phase'] + '\\n')
        try:
            if data['phase'] == 'contain':
                def run(argv):
                    cmd = argv[3:]
                    if cmd[:2] == ['service', 'inspect']:
                        return json.dumps({{'id': 'exact-service-id', 'name': 'utility_utility', 'mode': {{task_vars['fixture_mode']: {{}}}}}})
                    if cmd[:2] == ['service', 'ps']: return 'exact-task-id'
                    if cmd[:2] == ['node', 'ls']: return 'inventory-node-id'
                    if cmd[:2] in [['service', 'scale'], ['service', 'update'], ['service', 'rm']]:
                        if task_vars['fixture_stop_fails']:
                            if task_vars['fixture_stop_fails'] == 'after-stop': (root / 'writer').unlink(missing_ok=True)
                            raise RuntimeError('NONPRODUCTION scoped stop failed')
                        (root / 'writer').unlink(missing_ok=True)
                        return ''
                    if cmd[:3] == ['inspect', '--type', 'task']: return json.dumps('shutdown')
                    raise AssertionError(argv)
                result = f.CONTAIN.contain_swarm(data['request']['runtime'], run, sleep=lambda _: None)
            else:
                store = f.Store(root / 'policy.json', SimpleNamespace(setattr=lambda obj, name, value: setattr(obj, name, value)))
                store.current = json.loads(store.path.read_text())
                store.kernel.state = {{int(k): v for k, v in json.loads((root / 'kernel.json').read_text()).items()}}
                def runtime(expected):
                    if expected == 'absent' and (root / 'writer').exists(): raise RuntimeError('selected writer remains')
                result = f.ENGINE.transact(store, data['request'], data['phase'], data['token'], runtime)
                (root / 'kernel.json').write_text(json.dumps(store.kernel.state))
            return {{'rc': 0, 'stdout': json.dumps(result)}}
        except (RuntimeError, ValueError) as error:
            return {{'rc': 1, 'stderr': str(error)}}
""")
    (plugins / "docker_services_contain.py").write_text(f"""
import importlib.util, json
from pathlib import Path
spec = importlib.util.spec_from_file_location('transport', {str(plugins / "service_firewall_lifecycle.py")!r})
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)
class ActionModule(transport.f.CONTAIN_ACTION.ActionModule):
    def _execute_module(self, module_name, module_args, task_vars):
        data = json.loads(module_args['stdin'])
        module_args = {{**module_args, 'stdin': json.dumps({{'phase': 'contain', 'request': data}})}}
        return transport.ActionModule._execute_module(self, module_name, module_args, task_vars)
""")
    store = Store(tmp_path / "policy.json", SimpleNamespace(setattr=lambda obj, name, value: setattr(obj, name, value)))
    desired = request()
    # Keep caller rules independent of the selected writer's runtime.
    desired["runtime"]["binding"] = {"kind": "service", "runtime": "docker", "phase": "docker", "selector": "utility_utility"}
    desired["runtime"]["swarm_mode"] = mode
    ENGINE.transact(store, desired, "stage", "failed-operation", lambda _: None)
    (tmp_path / "kernel.json").write_text(json.dumps(store.kernel.state))
    (tmp_path / "writer").touch()
    plan = {
        **desired,
        "managed": True,
        "controller": "manager",
        "hosts": ["manager"],
        "inventory": {"manager": "192.0.2.48"},
        "profile": {"manager": "mgt"},
        "token": "failed-operation",
        "providers": [],
        "access_hosts": [],
    }
    # Execute the production deploy/rescue block, replacing only the failing
    # application deployment boundary. No file/stack/runtime socket is reachable.
    task = next(
        entry
        for entry in walk_tasks(yaml.safe_load((ROOT / "ansible/roles/docker_services/tasks/sub_tasks/deploy/stack.yml").read_text()))
        if any("docker_services_contain" in child for child in walk_tasks(entry.get("rescue", [])))
    )
    task["block"] = [{"name": "NONPRODUCTION deployment failure", "ansible.builtin.fail": {"msg": "original deployment failure"}}]
    playbook = tmp_path / "rescue.yml"
    variables = {
        "fixture_root": str(tmp_path),
        "fixture_mode": "Global" if mode == "global" else "Replicated",
        "fixture_stop_fails": stop_fails,
        "services_storage_host": "storage",
        "docker_services_deploy_stack_type": "swarm",
        "docker_services_deploy_stack_host_effective": "manager",
        "docker_services_deploy_stack_name": "utility",
        "_stack_def": {"firewall_plans": {"utility": plan}},
    }
    playbook.write_text(
        yaml.safe_dump(
            [{"hosts": "manager", "connection": "local", "gather_facts": False, "become": False, "vars": variables, "tasks": [task]}]
        )
    )
    config = tmp_path / "ansible.cfg"
    config.write_text(
        f"[defaults]\ncollections_path={tmp_path / 'collections'}\nroles_path={ROOT / 'ansible/roles'}\naction_plugins={plugins}\nvars_plugins_enabled=\nstdout_callback=default\n[inventory]\nenable_plugins=host_list\n"
    )
    argv = [str(Path(sys.executable).parent / "ansible-playbook"), "-i", "manager,", str(playbook)]

    def execute():
        return subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=35,
            env={**os.environ, "ANSIBLE_CONFIG": str(config), "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local")},
        )

    result = execute()
    assert result.returncode != 0 and "NONPRODUCTION deployment failure" in result.stdout, result.stdout + result.stderr
    saved = json.loads(store.path.read_text())["managed_services"]["utility"]
    assert saved["pending"] is bool(stop_fails)
    assert (tmp_path / "writer").exists() is (stop_fails is True)
    assert (tmp_path / "events").read_text().splitlines() == ["contain", "abort"]
    if stop_fails:
        assert saved["containment_failed"] and "scoped stop failed" in result.stdout
        # The same supported containment path succeeds after a transient stop
        # failure; no stale snapshot, node drain or daemon operation is needed.
        variables["fixture_stop_fails"] = False
        playbook.write_text(
            yaml.safe_dump(
                [{"hosts": "manager", "connection": "local", "gather_facts": False, "become": False, "vars": variables, "tasks": [task]}]
            )
        )
        retry = execute()
        assert retry.returncode != 0 and "original deployment failure" in retry.stdout
        assert not json.loads(store.path.read_text())["managed_services"]["utility"]["pending"]
        assert not (tmp_path / "writer").exists()


def test_access_withdrawal_and_shared_provider_declarations_keep_their_ownership(tmp_path, monkeypatch):
    store = Store(tmp_path / "policy.json", monkeypatch)
    client = provider_request(store)
    ENGINE.access_transact(store, client, "access_stage", "first", lambda _: None)
    ENGINE.access_transact(store, client, "access_finish", "first", lambda _: None)
    # Withdrawing the relationship reconciles only the owned contribution.
    withdrawn = client | {"providers": []}
    ENGINE.access_transact(store, withdrawn, "access_stage", "withdraw", lambda _: None)
    ENGINE.access_transact(store, withdrawn, "access_finish", "withdraw", lambda _: None)
    assert store.current["endpoints"][0]["callers"] == ["oldapp"]
    ENGINE.access_transact(store, client, "access_stage", "second", lambda _: None)
    changed = deepcopy(client)
    changed["runtime"]["binding"]["account"] = "podman-other"
    with pytest.raises(ValueError, match="identity/placement changed"):
        ENGINE.access_transact(store, changed, "access_stage", "changed", lambda _: None)
    # A later explicit provider deployment may adopt the shared permission.
    provider = request("database", 5432)
    provider["endpoints"][0].update(
        ids=["database/postgres"], destination=5432, callers=["oldapp", "newapp"], purpose="declared private publication"
    )
    provider["callers"] = {name: identity(name) for name in ["oldapp", "newapp"]}
    ENGINE.transact(store, provider, "stage", "shared", lambda _: None)
    ENGINE.transact(store, provider, "finish", "shared", lambda _: None)
    ENGINE.access_transact(store, client, "access_remove", "remove", lambda _: None)
    assert store.current["endpoints"][0]["callers"] == ["newapp", "oldapp"]
    assert store.current["callers"]["newapp"] == [client["runtime"]["binding"]]


def test_explicit_provider_relationship_is_discovered_without_a_legacy_catalog():
    catalog = {
        name: {
            "runtime": "podman",
            "image": "registry.invalid/nonproduction:1",
            "deploy": {"host": "manager", "execution": {"mode": "rootless", "host_user": "podman-" + name}},
        }
        for name in ["provider", "client", "unrelated"]
    }
    catalog["provider"]["ports"] = {"api": {"exposure": "private", "callers": ["client", "unrelated"], "published": 18030, "target": 8080}}
    result = DECL.plan("client", catalog, "manager", [], {"manager": {"local_ip": "192.0.2.48"}})
    assert result["managed"] and result["providers"][0]["endpoints"][0]["callers"] == ["client"]
    assert not result["endpoints"]


def test_docker_containment_action_check_mode_and_transport_errors_are_safe(monkeypatch):
    from ansible.plugins.action import ActionBase

    monkeypatch.setattr(ActionBase, "run", lambda *args: {})
    action = object.__new__(CONTAIN_ACTION.ActionModule)
    record = identity("utility") | {"binding": {"runtime": "docker", "selector": "utility_utility"}, "swarm_mode": "global"}
    action._task = SimpleNamespace(args={"runtime": record, "inventory_host": "manager"}, check_mode=True)
    calls = []

    def execute(**kwargs):
        calls.append(kwargs)
        assert json.loads(kwargs["module_args"]["stdin"]) == {"runtime": record}
        return {"rc": 1, "stderr": "NONPRODUCTION containment failed", "invocation": {"must_not_escape": True}}

    action._execute_module = execute
    assert action.run()["skipped"] and not calls
    action._task.check_mode = False
    result = action.run(task_vars={"hostvars": {"manager": {}}})
    assert result["failed"] and "NONPRODUCTION containment failed" in result["msg"]
    assert "invocation" not in result and "cmd" not in result
    assert len(calls) == 1


@pytest.mark.parametrize("phase", ["access_finish", "access_remove"])
@pytest.mark.parametrize("failure", ["test", "apply", "audit", "finalize"])
def test_permission_withdrawal_retains_identity_other_grants_and_retry_ownership(tmp_path, monkeypatch, failure, phase):
    store = Store(tmp_path / "policy.json", monkeypatch)
    client = provider_request(store)
    baseline = {"kind": "local", "phase": "podman", "account": "podman-newapp", "uid": 2222, "verified": True, "restart_verified": True}
    store.current["callers"]["newapp"] = [baseline]
    provider_a = {
        "ids": ["existing/api"],
        "service": "existing",
        "port": 18030,
        "destination": 8080,
        "callers": ["newapp"],
        "purpose": "retained provider-owned permission",
    }
    store.current["endpoints"].append(provider_a)
    store.apply(store.current, client, "stage")
    ENGINE.access_transact(store, client, "access_stage", "first", lambda _: None)
    ENGINE.access_transact(store, client, "access_finish", "first", lambda _: None)
    original_a = deepcopy(provider_a)
    if phase == "access_finish":
        client = deepcopy(client)
        client["providers"] = []
        ENGINE.access_transact(store, client, "access_stage", "remove", lambda _: None)
    audit, write = store.audit, store.write
    if failure in {"test", "apply"}:
        store.fail = failure
    elif failure == "audit":

        def fail_audit(policy, recovering=False):
            if policy["managed_services"]["newapp"].get("access", {}).get("withdrawing"):
                raise RuntimeError("audit failure")
            audit(policy, recovering)

        monkeypatch.setattr(store, "audit", fail_audit)
    else:

        def fail_finalize(policy):
            receipt = policy.get("managed_services", {}).get("newapp", {}).get("access", {})
            if not receipt.get("ports") and not receipt.get("withdrawing"):
                raise RuntimeError("finalize failure")
            write(policy)

        monkeypatch.setattr(store, "write", fail_finalize)
    with pytest.raises(RuntimeError, match=failure + " failure"):
        ENGINE.access_transact(store, client, phase, "remove", lambda _: None)
    assert store.current["managed_services"]["newapp"]["access"]["ports"] == [5432]
    assert original_a in store.current["endpoints"] and baseline in store.current["callers"]["newapp"]
    store.fail = None
    monkeypatch.setattr(store, "audit", audit)
    monkeypatch.setattr(store, "write", write)
    retry_token = "remove" if phase == "access_finish" else "retry"
    ENGINE.access_transact(store, client, phase, retry_token, lambda _: None)
    assert "newapp" not in next(e for e in store.current["endpoints"] if e["port"] == 5432)["callers"]
    assert original_a in store.current["endpoints"] and baseline in store.current["callers"]["newapp"]
    saved, events = deepcopy(store.current), list(store.events)
    assert not ENGINE.access_transact(store, client, phase, retry_token, lambda _: None)["changed"]
    assert store.current == saved and store.events.count("write") == events.count("write")


def test_cancel_releases_only_its_token_without_testing_or_stopping_providers(tmp_path, monkeypatch):
    store = Store(tmp_path / "policy.json", monkeypatch)
    client = provider_request(store)
    ENGINE.access_transact(store, client, "access_stage", "owner", lambda _: None)
    current = deepcopy(store.current)
    with pytest.raises(ValueError, match="no longer belongs"):
        ENGINE.access_transact(store, client, "access_cancel", "competitor", lambda _: None)
    assert store.current == current

    def forbidden(*args, **kwargs):
        raise AssertionError("cancellation must not audit/stop/change running applications or protection")

    monkeypatch.setattr(store, "audit", forbidden)
    monkeypatch.setattr(store, "test", forbidden)
    monkeypatch.setattr(store, "prepare", forbidden)
    monkeypatch.setattr(store, "apply", forbidden)
    assert ENGINE.access_transact(store, client, "access_cancel", "owner", forbidden)["changed"]
    assert store.current["endpoints"] == current["endpoints"] and store.current["callers"] == current["callers"]
    events = list(store.events)
    assert not ENGINE.access_transact(store, client, "access_cancel", "owner", forbidden)["changed"]
    assert store.events == events
