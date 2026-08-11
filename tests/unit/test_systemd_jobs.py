from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, StrictUndefined

REPO_ROOT = Path(__file__).resolve().parents[2]
ROLE_PATH = REPO_ROOT / "ansible/roles/systemd_jobs"
DEFAULTS_PATH = ROLE_PATH / "defaults/main.yml"
TASKS_PATH = ROLE_PATH / "tasks/main.yml"
SERVICE_TEMPLATE_PATH = ROLE_PATH / "templates/systemd-job.service.j2"
TIMER_TEMPLATE_PATH = ROLE_PATH / "templates/systemd-job.timer.j2"
DOCKER_TIMER_PATH = REPO_ROOT / "ansible/roles/docker/tasks/sub_tasks/prune/timer.yml"
DOCKER_MAIN_PATH = REPO_ROOT / "ansible/roles/docker/tasks/main.yml"


def task_named(tasks, name: str):
    return next(task for task in tasks if task.get("name") == name)


def valid_job(name: str = "example-job"):
    return {
        "name": name,
        "service": {"exec_start": "/bin/true"},
        "timer": {"on_calendar": "daily"},
    }


def run_role_check(
    tmp_path: Path,
    jobs=None,
    *,
    role_name: str = "systemd_jobs",
    service_mgr: str = "systemd",
    tags: str | None = None,
):
    playbook = tmp_path / "systemd-jobs.yml"
    play = {
        "name": "Exercise systemd_jobs validation",
        "hosts": "localhost",
        "connection": "local",
        "gather_facts": False,
        "vars": {"ansible_facts": {"service_mgr": service_mgr}},
        "roles": [role_name],
    }
    if jobs is not None:
        play["vars"]["systemd_jobs"] = jobs
    playbook.write_text(yaml.safe_dump([play], sort_keys=False))

    environment = os.environ.copy()
    environment.update(
        {
            "ANSIBLE_CONFIG": str(REPO_ROOT / "ansible/ansible.cfg"),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible-local"),
            "ANSIBLE_REMOTE_TEMP": str(tmp_path / "ansible-remote"),
        }
    )
    command = [str(Path(sys.executable).with_name("ansible-playbook")), "-i", "localhost,", str(playbook), "--check"]
    if tags is not None:
        command.extend(["--tags", tags])
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def render_template(path: Path, job: dict):
    environment = Environment(trim_blocks=True, lstrip_blocks=True, undefined=StrictUndefined)
    return environment.from_string(path.read_text()).render(systemd_jobs_job=job)


