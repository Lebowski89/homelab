"""Offline Skynet dispatch and NetBox configuration loading, with no SSH operations."""

from __future__ import annotations

import importlib.util
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
        "workstation_user_home": str(tmp_path / "managed-user"),
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
                    },
                    "no_log": True,
                    "diff": False,
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
    assert "DEPRECATION WARNING" not in result.stdout + result.stderr


@pytest.mark.integration
@pytest.mark.parametrize("override", [None, False, 0, 42, 1.5, "0", "", [], {}])
def test_shared_configuration_preserves_defined_falsy_host_overrides(bootstrap, override):
    directory, run = bootstrap
    path = directory / "host_vars/mgt.yml"
    settings = yaml.safe_load(path.read_text())
    settings["services_log_root"] = override
    path.write_text(yaml.safe_dump(settings))

    result, observed = run("run", "netbox", "recreate")
    assert result.returncode == 0, result.stdout + result.stderr
    assert observed["log_root"] == override
    assert type(observed["log_root"]) is type(override)
    assert "DEPRECATION WARNING" not in result.stdout + result.stderr


@pytest.mark.integration
@pytest.mark.parametrize("missing", ["inventory/netbox-bootstrap.yml", "netbox.yml", "group_vars/all/vault/netbox.yml"])
def test_missing_bootstrap_inputs_fail_before_lifecycle(bootstrap, missing):
    directory, run = bootstrap
    (directory / missing).unlink()  # Synthetic fixture files only.
    result, entered = run("run", "netbox", "deploy")
    assert result.returncode != 0, result.stdout + result.stderr
    assert entered is None


