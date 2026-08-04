import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest
from ansible.errors import AnsibleFilterError

MODULE_PATH = Path(__file__).resolve().parents[2] / "ansible" / "roles" / "podman_services" / "filter_plugins" / "podman_services.py"
spec = importlib.util.spec_from_file_location("podman_services", MODULE_PATH)
podman_services = importlib.util.module_from_spec(spec)
spec.loader.exec_module(podman_services)


def valid_cfg():
    return {
        "runtime": "podman",
        "image": "docker.io/n8nio/n8n:2.31.4",
        "ports": [{"published": 5678, "target": 5678}],
        "paths": [{"path": "/opt/n8n"}],
    }


def test_normalize_accepts_n8n_like_service():
    svc = podman_services.podman_service_normalize(valid_cfg(), "n8n")
    assert svc["image"] == "docker.io/n8nio/n8n:2.31.4"
    assert svc["secrets"] == []


@pytest.mark.parametrize("image", ["docker.io/n8nio/n8n:latest", "docker.io/n8nio/n8n", ""])
def test_image_must_be_exact_non_latest(image):
    cfg = valid_cfg()
    cfg["image"] = image
    with pytest.raises(AnsibleFilterError, match="exact, non-latest"):
        podman_services.podman_service_normalize(cfg, "n8n")


def test_unsafe_path_fails():
    cfg = valid_cfg()
    cfg["paths"] = [{"path": "/root/.ssh"}]
    with pytest.raises(AnsibleFilterError, match="/opt"):
        podman_services.podman_service_normalize(cfg, "n8n")


def test_bad_secret_fails():
    cfg = valid_cfg()
    cfg["secrets"] = [{"name": "x"}]
    with pytest.raises(AnsibleFilterError, match="not supported by Podman"):
        podman_services.podman_service_normalize(cfg, "n8n")


def test_canonical_value_free_secret_attachments_are_adapter_metadata():
    cfg = valid_cfg()
    cfg["secrets"] = ["generated_secret", "canonical_secret"]
    original = deepcopy(cfg)

    svc = podman_services.podman_service_normalize(cfg, "n8n")

    assert svc["secrets"] == []
    assert svc["secret_attachments"] == ["generated_secret", "canonical_secret"]
    assert cfg == original


def test_deprecated_secret_runtime_options_are_rejected():
    declarations = [
        {
            "name": "n8n_encryption_key_secret",
            "var": "n8n_encryption_key",
            "target": "/run/secrets/n8n_encryption_key_secret",
            "runtime_options": {"podman": {"immutable": True, "replace": True}},
        }
    ]
    with pytest.raises(AnsibleFilterError, match=r"runtime_options is deprecated; use secret.update_policy"):
        podman_services.podman_secret_declarations(declarations)


@pytest.mark.parametrize("value", [None, True, False, 0, 1, [], {}, "", " preserve", "Preserve"])
def test_podman_declaration_rejects_invalid_update_policy(value):
    declaration = {
        "name": "portable_secret",
        "var": "portable_secret",
        "target": "/run/secrets/portable_secret",
        "update_policy": value,
    }

    with pytest.raises(AnsibleFilterError, match="update_policy"):
        podman_services.podman_secret_declarations([declaration])


def test_volume_requires_target():
    cfg = valid_cfg()
    cfg["volumes"] = [{"name": "n8n-data"}]
    with pytest.raises(AnsibleFilterError, match=r"volumes\[0\]\.target"):
        podman_services.podman_service_normalize(cfg, "n8n")


def test_managed_named_network_is_accepted():
    cfg = valid_cfg()
    cfg["named_networks"] = {"managed": {"driver": "bridge", "external": False}}

    svc = podman_services.podman_service_normalize(cfg, "managedsvc")

    assert svc["network"] == {"name": "managed", "driver": "bridge", "external": False}


def test_external_named_network_is_accepted_without_managed_driver():
    cfg = valid_cfg()
    cfg["named_networks"] = {"shared": {"external": True}}

    svc = podman_services.podman_service_normalize(cfg, "sharedsvc")

    assert svc["network"] == {"name": "shared", "external": True}


def test_image_reference_drift_matching():
    result = podman_services.podman_image_reference_drift({"rc": 0, "stdout": "docker.io/n8nio/n8n:2.31.4"}, "docker.io/n8nio/n8n:2.31.4")
    assert result["drift"] is False
    assert "No Podman image reference drift" in result["message"]


def test_image_reference_drift_mismatching():
    result = podman_services.podman_image_reference_drift({"rc": 0, "stdout": "docker.io/n8nio/n8n:2.31.3"}, "docker.io/n8nio/n8n:2.31.4")
    assert result["drift"] is True
    assert result["missing"] is False


def test_image_reference_drift_missing_container():
    result = podman_services.podman_image_reference_drift({"rc": 125, "stdout": ""}, "docker.io/n8nio/n8n:2.31.4")
    assert result["drift"] is True
    assert result["missing"] is True


@pytest.mark.parametrize("action", ["deploy", "bootstrap", "update", "recreate", "remove"])
def test_secret_policy_preserve_never_replaces(action):
    assert podman_services.podman_secret_policy({"update_policy": "preserve"}, action) == {
        "force": False,
        "skip_existing": True,
    }


@pytest.mark.parametrize("action", ["deploy", "bootstrap", "remove"])
def test_secret_policy_reconcile_preserves_outside_rotation_actions(action):
    assert podman_services.podman_secret_policy({"update_policy": "reconcile"}, action) == {
        "force": False,
        "skip_existing": True,
    }


@pytest.mark.parametrize("action", ["update", "recreate"])
def test_secret_policy_reconcile_forces_rotation(action):
    assert podman_services.podman_secret_policy({"update_policy": "reconcile"}, action) == {
        "force": True,
        "skip_existing": False,
    }


def canonical_cfg():
    return {
        "runtime": "podman",
        "description": "Canonical Docker-style service",
        "image": "ghcr.io/example/portable:1.2.3",
        "user": "1001:1002",
        "environment": {"APP_ENV": "production", "COUNT": 2},
        "deploy": {"type": "container", "host": "podman01"},
        "ports": {
            "web": {
                "published": "8443",
                "target": "8080",
                "protocol": "TCP",
                "host_ip": "192.0.2.10",
            }
        },
        "volumes": {
            "config": {
                "type": "bind",
                "source": "/opt/portable/config",
                "target": "/config",
                "read_only": "true",
            },
            "data": {
                "type": "volume",
                "source": "portable-data",
                "target": "/data",
                "read_only": False,
            },
            "scratch": {
                "type": "tmpfs",
                "target": "/tmp",
                "tmpfs": {"size": "1048576", "mode": 1777},
            },
        },
        "paths": [{"path": "/opt/portable/config", "owner": "1001", "group": "1002", "mode": "0750"}],
        "cap_add": ["NET_BIND_SERVICE"],
        "cap_drop": ["ALL"],
        "no_new_privileges": True,
        "read_only": True,
        "healthcheck": {
            "test": ["CMD-SHELL", "curl -fsS http://127.0.0.1:8080/health"],
            "interval": "20s",
            "timeout": "5s",
            "retries": 4,
            "start_period": "30s",
        },
        "postgres": {"enable": True, "databases": ["portable"]},
        "traefik": {"enable": True, "port": 8080},
    }