def test_defaults_to_empty_job_list_and_empty_role_is_safe(tmp_path: Path):
    assert yaml.safe_load(DEFAULTS_PATH.read_text()) == {"systemd_jobs": []}

    result = run_role_check(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Systemd jobs | Validate systemd host" in result.stdout
    assert "skipping: [localhost]" in result.stdout


def test_valid_job_check_mode_renders_units_without_systemd_lifecycle(tmp_path: Path):
    result = run_role_check(tmp_path, [valid_job()])
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "Systemd jobs | Render service units" in output
    assert "Systemd jobs | Render timer units" in output
    assert "Systemd jobs | Apply timer lifecycle" in output
    assert "skipping: [localhost]" in output


@pytest.mark.parametrize(
    ("jobs", "expected_message"),
    [
        ([{"service": {"exec_start": "/bin/true"}, "timer": {"on_calendar": "daily"}}], "requires a non-empty name"),
        ([valid_job("../unsafe")], "requires a non-empty name"),
        ([valid_job("duplicate"), valid_job("duplicate")], "names must be unique"),
        ([{"name": "missing-exec", "service": {}, "timer": {"on_calendar": "daily"}}], "missing, invalid, or unsupported"),
        ([{"name": "missing-calendar", "service": {"exec_start": "/bin/true"}, "timer": {}}], "missing, invalid, or unsupported"),
    ],
    ids=["missing-name", "unsafe-name", "duplicate-name", "missing-exec-start", "missing-on-calendar"],
)
def test_invalid_job_definitions_are_rejected(tmp_path: Path, jobs, expected_message: str):
    result = run_role_check(tmp_path, jobs)
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert expected_message in output


def test_docker_templates_emit_supported_service_and_timer_directives():
    job = {
        "name": "docker-prune-safe",
        "description": "Safe Docker prune cleanup",
        "service": {
            "type": "oneshot",
            "exec_start": "/usr/local/sbin/docker-prune-safe",
            "user": "root",
            "group": "root",
            "working_directory": "/var/lib/docker",
            "wants": ["docker.service"],
            "after": ["docker.service"],
            "nice": 10,
            "io_scheduling_class": "best-effort",
            "io_scheduling_priority": 7,
        },
        "timer": {
            "description": "Run safe Docker prune cleanup",
            "on_calendar": "Sun *-*-* 04:30:00",
            "randomized_delay_sec": "1h",
            "persistent": True,
        },
    }

    service = render_template(SERVICE_TEMPLATE_PATH, job)
    timer = render_template(TIMER_TEMPLATE_PATH, job)

    for directive in (
        "Description=Safe Docker prune cleanup",
        "Wants=docker.service",
        "After=docker.service",
        "Type=oneshot",
        "ExecStart=/usr/local/sbin/docker-prune-safe",
        "User=root",
        "Group=root",
        "WorkingDirectory=/var/lib/docker",
        "Nice=10",
        "IOSchedulingClass=best-effort",
        "IOSchedulingPriority=7",
    ):
        assert directive in service

    assert "Description=Run safe Docker prune cleanup" in timer
    assert "OnCalendar=Sun *-*-* 04:30:00" in timer
    assert "RandomizedDelaySec=1h" in timer
    assert "Persistent=true" in timer
    assert "WantedBy=timers.target" in timer


def test_unspecified_optional_directives_are_omitted_and_defaults_render():
    service = render_template(SERVICE_TEMPLATE_PATH, valid_job())
    timer = render_template(TIMER_TEMPLATE_PATH, valid_job())

    assert "Type=oneshot" in service
    assert "ExecStart=/bin/true" in service
    for directive in (
        "Wants=",
        "After=",
        "User=",
        "Group=",
        "WorkingDirectory=",
        "Nice=",
        "IOSchedulingClass=",
        "IOSchedulingPriority=",
    ):
        assert directive not in service

    assert "OnCalendar=daily" in timer
    assert "Persistent=true" in timer
    assert "RandomizedDelaySec=" not in timer


@pytest.mark.skipif(shutil.which("systemd-analyze") is None, reason="systemd-analyze is unavailable")
def test_rendered_units_pass_systemd_analyze_verify(tmp_path: Path):
    service_path = tmp_path / "example-job.service"
    timer_path = tmp_path / "example-job.timer"
    service_path.write_text(render_template(SERVICE_TEMPLATE_PATH, valid_job()))
    timer_path.write_text(render_template(TIMER_TEMPLATE_PATH, valid_job()))

    result = subprocess.run(
        ["systemd-analyze", "verify", str(service_path), str(timer_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_lifecycle_reloads_only_changed_units_and_restarts_only_changed_enabled_timers():
    tasks = yaml.safe_load(TASKS_PATH.read_text())
    reload_task = task_named(tasks, "Systemd jobs | Reload systemd for changed units")
    lifecycle_task = task_named(tasks, "Systemd jobs | Apply timer lifecycle")

    assert reload_task["ansible.builtin.systemd_service"] == {"daemon_reload": True}
    assert "selectattr('changed')" in " ".join(reload_task["when"])
    assert reload_task["when"][0] == "not ansible_check_mode"

    lifecycle = lifecycle_task["ansible.builtin.systemd_service"]
    assert lifecycle["enabled"] == "{{ systemd_jobs_timer_result.systemd_jobs_job.enabled | default(true) }}"
    assert "systemd_jobs_timer_result.changed" in lifecycle["state"]
    assert all(state in lifecycle["state"] for state in ("stopped", "restarted", "started"))
    assert lifecycle_task["when"] == "not ansible_check_mode"


def test_docker_prune_maps_existing_api_to_generic_role_and_preserves_tags():
    tasks = yaml.safe_load(DOCKER_TIMER_PATH.read_text())
    docker_main = yaml.safe_load(DOCKER_MAIN_PATH.read_text())
    include = task_named(tasks, "Docker prune timer | Manage systemd job")
    main_include = task_named(docker_main, "Docker Prune Timer")
    job = include["vars"]["systemd_jobs"][0]

    assert include["ansible.builtin.include_role"]["name"] == "systemd_jobs"
    assert set(include["ansible.builtin.include_role"]["apply"]["tags"]) == {"docker_prune_timer", "systemd_jobs"}
    assert set(include["tags"]) == {"docker_prune_timer", "systemd_jobs"}
    assert "docker_prune_timer" in main_include["ansible.builtin.include_tasks"]["apply"]["tags"]
    assert "docker_prune_timer" in main_include["tags"]
    assert job == {
        "name": "{{ docker_prune_timer_name }}",
        "description": "Safe Docker prune cleanup",
        "service": {
            "type": "oneshot",
            "exec_start": "{{ docker_prune_script_path }}",
            "wants": ["docker.service"],
            "after": ["docker.service"],
            "nice": 10,
            "io_scheduling_class": "best-effort",
            "io_scheduling_priority": 7,
        },
        "timer": {
            "description": "Run safe Docker prune cleanup",
            "on_calendar": "{{ docker_prune_timer_on_calendar }}",
            "randomized_delay_sec": "{{ docker_prune_timer_randomized_delay_sec }}",
            "persistent": True,
        },
        "enabled": True,
    }


def test_docker_prune_timer_tag_reaches_generic_role_and_non_systemd_hosts_skip(tmp_path: Path):
    systemd_result = run_role_check(tmp_path, role_name="docker", tags="docker_prune_timer")
    systemd_output = systemd_result.stdout + systemd_result.stderr
    assert systemd_result.returncode == 0, systemd_output
    assert "Docker prune timer | Install safe prune script" in systemd_output
    assert "Systemd jobs | Render service units" in systemd_output
    assert "Systemd jobs | Render timer units" in systemd_output

    non_systemd_result = run_role_check(
        tmp_path,
        role_name="docker",
        service_mgr="unraid",
        tags="docker_prune_timer",
    )
    non_systemd_output = non_systemd_result.stdout + non_systemd_result.stderr
    assert non_systemd_result.returncode == 0, non_systemd_output
    assert "Docker prune timer | Skip non-systemd hosts" in non_systemd_output
    assert "Systemd jobs | Validate job collection" not in non_systemd_output


def test_docker_prune_keeps_script_ownership_and_no_longer_renders_units_directly():
    tasks = yaml.safe_load(DOCKER_TIMER_PATH.read_text())
    source = DOCKER_TIMER_PATH.read_text()
    copy_tasks = [task for task in tasks if "ansible.builtin.copy" in task]

    assert len(copy_tasks) == 1
    assert copy_tasks[0]["ansible.builtin.copy"]["dest"] == "{{ docker_prune_script_path }}"
    assert "/etc/systemd/system/" not in source
    assert "ansible.builtin.systemd" not in source

    script = copy_tasks[0]["ansible.builtin.copy"]["content"]
    for variable in (
        "docker_prune_filesystem_path",
        "docker_prune_timer_min_usage_percent",
        "docker_prune_until",
        "docker_prune_containers",
        "docker_prune_images",
        "docker_prune_builder_cache",
        "docker_prune_networks",
        "docker_prune_volumes",
    ):
        assert variable in script
    for command in (
        'docker container prune -f --filter "until=${UNTIL}"',
        'docker image prune -a -f --filter "until=${UNTIL}"',
        'docker builder prune -a -f --filter "until=${UNTIL}"',
        'docker network prune -f --filter "until=${UNTIL}"',
        "docker volume prune -f",
    ):
        assert command in script


def test_docker_retains_non_systemd_skip_boundary_and_generic_role_has_no_docker_logic():
    docker_tasks = yaml.safe_load(DOCKER_TIMER_PATH.read_text())
    support = task_named(docker_tasks, "Docker prune timer | Set whether host supports systemd timers")
    skip = task_named(docker_tasks, "Docker prune timer | Skip non-systemd hosts")

    support_expression = support["ansible.builtin.set_fact"]["docker_prune_timer_systemd_supported"]
    assert "docker_prune_manage_timer" in support_expression
    assert "ansible_facts.service_mgr" in support_expression
    assert "systemd" in support_expression
    assert "not docker_prune_timer_systemd_supported | bool" in skip["when"]

    implementation = "\n".join(
        path.read_text()
        for path in (
            TASKS_PATH,
            SERVICE_TEMPLATE_PATH,
            TIMER_TEMPLATE_PATH,
        )
    )
    assert "docker" not in implementation.lower()
    assert all(task["tags"] == "systemd_jobs" for task in yaml.safe_load(TASKS_PATH.read_text()))
