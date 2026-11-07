"""Platform/coexistence boundaries use only fixture metadata and fake kernels."""

import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from test_service_firewall_lifecycle import ACTION, REMOTE
from test_service_operational_maintenance import CHECK, worker_fixture
from test_worker_backend_firewall import FW, ROLE, ROOT, Kernel, apply


@pytest.mark.parametrize("profile", ["mgt", "workers"])
@pytest.mark.parametrize(
    ("distro", "version", "expected"),
    [
        ("fedora", "43", True),
        ("fedora", "45", True),
        ("fedora", "42", False),
        ("rocky", "9.7", False),
        ("rocky", "10.2", True),
        ("rocky", "8.10", False),
        ("rhel", "10", False),
        ("debian", "13", False),
    ],
)
def test_explicit_runtime_platforms(profile, distro, version, expected):
    assert FW.supported_platform(profile, {"ID": distro, "VERSION_ID": version}) is expected


def test_legacy_profile_boundaries_are_retained():
    assert FW.supported_platform("mgt", {"ID": "ubuntu", "VERSION_ID": "26.04"})
    assert not FW.supported_platform("workers", {"ID": "ubuntu", "VERSION_ID": "26.04"})
    assert FW.supported_platform("workers", {"ID": "ubuntu", "VERSION_ID": "24.04"})
    assert not FW.supported_platform("mgt", {"ID": "ubuntu", "VERSION_ID": "24.04"})
    assert FW.supported_platform("workers", {}, unraid=True)
    assert not FW.supported_platform("mgt", {}, unraid=True)


@pytest.fixture
def rpm_host(tmp_path, monkeypatch):
    """Every command and configuration read is replaced at the I/O boundary."""
    monkeypatch.setattr(FW, "read_os_release", lambda: {"ID": "rocky", "VERSION_ID": "10.2"})
    monkeypatch.setattr(FW, "Path", lambda path: tmp_path / path.lstrip("/"))
    for directory in ["usr/lib/firewalld", "etc/firewalld"]:
        (tmp_path / directory).mkdir(parents=True)
    host = SimpleNamespace(
        root=tmp_path,
        calls=[],
        state="active",
        backend="nftables",
        direct="",
        mixed=False,
        flow=False,
        version="2.4.3",
        runtime_version="2.4.3",
        runtime_state="RUNNING",
    )

    def read(argv):
        host.calls.append(argv)
        if argv == ["firewalld", "--version"]:
            raise RuntimeError("firewalld: error: unrecognized arguments: --version")
        if argv == ["firewall-offline-cmd", "--version"]:
            return host.version
        if argv[-1] == "--version":
            return "v1.8.11 (legacy)" if host.mixed and argv[0] == "ip6tables-restore" else "v1.8.11 (nf_tables)"
        if argv[0] == "nft":
            return json.dumps(
                {"nftables": [{"table": {"family": "inet", "name": "firewalld"}}, *([{"flowtable": {}}] if host.flow else [])]}
            )
        if argv[0] == "systemctl":
            assert argv[1:] == ["show", "firewalld.service", "--property=ActiveState", "--value"]
            return host.state
        if argv[0] == "busctl":
            assert argv[1] == "get-property"
            if argv[-1] in {"version", "state"}:
                assert argv[3:5] == ["/org/fedoraproject/FirewallD1", "org.fedoraproject.FirewallD1"]
                return 's "' + getattr(host, "runtime_" + argv[-1]) + '"'
            return 's "' + host.backend + '"'
        assert argv[0] == "firewall-cmd" and argv[-1] in {"--get-all-chains", "--get-all-rules", "--get-all-passthroughs"}
        return host.direct

    host.run = read
    return host


