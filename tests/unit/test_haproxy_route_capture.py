"""Bounded socket observation and reuse are tied to continuous host/caller identities."""

import hashlib
import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from test_mgt_firewall import FW, PREFLIGHT, PreflightHost


@pytest.mark.integration
@pytest.mark.parametrize("operation", ["collect", "candidates"])
@pytest.mark.parametrize("default_expansion", [False, True])
def test_embedded_collector_preserves_account_shell_variables_through_actual_ansible(tmp_path, operation, default_expansion):
    """command's default argument expansion must not substitute the become HOME."""
    root = Path(__file__).resolve().parents[2]
    playbook = {"tasks": yaml.safe_load((root / "ansible/operations/haproxy-firewall-preflight.yml").read_text())}
    name = "Collect projected" if operation == "collect" else "Generate unverified additions"
    command = deepcopy(next(task["ansible.builtin.command"] for task in playbook["tasks"] if name in task["name"]))
    if default_expansion:
        command.pop("expand_argument_vars", None)
    operator = tmp_path / "private-operator"
    account_home = tmp_path / "dedicated-home"
    operator.mkdir(mode=0o700)
    account_home.mkdir(mode=0o700)
    result_path = tmp_path / "child.json"
    child = (
        "import json,os,sys; "
        "print(json.dumps({'cwd':os.getcwd(),'home':os.environ['HOME'],"
        "'runtime':os.environ['XDG_RUNTIME_DIR'],'bus':os.environ['DBUS_SESSION_BUS_ADDRESS'],'args':sys.argv[1:]}))"
    )
    arguments = ["space in argument", "$HOME stays literal", "quote'and\"double", "$(must-not-execute)"]
    # Embed the actual collector source, including its literal $HOME/$@ shell.
    source = (root / "ansible/roles/service_firewall/files/haproxy-preflight.py").read_text().split('if __name__ == "__main__":')[0]
    source += (
        "\nimport subprocess\n"
        f"account=SimpleNamespace(pw_dir={str(account_home)!r},pw_uid=12345)\n"
        "argv=podman_command(account,'fixture-account')\n"
        # Run the exact env/shell/exec portion without runuser or a real Podman.
        # The child observes actual cwd and environment; no runtime is contacted.
        f"argv=argv[4:-2]+[{sys.executable!r},'-c',{child!r}]+{arguments!r}\n"
        "result=subprocess.run(argv,check=True,text=True,capture_output=True)\n"
        f"Path({str(result_path)!r}).write_text(result.stdout)\n"
    )
    command["argv"][0] = sys.executable
    command["stdin"] = "{}"
    source_file = tmp_path / "collector.py"
    source_file.write_text(source)
    play = tmp_path / "play.yml"
    play.write_text(
        yaml.safe_dump(
            [
                {
                    "name": "Execute embedded dedicated-account wrapper locally",
                    "hosts": "fixture",
                    "gather_facts": False,
                    "vars": {"haproxy_preflight_source": "{{ lookup('ansible.builtin.file', '" + str(source_file) + "') }}"},
                    "tasks": [{"name": "Use actual collector command options", "ansible.builtin.command": command, "changed_when": False}],
                }
            ],
            sort_keys=False,
        )
    )
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(
        yaml.safe_dump(
            {
                "all": {
                    "hosts": {
                        "fixture": {
                            "ansible_connection": "local",
                            "ansible_python_interpreter": sys.executable,
                        }
                    }
                }
            }
        )
    )
    cfg = tmp_path / "ansible.cfg"
    cfg.write_text("[defaults]\nstdout_callback=default\n[inventory]\nenable_plugins=yaml\n")
    result = subprocess.run(
        [str(Path(sys.executable).with_name("ansible-playbook")), "-i", str(inventory), str(play)],
        cwd=operator,
        env={**os.environ, "HOME": str(operator), "ANSIBLE_CONFIG": str(cfg), "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local")},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    observed = json.loads(result_path.read_text())
    if default_expansion:
        assert observed["cwd"] == str(operator) and observed["home"] == str(account_home)
        return
    assert observed == {
        "cwd": str(account_home),
        "home": str(account_home),
        "runtime": "/run/user/12345",
        "bus": "unix:path=/run/user/12345/bus",
        "args": arguments,
    }


