from __future__ import annotations

import datetime
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, StrictUndefined

REPO_ROOT = Path(__file__).resolve().parents[2]
ROLE_PATH = REPO_ROOT / "ansible/roles/postgres"
DEFAULTS_PATH = ROLE_PATH / "defaults/main.yml"
MAIN_TASKS_PATH = ROLE_PATH / "tasks/main.yml"
SETUP_TASKS_PATH = ROLE_PATH / "tasks/sub_tasks/backup_restore_validation_setup.yml"
ACTION_TASKS_PATH = ROLE_PATH / "tasks/sub_tasks/backup_restore_validation_action.yml"
RUNNER_TEMPLATE_PATH = ROLE_PATH / "templates/postgres-logical-backup-restore-validate.sh.j2"
GROUP_VARS_PATH = REPO_ROOT / "ansible/group_vars/tags_postgres.yml"
PLAYBOOK_PATH = REPO_ROOT / "ansible/playbook.yml"
SKYNET_TEMPLATE_PATH = REPO_ROOT / "ansible/roles/ubuntu/templates/skynet.j2"
SKYNET_DOC_PATH = REPO_ROOT / "docs/cheat_sheets/skynet.md"
BACKUP_DOC_PATH = REPO_ROOT / "docs/postgresql-logical-backups.md"
SYSTEMD_SERVICE_TEMPLATE = REPO_ROOT / "ansible/roles/systemd_jobs/templates/systemd-job.service.j2"
SYSTEMD_TIMER_TEMPLATE = REPO_ROOT / "ansible/roles/systemd_jobs/templates/systemd-job.timer.j2"
SNAPSHOT_ID_A = "a" * 64
SNAPSHOT_ID_B = "b" * 64
BACKUP_ID_A = "20260811T030412Z"
BACKUP_ID_B = "20260812T030412Z"


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


def write_executable(path: Path, source: str) -> None:
    path.write_text(source)
    path.chmod(0o755)


def snapshot(
    backup_root: Path,
    *,
    snapshot_id: str = SNAPSHOT_ID_A,
    backup_id: str = BACKUP_ID_A,
    snapshot_time: datetime.datetime | None = None,
    hostname: str = "pg-cluster",
    tags: list[str] | None = None,
    paths: list[str] | None = None,
) -> dict:
    timestamp = snapshot_time or (datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=10))
    return {
        "time": timestamp.isoformat().replace("+00:00", "Z"),
        "tree": "c" * 64,
        "paths": paths if paths is not None else [f"{backup_root}/{backup_id}"],
        "hostname": hostname,
        "username": "root",
        "uid": 0,
        "gid": 0,
        "tags": (
            tags
            if tags is not None
            else [
                "postgres-logical-backup",
                "cluster=pg-cluster",
                f"backup-id={backup_id}",
                "source-member=pg95",
            ]
        ),
        "id": snapshot_id,
    }


def make_artifact(
    tmp_path: Path,
    *,
    databases: tuple[str, ...] = ("appdb", "postgres"),
) -> Path:
    artifact = tmp_path / "artifact-source"
    dumps = artifact / "databases"
    dumps.mkdir(parents=True)
    for database in databases:
        (dumps / f"{database}.dump").write_text(f"custom archive for {database}\n")
    (artifact / "globals.sql").write_text("-- production globals retained but not executed\n")
    manifest_lines = [
        "start_utc=2026-08-11T03:04:12Z",
        "completion_utc=2026-08-11T03:05:12Z",
        "hostname=pg95",
        "patroni_member=pg95",
        "postgres_server_version=18.0-test",
        "backup_format=custom",
        f"database_count={len(databases)}",
        "globals_captured=yes",
        "archive_verification=pg_restore_list_passed",
        *(f"database={database}\tdump=databases/{database}.dump" for database in databases),
    ]
    (artifact / "manifest.txt").write_text("\n".join(manifest_lines) + "\n")
    rewrite_checksums(artifact)
    (artifact / "SUCCESS").touch()
    return artifact


def rewrite_checksums(artifact: Path) -> None:
    payloads = sorted((artifact / "databases").glob("*.dump"))
    payloads.extend((artifact / "globals.sql", artifact / "manifest.txt"))
    lines = []
    for payload in payloads:
        digest = hashlib.sha256(payload.read_bytes()).hexdigest()
        lines.append(f"{digest}  {payload.relative_to(artifact).as_posix()}")
    (artifact / "SHA256SUMS").write_text("\n".join(lines) + "\n")


