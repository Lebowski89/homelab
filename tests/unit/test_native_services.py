"""Run native service entry points with host mutations replaced by recorded actions."""

import json
import os
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / "ansible/roles/native_services"
ANSIBLE = str(Path(sys.executable).with_name("ansible-playbook"))
ENTRIES = {"alloy": "alloy_native", "node_exporter": "node_exporter", "keepalived": "keepalived", "technitium": "technitium_native"}
pytestmark = pytest.mark.integration


@pytest.fixture
def native_run(tmp_path):
    copied = tmp_path / "roles/native_services"
    shutil.copytree(ROLE, copied)
    operations = {
        "apt",
        "pip",
        "git",
        "apt_repository",
        "dnf",
        "rpm_key",
        "yum_repository",
        "get_url",
        "group",
        "user",
        "file",
        "getent",
        "template",
        "systemd",
        "systemd_service",
        "unarchive",
        "copy",
        "command",
        "wait_for",
        "setup",
        "stat",
        "slurp",
        "service_facts",
    }

    def instrument(tasks):
        for task in tasks:
            for branch in ("block", "rescue", "always"):
                instrument(task.get(branch, []))
            if "forgejo_runner_maintenance" in task:
                task["fixture_operation"] = {"module": "forgejo_runner_maintenance", "options": task.pop("forgejo_runner_maintenance")}
            for module in operations:
                key = f"ansible.builtin.{module}"
                if key in task:
                    task["fixture_operation"] = {"module": module, "options": task.pop(key) or {}}

    for directory in ("tasks", "handlers"):
        for path in (copied / directory).rglob("*.yml"):
            tasks = yaml.safe_load(path.read_text())
            instrument(tasks)
            path.write_text(yaml.safe_dump(tasks, sort_keys=False))
    plugins = tmp_path / "action_plugins"
    plugins.mkdir()
    for name in ("service_catalog_materialize", "service_firewall_plan"):
        (plugins / (name + ".py")).symlink_to(ROOT / "ansible/action_plugins" / (name + ".py"))
    shutil.copytree(ROOT / "ansible/roles/service_common", tmp_path / "roles/service_common")
    shutil.copytree(ROOT / "ansible/group_vars/all/services", tmp_path / "group_vars/all/services")
    shutil.copytree(ROOT / "ansible/tasks", tmp_path / "tasks")
    (plugins / "fixture_operation.py").write_text("""from ansible.plugins.action import ActionBase
from ansible.playbook.handler import Handler
from ansible.template import trust_as_template
import json
import base64
import os
import stat
from pathlib import Path

class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        v = task_vars
        module, options = self._task.args['module'], self._task.args['options']
        record = {'host': v['inventory_hostname'], 'module': module, 'options': options,
                  'handler': isinstance(self._task, Handler)}
        if self._task._role:
            record['entry'] = self._task._role._from_files.get('tasks', 'main')
        sentinels = {'alloy': 'alloy_native_packages', 'node_exporter': 'node_exporter_version',
                     'keepalived': 'keepalived_config_path', 'technitium': 'technitium_native_service_name'}
        record['defaults'] = sorted(name for name, key in sentinels.items() if key in v)
        if module == 'template':
            expression = "{{ lookup('ansible.builtin.template', " + repr(options['src']) + ") }}"
            record['content'] = self._templar.template(trust_as_template(expression))
        with open(v['fixture_record'], 'a') as output:
            output.write(json.dumps(record) + '\\n')
        result = {'changed': module in ('file', 'user', 'copy', 'template', 'unarchive')
                  and not v.get('fixture_unchanged', False), 'rc': 0, 'stdout': ''}
        if module == 'stat':
            app = v['native_services_application']
            state = v.get('fixture_state', {}).get(app)
            result['stat'] = ({'exists': v.get('fixture_ostree', False)} if options['path'] == '/run/ostree-booted' else
                              {'exists': state is not None} if options['path'].endswith('.json') else
                              v.get('fixture_resolver', {'exists': True, 'islnk': True, 'lnk_source': '/run/systemd/resolve/stub-resolv.conf'}))
            if app == 'technitium' and options['path'] == v['native_services_config']['install_marker']:
                with open(v['fixture_record']) as source:
                    operations = [json.loads(line) for line in source]
                extracted = any(op['module'] == 'unarchive' and op['host'] == v['inventory_hostname'] for op in operations)
                exists = v.get('fixture_application_installed', False) or (extracted and not v.get('fixture_bad_archive', False))
                result['stat'] = {'exists': exists, 'isreg': exists}
            if options['path'] == '/run/systemd/resolve/resolv.conf':
                exists = v.get('fixture_resolved_output', True)
                result['stat'] = {'exists': exists, 'isreg': exists}
        if module == 'forgejo_runner_maintenance':
            result['token']='a'*32
            if options['state']=='present' and v.get('fixture_runner_busy'):
                result.update(failed=True,msg='fixture acceptance is active')
        if module == 'slurp':
            state = (v.get('fixture_registration', {}) if options['src'].endswith('/registration.json')
                     else v.get('fixture_state', {})[v['native_services_application']])
            result['content'] = base64.b64encode((v.get('fixture_registration_raw',json.dumps(state)) if options['src'].endswith('/registration.json') else json.dumps(state)).encode()).decode()
        if module == 'service_facts':
            unit = v.get('native_services_unit', v.get('technitium_native_service_name', 'dns')).removesuffix('.service')
            result['ansible_facts'] = {'services': v.get('fixture_services', {unit + '.service': {'state': 'running'}})}
        if module == 'systemd_service' and record['handler'] and v.get('fixture_runner_handler_failure'):
            result.update(failed=True,msg='synthetic handler failure')
        if module == 'get_url' and v.get('fixture_download_failure', False):
            result.update(failed=True, msg='fixture download failure')
        if module == 'setup':
            result['ansible_facts'] = v['fixture_facts']
        if module == 'file' and v.get('fixture_real_repository') and options.get('path','').rstrip('/')==v['native_services_config']['data_dir']:
            home=Path(v['fixture_home']);home.mkdir(exist_ok=True,mode=0o700);home.chmod(int(options['mode'],8))
        if module == 'getent':
            if options['database'] == 'passwd':
                accounts = ({v['native_services_config']['user']: (['x', '1001', '1001', '', v['native_services_config']['data_dir'], '/usr/sbin/nologin'] if v['fixture_account'] else None)}
                            if v['native_services_application']=='forgejo_runner' else
                            {v['alloy_native_user']: ['x', '1001', '1001', '', '/fixture/alloy', '/usr/sbin/nologin']})
                if v.get('fixture_real_repository') and options.get('key')==v.get('workstation_user'):
                    accounts[options['key']]=['x',str(os.getuid()),str(os.getgid()),'',v['fixture_home'],'/usr/sbin/nologin']
                result['ansible_facts'] = {'getent_passwd': accounts if v['fixture_account'] or v['native_services_application']=='forgejo_runner' else {}}
            else:
                groups = {'systemd-journal': ['x', '999', '']}
                if v['ansible_facts']['os_family'] == 'Debian':
                    groups['adm'] = ['x', '4', '']
                if v['fixture_account']:
                    groups[v['alloy_native_group']] = ['x', '1001', '']
                result['ansible_facts'] = {'getent_group': groups}
        if module == 'command' and v['native_services_application']=='forgejo_runner':
            argv = options.get('argv', [])
            if '--verify' in argv:
                result['stdout_lines']=['[GNUPG:] VALIDSIG subkey 2026-01-01 1 0 4 0 22 8 00 ' +
                     ('0'*40 if v.get('fixture_bad_signature') else 'EB114F5E6C0DC2BCDD183550A4B61A2DC5923710')]
            elif argv and argv[0]=='/usr/local/bin/forgejo-runner' and '--version' in argv:
                result['stdout']='forgejo-runner version v'+('0.0.0' if v.get('fixture_bad_version') else v['native_services_config']['version'])
            elif '--import' in argv:
                result['stdout']='[GNUPG:] IMPORT_OK 1 EB114F5E6C0DC2BCDD183550A4B61A2DC5923710'
            elif argv and argv[0]=='flock' and v.get('fixture_runner_busy'):
                result.update(failed=True,rc=1,msg='fixture controller is busy')
            elif 'sysconfig' in str(argv):
                result['stdout']=v['workstation_ansible_venv_path']+'/lib64/python3.12/site-packages'
            else:
                result['stdout']='python3.12'
        if module=='stat' and v['native_services_application']=='forgejo_runner':
            path=options['path']; home=v['native_services_config']['data_dir']
            if path=='/etc/forgejo-runner/no-legacy-registration': result['stat']={'exists':False}
            elif path==home:
                mode=format(stat.S_IMODE(Path(v['fixture_home']).stat().st_mode),'04o') if v.get('fixture_real_repository') else '0700'
                result['stat']={'exists':v['fixture_account'],'isdir':True,'islnk':False,'uid':1001,'mode':mode}
            elif path.startswith('/etc/forgejo-runner/private/') or path==home+'/.ssh/known_hosts' or path=='/etc/forgejo-runner/config.yml' or (v.get('native_services_forgejo_runner_private_source_dir') and path.startswith(v['native_services_forgejo_runner_private_source_dir']+'/')):
                result['stat']={'exists':path.rsplit('/',1)[-1] not in v.get('fixture_missing_inputs',[]),'isreg':True,'islnk':False,'mode':'0600','uid':1001}
            elif path.startswith(home+'/homelab'): result['stat']={'exists':True,'isdir':True,'islnk':False}
            elif path in ['/etc/forgejo-runner','/var/cache/forgejo-runner'] or path.startswith('/var/cache/forgejo-runner/'):
                result['stat']={'exists':True,'isdir':True,'islnk':False,'uid':0}
            elif path=='/etc/forgejo-runner/private' or path.startswith(home+'/'):
                result['stat']={'exists':v['fixture_account'],'isdir':True,'islnk':False,'uid':1001}
        return result
""")
    cfg = tmp_path / "ansible.cfg"
    cfg.write_text(
        f"[defaults]\nroles_path = {tmp_path / 'roles'}\naction_plugins = {plugins}\ninject_facts_as_vars = false\nfilter_plugins = {ROOT / 'ansible/filter_plugins'}\n"
    )
    source_play = next(play for play in yaml.safe_load((ROOT / "ansible/playbook.yml").read_text()) if play.get("hosts") == "tags_skynet")
    selected_tasks = [task for task in source_play["tasks"] if set(task.get("tags", [])) & set(ENTRIES.values())]
    record = tmp_path / "operations.jsonl"

    def run(
        entries,
        *,
        check=False,
        account=True,
        peer_address=True,
        overrides=None,
        action="deploy",
        multiple_hosts=False,
        native_hosts=None,
        enabled=None,
        limit=None,
        containers=False,
        run_all=False,
        facts=None,
        ostree=False,
        update_policy=None,
    ):
        host_facts = {
            "system": "Linux",
            "distribution": "Ubuntu",
            "distribution_version": "26.04",
            "distribution_major_version": "26",
            "os_family": "Debian",
            "pkg_mgr": "apt",
            "service_mgr": "systemd",
            "architecture": "x86_64",
            "default_ipv4": {"interface": "eth0"},
            **(facts or {}),
        }
        variables = {
            "fixture_record": str(record),
            "fixture_account": account,
            "fixture_facts": host_facts,
            "ansible_facts": host_facts,
            "fixture_ostree": ostree,
        }
        if "alloy" in entries:
            variables.update(
                services_internal_zone="private.example.test",
                services_private_https_port=9443,
                alloy_native_user="fixture-alloy",
                alloy_native_group="fixture-alloy",
                alloy_native_service_name="fixture-alloyd",
                alloy_native_config_path="/fixture/alloy/config",
                alloy_native_journal_groups=["systemd-journal", "unavailable-group"],
            )
        if "node_exporter" in entries:
            variables.update(
                node_exporter_version="9.9.9",
                node_exporter_user="fixture-node",
                node_exporter_group="fixture-node",
                node_exporter_textfile_dir="/fixture/metrics",
                node_exporter_listen_address="127.0.0.1:19100",
                node_exporter_enabled_collectors=["textfile"],
                node_exporter_disabled_collectors=["wifi"],
                node_exporter_extra_args=["--web.disable-exporter-metrics"],
            )
        if "keepalived" in entries:
            variables.update(
                local_ip="192.0.2.10",
                keepalived_host_interface="fixture0",
                keepalived_dns_group="fixture_dns_peers",
                keepalived_instances={"fixture": {"virtual_router_id": 42, "virtual_ip": "192.0.2.53", "priority_var": "fixture_priority"}},
                fixture_priority=150,
                keepalived_dns_check_query="dns.example.test",
            )
        if "technitium" in entries:
            variables.update(
                technitium_native_web_port=15380, technitium_native_dns_port=15353, technitium_native_resolved_dns_servers=["192.0.2.53"]
            )
        if "forgejo_runner" in entries:
            if not (tmp_path / "roles/workstation").exists():
                shutil.copytree(ROOT / "ansible/roles/workstation", tmp_path / "roles/workstation")
                for path in (tmp_path / "roles/workstation/tasks").rglob("*.yml"):
                    tasks = yaml.safe_load(path.read_text())
                    if not ((overrides or {}).get("fixture_real_repository") and path.name == "repository.yml"):
                        instrument(tasks)
                    path.write_text(yaml.safe_dump(tasks, sort_keys=False))
            variables.update(yaml.safe_load((ROOT / "ansible/host_vars/molecule-controller.yml").read_text()))
            variables.update(
                services_internal_zone="private.example.test",
                services_private_https_port=9443,
                fixture_services={},
                workstation_repository_clone=False,
            )
        variables.update(overrides or {})
        if enabled is not None or update_policy is not None:
            for entry in entries:
                path = tmp_path / f"group_vars/all/services/{entry}.yml"
                declaration = yaml.safe_load(path.read_text())
                if enabled is not None:
                    declaration[entry]["enabled"] = enabled
                if update_policy is not None:
                    config = declaration[entry].get("targets", {}).get("native", declaration[entry])
                    config["native"]["update_policy"] = update_policy
                path.write_text(yaml.safe_dump(declaration))
        selected_host = "molecule-controller" if "forgejo_runner" in entries else "selected"
        inventory = {
            "all": {
                "children": {
                    "tags_skynet": {
                        "hosts": {
                            selected_host: {"ansible_connection": "local", **variables},
                            "other": {
                                "ansible_connection": "local",
                                **(variables if multiple_hosts else {}),
                                **({"node_exporter_listen_address": "127.0.0.1:29100"} if multiple_hosts else {}),
                                **({"local_ip": "192.0.2.11"} if peer_address else {}),
                            },
                        }
                    },
                    "fixture_dns_peers": {"hosts": {"selected": {}, "other": {}}},
                    **{
                        ("tags_podman" if entry == "alloy" else "tags_" + ENTRIES.get(entry, entry)): {
                            "hosts": dict.fromkeys(
                                native_hosts
                                if native_hosts is not None
                                else [selected_host, "other"]
                                if multiple_hosts
                                else [selected_host],
                                {},
                            )
                        }
                        for entry in entries
                    },
                }
            }
        }
        if containers:
            # Exercise real catalogue selection, materialization and dispatch
            # for Alloy's Docker/Podman/native targets. Replace the container
            # preflight and adapters at their I/O boundary; never inspect a
            # runtime, resolve secrets, pull images or start containers.
            for path in (tmp_path / "group_vars/all/services").glob("*.yml"):
                if path.stem not in {"alloy", "node_exporter"}:
                    path.unlink()
            inventory["all"]["vars"] = {
                **variables,
                "services_controller_inventory_group": "fixture_controller",
                "services_storage_inventory_group": "fixture_storage",
                "services_plex_host": variables.get("services_plex_host", "other"),
                "services_log_root": "/fixture/logs",
                "services_public_zone": "public.example.test",
                "services_internal_zone": "private.example.test",
                "services_lan_cidr": "192.0.2.0/24",
                "services_private_https_port": 9443,
                "local_ip": "192.0.2.10",
                "container_host_puid": 1000,
                "container_host_pgid": 1000,
                "container_host_appdata_root": "/fixture/apps",
                "container_host_data_root": "/fixture/data",
                "podman_shared_network_name": "fixture-shared",
            }
            inventory["all"]["children"].update(
                {
                    "fixture_controller": {"hosts": {"selected": {}}},
                    "fixture_storage": {"hosts": {"other": {}}},
                }
            )
            (tmp_path / "tasks/service_catalog_common_preflight.yml").write_text(
                yaml.safe_dump(
                    [
                        {
                            "fixture_operation": {
                                "module": "container_preflight",
                                "options": {
                                    "name": "{{ service_catalog_materialized_service.name }}",
                                    "action": "{{ service_catalog_action }}",
                                },
                            }
                        },
                        {"ansible.builtin.set_fact": {"service_catalog_common_context": {}}},
                    ]
                )
            )
            for runtime in ("docker", "podman"):
                tasks = tmp_path / f"roles/{runtime}_services/tasks"
                tasks.mkdir(parents=True, exist_ok=True)
                (tasks / "main.yml").write_text(
                    yaml.safe_dump(
                        [
                            {
                                "fixture_operation": {
                                    "module": "container_adapter",
                                    "options": {
                                        "runtime": runtime,
                                        "action": "{{ service_catalog_action }}",
                                        "name": f"{{{{ {runtime}_services_service_cfg.name }}}}",
                                        "deploy": f"{{{{ {runtime}_services_service_cfg.deploy }}}}",
                                    },
                                },
                            }
                        ]
                    )
                )
        inv = tmp_path / "inventory.yml"
        inv.write_text(yaml.safe_dump(inventory))
        play = {**deepcopy(source_play), "tasks": deepcopy(selected_tasks)}
        # Use the real catalogue and preflight; all remote modules are replaced
        # by the recorder and there is deliberately no application controller.
        instrument(play["pre_tasks"])
        instrument(play["tasks"])
        if "forgejo_runner" in entries:
            play["tasks"] = [
                {
                    "block": play["tasks"],
                    "always": [
                        {
                            "name": "Record only transient authentication cleanup booleans",
                            "when": "fixture_record is defined",
                            "fixture_operation": {
                                "module": "cleanup_snapshot",
                                "options": {
                                    "registration_empty": "{{ native_services_runner_registration | default({}) == {} }}",
                                    "read_empty": "{{ native_services_runner_registration_read | default({}) == {} }}",
                                },
                            },
                            "tags": ["always"],
                        }
                    ],
                }
            ]
        playbook = tmp_path / "play.yml"
        playbook.write_text(yaml.safe_dump([play], sort_keys=False))
        record.unlink(missing_ok=True)
        args = [
            ANSIBLE,
            "-i",
            str(inv),
            str(playbook),
            "--tags",
            ",".join(([action] if action else []) + [ENTRIES.get(entry, entry) for entry in entries]),
        ]
        if check:
            args.append("--check")
        if limit:
            args.extend(["--limit", limit])
        if run_all:
            args.extend(["-e", "docker_services_run_all=true"])
        result = subprocess.run(
            args,
            cwd=tmp_path,
            env={
                **os.environ,
                "ANSIBLE_CONFIG": str(cfg),
                "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
                "ANSIBLE_LOG_PATH": str(tmp_path / "ansible.log"),
            },
            capture_output=True,
            text=True,
        )
        records = [json.loads(line) for line in record.read_text().splitlines()] if record.exists() else []
        return result, records

    return run


