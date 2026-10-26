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
SHELL_TASKS_PATH = ROLE_PATH / "tasks/shell.yml"
DESKTOP_TASKS_PATH = ROLE_PATH / "tasks/desktop.yml"
VSCODE_TASKS_PATH = ROLE_PATH / "tasks/vscode.yml"
ANSIBLE_PLAYBOOK = shutil.which(str(Path(sys.executable).with_name("ansible-playbook")))

TOOL_TAGS = {
    "workstation_tools",
    "workstation_repository",
    "workstation_ansible",
    "workstation_collections",
    "workstation_skynet",
    "workstation_opentofu",
}

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


def test_main_playbook_provisions_workstation_first_and_only_once():
    plays = load_yaml(PLAYBOOK_PATH)
    play = plays[0]
    include = next(task for task in play["tasks"] if "ansible.builtin.include_role" in task)
    assert play["hosts"] == "{{ workstation_hosts | default('tags_workstation') }}"
    assert play["become"] is True
    assert play["tasks"][0]["become"] is False
    assert include["ansible.builtin.include_role"]["name"] == "workstation"
    assert set(include["tags"]) == WORKSTATION_TAGS | TOOL_TAGS | {"workstation_credentials"}
    assert include["ansible.builtin.include_role"]["apply"]["tags"] == ["workstation"]
    assert all(
        task.get("ansible.builtin.include_role", {}).get("name") != "workstation" for later in plays[1:] for task in later.get("tasks", [])
    )
    assert not (REPO_ROOT / "ansible/workstation.yml").exists()


def test_workstation_dynamic_includes_propagate_their_selection_tags():
    tasks = [
        task
        for task in load_yaml(MAIN_TASKS_PATH)
        if task["name"]
        not in {"Workstation | Configure automation tooling", "Workstation | Set up password files only when explicitly selected"}
    ]

    for task in tasks:
        include = task["ansible.builtin.include_tasks"]
        outer_tags = set(task["tags"])
        applied_tags = set(include["apply"]["tags"])
        assert "workstation" in outer_tags
        assert applied_tags == outer_tags

    validation = tasks[0]
    assert set(validation["tags"]) == WORKSTATION_TAGS

    expected_sections = {
        "workstation_apt": "packages.yml",
        "workstation_dev": "development.yml",
        "workstation_vscode": "vscode.yml",
        "workstation_shell": "shell.yml",
        "workstation_desktop": "desktop.yml",
    }
    for tag, task_file in expected_sections.items():
        selected_files = {task["ansible.builtin.include_tasks"]["file"] for task in tasks if tag in task["tags"]}
        assert selected_files == {"validate.yml", task_file}


def test_workstation_entries_share_the_platform_guard():
    for entry in ("validate.yml", "tools/validate_tools.yml", "tools/opentofu.yml", "vscode.yml"):
        tasks = load_yaml(ROLE_PATH / "tasks" / entry)
        assert (ROLE_PATH / "tasks" / entry).parent.joinpath(
            tasks[0]["ansible.builtin.import_tasks"]
        ).resolve() == ROLE_PATH / "tasks/platform.yml"


def test_workstation_user_is_resolved_from_remote_inventory_identity():
    defaults = load_yaml(DEFAULTS_PATH)
    validation = load_yaml(VALIDATE_TASKS_PATH)
    getent = next(task for task in validation if task["name"] == "Workstation | Read workstation user account")
    resolution = next(task for task in validation if task["name"] == "Workstation | Resolve workstation user facts")

    rendered_user = NativeEnvironment().from_string(defaults["workstation_user"]).render(ansible_user="remote-user", ansible_user_id="root")
    assert rendered_user == "remote-user"
    local_user = NativeEnvironment().from_string(defaults["workstation_user"]).render(ansible_facts={"user_id": "local-user"})
    assert local_user == "local-user"
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


@pytest.mark.integration
@pytest.mark.skipif(ANSIBLE_PLAYBOOK is None, reason="ansible-playbook is unavailable")
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


