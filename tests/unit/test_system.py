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
    fixture_roles = ("system", "postgres", "postgres_exporter", "docker", "podman", "service_common")
    for role in fixture_roles:
        shutil.copytree(REPO / "ansible/roles" / role, roles / role, ignore=shutil.ignore_patterns("__pycache__"))
    modules = {
        "apt",
        "uri",
        "community.general.sefcontext",
        "community.general.serestorecon",
        "get_url",
        "unarchive",
        "rpm_key",
        "yum_repository",
        "deb822_repository",
        "package_facts",
        "group",
        "user",
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
        "service_facts",
        "wait_for",
        "ansible.posix.sysctl",
        "community.general.pam_limits",
        "community.docker.docker_swarm",
        "community.docker.docker_network",
        "community.docker.docker_network_info",
        "community.docker.docker_node",
    }

    def instrument(tasks):
        for task in tasks:
            for branch in ("block", "rescue", "always"):
                instrument(task.get(branch, []))
            for module in modules:
                key = module if "." in module else f"ansible.builtin.{module}"
                if key in task:
                    task["fixture_operation"] = {"module": module, "options": task.pop(key)}
            if task.get("ansible.builtin.include_role", {}).get("name") == "systemd_jobs":
                task["fixture_operation"] = {"module": "include_role", "options": task.pop("ansible.builtin.include_role")}
            if isinstance(task.get("ansible.builtin.include_tasks"), dict) and task["ansible.builtin.include_tasks"].get(
                "file", ""
            ).startswith("sub_tasks/"):
                include = task["ansible.builtin.include_tasks"]
                if include["file"] not in {
                    "sub_tasks/backup_prerequisites.yml",
                    "sub_tasks/install.yml",
                    "sub_tasks/swarm.yml",
                    "sub_tasks/install/etcd.yml",
                    "sub_tasks/install/patroni.yml",
                    "sub_tasks/backup_remote_setup.yml",
                }:
                    task["fixture_operation"] = {"module": "include_tasks", "options": task.pop("ansible.builtin.include_tasks")}

    for role in fixture_roles:
        # Only PostgreSQL's entry point and the moved dependency file are selected.
        paths = list((roles / role / "tasks").rglob("*.yml")) + list((roles / role / "handlers").glob("*.yml"))
        for path in paths:
            tasks = yaml.safe_load(path.read_text())
            instrument(tasks)
            path.write_text(yaml.safe_dump(tasks, sort_keys=False))
    plugins = tmp_path / "action_plugins"
    plugins.mkdir()
    (plugins / "fixture_operation.py").write_text("""from ansible.plugins.action import ActionBase
from ansible.template import trust_as_template
import base64, fnmatch, hashlib, json
from pathlib import Path
class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        v = task_vars
        module, options = self._task.args['module'], self._task.args['options'] or {}
        record = {'module': module, 'options': options, 'environment': self._task.environment,
                  'no_log': self._task.no_log, 'diff': self._task.diff}
        if module == 'copy' and options.get('src') == 'docker-iptables-compat.conf':
            record['content'] = (Path(v['role_path']) / 'files' / options['src']).read_text()
        if module == 'copy' and options.get('dest') == '/etc/docker/daemon.json':
            record['content'] = options['content']
        if module == 'template' and options.get('src') in (
            'rootful-dns.conf.j2', 'shared.network.j2', 'patroni.yml.j2', 'etcd.default.j2', 'patroni-rpm.conf.j2',
            'postgres_exporter.service.j2', 'password.j2', 'environment.j2'):
            expression = "{{ lookup('ansible.builtin.template', " + repr(options['src']) + ") }}"
            content = self._templar.template(trust_as_template(expression))
            if self._task.no_log and options['src'] in ('password.j2', 'environment.j2'):
                record['content_digest'] = hashlib.sha256(content.encode()).hexdigest()
            else:
                record['content'] = content
        with open(v['fixture_record'], 'a') as output:
            output.write(json.dumps(record, default=str) + '\\n')
        state_path = Path(v['fixture_state'])
        state = json.loads(state_path.read_text())
        result = {'changed': False, 'rc': 0, 'stdout': '', 'stdout_lines': []}
        if module in ('apt', 'dnf') and options.get('name') == 'qemu-guest-agent' and v.get('fixture_guest_agent_failure', False):
            return dict(result, failed=True, rc=1, msg='fixture-agent-failure')
        if module == 'dnf' and str(options.get('name', '')).startswith('kernel-modules-extra-'):
            if v.get('fixture_kernel_package_unavailable', False):
                return dict(result, failed=True, rc=1, msg='fixture-running-kernel-package-unavailable')
            # Reproduce Ansible DNF4's older-NEVRA no-op when a newer kernel
            # supplement is installed. An exact uname-r capability must still
            # install its missing provider alongside that newer version.
            skip_older = (options.get('use_backend') == 'dnf4'
                          and v.get('fixture_newer_kernel_supplement', False)
                          and 'uname-r = ' not in options['name'])
            skip_older = skip_older or v.get('fixture_kernel_install_noop', False)
            result['changed'] = not state.get('docker_addrtype_available', False) and not skip_older
            if not self._play_context.check_mode and not skip_older:
                state['docker_addrtype_available'] = True
        if module == 'setup':
            if 'ansible_selinux' in options.get('filter', []):
                result['ansible_facts'] = {'ansible_selinux': v.get('fixture_selinux', {'status': 'enabled'}),
                    'ansible_distribution': v['fixture_facts']['distribution'], 'ansible_pkg_mgr': v['fixture_facts']['pkg_mgr']}
            else:
                result['ansible_facts'] = dict(v['fixture_facts'])
                if 'selinux' in options.get('gather_subset', []):
                    result['ansible_facts']['selinux'] = v.get('fixture_selinux', {'status': 'enabled'})
        elif module == 'service_facts':
            result['ansible_facts'] = {'services': v.get('fixture_services', {})}
            if state.get('docker_started', False):
                result['ansible_facts']['services']['docker.service'] = {'state': 'running'}
        elif module in ('community.general.sefcontext', 'community.general.serestorecon'):
            key = 'policy_contexts' if module.endswith('sefcontext') else 'restored_contexts'
            value = options.get('target', options.get('path'))
            result['changed'] = value not in state.get(key, [])
            if not self._play_context.check_mode and result['changed']:
                state.setdefault(key, []).append(value)
        elif module == 'package_facts':
            result['ansible_facts'] = {'packages': v.get('fixture_packages', {})}
        elif module == 'template' or (module == 'copy' and 'content' in record):
            if options.get('dest') == '/etc/docker/daemon.json' and v.get('fixture_docker_config_invalid', False):
                return dict(result, failed=True, msg='fixture-dockerd-validation-failed')
            if 'content' in record or 'content_digest' in record:
                path = options['dest']
                content = record.get('content', record.get('content_digest'))
                previous = state.get('podman_files', {}).get(path, v.get('fixture_files', {}).get(path))
                result['changed'] = previous != content
                if not self._play_context.check_mode:
                    state.setdefault('podman_files', {})[path] = content
            else:
                result['changed'] = v.get('fixture_nic_artifacts_changed', False)
        elif module == 'copy' and options.get('dest', '').endswith('/postgres_exporter'):
            path, source = options['dest'], options['src']
            result['changed'] = state.get('exporter_binaries', {}).get(path) != source
            if not self._play_context.check_mode:
                state.setdefault('exporter_binaries', {})[path] = source
        elif module == 'find':
            if str(options.get('paths', '')).startswith(('/etc/containers', '/root/.config/containers')):
                files = dict(v.get('fixture_files', {}), **state.get('podman_files', {}))
                result['files'] = [{'path': path, 'isreg': path not in v.get('fixture_symlinks', []),
                                    'islnk': path in v.get('fixture_symlinks', [])}
                                   for path in files if str(Path(path).parent) == options['paths']
                                   and fnmatch.fnmatch(Path(path).name, options['patterns'])
                                   and Path(path).name != options.get('excludes')]
            else:
                result['files'] = [{'path': '/etc/systemd/system/multi-user.target.wants/' + unit} for unit in v.get('fixture_nic_enabled', [])]
        elif module == 'file' and options.get('path', '').endswith('/40-skynet-docker-compat.conf') and options.get('state') == 'absent':
            result['changed'] = options['path'] in state.get('podman_files', {})
            if not self._play_context.check_mode:
                state.get('podman_files', {}).pop(options['path'], None)
        elif module == 'stat':
            path = options['path']
            exists = v.get('fixture_ostree', False) if path == '/run/ostree-booted' else False
            if path == v.get('system_swap_path', '/swapfile'):
                exists = state.get('exists', False)
            if path in v.get('fixture_files', {}):
                exists = True
            if path in state.get('podman_files', {}):
                exists = True
            directory = path in v.get('fixture_directories', [])
            exists = exists or directory
            result['stat'] = {'exists': exists, 'isdir': directory, 'islnk': path in v.get('fixture_symlinks', []), 'isreg': exists and not directory,
                              'path': path, 'executable': exists, 'size': state.get('size', 2048 * 1024 * 1024)}
        elif module == 'slurp':
            path = options['src']
            content = state['podman_files'][path] if path in state.get('podman_files', {}) else v['fixture_files'][path]
            result['content'] = base64.b64encode(content.encode()).decode()
        elif module == 'uri':
            if options['url'].endswith('/info') and 'fixture_docker_selinux' in v:
                enabled = state.get('docker_selinux_active', v['fixture_docker_selinux'])
                result.update(status=200, json={'SecurityOptions': ['name=selinux'] if enabled else [],
                              'Swarm': {'LocalNodeState': v.get('fixture_docker_swarm_state', 'inactive')}})
            elif options['url'].endswith('/containers/json'):
                result.update(status=200, json=v.get('fixture_docker_containers', []))
            elif options.get('method') == 'POST':
                state['swarm_active'] = True
                state['swarm_role'] = 'manager' if 'tags_swarm_manager' in v['group_names'] else 'worker'
                state['swarm_availability'] = options['body']['Availability']
                result.update(status=200, changed=True)
            elif '/nodes/' in options['url']:
                result.update(status=404 if v.get('fixture_other_swarm', False) else 200,
                              json={'Spec': {'Role': state.get('swarm_role', v.get('fixture_swarm_existing_role', 'manager'))}})
            else:
                # This one-host fixture serves both delegated primary and local requests.
                primary = sum(json.loads(line)['module'] == 'uri'
                              for line in Path(v['fixture_record']).read_text().splitlines()) == 1
                active = primary or state.get('swarm_active', False)
                result.update(status=200, json={'Swarm': {
                    'LocalNodeState': 'active' if active else 'inactive',
                    'ControlAvailable': primary or state.get('swarm_role') == 'manager',
                    'NodeID': 'fixture-node' if active else ''}})
        elif module == 'command':
            argv = options['argv']
            command = argv[0]
            if argv[:3] == ['systemctl', 'show', 'docker.service']:
                result['stdout'] = v.get('fixture_docker_exec_start',
                    '{ path=/usr/bin/dockerd ; argv[]=/usr/bin/dockerd -H fd:// --containerd=/run/containerd/containerd.sock ; }')
            elif command == 'printenv':
                result['stdout'] = v.get('fixture_provider_environment', '')
                result['rc'] = 0 if result['stdout'] else 1
            elif command == 'ps':
                result['stdout'] = '\\n'.join(str(uid) for uid in v.get('fixture_conmon_uids', []))
                result['rc'] = 0 if result['stdout'] else 1
            elif command in ('iptables', 'ip6tables', 'iptables-save', 'ip6tables-save', 'iptables-restore', 'ip6tables-restore'):
                backend = 'legacy' if command == v.get('fixture_legacy_compat_tool') else 'nf_tables'
                result['stdout'] = command + ' v1.8.11 (' + backend + ')'
            elif argv[:3] == ['systemctl', 'show', 'patroni.service']:
                config = v.get('fixture_patroni_unit_config', '/etc/patroni/patroni.yml')
                fragment = v.get('fixture_patroni_unit_fragment', '/usr/lib/systemd/system/patroni.service')
                environment = v.get('fixture_patroni_unit_environment', 'MALLOC_ARENA_MAX=1')
                envfiles = v.get('fixture_patroni_unit_envfiles', '/etc/patroni_env.conf (ignore_errors=yes)')
                passed = v.get('fixture_patroni_unit_pass_environment', '')
                result['stdout_lines'] = [
                    'ExecStart={ path=/usr/bin/patroni ; argv[]=/usr/bin/patroni ' + config + ' ; ignore_errors=no ; }',
                    'FragmentPath=' + fragment, 'Environment=' + environment,
                    'PassEnvironment=' + passed, 'EnvironmentFiles=' + envfiles]
                result['stdout'] = '\\n'.join(result['stdout_lines'])
            elif command.endswith('/restic') and argv[-1] == 'version':
                result['stdout'] = v.get('fixture_restic_version', 'restic 0.19.1 compiled with fixture')
            elif command.endswith('/postgres') and argv[-1] == '--version':
                result['stdout'] = 'postgres (PostgreSQL) ' + v.get('fixture_postgres_version', '18.6')
            elif command == 'readlink':
                result['stdout'] = v.get('fixture_realpaths', {}).get(argv[-1], argv[-1])
            elif command == 'docker' and 'join-token' in argv:
                result['stdout'] = 'synthetic-test-token'
            elif command == 'podman':
                if 'info' in argv:
                    result['stdout'] = json.dumps(v.get('fixture_podman_host', {
                        'networkBackend': 'netavark', 'cgroupVersion': 'v2',
                        'security': {'rootless': False, 'selinuxEnabled': True},
                        'networkBackendInfo': {'path': '/fixture/netavark', 'dns': {'path': '/fixture/aardvark-dns'}}}))
                elif 'exists' in argv:
                    result['rc'] = v.get('fixture_network_exists_rc', 0 if state.get('podman_network', False) else 1)
                elif 'inspect' in argv:
                    result['stdout'] = json.dumps(v.get('fixture_network', [{'name': v['podman_shared_network_name'],
                        'driver': 'bridge', 'dns_enabled': True, 'internal': False}]))
                elif 'ps' in argv:
                    result['stdout_lines'] = v.get('fixture_dns_users', [])
                    result['stdout'] = '\\n'.join(result['stdout_lines'])
                else:
                    result['stdout'] = v.get('fixture_podman_version', 'podman version 5.4.2')
                    result['rc'] = 0 if result['stdout'] else 2
            elif command == 'modinfo':
                available = state.get('docker_addrtype_available', not v.get('fixture_addrtype_missing', False))
                result['rc'] = 0 if available else 1
                result['stdout'] = '/fixture/xt_addrtype.ko.xz' if available else ''
            elif command == 'rpm':
                available = state.get('docker_addrtype_available', False)
                kernel_package = 'kernel-modules-extra-' + v['ansible_facts']['kernel']
                # rpm --whatprovides indexes the literal provide name. It does
                # not parse DNF's "capability = version" dependency expression.
                exact_package = argv == ['rpm', '-q', kernel_package]
                result['rc'] = 0 if available and exact_package else 1
                result['stdout'] = kernel_package if available and exact_package else 'no matching installed package'
            elif command == 'timeout':
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
        elif module == 'systemd_service' and options.get('name', '').endswith('-network.service'):
            result['changed'] = not state.get('podman_network', False)
            if not self._play_context.check_mode:
                state['podman_network'] = True
        elif module == 'systemd_service' and options.get('name') == 'docker.service' and 'fixture_docker_selinux' in v:
            active = state.get('docker_started', v.get('fixture_services', {}).get('docker.service', {}).get('state') == 'running')
            result['changed'] = options['state'] == 'restarted' or not active
            if not self._play_context.check_mode:
                state['docker_started'] = True
                if options['state'] == 'restarted' or not active:
                    config = state.get('podman_files', {}).get('/etc/docker/daemon.json', v.get('fixture_files', {}).get('/etc/docker/daemon.json', '{}'))
                    state['docker_selinux_active'] = json.loads(config).get('selinux-enabled', False) and not v.get('fixture_docker_capability_failure', False)
        state_path.write_text(json.dumps(state))
        return result
""")
    config = tmp_path / "ansible.cfg"
    config.write_text((REPO / "ansible/bootstrap.cfg").read_text().replace("[defaults]", f"[defaults]\naction_plugins = {plugins}"))
    state_file = tmp_path / "state.json"
    record = tmp_path / "calls.jsonl"

    def run(
        *,
        distro="Rocky",
        backend=None,
        tags="system_packages",
        overrides=None,
        state=None,
        check=False,
        main=False,
        role="system",
        inventory_groups=None,
        tasks_from=None,
    ):
        record.unlink(missing_ok=True)
        if state is not None or not state_file.exists():
            state_file.write_text(json.dumps(state or {}))
        facts = {
            "distribution": distro,
            "system": "Linux",
            "architecture": "x86_64",
            "distribution_release": "noble",
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
        if role in {"docker", "podman", "postgres_exporter"}:
            variables.update(
                {
                    "services_controller_inventory_group": "tags_service_controller",
                    "services_storage_inventory_group": "tags_service_storage",
                    "services_plex_host": "localhost",
                    "services_log_root": "/fixture/logs",
                    "services_public_zone": "example.invalid",
                    "services_internal_zone": "int.example.invalid",
                    "services_lan_cidr": "198.51.100.0/24",
                    "services_private_https_port": 8443,
                }
            )
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
                            **{
                                group: {"hosts": {"localhost": {}}}
                                for group in (
                                    "tags_docker",
                                    "tags_docker_install",
                                    "tags_swarm",
                                    "tags_podman",
                                    "tags_podman_install",
                                    "tags_service_controller",
                                    "tags_service_storage",
                                    *variables.get("fixture_inventory_groups", []),
                                )
                                if role in {"docker", "podman", "postgres_exporter"}
                            },
                            **(inventory_groups or {}),
                        }
                    }
                }
            )
        )
        plays = [
            {
                "hosts": "localhost",
                "connection": "local",
                "gather_facts": False,
                "pre_tasks": [{"name": "Gather fixture facts", "fixture_operation": {"module": "setup", "options": {}}, "tags": "always"}],
                **(
                    {
                        "tasks": [
                            {
                                "name": "Exercise the selected role entry point",
                                "ansible.builtin.include_role": {"name": role, "tasks_from": tasks_from},
                            }
                        ]
                    }
                    if tasks_from
                    else {"roles": [role]}
                ),
            }
        ]
        if main:
            plays = yaml.safe_load((REPO / "ansible/playbook.yml").read_text())
            for play in plays:
                instrument(play.get("tasks", []))
            shutil.copytree(REPO / "ansible/tasks", tmp_path / "tasks", dirs_exist_ok=True)
            shutil.copytree(REPO / "ansible/filter_plugins", tmp_path / "filter_plugins", dirs_exist_ok=True)
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
                "ANSIBLE_INJECT_FACT_VARS": "false",
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
    result, calls, _ = system_run(
        distro="Ubuntu",
        role="postgres",
        tags=tag,
        overrides={
            "ansible_facts": {
                "distribution": "Ubuntu",
                "distribution_version": "24.04",
                "distribution_major_version": "24",
                "pkg_mgr": "apt",
                "system": "Linux",
                "service_mgr": "systemd",
            }
        },
    )
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
