import importlib.util
from pathlib import Path

import pytest
import yaml
from ansible.errors import AnsibleFilterError

REPO_ROOT = Path(__file__).resolve().parents[2]
FILTER_PATH = REPO_ROOT / "ansible/roles/service_common/filter_plugins/service_common.py"
N8N_PATH = REPO_ROOT / "ansible/group_vars/all/services/n8n.yml"
AUTOBRR_PATH = REPO_ROOT / "ansible/group_vars/all/services/autobrr.yml"

spec = importlib.util.spec_from_file_location("service_common_postgres", FILTER_PATH)
service_common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service_common)

LIVE_VALUES = {"postgres_user": "database-user", "postgres_pass": "database-password"}


def normalize(postgres, *, controller="manager", hostvars=None, values=None, check_mode=False):
    return service_common.service_common_postgres_normalize(
        postgres,
        controller,
        {"manager": {"local_ip": "192.0.2.10"}} if hostvars is None else hostvars,
        LIVE_VALUES if values is None else values,
        check_mode,
    )


def test_default_inventory_host_resolves_local_ip_and_defaults():
    result = normalize({"enable": True, "databases": " n8n "})

    assert result == {
        "enable": True,
        "databases": ["n8n"],
        "port": 5432,
        "user_var": "postgres_user",
        "password_var": "postgres_pass",
        "host_inventory": "manager",
        "host": "192.0.2.10",
    }


def test_explicit_inventory_host_resolves_only_selected_local_ip():
    result = normalize(
        {"enable": True, "databases": ["one"], "host_inventory": "postgres-vip"},
        hostvars={
            "manager": {"local_ip": "192.0.2.10"},
            "postgres-vip": {"local_ip": "192.0.2.20"},
            "unrelated": "not-a-host-mapping",
        },
    )

    assert result["host_inventory"] == "postgres-vip"
    assert result["host"] == "192.0.2.20"


def test_explicit_host_does_not_read_inventory_or_controller():
    result = service_common.service_common_postgres_normalize(
        {"enable": True, "databases": ["one"], "host": " db.example.test "},
        None,
        None,
        LIVE_VALUES,
        False,
    )

    assert result["host"] == "db.example.test"
    assert "host_inventory" not in result


def test_host_and_host_inventory_are_mutually_exclusive():
    with pytest.raises(AnsibleFilterError, match="mutually exclusive"):
        normalize(
            {
                "enable": True,
                "databases": ["one"],
                "host": "192.0.2.10",
                "host_inventory": "manager",
            }
        )


@pytest.mark.parametrize(
    ("hostvars", "match"),
    [
        ({}, "not in hostvars"),
        ({"manager": {}}, r"local_ip must be a non-empty string"),
        ({"manager": {"local_ip": "  "}}, r"local_ip must be a non-empty string"),
    ],
)
def test_missing_inventory_host_or_local_ip_fails_clearly(hostvars, match):
    with pytest.raises(AnsibleFilterError, match=match):
        normalize({"enable": True, "databases": ["one"]}, hostvars=hostvars)


@pytest.mark.parametrize("postgres", [None, [], "enabled"])
def test_postgres_must_be_a_mapping(postgres):
    with pytest.raises(AnsibleFilterError, match="postgres must be a mapping"):
        normalize(postgres)


@pytest.mark.parametrize("enable", [None, 2, -1, "", "sometimes", [], {}])
def test_enable_is_a_strict_boolean(enable):
    with pytest.raises(AnsibleFilterError, match=r"postgres\.enable"):
        normalize({"enable": enable})


@pytest.mark.parametrize(
    "databases",
    [None, [], "", "   ", [""], ["one", "  "], ["one", 2], {"one": True}],
)
def test_enabled_databases_must_be_non_empty_strings(databases):
    with pytest.raises(AnsibleFilterError, match="databases"):
        normalize({"enable": True, "databases": databases})


@pytest.mark.parametrize("port", [None, True, "5432", 0, -1, 65536])
def test_port_must_be_an_integer_in_range(port):
    with pytest.raises(AnsibleFilterError, match="integer from 1 through 65535"):
        normalize({"enable": True, "databases": ["one"], "port": port})


