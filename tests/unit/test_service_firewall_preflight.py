"""Run production dispatch/preflight with only external I/O replaced."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from ansible_task_cases import walk_tasks

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("preflight_fixture", ROOT / "tests/unit/test_service_firewall_lifecycle.py")
F = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(F)


@pytest.mark.integration
@pytest.mark.parametrize("service_name", ["qbittorrent", "qui"])
def test_real_swarm_environment_preview_uses_current_service_context(tmp_path, service_name):
    context = F.REAL.context()
    service = F.REAL.resolve(F.REAL.CATALOG.service_catalog_merge_target(F.REAL.catalog()[service_name], None), context)
    active = tmp_path / "active.env"
    active.write_text("NONPRODUCTION active configuration\n")
    for declaration in service["swarm_env_templates"]:
        declaration["dest"] = str(active)
    task = next(
        task
        for task in yaml.safe_load((ROOT / "ansible/roles/docker_services/tasks/sub_tasks/preflight.yml").read_text())
        if task["name"] == "Preflight | Validate controller environment templates"
    )
    variables = {
        "docker_services_svc": service,
        "docker_services_service_name": service_name,
        "docker_services_controller_host": "localhost",
        "docker_services_common_values": {declaration["var"]: "NONPRODUCTION_VALUE" for declaration in service["infisical"]["secrets_map"]},
        "docker_services_common_host_defaults": {},
        "docker_services_application_template_vars": {},
        "services_lan_cidr": "192.0.2.0/24",
    }
    playbook = tmp_path / "preview.yml"
    playbook.write_text(
        yaml.safe_dump(
            [{"hosts": "localhost", "connection": "local", "gather_facts": False, "become": False, "vars": variables, "tasks": [task]}]
        )
    )
    config = tmp_path / "ansible.cfg"
    config.write_text(f"[defaults]\nroles_path={ROOT / 'ansible/roles'}\nvars_plugins_enabled=\nstdout_callback=default\n")
    result = subprocess.run(
        [str(Path(sys.executable).with_name("ansible-playbook")), "-i", "localhost,", str(playbook), "--tags", "deploy"],
        cwd=ROOT,
        env={**os.environ, "ANSIBLE_CONFIG": str(config), "ANSIBLE_LOG_PATH": str(tmp_path / "ansible.log")},
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    assert active.read_text() == "NONPRODUCTION active configuration\n"
    assert "NONPRODUCTION_VALUE" not in output
    assert result.returncode == 0, output
    assert "Render declarations without changing active files" in output and "changed=0" in output


@pytest.mark.integration
@pytest.mark.parametrize(
    "failure", ["lookup", "environment", "resolution", "partial", "cleanup", "adapter-init", "check-mode", "postgres-context"]
)
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
        "deploy": {"hosts": "manager", "type": "container", "execution": {"mode": "rootless", "host_user": "podman-utility"}},
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
            "deploy": {"hosts": "manager", "execution": {"mode": "rootless", "host_user": "podman-database"}},
            "ports": {"postgres": {"exposure": "private", "callers": ["utility", "oldapp"], "published": 5432, "target": 5432}},
        },
        "oldapp": {"runtime": "podman", "deploy": {"hosts": "manager", "execution": {"mode": "rootless", "host_user": "podman-oldapp"}}},
    }
    if failure == "postgres-context":
        catalog["utility"]["postgres"] = {"enable": True, "databases": ["fixture_db"]}
        copied_common = roles / "service_common"
        shutil.copytree(ROOT / "ansible/roles/service_common", copied_common)
        prerequisites = yaml.safe_load((copied_common / "tasks/postgres_operator.yml").read_text())
        for task in walk_tasks(prerequisites):
            if "ansible.builtin.stat" in task:
                task["fixture_missing_operator"] = task.pop("ansible.builtin.stat")
        (copied_common / "tasks/postgres_operator.yml").write_text(yaml.safe_dump(prerequisites))
        (plugins / "fixture_missing_operator.py").write_text(
            "from ansible.plugins.action import ActionBase\n"
            "class ActionModule(ActionBase):\n"
            " def run(self,tmp=None,task_vars=None): return {'changed':False,'stat':{'exists':False}}\n"
        )
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
    preparation = next(
        task
        for task in walk_tasks(adapter)
        if any(
            child.get("ansible.builtin.include_role", {}).get("tasks_from") == "access_cancel"
            for child in walk_tasks(task.get("rescue", []))
        )
    )
    preparation["block"] = [
        {"ansible.builtin.assert": {"that": ["'source_addresses' in podman_services_common_context.firewall_plan"]}},
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
        "vars_plugins_enabled=\ninject_facts_as_vars=false\nstdout_callback=default\n[inventory]\nenable_plugins=host_list\n"
    )
    playbook = tmp_path / "preflight.yml"
    variables = {
        "fixture_root": str(tmp_path),
        "fixture_mode": failure,
        **({"service_common_postgres_operator_context": True} if failure == "postgres-context" else {}),
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
                    "hosts": "manager,peer" if failure == "lookup" else "manager",
                    "any_errors_fatal": True,
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
    assert "'ansible_failed_task' is undefined" not in output
    assert "INJECT_FACTS_AS_VARS" not in output
    assert (tmp_path / "writer").read_text() == "NONPRODUCTION existing healthy writer"
    assert "NONPRODUCTION_VALUE" not in output
    if failure == "check-mode":
        assert result.returncode == 0, output
        assert "not verified deployment readiness" in " ".join(output.split())
        assert not (tmp_path / "events").exists()
        return
    assert result.returncode != 0, output
    if failure == "postgres-context":
        assert "requires the existing root-owned" in output
        assert not (tmp_path / "lookup-called").exists()
        assert "utility" not in json.loads(store.path.read_text()).get("managed_services", {})
        return
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


@pytest.mark.integration
@pytest.mark.parametrize("inspection", ["owned", "absent", "malformed"])
def test_legacy_publication_inspection_handoff(tmp_path, inspection):
    """Exercise materialization, planning and registered ownership evidence."""
    actions, roles = tmp_path / "actions", tmp_path / "roles"
    actions.mkdir()
    firewall = roles / "service_firewall/tasks"
    firewall.mkdir(parents=True)
    # Installed firewall auditing already has its own production-I/O fixture.
    # Keep this fixture at the runtime ownership/publication handoff boundary.
    (firewall / "lifecycle_inspect.yml").write_text(
        yaml.safe_dump([{"ansible.builtin.set_fact": {"service_firewall_ownership_proof": {}}}])
    )
    variables = F.REAL.context()
    inventory_hosts = variables.pop("hostvars")
    variables.pop("groups")
    variables.pop("inventory_hostname")
    for host, values in inventory_hosts.items():
        values["ansible_connection"] = "local"
        values["docker_swarm_node_labels"] = yaml.safe_load((ROOT / f"ansible/host_vars/{host}.yml").read_text())[
            "docker_swarm_node_labels"
        ]
    inventory_hosts["blacktop"] = {"ansible_connection": "local"}
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(yaml.safe_dump({"all": {"hosts": inventory_hosts}}))
    variables.update(
        svcfiles=F.REAL.catalog(),
        service_catalog_action="recreate",
        service_catalog_controller_host="mgt",
        service_catalog_dispatch_entry={"name": "bazarr", "runtime": "docker", "dispatch_host": "mgt"},
    )
    # Retain coverage for supported legacy declarations after the real Arr
    # catalog moves to explicit backend authorization.
    publication = variables["svcfiles"]["bazarr"]["ports"]["web_backend"]
    publication.pop("exposure")
    publication.pop("callers")
    events, receipt = tmp_path / "inspection.json", tmp_path / "accepted"
    (actions / "service_operational_check.py").write_text(f"""
