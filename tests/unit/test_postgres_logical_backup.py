from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, StrictUndefined

REPO_ROOT = Path(__file__).resolve().parents[2]
ROLE_PATH = REPO_ROOT / "ansible/roles/postgres"
DEFAULTS_PATH = ROLE_PATH / "defaults/main.yml"
MAIN_TASKS_PATH = ROLE_PATH / "tasks/main.yml"
SETUP_TASKS_PATH = ROLE_PATH / "tasks/sub_tasks/backup_setup.yml"
RUN_TASKS_PATH = ROLE_PATH / "tasks/sub_tasks/backup.yml"
SCRIPT_TEMPLATE_PATH = ROLE_PATH / "templates/postgres-logical-backup.sh.j2"
PLAYBOOK_PATH = REPO_ROOT / "ansible/playbook.yml"
GROUP_VARS_PATH = REPO_ROOT / "ansible/group_vars/tags_postgres.yml"
SKYNET_TEMPLATE_PATH = REPO_ROOT / "ansible/roles/ubuntu/templates/skynet.j2"
SKYNET_DOC_PATH = REPO_ROOT / "docs/cheat_sheets/skynet.md"
BACKUP_DOC_PATH = REPO_ROOT / "docs/postgresql-logical-backups.md"
SYSTEMD_SERVICE_TEMPLATE = REPO_ROOT / "ansible/roles/systemd_jobs/templates/systemd-job.service.j2"
SYSTEMD_TIMER_TEMPLATE = REPO_ROOT / "ansible/roles/systemd_jobs/templates/systemd-job.timer.j2"


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


def render_runner(tmp_path: Path) -> Path:
    backup_root = tmp_path / "backups"
    metrics_file = tmp_path / "textfile" / "postgres_logical_backup.prom"
    backup_root.mkdir()
    metrics_file.parent.mkdir()
    metrics_file.write_text("")
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()

    script = render_jinja(
        SCRIPT_TEMPLATE_PATH,
        postgres_backup_root=str(backup_root),
        postgres_backup_metrics_file=str(metrics_file),
        postgres_patroni_bin_dir=str(fake_bin),
        postgres_patroni_postgres_port=5432,
        postgres_patroni_node_name="postgres-1",
        postgres_patroni_restapi_port=8008,
        postgres_backup_local_retention_days=7,
        postgres_backup_failed_retention_days=2,
    )
    script_path = tmp_path / "postgres-logical-backup"
    script_path.write_text(script)
    script_path.chmod(0o755)

    fake_commands = {
        "curl": """#!/usr/bin/env bash
case "${FAKE_PATRONI_MODE:-leader}" in
  leader) printf '200' ;;
  replica) printf '503' ;;
  unavailable) exit 7 ;;
  *) printf '%s' "$FAKE_PATRONI_MODE" ;;
esac
""",
        "psql": """#!/usr/bin/env bash
if [[ "$*" == *"SELECT count(*)"* ]]; then
  printf '0\\n'
elif [[ "$*" == *"SELECT datname"* ]]; then
  printf 'appdb\\npostgres\\n'
elif [[ "$*" == *"SHOW server_version"* ]]; then
  printf '18.0-test\\n'
else
  exit 2
fi
""",
        "pg_dump": """#!/usr/bin/env bash
output=''
for argument in "$@"; do
  case "$argument" in
    --file=*) output="${argument#*=}" ;;
  esac
done
[[ -n "$output" ]]
printf 'fake custom archive\\n' > "$output"
""",
        "pg_restore": """#!/usr/bin/env bash
[[ "$1" == "--list" && -s "$2" ]]
""",
        "pg_dumpall": """#!/usr/bin/env bash
output=''
for argument in "$@"; do
  case "$argument" in
    --file=*) output="${argument#*=}" ;;
  esac
done
[[ -n "$output" ]]
printf '%s\\n' '-- PostgreSQL globals' > "$output"
""",
    }
    for command_name, command_source in fake_commands.items():
        command_path = fake_bin / command_name
        command_path.write_text(command_source)
        command_path.chmod(0o755)

    return script_path


