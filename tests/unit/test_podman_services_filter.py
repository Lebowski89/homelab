import importlib.util
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
        "container": {"image": "docker.io/n8nio/n8n:2.31.4", "ports": [{"host": 5678, "container": 5678}]},
        "host_paths": [{"path": "/opt/n8n"}],
        "secrets": [{"name": "postgres_user_secret", "infisical_path": "/Postgres", "infisical_key": "USER"}],
    }


def test_normalize_accepts_n8n_like_service():
    svc = podman_services.podman_service_normalize(valid_cfg(), "n8n")
    assert svc["image"] == "docker.io/n8nio/n8n:2.31.4"
    assert svc["secrets"][0]["name"] == "postgres_user_secret"


@pytest.mark.parametrize("image", ["docker.io/n8nio/n8n:latest", "docker.io/n8nio/n8n", ""])
def test_image_must_be_exact_non_latest(image):
    cfg = valid_cfg()
    cfg["container"]["image"] = image
    with pytest.raises(AnsibleFilterError, match="exact, non-latest"):
        podman_services.podman_service_normalize(cfg, "n8n")


def test_unsafe_path_fails():
    cfg = valid_cfg()
    cfg["host_paths"] = [{"path": "/root/.ssh"}]
    with pytest.raises(AnsibleFilterError, match="/opt"):
        podman_services.podman_service_normalize(cfg, "n8n")


def test_bad_secret_fails():
    cfg = valid_cfg()
    cfg["secrets"] = [{"name": "x"}]
    with pytest.raises(AnsibleFilterError, match="infisical"):
        podman_services.podman_service_normalize(cfg, "n8n")


def test_immutable_secret_cannot_be_replaceable():
    cfg = valid_cfg()
    cfg["secrets"] = [
        {
            "name": "n8n_encryption_key_secret",
            "infisical_path": "/N8N",
            "infisical_key": "ENCRYPTION_KEY",
            "immutable": True,
            "replace": True,
        }
    ]
    with pytest.raises(AnsibleFilterError, match="immutable"):
        podman_services.podman_service_normalize(cfg, "n8n")


def test_volume_requires_target():
    cfg = valid_cfg()
    cfg["volumes"] = [{"name": "n8n-data"}]
    with pytest.raises(AnsibleFilterError, match=r"volumes\[0\]\.target"):
        podman_services.podman_service_normalize(cfg, "n8n")


def test_container_user_string_rejected():
    cfg = valid_cfg()
    cfg["container"]["user"] = "1000:1000"
    with pytest.raises(AnsibleFilterError, match="container.user"):
        podman_services.podman_service_normalize(cfg, "n8n")


def test_container_uid_gid_must_be_numeric():
    cfg = valid_cfg()
    cfg["container"]["uid"] = "abc"
    cfg["container"]["gid"] = "1000"
    with pytest.raises(AnsibleFilterError, match="numeric"):
        podman_services.podman_service_normalize(cfg, "n8n")


def test_managed_network_must_be_dedicated_delete_on_stop():
    cfg = valid_cfg()
    cfg["network"] = {"name": "shared", "driver": "bridge", "delete_on_stop": False}
    with pytest.raises(AnsibleFilterError, match="dedicated"):
        podman_services.podman_service_normalize(cfg, "sharedsvc")


def test_dedicated_managed_network_is_accepted():
    cfg = valid_cfg()
    cfg["network"] = {"name": "dedicated", "driver": "bridge", "delete_on_stop": True}
    svc = podman_services.podman_service_normalize(cfg, "dedicatedsvc")
    assert svc["network"]["delete_on_stop"] is True


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


def test_secret_policy_deploy_preserves_existing_secret():
    policy = podman_services.podman_secret_policy({"replace": True}, "deploy")
    assert policy == {"force": False, "skip_existing": True}


def test_secret_policy_update_replaces_mutable_secret():
    policy = podman_services.podman_secret_policy({"replace": True}, "update")
    assert policy == {"force": True, "skip_existing": False}