def test_normalize_maps_every_canonical_docker_style_field():
    svc = podman_services.podman_service_normalize(canonical_cfg(), "portable")

    assert svc["image"] == "ghcr.io/example/portable:1.2.3"
    assert svc["container"]["image"] == svc["image"]
    assert svc["container"]["uid"] == "1001"
    assert svc["container"]["gid"] == "1002"
    assert svc["env"] == {"APP_ENV": "production", "COUNT": 2}
    assert svc["container"]["host"] == "podman01"
    assert svc["container"]["ports"] == [
        {
            "host": 8443,
            "container": 8080,
            "protocol": "tcp",
            "host_ip": "192.0.2.10",
        }
    ]
    assert svc["host_paths"] == [
        {
            "path": "/opt/portable/config",
            "owner": "1001",
            "group": "1002",
            "mode": "0750",
        }
    ]
    assert svc["container"]["mounts"] == [
        {
            "source": "/opt/portable/config",
            "target": "/config",
            "read_only": True,
        }
    ]
    assert svc["volumes"] == [
        {
            "name": "portable-data",
            "target": "/data",
            "read_only": False,
        }
    ]
    assert svc["container"]["tmpfs"] == [
        {
            "target": "/tmp",
            "options": ["size=1048576", "mode=1777"],
        }
    ]
    assert svc["container"]["cap_add"] == ["NET_BIND_SERVICE"]
    assert svc["container"]["cap_drop"] == ["ALL"]
    assert svc["container"]["no_new_privileges"] is True
    assert svc["container"]["read_only"] is True
    assert svc["container"]["healthcheck"] == {
        "command": "curl -fsS http://127.0.0.1:8080/health",
        "interval": "20s",
        "timeout": "5s",
        "retries": 4,
        "start_period": "30s",
    }
    assert svc["postgres"] == {"enable": True, "databases": ["portable"]}
    assert svc["traefik"] == {"enable": True, "port": 8080}


@pytest.mark.parametrize("ports_as_mapping", [False, True])
@pytest.mark.parametrize("volumes_as_mapping", [False, True])
def test_canonical_ports_and_volumes_accept_lists_and_named_mappings(ports_as_mapping, volumes_as_mapping):
    cfg = {
        "runtime": "podman",
        "image": "ghcr.io/example/portable:1.2.3",
    }
    port = {"published": 8080, "target": 80}
    volume = {
        "type": "bind",
        "source": "/opt/portable",
        "target": "/srv/portable",
    }
    cfg["ports"] = {"http": port} if ports_as_mapping else [port]
    cfg["volumes"] = {"data": volume} if volumes_as_mapping else [volume]

    svc = podman_services.podman_service_normalize(cfg, "portable")

    assert svc["container"]["ports"] == [{"host": 8080, "container": 80, "protocol": "tcp"}]
    assert svc["container"]["mounts"] == [
        {
            "source": "/opt/portable",
            "target": "/srv/portable",
            "read_only": False,
        }
    ]


@pytest.mark.parametrize(
    "user",
    [
        "1000",
        "1000:",
        ":1000",
        "1000:1000:1000",
        "-1:1000",
        "1000:-1",
        "user:1000",
        "1000:group",
        " 1000:1000",
        "1000:1000 ",
        1000,
    ],
)
def test_canonical_user_requires_exact_numeric_uid_gid(user):
    cfg = {
        "runtime": "podman",
        "image": "ghcr.io/example/portable:1.2.3",
        "user": user,
    }

    with pytest.raises(AnsibleFilterError, match="exactly two numeric"):
        podman_services.podman_service_normalize(cfg, "portable")


@pytest.mark.parametrize("image", ["ghcr.io/example/portable:latest", "ghcr.io/example/portable", ""])
def test_canonical_image_preserves_exact_non_latest_validation(image):
    cfg = {"runtime": "podman", "image": image}

    with pytest.raises(AnsibleFilterError, match="exact, non-latest"):
        podman_services.podman_service_normalize(cfg, "portable")


@pytest.mark.parametrize(
    ("legacy_field", "legacy_value"),
    [
        ("container", {"image": "ghcr.io/example/portable:1.2.3"}),
        ("env", {"MODE": "legacy"}),
        ("host_paths", [{"path": "/opt/legacy"}]),
        ("network", {"name": "legacy", "delete_on_stop": True}),
    ],
)
def test_removed_legacy_podman_fields_fail_clearly(legacy_field, legacy_value):
    cfg = minimal_canonical_cfg()
    cfg[legacy_field] = legacy_value

    with pytest.raises(AnsibleFilterError, match=rf"unsupported top-level fields for Podman: {legacy_field}"):
        podman_services.podman_service_normalize(cfg, "portable")


def test_legacy_named_volume_form_is_rejected():
    cfg = minimal_canonical_cfg()
    cfg["volumes"] = [{"name": "legacy-data", "target": "/legacy"}]

    with pytest.raises(AnsibleFilterError, match=r"volumes\[0\]\.source"):
        podman_services.podman_service_normalize(cfg, "portable")


def test_docker_style_service_switches_to_podman_by_changing_runtime():
    docker_style = {
        "runtime": "docker",
        "image": "ghcr.io/example/portable:1.2.3",
        "user": "1000:1000",
        "environment": {"TZ": "UTC"},
        "ports": {"http": {"published": 8080, "target": 80}},
        "volumes": {
            "config": {
                "type": "bind",
                "source": "/opt/portable",
                "target": "/config",
                "read_only": False,
            }
        },
        "paths": [{"path": "/opt/portable"}],
        "deploy": {
            "type": "container",
            "mode": "replicated",
            "replicas": 1,
            "host": "podman01",
        },
    }
    docker_style["runtime"] = "podman"

    svc = podman_services.podman_service_normalize(docker_style, "portable")

    assert svc["image"] == docker_style["image"]
    assert svc["env"] == docker_style["environment"]
    assert svc["container"]["host"] == "podman01"
    assert svc["container"]["mounts"][0]["source"] == "/opt/portable"


