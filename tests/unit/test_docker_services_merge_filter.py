from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_PATH = REPO_ROOT / "ansible/roles/docker_services/filter_plugins/docker_services_merge.py"


def load_plugin():
    spec = importlib.util.spec_from_file_location("docker_services_merge", PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)

    assert spec.loader is not None

    spec.loader.exec_module(module)
    return module


def test_no_target_removes_targets_key():
    plugin = load_plugin()

    service = {
        "image": "example/app:1",
        "environment": {"TZ": "Australia/Melbourne"},
        "targets": {
            "main": {"name": "example"},
        },
    }

    result = plugin.docker_services_merge_target(service, None)

    assert result == {
        "image": "example/app:1",
        "environment": {"TZ": "Australia/Melbourne"},
    }


def test_target_mappings_merge_recursively():
    plugin = load_plugin()

    service = {
        "environment": {
            "TZ": "Australia/Melbourne",
            "PUID": "99",
        },
        "deploy": {
            "type": "swarm",
            "mode": "replicated",
            "profile": "standard",
        },
        "targets": {
            "main": {
                "environment": {
                    "PGID": "100",
                },
                "deploy": {
                    "replicas": 1,
                },
            },
        },
    }

    result = plugin.docker_services_merge_target(service, "main")

    assert result["environment"] == {
        "TZ": "Australia/Melbourne",
        "PUID": "99",
        "PGID": "100",
    }

    assert result["deploy"] == {
        "type": "swarm",
        "mode": "replicated",
        "profile": "standard",
        "replicas": 1,
    }


def test_lists_append_rp():
    plugin = load_plugin()

    service = {
        "secrets": [
            "parent_secret",
            "shared_secret",
        ],
        "targets": {
            "main": {
                "secrets": [
                    "shared_secret",
                    "target_secret",
                ],
            },
        },
    }

    result = plugin.docker_services_merge_target(service, "main")

    assert result["secrets"] == [
        "parent_secret",
        "shared_secret",
        "target_secret",
    ]


def test_target_command_replaces_parent_command():
    plugin = load_plugin()

    service = {
        "command": ["parent", "command"],
        "targets": {
            "main": {
                "command": ["target", "command"],
            },
        },
    }

    result = plugin.docker_services_merge_target(service, "main")

    assert result["command"] == ["target", "command"]


def test_target_entrypoint_replaces_parent_entrypoint():
    plugin = load_plugin()

    service = {
        "entrypoint": ["/parent-entrypoint.sh"],
        "targets": {
            "main": {
                "entrypoint": ["/target-entrypoint.sh"],
            },
        },
    }

    result = plugin.docker_services_merge_target(service, "main")

    assert result["entrypoint"] == ["/target-entrypoint.sh"]


def test_target_healthcheck_test_replaces_parent_healthcheck_test():
    plugin = load_plugin()

    service = {
        "healthcheck": {
            "test": ["CMD", "parent"],
            "interval": "1m",
            "timeout": "15s",
        },
        "targets": {
            "main": {
                "healthcheck": {
                    "test": ["CMD", "target"],
                },
            },
        },
    }

    result = plugin.docker_services_merge_target(service, "main")

    assert result["healthcheck"] == {
        "test": ["CMD", "target"],
        "interval": "1m",
        "timeout": "15s",
    }


def test_missing_target_fails_clearly():
    plugin = load_plugin()

    service = {
        "targets": {
            "main": {},
        },
    }

    try:
        plugin.docker_services_merge_target(service, "missing")
    except Exception as exc:
        assert "target 'missing' was not found" in str(exc)
        assert "Available targets: main" in str(exc)
    else:
        raise AssertionError("Expected missing target to fail")
