"""Exercise explicit operation selection without inventory, secrets or runtimes."""

import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "tag,check",
    [
        (None, False),
        ("all", False),
        ("mgt_firewall_check", False),
        ("worker_backend_firewall_check", True),
        ("haproxy_preflight", True),
        ("prometheus_haproxy_scrape", False),
        ("loki_alertmanager_route", False),
        ("prometheus_alertmanager_routes", True),
        ("prometheus_scraparr_scrape", True),
        ("podman_pasta_signal", True),
    ],
)
def test_only_explicit_operation_runs_and_inherits_tags(tmp_path, tag, check):
    plays = yaml.safe_load((ROOT / "ansible/operations.yml").read_text())
    expected = []
    for index, play in enumerate(plays):
        play.update(hosts="localhost", connection="local", become=False)
        play.pop("vars_files")
        include = play["tasks"][0]
        if tag in include["tags"]:
            expected.append(index)
        source = ROOT / "ansible" / include["ansible.builtin.include_tasks"]["file"]
        tasks = yaml.safe_load(source.read_text())
        role = next((deepcopy(task) for task in tasks if "ansible.builtin.include_role" in task), None)
        marker = {"name": "Record selected operation", "ansible.builtin.debug": {"msg": f"SCOPED_OPERATION_{index}"}}
        if role:
            # Keep the real role-include/apply contract, but replace runtime code with a fixture role.
            role.pop("when", None)
            role.pop("vars", None)
            role["ansible.builtin.include_role"].update(name=f"fixture_{index}", tasks_from="main")
            role_dir = tmp_path / "roles" / f"fixture_{index}" / "tasks"
            role_dir.mkdir(parents=True)
            (role_dir / "main.yml").write_text(yaml.safe_dump([marker]))
            body = [role]
        else:
            body = [marker]
        task_file = tmp_path / f"operation-{index}.yml"
        task_file.write_text(yaml.safe_dump(body))
        include["ansible.builtin.include_tasks"]["file"] = str(task_file)
    playbook = tmp_path / "operations.yml"
    playbook.write_text(yaml.safe_dump(plays))
    config = tmp_path / "ansible.cfg"
    config.write_text(f"[defaults]\nroles_path={tmp_path / 'roles'}\nstdout_callback=default\nretry_files_enabled=False\n")
    command = [str(Path(sys.executable).parent / "ansible-playbook"), "-i", "localhost,", str(playbook)]
    if tag:
        command += ["--tags", tag]
    if check:
        command += ["--check"]
    result = subprocess.run(
        command,
        env={
            **os.environ,
            "ANSIBLE_CONFIG": str(config),
            "ANSIBLE_LOG_PATH": str(tmp_path / "ansible.log"),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
            "ANSIBLE_REMOTE_TEMP": str(tmp_path / "remote"),
        },
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    actual = [index for index in range(len(plays)) if f"SCOPED_OPERATION_{index}" in result.stdout]
    assert actual == expected, result.stdout
