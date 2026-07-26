import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest
from ansible.errors import AnsibleFilterError

MODULE_PATH = Path(__file__).resolve().parents[2] / "ansible" / "filter_plugins" / "service_catalog.py"
spec = importlib.util.spec_from_file_location("service_catalog", MODULE_PATH)
service_catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service_catalog)


def test_missing_runtime_defaults_to_docker():
    items = service_catalog.service_catalog_effective({"app": {"enabled": True}})

    assert items == [
        {
            "name": "app",
            "tags": ["app"],
            "enabled": True,
            "runtime": "docker",
            "config": {"enabled": True},
        }
    ]


def test_explicit_podman_runtime():
    items = service_catalog.service_catalog_effective({"n8n": {"runtime": "podman", "tags": ["automation"]}})

    assert items[0]["runtime"] == "podman"
    assert items[0]["config"]["runtime"] == "podman"
    assert "automation" in items[0]["tags"]


def test_invalid_runtime_fails():
    with pytest.raises(AnsibleFilterError, match="must be one of"):
        service_catalog.service_catalog_effective({"bad": {"runtime": "containerd"}})


def test_mixed_runtime_selection_splits():
    items = service_catalog.service_catalog_effective({"app": {}, "n8n": {"runtime": "podman"}})
    selected = service_catalog.service_catalog_select(items, ["all"], run_all=True)["selected"]

    assert [item["name"] for item in service_catalog.service_catalog_by_runtime(selected, "docker")] == ["app"]
    assert [item["name"] for item in service_catalog.service_catalog_by_runtime(selected, "podman")] == ["n8n"]


@pytest.mark.parametrize(
    ("service_cfg", "target_name", "message"),
    [
        ("not-a-mapping", None, "expected service_cfg to be a mapping"),
        ({"targets": []}, "primary", "expected targets to be a mapping"),
        ({"targets": {"primary": []}}, "primary", "expected target .primary. to be a mapping"),
        ({"targets": {"primary": {}}}, "missing", "Available targets: primary"),
    ],
)
def test_merge_target_rejects_invalid_input(service_cfg, target_name, message):
    with pytest.raises(AnsibleFilterError, match=message):
        service_catalog.service_catalog_merge_target(service_cfg, target_name)


def test_merge_target_rejects_nested_targets():
    service_cfg = {
        "targets": {
            "primary": {
                "targets": {"nested": {}},
            }
        }
    }

    with pytest.raises(AnsibleFilterError, match="target .primary. must not contain nested targets"):
        service_catalog.service_catalog_merge_target(service_cfg, "primary")


def test_canonical_target_merge_contract():
    services = {
        "app": {
            "runtime": "docker",
            "enabled": True,
            "description": "base",
            "environment": {"BASE": "base", "SHARED": "base"},
            "secrets": ["base-secret", "shared-secret"],
            "command": ["base", "command"],
            "entrypoint": ["/base-entrypoint"],
            "healthcheck": {
                "test": ["CMD", "base"],
                "interval": "30s",
                "timeout": "5s",
            },
            "targets": {
                "primary": {
                    "runtime": "podman",
                    "description": "target",
                    "environment": {"SHARED": "target", "TARGET": "target"},
                    "secrets": ["shared-secret", "target-secret"],
                    "command": ["target", "command"],
                    "entrypoint": ["/target-entrypoint"],
                    "healthcheck": {"test": ["CMD", "target"]},
                }
            },
        }
    }

    item = service_catalog.service_catalog_effective(services)[0]
    config = item["config"]

    assert item["runtime"] == "podman"
    assert config["runtime"] == "podman"
    assert item["enabled"] is True
    assert config["description"] == "target"
    assert config["environment"] == {
        "BASE": "base",
        "SHARED": "target",
        "TARGET": "target",
    }
    assert config["secrets"] == ["base-secret", "shared-secret", "target-secret"]
    assert config["command"] == ["target", "command"]
    assert config["entrypoint"] == ["/target-entrypoint"]
    assert config["healthcheck"] == {
        "test": ["CMD", "target"],
        "interval": "30s",
        "timeout": "5s",
    }
    assert "targets" not in config