def test_secret_policy_recreate_preserves_immutable_secret():
    policy = podman_services.podman_secret_policy({"replace": False}, "recreate")
    assert policy == {"force": False, "skip_existing": True}


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
    "cfg",
    [
        {
            "runtime": "podman",
            "image": "ghcr.io/example/portable:1.2.3",
            "container": {"image": "ghcr.io/example/portable:1.2.4"},
        },
        {
            "runtime": "podman",
            "image": "ghcr.io/example/portable:1.2.3",
            "environment": {"MODE": "canonical"},
            "env": {"MODE": "legacy"},
        },
        {
            "runtime": "podman",
            "image": "ghcr.io/example/portable:1.2.3",
            "user": "1000:1000",
            "container": {"uid": "1001", "gid": "1000"},
        },
        {
            "runtime": "podman",
            "image": "ghcr.io/example/portable:1.2.3",
            "deploy": {"host": "podman01"},
            "container": {"host": "podman02"},
        },
        {
            "runtime": "podman",
            "image": "ghcr.io/example/portable:1.2.3",
            "ports": [{"published": 8080, "target": 80}],
            "container": {"ports": [{"host": 8081, "container": 80}]},
        },
        {
            "runtime": "podman",
            "image": "ghcr.io/example/portable:1.2.3",
            "paths": [{"path": "/opt/portable"}],
            "host_paths": [{"path": "/opt/other"}],
        },
        {
            "runtime": "podman",
            "image": "ghcr.io/example/portable:1.2.3",
            "volumes": [{"type": "bind", "source": "/opt/portable", "target": "/data"}],
            "container": {"mounts": [{"source": "/opt/other", "target": "/data"}]},
        },
        {
            "runtime": "podman",
            "image": "ghcr.io/example/portable:1.2.3",
            "cap_drop": ["ALL"],
            "container": {"cap_drop": ["NET_RAW"]},
        },
        {
            "runtime": "podman",
            "image": "ghcr.io/example/portable:1.2.3",
            "read_only": True,
            "container": {"read_only": False},
        },
        {
            "runtime": "podman",
            "image": "ghcr.io/example/portable:1.2.3",
            "healthcheck": {"test": "true"},
            "container": {"healthcheck": {"command": "false"}},
        },
    ],
)
def test_conflicting_canonical_and_legacy_declarations_fail(cfg):
    with pytest.raises(AnsibleFilterError, match="Conflicting declarations"):
        podman_services.podman_service_normalize(cfg, "portable")


def test_equivalent_canonical_and_legacy_declarations_are_accepted():
    cfg = {
        "runtime": "podman",
        "image": "ghcr.io/example/portable:1.2.3",
        "user": "1000:1000",
        "ports": [{"published": "8080", "target": "80"}],
        "container": {
            "image": "ghcr.io/example/portable:1.2.3",
            "uid": 1000,
            "gid": 1000,
            "ports": [{"host": 8080, "container": 80, "protocol": "tcp"}],
        },
    }

    svc = podman_services.podman_service_normalize(cfg, "portable")

    assert svc["container"]["uid"] == "1000"
    assert svc["container"]["gid"] == "1000"
    assert svc["container"]["ports"] == [{"host": 8080, "container": 80, "protocol": "tcp"}]


def test_mixed_canonical_and_legacy_volume_entries_fail():
    cfg = {
        "runtime": "podman",
        "image": "ghcr.io/example/portable:1.2.3",
        "volumes": [
            {"type": "bind", "source": "/opt/portable", "target": "/data"},
            {"name": "legacy-data", "target": "/legacy"},
        ],
    }

    with pytest.raises(AnsibleFilterError, match="cannot mix"):
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


def test_secret_policy_parses_false_string_strictly():
    assert podman_services.podman_secret_policy({"replace": "false"}, "update") == {
        "force": False,
        "skip_existing": True,
    }


@pytest.mark.parametrize("value", [2, -1, "", "maybe", None])
def test_secret_policy_rejects_invalid_booleans(value):
    with pytest.raises(AnsibleFilterError, match=r"secret\.replace"):
        podman_services.podman_secret_policy({"replace": value}, "update")


def test_secret_and_network_booleans_are_normalized():
    cfg = minimal_canonical_cfg()
    cfg["secrets"] = [
        {
            "name": "portable_secret",
            "infisical_path": "/Portable",
            "infisical_key": "VALUE",
            "immutable": "false",
            "replace": "true",
        }
    ]
    cfg["network"] = {
        "name": "portable",
        "driver": "bridge",
        "delete_on_stop": "true",
    }

    svc = podman_services.podman_service_normalize(cfg, "portable")

    assert svc["secrets"][0]["immutable"] is False
    assert svc["secrets"][0]["replace"] is True
    assert svc["network"]["delete_on_stop"] is True


@pytest.mark.parametrize("field", ["no_new_privileges", "read_only"])
def test_top_level_security_boolean_rejects_integer_two(field):
    cfg = minimal_canonical_cfg()
    cfg[field] = 2

    with pytest.raises(AnsibleFilterError, match=field):
        podman_services.podman_service_normalize(cfg, "portable")


