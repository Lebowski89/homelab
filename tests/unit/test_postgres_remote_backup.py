from __future__ import annotations

import hashlib
import os
import pwd
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml
from ansible.plugins.test.core import version_compare
from jinja2 import Environment, StrictUndefined

REPO_ROOT = Path(__file__).resolve().parents[2]
ROLE_PATH = REPO_ROOT / "ansible/roles/postgres"
DEFAULTS_PATH = ROLE_PATH / "defaults/main.yml"
MAIN_TASKS_PATH = ROLE_PATH / "tasks/main.yml"
REMOTE_SETUP_TASKS_PATH = ROLE_PATH / "tasks/sub_tasks/backup_remote_setup.yml"
REMOTE_ACTION_TASKS_PATH = ROLE_PATH / "tasks/sub_tasks/backup_remote_action.yml"
REMOTE_SECRET_RECONCILE_TASKS_PATH = ROLE_PATH / "tasks/sub_tasks/backup_remote_secret_reconcile.yml"
LOCAL_RUNNER_TEMPLATE_PATH = ROLE_PATH / "templates/postgres-logical-backup.sh.j2"
REMOTE_RUNNER_TEMPLATE_PATH = ROLE_PATH / "templates/postgres-logical-backup-remote.sh.j2"
REMOTE_ENV_TEMPLATE_PATH = ROLE_PATH / "templates/postgres-logical-backup-remote.env.j2"
GROUP_VARS_PATH = REPO_ROOT / "ansible/group_vars/tags_postgres.yml"
PLAYBOOK_PATH = REPO_ROOT / "ansible/playbook.yml"
SKYNET_TEMPLATE_PATH = REPO_ROOT / "ansible/roles/ubuntu/templates/skynet.j2"
SKYNET_DOC_PATH = REPO_ROOT / "docs/cheat_sheets/skynet.md"
BACKUP_DOC_PATH = REPO_ROOT / "docs/postgresql-logical-backups.md"
SYSTEMD_SERVICE_TEMPLATE = REPO_ROOT / "ansible/roles/systemd_jobs/templates/systemd-job.service.j2"
SYSTEMD_TIMER_TEMPLATE = REPO_ROOT / "ansible/roles/systemd_jobs/templates/systemd-job.timer.j2"
ANSIBLE_PLAYBOOK = shutil.which(
    "ansible-playbook",
    path=os.pathsep.join((str(Path(sys.executable).parent), os.environ.get("PATH", ""))),
)
try:
    pwd.getpwnam("postgres")
except KeyError:
    POSTGRES_USER_AVAILABLE = False
else:
    POSTGRES_USER_AVAILABLE = True

REPOSITORY_ID_A = "a" * 64
REPOSITORY_ID_B = "b" * 64


def task_named(tasks: list[dict], name: str) -> dict:
    return next(task for task in tasks if task.get("name") == name)


def render_jinja(path: Path, **variables) -> str:
    environment = Environment(
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    environment.filters["quote"] = lambda value: shlex.quote(str(value))
    return environment.from_string(path.read_text()).render(**variables)


def render_value(value: str, **variables):
    environment = Environment(undefined=StrictUndefined)
    return yaml.safe_load(environment.from_string(value).render(**variables))


def restic_version_is_supported(output: str) -> bool:
    match = re.match(r"^restic ([0-9]+\.[0-9]+\.[0-9]+)(?:[-+~][^ ]+)?(?: |$)", output)
    return match is not None and version_compare(match.group(1), "0.17.1", ">=")


def render_remote_runner(
    tmp_path: Path,
    *,
    options: list[str] | None = None,
    retry_lock: str = "10m",
) -> Path:
    backup_root = tmp_path / "backups"
    state_dir = tmp_path / "state"
    config_dir = tmp_path / "config"
    metrics_file = tmp_path / "textfile" / "postgres_logical_backup_remote.prom"
    for directory in (backup_root, state_dir / "uploaded", config_dir, metrics_file.parent):
        directory.mkdir(parents=True, exist_ok=True)

    repository_file = config_dir / "repository"
    password_file = config_dir / "password"
    environment_file = config_dir / "backend.env"
    repository_file.write_text("local:test-repository\n")
    password_file.write_text("CHECK_MODE_TEST_PASSWORD\n")
    environment_file.write_text("")
    metrics_file.write_text("")

    fake_restic = tmp_path / "fake-restic"
    fake_restic.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf 'CALL' >> "$FAKE_RESTIC_LOG"
printf '\t%s' "$@" >> "$FAKE_RESTIC_LOG"
printf '\n' >> "$FAKE_RESTIC_LOG"

[[ -n "${RESTIC_REPOSITORY_FILE:-}" ]]
[[ -n "${RESTIC_PASSWORD_FILE:-}" ]]

command=''
previous_argument=''
for argument in "$@"; do
  if [[ "$previous_argument" == cat && "$argument" == config ]]; then
    command='cat-config'
    break
  fi
  case "$argument" in
    init|backup|forget) command="$argument"; break ;;
  esac
  previous_argument="$argument"
done

case "$command:${FAKE_RESTIC_MODE:-available}" in
  cat-config:missing|cat-config:missing-init-fail) exit 10 ;;
  cat-config:wrong-password) exit 12 ;;
  cat-config:backend-fail) exit 20 ;;
  cat-config:invalid-json) printf '{invalid json\n' ;;
  cat-config:missing-id) printf '{"version":2}\n' ;;
  cat-config:empty-id) printf '{"version":2,"id":""}\n' ;;
  cat-config:unsafe-id) printf '{"version":2,"id":"../../unsafe"}\n' ;;
  cat-config:*) printf '{"version":2,"id":"%s","chunker_polynomial":"3da3358b4dc173"}\n' "${FAKE_RESTIC_REPOSITORY_ID:-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa}" ;;
  init:missing-init-fail|init:init-fail) exit 21 ;;
  backup:backup-fail) exit 22 ;;
  backup:sleep) sleep 1 ;;
  forget:maintenance-fail) exit 23 ;;
