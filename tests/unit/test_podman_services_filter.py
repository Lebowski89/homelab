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
        "deploy": {"type": "swarm", "host": "podman01"},
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

    with pytest.raises(AnsibleFilterError, match=rf"removed legacy Podman fields: {legacy_field}"):
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
            "type": "swarm",
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
    with pytest.raises(AnsibleFilterError, match="service name"):
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

    with pytest.raises(AnsibleFilterError, match=r"deploy\."):
        podman_services.podman_service_normalize(cfg, "portable")


@pytest.mark.parametrize(
    "deploy",
    [
        {"host": "podman01"},
        {"type": "swarm", "mode": "replicated", "host": "podman01"},
        {"type": "swarm", "mode": "replicated", "replicas": 1, "host": "podman01"},
        {"type": "container", "replicas": "1", "host": "podman01"},
        {
            "type": "swarm",
            "mode": "replicated",
            "replicas": 1,
            "profile": "standard",
            "constraints": ["node.labels.zone == internal"],
            "host": "podman01",
        },
    ],
)
def test_supported_single_instance_deploy_forms_are_accepted(deploy):
    cfg = minimal_canonical_cfg()
    cfg["deploy"] = deploy

    svc = podman_services.podman_service_normalize(cfg, "portable")

    assert svc["container"]["host"] == "podman01"


def test_docker_only_deploy_metadata_is_ignored_without_mutating_input():
    cfg = minimal_canonical_cfg()
    cfg["deploy"] = {
        "host": "podman01",
        "profile": "careful",
        "constraints": ["node.labels.docker_services_host == manager"],
    }
    original = deepcopy(cfg)

    svc = podman_services.podman_service_normalize(cfg, "portable")

    assert svc["container"]["host"] == "podman01"
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
