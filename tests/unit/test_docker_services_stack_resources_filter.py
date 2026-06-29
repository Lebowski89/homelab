from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_PATH = REPO_ROOT / "ansible/roles/docker_services/filter_plugins/docker_services_stack_resources.py"


def load_plugin():
    spec = importlib.util.spec_from_file_location("docker_services_stack_resources", PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)

    assert spec.loader is not None

    spec.loader.exec_module(module)
    return module


def test_normalize_list_resources_defaults_external_true():
    plugin = load_plugin()

    result = plugin.docker_services_normalize_stack_resources(
        [
            "frontend",
            " backend ",
            "",
            None,
        ]
    )

    assert result == {
        "frontend": {
            "external": True,
        },
        "backend": {
            "external": True,
        },
    }

def test_normalize_mapping_resources_defaults_external_true_when_missing():
    plugin = load_plugin()

    result = plugin.docker_services_normalize_stack_resources(
        {
            "frontend": {
                "name": "frontend_external",
            },
            "backend": {
                "external": False,
            },
            "empty": None,
        }
    )

    assert result == {
        "frontend": {
            "name": "frontend_external",
            "external": True,
        },
        "backend": {
            "external": False,
        },
        "empty": {
            "external": True,
        },
    }


def test_normalize_string_input_fails():
    plugin = load_plugin()

    try:
        plugin.docker_services_normalize_stack_resources("frontend")
    except Exception as exc:
        assert "not a string" in str(exc)
    else:
        raise AssertionError("Expected string input to fail")


def test_merge_stack_networks_creates_stack_when_missing():
    plugin = load_plugin()

    result = plugin.docker_services_merge_stack_resources(
        {},
        "traefik",
        "networks",
        ["frontend"],
    )

    assert result == {
        "traefik": {
            "networks": {
                "frontend": {
                    "external": True,
                },
            },
        },
    }


def test_merge_stack_volumes_creates_stack_when_missing():
    plugin = load_plugin()

    result = plugin.docker_services_merge_stack_resources(
        {},
        "postgres",
        "volumes",
        ["pgdata"],
    )

    assert result == {
        "postgres": {
            "volumes": {
                "pgdata": {
                    "external": True,
                },
            },
        },
    }


def test_merge_stack_resources_preserves_existing_stack_fields():
    plugin = load_plugin()

    result = plugin.docker_services_merge_stack_resources(
        {
            "traefik": {
                "services": {
                    "traefik": {
                        "image": "traefik:v3",
                    },
                },
            },
        },
        "traefik",
        "networks",
        ["frontend"],
    )

    assert result == {
        "traefik": {
            "services": {
                "traefik": {
                    "image": "traefik:v3",
                },
            },
            "networks": {
                "frontend": {
                    "external": True,
                },
            },
        },
    }


def test_merge_stack_resources_recursive_merges_existing_resource_defs():
    plugin = load_plugin()

    result = plugin.docker_services_merge_stack_resources(
        {
            "traefik": {
                "networks": {
                    "frontend": {
                        "name": "frontend_external",
                        "external": True,
                    },
                },
            },
        },
        "traefik",
        "networks",
        {
            "frontend": {
                "driver": "overlay",
            },
        },
    )

    assert result == {
        "traefik": {
            "networks": {
                "frontend": {
                    "name": "frontend_external",
                    "external": True,
                    "driver": "overlay",
                },
            },
        },
    }


def test_merge_stack_resources_preserves_other_stacks():
    plugin = load_plugin()

    result = plugin.docker_services_merge_stack_resources(
        {
            "traefik": {
                "networks": {
                    "frontend": {
                        "external": True,
                    },
                },
            },
            "plex": {
                "services": {
                    "plex": {
                        "image": "plex",
                    },
                },
            },
        },
        "plex",
        "volumes",
        ["plex_config"],
    )

    assert result == {
        "traefik": {
            "networks": {
                "frontend": {
                    "external": True,
                },
            },
        },
        "plex": {
            "services": {
                "plex": {
                    "image": "plex",
                },
            },
            "volumes": {
                "plex_config": {
                    "external": True,
                },
            },
        },
    }


def test_invalid_resource_type_fails():
    plugin = load_plugin()

    try:
        plugin.docker_services_merge_stack_resources(
            {},
            "traefik",
            "configs",
            [],
        )
    except Exception as exc:
        assert "stack_resource_type must be one of" in str(exc)
    else:
        raise AssertionError("Expected invalid resource type to fail")


def test_empty_stack_name_fails():
    plugin = load_plugin()

    try:
        plugin.docker_services_merge_stack_resources(
            {},
            "",
            "networks",
            [],
        )
    except Exception as exc:
        assert "docker_services_stack_name must be a non-empty string" in str(exc)
    else:
        raise AssertionError("Expected empty stack name to fail")