def test_canonical_and_legacy_volume_read_only_values_are_strict_booleans():
    canonical = minimal_canonical_cfg()
    canonical["volumes"] = [
        {
            "type": "bind",
            "source": "/opt/portable",
            "target": "/data",
            "read_only": "false",
        }
    ]
    legacy = valid_cfg()
    legacy["volumes"] = [
        {
            "name": "portable-data",
            "target": "/data",
            "read_only": "false",
        }
    ]

    canonical_svc = podman_services.podman_service_normalize(canonical, "portable")
    legacy_svc = podman_services.podman_service_normalize(legacy, "n8n")

    assert canonical_svc["container"]["mounts"][0]["read_only"] is False
    assert legacy_svc["volumes"][0]["read_only"] is False


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("secret", "immutable"),
        ("secret", "replace"),
        ("network", "delete_on_stop"),
        ("volume", "read_only"),
    ],
)
def test_nested_boolean_fields_reject_integer_two(section, field):
    cfg = minimal_canonical_cfg()
    if section == "secret":
        cfg["secrets"] = [
            {
                "name": "portable_secret",
                "infisical_path": "/Portable",
                "infisical_key": "VALUE",
                field: 2,
            }
        ]
    elif section == "network":
        cfg["network"] = {"name": "portable", field: 2}
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
    cfg["container"]["systemd"] = {"after": after}

    with pytest.raises(AnsibleFilterError, match=r"container\.systemd\.after"):
        podman_services.podman_service_normalize(cfg, "n8n")


def test_systemd_after_is_normalized_when_valid():
    cfg = valid_cfg()
    cfg["container"]["systemd"] = {"after": [" postgresql.service ", "custom.target"]}

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
        ("unit", "../portable", r"container\.name"),
        ("network", "bad/network", r"network\.name"),
        ("named_volume", "../data", r"volumes\[0\]\.source"),
        ("legacy_volume", "bad/volume", r"volumes\[0\]\.name"),
        ("secret", "bad/secret", r"secrets\[0\]\.name"),
    ],
)
def test_quadlet_filename_and_resource_names_are_validated(location, value, match):
    cfg = minimal_canonical_cfg()
    if location == "unit":
        cfg["container"] = {"name": value}
    elif location == "network":
        cfg["network"] = {"name": value, "delete_on_stop": True}
    elif location == "named_volume":
        cfg["volumes"] = [{"type": "volume", "source": value, "target": "/data"}]
    elif location == "legacy_volume":
        cfg = valid_cfg()
        cfg["volumes"] = [{"name": value, "target": "/data"}]
    else:
        cfg["secrets"] = [
            {
                "name": value,
                "infisical_path": "/Portable",
                "infisical_key": "VALUE",
            }
        ]

    with pytest.raises(AnsibleFilterError, match=match):
        podman_services.podman_service_normalize(cfg, "portable")


def test_service_name_used_for_unit_filename_is_validated():
    with pytest.raises(AnsibleFilterError, match="service name"):
        podman_services.podman_service_normalize(minimal_canonical_cfg(), "../portable")


def test_description_conflict_is_rejected():
    cfg = minimal_canonical_cfg()
    cfg["description"] = "Canonical description"
    cfg["container"] = {"description": "Legacy description"}

    with pytest.raises(AnsibleFilterError, match="Conflicting declarations"):
        podman_services.podman_service_normalize(cfg, "portable")


def test_equivalent_canonical_and_legacy_descriptions_are_accepted():
    cfg = minimal_canonical_cfg()
    cfg["description"] = "Portable service"
    cfg["container"] = {"description": "Portable service"}

    svc = podman_services.podman_service_normalize(cfg, "portable")

    assert svc["description"] == "Portable service"


@pytest.mark.parametrize(
    "deploy",
    [
        {"mode": "global", "host": "podman01"},
        {"replicas": 0, "host": "podman01"},
        {"replicas": 2, "host": "podman01"},
        {"placement": {"constraints": ["node.role == worker"]}, "host": "podman01"},
        {"constraints": ["node.labels.zone == internal"], "host": "podman01"},
        {"profile": "standard", "host": "podman01"},
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
    ],
)
def test_supported_single_instance_deploy_forms_are_accepted(deploy):
    cfg = minimal_canonical_cfg()
    cfg["deploy"] = deploy

    svc = podman_services.podman_service_normalize(cfg, "portable")

    assert svc["container"]["host"] == "podman01"


@pytest.mark.parametrize(
    "canonical_volumes",
    [
        [],
        [{"type": "volume", "source": "portable-data", "target": "/data"}],
        [{"type": "tmpfs", "target": "/tmp"}],
    ],
)
def test_canonical_volumes_do_not_silently_combine_with_legacy_mounts(canonical_volumes):
    cfg = minimal_canonical_cfg()
    cfg["volumes"] = canonical_volumes
    cfg["container"] = {
        "mounts": [
            {
                "source": "/opt/legacy",
                "target": "/legacy",
                "read_only": False,
            }
        ]
    }

    with pytest.raises(AnsibleFilterError, match="Conflicting declarations"):
        podman_services.podman_service_normalize(cfg, "portable")