@pytest.mark.parametrize("entry", list(ENTRIES))
def test_selected_service_preserves_target_overrides_and_handler_isolation(native_run, entry):
    result, calls = native_run([entry])
    assert result.returncode == 0, result.stdout + result.stderr
    assert {call["host"] for call in calls} == {"selected"}
    # An ownership write may claim only configurations whose copy/template
    # already succeeded, including on the first installation.
    managed = set()
    for call in calls:
        destination = call["options"].get("dest", "")
        if call["module"] == "template" or destination == "/etc/systemd/resolved.conf.d/technitium.conf":
            managed.add(destination)
        if call["module"] == "copy" and destination.endswith(".json"):
            assert set(json.loads(call["options"]["content"])["files"]) <= managed
    handlers = [call["options"] for call in calls if call["handler"]]
    restarted = [options["name"] for options in handlers if options.get("state") == "restarted"]
    assert (
        restarted
        == {
            "alloy": ["fixture-alloyd"],
            "node_exporter": ["node_exporter"],
            "keepalived": ["keepalived"],
            "technitium": ["systemd-resolved"],
        }[entry]
    )
    templates = [call for call in calls if call["module"] == "template"]
    if entry == "alloy":
        assert templates[0]["options"]["dest"] == "/fixture/alloy/config"
        assert "https://loki.private.example.test:9443/loki/api/v1/push" in templates[0]["content"]
        user = next(call["options"] for call in calls if call["module"] == "user")
        assert user["name"] == "fixture-alloy" and user["append"] is True
        assert user["groups"] == ["systemd-journal"]
        assert not any(call["module"] == "group" for call in calls)
    elif entry == "node_exporter":
        download = next(call["options"] for call in calls if call["module"] == "get_url")
        assert download["checksum"].endswith("/v9.9.9/sha256sums.txt")
        assert "User=fixture-node" in templates[0]["content"]
        for setting in (
            "--collector.textfile",
            "--no-collector.wifi",
            "--collector.textfile.directory=/fixture/metrics*",
            "--web.listen-address=127.0.0.1:19100",
            "--web.disable-exporter-metrics",
        ):
            assert setting in templates[0]["content"]
    elif entry == "keepalived":
        config = next(call["content"] for call in templates if call["options"]["dest"].endswith("keepalived.conf"))
        assert "interface fixture0" in config and "priority 150" in config and "192.0.2.11" in config
        assert "dns.example.test" in templates[0]["content"]
    else:
        download = next(i for i, call in enumerate(calls) if call["module"] == "get_url")
        resolver = next(
            i
            for i, call in enumerate(calls)
            if call["module"] == "copy" and call["options"].get("dest") == "/etc/systemd/resolved.conf.d/technitium.conf"
        )
        restart = next(i for i, call in enumerate(calls) if call["handler"])
        commands = [i for i, call in enumerate(calls) if call["module"] == "command"]
        assert download < resolver < restart < commands[0] < commands[1]
        assert "DNS=192.0.2.53" in calls[resolver]["options"]["content"]
        assert [call["options"]["port"] for call in calls if call["module"] == "wait_for"] == [15380, 15353]


