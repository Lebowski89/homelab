"""Exercise Molecule's inventory handoff with the optional controller tooling."""

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "molecule/rocky_node_exporter"
pytestmark = pytest.mark.integration


@pytest.mark.parametrize("override", [False, True], ids=["empty-default", "unmarked-override"])
def test_cli_uses_the_intended_inventory_before_rejecting_guest_access(tmp_path, override):
    inventory = yaml.safe_load((SCENARIO / "inventory/hosts.yml.sample").read_text())
    targets = inventory["all"]["children"]["molecule_node_exporter"]["hosts"]
    next(iter(targets.values()))["molecule_node_exporter_disposable"] = False
    private_inventory = tmp_path / "inventory.yml"
    private_inventory.write_text(yaml.safe_dump(inventory))
    ssh_marker = tmp_path / "ssh-called"
    ssh = tmp_path / "blocked-ssh"
    ssh.write_text("#!/bin/sh\nprintf 'SSH_BLOCKED\\n' > " + shlex.quote(str(ssh_marker)) + "\nexit 96\n")
    ssh.chmod(0o700)
    env = {key: value for key, value in os.environ.items() if not key.startswith(("MOLECULE_", "HOMELAB_MOLECULE_"))}
    for key in ["SSH_AUTH_SOCK", "ANSIBLE_INVENTORY", "ANSIBLE_PRIVATE_KEY_FILE"]:
        env.pop(key, None)
    env.update(
        {
            "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"],
            "ANSIBLE_HOME": str(tmp_path / "ansible-home"),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible-local"),
            "ANSIBLE_LOG_PATH": str(tmp_path / "ansible.log"),
            "ANSIBLE_INJECT_FACT_VARS": "false",
            "ANSIBLE_SSH_EXECUTABLE": str(ssh),
            "XDG_CACHE_HOME": str(tmp_path / "cache"),
            "MOLECULE_EPHEMERAL_DIRECTORY": str(tmp_path / "state"),
        }
    )
    if override:
        env["HOMELAB_MOLECULE_INVENTORY"] = str(private_inventory)
    result = subprocess.run(
        [str(Path(sys.executable).with_name("molecule")), "check", "-s", "rocky_node_exporter"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "Unable to parse" not in output, output
    expected = "Explicitly opt one disposable SSH VM" if override else "Use an isolated inventory containing exactly one"
    assert expected in output, output
    assert not ssh_marker.exists(), "An inventory guard attempted to open SSH"
