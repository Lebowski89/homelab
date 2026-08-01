import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest
from ansible.errors import AnsibleFilterError

MODULE_PATH = Path(__file__).resolve().parents[2] / "ansible" / "filter_plugins" / "service_catalog.py"
spec = importlib.util.spec_from_file_location("service_catalog", MODULE_PATH)
service_catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service_catalog)


def test_missing_base_runtime_is_rejected():
    with pytest.raises(AnsibleFilterError, match="Service 'app' must explicitly declare runtime"):
        service_catalog.service_catalog_effective({"app": {"enabled": True}}, "manager")


@pytest.mark.parametrize("runtime", ["", "   ", None, 1, [], {}])
def test_empty_null_and_non_string_base_runtimes_are_rejected(runtime):
    with pytest.raises(AnsibleFilterError, match=r"app\.runtime must be a non-empty string"):
        service_catalog.service_catalog_effective({"app": {"runtime": runtime}}, "manager")


def test_explicit_podman_runtime():
    items = service_catalog.service_catalog_effective({"n8n": {"runtime": "podman", "tags": ["automation"]}}, "manager")

    assert items[0]["runtime"] == "podman"
    assert items[0]["dispatch_host"] == "n8n"
    assert "config" not in items[0]
    assert "automation" in items[0]["tags"]


def test_effective_target_entry_contains_only_selection_metadata():
    items = service_catalog.service_catalog_effective(
        {
            "app": {
                "runtime": "docker",
                "tags": ["base"],
                "targets": {
                    "primary": {
                        "runtime": "podman",
                        "tags": ["target"],
                    }
                },
            }
        },
        "manager",
    )

    assert items == [
        {
            "name": "app",
            "target": "primary",
            "runtime": "podman",
            "tags": ["app", "base", "primary", "target"],
            "enabled": True,
            "dispatch_host": "app",
        }
    ]


def test_invalid_runtime_fails():
    for runtime in ("containerd", "Docker", " docker"):
        with pytest.raises(AnsibleFilterError, match="must be one of"):
            service_catalog.service_catalog_effective({"bad": {"runtime": runtime}}, "manager")


def test_mixed_runtime_selection_splits():
    items = service_catalog.service_catalog_effective(
        {"app": {"runtime": "docker"}, "n8n": {"runtime": "podman"}},
        "manager",
    )
    selected = service_catalog.service_catalog_select(items, ["all"], run_all=True)["selected"]

    assert [item["name"] for item in service_catalog.service_catalog_by_runtime(selected, "docker")] == ["app"]
    assert [item["name"] for item in service_catalog.service_catalog_by_runtime(selected, "podman")] == ["n8n"]


def test_selection_and_runtime_partition_do_not_default_missing_metadata_runtime():
    item = {"name": "app", "tags": ["app"], "enabled": True}

    with pytest.raises(AnsibleFilterError, match=r"app\.runtime must be a non-empty string"):
        service_catalog.service_catalog_select([item], run_all=True)
    with pytest.raises(AnsibleFilterError, match=r"app\.runtime must be a non-empty string"):
        service_catalog.service_catalog_by_runtime([item], "docker")


@pytest.mark.parametrize(
    ("service_cfg", "target_name", "message"),
    [
        ("not-a-mapping", None, "expected service_cfg to be a mapping"),
        ({"runtime": "docker", "targets": []}, "primary", "expected targets to be a mapping"),
        ({"runtime": "docker", "targets": {"primary": []}}, "primary", "expected target .primary. to be a mapping"),
        ({"runtime": "docker", "targets": {"primary": {}}}, "missing", "Available targets: primary"),
    ],
)
def test_merge_target_rejects_invalid_input(service_cfg, target_name, message):
    with pytest.raises(AnsibleFilterError, match=message):
        service_catalog.service_catalog_merge_target(service_cfg, target_name)


def test_merge_target_rejects_nested_targets():
    service_cfg = {
        "runtime": "docker",
        "targets": {
            "primary": {
                "targets": {"nested": {}},
            }
        },
    }

    with pytest.raises(AnsibleFilterError, match="target .primary. must not contain nested targets"):
        service_catalog.service_catalog_merge_target(service_cfg, "primary")

    with pytest.raises(AnsibleFilterError, match="app.targets.primary must not contain nested targets"):
        service_catalog.service_catalog_effective({"app": service_cfg}, "manager")


