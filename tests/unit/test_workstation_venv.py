import importlib.util
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, StrictUndefined

REPO_ROOT = Path(__file__).resolve().parents[2]
VENV_TASKS = yaml.safe_load((REPO_ROOT / "ansible/roles/workstation/tasks/tools/ansible.yml").read_text())
VENV_FILTER_PATH = REPO_ROOT / "ansible/roles/workstation/filter_plugins/workstation.py"
VENV_FILTER_SPEC = importlib.util.spec_from_file_location("workstation_venv", VENV_FILTER_PATH)
workstation_venv = importlib.util.module_from_spec(VENV_FILTER_SPEC)
assert VENV_FILTER_SPEC.loader is not None
VENV_FILTER_SPEC.loader.exec_module(workstation_venv)


def task_named(tasks, name):
    return next(task for task in tasks if task["name"] == name)


def test_venv_detects_python_abi_drift_before_mutating_the_environment():
    determine = task_named(VENV_TASKS, "Workstation Ansible | Determine Python ABI directory")
    interpreter = task_named(VENV_TASKS, "Workstation Ansible | Check existing Ansible virtualenv interpreter")
    site_packages = task_named(VENV_TASKS, "Workstation Ansible | Check matching Ansible virtualenv site-packages")
    probe = task_named(VENV_TASKS, "Workstation Ansible | Probe existing Ansible virtualenv interpreter")
    recreate = task_named(VENV_TASKS, "Workstation Ansible | Recreate Ansible virtualenv after Python ABI drift")

    assert (
        VENV_TASKS.index(determine)
        < VENV_TASKS.index(interpreter)
        < VENV_TASKS.index(site_packages)
        < VENV_TASKS.index(probe)
        < VENV_TASKS.index(recreate)
    )
    assert determine["changed_when"] is False
    assert determine["check_mode"] is False
    assert site_packages["ansible.builtin.stat"]["path"] == "{{ workstation_ansible_library_path.stdout | trim }}"
    assert probe["changed_when"] is False
    assert probe["failed_when"] is False
    assert probe["check_mode"] is False


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ({"python_exists": False, "system_abi": "python3.14"}, "create"),
        (
            {
                "python_exists": True,
                "site_packages_exists": True,
                "probe_rc": 0,
                "probe_abi": "python3.14",
                "system_abi": "python3.14",
            },
            "preserve",
        ),
        (
            {
                "python_exists": True,
                "site_packages_exists": True,
                "probe_rc": 126,
                "probe_abi": "",
                "system_abi": "python3.14",
            },
            "recreate",
        ),
        (
            {
                "python_exists": True,
                "site_packages_exists": False,
                "probe_rc": 0,
                "probe_abi": "python3.14",
                "system_abi": "python3.14",
            },
            "recreate",
        ),
        (
            {
                "python_exists": True,
                "site_packages_exists": True,
                "probe_rc": 0,
                "probe_abi": "python3.13",
                "system_abi": "python3.14",
            },
            "recreate",
        ),
    ],
)
def test_venv_recovery_decision_covers_missing_compatible_and_drifted_states(status, expected):
    original = status.copy()

    assert workstation_venv.workstation_venv_recovery_action(status) == expected
    assert status == original


def test_venv_tasks_consume_recovery_decision_without_check_mode_mutation(tmp_path):
    recreate = task_named(VENV_TASKS, "Workstation Ansible | Recreate Ansible virtualenv after Python ABI drift")
    create = task_named(VENV_TASKS, "Workstation Ansible | Create missing Ansible virtualenv")
    pip = task_named(VENV_TASKS, "Workstation Ansible | Upgrade pip tooling in virtualenv")
    fixture = tmp_path / "synthetic-venv"
    fixture.mkdir()
    marker = fixture / "preserved.txt"
    marker.write_text("synthetic fixture")
    before = {path.name: path.read_bytes() for path in fixture.iterdir()}

    action = workstation_venv.workstation_venv_recovery_action(
        {
            "python_exists": True,
            "site_packages_exists": False,
            "probe_rc": 0,
            "probe_abi": "python3.14",
            "system_abi": "python3.14",
        }
    )

    assert action == "recreate"
    assert {path.name: path.read_bytes() for path in fixture.iterdir()} == before
    assert recreate["when"][0] == "not ansible_check_mode"
    assert create["when"][0] == "not ansible_check_mode"
    assert "workstation_venv_recovery_action" in recreate["when"][1]
    assert "workstation_venv_recovery_action" in create["when"][1]
    assert recreate["ansible.builtin.command"]["argv"] == [
        "{{ workstation_ansible_python_executable }}",
        "-m",
        "venv",
        "--clear",
        "{{ workstation_ansible_venv_path }}",
    ]
    assert create["ansible.builtin.command"]["argv"] == [
        "{{ workstation_ansible_python_executable }}",
        "-m",
        "venv",
        "{{ workstation_ansible_venv_path }}",
    ]
    pip_module = pip["ansible.builtin.pip"]
    packages = pip_module["name"]

    assert [package.split("==", 1)[0] for package in packages] == ["pip", "setuptools", "wheel"]
    assert all(package.count("==") == 1 and package.split("==", 1)[1] for package in packages)
    assert pip_module["state"] == "present"
    assert pip_module["virtualenv"] == "{{ workstation_ansible_venv_path }}"
    assert VENV_TASKS.index(recreate) < VENV_TASKS.index(create) < VENV_TASKS.index(pip)


@pytest.mark.integration
@pytest.mark.parametrize("alternate", [False, True])
def test_selected_interpreter_drives_abi_library_path_and_environment_creation(tmp_path, alternate):
    defaults = yaml.safe_load((REPO_ROOT / "ansible/roles/workstation/defaults/main.yml").read_text())
    selected = defaults["workstation_ansible_python_executable"]
    marker = tmp_path / "interpreter-calls"
    if alternate:
        executable = tmp_path / "selected-python"
        executable.write_text(f"#!/bin/sh\nprintf 'called\\n' >> {shlex.quote(str(marker))}\nexec {shlex.quote(sys.executable)} \"$@\"\n")
        executable.chmod(0o700)
        selected = str(executable)
    venv = tmp_path / "venv"
    variables = dict(workstation_ansible_python_executable=selected, workstation_ansible_venv_path=str(venv))
    environment = Environment(undefined=StrictUndefined)
    commands = [task["ansible.builtin.command"]["argv"] for task in VENV_TASKS if "ansible.builtin.command" in task]

    def invoke(argv):
        rendered = [environment.from_string(argument).render(**variables) for argument in argv]
        before = marker.read_text() if marker.exists() else ""
        result = subprocess.check_output(rendered, text=True).strip()
        if alternate and argv[0] != "{{ workstation_ansible_venv_path }}/bin/python":
            assert marker.read_text() == before + "called\n"
        return result

    abi = invoke(next(argv for argv in commands if "sys.version_info" in str(argv) and argv[0].startswith("{{ workstation_ansible_python")))
    library = Path(invoke(next(argv for argv in commands if "sysconfig" in str(argv))))
    create = next(argv for argv in commands if "venv" in argv and "--clear" not in argv)
    recreate = next(argv for argv in commands if "--clear" in argv)
    invoke(create)
    assert library.is_dir()
    probe = next(argv for argv in commands if argv[0] == "{{ workstation_ansible_venv_path }}/bin/python")
    assert invoke(probe) == abi
    sentinel = venv / "old-environment"
    sentinel.touch()
    invoke(recreate)
    assert not sentinel.exists() and library.is_dir()
    assert invoke(probe) == abi
