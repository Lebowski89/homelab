from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_PATH = REPO_ROOT / "ansible/roles/docker_services/filter_plugins/docker_services_list_fields.py"


def load_plugin():
    spec = importlib.util.spec_from_file_location("docker_services_list_fields", PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)

    assert spec.loader is not None

    spec.loader.exec_module(module)
    return module


def test_string_list_none_becomes_empty_list():
    plugin = load_plugin()

    assert plugin.docker_services_string_list(None) == []


def test_string_list_string_becomes_single_item_list():
    plugin = load_plugin()

    assert plugin.docker_services_string_list(" NET_ADMIN ") == ["NET_ADMIN"]


def test_string_list_empty_string_is_removed():
    plugin = load_plugin()

    assert plugin.docker_services_string_list("   ") == []


def test_string_list_sequence_is_trimmed_and_empty_items_removed():
    plugin = load_plugin()

    result = plugin.docker_services_string_list(
        [
            " NET_ADMIN ",
            "",
            None,
            " SYS_ADMIN ",
            "   ",
        ]
    )

    assert result == [
        "NET_ADMIN",
        "None",
        "SYS_ADMIN",
    ]


def test_string_list_mapping_uses_values():
    plugin = load_plugin()

    result = plugin.docker_services_string_list(
        {
            "first": " /dev/dri:/dev/dri ",
            "second": "/dev/net/tun:/dev/net/tun",
            "empty": "",
        }
    )

    assert result == [
        "/dev/dri:/dev/dri",
        "/dev/net/tun:/dev/net/tun",
    ]


def test_merge_string_list_append():
    plugin = load_plugin()

    result = plugin.docker_services_merge_string_list(
        ["NET_ADMIN"],
        ["SYS_ADMIN"],
        "append",
    )

    assert result == [
        "NET_ADMIN",
        "SYS_ADMIN",
    ]


def test_merge_string_list_replace():
    plugin = load_plugin()

    result = plugin.docker_services_merge_string_list(
        ["NET_ADMIN"],
        ["SYS_ADMIN"],
        "replace",
    )

    assert result == [
        "SYS_ADMIN",
    ]


def test_merge_string_list_append_unique_keeps_first_occurrence():
    plugin = load_plugin()

    result = plugin.docker_services_merge_string_list(
        ["NET_ADMIN", "SYS_ADMIN"],
        ["NET_ADMIN", "CHOWN"],
        "append_unique",
    )

    assert result == [
        "NET_ADMIN",
        "SYS_ADMIN",
        "CHOWN",
    ]


def test_merge_string_list_default_action_is_append():
    plugin = load_plugin()

    result = plugin.docker_services_merge_string_list(
        ["one"],
        ["two"],
    )

    assert result == [
        "one",
        "two",
    ]


def test_merge_string_list_invalid_action_fails():
    plugin = load_plugin()

    try:
        plugin.docker_services_merge_string_list([], [], "merge")
    except Exception as exc:
        assert "list field action must be one of" in str(exc)
    else:
        raise AssertionError("Expected invalid action to fail")


def test_set_service_field_creates_service_when_missing():
    plugin = load_plugin()

    result = plugin.docker_services_set_service_field(
        {},
        "qbittorrent",
        "devices",
        ["/dev/net/tun:/dev/net/tun"],
    )

    assert result == {
        "qbittorrent": {
            "devices": ["/dev/net/tun:/dev/net/tun"],
        },
    }


def test_set_service_field_preserves_existing_service_keys():
    plugin = load_plugin()

    result = plugin.docker_services_set_service_field(
        {
            "qbittorrent": {
                "image": "ghcr.io/hotio/qbittorrent:latest",
                "environment": {
                    "PUID": "1000",
                },
            },
        },
        "qbittorrent",
        "cap_add",
        ["NET_ADMIN"],
    )

    assert result == {
        "qbittorrent": {
            "image": "ghcr.io/hotio/qbittorrent:latest",
            "environment": {
                "PUID": "1000",
            },
            "cap_add": ["NET_ADMIN"],
        },
    }


def test_set_service_field_replaces_existing_field():
    plugin = load_plugin()

    result = plugin.docker_services_set_service_field(
        {
            "plex": {
                "tmpfs": ["/old"],
            },
        },
        "plex",
        "tmpfs",
        ["/transcode"],
    )

    assert result == {
        "plex": {
            "tmpfs": ["/transcode"],
        },
    }


def test_set_service_field_preserves_other_services():
    plugin = load_plugin()

    result = plugin.docker_services_set_service_field(
        {
            "plex": {
                "image": "plex",
            },
            "qbittorrent": {
                "image": "qbittorrent",
            },
        },
        "plex",
        "devices",
        ["/dev/dri:/dev/dri"],
    )

    assert result == {
        "plex": {
            "image": "plex",
            "devices": ["/dev/dri:/dev/dri"],
        },
        "qbittorrent": {
            "image": "qbittorrent",
        },
    }


def test_set_service_field_empty_service_name_fails():
    plugin = load_plugin()

    try:
        plugin.docker_services_set_service_field({}, "", "devices", [])
    except Exception as exc:
        assert "service_name must be a non-empty string" in str(exc)
    else:
        raise AssertionError("Expected empty service name to fail")


def test_set_service_field_empty_field_name_fails():
    plugin = load_plugin()

    try:
        plugin.docker_services_set_service_field({}, "plex", "", [])
    except Exception as exc:
        assert "field_name must be a non-empty string" in str(exc)
    else:
        raise AssertionError("Expected empty field name to fail")


def test_set_service_field_non_mapping_compose_services_fails():
    plugin = load_plugin()

    try:
        plugin.docker_services_set_service_field([], "plex", "devices", [])
    except Exception as exc:
        assert "compose_services must be a mapping" in str(exc)
    else:
        raise AssertionError("Expected non-mapping compose_services to fail")


def test_set_service_field_non_mapping_existing_service_fails():
    plugin = load_plugin()

    try:
        plugin.docker_services_set_service_field(
            {
                "plex": "not-a-dict",
            },
            "plex",
            "devices",
            [],
        )
    except Exception as exc:
        assert "compose_services['plex'] must be a mapping" in str(exc)
    else:
        raise AssertionError("Expected non-mapping existing service to fail")


def test_no_new_privileges_true_appends_unique_security_option():
    plugin = load_plugin()

    canonical = plugin.docker_services_no_new_privileges_security_opts(True, "container")
    result = plugin.docker_services_merge_string_list(
        ["label=disable", "no-new-privileges:true"],
        canonical,
        "append_unique",
    )

    assert result == ["label=disable", "no-new-privileges:true"]


def test_no_new_privileges_false_leaves_existing_security_options_unchanged():
    plugin = load_plugin()

    canonical = plugin.docker_services_no_new_privileges_security_opts(False, "container")
    result = plugin.docker_services_merge_string_list(["label=disable"], canonical, "append_unique")

    assert result == ["label=disable"]


@pytest.mark.parametrize("value", ["maybe", 2, None, [], {}])
def test_no_new_privileges_rejects_non_strict_boolean_values(value):
    plugin = load_plugin()

    with pytest.raises(Exception, match="must be boolean-like"):
        plugin.docker_services_no_new_privileges_security_opts(value, "container")


def test_no_new_privileges_true_is_rejected_for_swarm():
    plugin = load_plugin()

    with pytest.raises(Exception, match="only supported for Docker container deploys, not Swarm"):
        plugin.docker_services_no_new_privileges_security_opts(True, "swarm")