def test_merge_target_enforces_explicit_base_and_target_runtimes():
    with pytest.raises(AnsibleFilterError, match="base service must explicitly declare runtime"):
        service_catalog.service_catalog_merge_target({})
    with pytest.raises(AnsibleFilterError, match=r"service_cfg\.runtime must be one of"):
        service_catalog.service_catalog_merge_target({"runtime": "containerd"})
    with pytest.raises(AnsibleFilterError, match="target 'primary'.runtime must be one of"):
        service_catalog.service_catalog_merge_target(
            {"runtime": "docker", "targets": {"primary": {"runtime": "containerd"}}},
            "primary",
        )


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

    item = service_catalog.service_catalog_effective(services, "manager")[0]
    config = service_catalog.service_catalog_merge_target(services["app"], item["target"])

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
            "runtime": "docker",
            "enabled": base_enabled,
            "targets": {"primary": {"enabled": target_enabled}},
        }
    }
    item = service_catalog.service_catalog_effective(services, "manager")[0]

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
    docker_services = portable_target_fixture("docker")
    podman_services = portable_target_fixture("podman")
    docker_item = service_catalog.service_catalog_by_runtime(
        service_catalog.service_catalog_select(
            service_catalog.service_catalog_effective(docker_services, "manager"),
            run_all=True,
        )["selected"],
        "docker",
    )[0]
    podman_item = service_catalog.service_catalog_by_runtime(
        service_catalog.service_catalog_select(
            service_catalog.service_catalog_effective(podman_services, "manager"),
            run_all=True,
        )["selected"],
        "podman",
    )[0]
    docker = service_catalog.service_catalog_merge_target(docker_services["app"], docker_item["target"])
    podman = service_catalog.service_catalog_merge_target(podman_services["app"], podman_item["target"])

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
    items = service_catalog.service_catalog_effective({"svc": {"runtime": "podman", "targets": {"one": {}}}}, "manager")

    assert items[0]["runtime"] == "podman"
    assert items[0]["dispatch_host"] == "svc"
    assert "config" not in items[0]
    merged = service_catalog.service_catalog_merge_target(
        {"runtime": "podman", "targets": {"one": {}}},
        "one",
    )
    assert merged["runtime"] == "podman"
    assert "targets" not in merged


def test_valid_target_runtime_override_is_allowed():
    services = {
        "svc": {
            "runtime": "docker",
            "targets": {"portable": {"runtime": "podman"}},
        }
    }

    assert service_catalog.service_catalog_effective(services, "manager")[0]["runtime"] == "podman"


def test_top_level_systemd_is_valid_only_for_effective_podman_services():
    podman_cfg = {"runtime": "podman", "systemd": {"restart": "on-failure"}}
    docker_cfg = {"runtime": "docker", "systemd": {"restart": "on-failure"}}

    assert service_catalog.service_catalog_effective({"app": podman_cfg}, "manager")[0]["runtime"] == "podman"
    assert service_catalog.service_catalog_merge_target(podman_cfg)["systemd"] == {"restart": "on-failure"}
    with pytest.raises(AnsibleFilterError, match=r"Service 'app'.*valid only with runtime: podman.*runtime: docker"):
        service_catalog.service_catalog_effective({"app": docker_cfg}, "manager")
    with pytest.raises(AnsibleFilterError, match=r"effective service.*valid only with runtime: podman"):
        service_catalog.service_catalog_merge_target(docker_cfg)


def test_target_systemd_merges_recursively_without_mutating_source():
    service = {
        "runtime": "podman",
        "systemd": {
            "after": ["network-online.target"],
            "restart": "on-failure",
            "restart_sec": "15s",
        },
        "targets": {
            "worker": {
                "systemd": {
                    "restart": "always",
                }
            }
        },
    }
    original = deepcopy(service)

    merged = service_catalog.service_catalog_merge_target(service, "worker")

    assert merged["systemd"] == {
        "after": ["network-online.target"],
        "restart": "always",
        "restart_sec": "15s",
    }
    assert service == original


