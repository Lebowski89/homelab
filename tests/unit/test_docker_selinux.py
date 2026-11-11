"""Exercise opt-in daemon confinement with mocked host operations and real tasks."""

import json

import pytest
from test_container_installation import facts

pytest_plugins = ["test_system"]
pytestmark = pytest.mark.integration

CONFIG = "/etc/docker/daemon.json"


def run(system_run, *, check=False, overrides=None, **kwargs):
    host = facts("Rocky", "10.2")
    host["selinux"] = {"status": "enabled", "mode": "enforcing"}
    return system_run(
        role="docker",
        tags="docker_install",
        check=check,
        overrides={
            "ansible_facts": host,
            "docker_selinux_enable": True,
            "fixture_docker_selinux": False,
            "fixture_services": {"docker.service": {"state": "running"}},
            **(overrides or {}),
        },
        **kwargs,
    )


def successful(result):
    assert result.returncode == 0, result.stdout + result.stderr


def writes(calls):
    return [call for call in calls if call["module"] in {"dnf", "apt", "rpm_key", "yum_repository", "copy", "file", "systemd_service"}]


def restarts(calls):
    return [call for call in calls if call["module"] == "systemd_service" and call["options"]["state"] == "restarted"]


@pytest.mark.parametrize("distro,fresh", [("Rocky", False), ("Rocky", True), ("Fedora", True)])
def test_configuration_preserves_other_fields_and_converges_without_repeated_restarts(system_run, distro, fresh):
    existing = {} if fresh else {"log-driver": "local", "log-opts": {"max-size": "12m"}, "selinux-enabled": False}
    overrides = {"fixture_files": {} if fresh else {CONFIG: json.dumps(existing)}}
    if fresh:
        overrides["fixture_services"] = {}
    if distro == "Fedora":
        host = facts("Fedora", "44", "dnf5")
        host["selinux"] = {"status": "enabled", "mode": "enforcing"}
        overrides["ansible_facts"] = host
    result, calls, state = run(system_run, overrides=overrides, main=True)
    successful(result)
    assert json.loads(state["podman_files"][CONFIG]) == {**existing, "selinux-enabled": True}
    assert len(restarts(calls)) == (0 if fresh else 1)
    copy = next(call for call in calls if call["module"] == "copy")
    assert copy["no_log"] is True and copy["diff"] is False
    assert copy["options"]["validate"] == "/usr/bin/dockerd --validate --config-file %s"
    assert all(call["module"] != "community.docker.docker_swarm" for call in calls)
    policy = next(call["options"] for call in calls if call["module"] == "dnf" and call["options"].get("name") == "container-selinux")
    assert policy["use_backend"] == ("dnf5" if distro == "Fedora" else "dnf4")
    assert policy["state"] == "present" and policy["disable_gpg_check"] is False and policy["allowerasing"] is False
    result, calls, _ = run(
        system_run,
        overrides={**overrides, "fixture_docker_containers": [{"Id": "running"}], "fixture_docker_swarm_state": "active"},
        main=True,
    )
    successful(result)
    assert "changed=0" in result.stdout
    assert not restarts(calls)
    assert not any(call["module"] == "copy" for call in calls)


@pytest.mark.parametrize(
    "failure", ["running", "swarm", "alternate-config", "cli-selinux", "symlink", "invalid-json", "non-object", "permissive", "boolean"]
)
def test_unsafe_transition_fails_before_package_or_daemon_mutation(system_run, failure):
    overrides = {}
    if failure == "running":
        overrides["fixture_docker_containers"] = [{"Id": "running"}]
    elif failure == "swarm":
        overrides["fixture_docker_swarm_state"] = "active"
    elif failure in {"alternate-config", "cli-selinux"}:
        flag = "--config-file=/operator/daemon.json" if failure == "alternate-config" else "--selinux-enabled=false"
        overrides["fixture_docker_exec_start"] = "{ path=/usr/bin/dockerd ; argv[]=/usr/bin/dockerd " + flag + " ; }"
    elif failure == "symlink":
        overrides.update(fixture_files={CONFIG: "{}"}, fixture_symlinks=[CONFIG])
    elif failure in {"invalid-json", "non-object"}:
        overrides["fixture_files"] = {CONFIG: "{invalid" if failure == "invalid-json" else "[]"}
    elif failure == "permissive":
        host = facts("Fedora", "44", "dnf5")
        host["selinux"] = {"status": "enabled", "mode": "permissive"}
        overrides["ansible_facts"] = host
    else:
        overrides["docker_selinux_enable"] = "true"
    result, calls, _ = run(system_run, overrides=overrides)
    assert result.returncode != 0
    assert not writes(calls)


def test_semantically_enabled_configuration_is_not_reformatted_but_inactive_capability_is_restarted(system_run):
    config = '{"selinux-enabled":true,"log-driver":"local"}'
    result, calls, state = run(system_run, overrides={"fixture_files": {CONFIG: config}})
    successful(result)
    assert len(restarts(calls)) == 1
    assert CONFIG not in state.get("podman_files", {})
    assert not any(call["module"] == "copy" for call in calls)


def test_invalid_candidate_does_not_replace_configuration_or_restart(system_run):
    result, calls, state = run(
        system_run,
        overrides={"fixture_docker_config_invalid": True, "fixture_files": {CONFIG: '{"labels":["fixture-private-daemon-setting"]}'}},
    )
    assert result.returncode != 0
    assert CONFIG not in state.get("podman_files", {})
    assert not restarts(calls)
    assert any(call["module"] == "copy" and call["options"]["dest"] == CONFIG for call in calls)
    assert "candidate validation or installation failed" in result.stdout
    assert "fixture-private-daemon-setting" not in result.stdout + result.stderr


def test_failure_to_advertise_confinement_is_not_reported_as_success(system_run):
    result, _, _ = run(system_run, overrides={"fixture_docker_capability_failure": True})
    assert result.returncode != 0
    assert "Docker did not advertise SELinux" in result.stdout


def test_check_mode_defers_runtime_and_mutations_on_a_fresh_host(system_run):
    result, calls, _ = run(system_run, check=True, overrides={"fixture_services": {}})
    successful(result)
    assert not writes(calls)
    assert not any(call["module"] in {"command", "uri"} and call["options"].get("argv", [""])[0] != "modinfo" for call in calls)
    assert "confinement has not been verified" in result.stdout


def test_default_preserves_daemon_configuration_and_ignores_selinux_management(system_run):
    result, calls, _ = run(system_run, overrides={"docker_selinux_enable": False, "fixture_files": {CONFIG: "operator-managed"}})
    successful(result)
    assert not any(call["module"] in {"slurp", "copy", "uri", "service_facts"} for call in calls)
    assert not restarts(calls)
