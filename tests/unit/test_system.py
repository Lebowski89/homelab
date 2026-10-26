"""Execute the real role decisions with controller-side, stateful fake host operations."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, StrictUndefined

REPO = Path(__file__).resolve().parents[2]
ANSIBLE = shutil.which(str(Path(sys.executable).with_name("ansible-playbook")))
pytestmark = pytest.mark.integration


@pytest.fixture
def system_run(tmp_path):
    roles = tmp_path / "roles"
    for role in ("system", "postgres"):
        shutil.copytree(REPO / "ansible/roles" / role, roles / role, ignore=shutil.ignore_patterns("__pycache__"))
    modules = {
        "apt",
        "template",
        "find",
        "dnf",
        "command",
        "stat",
        "slurp",
        "file",
        "copy",
        "lineinfile",
        "systemd_service",
        "systemd",
        "setup",
        "ansible.posix.sysctl",
        "community.general.pam_limits",
    }

    def instrument(tasks):
        for task in tasks:
            for branch in ("block", "rescue", "always"):
                instrument(task.get(branch, []))
            for module in modules:
                key = module if "." in module else f"ansible.builtin.{module}"
                if key in task:
                    task["fixture_operation"] = {"module": module, "options": task.pop(key)}
            if "ansible.builtin.include_tasks" in task and task["ansible.builtin.include_tasks"].get("file", "").startswith("sub_tasks/"):
                include = task["ansible.builtin.include_tasks"]
                if include["file"] != "sub_tasks/backup_prerequisites.yml":
                    task["fixture_operation"] = {"module": "include_tasks", "options": task.pop("ansible.builtin.include_tasks")}

    for role in ("system", "postgres"):
        # Only PostgreSQL's entry point and the moved dependency file are selected.
        paths = list((roles / role / "tasks").rglob("*.yml")) + list((roles / role / "handlers").glob("*.yml"))
        for path in paths:
            tasks = yaml.safe_load(path.read_text())
            instrument(tasks)
            path.write_text(yaml.safe_dump(tasks, sort_keys=False))
    plugins = tmp_path / "action_plugins"
    plugins.mkdir()
    (plugins / "fixture_operation.py").write_text("""from ansible.plugins.action import ActionBase
import base64, json
from pathlib import Path
class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        v = task_vars
        module, options = self._task.args['module'], self._task.args['options'] or {}
        record = {'module': module, 'options': options, 'environment': self._task.environment}
        with open(v['fixture_record'], 'a') as output:
            output.write(json.dumps(record, default=str) + '\\n')
        state_path = Path(v['fixture_state'])
        state = json.loads(state_path.read_text())
        result = {'changed': False, 'rc': 0, 'stdout': '', 'stdout_lines': []}
        if module in ('apt', 'dnf') and options.get('name') == 'qemu-guest-agent' and v.get('fixture_guest_agent_failure', False):
            return dict(result, failed=True, rc=1, msg='fixture-agent-failure')
        if module == 'setup':
            result['ansible_facts'] = v['fixture_facts']
        elif module == 'template':
            result['changed'] = v.get('fixture_nic_artifacts_changed', False)
        elif module == 'find':
            result['files'] = [{'path': '/etc/systemd/system/multi-user.target.wants/' + unit} for unit in v.get('fixture_nic_enabled', [])]
        elif module == 'stat':
            path = options['path']
            exists = v.get('fixture_ostree', False) if path == '/run/ostree-booted' else False
            if path == v.get('system_swap_path', '/swapfile'):
                exists = state.get('exists', False)
            if path in v.get('fixture_files', {}):
                exists = True
            result['stat'] = {'exists': exists, 'isreg': exists,
                              'size': state.get('size', 2048 * 1024 * 1024)}
        elif module == 'slurp':
            result['content'] = base64.b64encode(v['fixture_files'][options['src']].encode()).decode()
        elif module == 'command':
            argv = options['argv']
            command = argv[0]
            if command == 'timeout':
                result['stdout_lines'] = ['SYSTEM_NIC_CHANGE=' + name for name in v.get('fixture_nic_drift', [])]
                result['stdout'] = '\\n'.join(result['stdout_lines'])
                if v.get('fixture_nic_preflight_failure', False):
                    result.update(rc=1, failed=True, msg='fixture-nic-preflight-failure')
            elif command == 'systemd-escape':
                result['stdout'] = argv[-1].replace('-', r'\\x2d')
            elif command == 'swapon' and '--show=NAME' in argv:
                result['stdout_lines'] = state.get('active', [])
            elif command == 'findmnt':
                result['stdout_lines'] = state.get('persistent', [])
                result['rc'] = 0 if result['stdout_lines'] else 1
            elif command == 'blkid':
                result['stdout'] = 'swap' if state.get('formatted', False) else ''
                result['rc'] = 0 if result['stdout'] else 2
            elif command == 'fallocate':
                result['changed'] = not state.get('exists', False)
                if not self._play_context.check_mode:
                    state['exists'] = True
            elif command == 'mkswap':
                if v.get('fixture_format_failure', False):
                    result.update(rc=1, failed=True)
                else:
                    state['formatted'] = True
            elif command == 'swapon':
                state['active'] = [argv[-1]]
        elif module == 'lineinfile' and options['path'] == '/etc/fstab':
            if not self._play_context.check_mode:
                state['persistent'] = [v.get('system_swap_path', '/swapfile')]
        state_path.write_text(json.dumps(state))
        return result