def test_canonical_volumes_without_tmpfs_conflict_with_legacy_tmpfs():
    cfg = minimal_canonical_cfg()
    cfg["volumes"] = [{"type": "bind", "source": "/opt/portable", "target": "/data"}]
    cfg["container"] = {"tmpfs": [{"target": "/tmp", "options": []}]}

    with pytest.raises(AnsibleFilterError, match="Conflicting declarations"):
        podman_services.podman_service_normalize(cfg, "portable")


def test_equivalent_canonical_and_legacy_mount_and_tmpfs_declarations_are_accepted():
    cfg = minimal_canonical_cfg()
    cfg["volumes"] = [
        {
            "type": "bind",
            "source": "/opt/portable",
            "target": "/data",
            "read_only": "false",
        },
        {
            "type": "tmpfs",
            "target": "/tmp",
            "tmpfs": {"size": 1024},
        },
    ]
    cfg["container"] = {
        "mounts": [
            {
                "source": "/opt/portable",
                "target": "/data",
                "read_only": False,
            }
        ],
        "tmpfs": [{"target": "/tmp", "options": ["size=1024"]}],
    }

    svc = podman_services.podman_service_normalize(cfg, "portable")

    assert svc["container"]["mounts"] == cfg["container"]["mounts"]
    assert svc["container"]["tmpfs"] == cfg["container"]["tmpfs"]


def test_legacy_named_volumes_continue_combining_with_legacy_mounts_and_tmpfs():
    cfg = valid_cfg()
    cfg["volumes"] = [{"name": "portable-data", "target": "/data"}]
    cfg["container"]["mounts"] = [
        {
            "source": "/opt/portable",
            "target": "/config",
            "read_only": False,
        }
    ]
    cfg["container"]["tmpfs"] = [{"target": "/tmp", "options": ["size=1024"]}]

    svc = podman_services.podman_service_normalize(cfg, "n8n")

    assert svc["volumes"][0]["name"] == "portable-data"
    assert svc["container"]["mounts"][0]["source"] == "/opt/portable"
    assert svc["container"]["tmpfs"] == [{"target": "/tmp", "options": ["size=1024"]}]


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
                    "runtime_options": {
                        "podman": {
                            "immutable": False,
                            "replace": True,
                        }
                    },
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
    svc = podman_services.podman_service_normalize(canonical_secret_cfg(), "portable")

    assert svc["infisical"]["secrets_map"] == [
        {"var": "portable_secret", "path": "/Portable", "name": "VALUE"},
        {"var": "template_only", "path": "/Portable", "name": "TEMPLATE"},
    ]
    assert svc["secrets"] == [
        {
            "name": "portable_secret",
            "var": "portable_secret",
            "target": "/run/secrets/portable_secret",
            "uid": "1001",
            "gid": "1002",
            "mode": "0400",
            "immutable": False,
            "replace": True,
        }
    ]


def test_equivalent_canonical_and_legacy_podman_secret_deduplicates():
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

    svc = podman_services.podman_service_normalize(cfg, "portable")

    assert len(svc["secrets"]) == 1


def test_conflicting_canonical_and_legacy_podman_secret_fails():
    cfg = canonical_secret_cfg()
    cfg["secrets"] = [
        {
            "name": "portable_secret",
            "infisical_path": "/Portable",
            "infisical_key": "DIFFERENT",
        }
    ]

    with pytest.raises(AnsibleFilterError, match="lookup differs"):
        podman_services.podman_service_normalize(cfg, "portable")


def test_runtime_options_podman_owns_network_and_systemd_policy():
    cfg = minimal_canonical_cfg()
    cfg["runtime_options"] = {
        "podman": {
            "network": {
                "name": "portable",
                "driver": "bridge",
                "delete_on_stop": True,
            },
            "systemd": {
                "after": ["network-online.target"],
                "restart": "on-failure",
                "restart_sec": "15s",
            },
        }
    }

    svc = podman_services.podman_service_normalize(cfg, "portable")

    assert svc["network"]["name"] == "portable"
    assert svc["container"]["systemd"]["restart"] == "on-failure"


def test_conflicting_runtime_options_and_legacy_network_fail():
    cfg = minimal_canonical_cfg()
    cfg["runtime_options"] = {
        "podman": {
            "network": {
                "name": "canonical",
                "delete_on_stop": True,
            }
        }
    }
    cfg["network"] = {"name": "legacy", "delete_on_stop": True}

    with pytest.raises(AnsibleFilterError, match="Conflicting declarations"):
        podman_services.podman_service_normalize(cfg, "portable")


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