def fixture(host="manager"):
    machine = PreflightHost(host)
    fw = SimpleNamespace(
        NAME=FW.NAME,
        integer=FW.integer,
        OWNED=SimpleNamespace(local_addresses=lambda run: {machine.address}),
        container_identities=lambda binding, run: [{"address": "172.18.0.2", "mac": "02:42:ac:12:00:02", "veth": "veth-fixture"}],
    )
    config = {
        "host": host,
        "controller": "manager",
        "expected": {"inventory_address": machine.address},
        "port": 5432,
        "accounts": [],
        "running_rootless_accounts": [],
        "window_seconds": 2,
        "sample_interval": 0.5,
        "capture_callers": ["infisical", "qui-alpha", "qui-bravo"],
    }
    initial = PREFLIGHT.collect({**config, "window_seconds": 0}, fw, machine.run, identity_lookup=machine.identity)
    return machine, fw, config, initial


def window(machine, fw, config, report, run=None, changed=None):
    now = [0.0]
    original = run or machine.run

    def sample(argv, data=None):
        if argv[0] == "nsenter" and "ss" in argv:
            # A short-lived connection exists ONLY during application activity.
            return original(argv, data) if 0.5 <= now[0] <= 1 else ""
        return original(argv, data)

    def sleep(seconds):
        now[0] += seconds
        if changed and now[0] >= 1:
            changed()

    return PREFLIGHT.capture_window(config, report, fw, sample, machine.account, machine.identity, clock=lambda: now[0], sleep=sleep)


@pytest.mark.parametrize("host", ["manager", "worker", "plex"])
def test_window_retains_short_lived_activity_after_final_snapshot_is_idle(host):
    machine, fw, config, report = fixture(host)
    result = window(machine, fw, config, report)
    assert result["capture"]["complete"] is True and result["capture"]["samples"] == 5
    assert len(result["containers"][0]["destinations"]) == 1
    if host == "manager":
        assert result["containers"][0]["binding"]["compose"] == {"project": "actual-infisical", "service": "infisical"}
    assert result["containers"][0]["binding"]["verified"] is False
    assert not any(".Env" in str(call) or "restart" in call or "connect" in call for call in machine.calls)


@pytest.mark.parametrize("change", ["pid", "replacement", "namespace", "start", "labels", "bridge", "host", "address", "command"])
def test_capture_rejects_replacement_and_identity_mismatches(change):
    machine, fw, config, report = fixture()
    altered = [False]
    original = machine.run

    def run(argv, data=None):
        if altered[0]:
            if change == "replacement" and argv[:4] == PREFLIGHT.DOCKER + ["ps"]:
                return "replacement-container"
            if change == "namespace" and argv[0] == "readlink":
                return "different-namespace"
            if change == "start" and argv[0] == "cat":
                return "1234 (reused pid) " + " ".join(["0"] * 19 + ["999"])
            if change == "command" and argv[0] == "nsenter":
                raise RuntimeError("ss: permission denied")
        return original(argv, data)

    def mutate():
        altered[0] = True
        if change == "pid":
            machine.pid += 1
        if change == "labels":
            machine.name = "other-app"
        if change == "host":
            machine.host = "other"
        if change == "address":
            machine.address = "192.0.2.99"
        if change == "bridge":
            fw.container_identities = lambda binding, run: [{"address": "172.18.0.99"}]

    with pytest.raises((ValueError, RuntimeError)):
        window(machine, fw, config, report, run, mutate)


def test_host_namespace_connections_remain_process_owned_during_window():
    machine, fw, config, _ = fixture()
    machine.host_network = True
    initial = PREFLIGHT.collect({**config, "window_seconds": 0}, fw, machine.run, identity_lookup=machine.identity)
    assert window(machine, fw, config, initial)["containers"][0]["destinations"] == []
    machine.owned_socket = True
    initial = PREFLIGHT.collect({**config, "window_seconds": 0}, fw, machine.run, identity_lookup=machine.identity)
    assert window(machine, fw, config, initial)["containers"][0]["destinations"][0]["owner_pids"] == [machine.pid]