import importlib.util, json
from pathlib import Path
spec = importlib.util.spec_from_file_location('actual_inspection', {str(ROOT / "ansible/action_plugins/service_operational_check.py")!r})
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ActionModule(m.ActionModule):
    def run(self, tmp=None, task_vars=None):
        result = super().run(tmp, task_vars)
        if {inspection!r} == 'malformed':
            result.pop('managed')
        Path({str(events)!r}).write_text(json.dumps({{'metadata': self._task.args['metadata'], 'result': result}}))
        return result

    def _execute_module(self, module_name=None, module_args=None, **kwargs):
        argv = module_args['argv']
        metadata = self._task.args['metadata']
        assert module_name == 'ansible.builtin.command'
        assert argv[:5] == ['docker', '--host', 'unix:///var/run/docker.sock', 'service', 'inspect']
        assert argv[-1] == metadata['stack'] + '_' + metadata['name']
        assert self.variables['inventory_hostname'] == 'mgt'
        if {inspection!r} == 'absent':
            return {{'rc': 1, 'stderr': 'no such service: ' + argv[-1]}}
        observed = {{
            'Spec': {{'Name': argv[-1], 'Labels': {{'com.docker.stack.namespace': metadata['stack']}},
                     'TaskTemplate': {{'Placement': {{'Constraints': metadata['deploy']['constraints']}}}}}},
            'ports': [{{'PublishedPort': p['published'], 'TargetPort': p['target'],
                       'Protocol': p.get('protocol', 'tcp'), 'PublishMode': p.get('mode', 'ingress')}}
                      for p in metadata['ports'].values()]
        }}
        return {{'rc': 0, 'stdout': json.dumps(observed)}}
