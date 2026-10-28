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
        "apt_repository",
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
            for module in operations:
                key = f"ansible.builtin.{module}"
                if key in task:
                    task["fixture_operation"] = {"module": module, "options": task.pop(key) or {}}

    for directory in ("tasks", "handlers"):
        for path in (copied / directory).glob("*.yml"):
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
        result = {'changed': module in ('file', 'user', 'copy', 'template'), 'rc': 0, 'stdout': ''}
        if module == 'stat':
            app = v['native_services_application']
            state = v.get('fixture_state', {}).get(app)
            result['stat'] = ({'exists': state is not None} if options['path'].endswith('.json') else
                              v.get('fixture_resolver', {'exists': True, 'islnk': True, 'lnk_source': '/run/systemd/resolve/stub-resolv.conf'}))
        if module == 'slurp':
            state = v.get('fixture_state', {})[v['native_services_application']]
            result['content'] = base64.b64encode(json.dumps(state).encode()).decode()
        if module == 'service_facts':
            result['ansible_facts'] = {'services': {v['native_services_unit'] + '.service': {'state': 'running'}}}
        if module == 'get_url' and v.get('fixture_download_failure', False):
            result.update(failed=True, msg='fixture download failure')
        if module == 'setup':
            result['ansible_facts'] = v['fixture_facts']
        if module == 'getent':
            if options['database'] == 'passwd':
                accounts = {v['alloy_native_user']: ['x', '1001', '1001', '', '/fixture/alloy', '/usr/sbin/nologin']}
                result['ansible_facts'] = {'getent_passwd': accounts if v['fixture_account'] else {}}
            else:
                groups = {'adm': ['x', '4', ''], 'systemd-journal': ['x', '999', '']}
                if v['fixture_account']:
                    groups[v['alloy_native_group']] = ['x', '1001', '']
                result['ansible_facts'] = {'getent_group': groups}
        return result
""")
    cfg = tmp_path / "ansible.cfg"
    cfg.write_text(
        f"[defaults]\nroles_path = {tmp_path / 'roles'}\naction_plugins = {plugins}\ninject_facts_as_vars = false\nfilter_plugins = {ROOT / 'ansible/filter_plugins'}\n"
    )
    source_play = next(play for play in yaml.safe_load((ROOT / "ansible/playbook.yml").read_text()) if play.get("hosts") == "tags_skynet")
    selected_tasks = [task for task in source_play["tasks"] if set(task.get("tags", [])) & set(ENTRIES.values())]
    record = tmp_path / "operations.jsonl"

    def run(entries, *, check=False, account=True, peer_address=True, overrides=None, action="deploy", multiple_hosts=False):
        variables = {
            "fixture_record": str(record),
            "fixture_account": account,
            "fixture_facts": {"os_family": "Debian", "default_ipv4": {"interface": "eth0"}},
            "ansible_facts": {"os_family": "Debian", "default_ipv4": {"interface": "eth0"}},
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
        variables.update(overrides or {})
        inventory = {
            "all": {
                "children": {
                    "tags_skynet": {
                        "hosts": {
                            "selected": {"ansible_connection": "local", **variables},
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
                        ("tags_podman" if entry == "alloy" else "tags_" + ENTRIES[entry]): {
                            "hosts": {"selected": {}, **({"other": {}} if multiple_hosts else {})}
                        }
                        for entry in entries
                    },
                }
            }
        }
        inv = tmp_path / "inventory.yml"
        inv.write_text(yaml.safe_dump(inventory))
        play = {**deepcopy(source_play), "tasks": deepcopy(selected_tasks)}
        # Use the real catalogue and preflight; all remote modules are replaced
        # by the recorder and there is deliberately no application controller.
        instrument(play["pre_tasks"])
        instrument(play["tasks"])
        playbook = tmp_path / "play.yml"
        playbook.write_text(yaml.safe_dump([play], sort_keys=False))
        record.unlink(missing_ok=True)
        args = [
            ANSIBLE,
            "-i",
            str(inv),
            str(playbook),
            "--tags",
            ",".join(([action] if action else []) + [ENTRIES[entry] for entry in entries]),
        ]
        if check:
            args.append("--check")
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
    result, calls = native_run(list(ENTRIES))
    assert result.returncode == 0, result.stdout + result.stderr
    restarted = [call["options"]["name"] for call in calls if call["handler"] and call["options"].get("state") == "restarted"]
    assert sorted(restarted) == ["fixture-alloyd", "keepalived", "node_exporter", "systemd-resolved"]


def test_fresh_alloy_check_mode_defers_package_account_work(native_run):
    result, calls = native_run(["alloy"], check=True, account=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert any(call["module"] == "apt" for call in calls)
    assert not any(call["module"] in ("user", "template", "systemd_service") for call in calls)


def test_alloy_install_requires_the_package_account_before_configuration(native_run):
    result, calls = native_run(["alloy"], account=False)
    assert result.returncode != 0
    assert any(call["module"] == "apt" for call in calls)
    assert not any(call["module"] in ("user", "template", "systemd_service") for call in calls)


def test_node_exporter_check_mode_skips_archive_and_service_lifecycle(native_run):
    result, calls = native_run(["node_exporter"], check=True, action=None)
    assert result.returncode == 0, result.stdout + result.stderr
    assert any(call["module"] == "template" for call in calls)
    assert not any(call["module"] in ("get_url", "unarchive", "copy", "systemd") for call in calls)


def test_keepalived_peer_validation_runs_before_installation(native_run):
    result, calls = native_run(["keepalived"], peer_address=False)
    assert result.returncode != 0
    assert "local_ip" in result.stdout
    assert not any(call["module"] == "apt" for call in calls)


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


def test_technitium_defined_false_empty_and_numeric_overrides_do_not_fall_back(native_run):
    result, calls = native_run(
        ["technitium"],
        overrides={
            "technitium_native_disable_resolved_stub": False,
            "technitium_native_resolved_dns_servers": [],
            "technitium_native_web_port": 15400,
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not any(call["options"].get("dest") in {"/etc/resolv.conf", "/etc/systemd/resolved.conf.d/technitium.conf"} for call in calls)
    assert not any(call["handler"] for call in calls)
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