@pytest.mark.parametrize(
    ("base_enabled", "target_enabled", "expected"),
    [(True, True, True), (False, True, False), (True, False, False)],
)
def test_base_and_target_enabled_states_are_both_respected(base_enabled, target_enabled, expected):
    services = {
        "app": {
            "enabled": base_enabled,
            "targets": {"primary": {"enabled": target_enabled}},
        }
    }
    item = service_catalog.service_catalog_effective(services)[0]

    assert item["enabled"] is expected
    assert service_catalog.service_catalog_select([item], run_all=True)["selected"] == ([item] if expected else [])


def portable_target_fixture(runtime):
    shared_lookup = {"var": "shared", "path": "/App", "name": "SHARED"}
    return {
        "app": {
            "runtime": runtime,
            "image": "example/app:1.0.0",
            "environment": {"BASE": "base"},
            "infisical": {"secrets_map": [shared_lookup]},
            "secrets": ["shared-secret"],
            "volumes": [
                {"type": "bind", "source": "/srv/base", "target": "/base"},
            ],
            "paths": [{"path": "/srv/base", "state": "directory"}],
            "copies": [{"src": "base", "dest": "/srv/base/config"}],
            "ports": [{"published": 8080, "target": 80, "protocol": "tcp"}],
            "healthcheck": {"test": ["CMD", "base"], "interval": "30s"},
            "targets": {
                "primary": {
                    "environment": {"TARGET": "target"},
                    "infisical": {
                        "secrets_map": [
                            deepcopy(shared_lookup),
                            {"var": "api", "path": "/App", "name": "API"},
                        ]
                    },
                    "secrets": ["shared-secret", "target-secret"],
                    "volumes": [
                        {"type": "volume", "source": "target-data", "target": "/data"},
                    ],
                    "paths": [{"path": "/srv/target", "state": "directory"}],
                    "copies": [{"src": "target", "dest": "/srv/target/config"}],
                    "ports": [{"published": 8443, "target": 443, "protocol": "tcp"}],
                    "healthcheck": {"test": ["CMD", "target"]},
                }
            },
        }
    }


def test_runtime_choice_does_not_change_portable_target_expansion():
    docker = service_catalog.service_catalog_effective(portable_target_fixture("docker"))[0]["config"]
    podman = service_catalog.service_catalog_effective(portable_target_fixture("podman"))[0]["config"]

    docker_portable = {key: value for key, value in docker.items() if key != "runtime"}
    podman_portable = {key: value for key, value in podman.items() if key != "runtime"}

    assert docker_portable == podman_portable
    assert docker["environment"] == {"BASE": "base", "TARGET": "target"}
    assert [entry["var"] for entry in docker["infisical"]["secrets_map"]] == ["shared", "api"]
    assert docker["secrets"] == ["shared-secret", "target-secret"]
    assert [volume["source"] for volume in docker["volumes"]] == ["/srv/base", "target-data"]
    assert [path["path"] for path in docker["paths"]] == ["/srv/base", "/srv/target"]
    assert [copy["src"] for copy in docker["copies"]] == ["base", "target"]
    assert [port["published"] for port in docker["ports"]] == [8080, 8443]
    assert docker["healthcheck"] == {"test": ["CMD", "target"], "interval": "30s"}
    assert "targets" not in docker
    assert "targets" not in podman


def test_target_inherits_parent_runtime():
    items = service_catalog.service_catalog_effective({"svc": {"runtime": "podman", "targets": {"one": {}}}})

    assert items[0]["runtime"] == "podman"
    assert items[0]["config"]["runtime"] == "podman"
    assert "targets" not in items[0]["config"]


def test_disabled_podman_and_remove_selection():
    items = service_catalog.service_catalog_effective({"n8n": {"runtime": "podman", "enabled": False}})

    assert service_catalog.service_catalog_select(items, ["n8n"])["disabled_only"] is True
    assert service_catalog.service_catalog_select(items, ["n8n"], allow_disabled=True)["selected"][0]["name"] == "n8n"


def test_all_selection_selects_enabled_mixed_services():
    items = service_catalog.service_catalog_effective({"app": {}, "off": {"runtime": "podman", "enabled": False}})
    selected = service_catalog.service_catalog_select(items, run_all=True)["selected"]

    assert [item["name"] for item in selected] == ["app"]