def minimal_canonical_cfg():
    return {
        "runtime": "podman",
        "image": "ghcr.io/example/portable:1.2.3",
    }


@pytest.mark.parametrize("value", [None, True, False, 0, 1, [], {}, "", " preserve", "preserve ", "Preserve"])
def test_secret_policy_rejects_invalid_update_policy(value):
    with pytest.raises(AnsibleFilterError, match=r"secret\.update_policy"):
        podman_services.podman_secret_policy({"update_policy": value}, "update")


def test_secret_and_network_values_are_normalized():
    cfg = minimal_canonical_cfg()
    declarations = [
        {
            "name": "portable_secret",
            "var": "portable_secret",
            "target": "/run/secrets/portable_secret",
            "update_policy": "reconcile",
        }
    ]
    cfg["named_networks"] = {"portable": {"driver": "bridge", "external": "false"}}

    svc = podman_services.podman_service_normalize(cfg, "portable")
    secrets = podman_services.podman_secret_declarations(declarations)

    assert secrets[0]["update_policy"] == "reconcile"
    assert svc["network"]["external"] is False


@pytest.mark.parametrize("field", ["no_new_privileges", "read_only"])
def test_top_level_security_boolean_rejects_integer_two(field):
    cfg = minimal_canonical_cfg()
    cfg[field] = 2

    with pytest.raises(AnsibleFilterError, match=field):
        podman_services.podman_service_normalize(cfg, "portable")


def test_canonical_volume_read_only_values_are_strict_booleans():
    canonical = minimal_canonical_cfg()
    canonical["volumes"] = [
        {
            "type": "bind",
            "source": "/opt/portable",
            "target": "/data",
            "read_only": "false",
        }
    ]
    canonical_svc = podman_services.podman_service_normalize(canonical, "portable")

    assert canonical_svc["container"]["mounts"][0]["read_only"] is False


@pytest.mark.parametrize(
    ("section", "field"),
    [("network", "external"), ("volume", "read_only")],
)
def test_nested_boolean_fields_reject_integer_two(section, field):
    cfg = minimal_canonical_cfg()
    if section == "network":
        cfg["named_networks"] = {"portable": {field: 2}}
    else:
        cfg["volumes"] = [
            {
                "type": "bind",
                "source": "/opt/portable",
                "target": "/data",
                field: 2,
            }
        ]

    with pytest.raises(AnsibleFilterError, match=field):
        podman_services.podman_service_normalize(cfg, "portable")


@pytest.mark.parametrize("host", ["", "   ", 42, None])
def test_deploy_host_must_be_nonempty_string(host):
    cfg = minimal_canonical_cfg()
    cfg["deploy"] = {"host": host}

    with pytest.raises(AnsibleFilterError, match=r"deploy\.host"):
        podman_services.podman_service_normalize(cfg, "portable")


def test_image_rejects_empty_tag():
    cfg = {"runtime": "podman", "image": "ghcr.io/example/portable:"}

    with pytest.raises(AnsibleFilterError, match="exact, non-latest"):
        podman_services.podman_service_normalize(cfg, "portable")


@pytest.mark.parametrize("path", ["/opt/../etc", "/opt/app/../../etc", "opt/portable"])
def test_host_paths_must_normalize_within_opt(path):
    cfg = minimal_canonical_cfg()
    cfg["paths"] = [{"path": path}]

    with pytest.raises(AnsibleFilterError, match=r"paths\[0\]\.path"):
        podman_services.podman_service_normalize(cfg, "portable")


@pytest.mark.parametrize("test", [["CMD"], ["CMD-SHELL"]])
def test_healthcheck_command_forms_require_a_command(test):
    cfg = minimal_canonical_cfg()
    cfg["healthcheck"] = {"test": test}

    with pytest.raises(AnsibleFilterError, match="must include a command"):
        podman_services.podman_service_normalize(cfg, "portable")


@pytest.mark.parametrize("field", ["postgres", "traefik"])
@pytest.mark.parametrize("value", [None, [], "enabled"])
def test_postgres_and_traefik_must_be_mappings(field, value):
    cfg = minimal_canonical_cfg()
    cfg[field] = value

    with pytest.raises(AnsibleFilterError, match=field):
        podman_services.podman_service_normalize(cfg, "portable")


@pytest.mark.parametrize("after", ["network.target", [""], [42], {"unit": "network.target"}])
def test_systemd_after_must_be_list_of_nonempty_unit_names(after):
    cfg = valid_cfg()
    cfg["systemd"] = {"after": after}

    with pytest.raises(AnsibleFilterError, match=r"n8n\.systemd\.after"):
        podman_services.podman_service_normalize(cfg, "n8n")


def test_systemd_after_is_normalized_when_valid():
    cfg = valid_cfg()
    cfg["systemd"] = {"after": [" postgresql.service ", "custom.target"]}

    svc = podman_services.podman_service_normalize(cfg, "n8n")

    assert svc["container"]["systemd"]["after"] == ["postgresql.service", "custom.target"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("published", True),
        ("published", 0),
        ("published", 65536),
        ("target", False),
        ("target", 0),
        ("target", 65536),
    ],
)
def test_ports_reject_booleans_and_values_outside_valid_range(field, value):
    cfg = minimal_canonical_cfg()
    port = {"published": 8080, "target": 80}
    port[field] = value
    cfg["ports"] = [port]

    with pytest.raises(AnsibleFilterError, match=field):
        podman_services.podman_service_normalize(cfg, "portable")


def test_unsupported_canonical_port_mode_is_rejected():
    cfg = minimal_canonical_cfg()
    cfg["ports"] = [{"published": 8080, "target": 80, "mode": "host"}]

    with pytest.raises(AnsibleFilterError, match=r"ports\[0\]\.mode"):
        podman_services.podman_service_normalize(cfg, "portable")


@pytest.mark.parametrize("host_ip", ["", "not-an-ip", "::1", "2001:db8::1"])
def test_port_host_ip_is_nonempty_ipv4_for_this_phase(host_ip):
    cfg = minimal_canonical_cfg()
    cfg["ports"] = [{"published": 8080, "target": 80, "host_ip": host_ip}]

    with pytest.raises(AnsibleFilterError, match="host_ip"):
        podman_services.podman_service_normalize(cfg, "portable")


