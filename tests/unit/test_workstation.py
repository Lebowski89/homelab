from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from jinja2.nativetypes import NativeEnvironment

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK_PATH = REPO_ROOT / "ansible/playbook.yml"
ROLE_PATH = REPO_ROOT / "ansible/roles/workstation"
DEFAULTS_PATH = ROLE_PATH / "defaults/main.yml"
MAIN_TASKS_PATH = ROLE_PATH / "tasks/main.yml"
VALIDATE_TASKS_PATH = ROLE_PATH / "tasks/validate.yml"
DEVELOPMENT_TASKS_PATH = ROLE_PATH / "tasks/development.yml"
VSCODE_TASKS_PATH = ROLE_PATH / "tasks/vscode.yml"
STANDALONE_PLAYBOOK_PATH = REPO_ROOT / "ansible/workstation.yml"
BOOTSTRAP_SCRIPT_PATH = REPO_ROOT / "scripts/bootstrap-workstation.sh"
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


def test_main_playbook_dispatches_workstation_role_from_inventory_group():
    plays = load_yaml(PLAYBOOK_PATH)
    play = next(play for play in plays if play["name"] == "Deploy homelab services")
    include = next(task for task in play["tasks"] if task["name"] == "Include Workstation role")

    assert play["hosts"] == "tags_skynet"
    assert play["become"] is True
    assert include["ansible.builtin.include_role"]["name"] == "workstation"
    assert include["when"] == "'tags_workstation' in group_names"
    assert set(include["tags"]) == WORKSTATION_TAGS
    assert include["ansible.builtin.include_role"]["apply"]["tags"] == ["workstation"]
    assert "blacktop" not in str(include)


def test_ubuntu_role_remains_explicitly_ubuntu_only():
    plays = load_yaml(PLAYBOOK_PATH)
    play = next(play for play in plays if play["name"] == "Deploy homelab services")
    include = next(task for task in play["tasks"] if task["name"] == "Include Ubuntu role")

    assert include["when"] == [
        'ansible_facts.os_family | default("") == "Debian"',
        'ansible_facts.distribution | default("") == "Ubuntu"',
    ]


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


def test_workstation_user_is_resolved_from_remote_inventory_identity():
    defaults = load_yaml(DEFAULTS_PATH)
    validation = load_yaml(VALIDATE_TASKS_PATH)
    getent = next(task for task in validation if task["name"] == "Workstation | Read workstation user account")
    resolution = next(task for task in validation if task["name"] == "Workstation | Resolve workstation user facts")

    assert defaults["workstation_user"] == "{{ ansible_user }}"
    rendered_user = NativeEnvironment().from_string(defaults["workstation_user"]).render(ansible_user="remote-user", ansible_user_id="root")
    assert rendered_user == "remote-user"
    assert getent["ansible.builtin.getent"]["key"] == "{{ workstation_user }}"
    assert set(resolution["ansible.builtin.set_fact"]) == {
        "workstation_user_uid",
        "workstation_user_gid",
        "workstation_user_home",
    }
    assert all("getent_passwd[workstation_user]" in value for value in resolution["ansible.builtin.set_fact"].values())


def run_workstation_path_validation(tmp_path: Path, shell_directories, xdg_directories):
    playbook = tmp_path / "validate-paths.yml"
    playbook.write_text(
        yaml.safe_dump(
            [
                {
                    "name": "Validate workstation paths",
                    "hosts": "localhost",
                    "connection": "local",
                    "gather_facts": False,
                    "vars": {
                        "workstation_shell_directories": shell_directories,
                        "workstation_xdg_directories": xdg_directories,
                    },
                    "tasks": [{"ansible.builtin.import_tasks": str(VALIDATE_TASKS_PATH)}],
                }
            ],
            sort_keys=False,
        )
    )
    environment = os.environ.copy()
    environment["ANSIBLE_LOCAL_TEMP"] = str(tmp_path / "ansible-local")
    environment["ANSIBLE_REMOTE_TEMP"] = str(tmp_path / "ansible-remote")
    return subprocess.run(
        [
            ANSIBLE_PLAYBOOK,
            "-i",
            "localhost,",
            str(playbook),
            "--start-at-task",
            "Workstation | Validate user path variables",
        ],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    ("shell_directories", "xdg_directories"),
    [
        ([], []),
        (["/home/operator/.ssh", "/home/operator/.local/bin"], ["/home/operator/Desktop"]),
    ],
)
def test_workstation_user_path_validation_accepts_absolute_string_lists(tmp_path: Path, shell_directories, xdg_directories):
    result = run_workstation_path_validation(tmp_path, shell_directories, xdg_directories)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("variable", ["shell", "xdg"])
@pytest.mark.parametrize("invalid_entry", [1, "", "   ", "relative/path"])
def test_workstation_user_path_validation_rejects_invalid_entries(tmp_path: Path, variable: str, invalid_entry):
    shell_directories = ["/home/operator/.ssh"]
    xdg_directories = ["/home/operator/Desktop"]
    if variable == "shell":
        shell_directories = [invalid_entry]
    else:
        xdg_directories = [invalid_entry]

    result = run_workstation_path_validation(tmp_path, shell_directories, xdg_directories)

    assert result.returncode != 0
    assert "Workstation user paths must be lists of non-empty absolute path strings." in result.stdout + result.stderr


def test_workstation_no_longer_provisions_a_local_ansible_controller():
    defaults = DEFAULTS_PATH.read_text()
    role_source = "\n".join(path.read_text() for path in ROLE_PATH.rglob("*.yml"))

    for obsolete in (
        "workstation_ansible_venv_enabled",
        "workstation_ansible_venv_path",
        "workstation_ansible_requirements_path",
        "workstation_ansible_collections_requirements_path",
        "workstation_ansible_collections_path",
        "ansible-galaxy",
        "ansible.builtin.pip",
        "playbook_dir",
    ):
        assert obsolete not in defaults
        assert obsolete not in role_source

    development = load_yaml(DEVELOPMENT_TASKS_PATH)
    assert [task["name"] for task in development] == [
        "Workstation Development | Install development packages",
        "Workstation Development | Manage Git identity block",
    ]
    assert not STANDALONE_PLAYBOOK_PATH.exists()
    assert not BOOTSTRAP_SCRIPT_PATH.exists()


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
def test_main_playbook_accepts_each_workstation_tag_with_synthetic_inventory(tmp_path: Path, tag: str):
    inventory = tmp_path / "inventory.ini"
    inventory.write_text(
        """[tags_skynet]
blacktop ansible_connection=local

[tags_workstation]
blacktop
"""
    )
    result = subprocess.run(
        [
            ANSIBLE_PLAYBOOK,
            "-i",
            str(inventory),
            str(PLAYBOOK_PATH),
            "--tags",
            tag,
            "--limit",
            "blacktop",
            "--list-tasks",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Include Workstation role" in result.stdout
    assert tag in result.stdout
