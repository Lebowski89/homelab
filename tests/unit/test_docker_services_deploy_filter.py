from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml
from ansible.errors import AnsibleFilterError
from ansible.plugins.filter.core import combine
from jinja2.nativetypes import NativeEnvironment

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_PATH = REPO_ROOT / "ansible/roles/docker_services/filter_plugins/docker_services_deploy.py"
DEPLOY_TASK_PATH = REPO_ROOT / "ansible/roles/docker_services/tasks/sub_tasks/compose/deploy.yml"
PERSIST_TASK_PATH = REPO_ROOT / "ansible/roles/docker_services/tasks/sub_tasks/save_stack.yml"


def load_plugin():
    spec = importlib.util.spec_from_file_location("docker_services_deploy", PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)

    assert spec.loader is not None

    spec.loader.exec_module(module)
    return module


def deploy_profiles():
    return {
        "none": {},
        "standard": {
            "restart_policy": {
                "condition": "on-failure",
                "delay": "10s",
                "max_attempts": 5,
                "window": "2m",
            },
            "update_config": {
                "parallelism": 1,
                "delay": "10s",
                "failure_action": "rollback",
                "order": "stop-first",
            },
            "rollback_config": {
                "parallelism": 1,
                "delay": "10s",
                "order": "stop-first",
            },
        },
    }


def test_attach_deploy_config_only_rebuilds_selected_service():
    plugin = load_plugin()
    sidecar = {"image": "example/sidecar:1.0.0", "environment": {"SIDE": "car"}}
    source = {
        "app": {
            "image": "example/app:1.0.0",
            "deploy": {
                "mode": "replicated",
                "restart_policy": {"condition": "any", "delay": "5s"},
            },
        },
        "sidecar": sidecar,
    }

    result = plugin.docker_services_attach_deploy_config(
        source,
        "app",
        {"mode": "global", "restart_policy": {"condition": "on-failure"}},
    )

    assert result["app"] == {
        "image": "example/app:1.0.0",
        "deploy": {
            "mode": "global",
            "restart_policy": {"condition": "on-failure", "delay": "5s"},
        },
    }
    assert result["sidecar"] is sidecar
    assert source["app"]["deploy"]["mode"] == "replicated"


def test_attach_task_references_stack_mapping_once_without_recursive_combine():
    tasks = yaml.safe_load(DEPLOY_TASK_PATH.read_text())
    attach = next(task for task in tasks if task["name"] == "Compose deploy settings | Add deploy settings to service")
    expression = attach["ansible.builtin.set_fact"]["docker_services_compose_services"]

    assert expression.count("docker_services_compose_services") == 1
    assert "docker_services_attach_deploy_config" in expression
    assert "combine(" not in expression


def test_sequential_manager_persistence_retains_services_and_stacks():
    tasks = yaml.safe_load(PERSIST_TASK_PATH.read_text())
    persist = next(task for task in tasks if task["name"] == "Save stack | Store completed Compose configuration")
    expression = persist["ansible.builtin.set_fact"]["docker_services_compose_stacks"]
    environment = NativeEnvironment()
    environment.filters["combine"] = combine
    template = environment.from_string(expression)

    def persist_stack(stacks, stack_name, services, deploy_host):
        return template.render(
            hostvars={"manager": {"docker_services_compose_stacks": stacks}},
            docker_services_primary_manager="manager",
            docker_services_stack_name_effective=stack_name,
            docker_services_stack_deploy_type="container",
            docker_services_deploy_host_effective=deploy_host,
            docker_services_compose_services=services,
            docker_services_stack_networks={},
            docker_services_stack_volumes={},
        )

    stacks = persist_stack({}, "shared", {"one": {"image": "example/one:1"}}, "docker-a")
    stacks = persist_stack(
        stacks,
        "shared",
        {
            "one": {"image": "example/one:1"},
            "two": {"image": "example/two:1"},
        },
        "docker-a",
    )
    stacks = persist_stack(stacks, "separate", {"three": {"image": "example/three:1"}}, "docker-b")

    assert list(stacks) == ["shared", "separate"]
    assert list(stacks["shared"]["services"]) == ["one", "two"]
    assert list(stacks["separate"]["services"]) == ["three"]


