from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from ansible.errors import AnsibleFilterError

PLUGIN_PATH = (
    Path(__file__).resolve().parents[2] / "ansible" / "roles" / "docker_services" / "filter_plugins" / "docker_services_secrets.py"
)
spec = importlib.util.spec_from_file_location("docker_services_secrets", PLUGIN_PATH)
docker_secrets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(docker_secrets)


def canonical_declaration(target="/run/secrets/app_secret"):
    return {
        "name": "app_secret",
        "var": "app_value",
        "target": target,
        "uid": "1000",
        "gid": "1001",
        "mode": "0400",
        "update_policy": "reconcile",
        "origins": ["canonical"],
    }


@pytest.mark.parametrize(
    ("policy", "action", "exists", "materialize", "overwrite"),
    [
        ("preserve", "deploy", False, True, False),
        ("preserve", "deploy", True, False, False),
        ("preserve", "bootstrap", True, False, False),
        ("preserve", "update", True, False, False),
        ("preserve", "recreate", True, False, False),
        ("preserve", "remove", True, False, False),
        ("reconcile", "deploy", False, True, False),
        ("reconcile", "bootstrap", False, True, False),
        ("reconcile", "update", False, True, True),
        ("reconcile", "deploy", True, False, False),
        ("reconcile", "bootstrap", True, False, False),
        ("reconcile", "update", True, True, True),
        ("reconcile", "recreate", True, True, True),
        ("reconcile", "remove", True, False, False),
    ],
)
def test_canonical_policy_drives_swarm_and_standalone_materialization(policy, action, exists, materialize, overwrite):
    declaration = canonical_declaration()
    declaration["update_policy"] = policy

    result = docker_secrets.docker_services_secret_policy(declaration, action, exists)

    assert result["materialize"] is materialize
    assert result["overwrite"] is overwrite
    assert result["reconcile"] is (exists and overwrite)


@pytest.mark.parametrize("policy", [None, True, False, 0, 1, [], {}, "", " reconcile", "Reconcile"])
def test_docker_secret_policy_rejects_invalid_values_without_exposing_data(policy):
    marker = "SYNTHETIC_VALUE_MUST_NOT_APPEAR"
    declaration = {"update_policy": policy, "value": marker}

    with pytest.raises(AnsibleFilterError) as exc_info:
        docker_secrets.docker_services_secret_policy(declaration, "update", True)

    assert marker not in str(exc_info.value)


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ({"rc": 1, "stdout": ""}, {"name": "app_secret", "exists": False, "ansible_managed": False}),
        (
            {"rc": 0, "stdout": '[{"Spec":{"Labels":{"ansible_key":"synthetic-hash"}}}]'},
            {"name": "app_secret", "exists": True, "ansible_managed": True},
        ),
        (
            {"rc": 0, "stdout": '[{"Spec":{"Labels":{"owner":"external"}}}]'},
            {"name": "app_secret", "exists": True, "ansible_managed": False},
        ),
    ],
)
def test_swarm_inspection_classifies_exact_secret_without_values(result, expected):
    assert docker_secrets.docker_services_secret_inspection(result, canonical_declaration()) == expected


def test_swarm_inspection_error_never_echoes_stdout():
    marker = "SYNTHETIC_INSPECTION_TEXT_MUST_NOT_APPEAR"

    with pytest.raises(AnsibleFilterError) as exc_info:
        docker_secrets.docker_services_secret_inspection(
            {"rc": 0, "stdout": marker},
            canonical_declaration(),
        )

    assert marker not in str(exc_info.value)


def test_swarm_canonical_attachment_uses_long_syntax_and_filename_target():
    attachments = docker_secrets.docker_services_secret_attachments(
        [],
        [canonical_declaration()],
        "swarm",
    )

    assert attachments == [
        {
            "source": "app_secret",
            "target": "app_secret",
            "uid": "1000",
            "gid": "1001",
            "mode": "0400",
        }
    ]


def test_swarm_rejects_arbitrary_canonical_target():
    with pytest.raises(AnsibleFilterError, match="directly beneath /run/secrets"):
        docker_secrets.docker_services_secret_attachments(
            [],
            [canonical_declaration("/etc/app_secret")],
            "swarm",
        )


def test_standalone_mapping_entry_becomes_valid_bind_not_stringified_dict():
    attachments = docker_secrets.docker_services_secret_attachments(
        [{"source": "legacy_secret", "target": "/custom/legacy"}],
        [],
        "container",
    )
    mounts = docker_secrets.docker_services_secret_mounts(attachments, "portable")

    assert mounts == [
        {
            "type": "bind",
            "source": "/opt/stacks/portable/secrets/legacy_secret",
            "target": "/custom/legacy",
            "read_only": True,
        }
    ]
    assert "{'source':" not in mounts[0]["source"]


def test_standalone_canonical_attachment_binds_to_absolute_target():
    attachments = docker_secrets.docker_services_secret_attachments(
        [],
        [canonical_declaration("/etc/app/secret")],
        "container",
    )
    mounts = docker_secrets.docker_services_secret_mounts(attachments, "portable")

    assert mounts[0]["source"] == "/opt/stacks/portable/secrets/app_secret"
    assert mounts[0]["target"] == "/etc/app/secret"


def test_legacy_string_attachment_output_is_unchanged():
    assert docker_secrets.docker_services_secret_attachments(
        ["existing_secret"],
        [],
        "swarm",
    ) == ["existing_secret"]


def test_canonical_attachment_upgrades_redundant_legacy_source_with_metadata():
    attachments = docker_secrets.docker_services_secret_attachments(
        ["app_secret"],
        [canonical_declaration()],
        "swarm",
    )

    assert attachments == [
        {
            "source": "app_secret",
            "target": "app_secret",
            "uid": "1000",
            "gid": "1001",
            "mode": "0400",
        }
    ]


def test_metadata_free_canonical_attachment_preserves_legacy_string_render():
    declaration = canonical_declaration()
    for field in ("uid", "gid", "mode"):
        declaration.pop(field)

    attachments = docker_secrets.docker_services_secret_attachments(
        ["app_secret"],
        [declaration],
        "swarm",
    )

    assert attachments == ["app_secret"]


def test_update_policy_stays_out_of_compose_attachment_metadata():
    attachments = docker_secrets.docker_services_secret_attachments(
        [],
        [canonical_declaration()],
        "swarm",
    )

    assert "update_policy" not in repr(attachments)
    assert "immutable" not in repr(attachments)
    assert "replace" not in repr(attachments)
