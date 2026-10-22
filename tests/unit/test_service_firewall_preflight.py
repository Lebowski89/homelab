"""Run production dispatch/preflight with only external I/O replaced."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("preflight_fixture", ROOT / "tests/unit/test_service_firewall_lifecycle.py")
F = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(F)


@pytest.mark.integration
@pytest.mark.parametrize("failure", ["lookup", "environment", "resolution", "partial", "cleanup", "adapter-init", "check-mode"])
def test_real_dispatch_cancels_preflight_and_transfers_adapter_cleanup(tmp_path, failure):
    plugins, roles = tmp_path / "actions", tmp_path / "roles"
    plugins.mkdir()
    # All firewall tasks execute unmodified, except account preparation, whose
    # OS/user-manager I/O is outside this preflight regression.
    fw = roles / "service_firewall"
    (fw / "tasks").mkdir(parents=True)
    for path in (ROOT / "ansible/roles/service_firewall/tasks").iterdir():
        if path.name != "prepare_callers.yml":
            (fw / "tasks" / path.name).symlink_to(path)
    (fw / "tasks/prepare_callers.yml").write_text("- ansible.builtin.debug:\n    msg: NONPRODUCTION account boundary\n")
    for name in ["defaults", "filter_plugins", "files", "templates"]:
        (fw / name).symlink_to(ROOT / "ansible/roles/service_firewall" / name)
    (plugins / "service_operational_check.py").write_text(
        "from ansible.plugins.action import ActionBase\n"
        "from ansible.errors import AnsibleActionFail\n"
        "class ActionModule(ActionBase):\n"
        "    def run(self, *args, **kwargs):\n"
        "        raise AnsibleActionFail('unexpected operational I/O in preflight fixture')\n"
    )
    cfg = {
        "name": "utility",
        "runtime": "podman",
        "image": "registry.invalid/nonproduction:1",
        "named_networks": {"utility": {"driver": "bridge", "external": False}},
        "deploy": {"host": "manager", "type": "container", "execution": {"mode": "rootless", "host_user": "podman-utility"}},
        "infisical": {"secrets_map": [{"var": "one", "path": "/NONPRODUCTION", "name": "ONE"}]},
        "environment": {"VALUE": {"value_from": {"infisical": "one"}}},
    }
    store = F.Store(tmp_path / "policy.json", SimpleNamespace(setattr=lambda obj, name, value: setattr(obj, name, value)))
    F.provider_request(store, "utility")
    (tmp_path / "kernel.json").write_text(json.dumps(store.kernel.state))
    (tmp_path / "writer").write_text("NONPRODUCTION existing healthy writer")
    catalog = {
        "utility": cfg,
        "database": {
            "name": "database",
            "runtime": "podman",
            "image": "registry.invalid/nonproduction:1",
            "deploy": {"host": "manager", "execution": {"mode": "rootless", "host_user": "podman-database"}},
            "ports": {"postgres": {"exposure": "private", "callers": ["utility", "oldapp"], "published": 5432, "target": 5432}},
        },
        "oldapp": {"runtime": "podman", "deploy": {"host": "manager", "execution": {"mode": "rootless", "host_user": "podman-oldapp"}}},
    }
    (tmp_path / "catalog.json").write_text(json.dumps(catalog))
    (tmp_path / "mode").write_text(failure)
    fixture_path = str(ROOT / "tests/unit/test_service_firewall_lifecycle.py")
    setup = f"""
import importlib.util, json, uuid
from pathlib import Path
from types import SimpleNamespace
spec = importlib.util.spec_from_file_location('fixture', {fixture_path!r})
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
"""
    (plugins / "service_catalog_materialize.py").write_text(
        setup
        + """
from ansible.plugins.action import ActionBase
class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        cfg = json.loads((Path(task_vars['fixture_root']) / 'catalog.json').read_text())['utility']
        if (Path(task_vars['fixture_root']) / 'mode').read_text() == 'environment':
            cfg['environment']['VALUE'] = {'value_from': {'infisical': 'undeclared'}}
        return {'changed': False, 'ansible_facts': {'service_catalog_host_materialized': [
            {'name': 'utility', 'runtime': 'podman', 'dispatch_host': 'manager', 'config': cfg}]}}
"""
    )
    (plugins / "service_firewall_plan.py").write_text(
        setup
        + """