@pytest.mark.integration
@pytest.mark.skipif(ANSIBLE_PLAYBOOK is None, reason="ansible-playbook is unavailable")
@pytest.mark.parametrize("variable", ["shell", "xdg"])
@pytest.mark.parametrize("invalid_entry", [1, "", "   ", "relative/path", "/home/operator/bin "])
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


def test_workstation_tooling_is_opt_in_and_isolated_from_development_baseline():
    defaults = load_yaml(DEFAULTS_PATH)
    assert defaults["workstation_tools_enabled"] is False
    assert defaults["workstation_repository_clone"] is False
    assert defaults["workstation_opentofu_enabled"] is False
    development = load_yaml(DEVELOPMENT_TASKS_PATH)
    assert [task["name"] for task in development] == [
        "Workstation Development | Install development packages",
        "Workstation Development | Manage Git identity block",
    ]


def test_workstation_does_not_manage_server_networking_or_ssh_state():
    role_source = "\n".join(path.read_text() for path in ROLE_PATH.rglob("*.yml")).lower()

    assert "netplan" not in role_source
    assert "networkmanager" not in role_source
    assert "sshd" not in role_source
    assert "openssh-server" not in role_source


def test_vscode_uses_microsoft_apt_repository_and_user_extensions():
    tasks = load_yaml(ROLE_PATH / "tasks/debian/vscode.yml")
    common = load_yaml(VSCODE_TASKS_PATH)
    source_task = next(task for task in tasks if "ansible.builtin.copy" in task)
    install_task = next(task for task in tasks if task.get("ansible.builtin.apt", {}).get("name") == "code")
    extension_task = next(task for task in common if "--install-extension" in task.get("ansible.builtin.command", {}).get("argv", []))

    source = source_task["ansible.builtin.copy"]["content"]
    assert "https://packages.microsoft.com/repos/code" in source
    assert "Signed-By: {{ workstation_vscode_key_path }}" in source
    cache_valid_time = install_task["ansible.builtin.apt"]["cache_valid_time"]
    assert NativeEnvironment().from_string(cache_valid_time).render(workstation_vscode_repository={"changed": True}) == 0
    assert NativeEnvironment().from_string(cache_valid_time).render(workstation_vscode_repository={"changed": False}) == 3600
    assert extension_task["become_user"] == "{{ workstation_user }}"
    assert extension_task["ansible.builtin.command"]["argv"][:2] == ["code", "--install-extension"]
    assert extension_task["loop"] == "{{ workstation_vscode_extensions }}"


def test_workstation_directory_tasks_preserve_existing_permissions():
    shell_task = next(task for task in load_yaml(SHELL_TASKS_PATH) if task["name"].endswith("Ensure user shell directories exist"))
    desktop_task = next(task for task in load_yaml(DESKTOP_TASKS_PATH) if task["name"].endswith("Ensure XDG user directories exist"))

    for task in (shell_task, desktop_task):
        directory = task["ansible.builtin.file"]
        assert directory["state"] == "directory"
        assert "mode" not in directory


@pytest.mark.integration
@pytest.mark.skipif(ANSIBLE_PLAYBOOK is None, reason="ansible-playbook is unavailable")
@pytest.mark.parametrize("tag", sorted(WORKSTATION_TAGS | TOOL_TAGS))
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
        env={
            **os.environ,
            "ANSIBLE_CONFIG": str(REPO_ROOT / "ansible/bootstrap.cfg"),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
            "ANSIBLE_COLLECTIONS_PATH": str(tmp_path / "empty-collections"),
            "ANSIBLE_COLLECTIONS_SCAN_SYS_PATH": "false",
        },
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Include Workstation role" in result.stdout
    assert tag in result.stdout


