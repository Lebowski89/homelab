"""Focused denial evidence tests; no production commands or sockets are used."""

from __future__ import annotations

import importlib.util
import json
import shlex
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("negative_cutover_test", ROOT / "ansible/operator/haproxy-cutover.py")
HELPER = importlib.util.module_from_spec(spec)
spec.loader.exec_module(HELPER)


@pytest.fixture(autouse=True)
def isolate_managed_writer_lock(tmp_path, monkeypatch):
    root = tmp_path / "managed-run"
    root.mkdir()
    monkeypatch.setattr(HELPER.FW.OWNED, "RUN", root)


@pytest.mark.parametrize("family,local", [(4, False), (6, False), (4, True), (6, True)])
@pytest.mark.parametrize("failure", ["", "refused", "unreachable", "connected", "no-drop", "no-observation", "expiry", "changed-source"])
def test_denial_requires_active_listener_timeout_and_exact_drop_cleanup(family, local, failure):
    source, destination = ("192.0.2.20", "192.0.2.48") if family == 4 else ("fd00::20", "fd00::48")
    plan = {"source": [source, 41001], "destination": [destination, 5432], "family": family, "route": {"dev": "fixture"}}
    chain = "SKY-MGT-OUT" if local else "SKY-MGT-PRE"
    drop = ["-p", "tcp", "-m", "addrtype", "--dst-type", "LOCAL", "--dport", "5432", "-j", "DROP"]
    installed, commands = [], []
    started = False
    checks = 0

    def execute(argv):
        commands.append(argv)
        if argv[0].endswith("-save"):
            count = 10 if not started or failure == "no-drop" else 12
            observation = ""
            if installed:
                packets = 0 if failure == "no-observation" else 2
                observation = f"[{packets}:120] -A {chain} " + shlex.join(installed[0]) + "\n"
            return observation + f"[{count}:600] -A {chain} " + shlex.join(drop) + "\n"
        if "-I" in argv:
            assert argv[argv.index("-I") + 2] == "1"
            installed.append(argv[argv.index("-I") + 3 :])
        elif "-D" in argv:
            assert argv[argv.index("-D") + 2 :] == installed.pop()
        else:
            pytest.fail("unexpected command: " + str(argv))
        return ""

    def active():
        nonlocal checks
        checks += 1
        if failure == "expiry" and checks == 2:
            raise ValueError("fixture listener expired")

    def probe():
        nonlocal started
        # The real reconciler replaces unexpected observation rules. A rival
        # writer must be excluded until this probe's exact cleanup completes.
        import fcntl

        with (HELPER.FW.OWNED.RUN / "writer.lock").open("a") as rival:
            try:
                fcntl.flock(rival, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                installed.clear()
        started = True
        status = {"refused": "error:111:Connection refused", "unreachable": "error:101:Network unreachable", "connected": "connected"}.get(
            failure, "timeout"
        )
        return {"result": status, "source": [source, 41002 if failure == "changed-source" else 41001], "destination": [destination, 5432]}

    if failure:
        with pytest.raises(ValueError):
            HELPER.negative_observe(plan, local, probe, active, execute)
    else:
        result = HELPER.negative_observe(plan, local, probe, active, execute)
        assert result["drop_increase"] == 2 and result["observation_packets"] == [2]
    assert installed == []
    mutations = [c for c in commands if "-I" in c or "-D" in c]
    assert len(mutations) == 2
    assert not any("-j" in c or "-F" in c or "-X" in c for c in mutations)
    assert mutations[0][0] == ("ip6tables" if family == 6 else "iptables")
    # Both normal and rejected observations release the shared lock.
    import fcntl

    with (HELPER.FW.OWNED.RUN / "writer.lock").open("a") as rival:
        fcntl.flock(rival, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_route_error_identifies_exact_command_and_stderr(monkeypatch, capsys):
    command = ["ip", "-j", "-6", "route", "get", "fd00::48", "oif", "tailscale0"]
    monkeypatch.setattr(
        HELPER.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=2, stdout="", stderr="RTNETLINK answers: Invalid argument\n")
    )
    with pytest.raises(RuntimeError, match="route get fd00::48 oif tailscale0: RTNETLINK"):
        HELPER.negative_command(command)
    record = json.loads(capsys.readouterr().out)
    assert record == {"operation": command, "status": 2, "stderr": "RTNETLINK answers: Invalid argument"}


@pytest.mark.parametrize(
    "route", [[], [{"dev": "fixture", "type": "unreachable"}], [{"dev": "wrong", "prefsrc": "192.0.2.20"}], [{"dev": "fixture"}]]
)
def test_missing_or_wrong_routes_fail_before_opening_socket(monkeypatch, route):
    monkeypatch.setattr(HELPER.socket, "socket", lambda *a, **k: pytest.fail("must not open a socket on an invalid route"))
    with pytest.raises(ValueError):
        HELPER.negative_socket("192.0.2.48", 5432, "fixture", execute=lambda argv: json.dumps(route))


@pytest.mark.parametrize("family,local", [(4, False), (6, False), (4, True), (6, True)])
def test_only_exact_owned_local_drop_is_selected(family, local):
    chain = "SKY-MGT-OUT" if local else "SKY-MGT-PRE"
    tool = "iptables" if family == 4 else "ip6tables"
    table = f"[0:0] -A {chain} -p tcp --dport 5432 -j DROP\n"
    with pytest.raises(ValueError, match="one exact owned DROP"):
        HELPER.negative_drop(tool, chain, 5432, execute=lambda argv: table)


@pytest.mark.parametrize("failure", ["", "ipv6-missing", "wrong-pid", "expired", "extended-limit"])
def test_listener_checks_both_families_exact_pid_and_original_runtime(monkeypatch, failure):
    batch = Path("/fixture/private-batch")
    unit = "skynet-haproxy-acceptance-fixture.service"
    command = ["/usr/bin/python3", str(batch / "haproxy-cutover.py"), "listen", "5432", "18405"]
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda path: (
            b"\0".join(x.encode() for x in command) + b"\0" if str(path) == "/proc/999999/cmdline" else pytest.fail("unapproved read")
        ),
    )
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda path: (
            "0::/skynet_pg_recovery.slice/" + unit + "\n" if str(path) == "/proc/999999/cgroup" else pytest.fail("unapproved read")
        ),
    )

    def execute(argv):
        if argv[0] == "systemctl":
            state = "inactive" if failure == "expired" else "active"
            runtime = "10min" if failure == "extended-limit" else "4min"
            return f"ActiveState={state}\nMainPID=999999\nRuntimeMaxUSec={runtime}\nSlice=skynet_pg_recovery.slice\nUser=root\n"
        assert argv[0] == "ss"
        if failure == "ipv6-missing" and "-6" in argv:
            return ""
        owner = "999998" if failure == "wrong-pid" else "999999"
        address = "0.0.0.0" if "-4" in argv else "*"
        return "\n".join(f'LISTEN 0 32 {address}:{p} *:* users:(("python3",pid={owner},fd=3))' for p in [5432, 18405])

    if failure:
        with pytest.raises(ValueError):
            HELPER.negative_listener(batch, unit, execute)
    else:
        assert HELPER.negative_listener(batch, unit, execute)["MainPID"] == "999999"


