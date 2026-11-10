"""Keep the optional VM scenario isolated before it can invoke a real role."""

import base64
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from ansible.utils.vars import merge_hash

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "molecule/rocky_node_exporter"
ANSIBLE = str(Path(sys.executable).with_name("ansible-playbook"))


def test_molecule_selects_only_node_exporter_without_provider_or_inventory_discovery():
    config = merge_hash(
        yaml.safe_load((ROOT / ".config/molecule/config.yml").read_text()),
        yaml.safe_load((SCENARIO / "molecule.yml").read_text()),
    )
    assert config["prerun"] is False
    assert config["dependency"]["enabled"] is False
    destroy = yaml.safe_load((SCENARIO / config["ansible"]["playbooks"]["destroy"]).read_text())
    assert all(play["hosts"] == "localhost" and play["gather_facts"] is False for play in destroy)
    assert all("ansible.builtin.debug" in task for play in destroy for task in play["tasks"])
    assert "--tags=node_exporter" in config["ansible"]["executor"]["args"]["ansible_playbook"]
    assert config["ansible"]["cfg"]["defaults"]["host_key_checking"] is True
    assert "auto" not in config["ansible"]["cfg"]["inventory"]["enable_plugins"].split(",")
    assert config["ansible"]["cfg"]["defaults"]["precedence"] == "all_inventory,groups_inventory"
    actions = {action for sequence in config["scenario"].values() for action in sequence}
    assert not actions & {"create", "destroy", "dependency"}
    inventory = yaml.safe_load((SCENARIO / "inventory/hosts.yml").read_text())
    assert inventory["all"]["children"]["molecule_node_exporter"]["hosts"] == {}