from ansible.plugins.action import ActionBase
class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        root = Path(task_vars['fixture_root'])
        catalog = json.loads((root / 'catalog.json').read_text())
        catalog['utility'] = self._task.args['entry']['config']
        plan = f.DECL.plan('utility', catalog, 'manager', [], {'manager': {'local_ip': '192.0.2.48'}})
        plan.update(action='deploy', token=str(uuid.uuid4()), legacy_publications=False)
        plan['metadata'] = f.REAL.COMMON.service_common_requirements_metadata(catalog['utility'], 'utility')
        plan['callers']['utility'] = plan['runtime'] | {'metadata': plan['metadata']}
        if root.joinpath('mode').read_text() in {'partial', 'cleanup'}:
            plan['access_hosts'].append('peer')
            plan['inventory']['peer'] = '192.0.2.20'
            plan['profile']['peer'] = 'workers'
        return {'changed': False, 'ansible_facts': {'service_firewall_lifecycle_plan': plan}}
"""
    )
    (plugins / "service_firewall_lifecycle.py").write_text(
        setup
        + """
class ActionModule(f.ACTION.ActionModule):
    def _execute_module(self, module_name, module_args, task_vars):
        root = Path(task_vars['fixture_root'])
        data = json.loads(module_args['stdin'])
        request, phase = data['request'], data['phase']
        mode = (root / 'mode').read_text()
        with (root / 'events').open('a') as output:
            output.write(json.dumps({'phase': phase, 'host': request['host'], 'token': data['token']}) + '\\n')
        store = f.Store(root / 'policy.json', SimpleNamespace(setattr=lambda obj, name, value: setattr(obj, name, value)))
        store.current = json.loads(store.path.read_text())
        store.kernel.state = {int(k): v for k, v in json.loads((root / 'kernel.json').read_text()).items()}
        try:
            if phase == 'addresses':
                return {'rc': 0, 'stdout': json.dumps({'changed': False, 'addresses': ['192.0.2.48']})}
            if request['host'] == 'peer':
                if phase == 'access_stage':
                    other = f.provider_request(store, 'concurrent')
                    f.ENGINE.access_transact(store, other, 'access_stage', 'unrelated', lambda _: None)
                    f.ENGINE.access_transact(store, other, 'access_finish', 'unrelated', lambda _: None)
                    raise RuntimeError('NONPRODUCTION peer staging failure')
                return {'rc': 0, 'stdout': json.dumps({'changed': False, 'families': [4, 6]})}
            if phase == 'access_cancel' and mode == 'cleanup':
                raise RuntimeError('NONPRODUCTION metadata write failure')
            if phase in {'inspect', 'access_inspect'}:
                store.validate(store.current)
                store.audit(store.current)
                result = {'changed': False, 'families': [4, 6]}
            else:
                result = f.ENGINE.access_transact(store, request, phase, data['token'], lambda _: None)
            if phase == 'access_stage':
                (root / 'staged-plan.json').write_text(json.dumps(task_vars['service_firewall_access_plan']))
            return {'rc': 0, 'stdout': json.dumps(result)}
        except (RuntimeError, ValueError) as error:
            return {'rc': 1, 'stderr': str(error)}
        finally:
            (root / 'kernel.json').write_text(json.dumps(store.kernel.state))
"""
    )
    lookup = tmp_path / "collections/ansible_collections/infisical/vault/plugins/lookup/read_secrets.py"
    lookup.parent.mkdir(parents=True)
    lookup.write_text("""
from ansible.plugins.lookup import LookupBase
from ansible.errors import AnsibleError
from pathlib import Path
class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        root = Path(variables['fixture_root'])
        policy = __import__('json').loads((root / 'policy.json').read_text())
        assert policy['managed_services']['utility']['access']['pending']
        (root / 'lookup-called').write_text('NONPRODUCTION lookup after staging')
        if (root / 'mode').read_text() == 'lookup':
            raise AnsibleError('NONPRODUCTION lookup failure')
        if (root / 'mode').read_text() == 'resolution':
            return [{'value': {'NONPRODUCTION': 'not a scalar'}}]
        return [{'value': 'NONPRODUCTION_VALUE'}]