""")
    config = tmp_path / "ansible.cfg"
    config.write_text((REPO / "ansible/bootstrap.cfg").read_text().replace("[defaults]", f"[defaults]\naction_plugins = {plugins}"))
    state_file = tmp_path / "state.json"
    record = tmp_path / "calls.jsonl"

    def run(*, distro="Rocky", backend=None, tags="system_packages", overrides=None, state=None, check=False, main=False, role="system"):
        record.unlink(missing_ok=True)
        if state is not None or not state_file.exists():
            state_file.write_text(json.dumps(state or {}))
        facts = {
            "distribution": distro,
            "distribution_version": "10.2",
            "distribution_major_version": "10",
            "os_family": "Debian" if distro in ("Ubuntu", "Debian") else "RedHat",
            "pkg_mgr": backend or ("apt" if distro in ("Ubuntu", "Debian") else "dnf"),
            "service_mgr": "systemd",
            "virtualization_type": "kvm",
            "virtualization_role": "guest",
        }
        variables = {
            "ansible_facts": facts,
            "fixture_facts": facts,
            "fixture_record": str(record),
            "fixture_state": str(state_file),
            "system_hosts": "all",
            "services_controller_host": "localhost",
            "ansible_become": False,
        }
        variables.update(overrides or {})
        variables["fixture_facts"] = variables.pop("ansible_facts", facts)
        inventory = tmp_path / "inventory.yml"
        inventory.write_text(
            yaml.safe_dump(
                {
                    "all": {
                        "children": {
                            "tags_skynet": {"hosts": {"localhost": variables}},
                            "tags_postgres": {"hosts": {"localhost": {}}},
                        }
                    }
                }
            )
        )
        plays = [
            {
                "hosts": "all",
                "connection": "local",
                "gather_facts": False,
                "pre_tasks": [{"name": "Gather fixture facts", "fixture_operation": {"module": "setup", "options": {}}, "tags": "always"}],
                "roles": [role],
            }
        ]
        if main:
            plays = yaml.safe_load((REPO / "ansible/playbook.yml").read_text())
            for play in plays:
                instrument(play.get("tasks", []))
            shutil.copytree(REPO / "ansible/tasks", tmp_path / "tasks", dirs_exist_ok=True)
            # Prove that application-wide Vault is never loaded with bootstrap.cfg.
            all_vars = tmp_path / "group_vars/all"
            all_vars.mkdir(parents=True, exist_ok=True)
            (all_vars / "private.yml").write_text("$ANSIBLE_VAULT;1.1;AES256\nsynthetic-invalid-vault\n")
        playbook = tmp_path / "playbook.yml"
        playbook.write_text(yaml.safe_dump(plays, sort_keys=False))
        result = subprocess.run(
            [ANSIBLE, "-i", str(inventory), "-c", "local", str(playbook), "--tags", tags, *(["--check"] if check else [])],
            env={
                **os.environ,
                "ANSIBLE_CONFIG": str(config),
                "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
                "ANSIBLE_COLLECTIONS_PATH": str(tmp_path / "empty-collections"),
                "ANSIBLE_COLLECTIONS_SCAN_SYS_PATH": "false",
            },
            capture_output=True,
            text=True,
            check=False,
        )
        calls = [json.loads(line) for line in record.read_text().splitlines()] if record.exists() else []
        return result, calls, json.loads(state_file.read_text())

    return run


def successful(result):
    assert result.returncode == 0, result.stdout + result.stderr


def package_calls(calls):
    return [call for call in calls if call["module"] in {"apt", "dnf"}]


@pytest.mark.parametrize(("distro", "backend"), [("Ubuntu", "apt"), ("Debian", "apt"), ("Rocky", "dnf"), ("Fedora", "dnf5")])
def test_native_packages_do_not_upgrade_or_cleanup_and_keep_guest_agent(system_run, distro, backend):
    result, calls, _ = system_run(distro=distro, backend=backend, main=True)
    successful(result)
    packages = package_calls(calls)
    assert packages and {call["module"] for call in packages} == {"apt" if backend == "apt" else "dnf"}
    for call in packages:
        assert call["options"]["state"] == "present"
        assert not {"upgrade", "autoremove", "autoclean"} & call["options"].keys()
        if backend != "apt":
            assert call["options"]["use_backend"] == backend
            assert "DEBIAN_FRONTEND" not in str(call["environment"])
            # Keep Rocky curl-minimal installed; no conflicting full-curl request.
            assert "curl" not in call["options"]["name"]
    assert any(call["options"].get("name") == "qemu-guest-agent" for call in packages)
    assert any(call["module"] == "systemd_service" and call["options"].get("name") == "qemu-guest-agent" for call in calls)
    assert not any(call["module"] in {"copy", "file", "lineinfile", "command"} for call in calls)


@pytest.mark.parametrize(
    ("distro", "backend", "overrides"),
    [
        ("CentOS", "dnf", {}),
        ("Bazzite", "dnf5", {}),
        ("Fedora", "dnf5", {"fixture_ostree": True}),
        ("Ubuntu", "dnf", {}),
        ("Rocky", "dnf", {"fixture_ostree": True}),
        ("Rocky", "dnf", {"system_resolved_enabled": True}),
        ("Rocky", "dnf", {"system_swap_enabled": "yes"}),
    ],
)
def test_unsupported_platform_or_feature_fails_before_mutation(system_run, distro, backend, overrides):
    result, calls, _ = system_run(distro=distro, backend=backend, overrides=overrides, tags="system")
    assert result.returncode != 0
    assert {call["module"] for call in calls} <= {"stat", "setup"}


@pytest.mark.parametrize(("distro", "backend"), [("Ubuntu", "apt"), ("Rocky", "dnf"), ("Fedora", "dnf5")])
def test_baseline_and_explicit_maintenance_are_separate(system_run, distro, backend):
    result, calls, _ = system_run(distro=distro, backend=backend, tags="system")
    successful(result)
    assert all(call["options"].get("state") == "present" for call in package_calls(calls))
    assert not any(call["options"].get("dest") == "/etc/resolv.conf" for call in calls)
    result, calls, _ = system_run(distro=distro, backend=backend, tags="system_updates", check=True)
    successful(result)
    packages = package_calls(calls)
    assert len(packages) == 1
    assert packages[0]["options"].get("upgrade") == "safe" if backend == "apt" else packages[0]["options"]["update_only"]
    assert not any(call["options"].get("autoremove") or call["options"].get("autoclean") for call in calls)


@pytest.mark.parametrize("dns_host", [False, True])
def test_optional_ubuntu_resolver_keeps_split_dns_and_scoped_stub_configuration(system_run, dns_host):
    result, calls, _ = system_run(
        distro="Ubuntu",
        tags="system_resolved",
        overrides={
            "system_resolved_enabled": True,
            "system_resolved_disable_stub": dns_host,
        },
    )
    successful(result)
    nss = next(call for call in calls if call["module"] == "lineinfile")
    assert "resolve [!UNAVAIL=return] dns" in nss["options"]["line"]
    dropin = next(call for call in calls if call["module"] == "copy")
    assert ("DNSStubListener=no" in dropin["options"]["content"]) == dns_host
    links = [call for call in calls if call["module"] == "file" and call["options"].get("state") == "link"]
    assert bool(links) == dns_host


def test_guest_agent_check_mode_does_not_start_service_and_bare_metal_has_no_agent(system_run):
    result, calls, _ = system_run(check=True)
    successful(result)
    assert not any(call["module"] == "systemd_service" for call in calls)
    facts = {
        "distribution": "Rocky",
        "distribution_major_version": "10",
        "os_family": "RedHat",
        "pkg_mgr": "dnf",
        "service_mgr": "systemd",
        "virtualization_type": "NA",
        "virtualization_role": "host",
    }
    result, calls, _ = system_run(overrides={"ansible_facts": facts})
    successful(result)
    assert not any(call["options"].get("name") == "qemu-guest-agent" for call in calls)


@pytest.mark.parametrize("check", [False, True])
@pytest.mark.parametrize("source", ["active", "persistent"])
def test_administrator_swap_is_preserved(system_run, check, source):
    result, calls, state = system_run(
        tags="system_swap", check=check, state={source: ["/dev/zram0"]}, overrides={"system_swap_enabled": True}
    )
    successful(result)
    assert not any(call["module"] in {"file", "lineinfile"} for call in calls)
    assert not any(call["module"] == "command" and call["options"]["argv"][0] in {"fallocate", "mkswap"} for call in calls)
    assert state == {source: ["/dev/zram0"]}


def test_swap_check_mode_missing_file_is_read_only(system_run):
    result, calls, state = system_run(tags="system_swap", check=True, overrides={"system_swap_enabled": True})
    successful(result)
    assert not state
    assert not any(call["module"] == "command" and call["options"]["argv"][0] == "mkswap" for call in calls)
    assert not any(call["module"] == "command" and call["options"]["argv"] == ["swapon", "/swapfile"] for call in calls)


def test_swap_creation_rerun_and_recovery_do_not_reformat_existing_swap(system_run):
    overrides = {"system_swap_enabled": True}
    result, calls, state = system_run(tags="system_swap", overrides=overrides)
    successful(result)
    assert state["formatted"] and state["active"] == state["persistent"] == ["/swapfile"]
    result, calls, _ = system_run(tags="system_swap", overrides=overrides)
    successful(result)
    assert not any(call["module"] == "command" and call["options"]["argv"][0] == "mkswap" for call in calls)
    assert not any(call["module"] == "command" and call["options"]["argv"] == ["swapon", "/swapfile"] for call in calls)
    # A formatted file after interruption is safely persisted/activated again.
    result, calls, state = system_run(tags="system_swap", state={"exists": True, "formatted": True}, overrides=overrides)
    successful(result)
    assert state["active"] == state["persistent"] == ["/swapfile"]
    assert not any(call["module"] == "command" and call["options"]["argv"][0] == "mkswap" for call in calls)


def test_swap_refuses_unrelated_or_partially_unformatted_files(system_run):
    result, calls, state = system_run(
        tags="system_swap", state={"exists": True, "formatted": False}, overrides={"system_swap_enabled": True}
    )
    assert result.returncode != 0
    assert not any(call["module"] in {"file", "lineinfile"} for call in calls)
    result, _, state = system_run(tags="system_swap", state={}, overrides={"system_swap_enabled": True, "fixture_format_failure": True})
    assert result.returncode != 0 and state["exists"] and not state.get("formatted")
    result, calls, _ = system_run(tags="system_swap", overrides={"system_swap_enabled": True})
    assert result.returncode != 0
    assert not any(call["module"] == "command" and call["options"]["argv"][0] == "mkswap" for call in calls)


@pytest.mark.parametrize("modified", [False, True])
def test_legacy_nic_settings_are_preserved_without_an_explicit_transition(system_run, modified):
    tasks = yaml.safe_load((REPO / "ansible/roles/system/tasks/cleanup.yml").read_text())
    unit = next(task["vars"]["system_legacy_nic_unit"] for task in tasks if "vars" in task)
    files = {
        "/etc/systemd/system/nic-tuning.service": unit + ("# administrator change\n" if modified else ""),
        "/usr/local/sbin/nic-tuning.sh": "#!/usr/bin/env bash\nset -e\n\nethtool -K ens18 rx-udp-gro-forwarding on rx-gro-list off\n",
    }
    result, calls, _ = system_run(tags="system_cleanup", overrides={"fixture_files": files})
    successful(result)
    removed = [call["options"]["path"] for call in calls if call["module"] == "file" and call["options"]["state"] == "absent"]
    assert not removed
    assert not any(call["module"] == "command" for call in calls)


@pytest.mark.parametrize("tag", ["postgres_backup", "postgres_backup_setup", "postgres_backup_run"])
def test_postgres_backup_installs_dependencies_before_setup_or_execution(system_run, tag):
    result, calls, _ = system_run(distro="Ubuntu", role="postgres", tags=tag)
    successful(result)
    packages = package_calls(calls)
    assert len(packages) == 1 and packages[0]["options"]["state"] == "present"
    assert calls.index(packages[0]) < next(i for i, call in enumerate(calls) if call["module"] == "include_tasks")


def test_inventory_keeps_swap_explicit_and_scoped_to_postgres():
    defaults = yaml.safe_load((REPO / "ansible/roles/system/defaults/main.yml").read_text())
    postgres = yaml.safe_load((REPO / "ansible/group_vars/tags_postgres.yml").read_text())
    assert defaults["system_swap_enabled"] is False
    assert postgres["system_swap_enabled"] is True


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("packages", "system_packages"),
        ("updates", "system_updates"),
        ("sysctl", "system_sysctl"),
        ("limits", "system_limits"),
        ("nic", "system_nic"),
    ],
)
def test_skynet_system_static_bootstrap_and_retired_network_commands(tmp_path, command, expected):
    source = REPO / "ansible/roles/workstation/templates/skynet.j2"
    defaults = yaml.safe_load((REPO / "ansible/roles/workstation/defaults/main.yml").read_text())
    # Supply synthetic paths; wrapper only invokes the fake Ansible recorder.
    values = {key: str(tmp_path / key) for key in defaults if key.startswith("workstation_")}
    values["workstation_repository_path"] = str(REPO)
    values["workstation_user_home"] = str(tmp_path / "home")
    wrapper = tmp_path / "skynet"
    wrapper.write_text(Environment(undefined=StrictUndefined).from_string(source.read_text()).render(**values))
    fake = tmp_path / "ansible-playbook"
    record = tmp_path / "arguments.json"
    fake.write_text(
        f"#!{sys.executable}\nimport json,os,sys\nfrom pathlib import Path\nPath({str(record)!r}).write_text(json.dumps([sys.argv[1:],os.environ['ANSIBLE_CONFIG']]))\n"
    )
    fake.chmod(0o755)
    env = {
        **os.environ,
        "ANSIBLE_PLAYBOOK_BIN": str(fake),
        "INVENTORY": "192.0.2.10,",
        "ANSIBLE_LOG_PATH": str(tmp_path / "ansible.log"),
    }
    env.pop("ANSIBLE_CONFIG", None)
    result = subprocess.run(["bash", str(wrapper), "run", "system", command], env=env, capture_output=True, text=True, check=False)
    successful(result)
    args, config = json.loads(record.read_text())
    assert args[args.index("--tags") + 1] == expected
    assert "system_hosts=all" in args and config.endswith("bootstrap.cfg")
    record.unlink()
    for args in [("run", "ubuntu", "netplan"), ("check", "Ubuntu", "network"), ("check", "ubuntu_netplan"), ("check", "System", "netplan")]:
        result = subprocess.run(["bash", str(wrapper), *args], env=env, capture_output=True, text=True, check=False)
        assert result.returncode != 0 and not record.exists()


def test_rocky_prior_major_and_dnf_autoclean_are_rejected_before_packages(system_run):
    facts = {"distribution": "Rocky", "distribution_major_version": "9", "os_family": "RedHat", "pkg_mgr": "dnf", "service_mgr": "systemd"}
    result, calls, _ = system_run(overrides={"ansible_facts": facts})
    assert result.returncode != 0 and not package_calls(calls)
    result, calls, _ = system_run(tags="system_updates", overrides={"system_updates_autoclean": True})
    assert result.returncode != 0 and not package_calls(calls)


@pytest.mark.parametrize(("changed", "drift", "expected"), [(False, [], []), (True, [], ["p0", "p1"]), (False, ["p1"], ["p1"])])
def test_nic_persistence_reapplies_configuration_changes_and_drift(system_run, changed, drift, expected):
    result, calls, _ = system_run(
        tags="system_nic",
        overrides={
            "system_nic_interfaces": {"p0": {"disable_fw_lldp": True}, "p1": {"udp_gro_forwarding": True}},
            "fixture_nic_artifacts_changed": changed,
            "fixture_nic_drift": drift,
        },
    )
    successful(result)
    restarted = [
        call["options"]["name"] for call in calls if call["module"] == "systemd_service" and call["options"].get("state") == "restarted"
    ]
    assert restarted == [f"skynet-system-nic@{name}.service" for name in expected]
    assert all(call["options"].get("state") != "started" for call in calls if call["module"] == "systemd_service")


@pytest.mark.parametrize(
    ("migrate", "modified", "preflight_failure", "accepted"),
    [
        (False, False, False, False),
        (True, True, False, False),
        (True, False, True, False),
        (True, False, False, True),
    ],
)
def test_nic_transition_requires_explicit_intent_known_artifacts_and_successful_preflight(
    system_run, migrate, modified, preflight_failure, accepted
):
    tasks = yaml.safe_load((REPO / "ansible/roles/system/tasks/cleanup.yml").read_text())
    unit = next(task["vars"]["system_legacy_nic_unit"] for task in tasks if "vars" in task)
    files = {
        "/etc/systemd/system/nic-tuning.service": unit + ("# administrator change\n" if modified else ""),
        "/usr/local/sbin/nic-tuning.sh": "#!/usr/bin/env bash\nset -e\n\nethtool -K p0 disable-fw-lldp on rx-udp-gro-forwarding on rx-gro-list off\n",
    }
    result, calls, _ = system_run(
        tags="system_nic",
        overrides={
            "system_nic_interfaces": {"p0": {"disable_fw_lldp": True}},
            "system_nic_migrate_legacy": migrate,
            "fixture_files": files,
            "fixture_nic_preflight_failure": preflight_failure,
        },
    )
    assert (result.returncode == 0) == accepted, result.stdout + result.stderr
    removals = [call for call in calls if call["module"] == "file" and call["options"].get("state") == "absent"]
    assert bool(removals) == accepted
    if not accepted:
        assert not any(call["module"] == "systemd_service" for call in calls)


def test_removed_nic_selection_disables_only_its_own_persistence(system_run):
    result, calls, _ = system_run(
        tags="system_nic",
        overrides={
            "system_nic_interfaces": {},
            "fixture_nic_enabled": ["skynet-system-nic@p0.service"],
            "fixture_files": {"/etc/systemd/system/skynet-system-nic@.service": "# Managed by Ansible: system NIC settings.\n"},
        },
    )
    successful(result)
    services = [call["options"] for call in calls if call["module"] == "systemd_service"]
    assert services == [{"name": "skynet-system-nic@p0.service", "enabled": False, "state": "stopped"}]


def test_nic_check_mode_never_applies_or_changes_services(system_run):
    result, calls, _ = system_run(
        tags="system_nic",
        check=True,
        overrides={
            "system_nic_interfaces": {"p0": {"disable_fw_lldp": True}},
            "fixture_nic_artifacts_changed": True,
        },
    )
    successful(result)
    assert not any(call["module"] == "systemd_service" for call in calls)
    assert not any(call["module"] == "command" and call["options"]["argv"][0] == "timeout" for call in calls)


@pytest.mark.parametrize(
    "interfaces", [{"p0": {"disable_fw_lldp": "yes"}}, {"p0;reboot": {"disable_fw_lldp": True}}, {"p0": {"unknown_setting": True}}]
)
def test_invalid_nic_selection_is_rejected_before_package_changes(system_run, interfaces):
    result, calls, _ = system_run(tags="system_nic", overrides={"system_nic_interfaces": interfaces})
    assert result.returncode != 0
    assert not package_calls(calls)
    assert not any(call["module"] == "command" for call in calls)


def test_nic_management_refuses_to_overwrite_an_unrelated_script(system_run):
    result, calls, _ = system_run(
        tags="system_nic",
        overrides={
            "system_nic_interfaces": {"p0": {"udp_gro_forwarding": True}},
            "fixture_files": {"/usr/local/sbin/skynet-system-nic": "#!/bin/sh\n# administrator settings\n"},
        },
    )
    assert result.returncode != 0
    assert not package_calls(calls)
    assert not any(call["module"] == "template" for call in calls)


@pytest.mark.parametrize(
    ("tag", "overrides", "error"),
    [
        ("system_packages", {"fixture_guest_agent_failure": True}, "fixture-agent-failure"),
        (
            "system_nic",
            {"system_nic_interfaces": {"p0": {"disable_fw_lldp": True}}, "fixture_nic_preflight_failure": True},
            "fixture-nic-preflight-failure",
        ),
    ],
)
def test_block_error_handling_preserves_failure_and_stops_later_changes(system_run, tag, overrides, error):
    result, calls, _ = system_run(tags=tag, overrides=overrides)
    assert result.returncode != 0
    assert error in result.stdout
    assert not any(call["module"] in {"template", "systemd_service"} for call in calls)