@pytest.mark.parametrize(
    ("location", "value", "match"),
    [
        ("network", "bad/network", r"named_networks key"),
        ("named_volume", "../data", r"volumes\[0\]\.source"),
        ("secret", "bad/secret", r"secret declarations\[0\]\.name"),
    ],
)
def test_quadlet_filename_and_resource_names_are_validated(location, value, match):
    cfg = minimal_canonical_cfg()
    if location == "network":
        cfg["named_networks"] = {value: {"external": False}}
    elif location == "named_volume":
        cfg["volumes"] = [{"type": "volume", "source": value, "target": "/data"}]
    else:
        declarations = [
            {
                "name": value,
                "var": "portable_secret",
                "target": "/run/secrets/portable_secret",
            }
        ]

        with pytest.raises(AnsibleFilterError, match=match):
            podman_services.podman_secret_declarations(declarations)
        return

    with pytest.raises(AnsibleFilterError, match=match):
        podman_services.podman_service_normalize(cfg, "portable")


def test_service_name_used_for_unit_filename_is_validated():
    with pytest.raises(
        AnsibleFilterError,
        match=r"\.\./portable\.name must be a valid Quadlet resource name",
    ):
        podman_services.podman_service_normalize(minimal_canonical_cfg(), "../portable")


def test_canonical_description_is_accepted():
    cfg = minimal_canonical_cfg()
    cfg["description"] = "Portable service"

    svc = podman_services.podman_service_normalize(cfg, "portable")

    assert svc["description"] == "Portable service"


@pytest.mark.parametrize(
    "deploy",
    [
        {"mode": "global", "host": "podman01"},
        {"replicas": 0, "host": "podman01"},
        {"replicas": 2, "host": "podman01"},
        {"placement": {"constraints": ["node.role == worker"]}, "host": "podman01"},
    ],
)
def test_unsupported_docker_deploy_semantics_are_rejected(deploy):
    cfg = minimal_canonical_cfg()
    cfg["deploy"] = deploy

    with pytest.raises(AnsibleFilterError, match="deploy"):
        podman_services.podman_service_normalize(cfg, "portable")


@pytest.mark.parametrize(
    "deploy",
    [
        {"host": "podman01"},
        {"type": "container", "mode": "replicated", "host": "podman01"},
        {"type": "container", "mode": "replicated", "replicas": 1, "host": "podman01"},
        {"type": "container", "replicas": "1", "host": "podman01"},
    ],
)
def test_supported_single_instance_deploy_forms_are_accepted(deploy):
    cfg = minimal_canonical_cfg()
    cfg["deploy"] = deploy

    svc = podman_services.podman_service_normalize(cfg, "portable")

    assert svc["container"]["host"] == "podman01"


def test_docker_only_deploy_metadata_is_rejected_without_mutating_input():
    cfg = minimal_canonical_cfg()
    cfg["deploy"] = {
        "host": "podman01",
        "profile": "careful",
        "constraints": ["node.labels.docker_services_host == manager"],
    }
    original = deepcopy(cfg)

    with pytest.raises(AnsibleFilterError, match="constraints, profile"):
        podman_services.podman_service_normalize(cfg, "portable")

    assert cfg == original


def test_environment_initial_normalization_rejects_invalid_keys_and_lists_but_preserves_typed_mappings():
    bad_key = minimal_canonical_cfg()
    bad_key["environment"] = {"BAD-KEY": "value"}
    complex_value = minimal_canonical_cfg()
    complex_value["environment"] = {"STRUCTURED": ["serialize", "me"]}
    typed_value = minimal_canonical_cfg()
    typed_value["environment"] = {
        "HOST": {"value_template": "app.${cloudflare_zone}"},
        "TOKEN": {"value_from": {"infisical": "application_token"}},
    }

    with pytest.raises(AnsibleFilterError, match=r"environment\.BAD-KEY"):
        podman_services.podman_service_normalize(bad_key, "portable")
    with pytest.raises(AnsibleFilterError, match=r"environment\.STRUCTURED"):
        podman_services.podman_service_normalize(complex_value, "portable")

    assert podman_services.podman_service_normalize(typed_value, "portable")["env"] == typed_value["environment"]


def canonical_secret_cfg():
    cfg = minimal_canonical_cfg()
    cfg["infisical"] = {
        "fail_on_empty": True,
        "secrets_map": [
            {
                "var": "portable_secret",
                "path": "/Portable",
                "name": "VALUE",
                "secret": {
                    "name": "portable_secret",
                    "target": "/run/secrets/portable_secret",
                    "uid": "1001",
                    "gid": "1002",
                    "mode": "0400",
                    "update_policy": "reconcile",
                },
            },
            {
                "var": "template_only",
                "path": "/Portable",
                "name": "TEMPLATE",
            },
        ],
    }
    return cfg


def test_canonical_secret_normalizes_for_native_podman_and_keeps_lookup_only_entry():
    service_common_spec = importlib.util.spec_from_file_location(
        "service_common_for_podman",
        Path("ansible/roles/service_common/filter_plugins/service_common.py"),
    )
    service_common = importlib.util.module_from_spec(service_common_spec)
    service_common_spec.loader.exec_module(service_common)
    normalized = service_common.service_common_infisical_normalize(canonical_secret_cfg()["infisical"]["secrets_map"])
    secrets = podman_services.podman_secret_declarations(normalized["secret_declarations"])

    assert normalized["secrets_map"] == [
        {"var": "portable_secret", "path": "/Portable", "name": "VALUE"},
        {"var": "template_only", "path": "/Portable", "name": "TEMPLATE"},
    ]
    assert secrets == [
        {
            "name": "portable_secret",
            "var": "portable_secret",
            "target": "/run/secrets/portable_secret",
            "uid": "1001",
            "gid": "1002",
            "mode": "0400",
            "update_policy": "reconcile",
        }
    ]


def test_legacy_podman_secret_contract_is_rejected():
    cfg = canonical_secret_cfg()
    cfg["secrets"] = [
        {
            "name": "portable_secret",
            "infisical_path": "/Portable",
            "infisical_key": "VALUE",
            "target": "/run/secrets/portable_secret",
            "uid": "1001",
            "gid": "1002",
            "mode": "0400",
            "immutable": False,
            "replace": True,
        }
    ]

    with pytest.raises(AnsibleFilterError, match="not supported by Podman"):
        podman_services.podman_service_normalize(cfg, "portable")


def test_check_mode_metadata_remains_owned_by_common_declaration():
    cfg = canonical_secret_cfg()
    cfg["infisical"]["secrets_map"][1]["check_mode_value"] = "check-mode.invalid"

    assert cfg["infisical"]["secrets_map"][1]["check_mode_value"] == "check-mode.invalid"


def test_runtime_adapter_does_not_merge_legacy_podman_lookup_metadata():
    cfg = canonical_secret_cfg()
    cfg["secrets"] = [
        {
            "name": "portable_secret",
            "infisical_path": "/Portable",
            "infisical_key": "DIFFERENT",
        }
    ]

    with pytest.raises(AnsibleFilterError, match="not supported by Podman"):
        podman_services.podman_service_normalize(cfg, "portable")


