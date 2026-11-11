"""Execute the central bridge owner without contacting a runtime or firewall."""

from copy import deepcopy

import pytest
from test_container_installation import facts

pytest_plugins = ["test_system"]
pytestmark = pytest.mark.integration

DNS_FILE = "/etc/containers/containers.conf.d/50-skynet-rootful-dns.conf"
HOST = {
    "networkBackend": "netavark",
    "cgroupVersion": "v2",
    "serviceIsRemote": False,
    "security": {"rootless": False, "selinuxEnabled": True},
    "networkBackendInfo": {"path": "/fixture/netavark", "dns": {"path": "/fixture/aardvark-dns"}},
}
NETWORK = {"name": "mgt-services", "driver": "bridge", "dns_enabled": True, "internal": False}


def run_network(system_run, *, distro="Rocky", version="10.1", backend=None, **kwargs):
    overrides = {
        "ansible_facts": facts(distro, version, backend),
        "fixture_files": {
            "/usr/lib/systemd/system-generators/podman-system-generator": "",
            "/fixture/netavark": "",
            "/fixture/aardvark-dns": "",
            **kwargs.pop("files", {}),
        },
        **kwargs.pop("overrides", {}),
    }
    return system_run(role="podman", tags="podman_network", main=True, overrides=overrides, **kwargs)


def successful(result):
    assert result.returncode == 0, result.stdout + result.stderr


def mutations(calls):
    return [call for call in calls if call["module"] in {"apt", "dnf", "file", "template", "copy", "systemd_service", "systemd"}]


@pytest.mark.parametrize("distro,version,backend", [("Ubuntu", "26.04", "apt"), ("Fedora", "43", "dnf5"), ("Rocky", "10.1", "dnf")])
def test_network_only_selection_preserves_central_resources_and_converges(system_run, distro, version, backend):
    args = dict(distro=distro, version=version, backend=backend)
    result, calls, _ = run_network(system_run, **args)
    successful(result)
    assert not any(call["module"] in {"apt", "dnf", "user", "group", "package_facts", "include_tasks"} for call in calls)
    templates = {call["options"]["dest"]: call["content"] for call in calls if call["module"] == "template"}
    assert "dns_bind_port = 5533" in templates[DNS_FILE]
    assert "NetworkName=mgt-services" in templates["/etc/containers/systemd/mgt-services.network"]
    assert all(call["options"].get("setype") == "_default" for call in calls if call["module"] in {"file", "template"})
    services = [call["options"] for call in calls if call["module"] == "systemd_service"]
    assert services == [{"daemon_reload": True}, {"name": "mgt-services-network.service", "state": "started"}]
    result, calls, _ = run_network(system_run, **args)
    successful(result)
    assert "changed=0" in result.stdout
    assert not any(call["module"] == "systemd_service" and "daemon_reload" in call["options"] for call in calls)
    assert not any(call["options"].get("state") in {"absent", "restarted", "stopped"} for call in calls)


def test_network_and_dns_overrides_retain_host_mode_dns_and_firewall_settings(system_run):
    result, calls, _ = run_network(
        system_run,
        overrides={
            "podman_shared_network_name": "operator-services",
            "podman_shared_network_dns_bind_port": 5534,
            "fixture_dns_users": ["host", "none"],
            "fixture_services": {"firewalld.service": {"state": "running"}},
        },
    )
    successful(result)
    assert any(call["module"] == "template" and "dns_bind_port = 5534" in call["content"] for call in calls)
    assert any(call["options"].get("name") == "operator-services-network.service" for call in calls)
    for call in calls:
        if call["module"] == "command":
            assert call["options"]["argv"][0] == "podman"
            assert not set(call["options"]["argv"]) & {"run", "restart", "stop", "rm", "reset", "reload"}
    assert not any("/etc/firewalld" in str(call["options"]) or "/etc/resolv.conf" in str(call["options"]) for call in mutations(calls))


@pytest.mark.parametrize("missing", [True, False], ids=["absent-runtime", "installed-runtime"])
def test_check_mode_never_initializes_runtime_or_starts_networks(system_run, missing):
    result, calls, _ = run_network(system_run, check=True, overrides={"fixture_podman_version": "" if missing else "podman version 5.4.2"})
    successful(result)
    commands = [call["options"]["argv"] for call in calls if call["module"] == "command"]
    assert commands == [["podman", "--version"]]
    assert not any(call["module"] in {"apt", "dnf", "systemd_service", "service_facts"} for call in calls)
    assert "deferred" in result.stdout and "does not verify DNS traffic" in result.stdout


@pytest.mark.parametrize("failure", ["platform", "backend", "rootless", "selinux", "provider", "old-runtime"])
def test_rejection_precedes_dns_quadlet_or_service_changes(system_run, failure):
    host = deepcopy(HOST)
    overrides = {"fixture_podman_host": host}
    if failure == "platform":
        overrides["ansible_facts"] = facts("AlmaLinux", "10.1")
    elif failure == "backend":
        host["networkBackend"] = "cni"
    elif failure == "rootless":
        host["security"]["rootless"] = True
    elif failure == "selinux":
        host["security"]["selinuxEnabled"] = False
    elif failure == "provider":
        host["networkBackendInfo"]["dns"]["path"] = "/fixture/missing-aardvark"
    else:
        overrides["fixture_podman_version"] = "podman version 5.4.0"
    result, calls, _ = run_network(system_run, overrides=overrides)
    assert result.returncode != 0
    assert not mutations(calls)


@pytest.mark.parametrize("properties", [{"driver": "macvlan"}, {"dns_enabled": False}, {"internal": True}, {"name": "another-network"}])
def test_incompatible_existing_network_requires_explicit_operator_maintenance(system_run, properties):
    result, calls, _ = run_network(system_run, overrides={"fixture_network_exists_rc": 0, "fixture_network": [{**NETWORK, **properties}]})
    assert result.returncode != 0 and "never removes networks" in result.stdout
    assert not mutations(calls)


@pytest.mark.parametrize("content", [None, "[network]\ndns_bind_port=5534\n", "[engine]\ndns_bind_port=5533\n"])
def test_changed_or_unknown_dns_port_cannot_disrupt_running_bridge_users(system_run, content):
    result, calls, _ = run_network(
        system_run, files={DNS_FILE: content} if content else {}, overrides={"fixture_dns_users": ["other-services"]}
    )
    assert result.returncode != 0 and "while bridge containers are running" in result.stdout
    assert not mutations(calls)


def test_unchanged_dns_port_allows_existing_bridge_users_without_restarting_them(system_run):
    result, calls, _ = run_network(
        system_run,
        files={DNS_FILE: "# operator comment\n[network]\ndns_bind_port = 5533 # DNS\n"},
        overrides={"fixture_dns_users": ["other-services"], "fixture_network_exists_rc": 0},
    )
    successful(result)
    assert not any(call["options"].get("state") in {"restarted", "stopped", "absent"} for call in calls)
    assert not any("ps" in call["options"].get("argv", []) for call in calls if call["module"] == "command")
