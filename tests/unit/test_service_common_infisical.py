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


def test_valid_map_keeps_lookup_config_separate_from_legacy_docker_declaration():
    normalized = service_common.service_common_infisical_normalize(valid_map(), "false")

    assert normalized["secrets_map"] == [
        {"var": "postgres_user", "path": "/Postgres", "name": "USER"},
        {"var": "postgres_pass", "path": "/Postgres", "name": "PASS"},
    ]
    assert normalized["fail_on_empty"] is False
    assert normalized["secret_declarations"] == [
        {
            "name": "postgres_pass_secret",
            "var": "postgres_pass",
            "target": "/run/secrets/postgres_pass_secret",
            "runtime_options": {},
            "origins": ["legacy_docker_secret"],
        }
    ]


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


@pytest.mark.parametrize("value", [None, "", "   ", 0, False, [], {}])
def test_check_mode_value_must_be_a_non_empty_string(value):
    entry = {"var": "zone", "path": "/Cloudflare", "name": "ZONE", "check_mode_value": value}

    with pytest.raises(AnsibleFilterError, match=r"\.check_mode_value must be a non-empty string"):
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


def canonical_map():
    return [
        {
            "var": "postgres_pass",
            "path": "/Postgres",
            "name": "PASS",
            "secret": {
                "name": "postgres_pass_secret",
                "target": "/run/secrets/postgres_pass_secret",
                "uid": "1000",
                "gid": "1000",
                "mode": "0400",
                "runtime_options": {
                    "podman": {
                        "immutable": False,
                        "replace": True,
                    }
                },
            },
        },
        {"var": "template_token", "path": "/App", "name": "TOKEN"},
    ]


def test_canonical_declaration_normalizes_and_lookup_only_stays_lookup_only():
    normalized = service_common.service_common_infisical_normalize(canonical_map())

    assert normalized["secrets_map"] == [
        {"var": "postgres_pass", "path": "/Postgres", "name": "PASS"},
        {"var": "template_token", "path": "/App", "name": "TOKEN"},
    ]
    assert normalized["secret_declarations"] == [
        {
            "name": "postgres_pass_secret",
            "var": "postgres_pass",
            "target": "/run/secrets/postgres_pass_secret",
            "uid": "1000",
            "gid": "1000",
            "mode": "0400",
            "runtime_options": {"podman": {"immutable": False, "replace": True}},
            "origins": ["canonical"],
        }
    ]
    assert "value" not in normalized["secret_declarations"][0]


def test_canonical_target_defaults_to_runtime_secret_path():
    entry = canonical_map()[0]
    del entry["secret"]["target"]

    normalized = service_common.service_common_infisical_normalize([entry])

    assert normalized["secret_declarations"][0]["target"] == "/run/secrets/postgres_pass_secret"


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("name", "", "non-empty string"),
        ("name", "bad/name", "resource name"),
        ("target", "relative", "absolute path"),
        ("uid", 1000, "numeric string"),
        ("uid", "-1", "numeric string"),
        ("gid", "user", "numeric string"),
        ("mode", 0o400, "quoted four-digit octal"),
        ("mode", "400", "quoted four-digit octal"),
        ("mode", "0988", "quoted four-digit octal"),
    ],
)
def test_canonical_secret_scalar_validation_is_strict(field, value, match):
    entry = canonical_map()[0]
    entry["secret"][field] = value

    with pytest.raises(AnsibleFilterError, match=match):
        service_common.service_common_infisical_normalize([entry])


@pytest.mark.parametrize(
    ("runtime_options", "match"),
    [
        ([], "runtime_options must be a mapping"),
        ({"docker": {}}, "unsupported runtimes"),
        ({"podman": []}, "podman must be a mapping"),
        ({"podman": {"unsupported": True}}, "unsupported fields"),
        ({"podman": {"immutable": "sometimes"}}, "strict boolean"),
        ({"podman": {"replace": 2}}, "boolean or integer"),
        ({"podman": {"immutable": True, "replace": True}}, "both immutable and replace"),
    ],
)
def test_canonical_runtime_options_are_strict(runtime_options, match):
    entry = canonical_map()[0]
    entry["secret"]["runtime_options"] = runtime_options

    with pytest.raises(AnsibleFilterError, match=match):
        service_common.service_common_infisical_normalize([entry])


