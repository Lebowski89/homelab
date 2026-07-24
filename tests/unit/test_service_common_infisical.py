import importlib.util
from pathlib import Path

import pytest
import yaml
from ansible.errors import AnsibleFilterError

FILTER_PATH = Path("ansible/roles/service_common/filter_plugins/service_common.py")
spec = importlib.util.spec_from_file_location("service_common", FILTER_PATH)
service_common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service_common)


def valid_map():
    return [
        {"var": "postgres_user", "path": "/Postgres", "name": "USER"},
        {
            "var": "postgres_pass",
            "path": "/Postgres",
            "name": "PASS",
            "docker_secret": "postgres_pass_secret",
        },
    ]


def test_valid_map_normalizes_and_ignores_adapter_metadata():
    normalized = service_common.service_common_infisical_normalize(valid_map(), "false")

    assert normalized == {
        "secrets_map": [
            {"var": "postgres_user", "path": "/Postgres", "name": "USER"},
            {"var": "postgres_pass", "path": "/Postgres", "name": "PASS"},
        ],
        "fail_on_empty": False,
    }


@pytest.mark.parametrize("value", [None, {}, "var", 1, ()])
def test_secrets_map_must_be_a_list(value):
    with pytest.raises(AnsibleFilterError, match="secrets_map must be a list"):
        service_common.service_common_infisical_normalize(value)


def test_every_secrets_map_entry_must_be_a_mapping():
    with pytest.raises(AnsibleFilterError, match=r"secrets_map\[0\] must be a mapping"):
        service_common.service_common_infisical_normalize(["not-a-mapping"])


@pytest.mark.parametrize("field", ["var", "path", "name"])
@pytest.mark.parametrize("value", [None, "", "   ", 42])
def test_required_fields_must_be_non_empty_strings(field, value):
    entry = {"var": "value", "path": "/App", "name": "KEY"}
    entry[field] = value

    with pytest.raises(AnsibleFilterError, match=rf"\.{field} must be a non-empty string"):
        service_common.service_common_infisical_normalize([entry])


def test_duplicate_normalized_var_names_are_rejected():
    secrets_map = [
        {"var": " token ", "path": "/App", "name": "FIRST"},
        {"var": "token", "path": "/App", "name": "SECOND"},
    ]

    with pytest.raises(AnsibleFilterError, match="duplicate Infisical var 'token'"):
        service_common.service_common_infisical_normalize(secrets_map)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, True),
        (False, False),
        (1, True),
        (0, False),
        ("true", True),
        ("YES", True),
        ("on", True),
        ("1", True),
        ("false", False),
        ("NO", False),
        ("off", False),
        ("0", False),
    ],
)
def test_fail_on_empty_uses_strict_boolean_parsing(value, expected):
    normalized = service_common.service_common_infisical_normalize([], value)

    assert normalized["fail_on_empty"] is expected


@pytest.mark.parametrize("value", [None, 2, -1, "", "maybe", [], {}])
def test_fail_on_empty_rejects_non_boolean_values(value):
    with pytest.raises(AnsibleFilterError, match="service_common_infisical_fail_on_empty"):
        service_common.service_common_infisical_normalize([], value)


def iter_infisical_declarations(value):
    if isinstance(value, dict):
        infisical = value.get("infisical")
        if isinstance(infisical, dict) and "secrets_map" in infisical:
            yield infisical
        for child in value.values():
            yield from iter_infisical_declarations(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_infisical_declarations(child)


def test_real_docker_service_declarations_are_accepted_without_yaml_changes():
    declaration_count = 0
    for path in sorted(Path("ansible/group_vars/all/services").glob("*.yml")):
        services = yaml.safe_load(path.read_text()) or {}
        for infisical in iter_infisical_declarations(services):
            service_common.service_common_infisical_normalize(
                infisical["secrets_map"],
                infisical.get("fail_on_empty", True),
            )
            declaration_count += 1

    assert declaration_count > 0


def test_empty_values_fail_when_enabled():
    config = service_common.service_common_infisical_normalize(
        [{"var": "token", "path": "/App", "name": "TOKEN"}],
        True,
    )

    with pytest.raises(AnsibleFilterError, match="empty required secret value"):
        service_common.service_common_infisical_finalize({"token": "  "}, config)


def test_empty_values_are_retained_when_disabled():
    config = service_common.service_common_infisical_normalize(
        [{"var": "token", "path": "/App", "name": "TOKEN"}],
        False,
    )

    assert service_common.service_common_infisical_finalize({"token": ""}, config) == {"token": ""}


def test_finalized_output_contains_only_current_service_keys():
    first = service_common.service_common_infisical_normalize(
        [{"var": "first", "path": "/One", "name": "VALUE"}],
        True,
    )
    second = service_common.service_common_infisical_normalize([], True)

    assert service_common.service_common_infisical_finalize({"first": "one"}, first) == {"first": "one"}
    assert service_common.service_common_infisical_finalize({"first": "stale"}, second) == {}