esac
"""
    )
    fake_restic.chmod(0o755)

    script = render_jinja(
        REMOTE_RUNNER_TEMPLATE_PATH,
        postgres_backup_root=str(backup_root),
        postgres_backup_remote_state_dir=str(state_dir),
        postgres_backup_remote_metrics_file=str(metrics_file),
        postgres_backup_remote_restic_path=str(fake_restic),
        postgres_backup_remote_repository_file=str(repository_file),
        postgres_backup_remote_password_file=str(password_file),
        postgres_backup_remote_environment_file=str(environment_file),
        postgres_backup_remote_snapshot_host="pg-cluster",
        postgres_patroni_scope="pg-cluster",
        inventory_hostname="pg95",
        postgres_backup_remote_keep_daily=14,
        postgres_backup_remote_keep_weekly=8,
        postgres_backup_remote_keep_monthly=12,
        postgres_backup_remote_retry_lock=retry_lock,
        postgres_backup_remote_options=options or [],
    )
    script_path = tmp_path / "postgres-logical-backup-remote"
    script_path.write_text(script)
    script_path.chmod(0o755)
    return script_path


def make_completed_backup(
    tmp_path: Path,
    backup_id: str,
    *,
    success: bool = True,
    valid_checksum: bool = True,
) -> Path:
    backup = tmp_path / "backups" / backup_id
    backup.mkdir()
    payload = backup / "payload.txt"
    payload.write_text(f"payload for {backup_id}\n")
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    (backup / "SHA256SUMS").write_text(f"{digest}  payload.txt\n")
    if not valid_checksum:
        payload.write_text("corrupted after checksum\n")
    if success:
        (backup / "SUCCESS").touch()
    return backup


def run_remote(
    script: Path,
    action: str,
    *,
    restic_mode: str = "available",
    repository_id: str = REPOSITORY_ID_A,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "FAKE_RESTIC_LOG": str(script.parent / "restic.log"),
            "FAKE_RESTIC_MODE": restic_mode,
            "FAKE_RESTIC_REPOSITORY_ID": repository_id,
        }
    )
    return subprocess.run(
        [str(script), action],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def restic_log(tmp_path: Path) -> str:
    path = tmp_path / "restic.log"
    return path.read_text() if path.exists() else ""


def run_setup_check(
    tmp_path: Path,
    *,
    remote_manage: bool = False,
    remote_enabled: bool = False,
    repository: str = "",
    backend_environment: dict[str, str] | None = None,
    backend_secrets: list[dict[str, str]] | None = None,
    secret_files: list[dict] | None = None,
    config_dir: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    inventory = tmp_path / "inventory.yml"
    playbook = tmp_path / "remote-backup.yml"
    play_vars = {
        "services_controller_host": "localhost",
        "ansible_facts": {"service_mgr": "systemd"},
        "postgres_backup_remote_manage": remote_manage,
        "postgres_backup_remote_enabled": remote_enabled,
        "postgres_backup_remote_repository": repository,
    }
    if config_dir is not None:
        play_vars.update(
            {
                "postgres_backup_remote_config_dir": str(config_dir),
                "postgres_backup_remote_repository_file": str(config_dir / "repository"),
                "postgres_backup_remote_password_file": str(config_dir / "password"),
                "postgres_backup_remote_environment_file": str(config_dir / "backend.env"),
                "postgres_backup_remote_managed_secret_files_manifest": str(config_dir / ".managed-secret-files"),
            }
        )
    if repository:
        play_vars.update(
            {
                "postgres_backup_remote_backend_environment": (
                    {"SAFE_REGION": "example-region-1"} if backend_environment is None else backend_environment
                ),
                "postgres_backup_remote_backend_secrets": (
                    [{"env": "BACKEND_TOKEN", "path": "/Restic/Postgres", "name": "BACKEND_TOKEN"}]
                    if backend_secrets is None
                    else backend_secrets
                ),
                "postgres_backup_remote_secret_files": (
                    [
                        {
                            "path": str((config_dir or Path("/etc/restic/postgres-logical-backup")) / "backend-key"),
                            "infisical": {"path": "/Restic/Postgres", "name": "BACKEND_KEY"},
                            "mode": "0600",
                        }
                    ]
                    if secret_files is None
                    else secret_files
                ),
                "postgres_backup_remote_options": ["--option", "sftp.command=ssh -i /protected/key"],
            }
        )
    inventory.write_text(
        yaml.safe_dump(
            {
                "all": {
                    "children": {"tags_postgres": {"hosts": {"localhost": {}}}},
                    "hosts": {"localhost": {"ansible_connection": "local"}},
                }
            },
            sort_keys=False,
        )
    )
    playbook.write_text(
        yaml.safe_dump(
            [
                {
                    "name": "Validate disabled PostgreSQL remote backup setup",
                    "hosts": "tags_postgres",
                    "gather_facts": False,
                    "vars": play_vars,
                    "roles": ["postgres"],
                }
            ],
            sort_keys=False,
        )
    )
    environment = os.environ.copy()
    environment.update(
        {
            "ANSIBLE_CONFIG": str(REPO_ROOT / "ansible/ansible.cfg"),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible-local"),
            "ANSIBLE_REMOTE_TEMP": str(tmp_path / "ansible-remote"),
        }
    )
    return subprocess.run(
        [
            ANSIBLE_PLAYBOOK,
            "-i",
            str(inventory),
            str(playbook),
            "--check",
            "--tags",
            "postgres_backup_remote_setup",
        ],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_remote_capability_defaults_are_provider_neutral_and_disabled():
    defaults = yaml.safe_load(DEFAULTS_PATH.read_text())
    group_vars = yaml.safe_load(GROUP_VARS_PATH.read_text())

    assert defaults["postgres_backup_remote_manage"] is False
    assert defaults["postgres_backup_remote_enabled"] is False
    assert defaults["postgres_backup_remote_repository"] == ""
    assert defaults["postgres_backup_remote_backend_environment"] == {}
    assert defaults["postgres_backup_remote_backend_secrets"] == []
    assert defaults["postgres_backup_remote_secret_files"] == []
    assert defaults["postgres_backup_remote_retry_lock"] == "10m"
    assert defaults["postgres_backup_remote_managed_secret_files_manifest"].endswith("/.managed-secret-files")
    assert defaults["postgres_backup_remote_keep_daily"] == 14
    assert defaults["postgres_backup_remote_keep_weekly"] == 8
    assert defaults["postgres_backup_remote_keep_monthly"] == 12
    assert not any(key.startswith("postgres_backup_remote_") for key in group_vars)


@pytest.mark.skipif(ANSIBLE_PLAYBOOK is None, reason="ansible-playbook is unavailable")
def test_disabled_remote_management_does_not_require_a_provider(tmp_path: Path):
    result = run_setup_check(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Remote logical backup | Validate configuration" in result.stdout
    assert "Remote logical backup | Install Restic package" in result.stdout
    assert "skipping: [localhost]" in result.stdout


def test_enabled_scheduling_requires_management_and_repository():
    tasks = yaml.safe_load(REMOTE_SETUP_TASKS_PATH.read_text())
    validation = task_named(tasks, "Remote logical backup | Validate configuration")
    conditions = " ".join(validation["ansible.builtin.assert"]["that"])

    assert "not postgres_backup_remote_enabled or postgres_backup_remote_manage" in conditions
    assert "postgres_backup_remote_repository | trim | length > 0" in conditions


@pytest.mark.skipif(ANSIBLE_PLAYBOOK is None, reason="ansible-playbook is unavailable")
def test_enabled_scheduling_without_repository_is_rejected_before_mutation(tmp_path: Path):
    result = run_setup_check(tmp_path, remote_manage=True, remote_enabled=True)

    assert result.returncode != 0
    assert "PostgreSQL remote logical backup configuration is invalid" in result.stdout
    assert "Remote logical backup | Install Restic package" not in result.stdout


@pytest.mark.skipif(ANSIBLE_PLAYBOOK is None, reason="ansible-playbook is unavailable")
@pytest.mark.skipif(not POSTGRES_USER_AVAILABLE, reason="postgres OS user is unavailable")
def test_configured_check_mode_uses_placeholders_without_live_restic_actions(tmp_path: Path):
    result = run_setup_check(tmp_path, remote_manage=True, repository="local:check-mode-repository")
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "Remote logical backup | Build deterministic check-mode credentials" in output
    assert "Remote logical backup | Resolve repository password through controller Infisical parameters" in output
    assert "Remote logical backup action | Invoke host-local runner" not in output
    assert "Systemd jobs | Render service units" in output


def test_restic_install_and_runner_are_scoped_to_managed_postgres_hosts():
    main_tasks = yaml.safe_load(MAIN_TASKS_PATH.read_text())
    setup_tasks = yaml.safe_load(REMOTE_SETUP_TASKS_PATH.read_text())
    include = task_named(main_tasks, "Configure PostgreSQL remote logical backups")
    install = task_named(setup_tasks, "Remote logical backup | Install Restic package")
    runner = task_named(setup_tasks, "Remote logical backup | Install host-local runner")

    assert include["when"] == "'tags_postgres' in group_names"
    assert "postgres" in include["tags"]
    assert install["when"] == "postgres_backup_remote_manage"
    assert install["ansible.builtin.apt"] == {"name": "restic", "state": "present"}
    assert runner["when"] == "postgres_backup_remote_manage"
    assert runner["ansible.builtin.template"]["dest"] == "{{ postgres_backup_remote_script_path }}"
    assert "restic" not in LOCAL_RUNNER_TEMPLATE_PATH.read_text().lower()


@pytest.mark.parametrize(
    ("output", "supported"),
    [
        ("restic 0.16.5 compiled with go1.22", False),
        ("restic 0.17.0 compiled with go1.23", False),
        ("restic 0.17.1 compiled with go1.23", True),
        ("restic 0.17.1+ds compiled with go1.23", True),
        ("restic 0.18.2 compiled with go1.24", True),
        ("restic 1.0.0 compiled with go1.25", True),
    ],
)
def test_restic_minimum_version_contract(output: str, supported: bool):
    assert restic_version_is_supported(output) is supported


def test_restic_version_is_checked_after_install_and_before_configuration():
    tasks = yaml.safe_load(REMOTE_SETUP_TASKS_PATH.read_text())
    task_names = [task.get("name") for task in tasks]
    install_name = "Remote logical backup | Install Restic package"
    query_name = "Remote logical backup | Query installed Restic version"
    require_name = "Remote logical backup | Require supported Restic version"
    configure_name = "Remote logical backup | Create protected configuration directory"
    query = task_named(tasks, query_name)
    requirement = task_named(tasks, require_name)

    assert task_names.index(install_name) < task_names.index(query_name) < task_names.index(require_name)
    assert task_names.index(require_name) < task_names.index(configure_name)
    assert query["ansible.builtin.command"]["argv"] == ["{{ postgres_backup_remote_restic_path }}", "version"]
    assert query["changed_when"] is False
    assert query["when"] == ["postgres_backup_remote_manage", "not ansible_check_mode"]
    assert "version('0.17.1', '>=')" in " ".join(requirement["ansible.builtin.assert"]["that"])
    assert "Restic 0.17.1 or newer" in requirement["ansible.builtin.assert"]["fail_msg"]
    assert "Minimum supported Restic version is 0.17.1" in BACKUP_DOC_PATH.read_text()


def test_infisical_lookups_use_controller_contract_and_hide_secret_material():
    tasks = yaml.safe_load(REMOTE_SETUP_TASKS_PATH.read_text())
    lookup_names = (
        "Remote logical backup | Resolve repository password through controller Infisical parameters",
        "Remote logical backup | Resolve backend environment secrets through controller",
        "Remote logical backup | Resolve backend secret files through controller",
    )
    write_names = (
        "Remote logical backup | Write repository location",
        "Remote logical backup | Write repository password",
        "Remote logical backup | Write protected backend environment",
        "Remote logical backup | Write protected backend secret files",
    )

    for name in lookup_names:
        task = task_named(tasks, name)
        source = str(task)
        assert task["delegate_to"] == "{{ services_controller_host }}"
        assert "hostvars[services_controller_host].infisical_lookup_default_params" in source
        assert "infisical.vault.read_secrets" in source
        assert "not ansible_check_mode" in task["when"]
        assert task["no_log"] is True
        assert task["diff"] is False

    for name in write_names:
        task = task_named(tasks, name)
        assert task["no_log"] is True
        assert task["diff"] is False


def test_protected_config_state_and_secret_files_have_restrictive_permissions():
    tasks = yaml.safe_load(REMOTE_SETUP_TASKS_PATH.read_text())
    config_dir = task_named(tasks, "Remote logical backup | Create protected configuration directory")
    state_dirs = task_named(tasks, "Remote logical backup | Create protected state directories")

    assert config_dir["ansible.builtin.file"]["owner"] == "root"
    assert config_dir["ansible.builtin.file"]["group"] == "root"
    assert config_dir["ansible.builtin.file"]["mode"] == "0700"
    assert state_dirs["ansible.builtin.file"]["mode"] == "0700"
    for name in (
        "Remote logical backup | Write repository location",
        "Remote logical backup | Write repository password",
        "Remote logical backup | Write protected backend environment",
        "Remote logical backup | Write protected backend secret files",
    ):
        module = next(
            value for key, value in task_named(tasks, name).items() if key in {"ansible.builtin.copy", "ansible.builtin.template"}
        )
        assert module["owner"] == "root"
        assert module["group"] == "root"
        assert module["mode"] == "0600"


def test_managed_secret_manifest_reconciles_only_previously_owned_files(tmp_path: Path):
    tasks = yaml.safe_load(REMOTE_SECRET_RECONCILE_TASKS_PATH.read_text())
    remove = task_named(tasks, "Remote logical backup secret reconciliation | Remove obsolete managed secret files")
    publish = task_named(tasks, "Remote logical backup secret reconciliation | Publish managed-file manifest atomically")
    source = REMOTE_SECRET_RECONCILE_TASKS_PATH.read_text()

    assert "postgres_backup_remote_previous_secret_file_paths" in remove["loop"]
    assert "difference(postgres_backup_remote_desired_secret_file_paths)" in remove["loop"]
    assert remove["ansible.builtin.file"]["state"] == "absent"
    assert publish["ansible.builtin.copy"]["mode"] == "0600"
    assert publish["ansible.builtin.copy"]["unsafe_writes"] is False
    assert "find:" not in source
    assert "rm -rf" not in source

    old_key = tmp_path / "old-key"
    still_desired = tmp_path / "still-desired"
    unrelated = tmp_path / "operator-notes"
    for path in (old_key, still_desired, unrelated):
        path.write_text(path.name)

    previous_managed = {old_key, still_desired}
    desired_managed = {still_desired}
    for obsolete in previous_managed.difference(desired_managed):
        obsolete.unlink()

    assert not old_key.exists()
    assert still_desired.exists()
    assert unrelated.exists()

    new_provider_credentials = tmp_path / "new-provider-credentials"
    new_provider_credentials.write_text("new")
    previous_managed = desired_managed
    desired_managed = {new_provider_credentials}
    for obsolete in previous_managed.difference(desired_managed):
        obsolete.unlink()

    assert not still_desired.exists()
    assert new_provider_credentials.exists()
    assert unrelated.exists()


@pytest.mark.skipif(ANSIBLE_PLAYBOOK is None, reason="ansible-playbook is unavailable")
@pytest.mark.skipif(not POSTGRES_USER_AVAILABLE, reason="postgres OS user is unavailable")
def test_secret_reconciliation_check_mode_plans_without_mutating_files(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    old_key = config_dir / "old-key"
    unrelated = config_dir / "operator-notes"
    manifest = config_dir / ".managed-secret-files"
    old_key.write_text("old")
    unrelated.write_text("operator")
    manifest.write_text(f"{old_key}\n")

    result = run_setup_check(
        tmp_path,
        remote_manage=True,
        repository="local:check-mode-repository",
        backend_environment={},
        backend_secrets=[],
        secret_files=[],
        config_dir=config_dir,
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "Remove obsolete managed secret files" in output
    assert "Publish managed-file manifest atomically" in output
    assert old_key.read_text() == "old"
    assert unrelated.read_text() == "operator"
    assert manifest.read_text() == f"{old_key}\n"


def test_backend_schema_is_shell_safe_and_secret_files_stay_under_config_dir():
    source = REMOTE_SETUP_TASKS_PATH.read_text()
    environment_template = REMOTE_ENV_TEMPLATE_PATH.read_text()

    assert "^[A-Za-z_][A-Za-z0-9_]*$" in source
    assert "dirname == postgres_backup_remote_config_dir" in source
    assert "postgres_backup_remote_secret_file.mode | default('0600') == '0600'" in source
    assert "RESTIC_PASSWORD_FILE" in source
    assert "RESTIC_REPOSITORY_FILE" in source
    assert "| replace" in environment_template


def test_reserved_backend_environment_names_cover_shell_startup_and_loader_controls():
    source = REMOTE_SETUP_TASKS_PATH.read_text()
    for name in (
        "IFS",
        "BASH_ENV",
        "ENV",
        "PATH",
        "SHELLOPTS",
        "BASHOPTS",
        "BASH_XTRACEFD",
        "POSIXLY_CORRECT",
        "LD_PRELOAD",
        "LD_LIBRARY_PATH",
    ):
        assert source.count(f"- {name}") == 2


@pytest.mark.parametrize(
    ("backend_environment", "backend_secrets"),
    [
        ({"IFS": "unsafe"}, []),
        ({}, [{"env": "BASH_XTRACEFD", "path": "/Restic/Postgres", "name": "TRACE_FD"}]),
        ({"POSIXLY_CORRECT": "1"}, []),
    ],
)
@pytest.mark.skipif(ANSIBLE_PLAYBOOK is None, reason="ansible-playbook is unavailable")
def test_reserved_backend_environment_names_are_rejected(
    tmp_path: Path,
    backend_environment: dict[str, str],
    backend_secrets: list[dict[str, str]],
):
    result = run_setup_check(
        tmp_path,
        remote_manage=True,
        repository="local:check-mode-repository",
        backend_environment=backend_environment,
        backend_secrets=backend_secrets,
        secret_files=[],
    )

    assert result.returncode != 0
    assert "must be safe string assignments" in result.stdout or "declarations are invalid" in result.stdout


@pytest.mark.skipif(ANSIBLE_PLAYBOOK is None, reason="ansible-playbook is unavailable")
@pytest.mark.skipif(not POSTGRES_USER_AVAILABLE, reason="postgres OS user is unavailable")
def test_normal_provider_environment_names_remain_allowed(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    result = run_setup_check(
        tmp_path,
        remote_manage=True,
        repository="local:check-mode-repository",
        backend_environment={
            "AWS_DEFAULT_REGION": "example-region-1",
            "B2_ACCOUNT_ID": "example-account",
            "RESTIC_FEATURES": "example-feature",
        },
        backend_secrets=[
            {"env": "AWS_ACCESS_KEY_ID", "path": "/Restic/Postgres", "name": "ACCESS_KEY"},
            {"env": "AWS_SECRET_ACCESS_KEY", "path": "/Restic/Postgres", "name": "SECRET_KEY"},
            {"env": "B2_ACCOUNT_KEY", "path": "/Restic/Postgres", "name": "ACCOUNT_KEY"},
        ],
        secret_files=[],
        config_dir=config_dir,
    )

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("unsafe_name", [".", "..", "sub/../escaped", "sub//escaped"])
@pytest.mark.skipif(ANSIBLE_PLAYBOOK is None, reason="ansible-playbook is unavailable")
def test_unsafe_secret_file_paths_are_rejected(tmp_path: Path, unsafe_name: str):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    result = run_setup_check(
        tmp_path,
        remote_manage=True,
        repository="local:check-mode-repository",
        backend_environment={},
        backend_secrets=[],
        secret_files=[
            {
                "path": f"{config_dir}/{unsafe_name}",
                "infisical": {"path": "/Restic/Postgres", "name": "UNSAFE"},
                "mode": "0600",
            }
        ],
        config_dir=config_dir,
    )

    assert result.returncode != 0
    assert "secret-file declarations are invalid" in result.stdout


def test_backend_environment_template_quotes_values_as_literal_assignments(tmp_path: Path):
    marker = tmp_path / "must-not-exist"
    rendered = render_jinja(
        REMOTE_ENV_TEMPLATE_PATH,
        postgres_backup_remote_resolved_backend_environment={
            "LITERAL_VALUE": f"$(touch {marker})",
            "SAFE_SETTING": "value with spaces",
        },
    )
    environment_file = tmp_path / "backend.env"
    environment_file.write_text(rendered)

    result = subprocess.run(
        [
            "bash",
            "-c",
            'set -a; source "$1"; printf "%s\\n%s\\n" "$SAFE_SETTING" "$LITERAL_VALUE"',
            "--",
            str(environment_file),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines() == ["value with spaces", f"$(touch {marker})"]
    assert not marker.exists()


def test_systemd_jobs_converge_lifecycle_and_maintenance_host_transitions():
    tasks = yaml.safe_load(REMOTE_SETUP_TASKS_PATH.read_text())
    uploader = task_named(tasks, "Remote logical backup | Manage uploader systemd job")
    maintenance = task_named(tasks, "Remote logical backup | Manage maintenance systemd job")
    uploader_job = uploader["vars"]["systemd_jobs"][0]
    maintenance_job = maintenance["vars"]["systemd_jobs"][0]

    assert uploader["ansible.builtin.include_role"]["name"] == "systemd_jobs"
    assert "when" not in uploader
    assert uploader_job["service"]["exec_start"] == "{{ postgres_backup_remote_script_path }} upload"
    assert uploader_job["service"]["user"] == "root"
    assert uploader_job["service"]["group"] == "root"
    assert uploader_job["service"]["wants"] == ["network-online.target"]
    assert uploader_job["service"]["after"] == ["network-online.target"]
    assert (
        render_value(
            uploader_job["enabled"],
            postgres_backup_remote_manage=True,
            postgres_backup_remote_enabled=True,
        )
        is True
    )
    assert (
        render_value(
            uploader_job["enabled"],
            postgres_backup_remote_manage=False,
            postgres_backup_remote_enabled=False,
        )
        is False
    )
    assert maintenance_job["service"]["exec_start"] == "{{ postgres_backup_remote_script_path }} maintenance"
    assert "when" not in maintenance
    assert maintenance_job["service"]["wants"] == ["network-online.target"]
    assert maintenance_job["service"]["after"] == ["network-online.target"]
    first_designation = {
        host: render_value(
            maintenance_job["enabled"],
            postgres_backup_remote_manage=True,
            postgres_backup_remote_enabled=True,
            inventory_hostname=host,
            postgres_backup_remote_maintenance_host="pg95",
        )
        for host in ("pg95", "pg96")
    }
    migrated_designation = {
        host: render_value(
            maintenance_job["enabled"],
            postgres_backup_remote_manage=True,
            postgres_backup_remote_enabled=True,
            inventory_hostname=host,
            postgres_backup_remote_maintenance_host="pg96",
        )
        for host in ("pg95", "pg96")
    }
    assert first_designation == {"pg95": True, "pg96": False}
    assert migrated_designation == {"pg95": False, "pg96": True}
    assert (
        render_value(
            maintenance_job["enabled"],
            postgres_backup_remote_manage=False,
            postgres_backup_remote_enabled=False,
            inventory_hostname="pg95",
            postgres_backup_remote_maintenance_host="pg95",
        )
        is False
    )
    assert "repository" not in str(uploader_job).lower()
    assert "password" not in str(uploader_job).lower()
    assert "secret" not in str(uploader_job).lower()

    for job in (uploader_job, maintenance_job):
        rendered = render_jinja(SYSTEMD_SERVICE_TEMPLATE, systemd_jobs_job=job)
        assert "Wants=network-online.target" in rendered
        assert "After=network-online.target" in rendered


def test_manual_actions_and_check_mode_plans_preserve_operation_boundaries():
    tasks = yaml.safe_load(MAIN_TASKS_PATH.read_text())
    init = task_named(tasks, "Initialize PostgreSQL remote backup repository explicitly")
    upload = task_named(tasks, "Run PostgreSQL remote backup uploader manually")
    maintenance = task_named(tasks, "Run PostgreSQL remote backup maintenance manually")
    check_upload = task_named(tasks, "Report PostgreSQL remote backup upload check-mode plan")
    source = MAIN_TASKS_PATH.read_text()

    assert "postgres_backup_remote_init" in " ".join(init["when"])
    assert "inventory_hostname == postgres_backup_remote_maintenance_host" in init["when"]
    assert "postgres_backup_remote_run" in " ".join(upload["when"])
    assert "inventory_hostname == postgres_backup_remote_maintenance_host" not in upload["when"]
    assert "inventory_hostname == postgres_backup_remote_maintenance_host" in maintenance["when"]
    assert "not ansible_check_mode" in init["when"]
    assert "not ansible_check_mode" in upload["when"]
    assert "not ansible_check_mode" in maintenance["when"]
    assert "ansible_check_mode" in check_upload["when"]
    assert "would upload eligible completed PostgreSQL logical backups" in check_upload["ansible.builtin.debug"]["msg"]
    assert "ansible.builtin.command" not in source


def test_remote_tags_are_wired_through_playbook_skynet_and_docs():
    playbook = PLAYBOOK_PATH.read_text()
    skynet = SKYNET_TEMPLATE_PATH.read_text()
    skynet_docs = SKYNET_DOC_PATH.read_text()
    backup_docs = BACKUP_DOC_PATH.read_text()

    for action in ("setup", "init", "run", "maintenance"):
        tag = f"postgres_backup_remote_{action}"
        command = f"backup-remote-{action}"
        assert tag in playbook
        assert tag in skynet
        assert tag in skynet_docs
        assert tag in backup_docs
        assert command in skynet
        assert command in skynet_docs


def test_only_completed_verified_backups_are_uploaded_with_stable_metadata(tmp_path: Path):
    script = render_remote_runner(tmp_path)
    eligible = make_completed_backup(tmp_path, "20260811T030412Z")
    make_completed_backup(tmp_path, ".staging-20260811T030412Z-123")
    make_completed_backup(tmp_path, "invalid-name")
    make_completed_backup(tmp_path, "20260812T030412Z", success=False)

    result = run_remote(script, "upload")
    log = restic_log(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / f"state/uploaded/{REPOSITORY_ID_A}/20260811T030412Z").is_file()
    assert "backup\t--host\tpg-cluster\t--group-by\thost" in log
    assert "--tag\tpostgres-logical-backup" in log
    assert "--tag\tcluster=pg-cluster" in log
    assert "--tag\tbackup-id=20260811T030412Z" in log
    assert "--tag\tsource-member=pg95" in log
    assert str(eligible) in log
    assert ".staging-" not in next(line for line in log.splitlines() if "\tbackup\t" in line)
    assert "invalid-name" not in log
    metrics = (tmp_path / "textfile/postgres_logical_backup_remote.prom").read_text()
    assert "postgres_backup_remote_last_run_success 1" in metrics
    assert "postgres_backup_remote_last_uploaded_count 1" in metrics
    assert "postgres_backup_remote_pending_count 0" in metrics
    assert not list((tmp_path / "textfile").glob("*.tmp.*"))


def test_checksum_failure_prevents_upload_marker_and_emits_failure_metrics(tmp_path: Path):
    script = render_remote_runner(tmp_path)
    make_completed_backup(tmp_path, "20260811T030412Z", valid_checksum=False)

    result = run_remote(script, "upload")

    assert result.returncode != 0
    assert "Checksum verification failed for backup 20260811T030412Z" in result.stderr
    assert "\tbackup\t" not in restic_log(tmp_path)
    assert not (tmp_path / f"state/uploaded/{REPOSITORY_ID_A}/20260811T030412Z").exists()
    metrics = (tmp_path / "textfile/postgres_logical_backup_remote.prom").read_text()
    assert "postgres_backup_remote_last_run_success 0" in metrics
    assert "postgres_backup_remote_pending_count 1" in metrics


def test_failed_upload_remains_pending_and_retries_successfully(tmp_path: Path):
    script = render_remote_runner(tmp_path)
    make_completed_backup(tmp_path, "20260811T030412Z")
    marker = tmp_path / f"state/uploaded/{REPOSITORY_ID_A}/20260811T030412Z"

    failed = run_remote(script, "upload", restic_mode="backup-fail")
    assert failed.returncode != 0
    assert not marker.exists()

    retried = run_remote(script, "upload")
    assert retried.returncode == 0, retried.stdout + retried.stderr
    assert marker.is_file()
    assert restic_log(tmp_path).count("\tbackup\t") == 2


def test_uploaded_marker_skips_backup_and_preserves_last_upload_timestamp(tmp_path: Path):
    script = render_remote_runner(tmp_path)
    make_completed_backup(tmp_path, "20260811T030412Z")
    marker = tmp_path / f"state/uploaded/{REPOSITORY_ID_A}/20260811T030412Z"
    marker.parent.mkdir()
    marker.touch()
    metrics_file = tmp_path / "textfile/postgres_logical_backup_remote.prom"
    metrics_file.write_text("postgres_backup_remote_last_success_timestamp_seconds 123\n")

    result = run_remote(script, "upload")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "\tbackup\t" not in restic_log(tmp_path)
    metrics = metrics_file.read_text()
    assert "postgres_backup_remote_last_success_timestamp_seconds 123" in metrics
    assert "postgres_backup_remote_last_uploaded_count 0" in metrics
    assert "postgres_backup_remote_pending_count 0" in metrics


def test_same_restic_repository_marker_prevents_duplicate_upload(tmp_path: Path):
    script = render_remote_runner(tmp_path)
    make_completed_backup(tmp_path, "20260811T030412Z")
    marker = tmp_path / f"state/uploaded/{REPOSITORY_ID_A}/20260811T030412Z"

    first = run_remote(script, "upload", repository_id=REPOSITORY_ID_A)
    second = run_remote(script, "upload", repository_id=REPOSITORY_ID_A)

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert marker.is_file()
    assert marker.parent.stat().st_mode & 0o777 == 0o700
    assert restic_log(tmp_path).count("\tcat\tconfig") == 2
    assert restic_log(tmp_path).count("\tbackup\t") == 1


def test_changing_restic_repository_id_reuploads_retained_local_backup_at_same_url(
    tmp_path: Path,
):
    script = render_remote_runner(tmp_path)
    make_completed_backup(tmp_path, "20260811T030412Z")
    repository_file = tmp_path / "config/repository"
    repository_value = repository_file.read_text()
    marker_a = tmp_path / f"state/uploaded/{REPOSITORY_ID_A}/20260811T030412Z"
    marker_b = tmp_path / f"state/uploaded/{REPOSITORY_ID_B}/20260811T030412Z"

    first = run_remote(script, "upload", repository_id=REPOSITORY_ID_A)
    second = run_remote(script, "upload", repository_id=REPOSITORY_ID_B)

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert repository_file.read_text() == repository_value
    assert marker_a.is_file()
    assert marker_b.is_file()
    assert restic_log(tmp_path).count("\tcat\tconfig") == 2
    assert restic_log(tmp_path).count("\tbackup\t") == 2


def test_failed_upload_to_new_repository_preserves_only_old_repository_marker(
    tmp_path: Path,
):
    script = render_remote_runner(tmp_path)
    make_completed_backup(tmp_path, "20260811T030412Z")
    marker_a = tmp_path / f"state/uploaded/{REPOSITORY_ID_A}/20260811T030412Z"
    marker_b = tmp_path / f"state/uploaded/{REPOSITORY_ID_B}/20260811T030412Z"

    first = run_remote(script, "upload", repository_id=REPOSITORY_ID_A)
    failed = run_remote(
        script,
        "upload",
        restic_mode="backup-fail",
        repository_id=REPOSITORY_ID_B,
    )

    assert first.returncode == 0, first.stdout + first.stderr
    assert failed.returncode != 0
    assert marker_a.is_file()
    assert not marker_b.exists()
    assert restic_log(tmp_path).count("\tbackup\t") == 2


@pytest.mark.parametrize(
    "restic_mode",
    ["invalid-json", "missing-id", "empty-id", "unsafe-id"],
)
def test_invalid_restic_repository_identity_fails_before_backup(
    tmp_path: Path,
    restic_mode: str,
):
    script = render_remote_runner(tmp_path)
    make_completed_backup(tmp_path, "20260811T030412Z")

    result = run_remote(script, "upload", restic_mode=restic_mode)

    assert result.returncode != 0
    assert "Restic repository config" in result.stderr
    assert "\tbackup\t" not in restic_log(tmp_path)
    assert not list((tmp_path / "state/uploaded").iterdir())


def test_overlap_lock_skips_cleanly_without_overwriting_metrics(tmp_path: Path):
    script = render_remote_runner(tmp_path)
    make_completed_backup(tmp_path, "20260811T030412Z")
    metrics_file = tmp_path / "textfile/postgres_logical_backup_remote.prom"
    environment = os.environ.copy()
    environment.update(
        {
            "FAKE_RESTIC_LOG": str(tmp_path / "restic.log"),
            "FAKE_RESTIC_MODE": "sleep",
        }
    )
    first = subprocess.Popen(
        [str(script), "upload"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    try:
        for _ in range(100):
            if "\tbackup\t" in restic_log(tmp_path):
                break
            if first.poll() is not None:
                break
            time.sleep(0.02)
        metrics_before_overlap = metrics_file.read_text()
        overlap = run_remote(script, "upload")
        metrics_after_overlap = metrics_file.read_text()
        first_stdout, first_stderr = first.communicate(timeout=10)
    finally:
        if first.poll() is None:
            first.terminate()
            first.wait(timeout=5)

    assert first.returncode == 0, first_stdout + first_stderr
    assert overlap.returncode == 0, overlap.stdout + overlap.stderr
    assert "POSTGRES_BACKUP_REMOTE_RESULT=SKIPPED_OVERLAP" in overlap.stdout
    assert metrics_after_overlap == metrics_before_overlap
    assert restic_log(tmp_path).count("\tbackup\t") == 1


@pytest.mark.parametrize(
    ("restic_mode", "expected_message"),
    [
        ("missing", "is not initialized; run the explicit init action"),
        ("wrong-password", "rejected its password"),
        ("backend-fail", "repository/backend access failed with exit code 20"),
    ],
)
def test_upload_probe_failures_never_initialize_or_upload(
    tmp_path: Path,
    restic_mode: str,
    expected_message: str,
):
    script = render_remote_runner(tmp_path)
    make_completed_backup(tmp_path, "20260811T030412Z")

    result = run_remote(script, "upload", restic_mode=restic_mode)
    log = restic_log(tmp_path)

    assert result.returncode != 0
    assert expected_message in result.stderr
    assert "\tcat\tconfig" in log
    assert "\tinit" not in log
    assert "\tbackup" not in log


def test_repository_initialization_only_initializes_precisely_missing_repository(tmp_path: Path):
    script = render_remote_runner(tmp_path)

    initialized = run_remote(script, "init", restic_mode="missing")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    assert "POSTGRES_BACKUP_REMOTE_RESULT=INITIALIZED" in initialized.stdout
    assert "\tcat\tconfig" in restic_log(tmp_path)
    assert "\tinit" in restic_log(tmp_path)

    (tmp_path / "restic.log").write_text("")
    existing = run_remote(script, "init")
    assert existing.returncode == 0, existing.stdout + existing.stderr
    assert "POSTGRES_BACKUP_REMOTE_RESULT=ALREADY_INITIALIZED" in existing.stdout
    assert "\tcat\tconfig" in restic_log(tmp_path)
    assert "\tinit" not in restic_log(tmp_path)


@pytest.mark.parametrize(
    ("restic_mode", "expected_message"),
    [
        ("wrong-password", "rejected its password; refusing initialization"),
        ("backend-fail", "repository/backend access failed with exit code 20; refusing initialization"),
    ],
)
def test_explicit_init_refuses_wrong_password_and_backend_failures(
    tmp_path: Path,
    restic_mode: str,
    expected_message: str,
):
    script = render_remote_runner(tmp_path)

    result = run_remote(script, "init", restic_mode=restic_mode)
    log = restic_log(tmp_path)

    assert result.returncode != 0
    assert expected_message in result.stderr
    assert "\tcat\tconfig" in log
    assert "\tinit" not in log


def test_explicit_init_failure_is_loud_after_missing_repository_probe(tmp_path: Path):
    script = render_remote_runner(tmp_path)

    result = run_remote(script, "init", restic_mode="missing-init-fail")
    log = restic_log(tmp_path)

    assert result.returncode != 0
    assert "\tcat\tconfig" in log
    assert "\tinit" in log


@pytest.mark.parametrize(
    ("restic_mode", "expected_message"),
    [
        ("missing", "is not initialized; run the explicit init action"),
        ("wrong-password", "rejected its password"),
        ("backend-fail", "repository/backend access failed with exit code 20"),
    ],
)
def test_maintenance_probe_failures_never_initialize_or_forget(
    tmp_path: Path,
    restic_mode: str,
    expected_message: str,
):
    script = render_remote_runner(tmp_path)

    result = run_remote(script, "maintenance", restic_mode=restic_mode)
    log = restic_log(tmp_path)

    assert result.returncode != 0
    assert expected_message in result.stderr
    assert "\tcat\tconfig" in log
    assert "\tinit" not in log
    assert "\tforget" not in log


def test_maintenance_is_scoped_and_uses_configured_retention_without_upload(tmp_path: Path):
    script = render_remote_runner(tmp_path)

    result = run_remote(script, "maintenance")
    log = restic_log(tmp_path)
    forget = next(line for line in log.splitlines() if "\tforget\t" in line)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "--prune" in forget
    assert "--host\tpg-cluster" in forget
    assert "--tag\tpostgres-logical-backup" in forget
    assert "--group-by\thost" in forget
    assert "--keep-daily\t14" in forget
    assert "--keep-weekly\t8" in forget
    assert "--keep-monthly\t12" in forget
    assert "\tbackup\t" not in log
    assert "\tinit" not in log


def test_maintenance_failure_is_loud(tmp_path: Path):
    script = render_remote_runner(tmp_path)

    result = run_remote(script, "maintenance", restic_mode="maintenance-fail")

    assert result.returncode != 0
    assert "maintenance operation failed" in result.stderr


def test_additional_restic_options_are_rendered_as_array_arguments(tmp_path: Path):
    script = render_remote_runner(tmp_path, options=["--option", "sftp.command=ssh -i /protected/key"])

    result = run_remote(script, "init")
    first_call = restic_log(tmp_path).splitlines()[0]

    assert result.returncode == 0, result.stdout + result.stderr
    assert "--option\tsftp.command=ssh -i /protected/key\t--retry-lock\t10m\tcat\tconfig" in first_call
    assert "eval" not in script.read_text()


def test_retry_lock_reaches_probe_backup_and_maintenance(tmp_path: Path):
    script = render_remote_runner(tmp_path, retry_lock="10m")
    make_completed_backup(tmp_path, "20260811T030412Z")

    upload = run_remote(script, "upload")
    assert upload.returncode == 0, upload.stdout + upload.stderr
    upload_calls = restic_log(tmp_path).splitlines()
    assert any("--retry-lock\t10m\tcat\tconfig" in call for call in upload_calls)
    assert any("--retry-lock\t10m\tbackup" in call for call in upload_calls)

    (tmp_path / "restic.log").write_text("")
    maintenance = run_remote(script, "maintenance")
    assert maintenance.returncode == 0, maintenance.stdout + maintenance.stderr
    maintenance_calls = restic_log(tmp_path).splitlines()
    assert any("--retry-lock\t10m\tcat\tconfig" in call for call in maintenance_calls)
    assert any("--retry-lock\t10m\tforget" in call for call in maintenance_calls)


def test_remote_runner_uses_atomic_metrics_and_state_without_touching_local_backups():
    source = REMOTE_RUNNER_TEMPLATE_PATH.read_text()
    upload_function = source.split("upload_backups()", maxsplit=1)[1].split("maintain_repository()", maxsplit=1)[0]

    assert 'mktemp "${METRICS_FILE}.tmp.XXXXXX"' in source
    assert 'mv -f -- "$metrics_tmp" "$METRICS_FILE"' in source
    assert 'mktemp "$REPOSITORY_UPLOADED_DIR/.${backup_id}.XXXXXX"' in source
    assert 'mv -f -- "$MARKER_TMP" "$marker"' in source
    assert "rm -rf" not in source
    assert "run_restic init" not in upload_function


def test_remote_systemd_units_pass_systemd_analyze_verify(tmp_path: Path):
    if shutil.which("systemd-analyze") is None:
        pytest.skip("systemd-analyze is unavailable")
    runner = tmp_path / "postgres-logical-backup-remote"
    runner.write_text("#!/bin/sh\nexit 0\n")
    runner.chmod(0o755)
    job = {
        "name": "postgres-logical-backup-remote",
        "description": "Upload completed PostgreSQL logical backups to Restic",
        "service": {
            "type": "oneshot",
            "exec_start": f"{runner} upload",
            "user": "root",
            "group": "root",
            "working_directory": str(tmp_path),
            "wants": ["network-online.target"],
            "after": ["network-online.target"],
            "nice": 10,
            "io_scheduling_class": "best-effort",
            "io_scheduling_priority": 7,
        },
        "timer": {
            "on_calendar": "*-*-* 04:00:00",
            "randomized_delay_sec": "30m",
            "persistent": True,
        },
        "enabled": False,
    }
    service_path = tmp_path / "postgres-logical-backup-remote.service"
    timer_path = tmp_path / "postgres-logical-backup-remote.timer"
    service_path.write_text(render_jinja(SYSTEMD_SERVICE_TEMPLATE, systemd_jobs_job=job))
    timer_path.write_text(render_jinja(SYSTEMD_TIMER_TEMPLATE, systemd_jobs_job=job))

    result = subprocess.run(
        ["systemd-analyze", "verify", str(service_path), str(timer_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Wants=network-online.target" in service_path.read_text()
    assert "After=network-online.target" in service_path.read_text()


def test_rendered_remote_runner_passes_bash_syntax(tmp_path: Path):
    script = render_remote_runner(tmp_path)

    result = subprocess.run(["bash", "-n", str(script)], check=False, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck is unavailable")
def test_rendered_remote_runner_passes_shellcheck(tmp_path: Path):
    script = render_remote_runner(tmp_path)

    result = subprocess.run(["shellcheck", str(script)], check=False, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
