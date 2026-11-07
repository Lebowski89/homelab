"""Exercise the explicit Netavark provider choice without runtime/firewall I/O."""

from copy import deepcopy

import pytest
from test_container_installation import facts
from test_system import REPO

pytest_plugins = ["test_system"]
pytestmark = pytest.mark.integration

CONFIG = "/etc/containers/containers.conf.d/40-skynet-docker-compat.conf"
CANONICAL = (REPO / "ansible/roles/podman/files/docker-iptables-compat.conf").read_text()
HOST = {
    "networkBackend": "netavark",
    "security": {"rootless": False},
    "networkBackendInfo": {"version": "netavark 1.17.2"},
}


def run(system_run, *, enabled=True, check=False, overrides=None):
    values = dict(overrides or {})
    files = {
        "/usr/bin/podman": "",
        "/sys/fs/cgroup/cgroup.controllers": "",
        "/usr/lib/systemd/system-generators/podman-system-generator": "",
        **values.pop("fixture_files", {}),
    }
    return system_run(
        role="podman",
        tags="podman_install",
        check=check,
        overrides={
            "ansible_facts": facts("Rocky", "10.2", "dnf"),
            "podman_install_enable": False,
            "podman_docker_iptables_compatibility": enabled,
            "fixture_podman_host": deepcopy(HOST),
            "fixture_files": files,
            **values,
        },
    )


def successful(result):
    assert result.returncode == 0, result.stdout + result.stderr


def mutations(calls):
    return [c for c in calls if c["module"] in {"apt", "dnf", "file", "copy", "template", "systemd", "systemd_service", "user", "group"}]


def test_explicit_choice_converges_and_can_be_retired_without_runtime_lifecycle(system_run):
    result, calls, state = run(system_run)
    successful(result)
    assert state["podman_files"][CONFIG] == CANONICAL
    assert {call["module"] for call in mutations(calls)} == {"file", "copy"}
    commands = [call["options"]["argv"] for call in calls if call["module"] == "command"]
    assert all(command[0] not in {"nft", "firewall-cmd", "systemctl", "docker"} for command in commands)
    assert all(not set(command) & {"-P", "-A", "-I", "restart", "stop", "rm", "reset"} for command in commands)
    result, calls, _ = run(system_run, overrides={"fixture_dns_users": ["running-container"], "fixture_conmon_uids": [2222]})
    successful(result)
    assert "changed=0" in result.stdout
    assert not any(call["options"]["argv"][0] == "ps" for call in calls if call["module"] == "command")
    result, calls, state = run(system_run, enabled=False)
    successful(result)
    assert CONFIG not in state["podman_files"]
    assert [call["options"] for call in mutations(calls)] == [{"path": CONFIG, "state": "absent"}]
    result, calls, _ = run(system_run, enabled=False)
    successful(result)
    assert not mutations(calls)


@pytest.mark.parametrize(
    "failure",
    ["rootful-running", "rootless-running", "disable-active", "operator-config", "config-environment", "owned-file", "symlink", "boolean"],
)
def test_unsafe_transitions_fail_before_package_or_configuration_mutations(system_run, failure):
    overrides = {"podman_install_enable": True}
    if failure == "rootful-running":
        overrides["fixture_dns_users"] = ["fixture-container"]
    elif failure == "rootless-running":
        overrides["fixture_conmon_uids"] = [0, 2222]
    elif failure == "disable-active":
        overrides.update(
            {"podman_docker_iptables_compatibility": False, "fixture_files": {CONFIG: CANONICAL}, "fixture_conmon_uids": [2222]}
        )
    elif failure == "operator-config":
        overrides["fixture_files"] = {"/etc/containers/containers.conf.d/99-operator.conf": '[network]\nfirewall_driver="nftables"\n'}
    elif failure == "config-environment":
        overrides["fixture_provider_environment"] = "/fixture/operator.conf"
    elif failure in {"owned-file", "symlink"}:
        overrides["fixture_files"] = {CONFIG: CANONICAL if failure == "symlink" else "[network]\ndns_bind_port=5533\n"}
        if failure == "symlink":
            overrides["fixture_symlinks"] = [CONFIG]
    else:
        overrides["podman_docker_iptables_compatibility"] = "true"
    result, calls, _ = run(system_run, overrides=overrides)
    assert result.returncode != 0
    assert not mutations(calls)


@pytest.mark.parametrize("failure", ["legacy-tools", "future-provider", "wrong-backend"])
def test_unsupported_provider_cannot_write_compatibility_configuration(system_run, failure):
    overrides = {}
    if failure == "legacy-tools":
        overrides["fixture_legacy_compat_tool"] = "ip6tables-restore"
    elif failure == "future-provider":
        overrides["fixture_podman_host"] = {**HOST, "networkBackendInfo": {"version": "netavark 1.18.0"}}
    else:
        overrides["fixture_podman_host"] = {**HOST, "networkBackend": "cni"}
    result, calls, _ = run(system_run, overrides=overrides)
    assert result.returncode != 0
    assert not mutations(calls)


@pytest.mark.parametrize("version", ["", "podman version 5.4.2"])
def test_check_mode_reports_configuration_without_runtime_database_or_provider_operations(system_run, version):
    result, calls, _ = run(system_run, check=True, overrides={"fixture_podman_version": version})
    successful(result)
    assert not mutations(calls)
    commands = [c["options"]["argv"] for c in calls if c["module"] == "command"]
    assert commands == [["podman", "--version"]]
    assert "packet flow has not been verified" in result.stdout


def test_default_does_not_select_a_provider_or_change_operator_configuration(system_run):
    result, calls, _ = run(
        system_run,
        enabled=False,
        overrides={
            "fixture_files": {
                "/etc/containers/containers.conf.d/99-operator.conf": '[network]\nfirewall_driver="nftables"\n',
                "/usr/lib/systemd/system-generators/podman-system-generator": "",
            }
        },
    )
    successful(result)
    assert not mutations(calls)
    assert not any(c["module"] in {"find", "slurp"} for c in calls)