@pytest.fixture
def molecule_run(tmp_path):
    scenario = tmp_path / "project/molecule/rocky_node_exporter"
    shutil.copytree(SCENARIO, scenario)
    shutil.copytree(ROOT / "molecule/shared", scenario.parent / "shared")
    (tmp_path / "project/ansible").symlink_to(ROOT / "ansible", target_is_directory=True)
    operations = {"setup", "stat", "slurp", "getent", "copy", "file", "dnf", "user", "group", "systemd_service", "command", "service_facts"}

    def instrument(value):
        if isinstance(value, list):
            for child in value:
                instrument(child)
        elif isinstance(value, dict):
            for operation in operations:
                key = "ansible.builtin." + operation
                if key in value:
                    value["molecule_fixture"] = {"module": operation, "options": value.pop(key)}
            boundary = value.get("ansible.builtin.include_tasks", {})
            if isinstance(boundary, dict) and str(boundary.get("file", "")).endswith("ansible/tasks/service_catalog_dispatch.yml"):
                value.pop("ansible.builtin.include_tasks")
                value["molecule_fixture"] = {
                    "module": "remove_fixture",
                    "options": {"service": "{{ service_catalog_dispatch_entry.name }}"},
                }
            # This fixture proves the guards, never the live role. Replace the
            # downstream real playbook with a sentinel if a guard regresses.
            if str(value.get("ansible.builtin.import_playbook", "")).endswith("ansible/playbook.yml"):
                value["ansible.builtin.import_playbook"] = "blocked.yml"
            for child in value.values():
                if isinstance(child, (list, dict)):
                    instrument(child)

    for source in scenario.parent.rglob("*.yml"):
        value = yaml.safe_load(source.read_text())
        instrument(value)
        source.write_text(yaml.safe_dump(value, sort_keys=False))
    (scenario / "blocked.yml").write_text(
        yaml.safe_dump(
            [
                {
                    "name": "Downstream boundary",
                    "hosts": "molecule_node_exporter",
                    "gather_facts": False,
                    "tasks": [{"molecule_fixture": {"module": "forbidden", "options": {}}, "tags": ["always"]}],
                }
            ]
        )
    )
    (scenario / "ownership_check.yml").write_text(
        yaml.safe_dump(
            [
                {"ansible.builtin.import_playbook": "guard.yml"},
                {
                    "name": "Owned boundary",
                    "hosts": "molecule_node_exporter",
                    "gather_facts": False,
                    "tags": ["always"],
                    "tasks": [{"ansible.builtin.import_tasks": "ownership.tasks.yml"}],
                },
            ]
        )
    )
    plugins = tmp_path / "actions"
    plugins.mkdir()
    # Only read-only target inspection is simulated. Any unexpected remote setup
    # or file/service mutation fails before a connection/module can be opened.
    action = """from ansible.plugins.action import ActionBase
import base64
import json

class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        v = task_vars
        operation = self._task.args['module']
        args = self._task.args['options']
        with open(v['fixture_record'], 'a') as output:
            output.write(json.dumps({'operation': operation, 'args': args}) + '\\n')
        if operation == 'setup':
            if not v.get('fixture_inspect', False):
                return {'failed': True, 'msg': 'REMOTE_BOUNDARY_REACHED'}
            return {'changed': False, 'ansible_facts': {
                'system': 'Linux', 'distribution': 'Rocky', 'distribution_major_version': '10',
                'architecture': 'x86_64', 'pkg_mgr': 'dnf', 'service_mgr': 'systemd',
                'virtualization_role': 'guest', 'virtualization_type': 'kvm', 'selinux': {'mode': 'enforcing'}}}
        if operation == 'stat':
            path = args['path']
            if path == '/var/lib/homelab-molecule-node-exporter':
                return {'changed': False, 'stat': v.get('fixture_marker', {'exists': False})}
            with open(v['fixture_record']) as source:
                removed = any(json.loads(line)['operation'] == 'remove_fixture' for line in source)
            retired = path in ['/etc/systemd/system/node_exporter.service', '/var/lib/native_services/node_exporter.json']
            exists = path in v.get('fixture_existing', []) and not (retired and removed)
            metric = path.endswith('/molecule.prom')
            if removed and metric and v.get('fixture_damage') == 'missing':
                exists = False
            result = {'exists': exists}
            if exists:
                result['checksum'] = 'changed' if removed and metric and v.get('fixture_damage') == 'changed' else 'original'
            return {'changed': False, 'stat': result}
        if operation == 'command':
            return {'changed': False, 'rc': 0, 'stdout': 'fixture diagnostics', 'stderr': ''}
        if operation == 'copy' and 'diagnostics-' in args.get('dest', ''):
            return {'changed': False}
        if operation == 'service_facts':
            return {'changed': False, 'ansible_facts': {'services': {}}}
        if operation == 'remove_fixture':
            return {'changed': True}
        if operation == 'file' and args.get('path') == '/var/lib/homelab-molecule-node-exporter' and args.get('state') == 'absent':
            return {'changed': True}
        if operation == 'slurp':
            return {'changed': False, 'content': v['fixture_marker_content']}
        if operation == 'getent':
            return {'changed': False, 'ansible_facts': {'getent_passwd': {args['key']: v.get('fixture_account')}}}
        return {'failed': True, 'msg': 'MUTATION_BOUNDARY_REACHED'}
"""
    (plugins / "molecule_fixture.py").write_text(action)
    record = tmp_path / "operations.jsonl"
    config = tmp_path / "ansible.cfg"
    config.write_text(
        f"[defaults]\nroles_path={ROOT / 'ansible/roles'}\n"
        f"action_plugins={plugins}:{ROOT / 'ansible/action_plugins'}\n"
        f"filter_plugins={ROOT / 'ansible/filter_plugins'}\n"
        "inject_facts_as_vars=false\nprecedence=all_inventory,groups_inventory\n"
        "[inventory]\nenable_plugins=yaml,ini,host_list\n"
    )

    def run(playbook, *, target=None, extra_host=False, inspect=False, marker=None, existing=None, account=None, limit=None, empty=False):
        host = {
            "ansible_host": "192.0.2.10",
            "ansible_user": "test-user",
            "ansible_connection": "ssh",
            "molecule_node_exporter_disposable": True,
            "fixture_inspect": inspect,
            "molecule_ephemeral_directory": str(tmp_path),
            "molecule_vm_evidence_directory": str(tmp_path),
            "fixture_record": str(record),
            "fixture_marker_content": base64.b64encode(b"foreign marker\n").decode(),
            "fixture_existing": existing or [],
            "fixture_account": account,
            **(target or {}),
        }
        if marker is not None:
            host["fixture_marker"] = marker
        inventory = {
            "all": {
                "children": {
                    "molecule_node_exporter": {"hosts": {"test-vm": host}},
                    "tags_skynet": {"children": {"molecule_node_exporter": {}}},
                    "tags_node_exporter": {"children": {"molecule_node_exporter": {}}},
                },
                "hosts": {
                    "localhost": {"ansible_connection": "local"},
                    **({"unrelated": {"ansible_connection": "ssh"}} if extra_host else {}),
                },
            }
        }
        path = tmp_path / "inventory.yml"
        path.write_text(yaml.safe_dump(inventory))
        if empty:
            path = scenario / "inventory/hosts.yml"
        args = [ANSIBLE, "-i", str(path), str(scenario / playbook), "--tags", "node_exporter"]
        if limit:
            args += ["--limit", limit]
        result = subprocess.run(
            args,
            cwd=ROOT,
            env={
                **os.environ,
                "ANSIBLE_CONFIG": str(config),
                "ANSIBLE_INJECT_FACT_VARS": "false",
                "ANSIBLE_HOME": str(tmp_path / "home"),
                "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
                "ANSIBLE_LOG_PATH": str(tmp_path / "ansible.log"),
            },
            text=True,
            capture_output=True,
            timeout=60,
        )
        operations = [json.loads(line) for line in record.read_text().splitlines()] if record.exists() else []
        return result, operations

    return run