@pytest.mark.parametrize("version", ["2.0.0", "2.4.3"])
def test_native_firewalld_coexistence_is_read_only_and_inactive_daemon_is_not_activated(rpm_host, version):
    rpm_host.version = version
    FW.rpm_firewall_preflight(rpm_host.run)
    assert len([command for command in rpm_host.calls if command[0] == "firewall-cmd"]) == 6
    rpm_host.calls.clear()
    rpm_host.state = "inactive"
    FW.rpm_firewall_preflight(rpm_host.run)
    assert not any(command[0] in {"busctl", "firewall-cmd"} for command in rpm_host.calls)
    assert not list(rpm_host.root.rglob("*.conf"))


@pytest.mark.parametrize(
    "conflict",
    ["mixed", "flow", "old-firewalld", "runtime-direct", "permanent-direct", "configured-backend", "configured-flow", "running-backend"],
)
def test_rpm_coexistence_conflicts_rejected_without_host_changes(rpm_host, conflict):
    if conflict in {"mixed", "flow"}:
        setattr(rpm_host, conflict, True)
    elif conflict == "old-firewalld":
        rpm_host.version = "1.3.4"
    elif conflict == "runtime-direct":
        rpm_host.direct = "ipv4 filter FOREIGN 0 -j ACCEPT"
    elif conflict == "permanent-direct":
        (rpm_host.root / "etc/firewalld/direct.xml").write_text('<direct><chain ipv="ipv4" table="filter" chain="FOREIGN"/></direct>')
    elif conflict == "configured-backend":
        (rpm_host.root / "etc/firewalld/firewalld.conf").write_text("FirewallBackend=iptables\n")
    elif conflict == "configured-flow":
        (rpm_host.root / "etc/firewalld/firewalld.conf").write_text("NftablesFlowtable=eth0\n")
    else:
        rpm_host.backend = "iptables"
    before = {path: path.read_bytes() for path in rpm_host.root.rglob("*") if path.is_file()}
    with pytest.raises(ValueError):
        FW.rpm_firewall_preflight(rpm_host.run)
    assert {path: path.read_bytes() for path in rpm_host.root.rglob("*") if path.is_file()} == before


def test_coexistence_uses_local_config_precedence(rpm_host):
    (rpm_host.root / "usr/lib/firewalld/firewalld.conf").write_text("FirewallBackend=iptables\n")
    (rpm_host.root / "etc/firewalld/firewalld.conf").write_text("# retained native backend\nFirewallBackend=nftables\n")
    FW.rpm_firewall_preflight(rpm_host.run)


@pytest.mark.parametrize("runtime_version,runtime_state", [("1.3.4", "RUNNING"), ("2.4.3", "INIT"), ("2.4.3", "FAILED")])
def test_upgraded_package_does_not_authorize_old_or_unready_daemon(rpm_host, runtime_version, runtime_state):
    rpm_host.runtime_version, rpm_host.runtime_state = runtime_version, runtime_state
    with pytest.raises(ValueError, match="running firewalld daemon|RUNNING state"):
        FW.rpm_firewall_preflight(rpm_host.run)
    assert not any(command[0] == "firewall-cmd" for command in rpm_host.calls)
    assert not list(rpm_host.root.rglob("*.conf"))


def test_unverifiable_runtime_property_is_rejected_without_activation(rpm_host):
    def read(argv):
        if argv[0] == "busctl" and argv[-1] == "version":
            return 'as 1 "2.4.3"'
        return rpm_host.run(argv)

    with pytest.raises(ValueError, match="cannot verify the running firewalld"):
        FW.rpm_firewall_preflight(read)
    assert not any(command[0] == "firewall-cmd" for command in rpm_host.calls)


def test_worker_fresh_nft_audit_and_removal_do_not_materialize_tables():
    kernel = Kernel("nf_tables")
    kernel.state = {family: {table: {} for table in ["mangle", "filter"]} for family in [4, 6]}
    native = deepcopy(kernel.native_rules)
    assert not apply(kernel, operation="check")["compliant"]
    assert not apply(kernel, operation="remove")["changed"]
    assert not any(command[0].endswith(("-save", "-restore")) for command, _ in kernel.calls)
    assert apply(kernel)["changed"]
    assert not apply(kernel)["changed"]
    assert apply(kernel, operation="check")["compliant"]
    assert kernel.native_rules == native