@pytest.mark.parametrize("change", [None, "id", "pid", "netns", "start_time", "labels", "bridge", "boot", "uid", "incomplete", "legacy"])
def test_reuse_requires_same_identity_and_recomputes_routes_from_fresh_topology(change):
    machine, fw, config, report = fixture("manager" if change == "bridge" else "worker")
    captured = window(machine, fw, config, report)
    fresh = PREFLIGHT.collect({**config, "window_seconds": 0}, fw, machine.run, identity_lookup=machine.identity)
    fresh["containers"][0]["destinations"] = []
    # The same VIP changes from mixed placement to worker-only without caller replacement.
    captured["topology"]["services"] = [
        {
            "name": "db_haproxy",
            "vips": [{"Addr": "172.98.0.144/24", "NetworkID": "overlay-id"}],
            "tasks": [{"node_id": "node-manager", "state": "running", "networks": []}],
        }
    ]
    fresh["topology"]["services"] = [
        {
            "name": "db_haproxy",
            "vips": [{"Addr": "172.98.0.144/24", "NetworkID": "overlay-id"}],
            "tasks": [{"node_id": "node-worker", "state": "running", "networks": []}],
        }
    ]
    if change in {"id", "pid", "netns", "start_time"}:
        fresh["containers"][0][change] = "changed"
    if change == "labels":
        fresh["containers"][0]["swarm"] = "other-service"
    if change == "bridge":
        fresh["containers"][0]["identities"][0]["veth"] = "replacement-veth"
    if change == "boot":
        fresh["identity"]["boot_id"] = "different"
    if change == "incomplete":
        captured["capture"]["complete"] = False
    if change == "legacy":
        for key in ["id", "netns", "start_time"]:
            captured["containers"][0].pop(key)
        captured.pop("capture")
    if change == "uid":
        captured["accounts"]["podman-forgejo"] = {"uid": 1004, "containers": [{"destinations": []}]}
        fresh["accounts"]["podman-forgejo"] = {"uid": 1005}
    if change:
        with pytest.raises(ValueError):
            PREFLIGHT.merge_capture([fresh], [captured])
        return
    original = deepcopy(captured)
    PREFLIGHT.merge_capture([fresh], [captured])
    PREFLIGHT.map_routes([fresh], "manager", "haproxy", ["worker", "plex"])
    route = fresh["containers"][0]["destinations"][0]["routes"][0]
    assert route["provider"] is True and route["worker_only"] is True
    assert captured == original
    assert fresh["containers"][0]["binding"]["verified"] is False


def test_targeted_window_rechecks_idle_callers_at_completion():
    machine, fw, config, report = fixture()
    config["identity_callers"] = config["capture_callers"]
    config["capture_callers"] = ["authelia"]
    before = len(machine.calls)
    with pytest.raises(ValueError, match="labels/PID changed"):
        window(machine, fw, config, report, changed=lambda: setattr(machine, "pid", 9999))
    assert not any(argv[0] == "nsenter" for argv in machine.calls[before:])


