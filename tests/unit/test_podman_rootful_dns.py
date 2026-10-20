"""Exercise the bridge DNS prerequisite without runtimes or a live inventory."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / "ansible/roles/podman"


def run_tasks(tmp_path, port, *, check=False):
    # Execute the real tasks/modules, redirecting only their filesystem targets
    # and fixture ownership. No production inventory, callbacks, lookups or role
    # entry point is loaded; no runtime/systemd command is part of these tasks.
    tasks = yaml.safe_load((ROLE / "tasks/rootful_dns.yml").read_text())
    for task in tasks:
        for module in ("ansible.builtin.file", "ansible.builtin.template"):
            if module not in task:
                continue
            args = task[module]
            key = "path" if module.endswith(".file") else "dest"
            args[key] = str(tmp_path / "configuration") + args[key].removeprefix("/etc/containers")
            args["owner"], args["group"] = str(os.getuid()), str(os.getgid())
            if module.endswith(".template"):
                args["src"] = str(ROLE / "templates" / args["src"])
    play = [{"hosts": "localhost", "connection": "local", "gather_facts": False, "become": False, "tasks": tasks}]
    playbook = tmp_path / "play.yml"
    playbook.write_text(yaml.safe_dump(play))
    config = tmp_path / "ansible.cfg"
    config.write_text("[defaults]\ninventory = localhost,\nstdout_callback = default\nretry_files_enabled = False\n")
    env = dict(
        {key: value for key, value in os.environ.items() if not key.startswith("ANSIBLE_")},
        ANSIBLE_CONFIG=str(config),
        ANSIBLE_LOCAL_TEMP=str(tmp_path / "local"),
        ANSIBLE_REMOTE_TEMP=str(tmp_path / "remote"),
        ANSIBLE_LOG_PATH=str(tmp_path / "ansible.log"),
        ANSIBLE_INVENTORY_ENABLED="host_list",
    )
    return subprocess.run(
        [
            str(Path(sys.executable).with_name("ansible-playbook")),
            "-i",
            "localhost,",
            str(playbook),
            "-e",
            json.dumps({"podman_shared_network_dns_bind_port": port}),
            *(["--check"] if check else []),
        ],
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )


def test_dns_dropin_is_narrow_idempotent_and_check_mode_does_not_write(tmp_path):
    unrelated = tmp_path / "configuration/containers.conf.d/10-existing.conf"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text("# unrelated fixture\n[engine]\nevents_logger = 'journald'\n")
    before = unrelated.read_bytes()
    result = run_tasks(tmp_path, 5533)
    assert result.returncode == 0, result.stdout + result.stderr
    target = unrelated.with_name("50-skynet-rootful-dns.conf")
    assert tomllib.loads(target.read_text()) == {"network": {"dns_bind_port": 5533}}
    assert target.stat().st_mode & 0o777 == 0o644
    assert unrelated.read_bytes() == before
    result = run_tasks(tmp_path, 5533)
    assert result.returncode == 0 and "changed=0" in result.stdout, result.stdout + result.stderr
    saved = target.read_bytes(), target.stat().st_mtime_ns
    result = run_tasks(tmp_path, 5534, check=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (target.read_bytes(), target.stat().st_mtime_ns) == saved
    assert unrelated.read_bytes() == before


def test_fresh_check_mode_plans_without_creating_configuration(tmp_path):
    result = run_tasks(tmp_path, 5533, check=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (tmp_path / "configuration").exists()


@pytest.mark.parametrize("port", [True, False, "5533", 5533.0, 53, 65536, None])
def test_invalid_dns_ports_fail_before_filesystem_mutation(tmp_path, port):
    result = run_tasks(tmp_path, port)
    assert result.returncode != 0
    assert "Rootful bridge DNS requires an explicit integer port" in result.stdout
    assert not (tmp_path / "configuration").exists()
