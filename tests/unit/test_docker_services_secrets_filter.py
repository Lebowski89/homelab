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
        "runtime_options": {"podman": {"immutable": False, "replace": True}},
        "origins": ["canonical"],
    }


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


def test_podman_only_runtime_options_never_enter_docker_attachment():
    attachments = docker_secrets.docker_services_secret_attachments(
        [],
        [canonical_declaration()],
        "swarm",
    )

    assert "runtime_options" not in repr(attachments)
    assert "immutable" not in repr(attachments)
    assert "replace" not in repr(attachments)