def render_validator(
    tmp_path: Path,
    *,
    snapshots: list[dict] | None = None,
    artifact: Path | None = None,
    max_age_hours: int = 48,
    min_free_bytes: int = 0,
) -> Path:
    backup_root = tmp_path / "backups"
    work_root = tmp_path / "work"
    config_dir = tmp_path / "config"
    metrics_file = tmp_path / "textfile/postgres_logical_backup_restore_validation.prom"
    fake_bin = tmp_path / "fake-bin"
    fake_proc = tmp_path / "proc"
    runtime_state = tmp_path / "runtime-state"
    for directory in (
        backup_root,
        work_root,
        config_dir,
        metrics_file.parent,
        fake_bin,
        fake_proc,
        runtime_state,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    (config_dir / "repository").write_text("local:test-repository\n")
    (config_dir / "password").write_text("TEST_REPOSITORY_PASSWORD\n")
    (config_dir / "backend.env").write_text("")
    metrics_file.write_text("")
    artifact = artifact or make_artifact(tmp_path)
    snapshots_file = tmp_path / "snapshots.json"
    snapshots_file.write_text(json.dumps(snapshots or [snapshot(backup_root)]))

    write_executable(
        fake_bin / "restic",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'RESTIC' >> "$FAKE_COMMAND_LOG"
printf '\t%s' "$@" >> "$FAKE_COMMAND_LOG"
printf '\n' >> "$FAKE_COMMAND_LOG"
command=''
previous=''
for argument in "$@"; do
  if [[ "$previous" == cat && "$argument" == config ]]; then command='cat-config'; break; fi
  case "$argument" in snapshots|restore) command="$argument"; break ;; esac
  previous="$argument"
done
case "$command:${FAKE_RESTIC_MODE:-available}" in
  cat-config:missing) exit 10 ;;
  cat-config:wrong-password) exit 12 ;;
  cat-config:backend-fail) exit 20 ;;
  cat-config:*) printf '{"version":2,"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}\n' ;;
  snapshots:snapshots-fail) exit 21 ;;
  snapshots:*) cat "$FAKE_SNAPSHOTS_FILE" ;;
  restore:restore-fail) exit 22 ;;
  restore:*)
    target=''
    previous=''
    for argument in "$@"; do
      if [[ "$previous" == --target ]]; then target="$argument"; break; fi
      previous="$argument"
    done
    [[ -n "$target" ]]
    cp -a "$FAKE_ARTIFACT_SOURCE/." "$target/"
    ;;
esac
""",
    )
    write_executable(
        fake_bin / "runuser",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'RUNUSER' >> "$FAKE_COMMAND_LOG"
printf '\t%s' "$@" >> "$FAKE_COMMAND_LOG"
printf '\n' >> "$FAKE_COMMAND_LOG"
[[ "$1" == -u && "$2" == postgres && "$3" == -- ]]
shift 3
exec "$@"
""",
    )
    write_executable(
        fake_bin / "initdb",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'INITDB' >> "$FAKE_COMMAND_LOG"
printf '\t%s' "$@" >> "$FAKE_COMMAND_LOG"
printf '\n' >> "$FAKE_COMMAND_LOG"
pgdata=''
previous=''
for argument in "$@"; do
  if [[ "$previous" == -D ]]; then pgdata="$argument"; fi
  previous="$argument"
done
[[ -n "$pgdata" ]]
[[ "${FAKE_INITDB_FAIL:-0}" != 1 ]]
: > "$pgdata/postgresql.conf"
""",
    )
    write_executable(
        fake_bin / "pg_ctl",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'PG_CTL' >> "$FAKE_COMMAND_LOG"
printf '\t%s' "$@" >> "$FAKE_COMMAND_LOG"
printf '\n' >> "$FAKE_COMMAND_LOG"
pgdata=''
previous=''
for argument in "$@"; do
  if [[ "$previous" == -D ]]; then pgdata="$argument"; fi
  previous="$argument"
done
[[ -n "$pgdata" ]]
case "$*" in
  *" start")
    [[ "${FAKE_PG_CTL_START_FAIL:-0}" != 1 ]]
    printf '%s\n' "$pgdata" > "$FAKE_RUNTIME_STATE/pgdata"
    sed -n "s/^unix_socket_directories = '\\(.*\\)'$/\\1/p" "$pgdata/postgresql.conf" > "$FAKE_RUNTIME_STATE/socket"
    sed -n 's/^port = //p' "$pgdata/postgresql.conf" > "$FAKE_RUNTIME_STATE/port"
    touch "$pgdata/postmaster.pid"
    ;;
  *" stop")
    [[ "${FAKE_PG_CTL_STOP_FAIL:-0}" != 1 ]]
    if [[ -s "$pgdata/postmaster.pid" ]]; then
      IFS= read -r stopped_pid < "$pgdata/postmaster.pid"
      if [[ "$stopped_pid" =~ ^[1-9][0-9]*$ ]]; then
        rm -rf -- "$FAKE_PROC_ROOT/$stopped_pid"
      fi
    fi
    rm -f "$pgdata/postmaster.pid"
    ;;
  *) exit 2 ;;
esac
""",
    )
    for command in ("createdb", "dropdb"):
        write_executable(
            fake_bin / command,
            f"""#!/usr/bin/env bash
set -euo pipefail
printf '{command.upper()}' >> "$FAKE_COMMAND_LOG"
printf '\t%s' "$@" >> "$FAKE_COMMAND_LOG"
printf '\n' >> "$FAKE_COMMAND_LOG"
""",
        )
    write_executable(
        fake_bin / "pg_restore",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'PG_RESTORE' >> "$FAKE_COMMAND_LOG"
printf '\t%s' "$@" >> "$FAKE_COMMAND_LOG"
printf '\n' >> "$FAKE_COMMAND_LOG"
if [[ -n "${FAKE_PG_RESTORE_SLEEP:-}" ]]; then sleep "$FAKE_PG_RESTORE_SLEEP"; fi
[[ "${FAKE_PG_RESTORE_FAIL:-0}" != 1 ]]
""",
    )
    write_executable(
        fake_bin / "psql",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'PSQL' >> "$FAKE_COMMAND_LOG"
printf '\t%s' "$@" >> "$FAKE_COMMAND_LOG"
printf '\n' >> "$FAKE_COMMAND_LOG"
query=''
for argument in "$@"; do
  case "$argument" in --command=*) query="${argument#*=}" ;; esac
done
case "$query" in
  "SHOW data_directory;")
    if [[ "${FAKE_PSQL_MODE:-safe}" == wrong-data ]]; then printf '/var/lib/postgresql/18/main\n'; else cat "$FAKE_RUNTIME_STATE/pgdata"; fi
    ;;
  "SHOW listen_addresses;")
    if [[ "${FAKE_PSQL_MODE:-safe}" == tcp ]]; then printf '127.0.0.1\n'; else printf '\n'; fi
    ;;
  "SHOW unix_socket_directories;")
    if [[ "${FAKE_PSQL_MODE:-safe}" == wrong-socket ]]; then printf '/var/run/postgresql\n'; else cat "$FAKE_RUNTIME_STATE/socket"; fi
    ;;
  "SHOW port;")
    if [[ "${FAKE_PSQL_MODE:-safe}" == wrong-port ]]; then printf '5432\n'; else cat "$FAKE_RUNTIME_STATE/port"; fi
    ;;
  "SELECT 1;"*)
    [[ "${FAKE_PSQL_MODE:-safe}" != sql-fail ]]
    printf '1\n0\n'
    ;;
  *) exit 3 ;;
esac
""",
    )
    write_executable(
        fake_bin / "install",
        """#!/usr/bin/env bash
set -euo pipefail
printf 'INSTALL' >> "$FAKE_COMMAND_LOG"
printf '\t%s' "$@" >> "$FAKE_COMMAND_LOG"
printf '\n' >> "$FAKE_COMMAND_LOG"
for argument in "$@"; do
  case "$argument" in /*) mkdir -p "$argument" ;; esac
done
""",
    )
    write_executable(fake_bin / "chown", "#!/usr/bin/env bash\nexit 0\n")
    write_executable(fake_bin / "id", "#!/usr/bin/env bash\nprintf '999\\n'\n")
    write_executable(fake_bin / "postgres", "#!/usr/bin/env bash\nexit 0\n")
    write_executable(fake_bin / "sleep", "#!/usr/bin/env bash\nexit 0\n")

    script = render_jinja(
        RUNNER_TEMPLATE_PATH,
        postgres_backup_root=str(backup_root),
        postgres_backup_restore_validation_work_root=str(work_root),
        postgres_backup_restore_validation_metrics_file=str(metrics_file),
        postgres_backup_remote_restic_path=str(fake_bin / "restic"),
        postgres_backup_remote_repository_file=str(config_dir / "repository"),
        postgres_backup_remote_password_file=str(config_dir / "password"),
        postgres_backup_remote_environment_file=str(config_dir / "backend.env"),
        postgres_backup_remote_snapshot_host="pg-cluster",
        postgres_patroni_scope="pg-cluster",
        postgres_patroni_bin_dir=str(fake_bin),
        postgres_backup_remote_retry_lock="10m",
        postgres_backup_restore_validation_port=55432,
        postgres_backup_restore_validation_max_snapshot_age_hours=max_age_hours,
        postgres_backup_restore_validation_min_free_bytes=min_free_bytes,
        postgres_backup_restore_validation_runuser_path=str(fake_bin / "runuser"),
        postgres_backup_remote_options=[],
    )
    script_path = tmp_path / "postgres-logical-backup-restore-validate"
    write_executable(script_path, script)
    environment = {
        "FAKE_COMMAND_LOG": str(tmp_path / "commands.log"),
        "FAKE_SNAPSHOTS_FILE": str(snapshots_file),
        "FAKE_ARTIFACT_SOURCE": str(artifact),
        "FAKE_RUNTIME_STATE": str(runtime_state),
        "FAKE_PROC_ROOT": str(fake_proc),
        "POSTGRES_BACKUP_RESTORE_VALIDATION_PROC_ROOT": str(fake_proc),
    }
    (tmp_path / "environment.json").write_text(json.dumps(environment))
    return script_path