def test_target_switching_to_docker_cannot_inherit_podman_systemd_policy():
    service = {
        "runtime": "podman",
        "systemd": {"restart": "on-failure"},
        "targets": {"docker": {"runtime": "docker"}},
    }

    with pytest.raises(AnsibleFilterError, match=r"target 'docker'.*runtime: docker"):
        service_catalog.service_catalog_effective({"app": service}, "manager")
    with pytest.raises(AnsibleFilterError, match=r"target 'docker'.*runtime: docker"):
        service_catalog.service_catalog_merge_target(service, "docker")


@pytest.mark.parametrize("runtime", ["", None, 1, "containerd"])
def test_invalid_target_runtime_override_is_rejected(runtime):
    services = {
        "svc": {
            "runtime": "docker",
            "targets": {"invalid": {"runtime": runtime}},
        }
    }

    with pytest.raises(AnsibleFilterError, match=r"svc\.targets\.invalid\.runtime must"):
        service_catalog.service_catalog_effective(services, "manager")


def test_disabled_podman_and_remove_selection():
    items = service_catalog.service_catalog_effective({"n8n": {"runtime": "podman", "enabled": False}}, "manager")

    assert service_catalog.service_catalog_select(items, ["n8n"])["disabled_only"] is True
    assert service_catalog.service_catalog_select(items, ["n8n"], allow_disabled=True)["selected"][0]["name"] == "n8n"


def test_all_selection_selects_enabled_mixed_services():
    items = service_catalog.service_catalog_effective(
        {
            "app": {"runtime": "docker"},
            "off": {"runtime": "podman", "enabled": False},
        },
        "manager",
    )
    selected = service_catalog.service_catalog_select(items, run_all=True)["selected"]

    assert [item["name"] for item in selected] == ["app"]


def test_dispatch_host_selection_uses_runtime_orchestration_host():
    items = service_catalog.service_catalog_effective(
        {
            "swarm": {"runtime": "docker", "deploy": {"type": "swarm", "host": "filesystem"}},
            "standalone": {
                "runtime": "docker",
                "deploy": {"type": "container", "host": "docker-vm"},
            },
            "standalone-empty": {
                "runtime": "docker",
                "deploy": {"type": "container", "host": ""},
            },
            "podman": {"runtime": "podman", "deploy": {"host": "podman-vm"}},
            "legacy-podman": {
                "runtime": "podman",
                "deploy": {"host": ""},
                "container": {"host": "legacy-vm"},
            },
            "default-podman": {
                "runtime": "podman",
                "deploy": {"host": ""},
                "container": {"host": ""},
            },
        },
        "manager",
    )
    by_name = {item["name"]: item for item in items}

    assert by_name["swarm"]["dispatch_host"] == "manager"
    assert by_name["standalone"]["dispatch_host"] == "docker-vm"
    assert by_name["standalone-empty"]["dispatch_host"] == "manager"
    assert by_name["podman"]["dispatch_host"] == "podman-vm"
    assert by_name["legacy-podman"]["dispatch_host"] == "legacy-vm"
    assert by_name["default-podman"]["dispatch_host"] == "default-podman"


def test_target_runtime_and_deploy_override_select_dispatch_host():
    items = service_catalog.service_catalog_effective(
        {
            "app": {
                "runtime": "docker",
                "deploy": {"type": "swarm", "host": "filesystem"},
                "targets": {
                    "podman": {"runtime": "podman", "deploy": {"host": "podman-vm"}},
                    "standalone": {"deploy": {"type": "container", "host": "docker-vm"}},
                },
            }
        },
        "manager",
    )
    by_target = {item["target"]: item for item in items}

    assert by_target["podman"]["dispatch_host"] == "podman-vm"
    assert by_target["standalone"]["dispatch_host"] == "docker-vm"


def test_catalog_requires_configured_docker_manager():
    with pytest.raises(AnsibleFilterError, match="docker_manager must be a non-empty string"):
        service_catalog.service_catalog_effective({"app": {"runtime": "docker"}}, "")


def test_catalog_order_and_source_are_unchanged_by_runtime_validation():
    services = {
        "first": {"runtime": "docker", "tags": ["one"]},
        "second": {"runtime": "podman", "tags": ["two"]},
    }
    original = deepcopy(services)

    items = service_catalog.service_catalog_effective(services, "manager")

    assert [item["name"] for item in items] == ["first", "second"]
    assert services == original