@pytest.mark.integration
@pytest.mark.parametrize(
    "target,extra_host",
    [
        ({"molecule_node_exporter_disposable": False}, False),
        ({"molecule_node_exporter_disposable": "true"}, False),
        ({"ansible_connection": "local"}, False),
        ({"ansible_host": "127.0.0.1"}, False),
        ({}, True),
    ],
)
def test_unsafe_inventory_stops_convergence_before_any_guest_operation(molecule_run, target, extra_host):
    result, operations = molecule_run("converge.yml", target=target, extra_host=extra_host)
    assert result.returncode != 0
    assert "disposable" in result.stdout, result.stdout + result.stderr
    assert operations == []


@pytest.mark.integration
def test_valid_disposable_inventory_is_accepted(molecule_run):
    result, operations = molecule_run("guard.yml", limit="localhost")
    assert result.returncode == 0, result.stdout + result.stderr
    assert operations == []


@pytest.mark.integration
def test_cleanup_leaves_an_unclaimed_installation_untouched(molecule_run):
    result, operations = molecule_run("cleanup.yml", inspect=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert {operation["operation"] for operation in operations} == {"setup", "stat"}


@pytest.mark.integration
@pytest.mark.parametrize(
    "marker",
    [
        {"exists": True, "isreg": True, "uid": 0, "mode": "0600"},
        {"exists": False, "islnk": True},
    ],
)
def test_cleanup_rejects_foreign_or_replaced_ownership_before_mutation(molecule_run, marker):
    result, operations = molecule_run("cleanup.yml", inspect=True, marker=marker)
    assert result.returncode != 0
    assert "does not own this marker" in result.stdout, result.stdout + result.stderr
    assert {operation["operation"] for operation in operations} <= {"setup", "stat", "slurp"}


@pytest.mark.integration
@pytest.mark.parametrize("existing_account", [False, True])
def test_prepare_rejects_existing_installation_before_claiming_it(molecule_run, existing_account):
    definition = yaml.safe_load((ROOT / "ansible/group_vars/all/services/node_exporter.yml").read_text())["node_exporter"]
    config = definition["native"]["config"]
    result, operations = molecule_run(
        "prepare.yml",
        inspect=True,
        account=["x", "1001", "1001", "", "/fixture", "/usr/sbin/nologin"] if existing_account else None,
        existing=[] if existing_account else [config["install_dir"] + "/node_exporter"],
    )
    assert result.returncode != 0
    assert {operation["operation"] for operation in operations} <= {"setup", "stat", "getent"}
    assert "MUTATION_BOUNDARY_REACHED" not in result.stdout
    if existing_account:
        assert any(operation["operation"] == "getent" for operation in operations)
    else:
        assert any((operation["args"] or {}).get("path") == config["install_dir"] + "/node_exporter" for operation in operations)


@pytest.mark.integration
def test_owned_marker_is_accepted_without_changing_the_guest(molecule_run):
    result, operations = molecule_run(
        "ownership_check.yml",
        inspect=True,
        marker={"exists": True, "isreg": True, "uid": 0, "mode": "0600"},
        target={"fixture_marker_content": base64.b64encode(b"homelab molecule rocky-node-exporter\n").decode()},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert {operation["operation"] for operation in operations} == {"setup", "stat", "slurp"}


@pytest.mark.integration
def test_empty_default_inventory_fails_before_any_guest_operation(molecule_run):
    result, operations = molecule_run("converge.yml", empty=True)
    assert result.returncode != 0
    assert "isolated inventory" in result.stdout, result.stdout + result.stderr
    assert operations == []


@pytest.mark.integration
@pytest.mark.parametrize("partial,damage", [(False, None), (True, None), (False, "missing"), (False, "changed")])
def test_owned_cleanup_uses_the_catalogue_and_preserves_existing_data(molecule_run, partial, damage):
    config = yaml.safe_load((ROOT / "ansible/group_vars/all/services/node_exporter.yml").read_text())["node_exporter"]["native"]["config"]
    result, operations = molecule_run(
        "cleanup.yml",
        inspect=True,
        marker={"exists": True, "isreg": True, "uid": 0, "mode": "0600"},
        target={
            "fixture_marker_content": base64.b64encode(b"homelab molecule rocky-node-exporter\n").decode(),
            "fixture_damage": damage,
        },
        existing=[]
        if partial
        else [
            config["install_dir"] + "/node_exporter",
            config["textfile_dir"],
            config["textfile_dir"] + "/molecule.prom",
            "/etc/systemd/system/node_exporter.service",
            "/var/lib/native_services/node_exporter.json",
        ],
    )
    assert (result.returncode == 0) is (damage is None), result.stdout + result.stderr
    dispatched = [operation for operation in operations if operation["operation"] == "remove_fixture"]
    assert [operation["args"]["service"] for operation in dispatched] == ["node_exporter"]
    retired_claim = [operation for operation in operations if operation["operation"] == "file"]
    assert bool(retired_claim) is (damage is None)