def run_validator(
    script: Path,
    **environment_overrides: str,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(json.loads((script.parent / "environment.json").read_text()))
    environment.update(environment_overrides)
    return subprocess.run(
        [str(script)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def command_log(tmp_path: Path) -> list[str]:
    path = tmp_path / "commands.log"
    return path.read_text().splitlines() if path.exists() else []


def metrics(tmp_path: Path) -> str:
    return (tmp_path / "textfile/postgres_logical_backup_restore_validation.prom").read_text()


def make_stale_workspace(
    tmp_path: Path,
    *,
    pid: str | None = None,
    recorded_pgdata: str | None = None,
) -> tuple[Path, Path]:
    stale = tmp_path / "work/run-20260811T030412Z-123456-Ab12Cd"
    stale_pgdata = stale / "cluster/data"
    stale_pgdata.mkdir(parents=True)
    if pid is not None:
        lines = [pid]
        if recorded_pgdata is not None:
            lines.append(recorded_pgdata)
        (stale_pgdata / "postmaster.pid").write_text("\n".join(lines) + "\n")
    return stale, stale_pgdata


def make_fake_process(
    tmp_path: Path,
    *,
    pid: str,
    executable: str,
    arguments: list[str],
    uid: int = 999,
) -> None:
    process_dir = tmp_path / "proc" / pid
    process_dir.mkdir(parents=True)
    (process_dir / "status").write_text(f"Name:\t{executable}\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n")
    (process_dir / "exe").symlink_to(tmp_path / "fake-bin" / executable)
    (process_dir / "cmdline").write_bytes(b"\0".join(argument.encode() for argument in arguments) + b"\0")


def test_restore_validation_defaults_are_disabled_and_reuse_remote_contract():
    defaults = yaml.safe_load(DEFAULTS_PATH.read_text())
    group_vars = yaml.safe_load(GROUP_VARS_PATH.read_text())

    assert defaults["postgres_backup_restore_validation_manage"] is False
    assert defaults["postgres_backup_restore_validation_enabled"] is False
    assert defaults["postgres_backup_restore_validation_host"] == "{{ postgres_backup_remote_maintenance_host }}"
    assert defaults["postgres_backup_restore_validation_timer_on_calendar"] == "Sun *-*-* 07:00:00"
    assert defaults["postgres_backup_restore_validation_max_snapshot_age_hours"] == 48
    assert defaults["postgres_backup_restore_validation_min_free_bytes"] == 5368709120
    assert not any(key.startswith("postgres_backup_restore_validation_") for key in group_vars)


def test_validation_host_and_remote_capability_are_required_before_mutation():
    tasks = yaml.safe_load(SETUP_TASKS_PATH.read_text())
    validation = task_named(tasks, "Backup restore validation | Validate configuration")
    work_root = task_named(tasks, "Backup restore validation | Create protected work root")
    conditions = " ".join(validation["ansible.builtin.assert"]["that"])

    assert "groups['tags_postgres'] | default([])" in conditions
    assert "postgres_backup_remote_manage" in conditions
    assert "postgres_backup_remote_repository | trim | length > 0" in conditions
    assert "not postgres_backup_restore_validation_enabled or postgres_backup_restore_validation_manage" in conditions
    assert "postgres_backup_root | regex_escape" in conditions
    assert work_root["when"] == [
        "postgres_backup_restore_validation_manage",
        "inventory_hostname == postgres_backup_restore_validation_host",
    ]
    assert work_root["ansible.builtin.file"]["owner"] == "root"
    assert work_root["ansible.builtin.file"]["group"] == "postgres"
    assert work_root["ansible.builtin.file"]["mode"] == "0710"
    assert (work_root["ansible.builtin.file"]["group"], work_root["ansible.builtin.file"]["mode"]) != (
        "root",
        "0700",
    )
    runner = RUNNER_TEMPLATE_PATH.read_text()
    assert 'chown root:postgres "$RUN_DIR"' in runner
    assert 'chmod 0710 "$RUN_DIR"' in runner
    assert 'install -d -o postgres -g postgres -m 0700 "$CLUSTER_DIR" "$PGDATA" "$SOCKET_DIR"' in runner


def test_systemd_job_exists_only_on_designated_host_and_uses_network_online():
    tasks = yaml.safe_load(SETUP_TASKS_PATH.read_text())
    include = task_named(tasks, "Backup restore validation | Manage systemd job")
    job = include["vars"]["systemd_jobs"][0]

    assert include["ansible.builtin.include_role"]["name"] == "systemd_jobs"
    assert "inventory_hostname == postgres_backup_restore_validation_host" in include["when"]
    assert job["service"]["user"] == "root"
    assert job["service"]["group"] == "root"
    assert job["service"]["wants"] == ["network-online.target"]
    assert job["service"]["after"] == ["network-online.target"]
    assert job["timer"]["on_calendar"] == "{{ postgres_backup_restore_validation_timer_on_calendar }}"
    assert job["enabled"] == "{{ postgres_backup_restore_validation_enabled }}"
    rendered = render_jinja(SYSTEMD_SERVICE_TEMPLATE, systemd_jobs_job=job)
    assert "Wants=network-online.target" in rendered
    assert "After=network-online.target" in rendered


def test_manual_action_and_check_mode_do_not_run_during_normal_role_execution():
    tasks = yaml.safe_load(MAIN_TASKS_PATH.read_text())
    run = task_named(tasks, "Run PostgreSQL backup restore validation manually")
    check = task_named(tasks, "Report PostgreSQL backup restore validation check-mode plan")
    action_tasks = yaml.safe_load(ACTION_TASKS_PATH.read_text())
    invoke = task_named(action_tasks, "Backup restore validation action | Invoke host-local runner")

    assert "'postgres_backup_restore_validation_run' in" in " ".join(run["when"])
    assert "not ansible_check_mode" in run["when"]
    assert "inventory_hostname == postgres_backup_restore_validation_host" in run["when"]
    assert "ansible_check_mode" in check["when"]
    assert "would select a recent PostgreSQL Restic snapshot" in check["ansible.builtin.debug"]["msg"]
    assert invoke["become_user"] == "root"
    assert invoke["ansible.builtin.command"]["argv"] == ["{{ postgres_backup_restore_validation_script_path }}"]


def test_restore_validation_tags_and_commands_are_wired_and_documented():
    sources = (
        PLAYBOOK_PATH.read_text(),
        SKYNET_TEMPLATE_PATH.read_text(),
        SKYNET_DOC_PATH.read_text(),
        BACKUP_DOC_PATH.read_text(),
    )
    for action in ("setup", "run"):
        tag = f"postgres_backup_restore_validation_{action}"
        command = f"backup-restore-validation-{action}"
        assert all(tag in source for source in sources)
        assert command in sources[1]
        assert command in sources[2]


def test_runner_preserves_restic_and_production_safety_boundaries():
    source = RUNNER_TEMPLATE_PATH.read_text()

    assert "run_restic cat config" in source
    assert "run_restic snapshots" in source
    assert "--json" in source
    assert '--host "$SNAPSHOT_HOST"' in source
    assert '--tag "postgres-logical-backup,cluster=$CLUSTER_SCOPE"' in source
    assert "--tag postgres-logical-backup" not in source
    assert "source-member=" not in source
    assert "inventory_hostname" not in source
    assert "run_restic init" not in source
    assert "run_restic forget" not in source
    assert "run_restic prune" not in source
    assert "--delete" not in source
    assert "patronictl" not in source.lower()
    assert "/leader" not in source
    assert "systemctl stop patroni" not in source.lower()
    assert "systemctl" not in source
    assert "globals.sql" in source
    assert "psql_value" in source
    assert "--file=globals.sql" not in source
    assert "5432" not in source
    assert "/var/run/postgresql" not in source


def test_successful_validation_restores_every_database_sequentially_and_emits_metrics(
    tmp_path: Path,
):
    script = render_validator(tmp_path)

    result = run_validator(script)
    log = command_log(tmp_path)
    joined = "\n".join(log)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "POSTGRES_BACKUP_RESTORE_VALIDATION_RESULT=VALIDATED" in result.stdout
    assert sum(line.startswith("PG_RESTORE\t") for line in log) == 2
    assert sum(line.startswith("CREATEDB\t") for line in log) == 2
    assert sum(line.startswith("DROPDB\t") for line in log) == 2
    lifecycle = [line.split("\t", 1)[0] for line in log if line.startswith(("CREATEDB\t", "PG_RESTORE\t", "DROPDB\t"))]
    assert lifecycle == [
        "CREATEDB",
        "PG_RESTORE",
        "DROPDB",
        "CREATEDB",
        "PG_RESTORE",
        "DROPDB",
    ]
    snapshots_call = next(line for line in log if line.startswith("RESTIC\t") and "\tsnapshots\t" in line)
    assert "\t--tag\tpostgres-logical-backup,cluster=pg-cluster" in snapshots_call
    assert snapshots_call.count("\t--tag\t") == 1
    install_call = next(line for line in log if line.startswith("INSTALL\t"))
    assert "\t-o\tpostgres\t-g\tpostgres\t-m\t0700" in install_call
    for directory in ("/cluster", "/cluster/data", "/cluster/socket"):
        assert directory in install_call
    for line in [line for line in log if line.startswith(("PSQL\t", "CREATEDB\t", "DROPDB\t", "PG_RESTORE\t"))]:
        assert "--host=" in line and "/cluster/socket" in line
        assert "--port=55432" in line
        assert "--username=postgres" in line
    restore_lines = [line for line in log if line.startswith("PG_RESTORE\t")]
    assert any(line.endswith("/appdb.dump") for line in restore_lines)
    assert any(line.endswith("/postgres.dump") for line in restore_lines)
    for line in restore_lines:
        for option in ("--exit-on-error", "--no-owner", "--no-acl", "--no-tablespaces"):
            assert option in line
    first_safety_query = next(index for index, line in enumerate(log) if "SHOW data_directory;" in line)
    first_restore = next(index for index, line in enumerate(log) if line.startswith("PG_RESTORE\t"))
    assert first_safety_query < first_restore
    assert "RUNUSER\t-u\tpostgres\t--" in joined
    assert "INITDB\t" in joined
    assert "PG_CTL\t" in joined and "\tstart" in joined and "\tstop" in joined
    assert "--auth-local=trust" in joined
    assert "--auth-host=reject" in joined
    assert "--template=template0" in joined
    for line in [line for line in log if line.startswith(("CREATEDB\t", "DROPDB\t"))]:
        assert line.endswith("\tpostgres_restore_validation")
    assert "--port=5432" not in joined
    assert "/var/run/postgresql" not in joined
    assert "globals.sql" not in joined
    assert not list((tmp_path / "work").glob("run-*"))
    metric_text = metrics(tmp_path)
    assert "postgres_backup_restore_validation_last_run_success 1" in metric_text
    assert "postgres_backup_restore_validation_last_database_count 2" in metric_text
    assert "postgres_backup_restore_validation_last_snapshot_timestamp_seconds 0" not in metric_text
    assert not list((tmp_path / "textfile").glob("*.tmp.*"))


def test_newest_valid_matching_snapshot_is_selected_and_unrelated_snapshot_is_ignored(
    tmp_path: Path,
):
    backup_root = tmp_path / "backups"
    now = datetime.datetime.now(datetime.UTC)
    snapshots = [
        snapshot(
            backup_root,
            snapshot_id="d" * 64,
            backup_id="20260813T030412Z",
            snapshot_time=now,
            hostname="pg95",
        ),
        snapshot(
            backup_root,
            snapshot_id=SNAPSHOT_ID_A,
            backup_id=BACKUP_ID_A,
            snapshot_time=now - datetime.timedelta(hours=2),
        ),
        snapshot(
            backup_root,
            snapshot_id=SNAPSHOT_ID_B,
            backup_id=BACKUP_ID_B,
            snapshot_time=now - datetime.timedelta(minutes=5),
        ),
    ]
    script = render_validator(tmp_path, snapshots=snapshots)

    result = run_validator(script)
    restore = next(line for line in command_log(tmp_path) if "\trestore\t" in line)

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"{SNAPSHOT_ID_B}:{backup_root}/{BACKUP_ID_B}" in restore
    assert SNAPSHOT_ID_A not in restore
    assert "d" * 64 not in restore


@pytest.mark.parametrize(
    ("mutator", "expected_message"),
    [
        (lambda item, root: item.update({"id": "../../unsafe"}), "unsafe ID"),
        (
            lambda item, root: item.update({"tags": ["postgres-logical-backup", "cluster=pg-cluster"]}),
            "exactly one backup-id",
        ),
        (
            lambda item, root: item.update(
                {
                    "tags": [
                        "postgres-logical-backup",
                        "cluster=pg-cluster",
                        "backup-id=../../unsafe",
                    ]
                }
            ),
            "invalid backup ID",
        ),
        (
            lambda item, root: item.update({"paths": [f"{root}/unexpected"]}),
            "unexpected source path",
        ),
        (lambda item, root: item.update({"tags": "malformed"}), "malformed tags"),
    ],
)
def test_malformed_matching_snapshot_metadata_is_rejected_before_restore(
    tmp_path: Path,
    mutator,
    expected_message: str,
):
    backup_root = tmp_path / "backups"
    item = snapshot(backup_root)
    mutator(item, backup_root)
    script = render_validator(tmp_path, snapshots=[item])

    result = run_validator(script)
    joined = "\n".join(command_log(tmp_path))

    assert result.returncode != 0
    assert expected_message in result.stderr
    assert "\trestore\t" not in joined
    assert "INITDB\t" not in joined


def test_no_matching_snapshot_and_stale_snapshot_fail_without_restore(tmp_path: Path):
    unrelated = snapshot(tmp_path / "no-match/backups", hostname="pg95")
    stale = snapshot(
        tmp_path / "stale/backups",
        snapshot_time=datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=49),
    )

    no_match_script = render_validator(tmp_path / "no-match", snapshots=[unrelated])
    no_match = run_validator(no_match_script)
    stale_script = render_validator(tmp_path / "stale", snapshots=[stale])
    stale_result = run_validator(stale_script)

    assert no_match.returncode != 0
    assert "no matching PostgreSQL" in no_match.stderr
    assert stale_result.returncode != 0
    assert "older than 48 hours" in stale_result.stderr
    assert not any("\trestore\t" in line for line in command_log(tmp_path / "stale"))


@pytest.mark.parametrize(
    ("restic_mode", "message"),
    [
        ("missing", "not initialized"),
        ("wrong-password", "rejected its password"),
        ("backend-fail", "exit code 20"),
        ("snapshots-fail", "restore validation failed"),
        ("restore-fail", "restore validation failed"),
    ],
)
def test_restic_failures_are_loud_and_never_modify_repository(
    tmp_path: Path,
    restic_mode: str,
    message: str,
):
    script = render_validator(tmp_path)

    result = run_validator(script, FAKE_RESTIC_MODE=restic_mode)
    joined = "\n".join(command_log(tmp_path))

    assert result.returncode != 0
    assert message in result.stderr
    assert "\tinit" not in joined
    assert "\tforget" not in joined
    assert "\tprune" not in joined
    assert "--delete" not in joined


@pytest.mark.parametrize(
    ("mutation", "expected_message"),
    [
        ("missing-success", "missing SUCCESS"),
        ("missing-globals", "missing globals.sql"),
        ("tampered-dump", "FAILED"),
        ("malformed-manifest", "unsafe database mapping"),
        ("count-mismatch", "database count does not match"),
        ("missing-dump", "missing databases/appdb.dump"),
        ("unexpected-dump", "do not exactly match the manifest"),
    ],
)
def test_invalid_restored_artifacts_fail_before_postgresql_starts(
    tmp_path: Path,
    mutation: str,
    expected_message: str,
):
    artifact = make_artifact(tmp_path)
    if mutation == "missing-success":
        (artifact / "SUCCESS").unlink()
    elif mutation == "missing-globals":
        (artifact / "globals.sql").unlink()
    elif mutation == "tampered-dump":
        (artifact / "databases/appdb.dump").write_text("tampered after checksum\n")
    elif mutation == "malformed-manifest":
        manifest = (artifact / "manifest.txt").read_text()
        (artifact / "manifest.txt").write_text(
            manifest.replace(
                "database=appdb\tdump=databases/appdb.dump",
                "database=appdb\tdump=../appdb.dump",
            )
        )
        rewrite_checksums(artifact)
    elif mutation == "count-mismatch":
        manifest = (artifact / "manifest.txt").read_text()
        (artifact / "manifest.txt").write_text(manifest.replace("database_count=2", "database_count=3"))
        rewrite_checksums(artifact)
    elif mutation == "missing-dump":
        (artifact / "databases/appdb.dump").unlink()
    elif mutation == "unexpected-dump":
        (artifact / "databases/unexpected.dump").write_text("unexpected\n")

    script = render_validator(tmp_path, artifact=artifact)
    result = run_validator(script)
    joined = "\n".join(command_log(tmp_path))

    assert result.returncode != 0
    assert expected_message in result.stdout + result.stderr
    assert "INITDB\t" not in joined
    assert "PG_RESTORE\t" not in joined
    assert not list((tmp_path / "work").glob("run-*"))


@pytest.mark.parametrize(
    ("psql_mode", "expected_message"),
    [
        ("wrong-data", "unexpected data directory"),
        ("tcp", "TCP listening enabled"),
        ("wrong-socket", "unexpected socket directory"),
        ("wrong-port", "unexpected port"),
    ],
)
def test_temporary_cluster_identity_mismatch_prevents_database_restore_and_cleans_up(
    tmp_path: Path,
    psql_mode: str,
    expected_message: str,
):
    script = render_validator(tmp_path)

    result = run_validator(script, FAKE_PSQL_MODE=psql_mode)
    log = command_log(tmp_path)
    joined = "\n".join(log)

    assert result.returncode != 0
    assert expected_message in result.stderr
    assert "PG_RESTORE\t" not in joined
    assert "CREATEDB\t" not in joined
    assert any(line.startswith("PG_CTL\t") and line.endswith("\tstop") for line in log)
    assert not list((tmp_path / "work").glob("run-*"))


def test_free_space_floor_fails_before_restic_restore(tmp_path: Path):
    script = render_validator(tmp_path, min_free_bytes=10**18)

    result = run_validator(script)
    joined = "\n".join(command_log(tmp_path))

    assert result.returncode != 0
    assert "below the configured free-space floor" in result.stderr
    assert "\trestore\t" not in joined
    assert "INITDB\t" not in joined
    assert "postgres_backup_restore_validation_last_run_success 0" in metrics(tmp_path)


@pytest.mark.parametrize(
    ("environment", "expected_log"),
    [
        ({"FAKE_INITDB_FAIL": "1"}, "INITDB\t"),
        ({"FAKE_PG_CTL_START_FAIL": "1"}, "PG_CTL\t"),
        ({"FAKE_PSQL_MODE": "sql-fail"}, "PSQL\t"),
    ],
)
def test_postgresql_startup_and_sql_failures_fail_the_validation(
    tmp_path: Path,
    environment: dict[str, str],
    expected_log: str,
):
    script = render_validator(tmp_path)

    result = run_validator(script, **environment)
    joined = "\n".join(command_log(tmp_path))

    assert result.returncode != 0
    assert expected_log in joined
    assert "postgres_backup_restore_validation_last_run_success 0" in metrics(tmp_path)
    assert not list((tmp_path / "work").glob("run-*"))


def test_cleanup_stop_failure_is_reported_and_preserves_the_workspace(tmp_path: Path):
    script = render_validator(tmp_path)

    result = run_validator(script, FAKE_PG_CTL_STOP_FAIL="1")

    assert result.returncode != 0
    assert "Failed to stop the temporary PostgreSQL validation cluster" in result.stderr
    assert "postgres_backup_restore_validation_last_run_success 0" in metrics(tmp_path)
    assert len(list((tmp_path / "work").glob("run-*"))) == 1


def test_pg_restore_failure_fails_run_preserves_last_success_and_cleans_cluster(
    tmp_path: Path,
):
    script = render_validator(tmp_path)
    metrics_file = tmp_path / "textfile/postgres_logical_backup_restore_validation.prom"
    metrics_file.write_text(
        "\n".join(
            (
                "postgres_backup_restore_validation_last_success_timestamp_seconds 123",
                "postgres_backup_restore_validation_last_database_count 7",
                "postgres_backup_restore_validation_last_snapshot_timestamp_seconds 456",
            )
        )
        + "\n"
    )

    result = run_validator(script, FAKE_PG_RESTORE_FAIL="1")
    log = command_log(tmp_path)
    metric_text = metrics(tmp_path)

    assert result.returncode != 0
    assert "postgres_backup_restore_validation_last_run_success 0" in metric_text
    assert "postgres_backup_restore_validation_last_success_timestamp_seconds 123" in metric_text
    assert "postgres_backup_restore_validation_last_database_count 7" in metric_text
    assert "postgres_backup_restore_validation_last_snapshot_timestamp_seconds 456" in metric_text
    assert any(line.startswith("PG_CTL\t") and line.endswith("\tstop") for line in log)
    assert not list((tmp_path / "work").glob("run-*"))


def test_overlap_skip_does_not_overwrite_health_metrics(tmp_path: Path):
    script = render_validator(tmp_path)
    environment = os.environ.copy()
    environment.update(json.loads((tmp_path / "environment.json").read_text()))
    environment["FAKE_PG_RESTORE_SLEEP"] = "1"
    first = subprocess.Popen(
        [str(script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    try:
        for _ in range(150):
            if any(line.startswith("PG_RESTORE\t") for line in command_log(tmp_path)):
                break
            if first.poll() is not None:
                break
            time.sleep(0.02)
        metrics_before = metrics(tmp_path)
        overlap = run_validator(script)
        metrics_after = metrics(tmp_path)
        first_stdout, first_stderr = first.communicate(timeout=15)
    finally:
        if first.poll() is None:
            first.terminate()
            first.wait(timeout=5)

    assert first.returncode == 0, first_stdout + first_stderr
    assert overlap.returncode == 0, overlap.stdout + overlap.stderr
    assert "POSTGRES_BACKUP_RESTORE_VALIDATION_RESULT=SKIPPED_OVERLAP" in overlap.stdout
    assert metrics_after == metrics_before


def test_stale_workspace_without_pid_is_removed_without_stop_and_remains_root_bounded(tmp_path: Path):
    script = render_validator(tmp_path)
    stale, _ = make_stale_workspace(tmp_path)
    invalid = tmp_path / "work/run-operator-notes"
    outside = tmp_path / "must-remain"
    invalid.mkdir()
    outside.mkdir()

    result = run_validator(script, FAKE_RESTIC_MODE="backend-fail")

    assert result.returncode != 0
    assert not stale.exists()
    assert not any(line.startswith("PG_CTL\t") for line in command_log(tmp_path))
    assert invalid.is_dir()
    assert outside.is_dir()
    source = RUNNER_TEMPLATE_PATH.read_text()
    assert '[[ "$(dirname -- "$candidate")" == "$WORK_ROOT" ]]' in source
    assert "^run-[0-9]{8}T[0-9]{6}Z-[0-9]+-[A-Za-z0-9]{6}$" in source
    assert "pg_ctl -D" not in source
    assert "pg_ctl status" not in source
    assert "\nkill " not in source
    assert "\nkillall " not in source
    assert "\npkill " not in source
    assert source.count("process_belongs_to_validator_pgdata \\") == 2


def test_dead_stale_pid_is_removed_without_postgresql_stop(tmp_path: Path):
    script = render_validator(tmp_path)
    stale, stale_pgdata = make_stale_workspace(tmp_path, pid="4242")
    (stale_pgdata / "postmaster.pid").write_text(f"4242\n{stale_pgdata}\n")

    result = run_validator(script, FAKE_RESTIC_MODE="backend-fail")

    assert result.returncode != 0
    assert "PID 4242 is not alive; no stop is required" in result.stdout
    assert not stale.exists()
    assert not any(line.startswith("PG_CTL\t") for line in command_log(tmp_path))


def test_exact_live_stale_validator_process_is_stopped_before_removal(tmp_path: Path):
    script = render_validator(tmp_path)
    stale, stale_pgdata = make_stale_workspace(tmp_path, pid="4242")
    (stale_pgdata / "postmaster.pid").write_text(f"4242\n{stale_pgdata}\n")
    make_fake_process(
        tmp_path,
        pid="4242",
        executable="postgres",
        arguments=[str(tmp_path / "fake-bin/postgres"), "-D", str(stale_pgdata)],
    )

    result = run_validator(script, FAKE_RESTIC_MODE="backend-fail")
    stop_calls = [line for line in command_log(tmp_path) if line.startswith("PG_CTL\t")]

    assert result.returncode != 0
    assert not stale.exists()
    assert len(stop_calls) == 1
    assert f"\t-D\t{stale_pgdata}\t-m\tfast\t-w\t-t\t60\tstop" in stop_calls[0]


@pytest.mark.parametrize(
    ("executable", "process_pgdata", "uid", "recorded_pgdata"),
    [
        ("sleep", None, 999, None),
        ("postgres", "/var/lib/postgresql/18/main", 999, None),
        ("postgres", "/tmp/different-validation-run/cluster/data", 999, None),
        ("postgres", None, 1000, None),
        ("postgres", None, 999, "/var/lib/postgresql/18/main"),
    ],
)
def test_ambiguous_live_stale_pid_fails_closed_without_stop_or_removal(
    tmp_path: Path,
    executable: str,
    process_pgdata: str | None,
    uid: int,
    recorded_pgdata: str | None,
):
    script = render_validator(tmp_path)
    stale, stale_pgdata = make_stale_workspace(tmp_path, pid="4242")
    recorded = recorded_pgdata or str(stale_pgdata)
    (stale_pgdata / "postmaster.pid").write_text(f"4242\n{recorded}\n")
    arguments = [str(tmp_path / f"fake-bin/{executable}")]
    if executable == "postgres":
        arguments.extend(("-D", process_pgdata or str(stale_pgdata)))
    else:
        arguments.append("60")
    make_fake_process(
        tmp_path,
        pid="4242",
        executable=executable,
        arguments=arguments,
        uid=uid,
    )

    result = run_validator(script)

    assert result.returncode != 0
    assert "Refusing to stop live PID 4242" in result.stderr
    assert stale.is_dir()
    assert not any(line.startswith("PG_CTL\t") for line in command_log(tmp_path))
    assert "postgres_backup_restore_validation_last_run_success 0" in metrics(tmp_path)


@pytest.mark.parametrize("malformed_pid", ["", "not-a-pid", "0", "-12"])
def test_malformed_stale_pid_never_causes_a_stop(tmp_path: Path, malformed_pid: str):
    script = render_validator(tmp_path)
    stale, stale_pgdata = make_stale_workspace(tmp_path, pid="placeholder")
    (stale_pgdata / "postmaster.pid").write_text(f"{malformed_pid}\n{stale_pgdata}\n")

    result = run_validator(script)

    assert result.returncode != 0
    assert "malformed postmaster.pid" in result.stderr
    assert stale.is_dir()
    assert not any(line.startswith("PG_CTL\t") for line in command_log(tmp_path))


def test_metrics_are_atomic_low_cardinality_and_failure_aware():
    source = RUNNER_TEMPLATE_PATH.read_text()

    assert 'mktemp "${METRICS_FILE}.tmp.XXXXXX"' in source
    assert 'mv -f -- "$metrics_tmp" "$METRICS_FILE"' in source
    assert "postgres_backup_restore_validation_last_run_success{" not in source
    assert "postgres_backup_restore_validation_last_database_count{" not in source
    for metric_name in (
        "last_attempt_timestamp_seconds",
        "last_success_timestamp_seconds",
        "last_run_success",
        "last_duration_seconds",
        "last_database_count",
        "last_snapshot_timestamp_seconds",
    ):
        assert f"postgres_backup_restore_validation_{metric_name}" in source


def test_rendered_validator_passes_bash_syntax(tmp_path: Path):
    script = render_validator(tmp_path)

    result = subprocess.run(
        ["bash", "-n", str(script)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck is unavailable")
def test_rendered_validator_passes_shellcheck(tmp_path: Path):
    script = render_validator(tmp_path)

    result = subprocess.run(
        ["shellcheck", str(script)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_restore_validation_systemd_units_pass_systemd_analyze_verify(tmp_path: Path):
    if shutil.which("systemd-analyze") is None:
        pytest.skip("systemd-analyze is unavailable")
    runner = tmp_path / "postgres-logical-backup-restore-validate"
    write_executable(runner, "#!/bin/sh\nexit 0\n")
    job = {
        "name": "postgres-logical-backup-restore-validation",
        "description": "Validate PostgreSQL logical backups restored from Restic",
        "service": {
            "type": "oneshot",
            "exec_start": str(runner),
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
            "description": "Validate PostgreSQL logical backups restored from Restic",
            "on_calendar": "Sun *-*-* 07:00:00",
            "randomized_delay_sec": "30m",
            "persistent": True,
        },
        "enabled": False,
    }
    service_path = tmp_path / f"{job['name']}.service"
    timer_path = tmp_path / f"{job['name']}.timer"
    service_path.write_text(render_jinja(SYSTEMD_SERVICE_TEMPLATE, systemd_jobs_job=job))
    timer_path.write_text(render_jinja(SYSTEMD_TIMER_TEMPLATE, systemd_jobs_job=job))

    result = subprocess.run(
        ["systemd-analyze", "verify", str(service_path), str(timer_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