@pytest.mark.parametrize("field", ["user_var", "password_var"])
@pytest.mark.parametrize("value", [None, "", "bad-name", "two words", 2])
def test_credential_references_must_be_identifiers(field, value):
    postgres = {"enable": True, "databases": ["one"]}
    postgres[field] = value

    with pytest.raises(AnsibleFilterError, match=field):
        normalize(postgres)


@pytest.mark.parametrize("missing", ["postgres_user", "postgres_pass"])
def test_check_mode_rejects_undeclared_credential_references(missing):
    values = {
        "postgres_user": "__CHECK_MODE_REDACTED_INFISICAL_postgres_user__",
        "postgres_pass": "__CHECK_MODE_REDACTED_INFISICAL_postgres_pass__",
    }
    values.pop(missing)

    with pytest.raises(AnsibleFilterError, match="references undeclared Infisical value"):
        normalize({"enable": True, "databases": ["one"]}, values=values, check_mode=True)


def test_check_mode_accepts_synthetic_values_without_authentication():
    values = {
        "postgres_user": "__CHECK_MODE_REDACTED_INFISICAL_postgres_user__",
        "postgres_pass": "__CHECK_MODE_REDACTED_INFISICAL_postgres_pass__",
    }

    result = normalize({"enable": True, "databases": ["one"]}, values=values, check_mode=True)

    assert result["databases"] == ["one"]
    assert "database-user" not in repr(result)
    assert "database-password" not in repr(result)


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"postgres_user": "user"},
        {"postgres_user": "", "postgres_pass": "password"},
        {"postgres_user": "user", "postgres_pass": "  "},
    ],
)
def test_live_execution_requires_non_empty_common_infisical_values(values):
    with pytest.raises(AnsibleFilterError, match="Infisical value"):
        normalize({"enable": True, "databases": ["one"]}, values=values)


def test_disabled_postgres_does_not_require_inventory_or_credentials():
    result = normalize({"enable": False}, controller="manager", hostvars={}, values={})

    assert result["enable"] is False
    assert result["databases"] == []


def test_real_n8n_postgres_declaration_resolves_with_common_values():
    n8n = yaml.safe_load(N8N_PATH.read_text())["n8n"]
    result = normalize(n8n["postgres"])

    assert result == {
        "enable": True,
        "databases": ["n8n"],
        "port": 5432,
        "user_var": "postgres_user",
        "password_var": "postgres_pass",
        "host_inventory": "manager",
        "host": "192.0.2.10",
    }


def test_real_autobrr_adapter_snapshot_reaches_common_postgres_normalization():
    autobrr = yaml.safe_load(AUTOBRR_PATH.read_text())["autobrr"]
    adapter_values = {
        entry["var"]: f"value-for-{entry['var']}"
        for entry in autobrr["infisical"]["secrets_map"]
    }

    result = normalize(autobrr["postgres"], values=adapter_values)

    assert result["enable"] is True
    assert result["databases"] == ["autobrr"]
    assert result["user_var"] == "postgres_user"
    assert result["password_var"] == "postgres_pass"
    assert {"postgres_user", "postgres_pass"}.issubset(adapter_values)


def test_adapter_reset_prevents_previous_values_satisfying_later_omitted_declaration():
    autobrr = yaml.safe_load(AUTOBRR_PATH.read_text())["autobrr"]
    previous_adapter_values = {
        entry["var"]: f"value-for-{entry['var']}"
        for entry in autobrr["infisical"]["secrets_map"]
    }
    later_service = {
        "infisical": {
            "secrets_map": [
                {
                    "var": "postgres_user",
                    "path": "/Postgres",
                    "name": "USER",
                }
            ]
        },
        "postgres": {
            "enable": True,
            "databases": ["later"],
        },
    }
    later_adapter_values = {
        entry["var"]: f"value-for-{entry['var']}"
        for entry in later_service["infisical"]["secrets_map"]
    }

    assert "postgres_pass" in previous_adapter_values
    assert "postgres_pass" not in later_adapter_values
    with pytest.raises(AnsibleFilterError, match=r"password_var.*postgres_pass"):
        normalize(later_service["postgres"], values=later_adapter_values)
