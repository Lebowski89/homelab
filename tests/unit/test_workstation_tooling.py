"""Offline workstation execution, checkout preservation and recovery boundaries."""

from __future__ import annotations

import json
import os
import pwd
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / "ansible/roles/workstation"
ANSIBLE = str(Path(sys.executable).with_name("ansible-playbook"))


def run_tasks(tmp_path, tasks, variables, *, host="localhost", connection="local"):
    """Use only a temporary static inventory/config; never load repository Vault."""
    cfg = tmp_path / "ansible.cfg"
    cfg.write_text("[defaults]\nhost_key_checking = True\n")
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(yaml.safe_dump({"all": {"hosts": {host: {"ansible_connection": connection}}}}))
    play = tmp_path / "play.yml"
    play.write_text(yaml.safe_dump([{"hosts": "all", "gather_facts": False, "vars": variables, "tasks": tasks}]))
    return subprocess.run(
        [ANSIBLE, "-i", str(inventory), str(play)],
        env={
            **os.environ,
            "ANSIBLE_CONFIG": str(cfg),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
            "ANSIBLE_REMOTE_TEMP": str(tmp_path / "remote"),
        },
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.integration
@pytest.mark.parametrize("worktree", [False, True])
@pytest.mark.parametrize("clone", [False, True])
def test_existing_dirty_checkout_is_never_updated_or_switched(tmp_path, worktree, clone):
    repo = tmp_path / "existing checkout"
    (repo / "ansible").mkdir(parents=True)
    (repo / "ansible/requirements.txt").write_text("# synthetic repository interface\n")
    # A worktree has a .git file; preservation must not depend on .git being a directory.
    if worktree:
        (repo / ".git").write_text("gitdir: /nonexistent/test-only-worktree\n")
    else:
        (repo / ".git").mkdir()
        (repo / ".git/HEAD").write_text("ref: refs/heads/operator-work\n")
    (repo / "dirty-user-file").write_text("uncommitted user work\n")
    before = {p.relative_to(repo): p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    result = run_tasks(
        tmp_path,
        [{"ansible.builtin.import_tasks": str(ROLE / "tasks/tools/repository.yml")}],
        {
            "workstation_repository_path": str(repo),
            "workstation_ansible_path": str(repo / "ansible"),
            "workstation_repository_clone": clone,
            "workstation_repository_url": "file:///nonexistent-test-repository",
            "workstation_repository_version": "main",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert before == {p.relative_to(repo): p.read_bytes() for p in repo.rglob("*") if p.is_file()}


@pytest.mark.integration
def test_missing_checkout_requires_explicit_opt_in(tmp_path):
    result = run_tasks(
        tmp_path,
        [{"ansible.builtin.import_tasks": str(ROLE / "tasks/tools/repository.yml")}],
        {"workstation_repository_path": str(tmp_path / "absent"), "workstation_repository_clone": False},
    )
    assert result.returncode != 0
    assert "explicitly enable" in result.stdout
    assert not (tmp_path / "absent").exists()


@pytest.mark.integration
@pytest.mark.parametrize(
    ("overrides", "accepted"),
    [
        ({}, True),
        ({"workstation_repository_path": "/tmp/operator checkout"}, True),
        ({"workstation_repository_path": "relative/checkout"}, False),
        ({"workstation_ansible_enabled": "false"}, False),
    ],
)
def test_real_workstation_validation_resolves_user_and_checks_portable_paths(tmp_path, overrides, accepted):
    if os.getuid() == 0:
        pytest.skip("workstation tooling intentionally requires a non-root account")
    variables = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
    variables.update(
        ansible_user=pwd.getpwuid(os.getuid()).pw_name,
        ansible_facts={"os_family": "Debian", "distribution": "Debian", "pkg_mgr": "apt", "service_mgr": "systemd"},
        **overrides,
    )
    result = run_tasks(
        tmp_path,
        [{"ansible.builtin.import_tasks": str(ROLE / "tasks/tools/validate_tools.yml")}],
        variables,
    )
    assert (result.returncode == 0) is accepted, result.stdout + result.stderr


@pytest.mark.integration
def test_rendered_wrapper_executes_locally_with_portable_paths_and_overrides(tmp_path):
    repo = tmp_path / "operator checkout"
    (repo / "ansible").mkdir(parents=True)
    variables = {
        "workstation_repository_path": str(repo),
        "workstation_ansible_venv_path": str(tmp_path / "venv"),
        "workstation_ansible_collections_path": str(tmp_path / "collections"),
        "workstation_ansible_log_path": str(tmp_path / "logs/ansible.log"),
        "workstation_become_pass_file": str(tmp_path / "absent-become"),
        "workstation_vault_pass_file": str(tmp_path / "absent-vault"),
        "workstation_skynet_doctor_ping_target": "tags_skynet",
    }
    wrapper = tmp_path / "skynet"
    wrapper.write_text(Environment(undefined=StrictUndefined).from_string((ROLE / "templates/skynet.j2").read_text()).render(**variables))
    syntax = subprocess.run(["bash", "-n", str(wrapper)], capture_output=True, text=True)
    assert syntax.returncode == 0, syntax.stderr
    executable = tmp_path / "record-playbook"
    executable.write_text(
        f"#!{sys.executable}\nimport json, os, sys\n"
        "print(json.dumps({'argv': sys.argv[1:], 'collections': os.environ['ANSIBLE_COLLECTIONS_PATH'], "
        "'config': os.environ['ANSIBLE_CONFIG'], 'log': os.environ['ANSIBLE_LOG_PATH']}))\n"
    )
    executable.chmod(0o755)
    env = {
        **{k: v for k, v in os.environ.items() if k not in {"ANSIBLE_CONFIG", "PLAYBOOK", "INVENTORY", "ANSIBLE_COLLECTIONS_PATH"}},
        "ANSIBLE_PLAYBOOK_BIN": str(executable),
        "REPO_ROOT": str(repo),
        "ANSIBLE_LOG_PATH": str(tmp_path / "test.log"),
        "BECOME_PASS_FILE": str(tmp_path / "absent-become"),
        "VAULT_PASS_FILE": str(tmp_path / "absent-vault"),
    }
    # The child is a local executable, not SSH into mgt. No live module can run.
    result = subprocess.run(["bash", str(wrapper), "install", "homepage"], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    observed = json.loads(result.stdout.splitlines()[-1])
    assert observed["argv"] == ["-i", str(repo / "ansible/netbox.yml"), str(repo / "ansible/playbook.yml"), "--tags", "deploy,homepage"]
    assert observed["collections"] == variables["workstation_ansible_collections_path"]
    assert observed["config"] == str(repo / "ansible/ansible.cfg")
    assert observed["log"] == str(tmp_path / "test.log")
    result = subprocess.run(["bash", str(wrapper), "run", "workstation", "tools"], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    observed = json.loads(result.stdout.splitlines()[-1])
    assert observed["argv"] == ["-i", str(repo / "ansible/netbox.yml"), str(repo / "ansible/playbook.yml"), "--tags", "workstation_tools"]
    for target, action in (
        ("ubuntu", "repo"),
        ("ubuntu", "venv"),
        ("ubuntu", "requirements"),
        ("ubuntu", "skynet"),
        ("opentofu", "install"),
    ):
        removed = subprocess.run(["bash", str(wrapper), "run", target, action], env=env, capture_output=True, text=True)
        assert removed.returncode != 0
        assert "Unknown role target/action" in removed.stdout + removed.stderr
    env.update(
        PLAYBOOK=str(repo / "ansible/bootstrap.yml"), INVENTORY="private-static.yml", ANSIBLE_COLLECTIONS_PATH="override-collections"
    )
    result = subprocess.run(["bash", str(wrapper), "raw", "--list-hosts"], env=env, capture_output=True, text=True)
    observed = json.loads(result.stdout.splitlines()[-1])
    assert observed["argv"] == ["-i", "private-static.yml", str(repo / "ansible/bootstrap.yml"), "--list-hosts"]
    assert observed["collections"] == "override-collections"


def test_bootstrap_entry_points_cannot_select_the_execution_machine():
    for filename in ("playbook.yml", "bootstrap.yml"):
        plays = yaml.safe_load((ROOT / "ansible" / filename).read_text())
        play = next(
            play
            for play in plays
            if any(task.get("ansible.builtin.import_tasks") == "tasks/recovery_target.yml" for task in play.get("pre_tasks", []))
        )
        assert play["hosts"] != "localhost"
        assert play.get("connection") != "local"
        assert play["gather_facts"] is False
        assert any(task.get("ansible.builtin.import_tasks") == "tasks/recovery_target.yml" for task in play["pre_tasks"])
        for task in play["tasks"]:
            tags = set(task["tags"]) - {"never"}
            assert tags <= set(task["ansible.builtin.include_role"]["apply"]["tags"])
    mgt = yaml.safe_load((ROOT / "ansible/host_vars/mgt.yml").read_text())
    assert mgt["docker_user"] == "mgt"
    assert mgt["podman_install_enable"] is True
    assert mgt["ansible_python_interpreter"] == "/opt/ansible/ansible-venv/bin/python"


def test_workstation_dynamic_includes_propagate_selection_without_unrelated_components():
    tasks = yaml.safe_load((ROLE / "tasks/tools.yml").read_text())
    selected = {}
    for task in tasks:
        include = task.get("ansible.builtin.include_tasks", task.get("ansible.builtin.include_role"))
        if include:
            assert set(include["apply"]["tags"]) == set(task["tags"])
        for tag in task.get("tags", []):
            if tag in {
                "workstation_repository",
                "workstation_ansible",
                "workstation_collections",
                "workstation_skynet",
                "workstation_opentofu",
            }:
                selected.setdefault(tag, []).append(task["name"])
    assert len(selected["workstation_ansible"]) == 2  # prerequisites and venv/dependencies
    assert len(selected["workstation_repository"]) == 2
    for component in ("collections", "skynet", "opentofu"):
        assert len(selected[f"workstation_{component}"]) == 1
    tofu = next(t for t in tasks if t.get("ansible.builtin.include_tasks", {}).get("file") == "tools/opentofu.yml")
    assert "ansible.builtin.include_role" not in tofu
    assert "opentofu_pve_user" not in str(tofu)


@pytest.mark.integration
@pytest.mark.parametrize("component", ["repository", "ansible", "collections", "skynet", "opentofu"])
def test_granular_tag_executes_validation_and_only_the_selected_tool(tmp_path, component):
    """Exercise real dynamic includes; substitute installation payloads with sentinels."""
    copied = tmp_path / "roles/workstation"
    shutil.copytree(ROLE, copied)
    # Validation here is a sentinel for tag propagation, not host provisioning.
    (copied / "tasks/tools/validate_tools.yml").write_text(
        yaml.safe_dump([{"name": "TOOL VALIDATION", "ansible.builtin.debug": {"msg": "validation selected"}}])
    )
    for tool in ("repository", "ansible", "collections", "skynet", "opentofu"):
        (copied / "tasks/tools" / ("ansible_collections.yml" if tool == "collections" else f"{tool}.yml")).write_text(
            yaml.safe_dump([{"name": f"TOOL PAYLOAD {tool}", "ansible.builtin.debug": {"msg": "synthetic payload"}}])
        )
    (copied / "tasks/packages.yml").write_text(yaml.safe_dump([{"ansible.builtin.debug": {"msg": "synthetic prerequisites"}}]))
    tasks = yaml.safe_load((copied / "tasks/tools.yml").read_text())
    for task in tasks:
        if "ansible.builtin.apt" in task:
            task.pop("ansible.builtin.apt")
            task["ansible.builtin.debug"] = {"msg": "synthetic prerequisites"}
        if "ansible.builtin.include_tasks" in task:
            task["ansible.builtin.include_tasks"]["apply"]["become"] = False
            task["ansible.builtin.include_tasks"]["apply"].pop("become_user", None)
        else:
            task["become"] = False
    (copied / "tasks/tools.yml").write_text(yaml.safe_dump(tasks))
    # Keep the existing workstation role's real entry point so both include layers execute.
    play = tmp_path / "play.yml"
    play.write_text(
        yaml.safe_dump(
            [
                {
                    "hosts": "localhost",
                    "connection": "local",
                    "gather_facts": False,
                    "vars": {"workstation_tools_enabled": True, "workstation_opentofu_enabled": True},
                    "roles": ["workstation"],
                }
            ]
        )
    )
    cfg = tmp_path / "ansible.cfg"
    cfg.write_text("[defaults]\nhost_key_checking = True\n")
    result = subprocess.run(
        [ANSIBLE, "-i", "localhost,", str(play), "--tags", f"workstation_{component}"],
        env={**os.environ, "ANSIBLE_CONFIG": str(cfg), "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "TOOL VALIDATION" in result.stdout
    for tool in ("repository", "ansible", "collections", "skynet", "opentofu"):
        assert (f"TOOL PAYLOAD {tool}" in result.stdout) is (tool == component)


@pytest.mark.integration
def test_virtualenv_library_path_uses_the_platform_python_scheme(tmp_path):
    tasks = yaml.safe_load((ROLE / "tasks/tools/ansible.yml").read_text())
    query = next(task["ansible.builtin.command"]["argv"] for task in tasks if task.get("register") == "workstation_ansible_library_path")
    venv = tmp_path / "user venv"
    argument = Environment(undefined=StrictUndefined).from_string(query[-1]).render(workstation_ansible_venv_path=str(venv))
    harness = """import sys, types
program, target = sys.argv[1:]
def library(name, scheme, vars):
    assert name == 'purelib' and scheme == 'venv'
    assert vars['base'] == vars['platbase'] == target
    return target + '/lib64/python3.14/site-packages'
sys.modules['sysconfig'] = types.SimpleNamespace(get_path=library)
sys.argv = ['python', target]
exec(program)
"""
    result = subprocess.run([sys.executable, "-c", harness, query[2], argument], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(venv / "lib64/python3.14/site-packages")


@pytest.mark.integration
@pytest.mark.parametrize("configured_venv", [True, False])
def test_service_tags_use_python3_with_or_without_a_configured_venv(tmp_path, configured_venv):
    repository = tmp_path / "checkout"
    (repository / "ansible").mkdir(parents=True)
    services = tmp_path / "services"
    services.mkdir()
    (services / "catalog.yml").write_text(
        yaml.safe_dump(
            {
                "enabled-service": {
                    "tags": ["service-a", " shared ", "shared"],
                    "targets": {
                        "active-target": {"tags": ["target-a", "shared"]},
                        "disabled-target": {"enabled": False, "tags": ["excluded-target"]},
                    },
                },
                "disabled-service": {"enabled": False, "tags": ["excluded-service"]},
            },
            sort_keys=False,
        )
    )
    tools = tmp_path / "system-bin"
    tools.mkdir()
    for tool in ("dirname", "cat", "awk", "sort", "find", "sed"):
        (tools / tool).symlink_to(shutil.which(tool))
    marker = tmp_path / "interpreter-used"
    venv = tmp_path / "configured-venv"
    for directory, identity in ((tools, "system-python3"), (venv / "bin", "venv-python3")):
        if identity == "venv-python3" and not configured_venv:
            continue
        directory.mkdir(parents=True, exist_ok=True)
        binary = directory / "python3"
        binary.write_text(
            f"#!{sys.executable}\nimport os, sys\nfrom pathlib import Path\n"
            f"Path({str(marker)!r}).write_text({identity!r})\n"
            f"os.execv({sys.executable!r}, [{sys.executable!r}, *sys.argv[1:]])\n"
        )
        binary.chmod(0o755)
    defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
    variables = {key: str(tmp_path / key) for key in defaults}
    variables.update(workstation_repository_path=str(repository), workstation_ansible_venv_path=str(venv))
    wrapper = tmp_path / "skynet"
    wrapper.write_text(Environment(undefined=StrictUndefined).from_string((ROLE / "templates/skynet.j2").read_text()).render(**variables))
    assert shutil.which("python", path=str(tools)) is None
    result = subprocess.run(
        ["/bin/bash", str(wrapper), "tags"],
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": str(tools), "SERVICES_DIR": str(services), "ANSIBLE_VENV_PATH": str(venv), "REPO_ROOT": str(repository)},
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert marker.read_text() == ("venv-python3" if configured_venv else "system-python3")
    assert result.stdout.split("# Service tags\n", 1)[1].splitlines() == ["enabled-service", "service-a", "shared", "target-a"]
    assert subprocess.run(["bash", "-n", str(wrapper)], capture_output=True).returncode == 0


@pytest.mark.integration
def test_documented_bootstrap_commands_preserve_a_checkout_path_with_spaces(tmp_path):
    checkout = tmp_path / "checkout with spaces"
    ansible_dir = checkout / "ansible"
    ansible_dir.mkdir(parents=True)
    (ansible_dir / "bootstrap.cfg").write_text("[defaults]\nhost_key_checking = True\n")
    # Both documented commands execute this controller-side assertion only.
    (ansible_dir / "playbook.yml").write_text(
        yaml.safe_dump(
            [
                {
                    "hosts": "all",
                    "gather_facts": False,
                    "tasks": [
                        {
                            "ansible.builtin.assert": {
                                "that": [
                                    "workstation_repository_path == " + repr(str(checkout)),
                                    "workstation_opentofu_enabled is sameas true",
                                ]
                            },
                            "tags": ["workstation_tools"],
                        }
                    ],
                }
            ]
        )
    )
    bootstrap = tmp_path / "bootstrap-venv"
    (bootstrap / "bin").mkdir(parents=True)
    (bootstrap / "bin/python").symlink_to(sys.executable)
    (bootstrap / "bin/ansible-playbook").symlink_to(ANSIBLE)
    text = (ROOT / "docs/cheat_sheets/workstation-setup.md").read_text()
    blocks = [textwrap.dedent(block) for block in re.findall(r"```bash\n(.*?)```", text, re.S)]
    encoding = next(block for block in blocks if "workstation_extra_vars=" in block)
    commands = [block for block in blocks if "--tags workstation_tools" in block]
    assert len(commands) == 2
    for command in commands:
        result = subprocess.run(
            ["bash"],
            input=encoding + "\n" + command.replace("--ask-become-pass", ""),
            capture_output=True,
            text=True,
            check=False,
            env={
                **os.environ,
                "checkout": str(checkout),
                "bootstrap_venv": str(bootstrap),
                "workstation_name": "blacktop",
                "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
            },
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "failed=0" in result.stdout
