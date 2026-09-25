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
    assert items[0]["podman_lifecycle"] == {
        "container_name": "n8n",
        "namespace_provider": None,
        "execution_mode": "rootful",
    }


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
            "podman_lifecycle": {
                "container_name": "app-primary",
                "namespace_provider": None,
                "execution_mode": "rootful",
            },
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


def test_missing_and_null_targets_are_base_only_services():
    missing = {"app": {"runtime": "docker"}}
    explicit_null = {"app": {"runtime": "docker", "targets": None}}

    assert service_catalog.service_catalog_effective(missing, "manager") == (
        service_catalog.service_catalog_effective(explicit_null, "manager")
    )


def test_explicit_empty_targets_are_rejected_clearly():
    services = {"empty_app": {"runtime": "docker", "targets": {}}}

    with pytest.raises(
        AnsibleFilterError,
        match=r"empty_app\.targets must contain at least one target; omit targets for a base-only service",
    ):
        service_catalog.service_catalog_effective(services, "manager")


def test_empty_targets_cannot_bypass_runtime_or_systemd_validation():
    with pytest.raises(AnsibleFilterError, match=r"invalid\.runtime must be one of"):
        service_catalog.service_catalog_effective(
            {"invalid": {"runtime": "containerd", "targets": {}}},
            "manager",
        )

    with pytest.raises(AnsibleFilterError, match=r"systemd.*valid only with runtime: podman"):
        service_catalog.service_catalog_effective(
            {
                "invalid_systemd": {
                    "runtime": "docker",
                    "systemd": {"restart": "on-failure"},
                    "targets": {},
                }
            },
            "manager",
        )


def test_canonical_target_merge_preserves_explicit_name_without_inventing_defaults():
    service = {
        "runtime": "podman",
        "image": "example.invalid/app:1.0.0",
        "targets": {
            "defaulted": {},
            "renamed": {"name": "custom-target"},
        },
    }

    base = service_catalog.service_catalog_merge_target(service)
    defaulted = service_catalog.service_catalog_merge_target(service, "defaulted")
    renamed = service_catalog.service_catalog_merge_target(service, "renamed")

    assert "name" not in base
    assert "name" not in defaulted
    assert renamed["name"] == "custom-target"


def podman_namespace_fixture():
    return {
        "downloader": {
            "runtime": "podman",
            "network_mode": "container:vpn-runtime",
            "deploy": {"host": "node-a", "execution": {"mode": "rootful"}},
        },
        "docker-app": {
            "runtime": "docker",
            "name": "vpn-runtime",
            "deploy": {"type": "container", "host": "docker-node"},
        },
        "vpn": {
            "runtime": "podman",
            "name": "vpn-runtime",
            "deploy": {"host": "node-a", "execution": {"mode": "rootful"}},
        },
        "browser": {
            "runtime": "podman",
            "network_mode": "container:vpn-runtime",
            "deploy": {"host": "node-a", "execution": {"mode": "rootful"}},
        },
        "unrelated": {
            "runtime": "podman",
            "deploy": {"host": "node-b", "execution": {"mode": "rootful"}},
        },
    }


def lifecycle_plan(services, *, selected_names=None, action="recreate"):
    items = service_catalog.service_catalog_effective(services, "manager")
    selected = items if selected_names is None else [item for item in items if item["name"] in selected_names]
    return service_catalog.service_catalog_podman_lifecycle_plan(items, selected, action)


def test_podman_namespace_planner_uses_only_lightweight_catalog_metadata(monkeypatch):
    services = podman_namespace_fixture()
    items = service_catalog.service_catalog_effective(services, "manager")
    selected = service_catalog.service_catalog_select(items, ["vpn"])["selected"]

    def reject_materialization(*_args, **_kwargs):
        raise AssertionError("lifecycle planning must not materialize service configurations")

    monkeypatch.setattr(service_catalog, "service_catalog_merge_target", reject_materialization)

    plan = service_catalog.service_catalog_podman_lifecycle_plan(items, selected, "recreate")

    assert [item["name"] for item in plan["selected"]] == ["vpn"]
    assert [item["name"] for item in plan["selected"][0]["podman_lifecycle"]["namespace_dependents"]] == [
        "downloader",
        "browser",
    ]


def test_podman_namespace_plan_derives_edges_and_orders_provider_before_two_consumers():
    plan = lifecycle_plan(podman_namespace_fixture())

    assert plan["dependencies"] == [
        {"consumer": "downloader", "provider": "vpn", "host": "node-a"},
        {"consumer": "browser", "provider": "vpn", "host": "node-a"},
    ]
    assert [item["name"] for item in plan["selected"]] == [
        "vpn",
        "docker-app",
        "downloader",
        "browser",
        "unrelated",
    ]
    assert plan["selected"][0]["podman_lifecycle"]["namespace_dependents"] == [
        {
            "name": "downloader",
            "container_name": "downloader",
            "unit_name": "downloader.service",
            "dispatch_host": "node-a",
        },
        {
            "name": "browser",
            "container_name": "browser",
            "unit_name": "browser.service",
            "dispatch_host": "node-a",
        },
    ]
    assert "podman_lifecycle" not in plan["selected"][1]