""")
    # Keep the actual adapter's ownership handoff and rescue. Replace its
    # application/runtime boundary with an inert finish or initialization error.
    adapter = yaml.safe_load((ROOT / "ansible/roles/podman_services/tasks/main.yml").read_text())
    adapter[1]["block"] = [
        {
            "name": "NONPRODUCTION adapter initialization",
            "when": "fixture_mode == 'adapter-init'",
            "ansible.builtin.fail": {"msg": "NONPRODUCTION initialization failure"},
        },
        {
            "ansible.builtin.include_role": {"name": "service_firewall", "tasks_from": "access"},
            "vars": {
                "service_firewall_access_plan": "{{ podman_services_common_context.firewall_plan }}",
                "service_firewall_access_phase": "access_finish",
            },
        },
    ]
    adapter_dir = roles / "podman_services/tasks"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "main.yml").write_text(yaml.safe_dump(adapter))
    config = tmp_path / "ansible.cfg"
    config.write_text(
        f"[defaults]\nroles_path={roles}:{ROOT / 'ansible/roles'}\naction_plugins={plugins}\n"
        f"collections_path={tmp_path / 'collections'}\nfilter_plugins={ROOT / 'ansible/roles/service_common/filter_plugins'}\n"
        "vars_plugins_enabled=\nstdout_callback=default\n[inventory]\nenable_plugins=host_list\n"
    )
    playbook = tmp_path / "preflight.yml"
    variables = {
        "fixture_root": str(tmp_path),
        "fixture_mode": failure,
        "service_catalog_controller_host": "manager",
        "services_controller_host": "manager",
        "services_storage_host": "storage",
        "service_catalog_action": "deploy",
        "service_catalog_dispatch_entry": {"name": "utility", "runtime": "podman", "dispatch_host": "manager"},
    }
    playbook.write_text(
        yaml.safe_dump(
            [
                {
                    "hosts": "manager",
                    "connection": "local",
                    "gather_facts": False,
                    "become": False,
                    "vars": variables,
                    "tasks": [
                        {
                            "ansible.builtin.include_tasks": {
                                "file": str(ROOT / "ansible/tasks/service_catalog_dispatch.yml"),
                                "apply": {"tags": ["deploy"]},
                            },
                            "tags": ["deploy"],
                        }
                    ],
                }
            ]
        )
    )
    env = {**os.environ, "ANSIBLE_CONFIG": str(config), "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local")}

    def execute(extra=()):
        result = subprocess.run(
            [str(Path(sys.executable).with_name("ansible-playbook")), "-i", "manager,peer,", str(playbook), "--tags", "deploy", *extra],
            capture_output=True,
            text=True,
            timeout=45,
            env=env,
        )
        (tmp_path / ("run-" + str(len(list(tmp_path.glob("run-*")))) + ".log")).write_text(result.stdout + result.stderr)
        return result

    result = execute(["--check"] if failure == "check-mode" else [])
    output = result.stdout + result.stderr
    assert (tmp_path / "writer").read_text() == "NONPRODUCTION existing healthy writer"
    assert "NONPRODUCTION_VALUE" not in output
    if failure == "check-mode":
        assert result.returncode == 0, output
        assert not (tmp_path / "events").exists()
        return
    assert result.returncode != 0, output
    if failure == "lookup":
        assert (tmp_path / "lookup-called").exists() and "Fetch requested values" in output
    elif failure == "environment":
        assert not (tmp_path / "lookup-called").exists() and "Validate and normalize canonical environment" in output
    elif failure == "resolution":
        assert (tmp_path / "lookup-called").exists() and "Resolve canonical environment" in output
    assert "Service operation failed at" in output, output
    policy = json.loads(store.path.read_text())
    access = policy["managed_services"]["utility"]["access"]
    assert access["pending"] is (failure == "cleanup"), output
    assert "utility" in policy["endpoints"][0]["callers"]
    events = [json.loads(line) for line in (tmp_path / "events").read_text().splitlines()]
    assert len([event for event in events if event["phase"] == "access_cancel" and event["host"] == "manager"]) == 1
    if failure in {"partial", "cleanup"}:
        assert "concurrent" in policy["endpoints"][0]["callers"]
    if failure == "cleanup":
        assert "Provider reservation cleanup failed" in output and "phase=access_cancel" in output
        assert "NONPRODUCTION peer staging failure" in output
        return
    old_token = access["token"]
    (tmp_path / "mode").write_text("success")
    variables["fixture_mode"] = "success"
    plays = yaml.safe_load(playbook.read_text())
    plays[0]["vars"] = variables
    playbook.write_text(yaml.safe_dump(plays))
    retry = execute()
    assert retry.returncode == 0, retry.stdout + retry.stderr
    latest = json.loads(store.path.read_text())["managed_services"]["utility"]["access"]
    assert latest["token"] != old_token and not latest["pending"]
    assert (tmp_path / "writer").read_text() == "NONPRODUCTION existing healthy writer"