def test_equivalent_canonical_and_legacy_docker_forms_deduplicate():
    entry = canonical_map()[0]
    entry["docker_secret"] = "postgres_pass_secret"

    normalized = service_common.service_common_infisical_normalize(
        [entry],
        legacy_docker_secrets=[
            {
                "source": "postgres_pass_secret",
                "target": "postgres_pass_secret",
                "uid": "1000",
                "gid": "1000",
                "mode": "0400",
            }
        ],
    )

    declaration = normalized["secret_declarations"][0]
    assert len(normalized["secret_declarations"]) == 1
    assert declaration["origins"] == [
        "canonical",
        "legacy_docker_secret",
        "legacy_docker_attachment",
    ]


def test_conflicting_canonical_and_legacy_docker_forms_fail():
    with pytest.raises(AnsibleFilterError, match="target differs"):
        service_common.service_common_infisical_normalize(
            canonical_map()[:1],
            legacy_docker_secrets=[
                {
                    "source": "postgres_pass_secret",
                    "target": "different",
                }
            ],
        )


def test_duplicate_secret_name_with_different_vars_fails():
    entries = canonical_map()[:1] + [
        {
            "var": "other",
            "path": "/Other",
            "name": "VALUE",
            "secret": {"name": "postgres_pass_secret"},
        }
    ]

    with pytest.raises(AnsibleFilterError, match="var differs"):
        service_common.service_common_infisical_normalize(entries)


def test_legacy_podman_secret_is_normalized_to_common_declaration():
    normalized = service_common.service_common_infisical_normalize(
        [],
        legacy_podman_secrets=[
            {
                "name": "legacy_secret",
                "infisical_path": "/Legacy",
                "infisical_key": "VALUE",
                "target": "/run/secrets/legacy_secret",
                "uid": "1000",
                "gid": "1000",
                "mode": "0400",
                "immutable": True,
                "replace": False,
            }
        ],
    )

    assert normalized["secrets_map"] == [{"var": "legacy_secret", "path": "/Legacy", "name": "VALUE"}]
    assert normalized["secret_declarations"][0]["var"] == "legacy_secret"
    assert normalized["secret_declarations"][0]["runtime_options"] == {"podman": {"immutable": True, "replace": False}}


def test_metadata_never_contains_secret_values():
    marker = "do-not-render-this-secret"
    normalized = service_common.service_common_infisical_normalize(canonical_map())

    assert marker not in repr(normalized)
    values = service_common.service_common_infisical_finalize(
        {"postgres_pass": marker, "template_token": "lookup-only"},
        normalized,
    )
    assert values["postgres_pass"] == marker
    assert marker not in repr(normalized["secret_declarations"])


def test_real_docker_legacy_secret_selection_is_preserved():
    selection_count = 0
    for path in sorted(Path("ansible/group_vars/all/services").glob("*.yml")):
        services = yaml.safe_load(path.read_text()) or {}
        for infisical in iter_infisical_declarations(services):
            expected = [
                (entry["docker_secret"].strip(), entry["var"].strip())
                for entry in infisical["secrets_map"]
                if isinstance(entry, dict) and entry.get("docker_secret")
            ]
            normalized = service_common.service_common_infisical_normalize(
                infisical["secrets_map"],
                infisical.get("fail_on_empty", True),
            )
            actual = [
                (entry["name"], entry["var"]) for entry in normalized["secret_declarations"] if "legacy_docker_secret" in entry["origins"]
            ]
            assert actual == expected
            selection_count += len(expected)

    assert selection_count > 0