""")
    # Run the production dispatch through the publication guard, ending before
    # common preparation, secrets, database access or adapter lifecycle.
    dispatch = tmp_path / "service_catalog_dispatch.yml"
    dispatch.write_text((ROOT / "ansible/tasks/service_catalog_dispatch.yml").read_text())
    preflight = yaml.safe_load((ROOT / "ansible/tasks/service_catalog_common_preflight.yml").read_text())
    boundary = next(
        index
        for index, task in enumerate(preflight)
        if task.get("ansible.builtin.include_role", {}).get("tasks_from") == "operational_requirements"
    )
    (tmp_path / "service_catalog_common_preflight.yml").write_text(
        yaml.safe_dump(
            preflight[:boundary]
            + [
                {"ansible.builtin.copy": {"dest": str(receipt), "content": "accepted ownership evidence", "mode": "0600"}},
                {"ansible.builtin.meta": "end_play"},
            ]
        )
    )
    playbook = tmp_path / "play.yml"
    playbook.write_text(
        yaml.safe_dump(
            [{"hosts": "mgt", "gather_facts": False, "vars": variables, "tasks": [{"ansible.builtin.include_tasks": str(dispatch)}]}]
        )
    )
    config = tmp_path / "ansible.cfg"
    config.write_text(
        f"[defaults]\ninventory={inventory}\nroles_path={roles}:{ROOT / 'ansible/roles'}\n"
        f"action_plugins={actions}:{ROOT / 'ansible/action_plugins'}\nlibrary={ROOT / 'ansible/library'}\n"
        f"filter_plugins={ROOT / 'ansible/roles/service_common/filter_plugins'}\n"
        "vars_plugins_enabled=\ninject_facts_as_vars=false\nstdout_callback=default\n[inventory]\nenable_plugins=yaml\n"
    )
    result = subprocess.run(
        [str(Path(sys.executable).with_name("ansible-playbook")), str(playbook)],
        cwd=ROOT,
        env={**os.environ, "ANSIBLE_CONFIG": str(config), "ANSIBLE_INJECT_FACT_VARS": "false"},
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    assert events.exists(), output
    evidence = json.loads(events.read_text())
    metadata = evidence["metadata"]
    assert metadata["runtime"] == "docker" and metadata["deploy"]["hosts"] == ["unraid"]
    assert metadata["deploy"]["constraints"] == [
        "node.labels.docker_services_host == " + inventory_hosts["unraid"]["docker_swarm_node_labels"]["docker_services_host"]
    ]
    assert "environment" not in metadata and "infisical" not in metadata
    assert "INJECT_FACTS_AS_VARS" not in output
    if inspection == "owned":
        assert result.returncode == 0, output
        assert evidence["result"]["managed"] is True and receipt.exists()
    else:
        assert result.returncode != 0 and not receipt.exists(), output
        if inspection == "absent":
            assert evidence["result"]["managed"] is False
            assert "no existing owned" in output and "New publications require exposure" in output
        else:
            assert "managed" not in evidence["result"]
            assert "did not return a valid boolean managed result" in output
            assert "New publications require exposure" not in output


@pytest.mark.integration
@pytest.mark.parametrize(
    "failure", ["database", "template", "absent", "after-removal", "foreign", "foreign-secret", "invalid-publication", "templates-valid"]
)
def test_real_bazarr_recreate_preserves_writer_and_recovers_absence(tmp_path, failure):
    """Run real dispatch/adapter/preflight; replace external mutation boundaries."""
    actions, roles = tmp_path / "actions", tmp_path / "roles"
    actions.mkdir()
    for role in ["docker_services", "service_common", "service_prepare", "service_firewall"]:
        shutil.copytree(ROOT / "ansible/roles" / role, roles / role)
    # Keep config application separate from read-only preparation. The real file
    # and application task implementations have their own rendering coverage.
    for role, file in [("service_common", "files"), ("service_common", "traefik"), ("service_prepare", "configure")]:
        (roles / role / "tasks" / (file + ".yml")).write_text(yaml.safe_dump([{"fixture_apply": {"phase": file}}]))
    for file in ["prepare_callers", "lifecycle_probes", "access_probes"]:
        (roles / "service_firewall/tasks" / (file + ".yml")).write_text("[]\n")
    for file in (roles / "docker_services/tasks").rglob("*.yml"):
        file.write_text(file.read_text().replace("/opt/stacks", str(tmp_path / "stacks")))
    inspection = roles / "docker_services/tasks/sub_tasks/secrets/inspect.yml"
    secret_tasks = yaml.safe_load(inspection.read_text())
    for task in secret_tasks:
        if "ansible.builtin.command" in task:
            task["fixture_secret_inspect"] = task.pop("ansible.builtin.command")
    inspection.write_text(yaml.safe_dump(secret_tasks))
    mode, writer, events = tmp_path / "mode", tmp_path / "writer", tmp_path / "events"
    mode.write_text(failure)
    if failure != "absent":
        writer.write_text("NONPRODUCTION old writer")
    setup = f"""