# Real Ansible dispatch with controller-side fake operations. These fixtures never
# invoke host package managers, downloads, sudo, user executables or services.
@pytest.fixture
def workstation_run(tmp_path):
    import json

    copied = tmp_path / "roles/workstation"
    shutil.copytree(ROLE_PATH, copied, ignore=shutil.ignore_patterns("__pycache__"))
    operations = {
        "apt",
        "dnf",
        "get_url",
        "rpm_key",
        "yum_repository",
        "apt_repository",
        "deb822_repository",
        "lineinfile",
        "copy",
        "file",
        "template",
        "command",
        "pip",
        "git",
        "blockinfile",
        "stat",
        "getent",
    }

    def instrument(tasks):
        for task in tasks:
            for branch in ("block", "rescue", "always"):
                instrument(task.get(branch, []))
            for module in operations:
                key = f"ansible.builtin.{module}"
                if key in task:
                    task["fixture_operation"] = {"module": module, "options": task.pop(key)}
                    if module in {"deb822_repository", "lineinfile"}:
                        # The optional real modules operate only on test-owned
                        # temporary paths, always as the invoking test user.
                        task["become"] = False

    for path in (copied / "tasks").rglob("*.yml"):
        tasks = load_yaml(path)
        instrument(tasks)
        path.write_text(yaml.safe_dump(tasks, sort_keys=False))
    plugins = tmp_path / "action_plugins"
    plugins.mkdir()
    (plugins / "fixture_operation.py").write_text(
        """from ansible.plugins.action import ActionBase
import json
from pathlib import Path
class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        module = self._task.args['module']
        options = self._task.args['options']
        with open(task_vars['fixture_record'], 'a') as output:
            output.write(json.dumps({'module': module, 'options': options,
                                     'user': self._play_context.become_user}, default=str) + '\\n')
        result = {'changed': False, 'rc': 0, 'stdout': '', 'stdout_lines': []}
        sources = task_vars.get('fixture_sources_dir')
        if sources and module in ('deb822_repository', 'lineinfile'):
            options = dict(options)
            if module == 'lineinfile':
                options['path'] = str(Path(sources) / Path(options['path']).name)
            return self._execute_module(
                module_name='fixture_deb822_repository' if module == 'deb822_repository' else 'ansible.builtin.lineinfile',
                module_args=options, task_vars=task_vars)
        if module == 'stat':
            result['stat'] = {'exists': task_vars['fixture_ostree'] if options['path'] == '/run/ostree-booted' else True,
                              'isreg': True}
        elif module == 'setup':
            result['ansible_facts'] = task_vars['fixture_system_facts']
        elif module == 'getent':
            result['ansible_facts'] = {'getent_passwd': task_vars['fixture_passwd']}
        elif module == 'command' and 'argv' in options:
            program = str(options['argv'])
            result['stdout'] = '/fixture/home/venv/lib64/python3.13/site-packages' if 'sysconfig' in program else 'python3.13'
        return result
"""
    )
    cfg = tmp_path / "ansible.cfg"
    cfg.write_text(f"[defaults]\naction_plugins = {plugins}\nhost_key_checking = True\n")
    record = tmp_path / "operations.jsonl"

    def run(
        *,
        fedora=False,
        tags="workstation",
        overrides=None,
        ostree=False,
        check=False,
        main=False,
        managed=False,
        inline=False,
        apt_sources=None,
    ):
        record.unlink(missing_ok=True)
        if apt_sources is not None:
            from ansible.modules import deb822_repository

            # Exercise the installed repository module, changing only its fixed
            # destination directory. All package managers and downloads stay stubbed.
            source = Path(deb822_repository.__file__).read_text()
            assert source.count("'/etc/apt/sources.list.d'") == 1
            (copied / "library/fixture_deb822_repository.py").write_text(
                source.replace("'/etc/apt/sources.list.d'", repr(str(apt_sources)))
            )
        facts = {
            "distribution": "Fedora" if fedora else "Debian",
            "os_family": "RedHat" if fedora else "Debian",
            "pkg_mgr": "dnf5" if fedora else "apt",
            "service_mgr": "systemd",
            "getent_passwd": {"fixture": ["x", "1001", "1001", "", "/fixture/home", "/bin/bash"]},
        }
        variables = {
            "ansible_user": "fixture",
            "ansible_facts": facts,
            "fixture_passwd": facts["getent_passwd"],
            "fixture_record": str(record),
            "fixture_ostree": ostree,
            "workstation_tools_enabled": True,
            "workstation_opentofu_enabled": True,
        }
        variables.update(overrides or {})
        if apt_sources is not None:
            variables["fixture_sources_dir"] = str(apt_sources)
        play = tmp_path / "play.yml"
        play.write_text(
            yaml.safe_dump(
                [{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": variables, "roles": ["workstation"]}]
            )
        )
        inventory_args = ["-i", "localhost,"]
        environment = {**os.environ, "ANSIBLE_CONFIG": str(cfg), "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local")}
        if main:
            # Run the real complete entry point, with only host operations mocked.
            plays = load_yaml(PLAYBOOK_PATH)
            instrument(plays[0]["tasks"])
            setup = plays[0]["tasks"][0]
            setup["fixture_operation"] = {"module": "setup", "options": setup.pop("ansible.builtin.setup")}
            play = tmp_path / "playbook.yml"
            play.write_text(yaml.safe_dump(plays, sort_keys=False))
            shutil.copytree(REPO_ROOT / "ansible/tasks", tmp_path / "tasks", dirs_exist_ok=True)
            hosts = tmp_path / "host_vars"
            hosts.mkdir(exist_ok=True)
            shutil.copyfile(REPO_ROOT / "ansible/host_vars/blacktop.yml", hosts / "blacktop.yml")
            # An unreadable fake Vault catches accidental application-wide loading.
            group_vars = tmp_path / "group_vars/all"
            group_vars.mkdir(parents=True, exist_ok=True)
            (group_vars / "private.yml").write_text("$ANSIBLE_VAULT;1.1;AES256\nsynthetic-invalid-vault\n")
            config = (REPO_ROOT / "ansible/bootstrap.cfg").read_text()
            cfg.write_text(config.replace("[defaults]", f"[defaults]\naction_plugins = {plugins}"))
            facts["user_id"] = "fixture"
            variables.pop("ansible_user")
            variables.pop("ansible_facts")
            variables.pop("workstation_tools_enabled")
            variables.pop("workstation_opentofu_enabled")
            variables.update(fixture_system_facts=facts, ansible_connection="local")
            variables.update(overrides or {})
            inventory = tmp_path / "inventory.yml"
            children = {"tags_workstation": {"hosts": {"blacktop": variables}}}
            if managed:
                children["tags_skynet"] = {"hosts": {"blacktop": {}}}
            inventory.write_text(yaml.safe_dump({"all": {"children": children}}))
            inventory_args = ["-i", str(inventory)]
            if inline:
                bootstrap_vars = tmp_path / "bootstrap-vars.yml"
                bootstrap_vars.write_text(yaml.safe_dump(variables))
                inventory_args = ["-i", "blacktop,", "-c", "local", "-e", "workstation_hosts=blacktop", "-e", f"@{bootstrap_vars}"]
            # No NetBox credentials, application Vault passwords or installed
            # collections are supplied. Disable scanning site-packages as well.
            environment.update(ANSIBLE_COLLECTIONS_PATH=str(tmp_path / "empty-collections"), ANSIBLE_COLLECTIONS_SCAN_SYS_PATH="false")
            assert not (tmp_path / "netbox.yml").exists()
        args = [ANSIBLE_PLAYBOOK, *inventory_args, str(play), "--tags", tags]
        if check:
            args.append("--check")
        result = subprocess.run(
            args,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        calls = [json.loads(line) for line in record.read_text().splitlines()] if record.exists() else []
        return result, calls

    return run


@pytest.mark.integration
@pytest.mark.parametrize("legacy", [False, True])
def test_opentofu_deb822_migration_refreshes_cache_and_preserves_other_sources(workstation_run, tmp_path, legacy):
    dependency = subprocess.run(["/usr/bin/python3", "-c", "import debian.deb822"], capture_output=True, check=False)
    if dependency.returncode:
        pytest.skip("the real deb822 module requires system python3-debian; never install dependencies in this test")
    sources = tmp_path / "apt-sources"
    sources.mkdir()
    overrides = {
        "workstation_opentofu_repo_filename": "fixture-tofu",
        "workstation_opentofu_source_url": "https://packages.example.test/tofu/",
        "workstation_opentofu_source_suite": "fixture-suite",
        "workstation_opentofu_keyring_file": str(tmp_path / "package-key.gpg"),
        "workstation_opentofu_keyring_file_repo": str(tmp_path / "repository-key.gpg"),
    }
    old_entry = (
        f"deb [signed-by={overrides['workstation_opentofu_keyring_file']},{overrides['workstation_opentofu_keyring_file_repo']}] "
        "https://packages.example.test/tofu/ fixture-suite main\n"
    )
    unrelated = "# Keep locally configured sources\ndeb https://other.example.test/debian stable main\n"
    old_file = sources / "fixture-tofu.list"
    if legacy:
        old_file.write_text(unrelated + old_entry)

    def run():
        result, calls = workstation_run(tags="workstation_opentofu", overrides=overrides, apt_sources=sources)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "DEPRECATION WARNING" not in result.stdout + result.stderr
        return calls

    calls = run()
    source = sources / "fixture-tofu.sources"
    fields = dict(line.split(": ", 1) for line in source.read_text().splitlines())
    assert (
        fields.items()
        >= {
            "Types": "deb",
            "URIs": overrides["workstation_opentofu_source_url"],
            "Suites": overrides["workstation_opentofu_source_suite"],
            "Components": "main",
            "Signed-By": f"{overrides['workstation_opentofu_keyring_file']} {overrides['workstation_opentofu_keyring_file_repo']}",
        }.items()
    )
    assert source.stat().st_mode & 0o777 == 0o644
    assert old_file.read_text() == unrelated if legacy else not old_file.exists()
    assert any(call["module"] == "apt" and "python3-debian" in call["options"].get("name", []) for call in calls)
    refresh = next(i for i, call in enumerate(calls) if call["module"] == "apt" and call["options"] == {"update_cache": True})
    assert refresh > next(i for i, call in enumerate(calls) if call["module"] == "lineinfile")
    assert calls[refresh + 1]["module"] == "apt"
    assert calls[refresh + 1]["options"]["state"] == "present"

    before = (source.read_bytes(), source.stat().st_mtime_ns)
    calls = run()
    assert (source.read_bytes(), source.stat().st_mtime_ns) == before
    assert not any(call["module"] == "apt" and call["options"] == {"update_cache": True} for call in calls)

    # A legacy-only change must also refresh the cache, even if .sources is unchanged.
    old_file.write_text(unrelated + old_entry)
    calls = run()
    assert old_file.read_text() == unrelated
    assert (source.read_bytes(), source.stat().st_mtime_ns) == before
    assert any(call["module"] == "apt" and call["options"] == {"update_cache": True} for call in calls)


@pytest.mark.integration
@pytest.mark.parametrize("fedora", [False, True])
def test_effective_platform_packages_and_shared_user_configuration(workstation_run, fedora):
    result, calls = workstation_run(
        fedora=fedora,
        overrides={
            "workstation_packages": ["fixture-host-package"],
            "workstation_git_manage_config": True,
            "workstation_git_user_name": "Fixture User",
            "workstation_git_user_email": "fixture@example.test",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    manager = "dnf" if fedora else "apt"
    installs = [call["options"] for call in calls if call["module"] == manager]
    assert any(options["name"] == ["fixture-host-package"] for options in installs)
    assert all(options["state"] == "present" and options["name"] != ["*"] for options in installs)
    assert not any(call["module"] == ("apt" if fedora else "dnf") for call in calls)
    names = {name for options in installs for name in options["name"]}
    assert ("python3-devel" in names) is fedora
    assert ("python3-venv" in names) is not fedora
    assert not ({"python3-apt", "build-essential", "python3-dev"} & names) if fedora else True
    git = next(call for call in calls if call["module"] == "blockinfile")
    assert git["user"] == "fixture"
    assert git["options"]["path"] == "/fixture/home/.gitconfig"
    pip = [call for call in calls if call["module"] == "pip"]
    assert any(call["options"].get("requirements", "").endswith("/ansible/requirements.txt") for call in pip)
    assert any(call["module"] == "command" and "collection" in call["options"].get("argv", []) for call in calls)
    assert not any("proxmox" in str(call).lower() for call in calls)
    rpm_repos = [call["options"] for call in calls if call["module"] == "yum_repository"]
    if fedora:
        assert {repo["name"] for repo in rpm_repos} == {"code", "opentofu"}
        assert all(repo["gpgcheck"] and repo["sslverify"] for repo in rpm_repos)
    else:
        assert not rpm_repos
        source = next(
            call["options"]["content"] for call in calls if call["module"] == "copy" and "Types: deb" in call["options"].get("content", "")
        )
        assert "Signed-By:" in source


@pytest.mark.integration
@pytest.mark.parametrize(
    "tag",
    [
        "workstation_apt",
        "workstation_dev",
        "workstation_desktop",
        "workstation_vscode",
        "workstation_ansible",
        "workstation_collections",
        "workstation_opentofu",
    ],
)
@pytest.mark.parametrize("fedora", [False, True])
def test_platform_selection_survives_granular_dynamic_tags(workstation_run, tag, fedora):
    result, calls = workstation_run(fedora=fedora, tags=tag)
    assert result.returncode == 0, result.stdout + result.stderr
    packages = [call for call in calls if call["module"] in {"apt", "dnf"}]
    if tag != "workstation_collections":
        assert packages
        assert {call["module"] for call in packages} == {"dnf" if fedora else "apt"}
        if tag == "workstation_apt":
            names = {name for call in packages for name in call["options"]["name"]}
            assert ("openssh-clients" in names) is fedora
            assert ("openssh-client" in names) is not fedora
    else:
        assert not packages
        assert any(call["module"] == "command" and "collection" in call["options"].get("argv", []) for call in calls)
    if tag != "workstation_vscode":
        assert not any(call["module"] == "yum_repository" and call["options"].get("name") == "code" for call in calls)


@pytest.mark.integration
@pytest.mark.parametrize(
    "facts, ostree",
    [
        ({"os_family": "RedHat", "distribution": "Fedora", "pkg_mgr": "dnf5", "service_mgr": "systemd"}, True),
        ({"os_family": "RedHat", "distribution": "Bazzite", "pkg_mgr": "dnf5", "service_mgr": "systemd"}, False),
        ({"os_family": "RedHat", "distribution": "Fedora", "pkg_mgr": "atomic_container", "service_mgr": "systemd"}, False),
        ({"os_family": "RedHat", "distribution": "Nobara", "pkg_mgr": "dnf", "service_mgr": "systemd"}, False),
    ],
)
@pytest.mark.parametrize("tag", ["workstation", "workstation_ansible", "workstation_opentofu"])
def test_unsupported_platform_is_rejected_before_mutation(workstation_run, facts, ostree, tag):
    result, calls = workstation_run(fedora=True, tags=tag, overrides={"ansible_facts": facts}, ostree=ostree)
    assert result.returncode != 0
    assert calls and all(call["module"] == "stat" for call in calls)
    assert "unsupported" in result.stdout.lower()


@pytest.mark.integration
@pytest.mark.parametrize("fedora", [False, True])
def test_check_mode_never_calls_external_installers(workstation_run, fedora):
    result, calls = workstation_run(fedora=fedora, check=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not any(
        call["module"]
        in {
            "apt",
            "dnf",
            "get_url",
            "rpm_key",
            "yum_repository",
            "apt_repository",
            "deb822_repository",
            "lineinfile",
            "pip",
            "command",
            "git",
        }
        for call in calls
    )
    assert "Would install" in result.stdout
    assert "Would ensure" in result.stdout


@pytest.mark.integration
def test_host_feature_toggles_skip_installers(workstation_run):
    result, calls = workstation_run(
        fedora=True,
        overrides={
            "workstation_vscode_enabled": False,
            "workstation_opentofu_enabled": False,
            "workstation_ansible_enabled": False,
            "workstation_ansible_collections_enabled": False,
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not any(
        call["module"] in {"get_url", "rpm_key", "yum_repository", "apt_repository", "deb822_repository", "lineinfile", "pip", "command"}
        for call in calls
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    "distribution, family, manager",
    [
        ("Ubuntu", "Debian", "apt"),
        ("Linux Mint", "Debian", "apt"),
        ("Fedora", "RedHat", "dnf"),
    ],
)
def test_supported_distribution_facts_choose_the_matching_backend(workstation_run, distribution, family, manager):
    result, calls = workstation_run(
        tags="workstation_ansible",
        overrides={
            "ansible_facts": {"distribution": distribution, "os_family": family, "pkg_mgr": manager, "service_mgr": "systemd"},
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    packages = [call for call in calls if call["module"] in {"apt", "dnf"}]
    assert packages and {call["module"] for call in packages} == {manager}
    if manager == "dnf":
        assert all(call["options"]["use_backend"] == "dnf" for call in packages)


@pytest.mark.integration
@pytest.mark.parametrize("selection, accepted", [([], True), (["*"], False), ([True], False)])
def test_package_selection_cannot_become_a_distribution_upgrade(workstation_run, selection, accepted):
    result, calls = workstation_run(tags="workstation_apt", overrides={"workstation_packages": selection})
    assert (result.returncode == 0) is accepted
    assert not any(call["module"] in {"apt", "dnf"} for call in calls)


@pytest.mark.integration
@pytest.mark.parametrize(
    "fedora, tag, managed",
    [(False, "workstation", False), (True, "workstation", False), (False, "workstation_tools", True), (True, "workstation_ansible", True)],
)
def test_actual_main_bootstrap_without_netbox_or_application_inputs(workstation_run, fedora, tag, managed):
    result, calls = workstation_run(fedora=fedora, tags=tag, main=True, managed=managed)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Service host contract |" not in result.stdout
    assert "Recovery target |" not in result.stdout
    assert "Include NetBox bootstrap role" not in result.stdout
    assert "Infisical" not in result.stdout
    # Follow the real host configuration rather than pinning its checkout location.
    blacktop = load_yaml(REPO_ROOT / "ansible/host_vars/blacktop.yml")
    repository = NativeEnvironment().from_string(blacktop["workstation_repository_path"]).render(workstation_user_home="/fixture/home")
    installs = [call for call in calls if call["module"] == "pip" and "requirements" in call["options"]]
    assert len(installs) == 1
    assert installs[0]["options"]["requirements"] == f"{repository}/ansible/requirements.txt"
    for call in calls:
        argv = call["options"].get("argv", []) if call["module"] == "command" else []
        if "collection" in argv:
            assert argv[argv.index("-p") + 1] == f"{repository}/ansible/collections"
    assert all(call["user"] == "fixture" for call in installs)
    assert sum(call["module"] == "setup" for call in calls) == 1
    assert {call["module"] for call in calls if call["module"] in {"apt", "dnf"}} == {"dnf" if fedora else "apt"}
    # Blacktop does not opt into OpenTofu installation; no API or service work.
    assert not any(call["module"] == "yum_repository" and call["options"].get("name") == "opentofu" for call in calls)


@pytest.mark.integration
@pytest.mark.parametrize("tags", ["deploy", "workstation_tools,deploy"])
def test_normal_service_selection_keeps_service_host_assertions(workstation_run, tags):
    result, calls = workstation_run(tags=tags, main=True, managed=True)
    assert result.returncode != 0
    assert "Service host contract | Validate singleton inventory roles" in result.stdout
    assert bool(calls) is ("workstation_tools" in tags)


@pytest.mark.integration
@pytest.mark.parametrize("tag", sorted(TOOL_TAGS))
def test_inline_bootstrap_inventory_and_granular_tools(workstation_run, tag):
    result, calls = workstation_run(main=True, inline=True, fedora=True, tags=tag, overrides={"workstation_opentofu_enabled": True})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Service host contract |" not in result.stdout
    assert "Recovery target |" not in result.stdout
    assert "Infisical" not in result.stdout
    assert sum(call["module"] == "setup" for call in calls) == 1
    repos = [call["options"]["name"] for call in calls if call["module"] == "yum_repository"]
    assert ("opentofu" in repos) is (tag in {"workstation_tools", "workstation_opentofu"})
