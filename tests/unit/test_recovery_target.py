"""Recovery guards through real entry points, without SSH or application calls."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
ANSIBLE = str(Path(sys.executable).with_name("ansible-playbook"))


@pytest.fixture
def recover(tmp_path):
    actions = tmp_path / "action_plugins"
    actions.mkdir()
    marker = tmp_path / "role-entered"
    (actions / "recovery_probe.py").write_text(
        "from pathlib import Path\nfrom ansible.plugins.action import ActionBase\n"
        "class ActionModule(ActionBase):\n"
        "    def run(self, tmp=None, task_vars=None):\n"
        f"        Path({str(marker)!r}).write_text(self._task.args['role'])\n"
        "        return {'changed': False}\n"
    )
    # Copy only public task sources. No private inventory/Vault or real role is loaded.
    shutil.copytree(ROOT / "ansible/tasks", tmp_path / "tasks")
    for name in ("bootstrap.yml", "playbook.yml"):
        shutil.copyfile(ROOT / "ansible" / name, tmp_path / name)
    for role in ("netbox", "infisical"):
        directory = tmp_path / "roles" / role / "tasks"
        directory.mkdir(parents=True)
        (directory / "main.yml").write_text(yaml.safe_dump([{"recovery_probe": {"role": role}}]))
    config = tmp_path / "ansible.cfg"
    config.write_text(
        f"[defaults]\nhost_key_checking = True\naction_plugins = {actions}\nfilter_plugins = {ROOT / 'ansible/filter_plugins'}\n"
    )

    def run(*, entry="bootstrap.yml", address="192.0.2.10", overrides=None, connection="ssh", singleton=True, explicit=True):
        values = {
            "ansible_connection": connection,
            "recovery_application_host": "application_host",
            "local_ip": "192.0.2.10",
            "container_host_puid": "1000",
            "container_host_pgid": "1000",
            "container_host_appdata_root": "/opt",
            "services_internal_zone": "example.internal",
            "services_private_https_port": 8443,
        }
        if explicit:
            values["ansible_host"] = address
        values.update(overrides or {})
        hosts = {"application_host": values}
        if not singleton:
            hosts["another_host"] = values
        inventory = tmp_path / "inventory.yml"
        inventory.write_text(
            yaml.safe_dump({"all": {"children": {"service_recovery": {"hosts": hosts}, "tags_service_controller": {"hosts": hosts}}}})
        )
        operation = "infisical_deploy" if entry == "bootstrap.yml" else "netbox_deploy"
        result = subprocess.run(
            [ANSIBLE, "-i", str(inventory), str(tmp_path / entry), "--tags", operation],
            capture_output=True,
            text=True,
            check=False,
            env={
                **os.environ,
                "ANSIBLE_CONFIG": str(config),
                "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
                "ANSIBLE_COLLECTIONS_PATH": str(tmp_path / "empty-collections"),
                "ANSIBLE_COLLECTIONS_SCAN_SYS_PATH": "false",
            },
        )
        return result, marker.read_text() if marker.exists() else None

    return run


@pytest.mark.integration
@pytest.mark.parametrize("entry", ["bootstrap.yml", "playbook.yml"])
@pytest.mark.parametrize(
    "address, accepted",
    [
        ("192.0.2.10", True),
        ("2001:db8::10", True),
        ("::ffff:192.0.2.10", True),
        ("localhost.localdomain", False),
        ("127.1.2.3", False),
        ("::1", False),
        ("::ffff:127.0.0.1", False),
    ],
)
def test_recovery_checks_destination_before_entering_either_role(recover, entry, address, accepted):
    result, entered = recover(entry=entry, address=address)
    assert (result.returncode == 0) is accepted, result.stdout + result.stderr
    assert entered == (("infisical" if entry == "bootstrap.yml" else "netbox") if accepted else None)


@pytest.mark.integration
@pytest.mark.parametrize(
    "options",
    [
        {"connection": "local"},
        {"singleton": False},
        {"explicit": False},
    ],
)
def test_recovery_keeps_explicit_remote_singleton_boundary(recover, options):
    result, entered = recover(**options)
    assert result.returncode != 0
    assert entered is None


@pytest.mark.integration
@pytest.mark.parametrize(
    "overrides",
    [
        {"local_ip": "REPLACE_WITH_NUMERIC_PRIMARY_LAN_IP"},
        {"local_ip": "192.0.2.999"},
        {"container_host_appdata_root": "relative/path"},
        {"container_host_appdata_root": "/opt/REPLACE_WITH_ROOT"},
        {"container_host_appdata_root": "/opt\nother"},
        {"container_host_puid": True},
        {"container_host_puid": -1},
        {"container_host_pgid": "REPLACE_WITH_EXISTING_GID"},
        {"services_internal_zone": "REPLACE_WITH_INTERNAL_ZONE"},
        {"services_internal_zone": "https://example.internal"},
        {"services_private_https_port": 65536},
        {"services_private_https_port": True},
    ],
)
def test_recovery_configuration_fails_before_application_operations(recover, overrides):
    result, entered = recover(overrides=overrides)
    assert result.returncode != 0, result.stdout + result.stderr
    assert entered is None


@pytest.mark.integration
def test_recovery_preserves_existing_ownership_and_address_formats(recover):
    result, entered = recover(
        overrides={
            "local_ip": "2001:db8::11",
            "container_host_appdata_root": "/srv/application data/",
            "container_host_puid": 0,
            "container_host_pgid": " 1000 ",
            "services_internal_zone": "Example.INTERNAL.",
            "services_private_https_port": "8443",
        }
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert entered == "infisical"