def run_runner(script_path: Path, mode: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["FAKE_PATRONI_MODE"] = mode
    return subprocess.run(
        [str(script_path)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def test_scheduled_backups_do_not_have_an_ansible_database_allowlist():
    defaults = yaml.safe_load(DEFAULTS_PATH.read_text())
    implementation = SETUP_TASKS_PATH.read_text() + SCRIPT_TEMPLATE_PATH.read_text()

    assert "postgres_backup_dbs" not in defaults
    assert "postgres_backup_dbs" not in implementation


def test_backup_root_is_durable_and_not_tmp():
    defaults = yaml.safe_load(DEFAULTS_PATH.read_text())

    assert defaults["postgres_backup_root"] == "/var/backups/postgresql"
    assert not defaults["postgres_backup_root"].startswith("/tmp")


def test_role_default_is_opt_in_but_postgres_group_enables_timer():
    defaults = yaml.safe_load(DEFAULTS_PATH.read_text())
    group_vars = yaml.safe_load(GROUP_VARS_PATH.read_text())

    assert defaults["postgres_backup_manage_timer"] is False
    assert group_vars["postgres_backup_manage_timer"] is True


def test_setup_installs_runner_on_postgres_hosts_with_restrictive_ownership():
    main_tasks = yaml.safe_load(MAIN_TASKS_PATH.read_text())
    setup_tasks = yaml.safe_load(SETUP_TASKS_PATH.read_text())
    include = task_named(main_tasks, "Configure PostgreSQL logical backups")
    install = task_named(setup_tasks, "Logical backup | Install host-local runner")
    backup_root = task_named(setup_tasks, "Logical backup | Create protected backup root")

    assert include["when"] == ["'tags_postgres' in group_names"]
    assert install["ansible.builtin.template"] == {
        "src": "postgres-logical-backup.sh.j2",
        "dest": "{{ postgres_backup_script_path }}",
        "owner": "root",
        "group": "root",
        "mode": "0755",
    }
    assert backup_root["ansible.builtin.file"]["owner"] == "postgres"
    assert backup_root["ansible.builtin.file"]["mode"] == "0750"


def test_metrics_permission_is_narrow():
    setup_tasks = yaml.safe_load(SETUP_TASKS_PATH.read_text())
    directory = task_named(setup_tasks, "Logical backup | Ensure textfile collector directory exists")
    metrics = task_named(setup_tasks, "Logical backup | Pre-create narrowly writable metrics file")

    assert "owner" not in directory["ansible.builtin.file"]
    assert directory["ansible.builtin.file"]["mode"] == "0755"
    assert metrics["ansible.builtin.file"]["owner"] == "postgres"
    assert metrics["ansible.builtin.file"]["group"] == "postgres"
    assert metrics["ansible.builtin.file"]["mode"] == "0644"


def test_systemd_jobs_owns_service_and_timer_rendering():
    setup_tasks = yaml.safe_load(SETUP_TASKS_PATH.read_text())
    include = task_named(setup_tasks, "Logical backup | Manage systemd service and timer")
    source = SETUP_TASKS_PATH.read_text()

    assert include["ansible.builtin.include_role"]["name"] == "systemd_jobs"
    assert "/etc/systemd/system" not in source
    assert "ansible.builtin.systemd_service" not in source


def test_systemd_job_runs_as_postgres_without_password_material():
    setup_tasks = yaml.safe_load(SETUP_TASKS_PATH.read_text())
    job = task_named(setup_tasks, "Logical backup | Manage systemd service and timer")["vars"]["systemd_jobs"][0]
    service = job["service"]

    assert service["type"] == "oneshot"
    assert service["user"] == "postgres"
    assert service["group"] == "postgres"
    assert service["exec_start"] == "{{ postgres_backup_script_path }}"
    assert "pass" not in str(job).lower()
    assert "secret" not in str(job).lower()


def test_timer_is_defined_for_each_postgres_host_not_a_discovered_leader():
    setup_tasks = yaml.safe_load(SETUP_TASKS_PATH.read_text())
    job = task_named(setup_tasks, "Logical backup | Manage systemd service and timer")["vars"]["systemd_jobs"][0]
    setup_source = SETUP_TASKS_PATH.read_text()

    assert job["timer"]["persistent"] is True
    assert job["enabled"] == "{{ postgres_backup_manage_timer }}"
    assert "postgres_backup_patroni_leader" not in setup_source
    assert "delegate_to" not in setup_source


def test_runner_uses_local_patroni_leader_endpoint():
    source = SCRIPT_TEMPLATE_PATH.read_text()

    assert "http://127.0.0.1:" in source
    assert "/leader" in source
    assert 'case "$patroni_http_code"' in source
    assert "200)" in source
    assert "503)" in source


def test_runner_uses_peer_authentication_without_password_or_tcp_host():
    source = SCRIPT_TEMPLATE_PATH.read_text()

    assert "PGPASSWORD" not in source
    assert "postgres_patroni_superuser_pass" not in source
    assert " -h " not in source
    assert "--host" not in source
    assert "export PGPASSFILE=/dev/null" in source
    assert "unset PGHOST" in source


def test_database_discovery_uses_actual_connectable_non_template_databases():
    source = SCRIPT_TEMPLATE_PATH.read_text()

    assert "SELECT datname FROM pg_database" in source
    assert "WHERE datallowconn AND NOT datistemplate" in source
    assert "ORDER BY datname" in source


def test_database_names_are_validated_before_becoming_paths():
    source = SCRIPT_TEMPLATE_PATH.read_text()

    assert "datname !~ '^[A-Za-z0-9_.-]+" in source
    assert "cannot be represented safely as backup filenames" in source
    assert 'dump_path="$STAGING_DIR/databases/$database.dump"' in source


def test_custom_format_dump_is_canonical():
    source = SCRIPT_TEMPLATE_PATH.read_text()

    assert '"$PG_DUMP"' in source
    assert "--format=custom" in source
    assert '--file="$dump_path"' in source


def test_cluster_globals_are_captured():
    source = SCRIPT_TEMPLATE_PATH.read_text()

    assert '"$PG_DUMPALL"' in source
    assert "--globals-only" in source
    assert "globals.sql" in source


def test_every_database_archive_is_verified():
    source = SCRIPT_TEMPLATE_PATH.read_text()
    loop = source.split('for database in "${DATABASES[@]}"; do', maxsplit=1)[1].split("done", maxsplit=1)[0]

    assert '"$PG_DUMP"' in loop
    assert '"$PG_RESTORE" --list "$dump_path"' in loop


def test_checksums_cover_payload_in_deterministic_order():
    source = SCRIPT_TEMPLATE_PATH.read_text()

    assert "LC_ALL=C sort -z" in source
    assert "sha256sum globals.sql manifest.txt" in source
    assert '> "$STAGING_DIR/SHA256SUMS"' in source
    assert "SHA256SUMS SHA256SUMS" not in source


def test_success_marker_and_promotion_follow_required_work():
    source = SCRIPT_TEMPLATE_PATH.read_text()

    positions = [
        source.index('"$PG_DUMP"'),
        source.index('"$PG_RESTORE"'),
        source.index('"$PG_DUMPALL"'),
        source.index("manifest.txt"),
        source.index("SHA256SUMS"),
        source.index('touch "$STAGING_DIR/SUCCESS"'),
        source.index('mv -- "$STAGING_DIR" "$FINAL_DIR"'),
    ]
    assert positions == sorted(positions)


def test_retention_is_root_bounded_and_name_constrained():
    source = SCRIPT_TEMPLATE_PATH.read_text()

    assert 'find "$BACKUP_ROOT"' in source
    assert "-mindepth 1" in source
    assert "-maxdepth 1" in source
    assert "'^[0-9]{8}T[0-9]{6}Z$'" in source
    assert "'^\\.staging-[0-9]{8}T[0-9]{6}Z-[0-9]+$'" in source
    assert '[[ "$candidate" == "$BACKUP_ROOT/"* ]]' in source


def test_manual_run_discovers_leader_and_invokes_installed_runner():
    tasks = yaml.safe_load(RUN_TASKS_PATH.read_text())
    query = task_named(tasks, "Logical backup run | Query Patroni cluster state")
    invoke = task_named(tasks, "Logical backup run | Invoke installed leader-gated runner")

    assert query["delegate_to"] == "{{ services_controller_host }}"
    assert "selectattr('role', 'equalto', 'leader')" in query["until"]
    assert invoke["become_user"] == "postgres"
    assert invoke["ansible.builtin.command"]["argv"] == ["{{ postgres_backup_script_path }}"]
    assert invoke["delegate_to"] == "{{ postgres_backup_patroni_leader }}"


def test_normal_role_execution_does_not_run_an_immediate_backup():
    main_tasks = yaml.safe_load(MAIN_TASKS_PATH.read_text())
    run_include = task_named(main_tasks, "Run PostgreSQL logical backup manually")
    condition = " ".join(run_include["when"])

    assert "postgres_backup_run" in condition
    assert "postgres_backup" in condition
    assert "'all'" not in condition


def test_setup_run_and_compatibility_tags_are_wired_and_documented():
    playbook = PLAYBOOK_PATH.read_text()
    skynet = SKYNET_TEMPLATE_PATH.read_text()
    docs = SKYNET_DOC_PATH.read_text()

    for tag in ("postgres_backup", "postgres_backup_setup", "postgres_backup_run"):
        assert tag in playbook
        assert tag in skynet
        assert tag in docs


def test_replica_skip_exits_zero_without_dumping_or_overwriting_metrics(tmp_path: Path):
    script = render_runner(tmp_path)
    metrics_file = tmp_path / "textfile" / "postgres_logical_backup.prom"
    original_metrics = "postgres_backup_last_run_success 1\n"
    metrics_file.write_text(original_metrics)

    result = run_runner(script, "replica")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "POSTGRES_BACKUP_RESULT=SKIPPED_NOT_LEADER" in result.stdout
    assert metrics_file.read_text() == original_metrics
    assert not list((tmp_path / "backups").glob("[0-9]*"))


def test_patroni_query_failure_is_not_a_replica_skip(tmp_path: Path):
    script = render_runner(tmp_path)

    result = run_runner(script, "unavailable")
    metrics = (tmp_path / "textfile" / "postgres_logical_backup.prom").read_text()

    assert result.returncode != 0
    assert "Unable to query local Patroni leader endpoint" in result.stderr
    assert "SKIPPED_NOT_LEADER" not in result.stdout
    assert "postgres_backup_last_run_success 0" in metrics


def test_unexpected_patroni_http_status_fails(tmp_path: Path):
    script = render_runner(tmp_path)

    result = run_runner(script, "500")

    assert result.returncode != 0
    assert "unexpected HTTP status 500" in result.stderr
    assert "SKIPPED_NOT_LEADER" not in result.stdout


def test_successful_runner_builds_verified_promoted_backup_and_metrics(tmp_path: Path):
    script = render_runner(tmp_path)

    result = run_runner(script, "leader")

    assert result.returncode == 0, result.stdout + result.stderr
    final_directories = list((tmp_path / "backups").glob("[0-9]*Z"))
    assert len(final_directories) == 1
    backup = final_directories[0]
    assert (backup / "SUCCESS").is_file()
    assert sorted(path.name for path in (backup / "databases").glob("*.dump")) == ["appdb.dump", "postgres.dump"]
    assert "database_count=2" in (backup / "manifest.txt").read_text()
    checksum = subprocess.run(
        ["sha256sum", "--check", "SHA256SUMS"],
        cwd=backup,
        check=False,
        capture_output=True,
        text=True,
    )
    assert checksum.returncode == 0, checksum.stdout + checksum.stderr
    metrics = (tmp_path / "textfile" / "postgres_logical_backup.prom").read_text()
    assert "postgres_backup_last_run_success 1" in metrics
    assert "postgres_backup_last_database_count 2" in metrics


def test_rendered_runner_passes_bash_syntax(tmp_path: Path):
    script = render_runner(tmp_path)

    result = subprocess.run(["bash", "-n", str(script)], check=False, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck is unavailable")
def test_rendered_runner_passes_shellcheck(tmp_path: Path):
    script = render_runner(tmp_path)

    result = subprocess.run(["shellcheck", str(script)], check=False, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(shutil.which("systemd-analyze") is None, reason="systemd-analyze is unavailable")
def test_postgres_units_pass_systemd_analyze_verify(tmp_path: Path):
    runner_path = tmp_path / "postgres-logical-backup"
    runner_path.write_text("#!/bin/sh\nexit 0\n")
    runner_path.chmod(0o755)
    job = {
        "name": "postgres-logical-backup",
        "description": "PostgreSQL leader logical backup",
        "service": {
            "type": "oneshot",
            "exec_start": str(runner_path),
            "user": "postgres",
            "group": "postgres",
            "working_directory": "/var/backups/postgresql",
            "after": ["patroni.service"],
            "nice": 10,
            "io_scheduling_class": "best-effort",
            "io_scheduling_priority": 7,
        },
        "timer": {
            "description": "Run PostgreSQL leader logical backup",
            "on_calendar": "*-*-* 03:00:00",
            "randomized_delay_sec": "30m",
            "persistent": True,
        },
        "enabled": True,
    }
    service_path = tmp_path / "postgres-logical-backup.service"
    timer_path = tmp_path / "postgres-logical-backup.timer"
    service_path.write_text(render_jinja(SYSTEMD_SERVICE_TEMPLATE, systemd_jobs_job=job))
    timer_path.write_text(render_jinja(SYSTEMD_TIMER_TEMPLATE, systemd_jobs_job=job))

    result = subprocess.run(
        ["systemd-analyze", "verify", str(service_path), str(timer_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_documentation_covers_architecture_operations_and_deferred_protection():
    docs = BACKUP_DOC_PATH.read_text()

    for statement in (
        "Patroni replicas provide high availability, not backups.",
        "local logical backups only",
        "off-host backup repository",
        "peer authentication",
        "pg_restore --list",
        "SHA256SUMS",
        "postgres_backup_setup",
        "postgres_backup_run",
        "systemctl status postgres-logical-backup.timer",
        "journalctl -u postgres-logical-backup.service",
    ):
        assert statement in docs