import json
from pathlib import Path
from ansible.errors import AnsibleActionFail
from ansible.plugins.action import ActionBase
mode, writer, events = Path({str(mode)!r}), Path({str(writer)!r}), Path({str(events)!r})
def record(value):
    with events.open('a') as stream: stream.write(json.dumps(value) + '\\n')
"""
    (actions / "fixture_apply.py").write_text(
        setup
        + """
class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        assert not writer.exists(), 'active configuration changed before interruption'
        record({'apply': self._task.args['phase']})
        if mode.read_text() == 'after-removal':
            raise AnsibleActionFail('NONPRODUCTION interrupted configuration application')
        return {'changed': False}
"""
    )
    (actions / "fixture_secret_inspect.py").write_text(
        setup
        + """
class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        record({'secret_inspect': True})
        return {'changed': False, 'rc': 0, 'stdout': json.dumps([{'Spec': {'Labels': {}}}])}
"""
    )
    # Execute the real runtime ownership/placement contract, with Docker's
    # public projection replaced. No Docker socket or live filesystem is used.
    (actions / "service_operational_check.py").write_text(
        setup
        + f"""
import importlib.util
spec = importlib.util.spec_from_file_location('real_check', {str(ROOT / "ansible/action_plugins/service_operational_check.py")!r})
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
class ActionModule(m.ActionModule):
    def _execute_module(self, module_name=None, module_args=None, **kwargs):
        argv, metadata = module_args['argv'], self._task.args['metadata']
        assert argv[:3] == ['docker', '--host', 'unix:///var/run/docker.sock']
        name = metadata['stack'] + '_' + metadata['name']
        if 'ls' in argv:
            return {{'rc': 0, 'stdout': name if writer.exists() else ''}}
        record({{'inspect': name, 'present': writer.exists()}})
        if not writer.exists(): return {{'rc': 1, 'stderr': 'no such service: ' + name}}
        observed = {{'Spec': {{'Name': name, 'Labels': {{'com.docker.stack.namespace': 'foreign' if mode.read_text() == 'foreign' else metadata['stack']}},
                              'TaskTemplate': {{'Placement': {{'Constraints': metadata['deploy']['constraints']}}}}}},
                    'ports': [{{'PublishedPort': p['published'], 'TargetPort': p['target'], 'Protocol': p.get('protocol','tcp'),
                               'PublishMode': p.get('mode','ingress')}} for p in metadata['ports'].values()]}}
        return {{'rc': 0, 'stdout': json.dumps(observed)}}
