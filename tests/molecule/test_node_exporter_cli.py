"""Exercise Molecule's inventory handoff with the optional controller tooling."""

import json
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


@pytest.mark.parametrize("scenario", ["rocky_node_exporter", "runtime_install", "application_lifecycle", "protected_network"])
@pytest.mark.parametrize("override", [False, True], ids=["empty-default", "unmarked-override"])
def test_cli_uses_the_intended_inventory_before_rejecting_guest_access(tmp_path, override, scenario):
    inventory = yaml.safe_load((SCENARIO / "inventory/hosts.yml.sample").read_text())
    targets = inventory["all"]["children"]["molecule_node_exporter"]["hosts"]
    next(iter(targets.values()))["molecule_node_exporter_disposable"] = False
    private_inventory = tmp_path / "inventory.yml"
    private_inventory.write_text(yaml.safe_dump(inventory))
    private_vars = tmp_path / "guest-vars.json"
    if scenario != "rocky_node_exporter":
        inventory = {
            "all": {
                "children": {
                    "molecule_guests": {
                        "hosts": {
                            "subject": {
                                "ansible_connection": "ssh",
                                "ansible_host": "192.0.2.10",
                                "ansible_user": "molecule",
                                "molecule_vm_disposable": False,
                            }
                        }
                    },
                    "tags_skynet": {"hosts": {"subject": {}}},
                }
            }
        }
        private_inventory.write_text(yaml.safe_dump(inventory))
        private_vars.write_text(
            json.dumps(
                {
                    "molecule_vm_run_id": "a" * 32,
                    "molecule_vm_platform": "rocky102",
                    "molecule_vm_images": json.loads((ROOT / "molecule/vm/images.json").read_text()),
                }
            )
        )
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
        if scenario != "rocky_node_exporter":
            env["HOMELAB_MOLECULE_VARS"] = str(private_vars)
    result = subprocess.run(
        [str(Path(sys.executable).with_name("molecule")), "check", "-s", scenario],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "Unable to parse" not in output, output
    # A real play recap distinguishes guard execution from a CLI/parser error.
    assert "failed=1" in output, output
    assert not ssh_marker.exists(), "An inventory guard attempted to open SSH"


def test_scenario_playbooks_and_dynamic_helpers_have_valid_ansible_structure(tmp_path):
    """Molecule syntax checks converge; compile the other entry points and helpers too."""
    playbook = tmp_path / "helpers.yml"
    imports = []
    for path in sorted((ROOT / "molecule").glob("*/*.yml")):
        data = yaml.safe_load(path.read_text())
        if (
            isinstance(data, list)
            and data
            and all(isinstance(play, dict) and ("hosts" in play or "ansible.builtin.import_playbook" in play) for play in data)
        ):
            imports.append({"ansible.builtin.import_playbook": str(path)})
    playbook.write_text(
        yaml.safe_dump(
            [
                {
                    "name": "Compile helpers without execution",
                    "hosts": "localhost",
                    "connection": "local",
                    "gather_facts": False,
                    "tasks": [{"ansible.builtin.import_tasks": str(path)} for path in sorted((ROOT / "molecule").glob("*/*.tasks.yml"))],
                }
            ]
            + imports,
            sort_keys=False,
        )
    )
    config = tmp_path / "ansible.cfg"
    config.write_text(
        f"[defaults]\nroles_path={ROOT}/ansible/roles\naction_plugins={ROOT}/ansible/action_plugins\n"
        f"filter_plugins={ROOT}/ansible/filter_plugins:{ROOT}/ansible/roles/service_common/filter_plugins\n"
        "precedence=all_inventory,groups_inventory\ninject_facts_as_vars=false\n"
        "[inventory]\nenable_plugins=yaml,ini,host_list\n"
    )
    env = {
        **os.environ,
        "ANSIBLE_CONFIG": str(config),
        "ANSIBLE_COLLECTIONS_PATH": os.environ.get(
            "ANSIBLE_COLLECTIONS_PATH",
            f"{ROOT}/ansible/collections:{Path.home()}/.local/share/homelab/collections:{Path.home()}/.ansible/collections",
        ),
        "ANSIBLE_HOME": str(tmp_path / "home"),
        "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
        "ANSIBLE_INJECT_FACT_VARS": "false",
    }
    result = subprocess.run(
        [str(Path(sys.executable).with_name("ansible-playbook")), "--inventory", "localhost,", "--syntax-check", str(playbook)],
        env=env,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
