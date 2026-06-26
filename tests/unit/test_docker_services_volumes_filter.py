from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_PATH = REPO_ROOT / "ansible/roles/docker_services/filter_plugins/docker_services_volumes.py"


def load_plugin():
    spec = importlib.util.spec_from_file_location("docker_services_volumes", PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)

    assert spec.loader is not None

    spec.loader.exec_module(module)
    return module


def test_mapping_input_becomes_list_of_values():
    plugin = load_plugin()

    result = plugin.docker_services_canonical_volumes(
        volumes={
            "config": {
                "type": "bind",
                "source": "/host/config",
                "target": "/config",
                "read_only": False,
            },
            "media": {
                "type": "bind",
                "source": "/host/media",
                "target": "/media",
                "read_only": True,
            },
        }
    )

    assert result == [
        {
            "type": "bind",
            "source": "/host/config",
            "target": "/config",
            "read_only": False,
        },
        {
            "type": "bind",
            "source": "/host/media",
            "target": "/media",
            "read_only": True,
        },
    ]


def test_paths_fallback_builds_bind_volume():
    plugin = load_plugin()

    result = plugin.docker_services_canonical_volumes(
        paths_type="bind",
        paths_host="/host/path",
        paths_container="/container/path",
        paths_read_only="true",
    )

    assert result == [
        {
            "type": "bind",
            "source": "/host/path",
            "target": "/container/path",
            "read_only": True,
        }
    ]


def test_tmpfs_volume_is_canonicalized():
    plugin = load_plugin()

    result = plugin.docker_services_canonical_volumes(
        volumes=[
            {
                "type": "tmpfs",
                "target": "/tmp",
                "tmpfs": {
                    "size": "1048576",
                    "mode": 1777,
                },
            }
        ]
    )

    assert result == [
        {
            "type": "tmpfs",
            "target": "/tmp",
            "tmpfs": {
                "size": 1048576,
                "mode": 1777,
            },
        }
    ]


def test_append_preserves_existing_and_adds_new():
    plugin = load_plugin()

    existing = [
        {
            "type": "bind",
            "source": "/old",
            "target": "/old",
            "read_only": False,
        }
    ]

    result = plugin.docker_services_merge_volumes(
        existing,
        volumes=[
            {
                "type": "bind",
                "source": "/new",
                "target": "/new",
                "read_only": False,
            }
        ],
        action="append",
    )

    assert result == [
        {
            "type": "bind",
            "source": "/old",
            "target": "/old",
            "read_only": False,
        },
        {
            "type": "bind",
            "source": "/new",
            "target": "/new",
            "read_only": False,
        },
    ]


def test_replace_discards_existing():
    plugin = load_plugin()

    result = plugin.docker_services_merge_volumes(
        [
            {
                "type": "bind",
                "source": "/old",
                "target": "/old",
                "read_only": False,
            }
        ],
        volumes=[
            {
                "type": "bind",
                "source": "/new",
                "target": "/new",
                "read_only": False,
            }
        ],
        action="replace",
    )

    assert result == [
        {
            "type": "bind",
            "source": "/new",
            "target": "/new",
            "read_only": False,
        }
    ]


def test_append_unique_dedupes_exact_bind_duplicate():
    plugin = load_plugin()

    existing = [
        {
            "type": "bind",
            "source": "/same",
            "target": "/config",
            "read_only": False,
        }
    ]

    result = plugin.docker_services_merge_volumes(
        existing,
        volumes=[
            {
                "type": "bind",
                "source": "/same",
                "target": "/config",
                "read_only": True,
            }
        ],
        action="append_unique",
    )

    assert result == [
        {
            "type": "bind",
            "source": "/same",
            "target": "/config",
            "read_only": False,
        }
    ]


def test_append_unique_does_not_dedupe_same_target_different_source_for_bind():
    plugin = load_plugin()

    existing = [
        {
            "type": "bind",
            "source": "/app1",
            "target": "/config",
            "read_only": False,
        }
    ]

    result = plugin.docker_services_merge_volumes(
        existing,
        volumes=[
            {
                "type": "bind",
                "source": "/app2",
                "target": "/config",
                "read_only": False,
            }
        ],
        action="append_unique",
    )

    assert result == [
        {
            "type": "bind",
            "source": "/app1",
            "target": "/config",
            "read_only": False,
        },
        {
            "type": "bind",
            "source": "/app2",
            "target": "/config",
            "read_only": False,
        },
    ]


def test_append_unique_dedupes_tmpfs_by_target():
    plugin = load_plugin()

    existing = [
        {
            "type": "tmpfs",
            "target": "/tmp",
            "tmpfs": {
                "size": 1024,
            },
        }
    ]

    result = plugin.docker_services_merge_volumes(
        existing,
        volumes=[
            {
                "type": "tmpfs",
                "target": "/tmp",
                "tmpfs": {
                    "size": 2048,
                },
            }
        ],
        action="append_unique",
    )

    assert result == [
        {
            "type": "tmpfs",
            "target": "/tmp",
            "tmpfs": {
                "size": 1024,
            },
        }
    ]


def test_invalid_volume_type_fails():
    plugin = load_plugin()

    try:
        plugin.docker_services_canonical_volumes(
            volumes=[
                {
                    "type": "weird",
                    "source": "/host",
                    "target": "/container",
                }
            ]
        )
    except Exception as exc:
        assert "volumes[0].type must be one of" in str(exc)
    else:
        raise AssertionError("Expected invalid volume type to fail")


def test_missing_bind_source_fails():
    plugin = load_plugin()

    try:
        plugin.docker_services_canonical_volumes(
            volumes=[
                {
                    "type": "bind",
                    "target": "/container",
                }
            ]
        )
    except Exception as exc:
        assert "volumes[0].source is required" in str(exc)
    else:
        raise AssertionError("Expected missing source to fail")


def test_missing_target_fails():
    plugin = load_plugin()

    try:
        plugin.docker_services_canonical_volumes(
            volumes=[
                {
                    "type": "bind",
                    "source": "/host",
                }
            ]
        )
    except Exception as exc:
        assert "volumes[0].target is required" in str(exc)
    else:
        raise AssertionError("Expected missing target to fail")