def test_unsupported_lookup_and_secret_fields_are_rejected():
    bad_lookup = canonical_map()[0]
    bad_lookup["unsupported"] = True
    bad_secret = canonical_map()[0]
    bad_secret["secret"]["unsupported"] = True

    with pytest.raises(AnsibleFilterError, match="unsupported fields"):
        service_common.service_common_infisical_normalize([bad_lookup])
    with pytest.raises(AnsibleFilterError, match="unsupported fields"):
        service_common.service_common_infisical_normalize([bad_secret])


def environment_config(*variables, fail_on_empty=True):
    return service_common.service_common_infisical_normalize(
        [{"var": variable, "path": "/Environment", "name": variable.upper()} for variable in variables],
        fail_on_empty,
    )


def test_environment_scalar_literals_and_null_are_preserved_deterministically():
    config = environment_config()
    environment = {
        "TEXT": 'value:with quotes "and JSON"',
        "COUNT": 2,
        "ENABLED": True,
        "EMPTY": None,
    }

    first = service_common.service_common_environment_resolve(environment, {}, config)
    second = service_common.service_common_environment_resolve(environment, {}, config)

    assert first == environment
    assert second == first
    assert list(first) == list(environment)


def test_environment_rejects_invalid_key_and_complex_literal():
    config = environment_config()

    with pytest.raises(AnsibleFilterError, match="must match"):
        service_common.service_common_environment_normalize({"BAD-KEY": "value"}, config)
    with pytest.raises(AnsibleFilterError, match="supported typed mapping"):
        service_common.service_common_environment_normalize({"STRUCTURED": ["not", "scalar"]}, config)


def test_environment_direct_infisical_value_resolves():
    config = environment_config("application_value")
    environment = {"APPLICATION_VALUE": {"value_from": {"infisical": "application_value"}}}

    assert service_common.service_common_environment_resolve(
        environment,
        {"application_value": "resolved-config"},
        config,
    ) == {"APPLICATION_VALUE": "resolved-config"}


def test_environment_template_resolves_one_multiple_repeated_and_mixed_references():
    config = environment_config("zone", "suffix")
    environment = {
        "ONE": {"value_template": "app.${zone}"},
        "MULTIPLE": {"value_template": "https://app.${zone}/${suffix}"},
        "REPEATED": {"value_template": "${zone}:${zone}"},
        "MIXED": {"value_template": 'prefix:{"zone":"${zone}"}:suffix'},
    }

    assert service_common.service_common_environment_resolve(
        environment,
        {"zone": "example.test", "suffix": "api"},
        config,
    ) == {
        "ONE": "app.example.test",
        "MULTIPLE": "https://app.example.test/api",
        "REPEATED": "example.test:example.test",
        "MIXED": 'prefix:{"zone":"example.test"}:suffix',
    }


def test_environment_template_double_dollar_is_a_literal_dollar():
    config = environment_config("zone")

    resolved = service_common.service_common_environment_resolve(
        {"PRICE": {"value_template": "cost=$$5 at ${zone}"}},
        {"zone": "example.test"},
        config,
    )

    assert resolved == {"PRICE": "cost=$5 at example.test"}


@pytest.mark.parametrize("template", ["${", "${}", "${bad-name}", "$zone", "trailing$"])
def test_environment_template_rejects_malformed_references(template):
    config = environment_config("zone")

    with pytest.raises(AnsibleFilterError):
        service_common.service_common_environment_normalize({"VALUE": {"value_template": template}}, config)


def test_environment_rejects_unknown_fields_unsupported_sources_and_conflicting_forms():
    config = environment_config("zone")

    with pytest.raises(AnsibleFilterError, match="unsupported fields"):
        service_common.service_common_environment_normalize({"VALUE": {"unknown": "zone"}}, config)
    with pytest.raises(AnsibleFilterError, match="unsupported sources"):
        service_common.service_common_environment_normalize(
            {"VALUE": {"value_from": {"vault": "zone"}}},
            config,
        )
    with pytest.raises(AnsibleFilterError, match="both value_from and value_template"):
        service_common.service_common_environment_normalize(
            {
                "VALUE": {
                    "value_from": {"infisical": "zone"},
                    "value_template": "${zone}",
                }
            },
            config,
        )