def test_provider_only_recreate_quiesces_both_consumers_without_selecting_unrelated_services():
    plan = lifecycle_plan(podman_namespace_fixture(), selected_names={"vpn"})
    provider = plan["selected"][0]
    dependents = provider["podman_lifecycle"]["namespace_dependents"]

    assert [item["name"] for item in plan["selected"]] == ["vpn"]
    assert [item["name"] for item in dependents] == ["downloader", "browser"]
    operation_order = (
        [f"stop {item['name']}" for item in reversed(dependents)] + ["restart vpn"] + [f"start {item['name']}" for item in dependents]
    )
    assert operation_order == [
        "stop browser",
        "stop downloader",
        "restart vpn",
        "start downloader",
        "start browser",
    ]


def test_consumer_only_recreate_does_not_select_or_restart_provider():
    plan = lifecycle_plan(podman_namespace_fixture(), selected_names={"browser"})

    assert [item["name"] for item in plan["selected"]] == ["browser"]
    assert plan["selected"][0]["podman_lifecycle"]["namespace_dependents"] == []


def test_transitive_namespace_dependencies_use_reverse_stop_and_forward_restore_order():
    services = {
        "leaf": {
            "runtime": "podman",
            "network_mode": "container:middle-runtime",
            "deploy": {"host": "node-a"},
        },
        "sibling": {
            "runtime": "podman",
            "network_mode": "container:root-runtime",
            "deploy": {"host": "node-a"},
        },
        "middle": {
            "runtime": "podman",
            "name": "middle-runtime",
            "network_mode": "container:root-runtime",
            "deploy": {"host": "node-a"},
        },
        "root": {
            "runtime": "podman",
            "name": "root-runtime",
            "deploy": {"host": "node-a"},
        },
    }
    plan = lifecycle_plan(services, selected_names={"root"})
    dependents = plan["selected"][0]["podman_lifecycle"]["namespace_dependents"]
    forward = [item["name"] for item in dependents]
    reverse = list(reversed(forward))

    assert forward.index("middle") < forward.index("leaf")
    assert forward.index("sibling") >= 0
    assert reverse.index("leaf") < reverse.index("middle")


def test_remove_requires_complete_dependent_closure_and_orders_consumers_first():
    services = podman_namespace_fixture()

    with pytest.raises(AnsibleFilterError, match=r"Cannot remove.*vpn.*downloader, browser"):
        lifecycle_plan(services, selected_names={"vpn"}, action="remove")

    plan = lifecycle_plan(services, selected_names={"vpn", "downloader", "browser"}, action="remove")
    assert [item["name"] for item in plan["selected"]] == ["downloader", "browser", "vpn"]

    full_plan = lifecycle_plan(services, action="remove")
    assert [item["name"] for item in full_plan["selected"]] == [
        "downloader",
        "docker-app",
        "browser",
        "vpn",
        "unrelated",
    ]


def test_unmanaged_container_namespace_reference_remains_external():
    services = {
        "consumer": {
            "runtime": "podman",
            "network_mode": "container:external-runtime",
            "deploy": {"host": "node-a"},
        }
    }

    plan = lifecycle_plan(services)

    assert plan["dependencies"] == []
    assert plan["selected"][0]["podman_lifecycle"]["namespace_dependents"] == []


def test_docker_service_with_matching_name_is_not_a_podman_namespace_provider():
    services = {
        "docker-provider": {
            "runtime": "docker",
            "name": "shared-runtime",
            "deploy": {"type": "container", "host": "docker-node"},
        },
        "consumer": {
            "runtime": "podman",
            "network_mode": "container:shared-runtime",
            "deploy": {"host": "node-a"},
        },
    }

    plan = lifecycle_plan(services)

    assert plan["dependencies"] == []
    assert [item["name"] for item in plan["selected"]] == ["docker-provider", "consumer"]
    assert "podman_lifecycle" not in plan["selected"][0]


def test_podman_namespace_self_dependency_is_rejected():
    services = {
        "loop": {
            "runtime": "podman",
            "name": "loop-runtime",
            "network_mode": "container:loop-runtime",
            "deploy": {"host": "node-a"},
        }
    }

    with pytest.raises(AnsibleFilterError, match="must not depend on its own"):
        lifecycle_plan(services)


def test_podman_namespace_dependency_cycle_is_rejected():
    services = {
        "alpha": {
            "runtime": "podman",
            "name": "alpha-runtime",
            "network_mode": "container:beta-runtime",
            "deploy": {"host": "node-a"},
        },
        "beta": {
            "runtime": "podman",
            "name": "beta-runtime",
            "network_mode": "container:alpha-runtime",
            "deploy": {"host": "node-a"},
        },
    }

    with pytest.raises(AnsibleFilterError, match="dependency cycle detected: alpha, beta"):
        lifecycle_plan(services)


def test_cross_host_managed_namespace_dependency_is_rejected():
    services = {
        "provider": {
            "runtime": "podman",
            "name": "provider-runtime",
            "deploy": {"host": "node-a"},
        },
        "consumer": {
            "runtime": "podman",
            "network_mode": "container:provider-runtime",
            "deploy": {"host": "node-b"},
        },
    }

    with pytest.raises(AnsibleFilterError, match=r"host-local.*provider-runtime.*provider on node-a"):
        lifecycle_plan(services)


def test_rootless_container_namespace_restriction_is_preserved_by_planner():
    services = {
        "consumer": {
            "runtime": "podman",
            "network_mode": "container:external-runtime",
            "deploy": {"host": "node-a", "execution": {"mode": "rootless"}},
        }
    }

    with pytest.raises(AnsibleFilterError, match="requires rootful Podman.*rootless"):
        lifecycle_plan(services)