def test_multiple_services_keep_their_defaults_and_handlers(native_run):
    result, calls = native_run(
        list(ENTRIES),
        overrides={
            "alloy_native_loki_url": "https://logs.example.test/push",
            "services_internal_zone": "{{ unused_native_zone }}",
            "services_private_https_port": "{{ unused_native_port }}",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    restarted = [call["options"]["name"] for call in calls if call["handler"] and call["options"].get("state") == "restarted"]
    assert sorted(restarted) == ["fixture-alloyd", "keepalived", "node_exporter", "systemd-resolved"]
    alloy_config = next(
        call["content"] for call in calls if call["module"] == "template" and call["options"]["dest"] == "/fixture/alloy/config"
    )
    assert "https://logs.example.test/push" in alloy_config


def test_fresh_alloy_check_mode_defers_package_account_work(native_run):
    result, calls = native_run(["alloy"], check=True, account=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not any(call["module"] in ("apt", "apt_repository", "get_url", "user", "template", "systemd_service") for call in calls)
    assert "deferred" in result.stdout


@pytest.mark.parametrize("backend", ["apt", "dnf"])
def test_alloy_install_requires_the_package_account_before_configuration(native_run, backend):
    result, calls = native_run(["alloy"], account=False, facts={} if backend == "apt" else rpm_alloy_facts())
    assert result.returncode != 0
    assert any(call["module"] == backend for call in calls)
    assert not any(call["module"] in ("user", "template", "systemd_service") for call in calls)


def test_node_exporter_check_mode_skips_archive_and_service_lifecycle(native_run):
    result, calls = native_run(["node_exporter"], check=True, action=None)
    assert result.returncode == 0, result.stdout + result.stderr
    assert any(call["module"] == "template" for call in calls)
    assert not any(call["module"] in ("get_url", "unarchive", "copy", "systemd") for call in calls)


@pytest.mark.parametrize("rpm", [False, True])
def test_keepalived_peer_validation_runs_before_installation(native_run, rpm):
    result, calls = native_run(["keepalived"], peer_address=False, facts=rpm_alloy_facts() if rpm else None)
    assert result.returncode != 0
    assert "local_ip" in result.stdout
    assert not any(call["module"] in {"apt", "dnf", "systemd_service", "file", "copy"} for call in calls)


def test_native_collector_runs_on_multiple_hosts_without_a_controller(native_run):
    result, calls = native_run(["node_exporter"], multiple_hosts=True)
    assert result.returncode == 0, result.stdout + result.stderr
    templates = [call for call in calls if call["module"] == "template"]
    assert {call["host"] for call in templates} == {"selected", "other"}
    for call in templates:
        assert "User=fixture-node" in call["content"]
        address = "127.0.0.1:29100" if call["host"] == "other" else "127.0.0.1:19100"
        assert "--web.listen-address=" + address in call["content"]
    restarts = [call for call in calls if call["handler"] and call["options"].get("state") == "restarted"]
    assert {call["host"] for call in restarts} == {"selected", "other"}


def test_native_recreate_only_restarts_the_selected_unit(native_run):
    result, calls = native_run(["node_exporter"], action="recreate")
    assert result.returncode == 0, result.stdout + result.stderr
    changes = [call for call in calls if call["module"] not in {"stat", "setup"}]
    assert [(call["module"], call["options"]) for call in changes] == [
        ("systemd_service", {"name": "node_exporter", "state": "restarted", "enabled": True})
    ]


def test_native_remove_retires_only_its_recorded_configuration(native_run):
    record = {"identity": "node_exporter", "unit": "node_exporter", "files": ["/etc/systemd/system/node_exporter.service"]}
    result, calls = native_run(["node_exporter"], action="remove", overrides={"fixture_state": {"node_exporter": record}})
    assert result.returncode == 0, result.stdout + result.stderr
    removed = [call["options"]["path"] for call in calls if call["module"] == "file" and call["options"]["state"] == "absent"]
    assert removed == ["/etc/systemd/system/node_exporter.service", "/var/lib/native_services/node_exporter.json"]
    assert not any(call["module"] in {"apt", "user", "group", "get_url", "command"} for call in calls)
    stopped = [call["options"] for call in calls if call["module"] == "systemd_service" and call["options"].get("state")]
    assert stopped == [{"name": "node_exporter", "state": "stopped", "enabled": False}]


@pytest.mark.parametrize("rpm", [False, True])
def test_technitium_defined_false_empty_and_numeric_overrides_do_not_fall_back(native_run, rpm):
    result, calls = native_run(
        ["technitium"],
        facts=rpm_alloy_facts("Rocky", "10.2") if rpm else None,
        overrides={
            "fixture_services": {"systemd-resolved.service": {"state": "running"}},
            "technitium_native_disable_resolved_stub": False,
            "technitium_native_resolved_dns_servers": [],
            "technitium_native_web_port": 15400,
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not any(call["options"].get("dest") in {"/etc/resolv.conf", "/etc/systemd/resolved.conf.d/technitium.conf"} for call in calls)
    restarted = [call["options"]["name"] for call in calls if call["handler"]]
    assert restarted == (["dns"] if rpm else [])
    assert [call["options"]["port"] for call in calls if call["module"] == "wait_for"] == [15400, 15353]


def test_technitium_removal_restores_owned_resolver_and_retains_application_data(native_run):
    record = {
        "identity": "technitium:native",
        "unit": "dns",
        "files": ["/etc/systemd/resolved.conf.d/technitium.conf"],
        "resolver": {
            "managed": True,
            "stat": {"exists": True, "islnk": True, "lnk_source": "/run/systemd/resolve/stub-resolv.conf"},
            "content": "",
        },
    }
    result, calls = native_run(
        ["technitium"],
        action="remove",
        overrides={
            "fixture_state": {"technitium": record},
            "fixture_resolver": {"exists": True, "islnk": True, "lnk_source": "/run/systemd/resolve/resolv.conf"},
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    links = [call["options"] for call in calls if call["module"] == "file" and call["options"].get("state") == "link"]
    assert links == [{"path": "/etc/resolv.conf", "src": "/run/systemd/resolve/stub-resolv.conf", "state": "link", "force": True}]
    assert not any(call["options"].get("path", "").startswith(("/etc/dns", "/opt/technitium")) for call in calls)

    # A later resolver owner must block removal before DNS is stopped or files
    # are deleted; the original record remains available for manual recovery.
    result, calls = native_run(
        ["technitium"],
        action="remove",
        overrides={
            "fixture_state": {"technitium": record},
            "fixture_resolver": {"exists": True, "islnk": False, "checksum": "changed-by-another-owner"},
        },
    )
    assert result.returncode != 0
    assert not any(call["module"] in {"systemd_service", "file", "copy"} for call in calls)


def test_failed_download_does_not_claim_preexisting_configuration(native_run):
    result, calls = native_run(["node_exporter"], overrides={"fixture_download_failure": True})
    assert result.returncode != 0
    ownership = [
        json.loads(call["options"]["content"])
        for call in calls
        if call["module"] == "copy" and call["options"].get("dest", "").endswith(".json")
    ]
    assert len(ownership) == 1 and ownership[0]["files"] == []
    assert not any(call["module"] == "template" for call in calls)


def test_selected_native_empty_group_fails_check_before_host_work(native_run):
    result, calls = native_run(["node_exporter"], check=True, native_hosts=[])
    assert result.returncode != 0, result.stdout + result.stderr
    assert "node_exporter" in result.stdout and "tags_node_exporter" in result.stdout
    assert not calls


def test_configured_disabled_native_check_needs_no_container_inventory(native_run):
    result, calls = native_run(["node_exporter"], check=True, native_hosts=[], enabled=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not calls


@pytest.mark.parametrize("action", ["drift", "bootstrap"])
def test_broad_container_actions_do_not_dispatch_native_installations(native_run, action):
    result, calls = native_run(
        ["alloy"], action=action, containers=True, run_all=True, overrides={"alloy_native_loki_url": "{{ must_not_materialize_native }}"}
    )
    assert result.returncode == 0, result.stdout + result.stderr
    adapters = [call["options"] for call in calls if call["module"] == "container_adapter"]
    assert {call["runtime"] for call in adapters} == {"docker", "podman"}
    assert len(adapters) == 2 and all(call["action"] == action for call in adapters)
    assert {call["module"] for call in calls} == {"setup", "container_preflight", "container_adapter"}


def test_explicit_native_drift_fails_before_materialization_and_host_work(native_run):
    result, calls = native_run(["alloy"], action="drift")
    assert result.returncode != 0
    assert "alloy:native" in result.stdout and "does not support drift" in result.stdout
    assert not calls


def test_native_host_limit_keeps_declared_group_placement(native_run):
    result, calls = native_run(["node_exporter"], check=True, multiple_hosts=True, limit="selected")
    assert result.returncode == 0, result.stdout + result.stderr
    assert {call["host"] for call in calls} == {"selected"}
    assert any(call["module"] == "template" for call in calls)


def test_technitium_remove_retries_an_interrupted_regular_resolver_restore(native_run):
    import base64

    content = "nameserver 192.0.2.53\n"
    record = {
        "identity": "technitium:native",
        "unit": "dns",
        "files": ["/etc/systemd/resolved.conf.d/technitium.conf"],
        "resolver": {
            "managed": True,
            "stat": {"exists": True, "islnk": False, "uid": 0, "gid": 0, "mode": "0644"},
            "content": base64.b64encode(content.encode()).decode(),
        },
    }
    # The previous attempt removed the owned link, then failed before copying
    # the saved regular file. Its private recovery record is still present.
    result, calls = native_run(
        ["technitium"],
        action="remove",
        overrides={
            "fixture_state": {"technitium": record},
            "fixture_resolver": {"exists": False},
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    restored = [call["options"] for call in calls if call["module"] == "copy" and call["options"].get("dest") == "/etc/resolv.conf"]
    assert restored == [{"dest": "/etc/resolv.conf", "content": content, "owner": 0, "group": 0, "mode": "0644"}]


def test_swarm_dispatch_under_limit_keeps_full_placement_on_manager(native_run):
    result, calls = native_run(
        [],
        containers=True,
        run_all=True,
        action="drift",
        limit="selected",
        overrides={"services_plex_host": "selected"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    adapters = [call for call in calls if call["module"] == "container_adapter"]
    docker = next(call for call in adapters if call["options"]["runtime"] == "docker")
    assert docker["host"] == "selected"  # Manager executes; workers do not.
    assert docker["options"]["deploy"]["hosts"] == ["other", "selected"]
    assert docker["options"]["deploy"]["constraints"] == [
        "node.platform.os == linux",
        "node.labels.ansible_host != selected",
    ]
    assert {call["host"] for call in adapters} == {"selected"}


def rpm_alloy_facts(distro="Rocky", version="10", backend="dnf"):
    return {
        "distribution": distro,
        "distribution_version": version,
        "distribution_major_version": version.split(".")[0],
        "os_family": "RedHat",
        "pkg_mgr": backend,
    }


@pytest.mark.parametrize(
    "facts,action,policy,expected_state",
    [
        ({}, "deploy", "present", "present"),
        ({**rpm_alloy_facts("Fedora", "43", "dnf5"), "architecture": "aarch64"}, "update", "latest", "latest"),
        (rpm_alloy_facts(), "deploy", "latest", "present"),
        (rpm_alloy_facts("Rocky", "9"), "update", "present", "present"),
    ],
    ids=["apt", "fedora-dnf5-update", "rocky10-deploy", "rocky9-update-present"],
)
def test_alloy_selects_signed_platform_repository_and_preserves_update_policy(native_run, facts, action, policy, expected_state):
    result, calls = native_run(["alloy"], facts=facts, action=action, update_policy=policy)
    assert result.returncode == 0, result.stdout + result.stderr
    rpm = facts.get("pkg_mgr") in {"dnf", "dnf5"}
    installs = [call["options"] for call in calls if call["module"] == ("dnf" if rpm else "apt")]
    assert installs[-1]["name"] == ["alloy"] and installs[-1]["state"] == expected_state
    assert not any(call["module"] == ("apt" if rpm else "dnf") for call in calls)
    if rpm:
        assert not any(call["module"] in {"apt_repository", "get_url"} for call in calls)
        repo = next(call["options"] for call in calls if call["module"] == "yum_repository")
        assert repo["baseurl"] == "https://rpm.grafana.com"
        assert repo["gpgcheck"] and repo["repo_gpgcheck"] and repo["sslverify"]
        assert any(call["module"] == "rpm_key" and call["options"].get("fingerprint") for call in calls)
        assert all(install["disable_gpg_check"] is False and install["allowerasing"] is False for install in installs)
        assert all(install["use_backend"] == ("dnf5" if facts["pkg_mgr"] == "dnf5" else "dnf4") for install in installs)
    else:
        repo = next(call["options"] for call in calls if call["module"] == "apt_repository")
        assert "https://apt.grafana.com stable main" in repo["repo"]
        assert "signed-by=/etc/apt/keyrings/grafana.asc" in repo["repo"]
        assert repo["update_cache"] is True
    user = next(call["options"] for call in calls if call["module"] == "user")
    assert user["groups"] == ["systemd-journal"] and user["append"] is True
    assert not any(call["module"] == "group" for call in calls)
    services = [call["options"] for call in calls if call["module"] == "systemd_service" and not call["handler"]]
    assert services == [{"name": "fixture-alloyd", "enabled": True, "state": "started"}]


def test_alloy_preserves_rpm_repository_and_package_overrides(native_run):
    result, calls = native_run(
        ["alloy"],
        facts=rpm_alloy_facts(),
        overrides={
            "alloy_native_rpm_baseurl": "https://packages.example.test/alloy",
            "alloy_native_rpm_key_url": "https://packages.example.test/signing.key",
            "alloy_native_repo_filename": "operator-grafana",
            "alloy_native_packages": ["alloy", "operator-package"],
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    repo = next(call["options"] for call in calls if call["module"] == "yum_repository")
    assert repo["baseurl"] == "https://packages.example.test/alloy"
    assert repo["gpgkey"] == "https://packages.example.test/signing.key"
    assert repo["file"] == "operator-grafana"
    installs = [call["options"]["name"] for call in calls if call["module"] == "dnf"]
    assert installs[-1] == ["alloy", "operator-package"]
    assert not any("/etc/apt" in str(call["options"]) for call in calls)


@pytest.mark.parametrize("facts", [rpm_alloy_facts(), rpm_alloy_facts("Fedora", "43", "dnf5")], ids=["rocky", "fedora"])
def test_fresh_rpm_alloy_check_mode_defers_installation_accounts_and_services(native_run, facts):
    result, calls = native_run(["alloy"], facts=facts, check=True, account=False, action=None)
    assert result.returncode == 0, result.stdout + result.stderr
    assert {call["module"] for call in calls} <= {"setup", "stat", "getent"}
    assert "deferred" in result.stdout


@pytest.mark.parametrize(
    "facts,ostree",
    [
        (rpm_alloy_facts(), True),
        (rpm_alloy_facts("AlmaLinux"), False),
        (rpm_alloy_facts("Rocky", "8"), False),
        (rpm_alloy_facts("Fedora", "40"), False),
        (rpm_alloy_facts(backend="apt"), False),
        ({**rpm_alloy_facts(), "service_mgr": "openrc"}, False),
        ({**rpm_alloy_facts(), "architecture": "s390x"}, False),
    ],
    ids=["ostree", "derivative", "old-rocky", "old-fedora", "wrong-manager", "no-systemd", "unsupported-architecture"],
)
def test_alloy_rejects_unsupported_platform_before_ownership_or_installation(native_run, facts, ostree):
    result, calls = native_run(["alloy"], facts=facts, ostree=ostree)
    assert result.returncode != 0
    assert {call["module"] for call in calls} <= {"setup", "stat"}
    assert "Native Alloy requires" in result.stdout


@pytest.mark.parametrize(
    "overrides", [{"alloy_native_rpm_baseurl": "http://packages.example.test"}, {"alloy_native_rpm_key_fingerprint": "incomplete"}]
)
def test_alloy_invalid_rpm_repository_inputs_fail_before_ownership(native_run, overrides):
    result, calls = native_run(["alloy"], facts=rpm_alloy_facts(), overrides=overrides)
    assert result.returncode != 0
    assert {call["module"] for call in calls} <= {"setup", "stat"}
    assert "HTTPS repository/key URLs" in result.stdout


@pytest.mark.parametrize("action", ["recreate", "remove"])
def test_alloy_rpm_lifecycle_needs_no_repository_or_package_changes(native_run, action):
    result, calls = native_run(["alloy"], facts=rpm_alloy_facts(), action=action, overrides={"alloy_native_rpm_baseurl": ""})
    assert result.returncode == 0, result.stdout + result.stderr
    assert not any(call["module"] in {"dnf", "apt", "yum_repository", "rpm_key", "get_url"} for call in calls)
    services = [call["options"] for call in calls if call["module"] == "systemd_service"]
    assert len(services) == 1 and services[0]["name"] == "fixture-alloyd"
    assert services[0]["state"] == ("restarted" if action == "recreate" else "stopped")


@pytest.mark.parametrize(
    "facts,action,policy,state",
    [
        (rpm_alloy_facts(), "deploy", "latest", "present"),
        (rpm_alloy_facts("Fedora", "45", "dnf5"), "update", "latest", "latest"),
        (rpm_alloy_facts("Rocky", "9"), "update", "present", "present"),
    ],
)
def test_keepalived_rpm_packages_update_scope_and_inventory_rendering(native_run, facts, action, policy, state):
    result, calls = native_run(["keepalived"], facts=facts, action=action, update_policy=policy)
    assert result.returncode == 0, result.stdout + result.stderr
    packages = [call["options"] for call in calls if call["module"] == "dnf"]
    assert "bind-utils" in packages[0]["name"]
    assert packages[-1]["state"] == state
    if state == "latest":
        assert packages[-1]["name"] == "keepalived"
    assert all(call["use_backend"] == ("dnf5" if facts["pkg_mgr"] == "dnf5" else "dnf4") for call in packages)
    assert all(call["disable_gpg_check"] is False and call["allowerasing"] is False for call in packages)
    assert not any(call["module"] == "apt" for call in calls)
    configs = [call for call in calls if call["module"] == "template"]
    assert any("interface fixture0" in call["content"] and "192.0.2.11" in call["content"] for call in configs)
    script = next(call for call in configs if call["options"]["src"].endswith("check-dns.sh.j2"))
    assert script["options"]["setype"] == "_default"  # Never opt into the unconfined-script domain.


@pytest.mark.parametrize("facts", [rpm_alloy_facts("Rocky", "10.2"), rpm_alloy_facts("Fedora", "43", "dnf5")])
def test_technitium_rpm_uses_portable_application_and_retains_networkmanager_resolver(native_run, facts):
    result, calls = native_run(["technitium"], facts=facts)
    assert result.returncode == 0, result.stdout + result.stderr
    packages = [call["options"] for call in calls if call["module"] == "dnf"]
    assert packages and "aspnetcore-runtime-10.0" in packages[0]["name"] and "bind-utils" in packages[0]["name"]
    assert all(call["state"] == "present" and not call["disable_gpg_check"] and not call["allowerasing"] for call in packages)
    archive = next(call["options"] for call in calls if call["module"] == "unarchive")
    assert archive["creates"] == "/opt/technitium/dns/DnsServerApp.dll" and archive["owner"] == "root"
    unit = next(call for call in calls if call["module"] == "template")
    assert "User=dns-server" in unit["content"] and "NoNewPrivileges=true" in unit["content"]
    assert "CapabilityBoundingSet=CAP_NET_BIND_SERVICE" in unit["content"]
    assert not any("/etc/resolv.conf" in str(call["options"]) or "/etc/NetworkManager/" in str(call["options"]) for call in calls)
    assert not any(call["module"] == "apt" or call["options"].get("cmd", "").startswith("bash ") for call in calls)
    probe = next(call["options"]["argv"] for call in calls if call["module"] == "command")
    assert probe[probe.index("-p") + 1] == "15353"


def test_technitium_existing_rpm_marker_preserves_application_and_custom_unit_paths(native_run):
    result, calls = native_run(
        ["technitium"],
        facts=rpm_alloy_facts("Rocky", "9.7"),
        action="update",
        overrides={
            "fixture_application_installed": True,
            "fixture_unchanged": True,
            "technitium_native_install_marker": "/opt/operator-dns/DnsServerApp.dll",
            "technitium_native_service_name": "operator-dns",
            "technitium_native_config_dir": "/srv/operator-dns",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not any(call["module"] in {"get_url", "unarchive"} for call in calls)
    unit = next(call for call in calls if call["module"] == "template")
    assert unit["options"]["dest"] == "/etc/systemd/system/operator-dns.service"
    assert "ExecStart=/usr/bin/dotnet /opt/operator-dns/DnsServerApp.dll /srv/operator-dns" in unit["content"]
    assert not any(call["handler"] for call in calls)
    assert not any(call["options"].get("recurse", False) for call in calls if call["module"] == "file")


def test_technitium_rpm_resolved_integration_records_recovery_and_precedes_service_restart(native_run):
    result, calls = native_run(
        ["technitium"],
        facts=rpm_alloy_facts("Rocky", "10.1"),
        overrides={"fixture_services": {"systemd-resolved.service": {"state": "running"}}},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    writes = [call for call in calls if call["module"] == "copy" and call["options"].get("dest", "").endswith(".json")]
    assert json.loads(writes[0]["options"]["content"])["resolver"]["managed"] is True
    assert "/etc/systemd/resolved.conf.d/technitium.conf" in json.loads(writes[-1]["options"]["content"])["files"]
    resolver = next(i for i, call in enumerate(calls) if call["options"].get("dest") == "/etc/resolv.conf")
    dns = next(i for i, call in enumerate(calls) if call["handler"] and call["options"].get("name") == "dns")
    assert resolver < dns


@pytest.mark.parametrize("entry", ["keepalived", "technitium"])
@pytest.mark.parametrize("rpm", [False, True])
def test_native_dns_fresh_check_mode_defers_packages_installers_and_services(native_run, entry, rpm):
    result, calls = native_run([entry], facts=rpm_alloy_facts("Rocky", "10.2") if rpm else None, check=True, action=None)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not any(call["module"] in {"apt", "dnf", "get_url", "unarchive", "systemd", "systemd_service", "command"} for call in calls)
    assert "deferred" in result.stdout


@pytest.mark.parametrize("entry", ["keepalived", "technitium"])
@pytest.mark.parametrize(
    "facts,ostree",
    [
        (rpm_alloy_facts("Rocky", "10.2"), True),
        (rpm_alloy_facts("AlmaLinux", "10.2"), False),
        (rpm_alloy_facts("Rocky", "8"), False),
        (rpm_alloy_facts("Fedora", "40"), False),
        (rpm_alloy_facts(backend="apt"), False),
        ({**rpm_alloy_facts(), "service_mgr": "openrc"}, False),
    ],
)
def test_native_dns_rejects_unsupported_platform_before_any_ownership_or_install(native_run, entry, facts, ostree):
    result, calls = native_run([entry], facts=facts, ostree=ostree)
    assert result.returncode != 0
    assert {call["module"] for call in calls} <= {"setup", "stat"}
    assert "Native DNS services require" in result.stdout


@pytest.mark.parametrize("version", ["9.6", "10.0"])
def test_technitium_rpm_requires_repositories_with_the_current_dotnet_runtime(native_run, version):
    result, calls = native_run(["technitium"], facts=rpm_alloy_facts("Rocky", version))
    assert result.returncode != 0
    assert {call["module"] for call in calls} <= {"setup", "stat"}
    assert "ASP.NET Core 10" in result.stdout


def test_technitium_rpm_refuses_missing_resolved_output_before_ownership(native_run):
    result, calls = native_run(
        ["technitium"],
        facts=rpm_alloy_facts("Rocky", "10.2"),
        overrides={"fixture_services": {"systemd-resolved.service": {"state": "running"}}, "fixture_resolved_output": False},
    )
    assert result.returncode != 0 and "no usable resolver output" in result.stdout
    assert {call["module"] for call in calls} <= {"setup", "stat", "service_facts"}


def test_technitium_rpm_download_failure_never_changes_host_dns(native_run):
    result, calls = native_run(["technitium"], facts=rpm_alloy_facts("Rocky", "10.2"), overrides={"fixture_download_failure": True})
    assert result.returncode != 0
    assert not any(call["module"] in {"systemd", "systemd_service", "unarchive"} for call in calls)
    assert not any(call["options"].get("dest") in {"/etc/resolv.conf", "/etc/systemd/resolved.conf.d/technitium.conf"} for call in calls)


@pytest.mark.parametrize("action", ["recreate", "remove"])
def test_technitium_rpm_lifecycle_retires_only_owned_unit_and_retains_runtime_data(native_run, action):
    record = {"identity": "technitium:native", "unit": "dns", "files": ["/etc/systemd/system/dns.service"], "resolver": {"managed": False}}
    result, calls = native_run(
        ["technitium"], facts=rpm_alloy_facts("Rocky", "10.2"), action=action, overrides={"fixture_state": {"technitium": record}}
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not any(call["module"] in {"apt", "dnf", "get_url", "unarchive", "group", "user"} for call in calls)
    mutations = [call["options"]["path"] for call in calls if call["module"] == "file"]
    assert mutations == (["/etc/systemd/system/dns.service", "/var/lib/native_services/technitium.json"] if action == "remove" else [])
    services = [call["options"] for call in calls if call["module"] in {"systemd_service", "systemd"}]
    assert services[0]["state"] == ("stopped" if action == "remove" else "restarted")
    if action == "remove":
        assert services[-1] == {"daemon_reload": True}


def test_technitium_rpm_multihost_installation_keeps_each_host_marker_and_unit_independent(native_run):
    result, calls = native_run(["technitium"], facts=rpm_alloy_facts("Rocky", "10.2"), multiple_hosts=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert {call["host"] for call in calls if call["module"] == "unarchive"} == {"selected", "other"}
    assert {call["host"] for call in calls if call["handler"] and call["options"]["name"] == "dns"} == {"selected", "other"}


def test_technitium_rpm_incomplete_archive_cannot_claim_a_unit_or_restart_dns(native_run):
    result, calls = native_run(["technitium"], facts=rpm_alloy_facts("Rocky", "10.2"), overrides={"fixture_bad_archive": True})
    assert result.returncode != 0 and "did not supply" in result.stdout
    assert not any(call["module"] in {"template", "systemd", "systemd_service"} for call in calls)
    records = [json.loads(call["options"]["content"]) for call in calls if call["options"].get("dest", "").endswith(".json")]
    assert all(record["files"] == [] for record in records)


@pytest.mark.parametrize("allowed", [True, False])
def test_runner_check_mode_validates_dedicated_vm_without_authentication_or_installation(native_run, allowed):
    facts = rpm_alloy_facts("Rocky", "10.2") | {"virtualization_role": "guest", "virtualization_type": "kvm"}
    result, calls = native_run(
        ["forgejo_runner"], check=True, account=False, facts=facts, overrides={"native_services_forgejo_runner_controller": allowed}
    )
    assert (result.returncode == 0) is allowed, result.stdout + result.stderr
    assert not any(call["module"] in {"copy", "get_url", "slurp", "systemd_service", "pip", "user", "group"} for call in calls)
    if allowed:
        assert "Would manage homelab-ci/homelab-ci" in result.stdout
    else:
        assert "dedicated Rocky 10 controller VM" in result.stdout


@pytest.mark.parametrize("busy", [False, True])
def test_runner_removal_preserves_authentication_and_evidence_and_never_stops_active_work(native_run, busy):
    owned = [
        "/etc/systemd/system/forgejo-runner.service",
        "/etc/systemd/system/forgejo-runner-agent.service",
        "/etc/forgejo-runner/config.yml",
    ]
    state = {"identity": "forgejo_runner", "unit": "forgejo-runner", "files": owned}
    facts = rpm_alloy_facts("Rocky", "10.2") | {"virtualization_role": "guest", "virtualization_type": "kvm"}
    result, calls = native_run(
        ["forgejo_runner"],
        action="remove",
        facts=facts,
        overrides={
            "fixture_state": {"forgejo_runner": state},
            "fixture_runner_busy": busy,
            "fixture_services": {"forgejo-runner.service": {"state": "running"}, "forgejo-runner-agent.service": {"state": "running"}},
        },
    )
    assert (result.returncode == 0) is not busy, result.stdout + result.stderr
    mutations = [call for call in calls if call["module"] == "systemd_service"]
    if busy:
        assert not mutations
    else:
        removed = [call["options"]["path"] for call in calls if call["module"] == "file" and call["options"].get("state") == "absent"]
        assert removed == owned + ["/var/lib/native_services/forgejo_runner.json"]
        assert {call["options"]["name"] for call in mutations if "name" in call["options"]} == {"forgejo-runner", "forgejo-runner-agent"}


@pytest.mark.parametrize("failure", [None, "signature", "version", "scope"])
def test_runner_install_uses_guarded_signature_registration_and_owned_units(native_run, failure):
    facts = rpm_alloy_facts("Rocky", "10.2") | {"virtualization_role": "guest", "virtualization_type": "kvm"}
    registration = {
        "uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "token": ("1" * 40),
        "repository": "homelab-ci/homelab-ci",
        "url": "https://forgejo.private.example.test:9443",
    }
    if failure == "scope":
        registration["repository"] = "another/repository"
    result, calls = native_run(
        ["forgejo_runner"],
        facts=facts,
        overrides={
            "fixture_registration": registration,
            "fixture_bad_signature": failure == "signature",
            "fixture_bad_version": failure == "version",
        },
    )
    assert (result.returncode == 0) is (failure is None), result.stdout + result.stderr
    installations = [call for call in calls if call["module"] == "copy" and call["options"].get("dest") == "/usr/local/bin/forgejo-runner"]
    assert bool(installations) is (failure not in {"signature", "scope"})
    assert any(call["module"] == "command" and "--verify" in call["options"].get("argv", []) for call in calls) is (failure != "scope")
    registration_reads = [
        call
        for call in calls
        if call["module"] == "slurp" and call["options"].get("src") == "/etc/forgejo-runner/private/registration.json"
    ]
    assert registration_reads
    starts = [call for call in calls if call["module"] == "systemd_service" and call["options"].get("state") in {"started", "restarted"}]
    if failure:
        assert not starts
    else:
        config = next(
            call["content"]
            for call in calls
            if call["module"] == "template" and call["options"]["dest"] == "/etc/forgejo-runner/config.yml"
        )
        assert yaml.safe_load(config)["server"]["connections"]["homelab-ci"]["uuid"] == registration["uuid"]
        assert yaml.safe_load(config)["runner"]["capacity"] == 1
        assert set(call["options"]["name"] for call in starts) == {"forgejo-runner", "forgejo-runner-agent"}
        ownership = [
            json.loads(call["options"]["content"])
            for call in calls
            if call["module"] == "copy" and call["options"].get("dest") == "/var/lib/native_services/forgejo_runner.json"
        ]
        assert set(ownership[-1]["files"]) == {
            "/etc/forgejo-runner/config.yml",
            "/etc/systemd/system/forgejo-runner.service",
            "/etc/systemd/system/forgejo-runner-agent.service",
        }
        assert all(("1" * 40) not in json.dumps(record) for record in ownership)
        release = next(
            i for i, call in enumerate(calls) if call["module"] == "forgejo_runner_maintenance" and call["options"]["state"] == "absent"
        )
        assert all(i < release for i, call in enumerate(calls) if call["handler"])


@pytest.mark.parametrize("failure", ["json", "repository", "instance", "uuid", "token", "extra"])
def test_selected_registration_is_rejected_before_draining_or_replacing_installation(native_run, failure):
    registration = {
        "url": "https://forgejo.private.example.test:9443",
        "repository": "homelab-ci/homelab-ci",
        "uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "token": "1" * 40,
    }
    if failure in ["repository", "instance", "uuid", "token"]:
        registration[{"instance": "url"}.get(failure, failure)] = "unrelated-or-invalid"
    if failure == "extra":
        registration["CI_API_TOKEN"] = "example-token"
    facts = rpm_alloy_facts("Rocky", "10.2") | {"virtualization_role": "guest", "virtualization_type": "kvm"}
    overrides = {"fixture_registration": registration, "native_services_forgejo_runner_private_source_dir": "/fixture/selected-receipt"}
    if failure == "json":
        overrides["fixture_registration_raw"] = "malformed synthetic JSON"
    result, calls = native_run(["forgejo_runner"], facts=facts, action="update", overrides=overrides)
    assert result.returncode != 0
    assert not any(
        call["module"] in {"copy", "file", "template", "group", "user", "systemd_service", "forgejo_runner_maintenance"} for call in calls
    )
    reads = [call["options"]["src"] for call in calls if call["module"] == "slurp"]
    assert reads == ["/fixture/selected-receipt/registration.json"]
    snapshot = next(call["options"] for call in calls if call["module"] == "cleanup_snapshot")
    assert snapshot == {"registration_empty": True, "read_empty": True}


def test_selected_four_field_registration_is_copied_without_other_authentication(native_run):
    registration = {
        "url": "https://forgejo.private.example.test:9443",
        "repository": "homelab-ci/homelab-ci",
        "uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "token": "1" * 40,
    }
    facts = rpm_alloy_facts("Rocky", "10.2") | {"virtualization_role": "guest", "virtualization_type": "kvm"}
    result, calls = native_run(
        ["forgejo_runner"],
        facts=facts,
        overrides={"fixture_registration": registration, "native_services_forgejo_runner_private_source_dir": "/fixture/selected-receipt"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    copies = [
        call["options"]
        for call in calls
        if call["module"] == "copy" and call["options"].get("dest") == "/etc/forgejo-runner/private/registration.json"
    ]
    assert copies and all(json.loads(copy["content"]) == registration and copy["mode"] == "0600" for copy in copies)


@pytest.mark.parametrize("action", ["remove", "recreate"])
def test_runner_lifecycle_uses_only_required_resident_inputs(native_run, action):
    owned = [
        "/etc/systemd/system/forgejo-runner.service",
        "/etc/systemd/system/forgejo-runner-agent.service",
        "/etc/forgejo-runner/config.yml",
    ]
    facts = rpm_alloy_facts("Rocky", "10.2") | {"virtualization_role": "guest", "virtualization_type": "kvm"}
    missing = ["registration.json", "provisioning.json", "allocation.json", "guest-key", "guest-key.pub", "proxmox-ca.pem", "known_hosts"]
    if action == "remove":
        missing += ["node-key", "config.yml"]
    result, calls = native_run(
        ["forgejo_runner"],
        action=action,
        facts=facts,
        overrides={
            "fixture_state": {"forgejo_runner": {"identity": "forgejo_runner", "unit": "forgejo-runner", "files": owned}},
            "fixture_missing_inputs": missing,
            "fixture_services": {"forgejo-runner.service": {"state": "running"}, "forgejo-runner-agent.service": {"state": "running"}},
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not any(call["module"] == "slurp" and call["options"]["src"].endswith("/registration.json") for call in calls)
    assert not any(call["module"] in {"get_url", "pip", "git"} for call in calls)
    assert any(
        call["module"] == "systemd_service" and call["options"].get("state") == ("stopped" if action == "remove" else "restarted")
        for call in calls
    )


def test_real_repository_preparation_preserves_private_home_on_first_install_and_update(native_run, tmp_path):
    import pwd

    home = tmp_path / "runner-home"
    home.mkdir(mode=0o700)
    origin = tmp_path / "source"
    origin.mkdir()
    source = origin / "ansible/requirements.txt"
    source.parent.mkdir()
    source.write_text("# Offline synthetic tooling interface\n")
    for args in [
        ["init", "--quiet", "--initial-branch=main"],
        ["add", "."],
        [
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "-m",
            "Synthetic main",
        ],
    ]:
        subprocess.run(["git", "-C", str(origin), *args], check=True, capture_output=True, text=True)
    registration = {
        "url": "https://forgejo.private.example.test:9443",
        "repository": "homelab-ci/homelab-ci",
        "uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "token": "1" * 40,
    }
    facts = rpm_alloy_facts("Rocky", "10.2") | {"virtualization_role": "guest", "virtualization_type": "kvm"}
    overrides = dict(
        fixture_real_repository=True,
        fixture_home=str(home),
        fixture_registration=registration,
        workstation_user=pwd.getpwuid(os.getuid()).pw_name,
        workstation_repository_clone=True,
        workstation_repository_path=str(home / "homelab"),
        workstation_repository_url=str(origin),
        workstation_ansible_path=str(home / "homelab/ansible"),
        ansible_become=False,
    )
    first, calls = native_run(["forgejo_runner"], facts=facts, overrides=overrides)
    assert first.returncode == 0, first.stdout + first.stderr
    assert home.stat().st_mode & 0o777 == 0o700
    checkout = home / "homelab/ansible/requirements.txt"
    assert checkout.read_bytes() == source.read_bytes()
    state = [
        json.loads(call["options"]["content"])
        for call in calls
        if call["module"] == "copy" and call["options"].get("dest") == "/var/lib/native_services/forgejo_runner.json"
    ][-1]
    second, calls = native_run(
        ["forgejo_runner"], facts=facts, action="update", overrides=overrides | {"fixture_state": {"forgejo_runner": state}}
    )
    assert second.returncode == 0, second.stdout + second.stderr
    assert home.stat().st_mode & 0o777 == 0o700
    assert checkout.read_bytes() == source.read_bytes()


@pytest.mark.parametrize("action", ["remove", "recreate"])
def test_runner_does_not_stop_foreign_units_even_without_provisioning_inputs(native_run, action):
    facts = rpm_alloy_facts("Rocky", "10.2") | {"virtualization_role": "guest", "virtualization_type": "kvm"}
    result, calls = native_run(
        ["forgejo_runner"],
        action=action,
        facts=facts,
        overrides={
            "fixture_services": {"forgejo-runner.service": {"state": "running"}},
            "fixture_missing_inputs": ["provisioning.json"],
        },
    )
    assert result.returncode != 0 and "refusing adoption or removal" in result.stdout
    assert not any(call["module"] in {"systemd_service", "forgejo_runner_maintenance", "file", "copy"} for call in calls)


def test_runner_restart_rejects_missing_boot_key_before_drain_or_service_changes(native_run):
    facts = rpm_alloy_facts("Rocky", "10.2") | {"virtualization_role": "guest", "virtualization_type": "kvm"}
    owned = [
        "/etc/systemd/system/forgejo-runner.service",
        "/etc/systemd/system/forgejo-runner-agent.service",
        "/etc/forgejo-runner/config.yml",
    ]
    result, calls = native_run(
        ["forgejo_runner"],
        action="recreate",
        facts=facts,
        overrides={
            "fixture_state": {"forgejo_runner": {"identity": "forgejo_runner", "unit": "forgejo-runner", "files": owned}},
            "fixture_missing_inputs": ["node-key"],
        },
    )
    assert result.returncode != 0
    assert not any(call["module"] in {"systemd_service", "forgejo_runner_maintenance", "file", "copy"} for call in calls)


def test_handler_failure_retains_maintenance_ownership_and_clears_private_snapshots(native_run):
    registration = {
        "url": "https://forgejo.private.example.test:9443",
        "repository": "homelab-ci/homelab-ci",
        "uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "token": "1" * 40,
    }
    facts = rpm_alloy_facts("Rocky", "10.2") | {"virtualization_role": "guest", "virtualization_type": "kvm"}
    result, calls = native_run(
        ["forgejo_runner"], facts=facts, overrides={"fixture_registration": registration, "fixture_runner_handler_failure": True}
    )
    assert result.returncode != 0 and "synthetic handler failure" in result.stdout
    assert [call["options"]["state"] for call in calls if call["module"] == "forgejo_runner_maintenance"] == ["present"]
    assert next(call["options"] for call in calls if call["module"] == "cleanup_snapshot") == {
        "registration_empty": True,
        "read_empty": True,
    }