def test_top_level_named_networks_and_systemd_own_podman_policy():
    cfg = minimal_canonical_cfg()
    cfg["named_networks"] = {"portable": {"driver": "bridge", "external": False}}
    cfg["systemd"] = {
        "after": ["network-online.target"],
        "restart": "on-failure",
        "restart_sec": "15s",
    }

    svc = podman_services.podman_service_normalize(cfg, "portable")

    assert svc["network"]["name"] == "portable"
    assert svc["container"]["systemd"]["restart"] == "on-failure"


@pytest.mark.parametrize(("field", "replacement"), [("network", "named_networks"), ("systemd", "top-level systemd")])
def test_retired_service_runtime_options_fail_with_migration_message(field, replacement):
    cfg = minimal_canonical_cfg()
    cfg["runtime_options"] = {"podman": {field: {}}}

    with pytest.raises(AnsibleFilterError, match=replacement):
        podman_services.podman_service_normalize(cfg, "portable")


@pytest.mark.parametrize(
    ("field", "canonical"),
    [
        ("network", {"named_networks": {"portable": {"external": False}}}),
        ("systemd", {"systemd": {"restart": "on-failure"}}),
    ],
)
def test_dual_retired_and_canonical_declarations_fail_clearly(field, canonical):
    cfg = minimal_canonical_cfg()
    cfg.update(canonical)
    cfg["runtime_options"] = {"podman": {field: {}}}

    with pytest.raises(AnsibleFilterError, match="cannot both be declared"):
        podman_services.podman_service_normalize(cfg, "portable")


@pytest.mark.parametrize("value", [None, [], "on-failure", 1])
def test_systemd_must_be_a_mapping(value):
    cfg = minimal_canonical_cfg()
    cfg["systemd"] = value

    with pytest.raises(AnsibleFilterError, match=r"portable\.systemd must be a mapping"):
        podman_services.podman_service_normalize(cfg, "portable")


def test_systemd_rejects_unsupported_keys():
    cfg = minimal_canonical_cfg()
    cfg["systemd"] = {"restart": "on-failure", "wanted_by": "multi-user.target"}

    with pytest.raises(AnsibleFilterError, match="unsupported fields: wanted_by"):
        podman_services.podman_service_normalize(cfg, "portable")


def test_podman_named_network_rejects_multiple_and_unsupported_options():
    multiple = minimal_canonical_cfg()
    multiple["named_networks"] = {"one": {"external": False}, "two": {"external": True}}
    unsupported = minimal_canonical_cfg()
    unsupported["named_networks"] = {"one": {"external": False, "delete_on_stop": True}}

    with pytest.raises(AnsibleFilterError, match="exactly one attached network"):
        podman_services.podman_service_normalize(multiple, "portable")
    with pytest.raises(AnsibleFilterError, match="unsupported fields: delete_on_stop"):
        podman_services.podman_service_normalize(unsupported, "portable")


def test_network_and_systemd_state_do_not_leak_between_services():
    first = minimal_canonical_cfg()
    first["named_networks"] = {"first": {"driver": "bridge", "external": False}}
    first["systemd"] = {"restart": "always"}
    second = minimal_canonical_cfg()

    first_service = podman_services.podman_service_normalize(first, "first")
    second_service = podman_services.podman_service_normalize(second, "second")

    assert first_service["network"]["name"] == "first"
    assert first_service["container"]["systemd"] == {"restart": "always"}
    assert second_service["network"] is None
    assert "systemd" not in second_service["container"]


@pytest.mark.parametrize(
    "runtime_options",
    [
        [],
        {"podman": []},
        {"podman": {"unsupported": True}},
        {"containerd": {}},
    ],
)
def test_runtime_options_shape_and_fields_are_strict(runtime_options):
    cfg = minimal_canonical_cfg()
    cfg["runtime_options"] = runtime_options

    with pytest.raises(AnsibleFilterError, match="runtime_options"):
        podman_services.podman_service_normalize(cfg, "portable")


@pytest.mark.parametrize("policy", ["preserve", "reconcile"])
def test_secret_policy_and_declarations_share_supported_update_policies(policy):
    declaration = {
        "name": "portable_secret",
        "var": "portable_secret",
        "target": "/run/secrets/portable_secret",
    }
    if policy != "preserve":
        declaration["update_policy"] = policy

    normalized = podman_services.podman_secret_declarations([declaration])[0]
    decision = podman_services.podman_secret_policy(declaration, "update")

    assert normalized["update_policy"] == policy
    assert decision == {
        "force": policy == "reconcile",
        "skip_existing": policy != "reconcile",
    }


UNSUPPORTED_PODMAN_TOP_LEVEL_FIELDS = [
    "cgroup",
    "cleanup",
    "command",
    "configs",
    "container",
    "container_name",
    "depends_on",
    "device_cgroup_rules",
    "devices",
    "dns",
    "drift",
    "entrypoint",
    "env",
    "env_file",
    "expose",
    "extra_hosts",
    "group",
    "host_paths",
    "hostname",
    "init",
    "labels",
    "named_volumes",
    "network",
    "network_mode",
    "networks",
    "pid",
    "privileged",
    "pull_policy",
    "security_opt",
    "settings",
    "shm_size",
    "shm_tmpfs_size",
    "stack",
    "stop_grace_period",
    "stop_signal",
    "swarm_configs",
    "swarm_env_templates",
    "sysctls",
    "targets",
    "themepark",
    "tmpfs",
    "ulimits",
    "working_dir",
]


@pytest.mark.parametrize("field", UNSUPPORTED_PODMAN_TOP_LEVEL_FIELDS)
def test_unsupported_top_level_fields_are_rejected_instead_of_discarded(field):
    cfg = minimal_canonical_cfg()
    cfg[field] = True

    with pytest.raises(AnsibleFilterError, match=rf"portable.*unsupported top-level fields for Podman: {field}"):
        podman_services.podman_service_normalize(cfg, "portable")


def test_multiple_unsupported_top_level_fields_are_reported_in_sorted_order():
    cfg = minimal_canonical_cfg()
    cfg.update({"settings": {}, "hostname": "portable", "command": ["serve"]})

    with pytest.raises(AnsibleFilterError) as error:
        podman_services.podman_service_normalize(cfg, "portable")

    assert str(error.value) == ("portable contains unsupported top-level fields for Podman: command, hostname, settings")