@pytest.mark.integration
@pytest.mark.parametrize("fault", [None, "policy-host", "policy-address", "observed-address", "policy-owner", "firewall"])
def test_remote_bootstrap_inspects_actual_protection_before_stops(bootstrap, tmp_path, fault):
    directory, run = bootstrap
    spec = importlib.util.spec_from_file_location("bootstrap_maintenance", ROOT / "tests/unit/test_service_operational_maintenance.py")
    maintenance = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(maintenance)
    check, fixture = maintenance.CHECK, maintenance.FIXTURE

    # Keep the real bootstrap -> NetBox -> common requirements -> action path.
    # Only the remote module boundary and the subsequent stop payload are stubbed.
    for path in (
        "roles/netbox/tasks/main.yml",
        "roles/netbox/tasks/requirements.yml",
        "roles/podman_services/tasks/validate_definitions.yml",
        "roles/podman_services/filter_plugins/podman_services.py",
        "roles/service_common/defaults/main.yml",
        "roles/service_common/filter_plugins/service_common.py",
        "roles/service_common/tasks/operational_requirements.yml",
        "roles/service_common/tasks/operational_inspection.yml",
    ):
        target = directory / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "ansible" / path, target)
    # Supply synthetic values separately, through the same explicit Vault file.
    vault = directory / "group_vars/all/vault/netbox.yml"
    vault_lib = VaultLib([("default", VaultSecret((tmp_path / "vault-password").read_bytes()))])
    inputs = yaml.safe_load(vault_lib.decrypt(vault.read_bytes()))
    inputs.update(
        {
            key: "NONPRODUCTION-fixture-input"
            for key in ("netbox_superuser_email", "netbox_superuser_password", "netbox_postgres_user", "netbox_postgres_pass")
        }
    )
    vault.write_bytes(vault_lib.encrypt(yaml.safe_dump(inputs)))
    context = {
        **yaml.safe_load((directory / "group_vars/all/services.yml").read_text()),
        **yaml.safe_load((directory / "roles/netbox/defaults/main.yml").read_text()),
        "inventory_hostname": "mgt",
        "local_ip": "192.0.2.48",
        "container_host_appdata_root": "/opt",
        "container_host_puid": "1000",
        "container_host_pgid": "1000",
        "services_internal_zone": "example.internal",
        "services_private_https_port": 9443,
    }

    def resolve(value, defaults=None):
        for _ in range(8):
            value = fixture.resolve(value, {**(defaults or {}), **context})
        return value

    records = []
    for role in ("netbox", "infisical"):
        defaults = yaml.safe_load((ROOT / f"ansible/roles/{role}/defaults/main.yml").read_text())
        records.extend(check.MGT.bootstrap_metadata(role, defaults, resolve))
    plan = check.MGT.build_plan({}, "mgt", resolve, records)
    # Only NetBox's endpoints are active; all declared bootstrap principals remain.
    endpoints = [e for e in plan["endpoints"] if e["service"].startswith("netbox")]
    callers = {name for e in endpoints for name in e["callers"]}
    policy = {
        "schema": 1,
        "backend": "nf_tables",
        "inputs_verified": True,
        "inventory_host": "other" if fault == "policy-host" else "mgt",
        "inventory_address": "192.0.2.99" if fault == "policy-address" else context["local_ip"],
        "endpoints": endpoints,
        "principals": plan["principals"],
        "callers": {
            name: [
                {"kind": "local", "phase": "podman", "account": "podman-" + name, "uid": 2019, "verified": True, "restart_verified": True}
            ]
            for name in callers
        },
    }
    files = {
        "/etc/skynet-mgt-firewall/policy.json": [1000 if fault == "policy-owner" else 0, json.dumps(policy)],
        "/etc/skynet-mgt-firewall/policy.py": [0, "# NONPRODUCTION helper fixture"],
    }
    units = []
    for raw in context["netbox_podman_services"]:
        cfg = resolve(maintenance.COMMON.service_common_requirements_metadata(raw, resolve(raw["name"])))
        unit = cfg["name"]
        units.append(unit)
        account = cfg["deploy"]["execution"]["host_user"]
        state = {
            "version": 2,
            "managed_by": "podman_services",
            "service": unit,
            "unit_name": unit + ".service",
            "mode": "rootless",
            "host_user": account,
            "uid": "2019",
            "gid": "2019",
            "home": "/var/lib/" + account,
            "quadlet_dir": "/var/lib/" + account + "/.config/containers/systemd",
        }
        marker = {key: state[key] for key in ("managed_by", "service", "host_user", "uid", "gid", "home")}
        normalized = check.PODMAN.podman_service_normalize(cfg, unit)
        files["/var/lib/podman-services/" + unit + ".yml"] = [0, yaml.safe_dump(state)]
        files["/var/lib/podman-services/accounts/" + account + ".yml"] = [0, yaml.safe_dump(marker)]
        files[state["quadlet_dir"] + "/" + unit + ".container"] = [2019, fixture.render_container(normalized)]
        for mount in normalized["container"].get("mounts", []):
            files[mount["source"]] = [2019, None]
    remote_files = tmp_path / "remote-files.json"
    remote_files.write_text(json.dumps(files))
    events = tmp_path / "remote-events.jsonl"
    observed_address = "192.0.2.99" if fault == "observed-address" else context["local_ip"]
    (directory / "action_plugins/service_operational_check.py").write_text(f"""
import base64, importlib.util, json
from pathlib import Path
spec = importlib.util.spec_from_file_location("actual_check", {str(ROOT / "ansible/action_plugins/service_operational_check.py")!r})
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
files = json.loads(Path({str(remote_files)!r}).read_text())

class ActionModule(m.ActionModule):
    def _execute_module(self, module_name=None, module_args=None, **kwargs):
        a = module_args
        with Path({str(events)!r}).open("a") as stream:
            stream.write(json.dumps([module_name, a]) + "\\n")
        if module_name == "ansible.builtin.stat":
            v = files.get(a["path"])
            return {{"stat": {{"exists": v is not None, "uid": v[0] if v else 0,
                "isreg": v is not None and v[1] is not None, "isdir": v is not None and v[1] is None,
                "islnk": False, "mode": "0644"}}}}
        if module_name == "ansible.builtin.slurp":
            return {{"content": base64.b64encode(files[a["src"]][1].encode()).decode()}}
        if module_name == "ansible.builtin.command":
            argv = a["argv"]
            if argv[0] == "getent":
                account = argv[-1]
                return {{"rc": 0, "stdout": account + ":x:2019:2019::/var/lib/" + account + ":/usr/sbin/nologin"}}
            if argv[0] == "ip":
                return {{"rc": 0, "stdout": json.dumps([{{"addr_info": [{{"local": {observed_address!r}}}]}}])}}
            if "check" in argv:
                return {{"rc": 0, "stdout": json.dumps({{"compliant": {fault != "firewall"!r}, "pending": [], "families": [4, 6]}})}}
            if argv[0] == "systemctl":
                return {{"rc": 0, "stdout": "active"}}
        raise AssertionError("Unexpected remote operation")
""")
    stopped = tmp_path / "stop-reached.json"
    (directory / "action_plugins/stop_probe.py").write_text(
        "import json\nfrom pathlib import Path\nfrom ansible.plugins.action import ActionBase\n"
        "class ActionModule(ActionBase):\n"
        "    def run(self, tmp=None, task_vars=None):\n"
        f"        Path({str(stopped)!r}).write_text(json.dumps(task_vars['netbox_podman_prerequisite_proofs']))\n"
        "        return {'changed': False}\n"
    )
    (directory / "roles/podman_services/tasks/stop_bootstrap.yml").write_text("- stop_probe: {}\n- ansible.builtin.meta: end_play\n")
    result, _ = run("run", "netbox", "recreate")
    output = result.stdout + result.stderr
    assert (result.returncode == 0) == (fault is None), output
    assert stopped.exists() == (fault is None), output
    rows = [json.loads(row) for row in events.read_text().splitlines()]
    if fault is None:
        proofs = json.loads(stopped.read_text())
        assert set(proofs) == set(units)
        assert all(proof["acl"] == ["bootstrap"] and proof["ownership_transition"] for proof in proofs.values())
        assert sum(name.endswith("command") and "check" in args["argv"] for name, args in rows) == len(units)
    else:
        expected = {
            "policy-host": "installed mgt policy inventory identity differs",
            "policy-address": "installed mgt policy inventory identity differs",
            "observed-address": "does not carry its verified inventory address",
            "policy-owner": "installed metadata ownership/mode differs",
            "firewall": "installed mgt protection or caller reconciliation is not compliant",
        }
        assert expected[fault] in output, output
