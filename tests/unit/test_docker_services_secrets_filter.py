from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
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


SECRET_TASKS_PATH = Path(__file__).resolve().parents[2] / "ansible/roles/docker_services/tasks/sub_tasks/prep/secrets.yml"


def _rewrite_secret_fixture_path(value):
    production_root = "/opt/stacks/{{ docker_services_stack_name }}/secrets"
    if isinstance(value, dict):
        return {key: _rewrite_secret_fixture_path(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_rewrite_secret_fixture_path(item) for item in value]
    if isinstance(value, str):
        return value.replace(production_root, "{{ synthetic_secret_dir }}")
    return value


def _standalone_materialization_tasks(tmp_path):
    selected_names = {
        "Prep - Secrets | Ensure secrets directory exists on deploy host",
        "Prep - Secrets | Inspect standalone secret paths",
        "Prep - Secrets | Remove incompatible standalone secret paths",
        "Prep - Secrets | Predict file creation after incompatible path repair",
        "Prep - Secrets | Write secret files on deploy host",
        "Prep - Secrets | Enforce secret file ownership and mode",
        "Prep - Secrets | Verify secret paths exist and are files",
        "Prep - Secrets | Fail if any secret path is not a file",
    }
    production_tasks = yaml.safe_load(SECRET_TASKS_PATH.read_text())
    selected = [task for task in production_tasks if task["name"] in selected_names]
    assert {task["name"] for task in selected} == selected_names
    fixture_tasks = tmp_path / "standalone-secret-tasks.yml"
    fixture_tasks.write_text(yaml.safe_dump(_rewrite_secret_fixture_path(selected), sort_keys=False))
    return fixture_tasks


def _run_standalone_secret_fixture(
    tmp_path,
    *,
    initial_kind,
    update_policy,
    check_mode=False,
):
    secret_dir = tmp_path / "secret-files"
    secret_dir.mkdir()
    secret_dir.chmod(0o700)
    secret_path = secret_dir / "synthetic_secret"
    existing_value = "SYNTHETIC_EXISTING_SECRET_VALUE"
    desired_value = "SYNTHETIC_DESIRED_SECRET_VALUE"
    if initial_kind == "file":
        secret_path.write_text(existing_value)
        secret_path.chmod(0o600)
    elif initial_kind == "directory":
        secret_path.mkdir()
    elif initial_kind != "missing":
        raise AssertionError(f"unsupported fixture kind: {initial_kind}")

    inventory = tmp_path / "inventory.yml"
    inventory.write_text(
        yaml.safe_dump(
            {
                "all": {
                    "hosts": {
                        "localhost": {
                            "ansible_connection": "local",
                            "container_host_puid": str(os.getuid()),
                            "container_host_pgid": str(os.getgid()),
                        }
                    }
                }
            },
            sort_keys=False,
        )
    )
    localhost_inventory = yaml.safe_load(inventory.read_text())["all"]["hosts"]["localhost"]
    assert localhost_inventory["container_host_puid"] == str(os.getuid())
    assert localhost_inventory["container_host_pgid"] == str(os.getgid())

    fixture_tasks = _standalone_materialization_tasks(tmp_path)
    playbook = tmp_path / "standalone-secret-playbook.yml"
    playbook.write_text(
        yaml.safe_dump(
            [
                {
                    "name": "Exercise standalone secret file materialization",
                    "hosts": "localhost",
                    "connection": "local",
                    "gather_facts": False,
                    "vars": {
                        "synthetic_secret_dir": str(secret_dir),
                        "docker_services_stack_deploy_type": "container",
                        "docker_services_stack_name": "synthetic",
                        "docker_services_secrets_host_effective": "localhost",
                        "docker_services_common_action": "update",
                        "docker_services_docker_secret_items": [
                            {
                                "name": "synthetic_secret",
                                "var": "synthetic_secret_value",
                                "value": desired_value,
                                "update_policy": update_policy,
                                "mode": "0600",
                            }
                        ],
                    },
                    "tasks": [
                        {
                            "name": "Run production standalone materialization tasks",
                            "ansible.builtin.include_tasks": str(fixture_tasks),
                        }
                    ],
                }
            ],
            sort_keys=False,
        )
    )
    environment = os.environ.copy()
    environment.update(
        {
            "ANSIBLE_CONFIG": str(Path(__file__).resolve().parents[2] / "ansible/ansible.cfg"),
            "ANSIBLE_FILTER_PLUGINS": str(PLUGIN_PATH.parent),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible-local"),
            "ANSIBLE_LOG_PATH": str(tmp_path / "ansible.log"),
            "ANSIBLE_NOCOLOR": "true",
            "ANSIBLE_STDOUT_CALLBACK": "default",
        }
    )
    command = [
        str(Path(sys.executable).with_name("ansible-playbook")),
        "-i",
        str(inventory),
        str(playbook),
    ]
    if check_mode:
        command.append("--check")
    result = subprocess.run(
        command,
        cwd=Path(__file__).resolve().parents[2],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert existing_value not in output
    assert desired_value not in output
    return secret_path, output, existing_value, desired_value


@pytest.mark.parametrize(
    ("initial_kind", "update_policy", "expected"),
    [
        ("file", "preserve", "existing"),
        ("file", "reconcile", "desired"),
        ("directory", "preserve", "desired"),
        ("missing", "preserve", "desired"),
    ],
)
def test_standalone_secret_materialization_preserves_reconciles_and_repairs(
    tmp_path,
    initial_kind,
    update_policy,
    expected,
):
    secret_path, _, existing_value, desired_value = _run_standalone_secret_fixture(
        tmp_path,
        initial_kind=initial_kind,
        update_policy=update_policy,
    )

    assert secret_path.is_file()
    assert secret_path.read_text() == (existing_value if expected == "existing" else desired_value)


@pytest.mark.parametrize(
    ("initial_kind", "update_policy", "predicted_changes"),
    [
        ("file", "preserve", 0),
        ("file", "reconcile", 1),
        ("directory", "preserve", 2),
        ("missing", "preserve", 1),
    ],
)
def test_standalone_secret_check_mode_predicts_without_mutating(
    tmp_path,
    initial_kind,
    update_policy,
    predicted_changes,
):
    secret_path, output, existing_value, _ = _run_standalone_secret_fixture(
        tmp_path,
        initial_kind=initial_kind,
        update_policy=update_policy,
        check_mode=True,
    )

    assert f"changed={predicted_changes}" in output
    if initial_kind == "file":
        assert secret_path.is_file()
        assert secret_path.read_text() == existing_value
    elif initial_kind == "directory":
        assert secret_path.is_dir()
    else:
        assert not secret_path.exists()
