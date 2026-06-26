from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_PATH = REPO_ROOT / "ansible/roles/docker_services/filter_plugins/docker_services_deploy.py"


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

    try:
        plugin.docker_services_build_deploy_config(
            {
                "mode": "replicated",
                "profile": "standard",
            },
            profiles=deploy_profiles(),
            restart_policy="not-a-dict",
        )
    except Exception as exc:
        assert "deploy_restart_policy override must be a mapping" in str(exc)
    else:
        raise AssertionError("Expected non-mapping override to fail")
