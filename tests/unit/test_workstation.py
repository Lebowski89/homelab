from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK_PATH = REPO_ROOT / "ansible/workstation.yml"
ROLE_PATH = REPO_ROOT / "ansible/roles/workstation"
MAIN_TASKS_PATH = ROLE_PATH / "tasks/main.yml"
VALIDATE_TASKS_PATH = ROLE_PATH / "tasks/validate.yml"
VSCODE_TASKS_PATH = ROLE_PATH / "tasks/vscode.yml"
ANSIBLE_PLAYBOOK = shutil.which("ansible-playbook") or str(Path(sys.executable).with_name("ansible-playbook"))

WORKSTATION_TAGS = {
    "workstation",
    "workstation_apt",
    "workstation_dev",
    "workstation_vscode",
    "workstation_shell",
    "workstation_desktop",
}


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text())


def test_workstation_playbook_is_local_and_isolated_from_server_roles():
    plays = load_yaml(PLAYBOOK_PATH)

    assert len(plays) == 1
    play = plays[0]
    assert play["hosts"] == "localhost"
    assert play["connection"] == "local"
    assert play["gather_facts"] is True
    assert play["become"] is False

    include = play["tasks"][0]
    assert include["ansible.builtin.include_role"]["name"] == "workstation"
    assert set(include["tags"]) == WORKSTATION_TAGS
    assert set(include["ansible.builtin.include_role"]["apply"]["tags"]) == WORKSTATION_TAGS
    assert "ubuntu" not in PLAYBOOK_PATH.read_text().lower()


def test_workstation_dynamic_includes_propagate_their_selection_tags():
    tasks = load_yaml(MAIN_TASKS_PATH)

    for task in tasks:
        include = task["ansible.builtin.include_tasks"]
        outer_tags = set(task["tags"])
        applied_tags = set(include["apply"]["tags"])
        assert "workstation" in outer_tags
        assert applied_tags == outer_tags

    validation = tasks[0]
    assert set(validation["tags"]) == WORKSTATION_TAGS

    expected_sections = {
        "workstation_apt": "apt.yml",
        "workstation_dev": "development.yml",
        "workstation_vscode": "vscode.yml",
        "workstation_shell": "shell.yml",
        "workstation_desktop": "desktop.yml",
    }
    for tag, task_file in expected_sections.items():
        selected_files = {task["ansible.builtin.include_tasks"]["file"] for task in tasks if tag in task["tags"]}
        assert selected_files == {"validate.yml", task_file}


def test_workstation_platform_guard_is_debian_family_apt_and_systemd():
    validation = load_yaml(VALIDATE_TASKS_PATH)
    platform_assert = validation[0]["ansible.builtin.assert"]["that"]

    assert 'ansible_facts.os_family | default("") == "Debian"' in platform_assert
    assert 'ansible_facts.pkg_mgr | default("") == "apt"' in platform_assert
    assert 'ansible_facts.service_mgr | default("") == "systemd"' in platform_assert


def test_workstation_does_not_manage_server_networking_or_ssh_state():
    role_source = "\n".join(path.read_text() for path in ROLE_PATH.rglob("*.yml")).lower()

    assert "netplan" not in role_source
    assert "networkmanager" not in role_source
    assert "sshd" not in role_source
    assert "openssh-server" not in role_source


def test_vscode_uses_microsoft_apt_repository_and_user_extensions():
    tasks = load_yaml(VSCODE_TASKS_PATH)
    source_task = next(task for task in tasks if task["name"].endswith("Configure Microsoft repository"))
    extension_task = next(task for task in tasks if task["name"].endswith("Install configured extensions"))

    source = source_task["ansible.builtin.copy"]["content"]
    assert "https://packages.microsoft.com/repos/code" in source
    assert "Signed-By: {{ workstation_vscode_key_path }}" in source
    assert extension_task["become_user"] == "{{ workstation_user }}"
    assert extension_task["ansible.builtin.command"]["argv"][:2] == ["code", "--install-extension"]
    assert extension_task["loop"] == "{{ workstation_vscode_extensions }}"


@pytest.mark.skipif(ANSIBLE_PLAYBOOK is None, reason="ansible-playbook is unavailable")
@pytest.mark.parametrize("tag", sorted(WORKSTATION_TAGS))
def test_ansible_accepts_each_workstation_tag(tag: str):
    result = subprocess.run(
        [
            ANSIBLE_PLAYBOOK,
            "-i",
            "localhost,",
            str(PLAYBOOK_PATH),
            "--tags",
            tag,
            "--list-tasks",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Include workstation role" in result.stdout
    assert tag in result.stdout