"""
    )
    (actions / "service_firewall_lifecycle.py").write_text(
        setup
        + """
class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        if self._task.check_mode: return {'changed': False, 'skipped': True}
        phase = self._task.args['phase']
        record({'firewall': phase})
        return {'changed': False, 'addresses': ['192.0.2.10']}
"""
    )
    collection = tmp_path / "collections/ansible_collections"
    lookup = collection / "infisical/vault/plugins/lookup/read_secrets.py"
    lookup.parent.mkdir(parents=True)
    lookup.write_text(
        "from ansible.plugins.lookup import LookupBase\n"
        "class LookupModule(LookupBase):\n"
        " def run(self, terms, variables=None, **kwargs): return [{'value':'NONPRODUCTION_VALUE'}]\n"
    )
    pg = collection / "community/postgresql/plugins/modules/postgresql_db.py"
    pg.parent.mkdir(parents=True)
    pg.write_text(f"""
from ansible.module_utils.basic import AnsibleModule
from pathlib import Path
import json
m=AnsibleModule(argument_spec={{k:{{'type':'str','no_log':k=='login_password'}} for k in ['login_host','login_port','login_user','login_password','name','state']}},supports_check_mode=True)
with Path({str(events)!r}).open('a') as s: s.write(json.dumps({{'database':True,'old_writer':Path({str(writer)!r}).exists()}})+'\\n')
if Path({str(mode)!r}).read_text()=='database': m.fail_json(msg='NONPRODUCTION database preparation failure')
m.exit_json(changed=False)
""")
    stack = collection / "community/docker/plugins/modules/docker_stack.py"
    stack.parent.mkdir(parents=True)
    stack.write_text(f"""
