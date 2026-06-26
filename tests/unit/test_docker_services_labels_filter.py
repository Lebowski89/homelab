from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_PATH = REPO_ROOT / "ansible/roles/docker_services/filter_plugins/docker_services_labels.py"


def load_plugin():
    spec = importlib.util.spec_from_file_location("docker_services_labels", PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)

    assert spec.loader is not None

    spec.loader.exec_module(module)
    return module


def test_mapping_input_is_canonicalized():
    plugin = load_plugin()

    result = plugin.docker_services_canonical_labels(
        {
            " traefik.enable ": "true",
            "": "ignored",
            "com.example.number": 1,
        }
    )

    assert result == {
        "traefik.enable": "true",
        "com.example.number": 1,
    }


def test_sequence_input_parses_key_value_strings():
    plugin = load_plugin()

    result = plugin.docker_services_canonical_labels(
        [
            "traefik.enable=true",
            " traefik.http.routers.app.rule = Host(`app.example.com`) ",
            "ignored-without-equals",
            "=ignored-empty-key",
        ]
    )

    assert result == {
        "traefik.enable": "true",
        "traefik.http.routers.app.rule": "Host(`app.example.com`)",
    }


def test_sequence_duplicate_key_keeps_last_value():
    plugin = load_plugin()

    result = plugin.docker_services_canonical_labels(
        [
            "traefik.enable=false",
            "traefik.enable=true",
        ]
    )

    assert result == {
        "traefik.enable": "true",
    }


def test_append_new_wins_overwrites_existing_label():
    plugin = load_plugin()

    result = plugin.docker_services_merge_labels(
        {
            "traefik.enable": "false",
            "existing.only": "yes",
        },
        {
            "traefik.enable": "true",
            "new.only": "yes",
        },
        action="append",
        precedence="new_wins",
    )

    assert result == {
        "traefik.enable": "true",
        "existing.only": "yes",
        "new.only": "yes",
    }


def test_append_existing_wins_keeps_existing_label():
    plugin = load_plugin()

    result = plugin.docker_services_merge_labels(
        {
            "traefik.enable": "false",
            "existing.only": "yes",
        },
        {
            "traefik.enable": "true",
            "new.only": "yes",
        },
        action="append",
        precedence="existing_wins",
    )

    assert result == {
        "traefik.enable": "false",
        "new.only": "yes",
        "existing.only": "yes",
    }


def test_replace_discards_existing_labels():
    plugin = load_plugin()

    result = plugin.docker_services_merge_labels(
        {
            "old": "value",
        },
        {
            "new": "value",
        },
        action="replace",
        precedence="new_wins",
    )

    assert result == {
        "new": "value",
    }


def test_append_unique_adds_only_missing_keys():
    plugin = load_plugin()

    result = plugin.docker_services_merge_labels(
        {
            "traefik.enable": "false",
            "existing.only": "yes",
        },
        {
            "traefik.enable": "true",
            "new.only": "yes",
        },
        action="append_unique",
        precedence="new_wins",
    )

    assert result == {
        "traefik.enable": "false",
        "existing.only": "yes",
        "new.only": "yes",
    }


def test_recursive_merge_for_mapping_values_with_new_wins():
    plugin = load_plugin()

    result = plugin.docker_services_merge_labels(
        {
            "nested": {
                "old": "keep",
                "shared": "old",
            },
        },
        {
            "nested": {
                "shared": "new",
                "new": "add",
            },
        },
        action="append",
        precedence="new_wins",
    )

    assert result == {
        "nested": {
            "old": "keep",
            "shared": "new",
            "new": "add",
        },
    }


def test_invalid_action_fails():
    plugin = load_plugin()

    try:
        plugin.docker_services_merge_labels(
            {},
            {},
            action="merge",
            precedence="new_wins",
        )
    except Exception as exc:
        assert "labels_action must be one of" in str(exc)
    else:
        raise AssertionError("Expected invalid action to fail")


def test_invalid_precedence_fails():
    plugin = load_plugin()

    try:
        plugin.docker_services_merge_labels(
            {},
            {},
            action="append",
            precedence="sometimes",
        )
    except Exception as exc:
        assert "labels_precedence must be one of" in str(exc)
    else:
        raise AssertionError("Expected invalid precedence to fail")


def test_string_input_fails():
    plugin = load_plugin()

    try:
        plugin.docker_services_canonical_labels("traefik.enable=true")
    except Exception as exc:
        assert "labels must be a mapping or list" in str(exc)
    else:
        raise AssertionError("Expected string labels input to fail")