@pytest.mark.parametrize(
    "failure",
    [
        "",
        "link-local",
        "no-lan6",
        "occupied",
        "wrong-peer",
        "peer-route-error",
        "unit-present",
        "root-in-authorized-slice",
        "ssh-key",
        "tailscale-ambiguous",
        "tailscale-route-source",
        "tailscale-source-changed",
        "actual-service",
        "actual-replaced",
    ],
)
def test_actual_negative_operation_preserves_state_and_uses_recorded_unit(tmp_path, monkeypatch, capsys, failure):
    """Execute the orchestrator on public fixtures; all OS/network calls are denied or replaced."""
    import inspect
    import io
    import select
    from copy import deepcopy

    sources = {
        name: inspect.getsource(getattr(HELPER, name))
        for name in ["negative_command", "negative_socket", "negative_connect", "negative_peer"]
    }
    batch = tmp_path / "prepared"
    batch.mkdir()
    unit = "skynet-haproxy-acceptance-fixture.service"
    binding = {"kind": "local", "phase": "podman", "account": "podman-fixture", "uid": 1004, "verified": True, "restart_verified": True}
    policy = {
        "schema": 1,
        "backend": "nf_tables",
        "inventory_host": "manager",
        "inventory_address": "192.0.2.48",
        "inputs_verified": True,
        "endpoints": [{"port": 5432, "callers": ["database"]}, {"port": 18405, "callers": ["metrics"]}],
        "callers": {"database": [binding], "metrics": [binding]},
        "principals": {},
    }
    HELPER.FW.validate_policy(policy, require_verified=True)
    stage = {"controller": "manager", "workers": ["storage", "media"], "policy": policy}
    inputs = {"mgt_firewall_callers": policy["callers"], "mgt_firewall_inputs_verified": True}
    host_identity = {"hostname": "manager", "boot_id": "fixture-manager-boot"}
    peer_identity = {"hostname": "storage", "boot_id": "fixture-storage-boot"}
    reports = [
        {"host": "manager", "identity": host_identity, "inventory_address": "192.0.2.48"},
        {"host": "storage", "identity": peer_identity, "inventory_address": "192.0.2.20"},
    ]
    peer = {
        "inventory_host": "storage",
        "inventory_address": "192.0.2.20",
        "ansible_host": "192.0.2.20",
        "ansible_user": "fixture",
        "ansible_port": 22,
        "operator": {"uid": 1234, "account": "fixture-operator", "home": str(tmp_path / "operator-home"), "ssh_auth_sock": None},
    }
    monkeypatch.setenv("SUDO_UID", "1234")
    monkeypatch.setattr(
        HELPER.pwd, "getpwuid", lambda uid: SimpleNamespace(pw_uid=1234, pw_name="fixture-operator", pw_dir=str(tmp_path / "operator-home"))
    )
    for name, value in [
        ("working-policy.json", inputs),
        ("stage.json", stage),
        ("peer.json", peer),
        ("deployment-inputs.json", {"services_mgt_backend_acl_ready": False}),
    ]:
        (batch / name).write_text(json.dumps(value))
    (batch / "rollback-state.sh").write_text(
        f'declare -- policy_started="true"\ndeclare -- deployment_started="false"\ndeclare -- probe_unit="{unit}"\n'
    )
    actual = failure.startswith("actual-")
    if actual:
        (batch / "rollback-state.sh").write_text(
            'declare -- exclusion_started="true"\ndeclare -- policy_started="true"\n'
            'declare -- deployment_started="true"\ndeclare -- probe_unit=""\n'
        )
        monkeypatch.setattr(HELPER, "deployment", lambda *args: None)
    metadata = batch / "worker-offline-20261009T200449Z-2609904/worker-only.json.metadata.json"
    metadata.parent.mkdir()
    metadata.write_text(json.dumps(reports))
    saved = {path: path.read_bytes() for path in batch.rglob("*") if path.is_file()}
    read, path_read = HELPER.read, Path.read_text
    monkeypatch.setattr(
        HELPER, "read", lambda path: deepcopy(policy) if str(path) == "/etc/skynet-mgt-firewall/policy.json" else read(path)
    )
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda path, *a, **k: (
            (
                "0::/skynet_pg_prepare.slice/fixture.service\n"
                if failure == "root-in-authorized-slice"
                else "0::/user.slice/fixture.service\n"
            )
            if str(path) == "/proc/self/cgroup"
            else path_read(path, *a, **k)
        ),
    )
    monkeypatch.setattr(HELPER.os, "getuid", lambda: 0)
    monkeypatch.setattr(HELPER.os, "geteuid", lambda: 0)
    monkeypatch.setattr(HELPER.PREFLIGHT, "observed_identity", lambda: host_identity)
    monkeypatch.setattr(HELPER, "load", lambda *a: SimpleNamespace(socket_uid=lambda stream: 0))
    monkeypatch.setattr(HELPER.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(select, "select", lambda readers, *a: (readers, [], []))
    links = [
        {"ifname": "fixture-lan", "addr_info": [{"local": a} for a in ["192.0.2.48", "192.0.2.53", "fd00::48"]]},
        {
            "ifname": "tailscale0",
            "addr_info": [
                {"local": "100.64.0.48", "scope": "global", "family": "inet"},
                {"local": "fd01::48", "scope": "global", "family": "inet6"},
            ],
        },
    ]
    if failure == "no-lan6":
        links[0]["addr_info"].pop()
    if failure == "link-local":
        links[1]["addr_info"].append({"local": "fe80::48", "scope": "link", "family": "inet6"})
    if failure == "tailscale-ambiguous":
        links[1]["addr_info"].append({"local": "fd01::99", "scope": "global", "family": "inet6"})
    commands, observations = [], []
    monkeypatch.setattr(HELPER, "negative_listener", lambda *a: {"ActiveState": "active"})
    service_checks = []

    def actual_listener(*args):
        service_checks.append(True)
        return {"container": "changed" if failure == "actual-replaced" and len(service_checks) > 1 else "fixture"}

    monkeypatch.setattr(HELPER, "service_listener", actual_listener)

    def execute(argv):
        commands.append(argv)
        if argv[:2] == ["/usr/bin/python3", "/etc/skynet-mgt-firewall/policy.py"]:
            return json.dumps({"compliant": True, "families": [4, 6], "pending": []})
        if argv[0] == "ip":
            return json.dumps(links)
        if argv[0] == "ss":
            return "fixture occupied listener" if failure == "occupied" else ""
        if argv[0] == "systemctl":
            return "loaded" if failure == "unit-present" else "not-found"
        if argv[0] == "systemd-run":
            return ""
        pytest.fail("unapproved OS command: " + repr(argv))

    monkeypatch.setattr(HELPER, "run", execute)
    monkeypatch.setattr(HELPER, "negative_command", execute)

    def remote(argv, **kwargs):
        assert argv[:4] == ["runuser", "-u", "fixture-operator", "--"]
        assert "StrictHostKeyChecking=yes" in argv
        if failure == "ssh-key":
            return SimpleNamespace(returncode=255, stdout="", stderr="No ED25519 host key is known; Host key verification failed.")
        arguments = shlex.split(argv[-1])
        if len(arguments) == 3:
            observed = {"hostname": "other", "boot_id": "other-boot"} if failure == "wrong-peer" else peer_identity
            return SimpleNamespace(
                returncode=0,
                stderr="",
                stdout=json.dumps(
                    {
                        "identity": observed,
                        "links": [
                            {"ifname": "fixture-lan", "addr_info": [{"local": "192.0.2.20"}]},
                            {
                                "ifname": "tailscale0",
                                "addr_info": [
                                    {"local": "100.64.0.20", "scope": "global", "family": "inet"},
                                    {"local": "fd01::20", "scope": "global", "family": "inet6"},
                                    {"local": "fe80::20", "scope": "link", "family": "inet6"},
                                ],
                            },
                        ],
                    }
                ),
            )
        route = arguments[3:]
        if failure == "peer-route-error":
            return SimpleNamespace(returncode=2, stderr="RTNETLINK answers: Invalid argument", stdout="")
        source = (
            ("fd01::20" if "-6" in route else "100.64.0.20")
            if route[-1] == "tailscale0"
            else ("fd00::20" if "-6" in route else "192.0.2.20")
        )
        if failure == "tailscale-route-source" and route[-1] == "tailscale0":
            source = "fe80::20" if "-6" in route else "192.0.2.20"
        return SimpleNamespace(returncode=0, stderr="", stdout=json.dumps([{"dev": route[-1], "prefsrc": source}]))

    monkeypatch.setattr(HELPER.subprocess, "run", remote)

    class Socket:
        def close(self):
            pass

    def socket(destination, port, interface="", **kwargs):
        source = ("fd01::20" if ":" in destination else "100.64.0.20") if interface == "tailscale0" else "192.0.2.20"
        if failure == "tailscale-source-changed":
            source = "192.0.2.20"
        return Socket(), {
            "family": HELPER.ipaddress.ip_address(destination).version,
            "source": [source, 41000],
            "destination": [destination, port],
            "route": {"dev": interface},
            "scope": 0,
        }

    monkeypatch.setattr(HELPER, "negative_socket", socket)
    monkeypatch.setattr(
        HELPER, "negative_connect", lambda stream, plan: {"result": "timeout", "source": plan["source"], "destination": plan["destination"]}
    )

    class Child:
        def __init__(self, argv, **kwargs):
            assert argv[:4] == ["runuser", "-u", "fixture-operator", "--"]
            assert "StrictHostKeyChecking=yes" in argv
            arguments = shlex.split(argv[-1])
            compile(arguments[3], "<actual-peer-program>", "exec")
            self.plan = socket(arguments[4], int(arguments[5]), arguments[6])[1]
            self.plan["host_identity"] = peer_identity
            self.stdout, self.stderr = io.StringIO(json.dumps({"ready": self.plan}) + "\n"), io.StringIO()
            self.returncode = None

        def communicate(self, message, **kwargs):
            assert message == "PROBE\n"
            self.returncode = 0
            return json.dumps({"result": "timeout", "source": self.plan["source"], "destination": self.plan["destination"]}), ""

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -9

        def wait(self, **kwargs):
            return self.returncode

    monkeypatch.setattr(HELPER.subprocess, "Popen", Child)
    aliases = {"execute": "negative_command", "socket": "negative_socket", "<lambda>": "negative_connect"}
    monkeypatch.setattr(inspect, "getsource", lambda function: sources[aliases.get(function.__name__, function.__name__)])

    def observe(plan, local, probe, active):
        result = probe()
        assert result["result"] == "timeout"
        observations.append((local, plan["destination"]))
        if local:
            assert result["socket_uid"] == result["process_uid"] == 0

    monkeypatch.setattr(HELPER, "negative_observe", observe)
    if failure not in {"", "link-local", "no-lan6", "actual-service"}:
        with pytest.raises(ValueError):
            HELPER.negative(str(batch), str(batch / "peer.json"), actual=actual)
        assert any(c[0] == "systemd-run" for c in commands) == (failure == "tailscale-source-changed")
        if failure != "tailscale-source-changed":
            assert observations == []
    else:
        HELPER.negative(str(batch), str(batch / "peer.json"), actual=actual)
        starts = [c for c in commands if c[0] == "systemd-run"]
        if actual:
            assert starts == [] and len(service_checks) > 24
            assert not any(c[0] in {"ss", "systemctl"} for c in commands)
        else:
            assert len(starts) == 1
            assert "--unit=" + unit in starts[0] and "--property=RuntimeMaxSec=240" in starts[0]
            assert starts[0][-5:] == ["/usr/bin/python3", str(batch / "haproxy-cutover.py"), "listen", "5432", "18405"]
        assert len(observations) == (20 if failure == "no-lan6" else 24) and {p for _, (_, p) in observations} == {5432, 18405}
        assert not any(address.startswith("fe80:") for _, (address, _) in observations)
        assert '"negative_acceptance": "passed"' in capsys.readouterr().out
    assert all(path.read_bytes() == content for path, content in saved.items())
    assert not any(c[0] in ["docker", "podman"] or "stop" in c or "restart" in c for c in commands)


@pytest.mark.integration
@pytest.mark.parametrize("stage,status", [("sudo", 42), ("inventory", 75), ("acceptance", 66), ("success", 0)])
@pytest.mark.parametrize("config_choice", ["default", "override"])
@pytest.mark.parametrize("actual", [False, True])
def test_logged_shell_wrapper_preserves_early_failure_and_status(tmp_path, stage, status, config_choice, actual):
    import os
    import subprocess

    batch = tmp_path / "private-batch"
    batch.mkdir(mode=0o700)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    sudo = bindir / "sudo"
    sudo.write_text("""#!/bin/bash
set -eu
if [[ "$1" = -v ]]; then
  echo 'fixture interactive authentication prompt'
  if [[ "$FIXTURE_STAGE" = sudo ]]; then exit 42; fi
  exit 0
fi
test "$1" = -n
shift
exec "$@"
""")
    producer = venv / "bin/python"
    producer.write_text("""#!/bin/bash
set -eu
printf 'fixture ansible config: %s\\n' "$ANSIBLE_CONFIG"
if [[ "$1" = - ]]; then
  cat >/dev/null
  if [[ "$FIXTURE_STAGE" = inventory ]]; then echo 'fixture inventory failure' >&2; exit 75; fi
  printf '{}\\n' >"$3"
  exit 0
fi
if [[ "$2" == accept-native ]]; then
  test "$FIXTURE_MODE" == negative-service
  echo 'fixture native actual-service probes passed'
  exit 0
fi
test "$2" = "$FIXTURE_MODE"
if [[ "$FIXTURE_STAGE" = acceptance ]]; then echo 'fixture denied-evidence failure' >&2; exit 66; fi
echo 'fixture negative acceptance passed'
""")
    sudo.chmod(0o755)
    producer.chmod(0o755)
    environment = {
        "PATH": str(bindir) + ":/usr/bin:/bin",
        "VIRTUAL_ENV": str(venv),
        "PLAYBOOK": str(tmp_path / "repo/ansible/playbook.yml"),
        "FIXTURE_STAGE": stage,
        "HOME": str(tmp_path),
        "FIXTURE_MODE": "negative-service" if actual else "negative",
    }
    expected_config = tmp_path / "repo/ansible/ansible.cfg"
    if config_choice == "override":
        expected_config = tmp_path / "explicit-config.cfg"
        environment["ANSIBLE_CONFIG"] = str(expected_config)
    result = subprocess.run(
        ["/bin/bash", str(ROOT / "ansible/operator/haproxy-negative-acceptance.sh"), *(["--actual"] if actual else []), str(batch)],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == status, result.stdout + result.stderr
    logs = list(batch.glob("negative-*/operator.log"))
    assert len(logs) == 1 and logs[0].stat().st_mode & 0o777 == 0o600
    assert logs[0].parent.stat().st_mode & 0o777 == 0o700
    text = logs[0].read_text()
    assert "fixture interactive authentication prompt" in text and "fixture interactive authentication prompt" in result.stdout
    assert f"Negative acceptance exited with status {status}" in text
    if stage != "sudo":
        assert f"fixture ansible config: {expected_config}" in text
    assert result.stdout.index("Private log:") < result.stdout.index("fixture interactive authentication prompt")
    assert os.path.commonpath([logs[0], tmp_path]) == str(tmp_path)


@pytest.mark.integration
@pytest.mark.parametrize("initialize,success", [(False, False), (True, True)])
def test_actual_embedded_inventory_projection_initializes_collection_loader(tmp_path, initialize, success):
    """Real Ansible parsing of a local NetBox-shaped plugin; outbound calls forbidden."""
    import os
    import pwd
    import subprocess
    import sys

    repo = tmp_path / "repo"
    (repo / "ansible").mkdir(parents=True)
    collection = tmp_path / "collections/ansible_collections/netbox/netbox/plugins/inventory"
    collection.mkdir(parents=True)
    (collection / "nb_inventory.py").write_text('''from ansible.plugins.inventory import BaseInventoryPlugin
DOCUMENTATION = r"""
name: nb_inventory
plugin_type: inventory
short_description: Offline deterministic NetBox-shaped regression fixture
description: Supplies only public fixture inventory without any API.
options:
  plugin:
    description: Exact collection inventory plugin name.
    required: true
    choices: [netbox.netbox.nb_inventory]
"""
class InventoryModule(BaseInventoryPlugin):
    NAME = 'netbox.netbox.nb_inventory'
    def verify_file(self,path):
        return super().verify_file(path) and path.endswith('.yml')
    def parse(self,inventory,loader,path,cache=True):
        super().parse(inventory,loader,path,cache)
        self._read_config_data(path)
        inventory.add_host('plex')
        for name,value in {'local_ip':'192.0.2.59','ansible_host':'100.64.0.59','ansible_user':'fixture','ansible_port':2222,
                           'must_not_project':'FAKE-PRIVATE-FIELD'}.items():
            inventory.set_variable('plex',name,value)
''')
    config = repo / "ansible/ansible.cfg"
    config.write_text(f"[defaults]\ncollections_path = {tmp_path}/collections\n")
    (repo / "ansible/netbox.yml").write_text("---\nplugin: netbox.netbox.nb_inventory\n")
    output = tmp_path / "peer.json"
    source = (ROOT / "ansible/operator/haproxy-negative-acceptance.sh").read_text().split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
    if not initialize:
        source = source.replace("init_plugin_loader()\n", "")
    prohibit_network = """import socket,ipaddress
def prohibited(*a,**k): raise AssertionError('network forbidden in local inventory regression')
numeric_getaddrinfo=socket.getaddrinfo
def local_numeric(host,*a,**k):
    ipaddress.ip_address(host)
    return numeric_getaddrinfo(host,*a,**k)
socket.socket.connect=prohibited
socket.create_connection=prohibited
socket.getaddrinfo=local_numeric
socket.gethostbyname=prohibited
socket.gethostbyaddr=prohibited
"""
    environment = {**os.environ, "ANSIBLE_CONFIG": str(config), "HOME": str(tmp_path)}
    environment.pop("ANSIBLE_COLLECTIONS_PATH", None)
    environment.pop("ANSIBLE_COLLECTIONS_PATHS", None)
    environment.pop("SSH_AUTH_SOCK", None)
    # Ansible fixture parsing may run under root in CI; project a public
    # non-root operator fixture without changing actual subprocess credentials.
    if os.getuid() == 0:
        source = source.replace(
            "operator=pwd.getpwuid(os.getuid())",
            "from types import SimpleNamespace\noperator=SimpleNamespace(pw_uid=1234,pw_name='fixture-operator',pw_dir='/fixture/operator')",
        )
        operator_identity = {"uid": 1234, "account": "fixture-operator", "home": "/fixture/operator", "ssh_auth_sock": None}
    else:
        account = pwd.getpwuid(os.getuid())
        operator_identity = {"uid": account.pw_uid, "account": account.pw_name, "home": account.pw_dir, "ssh_auth_sock": None}
    result = subprocess.run(
        [sys.executable, "-c", prohibit_network + source, str(repo), str(output)],
        env=environment,
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert (result.returncode == 0) is success, result.stdout + result.stderr
    assert "FAKE-PRIVATE-FIELD" not in result.stdout + result.stderr
    if success:
        assert json.loads(output.read_text()) == {
            "inventory_host": "plex",
            "inventory_address": "192.0.2.59",
            "ansible_host": "100.64.0.59",
            "ansible_user": "fixture",
            "ansible_port": 2222,
            "operator": operator_identity,
        }
        assert "unknown plugin" not in result.stderr
        assert output.stat().st_mode & 0o777 == 0o600
    else:
        assert "unknown plugin 'netbox.netbox.nb_inventory'" in result.stderr
        assert "Plex inventory peer is missing" in result.stderr
        assert not output.exists()


@pytest.mark.parametrize("invalid", ["", "root", "uid", "account", "home", "agent"])
def test_peer_ssh_retains_original_operator_context_and_strict_trust(tmp_path, monkeypatch, invalid):
    peer = {
        "ansible_user": "fixture-peer",
        "ansible_host": "192.0.2.59",
        "ansible_port": 2222,
        "operator": {
            "uid": 1234,
            "account": "fixture-operator",
            "home": str(tmp_path / "operator-home"),
            "ssh_auth_sock": str(tmp_path / "fixture-agent.sock"),
        },
    }
    monkeypatch.setenv("SUDO_UID", "1234")
    monkeypatch.setattr(
        HELPER.pwd, "getpwuid", lambda uid: SimpleNamespace(pw_uid=1234, pw_name="fixture-operator", pw_dir=str(tmp_path / "operator-home"))
    )
    if invalid == "root":
        monkeypatch.setenv("SUDO_UID", "0")
    if invalid == "uid":
        peer["operator"]["uid"] = 0
    if invalid == "account":
        peer["operator"]["account"] = "root"
    if invalid == "home":
        peer["operator"]["home"] = "/root"
    if invalid == "agent":
        peer["operator"]["ssh_auth_sock"] = "relative.sock"
    if invalid:
        with pytest.raises(ValueError):
            HELPER.negative_peer_ssh(peer)
        return
    command = HELPER.negative_peer_ssh(peer)
    assert command[:4] == ["runuser", "-u", "fixture-operator", "--"]
    assert "HOME=" + str(tmp_path / "operator-home") in command
    assert "SSH_AUTH_SOCK=" + str(tmp_path / "fixture-agent.sock") in command
    assert command[command.index("/bin/sh") : command.index("ssh")] == [
        "/bin/sh",
        "-c",
        'cd "$HOME" || exit; exec "$@"',
        "skynet-haproxy-peer",
    ]
    assert "StrictHostKeyChecking=yes" in command
    assert "BatchMode=yes" in command and command[-3:] == ["-p", "2222", "fixture-peer@192.0.2.59"]


@pytest.mark.integration
def test_real_openssh_resolves_fixture_operator_trust_without_connecting(tmp_path, monkeypatch):
    import shutil
    import subprocess

    ssh = shutil.which("ssh")
    if not ssh:
        pytest.skip("OpenSSH client unavailable for offline configuration test")
    operator_home = tmp_path / "operator-home"
    operator_home.mkdir(mode=0o700)
    peer = {
        "ansible_user": "fixture-peer",
        "ansible_host": "192.0.2.59",
        "ansible_port": 2222,
        "operator": {"uid": 1234, "account": "fixture-operator", "home": str(operator_home), "ssh_auth_sock": None},
    }
    monkeypatch.setenv("SUDO_UID", "1234")
    monkeypatch.setattr(
        HELPER.pwd, "getpwuid", lambda uid: SimpleNamespace(pw_uid=1234, pw_name="fixture-operator", pw_dir=str(operator_home))
    )
    command = HELPER.negative_peer_ssh(peer)
    ssh_arguments = command[command.index("ssh") + 1 :]
    results = []
    for name in ["root", "operator"]:
        config = tmp_path / (name + ".ssh-config")
        known_hosts = tmp_path / (name + ".known-hosts")
        known_hosts.write_text("# PUBLIC OFFLINE FIXTURE ONLY\n")
        config.write_text(f"Host *\n  UserKnownHostsFile {known_hosts}\n")
        # -G exits after client configuration resolution; no handshake, remote
        # command, host-key enrollment or network connection takes place.
        result = subprocess.run([ssh, "-G", "-F", str(config), *ssh_arguments], text=True, capture_output=True, check=False, timeout=10)
        assert result.returncode == 0, result.stderr
        values = {line.split(" ", 1)[0]: line.split(" ", 1)[1] for line in result.stdout.splitlines() if " " in line}
        assert values["stricthostkeychecking"] == "true"
        assert values["updatehostkeys"] == "false"
        assert values["userknownhostsfile"] == str(known_hosts)
        assert values["user"] == "fixture-peer" and values["port"] == "2222"
        results.append(values["userknownhostsfile"])
    assert results[0] != results[1]


@pytest.mark.integration
def test_actual_container_inspection_renders_go_fields_not_json_keys(tmp_path, monkeypatch, go_cache):
    import os
    import shutil
    import subprocess

    go = shutil.which("go")
    if not go:
        pytest.skip("Go unavailable for actual Podman inspection template regression")
    source = tmp_path / "projection.go"
    # Minimal projections of Podman's InspectContainerData/State/NetworkSettings
    # and InspectHostPort: Go field names deliberately differ from JSON tags.
    source.write_text("""package main
import ("encoding/json"; "fmt"; "os"; "text/template")
type State struct { Pid int; Running bool }
type HostPort struct { HostIP string `json:"HostIp"`; HostPort string }
type Network struct { Ports map[string][]HostPort }
type Container struct {
    ID string `json:"Id"`
    State *State
    Image string
    NetworkSettings *Network
}
func main() {
    var container Container
    if err := json.NewDecoder(os.Stdin).Decode(&container); err != nil { panic(err) }
    funcs := template.FuncMap{"json": func(v any) (string,error) { b,e := json.Marshal(v); return string(b),e }}
    projection,err := template.New("inspect").Funcs(funcs).Parse(os.Args[1])
    if err == nil { err = projection.Execute(os.Stdout,container) }
    if err != nil { fmt.Fprintln(os.Stderr,err); os.Exit(1) }
}
""")
    environment = {
        **os.environ,
        "GOTOOLCHAIN": "local",
        "GOPROXY": "off",
        "GOSUMDB": "off",
        "GO111MODULE": "off",
        "GOCACHE": str(go_cache),
    }
    binary = tmp_path / "projection"
    built = subprocess.run([go, "build", "-o", str(binary), str(source)], env=environment, capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stderr
    ports = {"5432/tcp": [{"HostIp": "192.0.2.48", "HostPort": "5432"}], "80/tcp": None}
    raw = {"Id": "a" * 64, "State": {"Pid": 100, "Running": True}, "Image": "b" * 64, "NetworkSettings": {"Ports": ports}}
    monkeypatch.setattr(HELPER.pwd, "getpwnam", lambda name: SimpleNamespace(pw_uid=1011, pw_name=name, pw_dir="/fixture/home"))
    (tmp_path / "image-id").write_text(raw["Image"])
    (tmp_path / "stage.json").write_text(
        json.dumps({"definition": {"ports": {"postgres": {"host_ip": "192.0.2.48", "published": 5432, "target": 5432}}}})
    )

    def project(format_string):
        return subprocess.run([str(binary), format_string], input=json.dumps(raw), text=True, capture_output=True, check=False, timeout=10)

    def execute(argv):
        if "systemctl" in argv:
            return (
                "ActiveState=active\nControlGroup=/user.slice/user-1011.slice/user@1011.service/app.slice/haproxy.service\nInvocationID="
                + "d" * 32
                + "\n"
            )
        if "/usr/bin/podman" in argv:
            index = argv.index("/usr/bin/podman")
            assert argv[:index] == [
                "runuser",
                "-u",
                "podman-haproxy",
                "--",
                "env",
                "HOME=/fixture/home",
                "XDG_RUNTIME_DIR=/run/user/1011",
                "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1011/bus",
                "/bin/sh",
                "-c",
                'cd "$HOME" || exit; exec "$@"',
                "skynet-forgejo",
            ]
            assert argv[index : index + 5] == ["/usr/bin/podman", "--remote=false", "container", "inspect", "--format"]
            assert argv[-1] == "haproxy"
            format_string = argv[index + 5]
            broken = project(format_string.replace(".ID", ".Id"))
            assert broken.returncode != 0 and "can't evaluate field Id" in broken.stderr
            rendered = project(format_string)
            assert rendered.returncode == 0, rendered.stderr
            assert json.loads(rendered.stdout) == {"id": raw["Id"], "pid": 100, "running": True, "image": raw["Image"], "ports": ports}
            return rendered.stdout
        assert argv[0] == "ss"
        # Inspection and its strict image/publication guards passed. Do not
        # inspect any real sockets/processes in this projection-only regression.
        raise RuntimeError("fixture reached listener validation")

    with pytest.raises(RuntimeError, match="fixture reached listener validation"):
        HELPER.service_listener(tmp_path, execute)


@pytest.mark.parametrize(
    "failure",
    ["", "inactive", "wrong-image", "wrong-publication", "missing-listener", "other-uid", "other-cgroup", "unknown-socket", "extra-ipv6"],
)
def test_actual_service_listener_uses_declared_bindings_and_exclusive_account_unit(tmp_path, monkeypatch, failure):
    cgroup = "/user.slice/user-1011.slice/user@1011.service/app.slice/haproxy.service"
    ports = {
        "5432/tcp": [{"HostIp": "192.0.2.48", "HostPort": "5432"}],
        "8405/tcp": [{"HostIp": "192.0.2.48", "HostPort": "18405"}],
        "80/tcp": None,
    }
    record = {"id": "a" * 64, "pid": 100, "running": True, "image": "sha256:" + "b" * 64, "ports": ports}
    (tmp_path / "image-id").write_text("b" * 64)
    (tmp_path / "stage.json").write_text(
        json.dumps(
            {
                "definition": {
                    "ports": {
                        "postgres": {"host_ip": "192.0.2.48", "published": 5432, "target": 5432},
                        "metrics": {"host_ip": "192.0.2.48", "published": 18405, "target": 8405},
                    }
                }
            }
        )
    )
    if failure == "wrong-image":
        record["image"] = "c" * 64
    if failure == "wrong-publication":
        ports["5432/tcp"][0]["HostIp"] = "0.0.0.0"
    monkeypatch.setattr(HELPER.pwd, "getpwnam", lambda name: SimpleNamespace(pw_uid=1011, pw_name=name, pw_dir="/fixture/home"))
    monkeypatch.setattr(HELPER.PREFLIGHT, "process_identity", lambda *args: {"netns": "fixture", "start_time": "1"})
    original = Path.read_text

    def read(path, *args, **kwargs):
        if str(path) == "/proc/200/status":
            return "Uid:\t" + ("0 0" if failure == "other-uid" else "1011 1011") + " 1011 1011\n"
        if str(path) == "/proc/200/cgroup":
            return "0::" + ("/unrelated.service" if failure == "other-cgroup" else cgroup + "/runtime") + "\n"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    commands = []

    def execute(argv):
        commands.append(argv)
        if "systemctl" in argv:
            return (
                "ActiveState="
                + ("inactive" if failure == "inactive" else "active")
                + "\nControlGroup="
                + cgroup
                + "\nInvocationID="
                + "d" * 32
                + "\n"
            )
        if "/usr/bin/podman" in argv:
            assert "inspect" in argv and argv[-1] == "haproxy"
            return json.dumps(record)
        assert argv[0] == "ss"
        if "-6" in argv:
            return 'LISTEN 0 32 [::]:5432 [::]:* users:(("rootlessport",pid=200,fd=3))' if failure == "extra-ipv6" else ""
        selected = [5432] if failure == "missing-listener" else [5432, 18405]
        return "\n".join(
            f"LISTEN 0 32 192.0.2.48:{p} 0.0.0.0:* " + ("" if failure == "unknown-socket" else 'users:(("rootlessport",pid=200,fd=3))')
            for p in selected
        )

    if failure:
        with pytest.raises(ValueError):
            HELPER.service_listener(tmp_path, execute)
    else:
        observed = HELPER.service_listener(tmp_path, execute)
        assert observed["listener_families"] == [4]
        assert observed["listeners"] == [("192.0.2.48", "18405"), ("192.0.2.48", "5432")]
        assert {"-4", "-6"} <= {arg for command in commands for arg in command}
    assert not any("start" in command or "stop" in command or "restart" in command or "--pull" in command for command in commands)


@pytest.mark.parametrize("failure", ["", "denied", "replacement", "binding"])
def test_native_actual_acceptance_requires_context_counters_and_cleanup(tmp_path, monkeypatch, failure):
    values = {
        "mgt_firewall_callers": {
            name: [
                {
                    "kind": "local",
                    "phase": "native",
                    "account": "root",
                    "uid": 0,
                    "cgroup": path,
                    "verified": True,
                    "restart_verified": True,
                }
            ]
            for name, path in HELPER.SLICES.items()
        }
    }
    if failure == "binding":
        values["mgt_firewall_callers"]["controller"][0]["cgroup"] = "unrelated.slice"
    (tmp_path / "working-policy.json").write_text(json.dumps(values))
    (tmp_path / "stage.json").write_text(json.dumps({"policy": {"inventory_address": "192.0.2.48"}}))
    monkeypatch.setattr(HELPER, "actual_state", lambda *args: None)
    monkeypatch.setattr(HELPER, "continuation_policy", lambda *args: None)
    checks = []

    def active(*args):
        checks.append(True)
        return "changed" if failure == "replacement" and len(checks) > 1 else "fixture-actual-unit"

    monkeypatch.setattr(HELPER, "service_listener", active)
    installed = []

    def execute(argv):
        if argv[0].endswith("-save"):
            return "\n".join("[2:120] -A OUTPUT " + shlex.join(rule) for table, rule in installed if table == argv[-1])
        if "-I" in argv:
            installed.append((argv[argv.index("-t") + 1], argv[argv.index("-I") + 3 :]))
        elif "-D" in argv:
            installed.remove((argv[argv.index("-t") + 1], argv[argv.index("-D") + 2 :]))
        else:
            assert argv[:2] == ["/usr/bin/python3", "/usr/local/libexec/skynet-mgt-operator/mgt-operator.py"]
            assert argv[2] == "probe" and argv[-3:] == ["192.0.2.48", "5432", "0"]
            if failure == "denied":
                raise RuntimeError("fixture native caller denied")
            name = argv[3]
            return json.dumps(
                {"socket_uid": 0, "process_uid": 0, "cgroup": HELPER.SLICES[name] + "/child.service", "destination": ["192.0.2.48", 5432]}
            )
        return ""

    monkeypatch.setattr(HELPER, "run", execute)
    original_observe = HELPER.observe_rules

    def observe(rules, probe):
        assert {rule[1] for rule in rules} == {"mangle", "filter"}
        assert all("--path" in rule[3] and "--uid-owner" in rule[3] for rule in rules)
        return original_observe(rules, probe, execute)

    monkeypatch.setattr(HELPER, "observe_rules", observe)
    if failure:
        with pytest.raises((ValueError, RuntimeError)):
            HELPER.accept_native(tmp_path)
    else:
        HELPER.accept_native(tmp_path)
        assert len(checks) == 3
    assert installed == []


@pytest.mark.parametrize("failure", ["", "predeployment", "probe-present", "duplicate", "missing", "ack-false", "ack-string"])
def test_actual_acceptance_state_and_strict_deployment_gate(tmp_path, failure):
    state = (
        'declare -- exclusion_started="true"\ndeclare -- policy_started="true"\n'
        'declare -- deployment_started="true"\ndeclare -- probe_unit=""\n'
    )
    if failure == "predeployment":
        state = state.replace('deployment_started="true"', 'deployment_started="false"')
    if failure == "probe-present":
        state = state.replace('probe_unit=""', 'probe_unit="skynet-haproxy-acceptance-fixture.service"')
    if failure == "duplicate":
        state += 'declare -- deployment_started="true"\n'
    if failure == "missing":
        state = state.replace('declare -- exclusion_started="true"\n', "")
    (tmp_path / "rollback-state.sh").write_text(state)
    (tmp_path / "deployment-inputs.json").write_text(
        json.dumps(
            {
                "service_common_postgres_operator_context": True,
                "podman_services_pull_images": False,
                "services_mgt_backend_acl_ready": False if failure == "ack-false" else "true" if failure == "ack-string" else True,
                "services_rootless_data_ready": {"haproxy": True},
            }
        )
    )
    before = {p: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    if failure:
        with pytest.raises(ValueError):
            HELPER.actual_state(tmp_path)
    else:
        HELPER.actual_state(tmp_path)
    assert all(p.read_bytes() == data for p, data in before.items())


@pytest.mark.integration
@pytest.mark.parametrize("status", [0, 69])
def test_documented_activity_batch_runs_existing_capture_and_preserves_status(tmp_path, status):
    import os
    import re
    import subprocess

    batch = tmp_path / "batch"
    batch.mkdir(mode=0o700)
    accepted = batch / "working-policy.json"
    accepted.write_text('{"fixture":true}\n')
    bindir = tmp_path / "bin"
    bindir.mkdir()
    command = bindir / "skynet"
    command.write_text("""#!/usr/bin/python3
import json,os,sys
from pathlib import Path
args=sys.argv[1:]
assert args[:3]==['raw','--tags','haproxy_preflight']
assert Path(os.environ['PLAYBOOK']).name=='operations.yml'
assert '@'+str(Path(os.environ['FIXTURE_BATCH'])/'working-policy.json') in args
settings=next(json.loads(v) for v in args if v.startswith('{'))
assert settings=={'haproxy_preflight_window_seconds':600,'haproxy_preflight_sample_interval':0.5}
output=Path(next(v.split('=',1)[1] for v in args if v.startswith('haproxy_preflight_output=')))
print('fixture activity capture',flush=True)
if os.environ['FIXTURE_STATUS']=='0':
 output.write_text('{}')
 Path(str(output)+'.metadata.json').write_text('[]')
sys.exit(int(os.environ['FIXTURE_STATUS']))
""")
    command.chmod(0o755)
    blocks = re.findall(r"```bash\n(.*?)\n```", (ROOT / "migrator/guides/haproxy.md").read_text(), re.S)
    snippet = next(block for block in blocks if 'haproxy_preflight_window_seconds":600' in block)
    snippet = snippet.replace("/opt/homelab", str(tmp_path / "repo")).replace("/opt/ansible/ansible-venv", str(tmp_path / "venv"))
    result = subprocess.run(
        ["/bin/bash", "-c", snippet],
        env={
            **os.environ,
            "PATH": str(bindir) + ":/usr/bin:/bin",
            "FIXTURE_BATCH": str(batch),
            "FIXTURE_STATUS": str(status),
            "HAPROXY_BATCH": str(batch),
        },
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == status, result.stdout + result.stderr
    assert result.stdout.index("Private log:") < result.stdout.index("fixture activity capture")
    logs = list(batch.glob("live-activity-*/operator.log"))
    assert len(logs) == 1 and logs[0].stat().st_mode & 0o777 == 0o600
    assert logs[0].parent.stat().st_mode & 0o777 == 0o700
    assert f"Activity capture exited with status {status}" in logs[0].read_text()
    assert accepted.read_text() == '{"fixture":true}\n'


@pytest.mark.parametrize("family,local", [(4, False), (6, False), (4, True), (6, True)])
def test_retransmission_between_counter_reads_keeps_observation_inside_drop_interval(family, local):
    """A late retransmission must not make a valid DROP look smaller than its observer."""
    chain = "SKY-MGT-OUT" if local else "SKY-MGT-PRE"
    source, destination = ("127.0.0.1", "127.0.0.1") if family == 4 else ("::1", "::1")
    plan = {"source": [source, 41001], "destination": [destination, 19091], "family": family, "route": {"dev": "lo"}}
    drop = ["-p", "tcp", "-m", "addrtype", "--dst-type", "LOCAL", "--dport", "19091", "-j", "DROP"]
    installed, snapshots = [], []

    def execute(argv):
        if argv[0].endswith("-save"):
            # Reproduce the live 4-DROP/5-observation discrepancy: a packet
            # arrives between the two reads, increasing both counters together.
            count = 10 if not installed else 14 + len(snapshots) - 1
            snapshots.append(count)
            observation = ""
            if installed:
                observation = f"[{count - 10}:300] -A {chain} " + shlex.join(installed[0]) + "\n"
            return observation + f"[{count}:900] -A {chain} " + shlex.join(drop) + "\n"
        if "-I" in argv:
            installed.append(argv[argv.index("-I") + 3 :])
        elif "-D" in argv:
            assert argv[argv.index("-D") + 2 :] == installed.pop()
        else:
            pytest.fail("unexpected operation")
        return ""

    evidence = HELPER.negative_observe(
        plan, local, lambda: {"result": "timeout", "source": plan["source"], "destination": plan["destination"]}, lambda: None, execute
    )
    assert snapshots == [10, 14, 15]
    assert evidence["observation_packets"] == [4] and evidence["drop_increase"] == 5
    assert installed == []
