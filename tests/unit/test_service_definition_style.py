from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_DIR = REPO_ROOT / "ansible/group_vars/all/services"

CANONICAL_SECTIONS = (
    ("enabled", "runtime", "tags", "name", "description", "stack"),
    ("image", "hostname", "container_name", "user", "group", "working_dir", "entrypoint", "command"),
    ("environment", "env_file", "infisical", "secrets", "swarm_configs", "configs", "swarm_env_templates", "settings"),
    ("paths_vault", "application_prepare", "prep"),
    ("depends_on", "named_networks", "ports", "expose", "extra_hosts", "dns"),
    ("paths", "copies", "templates", "named_volumes", "volumes", "tmpfs"),
    (
        "devices",
        "device_cgroup_rules",
        "cgroup",
        "cap_add",
        "cap_drop",
        "security_opt",
        "no_new_privileges",
        "read_only",
        "privileged",
        "sysctls",
        "ulimits",
        "shm_size",
        "shm_tmpfs_size",
    ),
    ("healthcheck",),
    ("traefik", "themepark", "postgres"),
    ("labels", "cleanup", "deploy", "container", "systemd", "runtime_options", "drift"),
    ("targets",),
)
CANONICAL_KEYS = tuple(key for section in CANONICAL_SECTIONS for key in section)
KEY_RANK = {key: index for index, key in enumerate(CANONICAL_KEYS)}
INFISICAL_DECLARATION_KEYS = ("var", "path", "name", "check_mode_value", "secret")
INFISICAL_KEY_RANK = {key: index for index, key in enumerate(INFISICAL_DECLARATION_KEYS)}


def assert_key_order(mapping, *, location):
    assert isinstance(mapping, dict), f"{location}: expected a mapping"
    keys = list(mapping)
    unknown = [key for key in keys if key not in KEY_RANK]
    assert not unknown, f"{location}: unknown immediate keys: {unknown}"

    expected = sorted(keys, key=KEY_RANK.__getitem__)
    assert keys == expected, f"{location}: misordered keys: actual={keys}, expected={expected}"


def assert_infisical_declaration_order(mapping, *, location):
    infisical = mapping.get("infisical", {})
    if not isinstance(infisical, dict):
        return
    secrets_map = infisical.get("secrets_map", [])
    if not isinstance(secrets_map, list):
        return

    for index, declaration in enumerate(secrets_map):
        if not isinstance(declaration, dict):
            continue
        declaration_location = f"{location}.infisical.secrets_map[{index}]"
        keys = list(declaration)
        unknown = [key for key in keys if key not in INFISICAL_KEY_RANK]
        assert not unknown, f"{declaration_location}: unknown declaration keys: {unknown}"
        expected = sorted(keys, key=INFISICAL_KEY_RANK.__getitem__)
        assert keys == expected, f"{declaration_location}: misordered keys: actual={keys}, expected={expected}"


def assert_service_document_style(document, *, filename):
    assert isinstance(document, dict), f"{filename}: expected a service mapping"
    for service_name, service_cfg in document.items():
        location = f"{filename}:{service_name}"
        if isinstance(service_cfg, dict) and "targets" in service_cfg:
            assert list(service_cfg)[-1] == "targets", f"{location}: targets must be the final base key"
        assert_key_order(service_cfg, location=location)
        assert_infisical_declaration_order(service_cfg, location=location)

        targets = service_cfg.get("targets")
        if targets is None:
            continue
        assert isinstance(targets, dict), f"{location}.targets: expected a mapping"
        for target_name, target_cfg in targets.items():
            target_location = f"{location}/{target_name}"
            assert isinstance(target_cfg, dict), f"{target_location}: expected a mapping"
            assert "targets" not in target_cfg, f"{target_location}: nested targets are invalid"
            assert_key_order(target_cfg, location=target_location)
            assert_infisical_declaration_order(target_cfg, location=target_location)


def test_all_repository_service_definitions_follow_canonical_layout():
    paths = sorted(SERVICES_DIR.glob("*.yml"))
    assert paths
    enabled_states = set()

    for path in paths:
        document = yaml.safe_load(path.read_text())
        enabled_states.update(service_cfg.get("enabled") for service_cfg in document.values())
        assert_service_document_style(document, filename=path.name)

    assert enabled_states >= {True, False}


@pytest.mark.parametrize("runtime", ["docker", "podman"])
def test_correctly_ordered_runtime_service_is_accepted(runtime):
    document = {
        "example": {
            "enabled": True,
            "runtime": runtime,
            "tags": ["example"],
            "name": "example",
            "image": "example/image:1.0",
            "environment": {"TZ": "Etc/UTC"},
            "ports": [{"published": 1234, "target": 1234}],
            "volumes": {},
            "healthcheck": {"test": ["CMD", "healthcheck"]},
            "deploy": {"type": "container"},
        }
    }

    assert_service_document_style(document, filename=f"{runtime}.yml")


def test_correctly_ordered_base_plus_target_service_is_accepted():
    document = {
        "example": {
            "enabled": True,
            "runtime": "docker",
            "tags": ["example"],
            "image": "example/image:1.0",
            "environment": {"TZ": "Etc/UTC"},
            "deploy": {"type": "swarm"},
            "targets": {
                "primary": {
                    "tags": ["primary"],
                    "name": "example-primary",
                    "environment": {"INSTANCE": "primary"},
                    "ports": [{"published": 1234, "target": 1234}],
                    "healthcheck": {"test": ["CMD", "healthcheck"]},
                }
            },
        }
    }

    assert_service_document_style(document, filename="targets.yml")


def test_arbitrary_nested_application_mappings_are_not_reordered():
    document = {
        "example": {
            "enabled": True,
            "runtime": "docker",
            "environment": {"runtime": "nested-value", "enabled": "nested-value"},
            "deploy": {"runtime_options": {}, "labels": {}},
        }
    }

    assert_service_document_style(document, filename="nested-data.yml")


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (
            {
                "example": {
                    "enabled": True,
                    "runtime": "docker",
                    "infisical": {},
                    "tags": ["example"],
                }
            },
            "misordered keys",
        ),
        (
            {
                "example": {
                    "enabled": True,
                    "runtime": "docker",
                    "targets": {},
                    "deploy": {"type": "swarm"},
                }
            },
            "targets must be the final base key",
        ),
        (
            {
                "example": {
                    "enabled": True,
                    "runtime": "docker",
                    "targets": {"primary": {"ports": [], "environment": {}}},
                }
            },
            "example/primary: misordered keys",
        ),
        (
            {
                "example": {
                    "enabled": True,
                    "runtime": "docker",
                    "targets": {"primary": {"targets": {}}},
                }
            },
            "nested targets are invalid",
        ),
        (
            {"example": {"enabled": True, "runtime": "docker", "unclassified": True}},
            "unknown immediate keys: ['unclassified']",
        ),
        (
            {
                "example": {
                    "enabled": True,
                    "runtime": "docker",
                    "targets": {"primary": {"unclassified": True}},
                }
            },
            "invalid.yml:example/primary: unknown immediate keys: ['unclassified']",
        ),
    ],
    ids=(
        "infisical-after-runtime",
        "base-key-after-targets",
        "misordered-target",
        "nested-targets",
        "unknown-root-key",
        "unknown-target-key",
    ),
)
def test_invalid_service_layout_is_rejected_clearly(document, message):
    with pytest.raises(AssertionError) as error:
        assert_service_document_style(document, filename="invalid.yml")

    assert message in str(error.value)
