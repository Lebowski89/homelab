from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_PATH = REPO_ROOT / "ansible/roles/docker_services/filter_plugins/docker_services_ports.py"


def load_plugin():
    spec = importlib.util.spec_from_file_location("docker_services_ports", PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)

    assert spec.loader is not None

    spec.loader.exec_module(module)
    return module


def test_mapping_input_becomes_list_of_values_for_swarm():
    plugin = load_plugin()

    result = plugin.docker_services_canonical_ports(
        ports={
            "web": {
                "target": "8080",
                "published": "80",
            },
            "dns": {
                "target": 53,
                "published": 53,
                "protocol": "udp",
                "mode": "host",
            },
        },
        stack_deploy_type="swarm",
    )

    assert result == [
        {
            "target": 8080,
            "published": 80,
            "protocol": "tcp",
            "mode": "ingress",
        },
        {
            "target": 53,
            "published": 53,
            "protocol": "udp",
            "mode": "host",
        },
    ]


def test_container_deploy_omits_mode():
    plugin = load_plugin()

    result = plugin.docker_services_canonical_ports(
        ports=[
            {
                "target": 8080,
                "published": 80,
                "protocol": "tcp",
                "mode": "host",
            }
        ],
        stack_deploy_type="container",
    )

    assert result == [
        {
            "target": 8080,
            "published": 80,
            "protocol": "tcp",
        }
    ]


def test_legacy_ports_fallback_builds_port():
    plugin = load_plugin()

    result = plugin.docker_services_canonical_ports(
        stack_deploy_type="swarm",
        ports_container="8090",
        ports_host="8090",
        ports_protocol="tcp",
        ports_mode="host",
    )

    assert result == [
        {
            "target": 8090,
            "published": 8090,
            "protocol": "tcp",
            "mode": "host",
        }
    ]


def test_append_preserves_existing_and_adds_new():
    plugin = load_plugin()

    existing = [
        {
            "target": 8080,
            "published": 80,
            "protocol": "tcp",
            "mode": "ingress",
        }
    ]

    result = plugin.docker_services_merge_ports(
        existing,
        ports=[
            {
                "target": 8443,
                "published": 443,
                "protocol": "tcp",
                "mode": "ingress",
            }
        ],
        action="append",
        stack_deploy_type="swarm",
    )

    assert result == [
        {
            "target": 8080,
            "published": 80,
            "protocol": "tcp",
            "mode": "ingress",
        },
        {
            "target": 8443,
            "published": 443,
            "protocol": "tcp",
            "mode": "ingress",
        },
    ]


def test_replace_discards_existing():
    plugin = load_plugin()

    result = plugin.docker_services_merge_ports(
        [
            {
                "target": 8080,
                "published": 80,
                "protocol": "tcp",
                "mode": "ingress",
            }
        ],
        ports=[
            {
                "target": 9090,
                "published": 9090,
            }
        ],
        action="replace",
        stack_deploy_type="swarm",
    )

    assert result == [
        {
            "target": 9090,
            "published": 9090,
            "protocol": "tcp",
            "mode": "ingress",
        }
    ]


def test_append_unique_dedupes_same_port_tuple():
    plugin = load_plugin()

    existing = [
        {
            "target": 8080,
            "published": 80,
            "protocol": "tcp",
            "mode": "ingress",
        }
    ]

    result = plugin.docker_services_merge_ports(
        existing,
        ports=[
            {
                "target": "8080",
                "published": "80",
                "protocol": "tcp",
                "mode": "ingress",
            }
        ],
        action="append_unique",
        stack_deploy_type="swarm",
    )

    assert result == [
        {
            "target": 8080,
            "published": 80,
            "protocol": "tcp",
            "mode": "ingress",
        }
    ]


def test_append_unique_keeps_same_port_with_different_protocol():
    plugin = load_plugin()

    existing = [
        {
            "target": 53,
            "published": 53,
            "protocol": "tcp",
            "mode": "ingress",
        }
    ]

    result = plugin.docker_services_merge_ports(
        existing,
        ports=[
            {
                "target": 53,
                "published": 53,
                "protocol": "udp",
                "mode": "ingress",
            }
        ],
        action="append_unique",
        stack_deploy_type="swarm",
    )

    assert result == [
        {
            "target": 53,
            "published": 53,
            "protocol": "tcp",
            "mode": "ingress",
        },
        {
            "target": 53,
            "published": 53,
            "protocol": "udp",
            "mode": "ingress",
        },
    ]


def test_existing_invalid_entries_are_ignored_like_old_jinja():
    plugin = load_plugin()

    result = plugin.docker_services_merge_ports(
        [
            {
                "target": 8080,
            },
            "not-a-dict",
        ],
        ports=[
            {
                "target": 9090,
                "published": 9090,
            }
        ],
        action="append",
        stack_deploy_type="swarm",
    )

    assert result == [
        {
            "target": 9090,
            "published": 9090,
            "protocol": "tcp",
            "mode": "ingress",
        }
    ]


def test_invalid_protocol_fails():
    plugin = load_plugin()

    try:
        plugin.docker_services_canonical_ports(
            ports=[
                {
                    "target": 8080,
                    "published": 80,
                    "protocol": "sctp",
                }
            ],
            stack_deploy_type="swarm",
        )
    except Exception as exc:
        assert "protocol must be one of" in str(exc)
    else:
        raise AssertionError("Expected invalid protocol to fail")


def test_missing_target_fails():
    plugin = load_plugin()

    try:
        plugin.docker_services_canonical_ports(
            ports=[
                {
                    "published": 80,
                }
            ],
            stack_deploy_type="swarm",
        )
    except Exception as exc:
        assert "must include both 'target' and 'published'" in str(exc)
    else:
        raise AssertionError("Expected missing target to fail")


def test_invalid_action_fails():
    plugin = load_plugin()

    try:
        plugin.docker_services_merge_ports(
            [],
            ports=[
                {
                    "target": 8080,
                    "published": 80,
                }
            ],
            action="merge-sort-of",
            stack_deploy_type="swarm",
        )
    except Exception as exc:
        assert "ports_action must be one of" in str(exc)
    else:
        raise AssertionError("Expected invalid action to fail")
