"""Offline Skynet dispatch and NetBox configuration loading, with no SSH operations."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from ansible.parsing.vault import VaultLib, VaultSecret
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]
ANSIBLE = str(Path(sys.executable).with_name("ansible-playbook"))


@pytest.fixture
def bootstrap(tmp_path):
    repo = tmp_path / "operator checkout"
    directory = repo / "ansible"
    directory.mkdir(parents=True)
    for path in (
        "bootstrap.yml",
        "bootstrap.cfg",
        "tasks/netbox_bootstrap.yml",
        "tasks/recovery_target.yml",
        "filter_plugins/network_validation.py",
        "group_vars/all/services.yml",
        "host_vars/mgt.yml",
        "inventory/netbox-bootstrap.yml.sample",
        "roles/netbox/defaults/main.yml",
    ):
        target = directory / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "ansible" / path, target)
    inventory = directory / "inventory/netbox-bootstrap.yml"
    values = yaml.safe_load((directory / "inventory/netbox-bootstrap.yml.sample").read_text())
    # Keep the real inventory hostname and wiring, but use documentation addresses.
    values["all"]["children"]["service_recovery"]["hosts"]["mgt"].update(ansible_host="192.0.2.40", local_ip="192.0.2.48")
    inventory.write_text(yaml.safe_dump(values))
    (directory / "netbox.yml").write_text("plugin: unavailable.netbox.inventory\napi_endpoint: https://netbox.example.internal:9443\n")
    # Invalid unrelated application Vault must never be discovered or decrypted.
    vault = directory / "group_vars/all/vault"
    vault.mkdir()
    (vault / "unrelated.yml").write_text("$ANSIBLE_VAULT;1.1;AES256\nNONPRODUCTION-invalid-vault\n")
    password = tmp_path / "vault-password"
    password.write_text("NONPRODUCTION-fixture-password")
    vault_lib = VaultLib([("default", VaultSecret(password.read_bytes()))])
    (vault / "netbox.yml").write_bytes(
        vault_lib.encrypt(yaml.safe_dump({"netbox_domain": "example.test", "netbox_redis_password": "NONPRODUCTION-fixture-redis"}))
    )
    become = tmp_path / "become-password"
    become.write_text("NONPRODUCTION-unused-become-password")
    wrapper = tmp_path / "skynet"
    variables = {
        "workstation_repository_path": str(repo),
        "workstation_become_pass_file": str(become),
        "workstation_vault_pass_file": str(password),
        "workstation_skynet_doctor_ping_target": "tags_skynet",
        "workstation_ansible_venv_path": str(Path(sys.executable).parent.parent),
        "workstation_ansible_log_path": str(tmp_path / "ansible.log"),
        "workstation_ansible_collections_path": str(tmp_path / "empty-collections"),
    }
    wrapper.write_text(
        Environment(undefined=StrictUndefined)
        .from_string((ROOT / "ansible/roles/workstation/templates/skynet.j2").read_text())
        .render(**variables)
    )
    marker = tmp_path / "role-entered.json"
    plugins = directory / "action_plugins"
    plugins.mkdir()
    (plugins / "bootstrap_probe.py").write_text(
        "import json\nfrom pathlib import Path\nfrom ansible.plugins.action import ActionBase\n"
        "class ActionModule(ActionBase):\n"
        "    def run(self, tmp=None, task_vars=None):\n"
        f"        Path({str(marker)!r}).write_text(json.dumps(self._task.args))\n"
        "        return {'changed': False}\n"
    )
    # Replace only the lifecycle payload: all configuration and recovery guards run.
    tasks = directory / "roles/netbox/tasks"
    tasks.mkdir()
    (tasks / "main.yml").write_text(
        yaml.safe_dump(
            [
                {
                    "bootstrap_probe": {
                        "host": "{{ inventory_hostname }}",
                        "connection": "{{ ansible_connection }}",
                        "address": "{{ ansible_host }}",
                        "user": "{{ ansible_user }}",
                        "interpreter": "{{ ansible_python_interpreter }}",
                        "puid": "{{ netbox_puid }}",
                        "pgid": "{{ netbox_pgid }}",
                        "path": "{{ netbox_base_path }}",
                        "timezone": "{{ netbox_timezone }}",
                        "frontend": "{{ netbox_frontend_address }}",
                        "vault_loaded": "{{ netbox_redis_password == 'NONPRODUCTION-fixture-redis' }}",
                        "domain_loaded": "{{ netbox_domain == 'example.test' }}",
                        "log_root": "{{ services_log_root }}",
                    }
                }
            ]
        )
    )
    cwd = tmp_path / "blacktop"
    cwd.mkdir()

    def run(*args, record=False, env_overrides=None):
        env = {
            **{key: value for key, value in os.environ.items() if not key.startswith("ANSIBLE_")},
            "INVENTORY": str(directory / "netbox.yml"),
            "PLAYBOOK": str(directory / "playbook.yml"),
            "ANSIBLE_CONFIG": str(directory / "does-not-exist.cfg"),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
            "ANSIBLE_COLLECTIONS_SCAN_SYS_PATH": "false",
            "HOSTNAME": "blacktop",
        }
        if record:
            executable = tmp_path / "record-playbook"
            executable.write_text(
                f"#!{sys.executable}\nimport json, os, sys\n"
                "print(json.dumps({'argv': sys.argv[1:], 'config': os.environ['ANSIBLE_CONFIG'], "
                "'strict_inventory': os.environ.get('ANSIBLE_INVENTORY_UNPARSED_FAILED')}))\n"
            )
            executable.chmod(0o755)
            env["ANSIBLE_PLAYBOOK_BIN"] = str(executable)
        else:
            env["ANSIBLE_PLAYBOOK_BIN"] = ANSIBLE
        env.update(env_overrides or {})
        result = subprocess.run(["bash", str(wrapper), *args], cwd=cwd, env=env, capture_output=True, text=True, check=False)
        return result, json.loads(marker.read_text()) if marker.exists() else None

    return directory, run


@pytest.mark.integration
@pytest.mark.parametrize(
    ("command", "tag"),
    [
        (["run", "netbox", "deploy"], "netbox_deploy"),
        (["run", "netbox", "recreate"], "netbox_recreate"),
        (["deploy", "netbox"], "netbox_deploy"),
        (["recreate", "netbox"], "netbox_recreate"),
        (["bootstrap", "netbox"], "netbox_bootstrap"),
        (["check", "netbox"], "netbox_deploy"),
    ],
)
def test_netbox_dispatch_overrides_dynamic_inventory_before_ansible(bootstrap, command, tag):
    directory, run = bootstrap
    result, _ = run(*command, record=True)
    assert result.returncode == 0, result.stdout + result.stderr
    observed = json.loads(result.stdout.splitlines()[-1])
    args = observed["argv"]
    assert args[:3] == ["-i", str(directory / "inventory/netbox-bootstrap.yml"), str(directory / "bootstrap.yml")]
    assert args[args.index("--tags") + 1] == tag
    assert args[args.index("--vault-password-file") + 1].endswith("vault-password")
    assert args[args.index("--become-password-file") + 1].endswith("become-password")
    assert args[-2:] == ["-e", f"@{directory}/group_vars/all/vault/netbox.yml"]
    assert observed["config"] == str(directory / "bootstrap.cfg")
    assert observed["strict_inventory"] == "true"


@pytest.mark.integration
@pytest.mark.parametrize(("executor", "overrides"), [("mgt", False), ("blacktop", False), ("blacktop", True)])
def test_netbox_loads_shared_configuration_and_only_its_vault(bootstrap, executor, overrides):
    directory, run = bootstrap
    if overrides:
        path = directory / "host_vars/mgt.yml"
        settings = yaml.safe_load(path.read_text())
        settings.update(
            container_host_puid="1234",
            container_host_pgid="5678",
            container_host_appdata_root="/srv/application data",
            timezone="UTC",
            services_internal_zone="override.internal",
            services_private_https_port=10443,
            services_log_root="/var/log/operator-services",
        )
        path.write_text(yaml.safe_dump(settings))
    result, observed = run("run", "netbox", "recreate", env_overrides={"HOSTNAME": executor})
    assert result.returncode == 0, result.stdout + result.stderr
    assert observed == {
        "host": "mgt",
        "connection": "ssh",
        "address": "192.0.2.40",
        "user": "mgt",
        "interpreter": "/opt/ansible/ansible-venv/bin/python",
        "puid": "1234" if overrides else "1000",
        "pgid": "5678" if overrides else "1000",
        "path": "/srv/application data/netbox" if overrides else "/opt/netbox",
        "timezone": "UTC" if overrides else "Australia/Melbourne",
        "frontend": "https://netbox.override.internal:10443" if overrides else "https://netbox.example.internal:9443",
        "vault_loaded": True,
        "domain_loaded": True,
        "log_root": "/var/log/operator-services" if overrides else "/var/log/skynet",
    }
    assert "Failed to parse inventory" not in result.stderr


@pytest.mark.integration
@pytest.mark.parametrize("missing", ["inventory/netbox-bootstrap.yml", "netbox.yml", "group_vars/all/vault/netbox.yml"])
def test_missing_bootstrap_inputs_fail_before_lifecycle(bootstrap, missing):
    directory, run = bootstrap
    (directory / missing).unlink()  # Synthetic fixture files only.
    result, entered = run("run", "netbox", "deploy")
    assert result.returncode != 0, result.stdout + result.stderr
    assert entered is None