def test_environment_rejects_invalid_and_undeclared_identifiers():
    config = environment_config("zone")

    with pytest.raises(AnsibleFilterError, match="must match"):
        service_common.service_common_environment_normalize(
            {"VALUE": {"value_from": {"infisical": "bad-name"}}},
            config,
        )
    with pytest.raises(AnsibleFilterError, match="undeclared Infisical var"):
        service_common.service_common_environment_normalize(
            {"VALUE": {"value_template": "${missing}"}},
            config,
        )
    with pytest.raises(AnsibleFilterError, match="must match"):
        service_common.service_common_infisical_normalize([{"var": "bad-name", "path": "/App", "name": "VALUE"}])


def test_environment_rejects_declared_reference_without_fetched_value():
    config = environment_config("zone")

    with pytest.raises(AnsibleFilterError, match="no fetched value is available"):
        service_common.service_common_environment_resolve(
            {"VALUE": {"value_from": {"infisical": "zone"}}},
            {},
            config,
        )


def test_environment_empty_reference_obeys_both_fail_on_empty_policies():
    required = environment_config("zone", fail_on_empty=True)
    optional = environment_config("zone", fail_on_empty=False)
    environment = {"VALUE": {"value_from": {"infisical": "zone"}}}

    with pytest.raises(AnsibleFilterError, match="empty value"):
        service_common.service_common_environment_resolve(environment, {"zone": ""}, required)
    assert service_common.service_common_environment_resolve(environment, {"zone": ""}, optional) == {"VALUE": ""}
    assert service_common.service_common_environment_resolve(environment, {"zone": None}, optional) == {"VALUE": None}


def test_environment_substitution_does_not_recursively_expand_fetched_values():
    config = environment_config("zone", "other")

    resolved = service_common.service_common_environment_resolve(
        {"VALUE": {"value_template": "prefix-${zone}"}},
        {"zone": "${other}", "other": "must-not-appear"},
        config,
    )

    assert resolved == {"VALUE": "prefix-${other}"}


def test_environment_resolution_is_isolated_between_services():
    first_config = environment_config("first")
    second_config = environment_config()

    first = service_common.service_common_environment_resolve(
        {"VALUE": {"value_from": {"infisical": "first"}}},
        {"first": "first-service"},
        first_config,
    )
    second = service_common.service_common_environment_resolve({"VALUE": "second-service"}, {}, second_config)

    assert first == {"VALUE": "first-service"}
    assert second == {"VALUE": "second-service"}


def test_check_mode_values_use_explicit_standin_and_default_redaction():
    config = service_common.service_common_infisical_normalize(
        [
            {
                "var": "cloudflare_zone",
                "path": "/Cloudflare",
                "name": "ZONE",
                "check_mode_value": "check-mode.invalid",
            },
            {"var": "token", "path": "/App", "name": "TOKEN"},
        ]
    )

    first = service_common.service_common_infisical_check_values(config)
    second = service_common.service_common_infisical_check_values(config)

    assert (
        first
        == second
        == {
            "cloudflare_zone": "check-mode.invalid",
            "token": "__CHECK_MODE_REDACTED_INFISICAL_token__",
        }
    )
    assert service_common.service_common_environment_resolve(
        {"HOST": {"value_template": "app.${cloudflare_zone}"}},
        first,
        config,
    ) == {"HOST": "app.check-mode.invalid"}


def test_check_mode_value_metadata_does_not_change_live_finalization():
    config = service_common.service_common_infisical_normalize(
        [
            {
                "var": "cloudflare_zone",
                "path": "/Cloudflare",
                "name": "ZONE",
                "check_mode_value": "check-mode.invalid",
            }
        ]
    )

    assert service_common.service_common_infisical_finalize(
        {"cloudflare_zone": "live.example"},
        config,
    ) == {"cloudflare_zone": "live.example"}