def test_targeted_capture_combines_windows_with_original_provenance_and_fresh_routes(tmp_path):
    earlier, current = [], []
    for host in PreflightHost.addresses:
        machine, fw, config, report = fixture(host)
        old = window(machine, fw, config, report)
        # The prior full window missed only Infisical. Its one-shot predecessor
        # cannot supply the missing PID/namespace evidence.
        if host == "manager":
            old["containers"][0]["destinations"] = []
        else:
            old["containers"][0]["destinations"][0]["routes"] = [{"kind": "unresolved"}]
        earlier.append(old)
        fresh = PREFLIGHT.collect({**config, "window_seconds": 0}, fw, machine.run, identity_lookup=machine.identity)
        current.append(
            window(machine, fw, {**config, "identity_callers": config["capture_callers"], "capture_callers": ["infisical"]}, fresh)
        )
        assert bool(current[-1]["containers"][0]["destinations"]) is (host == "manager")
    source = tmp_path / "earlier.metadata.json"
    source.write_text(json.dumps(earlier))
    snapshot = deepcopy(earlier)
    result = PREFLIGHT.candidates(
        {
            "plan": {
                "endpoints": [{"ids": ["haproxy/postgres"], "callers": ["infisical", "qui-alpha", "qui-bravo"]}],
                "principals": {
                    "infisical": {"inventory_hosts": "manager"},
                    "qui-alpha": {"inventory_hosts": "worker"},
                    "qui-bravo": {"inventory_hosts": "plex"},
                },
            },
            "controller": "manager",
            "workers": ["worker", "plex"],
            "existing": {},
            "expected_hosts": {h: {"inventory_address": a} for h, a in PreflightHost.addresses.items()},
            "collection": [{"haproxy_preflight_host": r["host"], "stdout": json.dumps(r)} for r in current],
            "capture_reports": earlier,
            "capture_source": {"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
        }
    )
    for report in result["reports"]:
        assert report["capture"]["callers"] == ["infisical"]
        connection = report["containers"][0]["destinations"][0]
        if report["host"] != "manager":
            observation = connection["observations"][0]
            assert observation["source"]["path"] == str(source)
            assert observation["capture"] == next(r for r in earlier if r["host"] == report["host"])["capture"]
            assert connection["routes"][0]["provider"] is True
            route = connection["routes"][0]
            if report["host"] == "worker":
                assert route["kind"] == "overlay_service" and route["worker_only"] is True
            else:
                assert route["kind"] == "overlay_task" and route["task_host"] == "plex"
    # Reuse the aggregate again: preserve the original source and window.
    next_reports = deepcopy(result["reports"])
    for report in next_reports:
        for record in report["containers"]:
            record["destinations"] = []
    PREFLIGHT.merge_capture(next_reports, result["reports"], {"path": "aggregate", "sha256": "other"})
    assert (
        next_reports[1]["containers"][0]["destinations"][0]["observations"]
        == result["reports"][1]["containers"][0]["destinations"][0]["observations"]
    )
    for report in next_reports:
        report["topology"]["services"] = []
        report["topology"]["networks"] = []
    PREFLIGHT.map_routes(next_reports, "manager", "haproxy", ["worker", "plex"])
    assert next_reports[1]["containers"][0]["destinations"][0]["routes"] == [{"kind": "unresolved"}]
    assert earlier == snapshot
    assert result["candidate"]["mgt_firewall_inputs_verified"] is False
    assert all(binding["verified"] is False for values in result["candidate"]["mgt_firewall_callers"].values() for binding in values)


@pytest.mark.parametrize(
    "key,value",
    [
        ("window_seconds", True),
        ("window_seconds", 601),
        ("window_seconds", "180"),
        ("sample_interval", False),
        ("sample_interval", 0),
        ("sample_interval", 6),
    ],
)
def test_capture_options_are_bounded_and_strict(key, value):
    machine, fw, config, report = fixture()
    config[key] = value
    with pytest.raises(ValueError):
        window(machine, fw, config, report)


@pytest.mark.integration
@pytest.mark.parametrize(
    "mismatch,check,targeted,address_drift",
    [
        (False, False, False, False),
        (True, False, False, False),
        (False, True, False, False),
        (False, False, True, False),
        (False, False, True, True),
    ],
)
def test_actual_ansible_async_collection_polling_aggregation_and_read_only_check(tmp_path, mismatch, check, targeted, address_drift):
    import json
    import os
    import subprocess
    from pathlib import Path

    import yaml

    root = Path(__file__).resolve().parents[2]
    source_play = {"tasks": yaml.safe_load((root / "ansible/operations/haproxy-firewall-preflight.yml").read_text())}
    tasks = source_play["tasks"]
    first = next(i for i, t in enumerate(tasks) if "Collect projected" in t["name"])
    last = next(i for i, t in enumerate(tasks) if "Prepare optional" in t["name"])
    selected = deepcopy(tasks[first:last])
    executable = str(Path(sys.executable).with_name("ansible-playbook"))
    for task in selected:
        if "ansible.builtin.command" in task:
            task["ansible.builtin.command"]["argv"][0] = sys.executable
    collector = (
        "import json,sys\n"
        f"sys.path.insert(0,{str(Path(__file__).parent)!r})\n"
        "from test_mgt_firewall import PreflightHost,PREFLIGHT\n"
        "config=json.loads(sys.stdin.read())\n"
        "try:\n"
        " if sys.argv[1]=='collect':\n"
        "  host=config['host']\n"
        f"  if {mismatch!r} and host=='worker': host='manager'\n"
        "  result=PreflightHost(host).collect(config)\n"
        " else: result=PREFLIGHT.candidates(config)\n"
        " print(json.dumps(result))\n"
        "except Exception as error:\n"
        " print('host='+config.get('host','manager')+' operation='+sys.argv[1]+': '+str(error),file=sys.stderr)\n"
        " sys.exit(1)\n"
    )
    hosts = PreflightHost.addresses
    plan = {
        "endpoints": [{"ids": ["haproxy/postgres"], "callers": ["infisical", "qui-alpha"]}],
        "principals": {"infisical": {"inventory_hosts": "manager"}, "qui-alpha": {"inventory_hosts": "worker"}},
    }
    output = tmp_path / "candidate.json"
    variables = {
        "haproxy_preflight_source": collector,
        "haproxy_preflight_window_seconds": 1,
        "haproxy_preflight_sample_interval": 0.1,
        "haproxy_preflight_hosts": list(hosts),
        "haproxy_preflight_expected_hosts": {h: {"inventory_address": a} for h, a in hosts.items()},
        "haproxy_preflight_endpoint": {"port": 5432, "service": "haproxy", "callers": ["infisical", "qui-alpha", "qui-bravo"]},
        "haproxy_preflight_accounts": [],
        "haproxy_preflight_running_rootless_accounts": [],
        "services_controller_host": "manager",
        "services_storage_host": "worker",
        "services_plex_host": "plex",
        "mgt_firewall_plan": plan,
        "mgt_firewall_active_endpoints": ["homepage/backend"],
        "mgt_firewall_callers": {"traefik": []},
        "haproxy_preflight_names": {},
        "haproxy_preflight_output": str(output),
    }
    if targeted:
        variables["haproxy_preflight_capture_callers"] = ["infisical"]
        captured = []
        for host in hosts:
            machine, fw, config, report = fixture(host)
            old = window(machine, fw, config, report)
            if host == "manager":
                old["containers"][0]["destinations"] = []
                if address_drift:
                    old["addresses"].append("fe80::1234")
            captured.append(old)
        capture_path = tmp_path / "previous.metadata.json"
        capture_path.write_text(json.dumps(captured))
        variables["haproxy_preflight_capture_metadata"] = str(capture_path)
    play = tmp_path / "play.yml"
    play.write_text(
        yaml.safe_dump(
            [{"name": "Isolated real async fixture", "hosts": "manager", "gather_facts": False, "vars": variables, "tasks": selected}],
            sort_keys=False,
        )
    )
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(
        yaml.safe_dump(
            {
                "all": {
                    "vars": {"ansible_connection": "local", "ansible_python_interpreter": sys.executable},
                    "hosts": {h: {"local_ip": a} for h, a in hosts.items()},
                }
            }
        )
    )
    cfg = tmp_path / "ansible.cfg"
    cfg.write_text("[defaults]\nstdout_callback=default\n[inventory]\nenable_plugins=yaml\n")
    environment = {
        **os.environ,
        "ANSIBLE_CONFIG": str(cfg),
        "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
        "ANSIBLE_ASYNC_DIR": str(tmp_path / "async"),
        "ANSIBLE_LOG_PATH": str(tmp_path / "ansible.log"),
    }
    result = subprocess.run(
        [executable, "-i", str(inventory), str(play), *(["--check"] if check else [])],
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert (result.returncode == 0) is (not mismatch and not address_drift), result.stdout + result.stderr
    assert "FIREWALL_SOURCE" not in result.stdout + result.stderr
    if mismatch:
        assert "observed host identity does not match inventory address" in result.stdout
    elif check:
        assert "changed=0" in result.stdout and not output.exists()
        assert not Path(str(output) + ".collection.json").exists()
        assert not (tmp_path / "async").exists()
    elif address_drift:
        assert "provider-removal transition retained provider identity missing/ambiguous" in result.stdout
        assert not output.exists() and not Path(str(output) + ".metadata.json").exists()
        saved = Path(str(output) + ".collection.json")
        reports = json.loads(saved.read_text())
        assert [r["host"] for r in reports] == list(hosts)
        assert len({r["identity"]["boot_id"] for r in reports}) == 3
        assert reports[0]["identity"] == captured[0]["identity"]
        assert PREFLIGHT.capture_host_differences(reports[0], captured[0]) == {"addresses": {"added": [], "removed": ["fe80::1234"]}}
        assert saved.stat().st_mode & 0o777 == 0o600
        assert "cmd" not in saved.read_text() and "FIREWALL_SOURCE" not in saved.read_text()
    else:
        reports = json.loads(Path(str(output) + ".metadata.json").read_text())
        assert [r["host"] for r in reports] == list(hosts)
        assert len({r["identity"]["boot_id"] for r in reports}) == 3
        assert all(r["capture"]["complete"] and r["capture"]["samples"] >= 2 for r in reports)
        assert not list((tmp_path / "async").glob("*"))
        candidate = json.loads(output.read_text())
        assert candidate["mgt_firewall_inputs_verified"] is False
        if targeted:
            assert all(r["capture"]["callers"] == ["infisical"] for r in reports)
            assert reports[0]["containers"][0]["destinations"]
            assert reports[1]["containers"][0]["destinations"][0]["observations"][0]["source"] == {
                "path": str(capture_path),
                "sha256": hashlib.sha256(capture_path.read_bytes()).hexdigest(),
            }
        assert candidate["mgt_firewall_callers"]["qui-alpha"][0]["route_verified"] is False


@pytest.mark.parametrize("change", [None, "uid", "pid", "namespace"])
def test_rootless_capture_preserves_account_and_continuous_process_identity(change):
    machine, fw, config, _ = fixture()
    config["accounts"] = config["running_rootless_accounts"] = ["podman-forgejo"]
    account = SimpleNamespace(pw_uid=1004, pw_dir="/fake/forgejo")
    machine.account = lambda name: account
    altered = [False]
    pid = [777]
    original = machine.run

    def run(argv, data=None):
        if argv[0] == "runuser":
            assert 'cd "$HOME" || exit; exec "$@"' in argv
            assert "HOME=/fake/forgejo" in argv and "XDG_RUNTIME_DIR=/run/user/1004" in argv
            return "rootless-container" if "ps" in argv else str(pid[0])
        if argv[0] == "cat" and argv[-1].startswith("/proc/777/"):
            return "777 (forgejo) " + " ".join(["0"] * 19 + ["987"])
        if argv[0] == "readlink" and argv[-1].startswith("/proc/777/"):
            return "new-rootless-netns" if change == "namespace" and altered[0] else "rootless-netns"
        if argv[0] == "nsenter" and argv[2] == "777":
            return "0 0 172.19.0.2:12345 192.0.2.48:5432\n"
        return original(argv, data)

    report = PREFLIGHT.collect(
        {**config, "window_seconds": 0}, fw, run, account_lookup=lambda name: account, identity_lookup=machine.identity
    )

    def mutate():
        altered[0] = True
        if change == "uid":
            account.pw_uid = 1005
        if change == "pid":
            pid[0] = 778

    if change:
        with pytest.raises(ValueError):
            window(machine, fw, config, report, run, mutate)
    else:
        result = window(machine, fw, config, report, run)
        record = result["accounts"]["podman-forgejo"]["containers"][0]
        assert record["pid"] == 777 and record["netns"] == "rootless-netns"
        assert record["destinations"][0]["destination"] == "192.0.2.48"


@pytest.mark.parametrize("change", ["link_local", "boot_id", "hostname", "incomplete"])
def test_retained_host_guard_identifies_exact_difference_without_relaxation(change):
    machine, fw, config, report = fixture()
    captured = window(machine, fw, config, report)
    fresh = deepcopy(captured)
    if change == "link_local":
        captured["addresses"].append("fe80::1234")
        expected = {"addresses": {"added": [], "removed": ["fe80::1234"]}}
    elif change in {"boot_id", "hostname"}:
        fresh["identity"][change] = "different"
        expected = {"identity": [change]}
    else:
        captured["capture"]["complete"] = False
        expected = {"capture.complete": "missing or not strict true"}
    assert PREFLIGHT.capture_host_differences(fresh, captured) == expected
    with pytest.raises(ValueError, match="capture host identity differs/incomplete") as error:
        PREFLIGHT.merge_capture([fresh], [captured])
    detail = json.loads(str(error.value).split(": ", 1)[1])
    assert detail == {"host": "manager", "differences": expected}


def provider_transition_fixture():
    old_reports, reports = [], []
    for host in PreflightHost.addresses:
        machine, fw, options, report = fixture(host)
        old = window(machine, fw, options, report)
        fresh = PREFLIGHT.collect({**options, "window_seconds": 0}, fw, machine.run, identity_lookup=machine.identity)
        fresh["containers"][0]["destinations"] = []
        provider = deepcopy(old["containers"][0])
        provider.update(
            id="provider-" + host,
            name="db_haproxy.node-" + host + ".task-" + host,
            swarm="db_haproxy",
            project=None,
            service=None,
            pid=9000 + machine.pid,
            start_time="9876",
            netns="provider-ns-" + host,
            destinations=[],
        )
        provider["binding"] = {"kind": "container", "runtime": "docker", "phase": "docker", "selector": "db_haproxy"}
        provider["identities"] = [{"veth": "veth-provider", "address": "172.18.0.14", "mac": "02:42:ac:12:00:14"}]
        old["containers"].append(provider)
        if host != "manager":
            fresh["containers"].append(deepcopy(provider))
        else:
            old["addresses"].append("fe80::1234")
            old["topology"]["services"][0]["tasks"].append(
                {"id": "task-manager", "node_id": "node-manager", "state": "running", "networks": []}
            )
            old["providers"] = [
                {
                    **{k: old["topology"]["services"][0][k] for k in ["id", "name", "vips", "ports"]},
                    "image": "fixture-haproxy@sha256:fake",
                    "configs": [{"ConfigID": "fixture-native"}],
                }
            ]
        old_reports.append(old)
        reports.append(fresh)
    forgejo = {
        "id": "forgejo",
        "pid": 1004,
        "start_time": "10040",
        "netns": "rootless-ns",
        "host_network": True,
        "account": "podman-forgejo",
        "destinations": [{"destination": "192.0.2.48", "port": 5432}],
    }
    old_reports[0]["accounts"]["podman-forgejo"] = {"uid": 1004, "containers": [deepcopy(forgejo)]}
    forgejo["destinations"] = []
    reports[0]["accounts"]["podman-forgejo"] = {"uid": 1004, "containers": [forgejo]}
    context = {
        "controller": "manager",
        "workers": ["worker", "plex"],
        "expected_hosts": {h: {"inventory_address": a} for h, a in PreflightHost.addresses.items()},
        "plan": {
            "endpoints": [
                {"ids": ["haproxy/postgres"], "callers": ["infisical", "qui-alpha", "qui-bravo", "forgejo", "controller", "recovery"]}
            ],
            "principals": {
                "forgejo": {"inventory_hosts": "manager", "future_account": "podman-forgejo"},
                "infisical": {"inventory_hosts": "manager"},
                "qui-alpha": {"inventory_hosts": "worker"},
                "qui-bravo": {"inventory_hosts": "plex"},
            },
        },
        "existing": {},
        "names": {"infisical": "infisical-infisical-1"},
    }
    return old_reports, reports, context


def test_candidates_reuse_only_validated_provider_removal_and_preserve_provenance():
    retained, fresh, context = provider_transition_fixture()
    original = deepcopy(retained)
    source = {"path": "/fixture/retained.json", "sha256": "a" * 64}
    with pytest.raises(ValueError, match="capture host identity differs"):
        PREFLIGHT.merge_capture(deepcopy(fresh), retained, source)
    result = PREFLIGHT.candidates(
        {
            **context,
            "capture_reports": retained,
            "capture_source": source,
            "collection": [{"haproxy_preflight_host": r["host"], "stdout": json.dumps(r)} for r in fresh],
        }
    )
    assert retained == original
    report = result["reports"][0]
    transition = report["capture_history"][-1]["provider_removal"]
    assert transition == {
        "provider": "service-haproxy",
        "removed_container": "provider-manager",
        "removed_veths": ["veth-provider"],
        "removed_link_local": ["fe80::1234"],
    }
    assert report["addresses"] == fresh[0]["addresses"]
    assert report["containers"][0]["destinations"][0]["observations"][0] == {"capture": retained[0]["capture"], "source": source}
    assert result["reports"][1]["containers"][0]["destinations"][0]["routes"][0]["worker_only"] is True
    assert result["candidate"]["mgt_firewall_inputs_verified"] is False
    assert result["candidate"]["mgt_firewall_callers"]["qui-alpha"][0]["route_verified"] is False


@pytest.mark.parametrize(
    "change",
    [
        "global_loss",
        "added_address",
        "boot",
        "hostname",
        "missing_inventory",
        "worker_address",
        "caller_pid",
        "caller_ns",
        "caller_bridge",
        "caller_replaced",
        "missing_caller",
        "incomplete",
        "provider_running",
        "provider_veth",
        "missing_interfaces",
        "provider_vip",
        "mgt_task",
        "worker_provider_replaced",
        "worker_task_replaced",
        "duplicate_boot",
        "wrong_host",
        "account_uid",
        "extra_caller",
    ],
)
def test_provider_removal_transition_retains_independent_identity_and_placement_guards(change):
    retained, fresh, context = provider_transition_fixture()
    if change == "global_loss":
        retained[0]["addresses"].append("192.0.2.99")
    elif change == "added_address":
        fresh[0]["addresses"].append("fe80::9999")
    elif change == "boot":
        fresh[0]["identity"]["boot_id"] = "new-boot"
    elif change == "hostname":
        fresh[0]["identity"]["hostname"] = "wrong-host"
    elif change == "missing_inventory":
        fresh[0]["addresses"] = []
    elif change == "worker_address":
        retained[1]["addresses"].append("fe80::4321")
    elif change == "caller_pid":
        fresh[0]["containers"][0]["pid"] += 1
    elif change == "caller_ns":
        fresh[0]["containers"][0]["netns"] = "replaced-namespace"
    elif change == "caller_bridge":
        fresh[0]["containers"][0]["identities"][0]["veth"] = "replaced-veth"
    elif change == "caller_replaced":
        fresh[0]["containers"][0]["id"] = "replacement"
    elif change == "missing_caller":
        fresh[0]["containers"] = []
    elif change == "incomplete":
        retained[1]["capture"]["complete"] = False
    elif change == "provider_running":
        fresh[0]["containers"].append(deepcopy(retained[0]["containers"][-1]))
    elif change == "provider_veth":
        fresh[0]["interface_names"].append("veth-provider")
    elif change == "missing_interfaces":
        fresh[0].pop("interface_names")
    elif change == "provider_vip":
        fresh[0]["topology"]["services"][0]["vips"][0]["Addr"] = "172.98.0.145/24"
    elif change == "mgt_task":
        fresh[0]["topology"]["services"][0]["tasks"].append(deepcopy(retained[0]["topology"]["services"][0]["tasks"][-1]))
    elif change == "worker_provider_replaced":
        fresh[1]["containers"][-1]["pid"] += 1
    elif change == "worker_task_replaced":
        fresh[0]["topology"]["services"][0]["tasks"][0]["id"] = "replacement-task"
    elif change == "duplicate_boot":
        fresh[1]["identity"]["boot_id"] = retained[1]["identity"]["boot_id"] = fresh[0]["identity"]["boot_id"]
    elif change == "wrong_host":
        fresh[0]["host"] = "wrong-host"
    elif change == "account_uid":
        fresh[0]["accounts"]["podman-forgejo"]["uid"] = 1005
    elif change == "extra_caller":
        fresh[1]["containers"].append(deepcopy(fresh[0]["containers"][0]))
    # Idle callers receive the same strict identity checks as those with destinations.
    retained[0]["containers"][0]["destinations"] = []
    before = deepcopy(retained)
    with pytest.raises(ValueError):
        PREFLIGHT.merge_capture(fresh, retained, transition_context=context)
    assert retained == before