def test_replicated_standard_profile_builds_expected_config():
    plugin = load_plugin()

    result = plugin.docker_services_build_deploy_config(
        {
            "mode": "replicated",
            "replicas": 2,
            "constraints": [
                "node.labels.docker_services_host == docker_services_unraid_host",
            ],
            "profile": "standard",
        },
        profiles=deploy_profiles(),
        default_profile="none",
    )

    assert result == {
        "mode": "replicated",
        "replicas": 2,
        "placement": {
            "constraints": [
                "node.labels.docker_services_host == docker_services_unraid_host",
            ],
        },
        "restart_policy": {
            "condition": "on-failure",
            "delay": "10s",
            "max_attempts": 5,
            "window": "2m",
        },
        "update_config": {
            "parallelism": 1,
            "delay": "10s",
            "failure_action": "rollback",
            "order": "stop-first",
        },
        "rollback_config": {
            "parallelism": 1,
            "delay": "10s",
            "order": "stop-first",
        },
    }


def test_global_mode_omits_replicas():
    plugin = load_plugin()

    result = plugin.docker_services_build_deploy_config(
        {
            "mode": "global",
            "replicas": 3,
            "profile": "none",
        },
        profiles=deploy_profiles(),
    )

    assert result == {
        "mode": "global",
    }


def test_constraints_string_is_split_and_trimmed():
    plugin = load_plugin()

    result = plugin.docker_services_build_deploy_config(
        {
            "mode": "replicated",
            "constraints": "node.role == worker, node.platform.os == linux, ",
            "profile": "none",
        },
        profiles=deploy_profiles(),
    )

    assert result["placement"] == {
        "constraints": [
            "node.role == worker",
            "node.platform.os == linux",
        ],
    }


def test_explicit_update_config_overrides_profile_value():
    plugin = load_plugin()

    result = plugin.docker_services_build_deploy_config(
        {
            "mode": "replicated",
            "profile": "standard",
        },
        profiles=deploy_profiles(),
        update_config={
            "delay": "30s",
        },
    )

    assert result["update_config"] == {
        "parallelism": 1,
        "delay": "30s",
        "failure_action": "rollback",
        "order": "stop-first",
    }


def test_resources_are_added_when_present():
    plugin = load_plugin()

    result = plugin.docker_services_build_deploy_config(
        {
            "mode": "replicated",
            "profile": "none",
            "resources": {
                "limits": {
                    "memory": "512M",
                },
            },
        },
        profiles=deploy_profiles(),
    )

    assert result["resources"] == {
        "limits": {
            "memory": "512M",
        },
    }


def test_profile_argument_overrides_deploy_cfg_profile():
    plugin = load_plugin()

    result = plugin.docker_services_build_deploy_config(
        {
            "mode": "replicated",
            "profile": "none",
        },
        profile="standard",
        profiles=deploy_profiles(),
    )

    assert "restart_policy" in result
    assert "update_config" in result
    assert "rollback_config" in result


def test_invalid_mode_fails():
    plugin = load_plugin()

    try:
        plugin.docker_services_build_deploy_config(
            {
                "mode": "weird",
            },
            profiles=deploy_profiles(),
        )
    except Exception as exc:
        assert "deploy_mode must be 'replicated' or 'global'" in str(exc)
    else:
        raise AssertionError("Expected invalid mode to fail")


def test_invalid_replicas_fails():
    plugin = load_plugin()

    try:
        plugin.docker_services_build_deploy_config(
            {
                "mode": "replicated",
                "replicas": "one",
            },
            profiles=deploy_profiles(),
        )
    except Exception as exc:
        assert "deploy_replicas must be a non-negative integer" in str(exc)
    else:
        raise AssertionError("Expected invalid replicas to fail")


def test_unknown_profile_fails():
    plugin = load_plugin()

    try:
        plugin.docker_services_build_deploy_config(
            {
                "mode": "replicated",
                "profile": "missing",
            },
            profiles=deploy_profiles(),
        )
    except Exception as exc:
        assert "Unknown deploy profile 'missing'" in str(exc)
    else:
        raise AssertionError("Expected unknown profile to fail")


def test_non_mapping_override_fails():
    plugin = load_plugin()

    with pytest.raises(AnsibleFilterError, match="deploy_restart_policy override must be a mapping"):
        plugin.docker_services_build_deploy_config(
            {
                "mode": "replicated",
                "profile": "standard",
            },
            profiles=deploy_profiles(),
            restart_policy="not-a-dict",
        )


def test_docker_rejects_podman_execution_contract():
    plugin = load_plugin()

    with pytest.raises(AnsibleFilterError, match=r"deploy\.execution is only supported by the Podman adapter"):
        plugin.docker_services_build_deploy_config(
            {"type": "container", "execution": {"mode": "rootless", "host_user": "podman-adminer"}},
            profiles=deploy_profiles(),
        )