def test_unknown_top_level_field_is_rejected():
    cfg = minimal_canonical_cfg()
    cfg["invented_podman_behavior"] = True

    with pytest.raises(AnsibleFilterError, match="invented_podman_behavior"):
        podman_services.podman_service_normalize(cfg, "portable")


def test_catalog_common_and_application_owned_fields_are_accepted_without_mutation():
    cfg = minimal_canonical_cfg()
    cfg.update(
        {
            "enabled": True,
            "tags": ["portable"],
            "environment": {"MODE": "test"},
            "infisical": {"secrets_map": []},
            "paths": [],
            "copies": [],
            "templates": [],
            "traefik": {},
            "postgres": {},
            "application_prepare": {"handler": ""},
            "prep": {"synthetic": True},
            "paths_vault": {"vault_dir": "/synthetic"},
            "secrets": [],
            "named_networks": {},
            "volumes": [],
            "cap_add": [],
            "cap_drop": [],
            "no_new_privileges": False,
            "read_only": False,
            "healthcheck": {"test": ["NONE"]},
            "deploy": {"type": "container", "mode": "replicated", "replicas": 1},
            "systemd": {},
        }
    )
    original = deepcopy(cfg)

    normalized = podman_services.podman_service_normalize(cfg, "portable")

    assert normalized["name"] == "portable"
    assert cfg == original


def test_rejected_top_level_fields_do_not_mutate_source_mapping():
    cfg = minimal_canonical_cfg()
    cfg.update({"hostname": "portable", "command": ["serve"]})
    original = deepcopy(cfg)

    with pytest.raises(AnsibleFilterError):
        podman_services.podman_service_normalize(cfg, "portable")

    assert cfg == original


def test_docker_configuration_is_rejected_by_runtime_before_podman_field_validation():
    cfg = {"runtime": "docker", "image": "ghcr.io/example/portable:1.2.3", "command": ["serve"]}

    with pytest.raises(AnsibleFilterError, match=r"runtime must be podman") as error:
        podman_services.podman_service_normalize(cfg, "portable")

    assert "unsupported top-level" not in str(error.value)


@pytest.mark.parametrize(
    ("role_prefix", "explicit_name", "expected"),
    [
        ("portable", None, "portable"),
        ("portable", "custom-portable", "custom-portable"),
        ("portable-blue", None, "portable-blue"),
        ("portable-blue", "blue-instance", "blue-instance"),
    ],
)
def test_effective_name_controls_normalized_service_and_unit_name(role_prefix, explicit_name, expected):
    cfg = minimal_canonical_cfg()
    if explicit_name is not None:
        cfg["name"] = explicit_name

    normalized = podman_services.podman_service_normalize(cfg, role_prefix)

    assert normalized["name"] == expected
    assert normalized["unit_name"] == expected


def test_explicit_invalid_service_name_is_rejected():
    cfg = minimal_canonical_cfg()
    cfg["name"] = "bad/name"

    with pytest.raises(AnsibleFilterError, match=r"portable\.name.*valid Quadlet resource name"):
        podman_services.podman_service_normalize(cfg, "portable")


@pytest.mark.parametrize("deploy_type", ["swarm", "", "Podman"])
def test_podman_deploy_type_must_be_container(deploy_type):
    cfg = minimal_canonical_cfg()
    cfg["deploy"] = {"type": deploy_type}

    with pytest.raises(AnsibleFilterError, match=r"deploy\.type"):
        podman_services.podman_service_normalize(cfg, "portable")


@pytest.mark.parametrize("field", ["profile", "constraints"])
def test_podman_rejects_swarm_deploy_metadata(field):
    cfg = minimal_canonical_cfg()
    cfg["deploy"] = {"type": "container", field: "synthetic"}

    with pytest.raises(AnsibleFilterError, match=rf"deploy.*unsupported fields for Podman: {field}"):
        podman_services.podman_service_normalize(cfg, "portable")


def test_nonempty_docker_runtime_options_are_not_silently_ignored_by_podman():
    cfg = minimal_canonical_cfg()
    cfg["runtime_options"] = {"docker": {"synthetic": True}}

    with pytest.raises(AnsibleFilterError, match=r"runtime_options\.docker.*synthetic"):
        podman_services.podman_service_normalize(cfg, "portable")


def rootless_cfg():
    return {
        "runtime": "podman",
        "image": "registry.example.invalid/adminer:5.4.2",
        "user": "1000:1000",
        "named_networks": {"adminer": {"driver": "bridge", "external": False}},
        "ports": [{"published": 18080, "target": 8080, "protocol": "tcp"}],
        "deploy": {
            "type": "container",
            "host": "manager",
            "execution": {"mode": "rootless", "host_user": "podman-adminer"},
        },
        "cap_add": [],
        "cap_drop": ["all"],
        "no_new_privileges": True,
    }


def rootless_bind_cfg():
    cfg = rootless_cfg()
    cfg["user"] = "0:0"
    cfg["image"] = "lscr.io/linuxserver/thelounge:v4.5.1-ls225"
    cfg["environment"] = {"PUID": "1000", "PGID": "1000"}
    cfg["deploy"]["execution"] = {
        "mode": "rootless",
        "host_user": "podman-thelounge",
        "userns": {"mode": "keep-id", "uid": "1000", "gid": 1000},
    }
    cfg["paths"] = [{"path": "/opt/appdata/thelounge", "state": "directory", "mode": "0750"}]
    cfg["volumes"] = {
        "config": {
            "type": "bind",
            "source": "/opt/appdata/thelounge",
            "target": "/config",
            "read_only": False,
        }
    }
    return cfg


def test_rootless_bind_mount_uses_validated_keep_id_and_dedicated_path_ownership_without_mutation():
    cfg = rootless_bind_cfg()
    original = deepcopy(cfg)

    normalized = podman_services.podman_service_normalize(cfg, "thelounge")

    assert normalized["execution"] == {
        "mode": "rootless",
        "host_user": "podman-thelounge",
        "userns": {"mode": "keep-id", "uid": "1000", "gid": "1000"},
    }
    assert normalized["container"]["uid"] == "0"
    assert normalized["container"]["gid"] == "0"
    assert normalized["execution"]["userns"]["uid"] == str(normalized["env"]["PUID"])
    assert normalized["execution"]["userns"]["gid"] == str(normalized["env"]["PGID"])
    assert normalized["host_paths"] == cfg["paths"]
    assert normalized["container"]["mounts"] == [
        {
            "source": "/opt/appdata/thelounge",
            "target": "/config",
            "read_only": False,
        }
    ]
    assert normalized["volumes"] == []
    assert cfg == original