@pytest.mark.parametrize("profile", ["mgt", "workers"])
def test_automatic_lifecycle_checks_rpm_boundary_before_policy_or_runtime_mutation(tmp_path, monkeypatch, profile):
    store = object.__new__(REMOTE.Store)
    store.profile, store.flash, store.request = profile, False, {"action": "install"}
    events = []
    platform = SimpleNamespace(
        read_os_release=lambda: {"ID": "rocky", "VERSION_ID": "10.2"},
        supported_platform=FW.supported_platform,
        rpm_firewall_preflight=lambda: (_ for _ in ()).throw(ValueError("Direct configuration conflict")),
        local_addresses=lambda _: ["192.0.2.48"],
        execute=None,
    )
    helper = SimpleNamespace(validate_policy=lambda _: events.append("policy"), **vars(platform))
    helper.OWNED = platform
    store.helper = helper
    monkeypatch.setattr(REMOTE, "Path", lambda path: tmp_path / path.lstrip("/"))
    (tmp_path / "run/systemd/system").mkdir(parents=True)
    with pytest.raises(ValueError, match="Direct configuration"):
        store.validate({"inventory_address": "192.0.2.48"})
    assert events == []
    store.request = {"action": "remove", "source_addresses": ["192.0.2.48"]}
    store.validate({"inventory_address": "192.0.2.48", "sources": ["192.0.2.48"]})
    assert events == ["policy"]


@pytest.mark.parametrize(("profile", "unraid"), [("mgt", False), ("workers", False), ("workers", True)])
def test_transport_selects_actual_worker_storage_and_keeps_interpreter_in_persistence(monkeypatch, profile, unraid):
    from ansible.plugins.action import ActionBase

    monkeypatch.setattr(ActionBase, "run", lambda *args: {})
    host = "storage" if profile == "workers" else "manager"
    action = object.__new__(ACTION.ActionModule)
    action._task = SimpleNamespace(
        check_mode=False,
        args={
            "phase": "install",
            "profile": profile,
            "policy": {"inventory_address": "192.0.2.48", "endpoints": []},
            "inventory_host": host,
        },
    )
    observed = []

    def execute(module_name, module_args, **kwargs):
        if module_name == "ansible.builtin.stat":
            assert module_args["path"] == "/etc/unraid-version"
            return {"stat": {"exists": unraid}}
        assert module_name == "ansible.builtin.command"
        assert module_args["argv"][:2] == ["/usr/bin/python3.11", "-c"]
        observed.append(json.loads(module_args["stdin"]))
        return {"rc": 0, "stdout": '{"changed":false}'}

    action._execute_module = execute
    result = action.run(
        task_vars={"services_storage_host": "storage", "hostvars": {host: {"ansible_python_interpreter": "/usr/bin/python3.11"}}}
    )
    assert not result.get("failed")
    root = observed[0]["request"]["root"]
    assert root == (
        "/etc/skynet-mgt-firewall"
        if profile == "mgt"
        else "/boot/config/skynet-worker-backend-firewall"
        if unraid
        else "/etc/skynet-worker-backend-firewall"
    )
    for content in observed[0]["units"].values():
        if "ExecStart" in content:
            assert "=/usr/bin/python3.11 " in content


