import importlib.util
from pathlib import Path

import pytest
import yaml

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
        "python3",
        "-m",
        "venv",
        "--clear",
        "{{ workstation_ansible_venv_path }}",
    ]
    assert create["ansible.builtin.command"]["argv"] == [
        "python3",
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