def test_rootless_linuxserver_container_root_contract_is_separate_from_the_nonroot_execution_account():
    normalized = podman_services.podman_service_normalize(rootless_bind_cfg(), "thelounge")
    account = rootless_account_context()
    account.update(
        {
            "host_user": "podman-thelounge",
            "service": "thelounge",
            "comment": "Managed rootless Podman account for thelounge",
            "home": "/var/lib/podman-thelounge",
            "account": [
                "x",
                "1001",
                "1001",
                "Managed rootless Podman account for thelounge",
                "/var/lib/podman-thelounge",
                "/usr/sbin/nologin",
            ],
            "group": ["x", "1001", ""],
            "group_names": ["podman-thelounge"],
            "persisted": {
                "managed_by": "podman_services",
                "service": "thelounge",
                "mode": "rootless",
                "host_user": "podman-thelounge",
                "uid": "1001",
                "gid": "1001",
            },
        }
    )
    subordinate_ids = podman_services.podman_subid_range(
        "podman-thelounge:165536:65536\n",
        "podman-thelounge",
    )

    assert normalized["container"]["uid"] == "0"
    assert normalized["container"]["gid"] == "0"
    assert int(account["account"][1]) > 0
    assert int(account["account"][2]) > 0
    assert subordinate_ids["start"] > 0
    assert podman_services.podman_rootless_account_contract(account) == {"create": False}


@pytest.mark.parametrize(
    ("userns", "message"),
    [
        (None, "userns keep-id mapping is required"),
        ({"mode": "host", "uid": "1000", "gid": "1000"}, "mode"),
        ({"mode": "keep-id", "uid": "1000"}, "both uid and gid"),
        ({"mode": "keep-id", "uid": "65536", "gid": "1000"}, "between 0 and 65535"),
    ],
)
def test_rootless_bind_mount_requires_valid_keep_id_mapping(userns, message):
    cfg = rootless_bind_cfg()
    if userns is None:
        del cfg["deploy"]["execution"]["userns"]
    else:
        cfg["deploy"]["execution"]["userns"] = userns

    with pytest.raises(AnsibleFilterError, match=message):
        podman_services.podman_service_normalize(cfg, "thelounge")


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing_path", "declare exactly"),
        ("different_path", "declare exactly"),
        ("explicit_owner", "must omit owner and group"),
        ("outside_opt", "absolute path within /opt"),
    ],
)
def test_rootless_bind_mount_requires_an_exact_adapter_owned_host_path(mutation, message):
    cfg = rootless_bind_cfg()
    if mutation == "missing_path":
        cfg["paths"] = []
    elif mutation == "different_path":
        cfg["paths"][0]["path"] = "/opt/appdata/other"
    elif mutation == "explicit_owner":
        cfg["paths"][0]["owner"] = "podman-thelounge"
    else:
        cfg["paths"][0]["path"] = "/srv/thelounge"
        cfg["volumes"]["config"]["source"] = "/srv/thelounge"

    with pytest.raises(AnsibleFilterError, match=message):
        podman_services.podman_service_normalize(cfg, "thelounge")


def test_omitted_execution_defaults_to_rootful_without_mutating_source():
    cfg = minimal_canonical_cfg()
    original = deepcopy(cfg)

    normalized = podman_services.podman_service_normalize(cfg, "portable")

    assert normalized["execution"] == {"mode": "rootful"}
    assert cfg == original


def test_explicit_rootful_execution_is_accepted():
    cfg = minimal_canonical_cfg()
    cfg["deploy"] = {"type": "container", "execution": {"mode": "rootful"}}

    normalized = podman_services.podman_service_normalize(cfg, "portable")

    assert normalized["execution"] == {"mode": "rootful"}


def test_rootless_execution_is_normalized_and_container_user_remains_independent():
    cfg = rootless_cfg()
    original = deepcopy(cfg)

    normalized = podman_services.podman_service_normalize(cfg, "adminer")

    assert normalized["execution"] == {"mode": "rootless", "host_user": "podman-adminer"}
    assert normalized["container"]["uid"] == "1000"
    assert normalized["container"]["gid"] == "1000"
    assert cfg == original


@pytest.mark.parametrize("execution", [{}, {"host_user": "podman-adminer"}])
def test_present_execution_requires_mode(execution):
    cfg = rootless_cfg()
    cfg["deploy"]["execution"] = execution

    with pytest.raises(AnsibleFilterError, match=r"deploy\.execution\.mode"):
        podman_services.podman_service_normalize(cfg, "adminer")


@pytest.mark.parametrize("mode", [None, "", 0, False, [], {}])
def test_execution_rejects_null_empty_and_non_string_modes(mode):
    cfg = rootless_cfg()
    cfg["deploy"]["execution"]["mode"] = mode

    with pytest.raises(AnsibleFilterError, match=r"deploy\.execution\.mode"):
        podman_services.podman_service_normalize(cfg, "adminer")


def test_execution_rejects_unsupported_mode():
    cfg = rootless_cfg()
    cfg["deploy"]["execution"]["mode"] = "daemonless"

    with pytest.raises(AnsibleFilterError, match=r"rootful.*rootless"):
        podman_services.podman_service_normalize(cfg, "adminer")


@pytest.mark.parametrize("host_user", [None, "", "root", "mgt", "Adminer", "podman adminer", "42adminer", []])
def test_rootless_execution_requires_valid_host_user(host_user):
    cfg = rootless_cfg()
    if host_user is None:
        del cfg["deploy"]["execution"]["host_user"]
    else:
        cfg["deploy"]["execution"]["host_user"] = host_user

    with pytest.raises(AnsibleFilterError, match=r"deploy\.execution\.host_user"):
        podman_services.podman_service_normalize(cfg, "adminer")


def test_rootful_execution_rejects_host_user():
    cfg = minimal_canonical_cfg()
    cfg["deploy"] = {
        "type": "container",
        "execution": {"mode": "rootful", "host_user": "podman-adminer"},
    }

    with pytest.raises(AnsibleFilterError, match=r"host_user is only valid"):
        podman_services.podman_service_normalize(cfg, "portable")


def test_rootful_execution_rejects_rootless_user_namespace_mapping():
    cfg = minimal_canonical_cfg()
    cfg["deploy"] = {
        "type": "container",
        "execution": {
            "mode": "rootful",
            "userns": {"mode": "keep-id", "uid": "1000", "gid": "1000"},
        },
    }

    with pytest.raises(AnsibleFilterError, match=r"userns is only valid"):
        podman_services.podman_service_normalize(cfg, "portable")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("volumes", [{"type": "volume", "source": "adminer", "target": "/data"}]),
        ("cap_add", ["NET_ADMIN"]),
        ("secrets", ["adminer_secret"]),
        ("copies", [{"src": "synthetic", "dest": "/opt/adminer/config"}]),
        ("templates", [{"src": "synthetic.j2", "dest": "/opt/adminer/config"}]),
        ("application_prepare", {"handler": "synthetic"}),
        ("prep", {"synthetic": True}),
    ],
)
def test_rootless_execution_rejects_unsupported_initial_capabilities(field, value):
    cfg = rootless_cfg()
    cfg[field] = value

    with pytest.raises(AnsibleFilterError, match=field):
        podman_services.podman_service_normalize(cfg, "adminer")