def test_rpm_storage_worker_protection_audit_uses_posix_policy_and_systemd():
    cfg, variables, policy, _ = worker_fixture()
    host = variables["services_storage_host"]
    variables["hostvars"][host]["ansible_python_interpreter"] = "/usr/bin/python3.11"
    policy["backend"] = "nf_tables"
    action = object.__new__(CHECK.ActionModule)
    action.variables = variables
    paths, commands = [], []
    action.module = lambda *_: {"stat": {"exists": False}}
    action.unraid_flash_device = lambda: pytest.fail("RPM storage must not inspect Unraid flash")
    action.read = lambda path, **kwargs: paths.append(path) or json.dumps(policy)
    action.owned = lambda path, **kwargs: paths.append(path)

    def command(argv):
        commands.append(argv)
        if argv[0] == "ip":
            return json.dumps([{"addr_info": [{"local": policy["inventory_address"]}]}])
        if "check" in argv:
            return '{"compliant":true,"families":[4,6]}'
        assert argv[0] == "systemctl" and argv[1] in {"is-enabled", "is-active"}
        return "active"

    action.command = command
    action.protection(cfg, host)
    assert all(path.startswith("/etc/skynet-worker-backend-firewall/") for path in paths)
    assert any(argv[0] == "/usr/bin/python3.11" for argv in commands)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("profile", "distro", "version", "manager", "ostree", "success"),
    [
        ("mgt", "Rocky", "10.2", "dnf", False, True),
        ("workers", "Rocky", "10.2", "dnf", False, True),
        ("workers", "Rocky", "9.7", "dnf", False, False),
        ("mgt", "Fedora", "43", "dnf5", False, True),
        ("workers", "Fedora", "45", "dnf5", False, True),
        ("mgt", "Rocky", "10.2", "apt", False, False),
        ("mgt", "Fedora", "43", "dnf5", True, False),
        ("mgt", "AlmaLinux", "10.2", "dnf", False, False),
    ],
)
def test_tagged_check_mode_platform_gate_uses_explicit_facts(tmp_path, profile, distro, version, manager, ostree, success):
    binary = Path(sys.executable).with_name("ansible-playbook")
    if not binary.is_file():
        pytest.skip("repository Ansible environment unavailable")
    roles = tmp_path / "roles"
    role = roles / "service_firewall"
    (role / "tasks").mkdir(parents=True)
    # Actual entry and platform tasks, replacing fact/stat I/O with metadata.
    (role / "tasks/main.yml").write_text((ROLE / "tasks/main.yml").read_text())
    tasks = yaml.safe_load((ROLE / "tasks/platform.yml").read_text())
    tasks = [task for task in tasks if not any(key in task for key in ["ansible.builtin.setup", "ansible.builtin.stat"])]
    (role / "tasks/platform.yml").write_text(yaml.safe_dump(tasks))
    (role / f"tasks/{profile}").mkdir()
    (role / f"tasks/{profile}/main.yml").write_text(
        yaml.safe_dump([{"name": "Safe profile sentinel", "ansible.builtin.debug": {"msg": "profile reached"}}])
    )
    tag = ("mgt_firewall_" if profile == "mgt" else "worker_backend_firewall_") + "install"
    variables = {
        "service_firewall_profile": profile,
        "service_firewall_operation": "install",
        "service_firewall_unraid": {"stat": {"exists": False}},
        "service_firewall_ostree": {"stat": {"exists": ostree}},
        "ansible_facts": {
            "distribution": distro,
            "distribution_version": version,
            "distribution_major_version": version.split(".")[0],
            "system": "Linux",
            "pkg_mgr": manager,
            "service_mgr": "systemd",
            "python": {"version": {"major": 3, "minor": 11}},
        },
    }
    play = [
        {
            "hosts": "localhost",
            "gather_facts": False,
            "vars": variables,
            "tasks": [
                {
                    "name": "Tagged role",
                    "ansible.builtin.include_role": {"name": "service_firewall", "apply": {"tags": [tag]}},
                    "tags": [tag],
                }
            ],
        }
    ]
    path = tmp_path / "play.yml"
    path.write_text(yaml.safe_dump(play))
    result = subprocess.run(
        [str(binary), "-i", "localhost,", "-c", "local", str(path), "--check", "--tags", tag],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "ANSIBLE_CONFIG": str(ROOT / "ansible/bootstrap.cfg"),
            "ANSIBLE_ROLES_PATH": str(roles),
            "ANSIBLE_INJECT_FACT_VARS": "false",
        },
    )
    assert (result.returncode == 0) is success, result.stdout + result.stderr
    assert ("profile reached" in result.stdout) is success
    if success:
        assert "remain unverified" in result.stdout and "changed=0" in result.stdout
    else:
        assert "Service firewall requires conventional" in result.stdout
