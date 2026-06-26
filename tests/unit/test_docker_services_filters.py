from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_PATH = REPO_ROOT / "ansible/filter_plugins/docker_services.py"


def load_plugin():
    spec = importlib.util.spec_from_file_location("docker_services_filters", PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)

    assert spec.loader is not None

    spec.loader.exec_module(module)
    return module


def test_effective_services_expands_targets():
    plugin = load_plugin()

    services = {
        "qbittorrent": {
            "enabled": True,
            "tags": ["torrents", "qbittorrent"],
            "targets": {
                "downloads": {
                    "name": "qbittorrent",
                    "tags": ["qbittorrent-main"],
                },
                "seeds": {
                    "name": "qbittorrent-xs",
                    "tags": ["qbittorrent-xs"],
                },
            },
        }
    }

    result = plugin.docker_services_effective(services)

    assert result == [
        {
            "name": "qbittorrent",
            "target": "downloads",
            "tags": ["qbittorrent", "torrents", "downloads", "qbittorrent-main"],
            "enabled": True,
        },
        {
            "name": "qbittorrent",
            "target": "seeds",
            "tags": ["qbittorrent", "torrents", "seeds", "qbittorrent-xs"],
            "enabled": True,
        },
    ]


def test_disabled_service_matches_but_is_not_selected():
    plugin = load_plugin()

    effective = [
        {
            "name": "mariadb",
            "tags": ["mariadb"],
            "enabled": False,
        }
    ]

    result = plugin.docker_services_select(
        effective,
        run_tags=["deploy", "mariadb"],
        run_all=False,
        allow_disabled=False,
    )

    assert result["matched"] == effective
    assert result["selected"] == []
    assert result["disabled_only"] is True


def test_disabled_service_can_be_selected_for_remove():
    plugin = load_plugin()

    effective = [
        {
            "name": "mariadb",
            "tags": ["mariadb"],
            "enabled": False,
        }
    ]

    result = plugin.docker_services_select(
        effective,
        run_tags=["remove", "mariadb"],
        run_all=False,
        allow_disabled=True,
    )

    assert result["matched"] == effective
    assert result["selected"] == effective
    assert result["disabled_only"] is False


def test_run_all_selects_enabled_only():
    plugin = load_plugin()

    effective = [
        {"name": "enabled_app", "tags": ["apps"], "enabled": True},
        {"name": "disabled_app", "tags": ["apps"], "enabled": False},
    ]

    result = plugin.docker_services_select(
        effective,
        run_tags=["deploy"],
        run_all=True,
        allow_disabled=False,
    )

    assert result["selected"] == [
        {"name": "enabled_app", "tags": ["apps"], "enabled": True},
    ]


def test_scalar_tags_are_normalized():
    plugin = load_plugin()

    services = {
        "homepage": {
            "enabled": True,
            "tags": "apps",
        }
    }

    result = plugin.docker_services_effective(services)

    assert result == [
        {
            "name": "homepage",
            "tags": ["homepage", "apps"],
            "enabled": True,
        }
    ]


def test_invalid_enabled_value_fails_fast():
    plugin = load_plugin()

    services = {
        "scraparr": {
            "enabled": "scraparr",
        }
    }

    try:
        plugin.docker_services_effective(services)
    except Exception as exc:
        assert "scraparr.enabled must be boolean-like" in str(exc)
    else:
        raise AssertionError("Expected invalid enabled value to fail")