@pytest.mark.parametrize(
    ("port", "message"),
    [
        ({"published": 443, "target": 8080, "protocol": "tcp"}, "privileged port"),
        ({"published": 18080, "target": 8080, "protocol": "udp"}, "protocol"),
    ],
)
def test_rootless_execution_rejects_unsupported_ports(port, message):
    cfg = rootless_cfg()
    cfg["ports"] = [port]

    with pytest.raises(AnsibleFilterError, match=message):
        podman_services.podman_service_normalize(cfg, "adminer")


def test_rootless_execution_requires_managed_bridge_network():
    cfg = rootless_cfg()
    cfg["named_networks"] = {"adminer": {"external": True}}

    with pytest.raises(AnsibleFilterError, match=r"managed bridge"):
        podman_services.podman_service_normalize(cfg, "adminer")


def test_rootless_execution_rejects_native_infisical_secret_metadata():
    cfg = rootless_cfg()
    cfg["infisical"] = {"secrets_map": [{"var": "key", "path": "/Synthetic", "name": "KEY", "secret": {"name": "key"}}]}

    with pytest.raises(AnsibleFilterError, match=r"secrets"):
        podman_services.podman_service_normalize(cfg, "adminer")


def test_rootless_execution_requires_fully_qualified_exact_image():
    cfg = rootless_cfg()
    cfg["image"] = "adminer:5.4.2"

    with pytest.raises(AnsibleFilterError, match=r"fully qualified"):
        podman_services.podman_service_normalize(cfg, "adminer")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("devices", ["/dev/null:/dev/null"]),
        ("network_mode", "host"),
        ("privileged", True),
    ],
)
def test_unsupported_top_level_host_access_fields_are_rejected(field, value):
    cfg = rootless_cfg()
    cfg[field] = value

    with pytest.raises(AnsibleFilterError, match=rf"adminer.*{field}"):
        podman_services.podman_service_normalize(cfg, "adminer")


def rootless_account_context():
    return {
        "host_user": "podman-adminer",
        "service": "adminer",
        "comment": "Managed rootless Podman account for adminer",
        "home": "/var/lib/podman-adminer",
        "shell": "/usr/sbin/nologin",
        "account": ["x", "1001", "1001", "Managed rootless Podman account for adminer", "/var/lib/podman-adminer", "/usr/sbin/nologin"],
        "group": ["x", "1001", ""],
        "group_names": ["podman-adminer"],
        "password_locked": True,
        "home_exists": True,
        "marker": {},
        "persisted": {
            "managed_by": "podman_services",
            "service": "adminer",
            "mode": "rootless",
            "host_user": "podman-adminer",
            "uid": "1001",
            "gid": "1001",
        },
    }


def test_rootless_account_contract_creates_only_when_every_owned_object_is_absent():
    context = rootless_account_context()
    context.update(
        {
            "account": None,
            "group": None,
            "group_names": [],
            "password_locked": False,
            "home_exists": False,
            "persisted": {},
        }
    )

    assert podman_services.podman_rootless_account_contract(context) == {"create": True}


def test_rootless_account_contract_adopts_the_exact_existing_adminer_account_from_legacy_state():
    assert podman_services.podman_rootless_account_contract(rootless_account_context()) == {"create": False}


def test_rootless_account_contract_adopts_an_exact_marker_owned_account_without_state():
    context = rootless_account_context()
    context["persisted"] = {}
    context["marker"] = {
        "managed_by": "podman_services",
        "service": "adminer",
        "host_user": "podman-adminer",
        "home": "/var/lib/podman-adminer",
        "uid": "1001",
        "gid": "1001",
    }

    assert podman_services.podman_rootless_account_contract(context) == {"create": False}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("account", ["x", "1001", "1001", "ordinary account", "/var/lib/podman-adminer", "/usr/sbin/nologin"]),
        ("group_names", ["podman-adminer", "sudo"]),
        ("password_locked", False),
    ],
)
def test_rootless_account_contract_rejects_incompatible_existing_accounts(field, value):
    context = rootless_account_context()
    context[field] = value

    with pytest.raises(AnsibleFilterError, match=r"does not match the dedicated managed contract"):
        podman_services.podman_rootless_account_contract(context)


def test_rootless_account_contract_rejects_uid_zero_even_with_matching_metadata():
    context = rootless_account_context()
    context["account"][1] = "0"
    context["persisted"]["uid"] = "0"

    with pytest.raises(AnsibleFilterError, match=r"UID or GID 0"):
        podman_services.podman_rootless_account_contract(context)


def test_rootless_account_contract_rejects_an_unmanaged_preexisting_home():
    context = rootless_account_context()
    context.update({"account": None, "group": None, "marker": {}, "persisted": {}})

    with pytest.raises(AnsibleFilterError, match=r"unmanaged home"):
        podman_services.podman_rootless_account_contract(context)


def test_rootless_account_contract_rejects_cross_service_account_reuse():
    context = rootless_account_context()
    context["persisted"] = {}
    context["marker"] = {
        "managed_by": "podman_services",
        "service": "another-service",
        "host_user": "podman-adminer",
        "home": "/var/lib/podman-adminer",
        "uid": "1001",
        "gid": "1001",
    }

    with pytest.raises(AnsibleFilterError, match=r"cross-service reuse"):
        podman_services.podman_rootless_account_contract(context)


def test_subordinate_id_range_requires_one_full_rootless_allocation():
    value = "other:100000:65536\npodman-adminer:165536:65536\n"

    assert podman_services.podman_subid_range(value, "podman-adminer") == {"start": 165536, "count": 65536}


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("other:100000:65536\n", "found 0"),
        ("podman-adminer:165536:1024\n", "at least 65536"),
        ("podman-adminer:165536:65536\npodman-adminer:231072:65536\n", "found 2"),
        ("podman-adminer:not-a-number:65536\n", "Malformed"),
    ],
)
def test_subordinate_id_range_rejects_missing_small_duplicate_and_malformed_entries(value, message):
    with pytest.raises(AnsibleFilterError, match=message):
        podman_services.podman_subid_range(value, "podman-adminer")