from ansible.module_utils.basic import AnsibleModule
from pathlib import Path
import json
m=AnsibleModule(argument_spec={{'name':{{'type':'str'}},'state':{{'type':'str'}},'compose':{{'type':'list','elements':'str'}}}},supports_check_mode=True)
with Path({str(events)!r}).open('a') as s: s.write(json.dumps({{'runtime':m.params['state']}})+'\\n')
p=Path({str(writer)!r})
if m.params['state']=='absent': p.unlink(missing_ok=True)
else: p.write_text('NONPRODUCTION replacement writer')
m.exit_json(changed=True)
""")
    stack.with_name("docker_compose_v2.py").write_text(
        "from ansible.module_utils.basic import AnsibleModule\n"
        "m=AnsibleModule(argument_spec={})\n"
        "m.fail_json(msg='Standalone lifecycle must not run for this Swarm fixture')\n"
    )
    variables = F.REAL.context()
    hosts = variables.pop("hostvars")
    variables.pop("groups")
    variables.pop("inventory_hostname")
    for host, values in hosts.items():
        values.update(ansible_connection="local", ansible_python_interpreter=sys.executable)
        values["docker_swarm_node_labels"] = yaml.safe_load((ROOT / f"ansible/host_vars/{host}.yml").read_text())[
            "docker_swarm_node_labels"
        ]
    hosts["mgt"]["service_common_postgres_operator_context"] = False
    hosts["blacktop"] = {"ansible_connection": "local"}
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(yaml.safe_dump({"all": {"hosts": hosts}}))
    variables.update(
        svcfiles=F.REAL.catalog(),
        service_catalog_action="recreate",
        service_catalog_controller_host="mgt",
        service_catalog_dispatch_entry={"name": "bazarr", "runtime": "docker", "dispatch_host": "mgt"},
        docker_services_primary_manager="mgt",
        fixture_failure=failure,
    )
    if failure == "templates-valid":
        # The real no-publication Arr service also exercises all three shared
        # application templates before interruption, without artificial ports.
        variables["service_catalog_dispatch_entry"]["name"] = "recyclarr"
    if failure == "invalid-publication":
        variables["svcfiles"]["bazarr"]["ports"]["web_backend"]["callers"] = []
    if failure == "template":
        variables["svcfiles"]["bazarr"]["templates"] = [{"src": "MISSING-FIXTURE.j2", "dest": str(tmp_path / "config")}]
    if failure == "foreign-secret":
        credential = next(item for item in variables["svcfiles"]["bazarr"]["infisical"]["secrets_map"] if item["var"] == "postgres_pass")
        credential["secret"] = {"name": "NONPRODUCTION_foreign", "update_policy": "reconcile"}
    config = tmp_path / "ansible.cfg"
    config.write_text(
        f"[defaults]\ninventory={inventory}\nroles_path={roles}\naction_plugins={actions}:{ROOT / 'ansible/action_plugins'}\n"
        f"collections_path={tmp_path / 'collections'}:{ROOT / 'ansible/collections'}\nlibrary={ROOT / 'ansible/library'}\n"
        f"filter_plugins={ROOT / 'ansible/filter_plugins'}:{ROOT / 'ansible/roles/service_common/filter_plugins'}\n"
        "vars_plugins_enabled=\ninject_facts_as_vars=false\nstdout_callback=default\n[inventory]\nenable_plugins=yaml\n"
    )
    playbook = tmp_path / "play.yml"
    batch_deploy = next(
        task
        for play in yaml.safe_load((ROOT / "ansible/playbook.yml").read_text())
        for task in play.get("tasks", [])
        if task.get("ansible.builtin.include_tasks", {}).get("file", "").endswith("/deploy/all.yml")
    )
    playbook.write_text(
        yaml.safe_dump(
            [
                {
                    "hosts": "mgt,unraid,plex",
                    "gather_facts": False,
                    "vars": variables,
                    "tasks": [
                        {
                            "ansible.builtin.include_tasks": {
                                "file": str(ROOT / "ansible/tasks/service_catalog_dispatch.yml"),
                                "apply": {"tags": ["recreate"]},
                            },
                            "tags": ["recreate"],
                        },
                        {
                            "when": "fixture_failure == 'absent' and inventory_hostname == 'mgt'",
                            "tags": ["recreate"],
                            "block": [{"ansible.builtin.fail": {"msg": "NONPRODUCTION later service preparation failure"}}],
                            "rescue": [
                                {"ansible.builtin.stat": {"path": str(writer)}, "register": "fixture_ready"},
                                {"ansible.builtin.assert": {"that": "fixture_ready.stat.exists"}},
                            ],
                        },
                        batch_deploy,
                    ],
                }
            ]
        )
    )

    def execute(check=False):
        return subprocess.run(
            [str(Path(sys.executable).with_name("ansible-playbook")), str(playbook), "--tags", "recreate"] + (["--check"] if check else []),
            cwd=ROOT,
            env={**os.environ, "ANSIBLE_CONFIG": str(config), "ANSIBLE_INJECT_FACT_VARS": "false"},
            capture_output=True,
            text=True,
        )

    result = execute(check=failure == "invalid-publication")
    output = result.stdout + result.stderr
    rows = [json.loads(line) for line in events.read_text().splitlines()] if events.exists() else []
    assert "NONPRODUCTION_VALUE" not in output and "INJECT_FACTS_AS_VARS" not in output
    if failure in {"database", "template", "foreign", "foreign-secret", "invalid-publication"}:
        assert result.returncode != 0, output
        assert writer.read_text() == "NONPRODUCTION old writer"
        assert not any("runtime" in row or "apply" in row for row in rows), rows
        if failure == "database":
            assert any(row.get("database") and row["old_writer"] for row in rows), output
        if failure == "foreign":
            assert "Docker stack ownership differs" in output
        if failure == "foreign-secret":
            assert any(row.get("secret_inspect") for row in rows), output
            assert not any(row.get("database") for row in rows)
        if failure == "invalid-publication":
            assert "private publications need callers" in output
        return
    if failure == "after-removal":
        assert result.returncode != 0 and not writer.exists(), output
        assert any(row.get("runtime") == "absent" for row in rows)
        mode.write_text("success")
        result = execute()
        output = result.stdout + result.stderr
    assert result.returncode == 0 and writer.exists(), output
    assert writer.read_text() == "NONPRODUCTION replacement writer"
    rows = [json.loads(line) for line in events.read_text().splitlines()]
    assert sum(row.get("runtime") == "present" for row in rows) == 1
