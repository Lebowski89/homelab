"""Native operator contexts without systemd, hosts, sockets or real credentials."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from ansible.errors import AnsibleFilterError

ROOT = Path(__file__).resolve().parents[2]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OP = load("ansible/operator/mgt-operator.py", "native_operator_test")
COMMON = load("ansible/roles/service_common/filter_plugins/service_common.py", "native_operator_common")
FW = load("ansible/roles/service_firewall/files/mgt-firewall.py", "native_operator_firewall")


@pytest.mark.parametrize("enabled", [None, "true", "false", 0, 1, [], {}])
def test_operator_interpreter_requires_strict_opt_in(enabled):
    with pytest.raises(AnsibleFilterError, match="strict boolean"):
        COMMON.service_common_postgres_operator_interpreter(enabled, sys.executable)


def test_operator_interpreter_preserves_default_and_selects_only_prepared_wrapper():
    assert COMMON.service_common_postgres_operator_interpreter(False, sys.executable) == sys.executable
    assert COMMON.service_common_postgres_operator_interpreter(True, "auto") == "/usr/local/libexec/skynet-mgt-operator/postgres-python"


@pytest.mark.parametrize("change", [None, "missing", "unowned", "symlink", "writable", "inactive", "wrong-cgroup", "wrong-fragment"])
def test_persistent_slice_is_required_and_inspection_does_not_repair_it(tmp_path, monkeypatch, change):
    monkeypatch.setattr(OP, "SYSTEMD", tmp_path)
    path = tmp_path / OP.SLICES["controller"]
    if change != "missing":
        path.write_text("foreign unit\n" if change == "unowned" else OP.MARKER + "[Slice]\n")
        path.chmod(0o666 if change == "writable" else 0o644)
    if change == "symlink":
        other = tmp_path / "other"
        other.write_text(OP.MARKER)
        path.unlink()
        path.symlink_to(other)
    # Model root-owned unit metadata even when CI's filesystem user is unprivileged.
    original = Path.lstat

    def owned_info(value, *args, **kwargs):
        info = original(value, *args, **kwargs)
        return SimpleNamespace(st_mode=info.st_mode, st_uid=0, st_gid=0)

    monkeypatch.setattr(Path, "lstat", owned_info)
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        state = "inactive" if change == "inactive" else "active"
        cgroup = "/system.slice/shared.slice" if change == "wrong-cgroup" else "/" + path.name
        fragment = "/run/systemd/transient/" + path.name if change == "wrong-fragment" else str(path)
        return SimpleNamespace(returncode=0, stdout=f"ActiveState={state}\nControlGroup={cgroup}\nFragmentPath={fragment}\n")

    monkeypatch.setattr(OP.subprocess, "run", run)
    before = sorted(tmp_path.iterdir())
    if change:
        with pytest.raises((OSError, ValueError)):
            OP.require_slice("controller")
    else:
        assert OP.require_slice("controller") == path.name
    assert sorted(tmp_path.iterdir()) == before
    assert all(argv[:2] == ["/usr/bin/systemctl", "show"] for argv in calls)


def test_nonroot_execution_is_rejected_before_any_manager_request(monkeypatch):
    monkeypatch.setattr(OP.os, "getuid", lambda: 1000)
    monkeypatch.setattr(OP.os, "geteuid", lambda: 0)
    monkeypatch.setattr(OP, "require_slice", lambda context: pytest.fail("manager queried before root validation"))
    with pytest.raises(ValueError, match="after become"):
        OP.launch("controller", [OP.PYTHON])


@pytest.mark.integration
@pytest.mark.parametrize("context", ["controller", "recovery"])
def test_launcher_preserves_pipe_output_and_exit_without_secret_environment(tmp_path, context):
    fake = tmp_path / "systemd-run"
    fake.write_text(
        "#!/usr/bin/python3\nimport os,sys\n"
        "assert '--pipe' in sys.argv and '--wait' in sys.argv and '--collect' in sys.argv\n"
        "assert '--property=User=root' in sys.argv and '--property=UMask=0077' in sys.argv\n"
        "assert not any(value.startswith('--setenv') for value in sys.argv)\n"
        "command=sys.argv[sys.argv.index('--')+1:]\nos.execv(command[0],command)\n"
    )
    fake.chmod(0o755)
    source = (ROOT / "ansible/operator/mgt-operator.py").read_text().replace('"/usr/bin/systemd-run"', repr(str(fake)))
    # Only external privilege/installed-unit prerequisites are simulated.
    source = source.replace(
        'if __name__ == "__main__":',
        'require_root = lambda: None\nrequire_slice = lambda context: SLICES[context]\nif __name__ == "__main__":',
    )
    if context == "controller":
        program = tmp_path / "postgres-python"
        source = source.replace('PYTHON = "/opt/ansible/ansible-venv/bin/python"', "PYTHON = " + repr(sys.executable))
        arguments = [sys.executable, str(program)]
        payload = "import sys\nprint('NONPRODUCTION-pipelined-module')\nsys.exit(7)\n"
    else:
        program = tmp_path / "native-launcher.py"
        arguments = [sys.executable, str(program), "recovery", sys.executable, "-c", "import sys; print(sys.stdin.read()); sys.exit(9)"]
        payload = "NONPRODUCTION-recovery-input"
    program.write_text(source)
    result = subprocess.run(arguments, input=payload, text=True, capture_output=True)
    assert result.returncode == (7 if context == "controller" else 9), result.stderr
    assert "NONPRODUCTION" in result.stdout and result.stderr == ""


@pytest.mark.parametrize("wrong", [None, "unrelated-root", "socket-uid"])
def test_probe_checks_actual_socket_uid_and_cgroup_without_database_payload(monkeypatch, capsys, wrong):
    monkeypatch.setattr(OP.os, "getuid", lambda: 0)
    monkeypatch.setattr(OP.os, "geteuid", lambda: 0)
    calls = []

    class Connection:
        family = OP.socket.AF_INET

        def __enter__(self):
            return self

        def __exit__(self, *args):
            calls.append("closed")

        def fileno(self):
            return 4242

        def getsockname(self):
            return ("192.0.2.48", 32000)

        def getpeername(self):
            return ("192.0.2.48", 5432)

        def send(self, *args):
            pytest.fail("database payload sent")

        def recv(self, *args):
            pytest.fail("database payload read")

    def connect(*args, **kwargs):
        calls.append("connected")
        return Connection()

    monkeypatch.setattr(OP.socket, "create_connection", connect)
    original_fstat = os.fstat
    monkeypatch.setattr(OP.os, "fstat", lambda fd: SimpleNamespace(st_ino=77) if fd == 4242 else original_fstat(fd))

    def read(path, *args, **kwargs):
        if str(path) == "/proc/self/cgroup":
            parent = "system.slice/unrelated.service" if wrong == "unrelated-root" else OP.SLICES["controller"] + "/job.service"
            return "0::/" + parent + "\n"
        assert str(path) == "/proc/self/net/tcp"
        uid = 1004 if wrong == "socket-uid" else 0
        return f"HEADER\n0: LOCAL REMOTE 01 QUEUE TIMER RETRANS {uid} TIMEOUT 77\n"

    monkeypatch.setattr(Path, "read_text", read)
    if wrong:
        with pytest.raises(ValueError):
            OP.probe("controller", "192.0.2.48", 5432, 0)
        assert capsys.readouterr().out == ""
        if wrong == "unrelated-root":
            assert calls == []
    else:
        OP.probe("controller", "192.0.2.48", 5432, 0)
        evidence = json.loads(capsys.readouterr().out)
        assert evidence["socket_uid"] == evidence["process_uid"] == 0
        assert evidence["binding_cgroup"] == OP.SLICES["controller"]
        assert evidence["cgroup"] == OP.SLICES["controller"] + "/job.service"
        assert calls == ["connected", "closed"]


@pytest.mark.parametrize("context", ["controller", "recovery"])
def test_firewall_native_binding_remains_uid_and_exact_persistent_slice(context):
    binding = {
        "kind": "local",
        "phase": "native",
        "account": "root",
        "uid": 0,
        "cgroup": OP.SLICES[context],
        "verified": False,
        "restart_verified": False,
    }
    policy = {
        "schema": 1,
        "backend": "nf_tables",
        "inventory_host": "manager",
        "inventory_address": "192.0.2.48",
        "inputs_verified": False,
        "endpoints": [{"port": 5432, "callers": [context]}],
        "callers": {context: [binding]},
    }
    FW.validate_policy(policy, require_verified=False)
    assert FW.caller_match(binding, 4, True) == ["-m", "owner", "--uid-owner", "0", "-m", "cgroup", "--path", OP.SLICES[context]]
    with pytest.raises(ValueError, match="inputs_verified"):
        FW.validate_policy(policy)


@pytest.mark.integration
@pytest.mark.parametrize(
    "opt_in,check_mode", [(False, False), (True, False), (True, True), ("controller-default", False), ("missing-wrapper", False)]
)
def test_actual_delegated_postgres_module_enters_only_opted_context(tmp_path, opt_in, check_mode):
    """Execute the real task/normalizer with a fake PG module and manager only."""
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    collections = fixture / "collections/ansible_collections/community/postgresql/plugins/modules"
    collections.mkdir(parents=True)
    (collections / "postgresql_db.py").write_text(
        "from ansible.module_utils.basic import AnsibleModule\nimport os\n"
        "m=AnsibleModule(argument_spec={key:{'type':'str','no_log':key in ['login_user','login_password']} "
        "for key in ['login_host','login_port','login_user','login_password','name','state']})\n"
        "m.exit_json(changed=False,native_context=os.environ.get('FIXTURE_CONTEXT','outside'),destination=m.params['login_host'])\n"
    )
    filters = fixture / "filters"
    filters.mkdir()
    controller_default = isinstance(opt_in, str)
    missing_wrapper = opt_in == "missing-wrapper"
    enabled = controller_default or opt_in
    installation = fixture / "operator"
    installation.mkdir(mode=0o755)
    wrapper = installation / "postgres-python"
    filter_source = (ROOT / "ansible/roles/service_common/filter_plugins/service_common.py").read_text()
    (filters / "service_common.py").write_text(
        filter_source.replace("/usr/local/libexec/skynet-mgt-operator/postgres-python", str(wrapper))
    )
    fake = fixture / "systemd-run"
    receipt = fixture / "systemd-request"
    fake.write_text(
        "#!/usr/bin/python3\nimport os,sys\n"
        "assert '--slice=skynet_pg_prepare.slice' in sys.argv\n"
        "assert '--property=User=root' in sys.argv\n"
        f"open({str(receipt)!r},'w').write('controller module only')\n"
        "os.environ['FIXTURE_CONTEXT']='controller'\n"
        "args=sys.argv[sys.argv.index('--')+1:]\nos.execv(args[0],args)\n"
    )
    fake.chmod(0o755)
    source = (ROOT / "ansible/operator/mgt-operator.py").read_text()
    source = source.replace('"/usr/bin/systemd-run"', repr(str(fake)))
    source = source.replace('PYTHON = "/opt/ansible/ansible-venv/bin/python"', "PYTHON = " + repr(sys.executable))
    source = source.replace(
        'if __name__ == "__main__":',
        'require_root = lambda: None\nrequire_slice = lambda context: SLICES[context]\nif __name__ == "__main__":',
    )
    (installation / "mgt-operator.py").write_text(source)
    (installation / "mgt-operator.py").chmod(0o755)
    if not missing_wrapper:
        wrapper.symlink_to("mgt-operator.py")
    prerequisites = (
        (ROOT / "ansible/roles/service_common/tasks/postgres_operator.yml")
        .read_text()
        .replace("/usr/local/libexec/skynet-mgt-operator", str(installation))
    )
    prerequisites = yaml.safe_load(prerequisites)
    # Inspect real fixture files; model root ownership without changing CI users.
    for block in prerequisites:
        for child in block.get("block", []):
            if "ansible.builtin.stat" in child:
                child["fixture_stat"] = child.pop("ansible.builtin.stat")
    (fixture / "postgres_operator.yml").write_text(yaml.safe_dump(prerequisites))
    actions = fixture / "actions"
    actions.mkdir()
    (actions / "fixture_stat.py").write_text(
        "from ansible.plugins.action import ActionBase\n"
        "class ActionModule(ActionBase):\n"
        " def run(self,tmp=None,task_vars=None):\n"
        "  r=self._execute_module(module_name='ansible.builtin.stat',module_args=self._task.args,task_vars=task_vars)\n"
        "  if r.get('stat',{}).get('exists'): r['stat'].update(uid=0,gid=0)\n"
        "  return r\n"
    )
    tasks = yaml.safe_load((ROOT / "ansible/roles/service_common/tasks/postgres.yml").read_text())
    tasks[-1]["register"] = "fixture_result"
    tasks.append(
        {
            "name": "Assert module context and delegated destination",
            "ansible.builtin.assert": {
                "that": [
                    "fixture_result.skipped | default(false)"
                    if check_mode
                    else "fixture_result.results[0].native_context == '" + ("controller" if enabled else "outside") + "'",
                    "ansible_check_mode or fixture_result.results[0].destination == '192.0.2.48'",
                    "ansible_python_interpreter == '" + sys.executable + "'",
                ]
            },
        }
    )
    # Become is inherited exactly as in playbook.yml; fake sudo never changes
    # actual privileges or touches PAM/systemd.
    sudo = fixture / "sudo"
    sudo.write_text(
        "#!/usr/bin/python3\nimport os,sys\nargs=sys.argv[1:]\n"
        "while args and args[0].startswith('-'):\n"
        " flag=args.pop(0)\n if flag in ['-u','-p']: args.pop(0)\n"
        "os.execvp(args[0],args)\n"
    )
    sudo.chmod(0o755)
    inventory = fixture / "inventory.yml"
    inventory.write_text(
        yaml.safe_dump(
            {
                "all": {
                    "hosts": {
                        host: {
                            "ansible_connection": "local",
                            "ansible_python_interpreter": sys.executable,
                            "ansible_become_exe": str(sudo),
                            "local_ip": ip,
                            **(
                                {
                                    "service_common_postgres_operator_context": yaml.safe_load(
                                        (ROOT / "ansible/host_vars/mgt.yml").read_text()
                                    )["service_common_postgres_operator_context"]
                                }
                                if controller_default and host == "manager"
                                else ({"service_common_postgres_operator_context": False} if controller_default else {})
                            ),
                        }
                        for host, ip in [("manager", "192.0.2.48"), ("worker", "192.0.2.20")]
                    }
                }
            }
        )
    )
    playbook = fixture / "play.yml"
    playbook.write_text(
        yaml.safe_dump(
            [
                {
                    "name": "Offline delegated preparation regression",
                    "hosts": "worker",
                    "become": True,
                    "gather_facts": False,
                    "vars": {
                        "service_common_controller_host": "manager",
                        **({} if controller_default else {"service_common_postgres_operator_context": opt_in}),
                        "service_common_service": {"postgres": {"enable": True, "databases": ["fixture_db"]}},
                        "service_common_infisical_values": {
                            "postgres_user": "NONPRODUCTION-user",
                            "postgres_pass": "NONPRODUCTION-password",
                        },
                    },
                    "tasks": tasks,
                }
            ]
        )
    )
    config = fixture / "ansible.cfg"
    config.write_text(
        f"[defaults]\ninventory={inventory}\nfilter_plugins={filters}\nvars_plugins_enabled=\n"
        f"collections_path={fixture / 'collections'}:{ROOT / 'ansible/collections'}\n"
        f"local_tmp={fixture / 'tmp'}\naction_plugins={actions}\ninject_facts_as_vars=false\n[connection]\npipelining=True\n[inventory]\nenable_plugins=yaml\n"
    )
    argv = [str(Path(sys.executable).parent / "ansible-playbook"), str(playbook)] + (["--check"] if check_mode else [])
    result = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, env={**os.environ, "ANSIBLE_CONFIG": str(config)})
    output = result.stdout + result.stderr
    assert "NONPRODUCTION-password" not in output
    if missing_wrapper:
        assert result.returncode != 0 and "requires the existing root-owned" in output
        assert not receipt.exists()
    else:
        assert result.returncode == 0, output
        assert "failed=0" in result.stdout
        assert receipt.exists() is bool(enabled and not check_mode)


def shell_fixture(tmp_path):
    """Redirect persistent paths and external manager/ownership prerequisites only."""
    executable_dir = tmp_path / "bin"
    executable_dir.mkdir()
    journal = tmp_path / "operations"
    systemd = tmp_path / "systemd"
    systemd.mkdir()
    install_dir = tmp_path / "installed"
    manager = executable_dir / "systemctl"
    manager.write_text(
        "#!/usr/bin/python3\nimport sys\nfrom pathlib import Path\n"
        f"with open({str(journal)!r},'a') as f: f.write(' '.join(sys.argv[1:])+'\\n')\n"
        "if sys.argv[1]=='show':\n"
        f" print('ActiveState=active\\nControlGroup=/'+sys.argv[2]+'\\nFragmentPath='+{str(systemd)!r}+'/'+sys.argv[2])\n"
    )
    manager.chmod(0o755)
    installer = executable_dir / "install"
    installer.write_text(
        "#!/usr/bin/python3\nimport os,sys\nargs=sys.argv[1:]\n"
        "for flag in ['-o','-g']:\n"
        " if flag in args: i=args.index(flag); del args[i:i+2]\n"
        "os.execv('/usr/bin/install',['/usr/bin/install',*args])\n"
    )
    installer.chmod(0o755)

    def adapt(source):
        return (
            source.replace("/usr/local/libexec/skynet-mgt-operator", str(install_dir))
            .replace("/etc/systemd/system", str(systemd))
            .replace("/usr/bin/systemctl", str(manager))
            .replace('test "$EUID" = 0', "true")
            .replace("info.st_uid == info.st_gid == 0", f"info.st_uid == {os.getuid()} and info.st_gid == {os.getgid()}")
            .replace(
                "alias.lstat().st_uid == alias.lstat().st_gid == 0",
                f"alias.lstat().st_uid == {os.getuid()} and alias.lstat().st_gid == {os.getgid()}",
            )
            .replace("info.st_uid != 0 or info.st_gid != 0", f"info.st_uid != {os.getuid()} or info.st_gid != {os.getgid()}")
        )

    return adapt, {**os.environ, "PATH": str(executable_dir) + ":" + os.environ["PATH"]}, journal, systemd, install_dir


@pytest.mark.integration
@pytest.mark.parametrize("mode", ["check", "collision-check", "collision-apply", "apply-twice"])
def test_operator_preparation_read_only_collisions_and_idempotent_state(tmp_path, mode):
    adapt, environment, journal, systemd, install_dir = shell_fixture(tmp_path)
    sources = tmp_path / "sources"
    sources.mkdir()
    for path in (ROOT / "ansible/operator").iterdir():
        if path.is_file():
            (sources / path.name).write_text(adapt(path.read_text()))
    if mode.startswith("collision"):
        (systemd / OP.SLICES["recovery"]).write_text("foreign unit\n")
    before = {str(path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    argv = ["/bin/bash", str(sources / "prepare-native-operator.sh")]
    if mode.endswith("check"):
        argv.append("--check")
    result = subprocess.run(argv, text=True, capture_output=True, env=environment)
    if mode.startswith("collision"):
        assert result.returncode != 0 and "unowned destination" in result.stderr
    else:
        assert result.returncode == 0, result.stdout + result.stderr
    if mode != "apply-twice":
        assert {str(path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before
        assert not journal.exists() and not install_dir.exists()
    else:
        installed = {str(path): path.read_bytes() for base in [systemd, install_dir] for path in base.iterdir()}
        again = subprocess.run(argv, text=True, capture_output=True, env=environment)
        assert again.returncode == 0, again.stdout + again.stderr
        assert installed == {str(path): path.read_bytes() for base in [systemd, install_dir] for path in base.iterdir()}
        assert (install_dir / "postgres-python").is_symlink()
        assert journal.read_text().count("enable --now skynet_pg_prepare.slice skynet_pg_recovery.slice") == 2
        assert "restart" not in journal.read_text()


@pytest.mark.integration
@pytest.mark.parametrize("failure", [None, "unrelated-root", "union", "validate", "apply"])
def test_offline_policy_union_restore_is_scoped_and_preserves_failures(tmp_path, failure):
    adapt, environment, journal, _, _ = shell_fixture(tmp_path)
    handoff = tmp_path / "handoff"
    handoff.mkdir()
    (handoff / "policy-before.json").write_text('{"fixture":"NONPRODUCTION"}\n')
    (handoff / "policy-before.py").write_text(
        "import sys\n"
        f"with open({str(journal)!r},'a') as f: f.write('policy '+sys.argv[1]+'\\n')\n"
        f"sys.exit(19 if sys.argv[1]=={failure!r} else 0)\n"
    )
    (handoff / "haproxy-cutover.py").write_text(
        "import sys\n"
        f"with open({str(journal)!r},'a') as f: f.write('verify policy union\\n')\n"
        "assert sys.argv[1]=='rollback-policy'\n"
        f"sys.exit(19 if {failure!r}=='union' else 0)\n"
    )
    cgroup = tmp_path / "cgroup"
    cgroup.write_text(
        "0::/" + ("system.slice/unrelated.service" if failure == "unrelated-root" else "skynet_pg_recovery.slice/job.service") + "\n"
    )
    persistent = tmp_path / "policy"
    persistent.mkdir()
    script = tmp_path / "rollback.sh"
    source = adapt((ROOT / "ansible/operator/haproxy-policy-rollback.sh").read_text())
    script.write_text(source.replace("/proc/self/cgroup", str(cgroup)).replace("/etc/skynet-mgt-firewall", str(persistent)))
    result = subprocess.run(["/bin/bash", str(script), str(handoff)], text=True, capture_output=True, env=environment)
    if failure == "unrelated-root":
        assert result.returncode != 0 and "recovery context" in result.stderr
        assert not journal.exists()
    elif failure:
        assert result.returncode == 19
        assert not list(persistent.iterdir())
        assert journal.read_text() == "verify policy union\n" + (
            ""
            if failure == "union"
            else (
                "policy validate\n"
                if failure == "validate"
                else "policy validate\nstop skynet-mgt-firewall-reconcile.timer\nstop skynet-mgt-firewall-reconcile.service\npolicy apply\n"
            )
        )
    else:
        assert result.returncode == 0, result.stderr
        assert journal.read_text() == (
            "verify policy union\npolicy validate\nstop skynet-mgt-firewall-reconcile.timer\nstop skynet-mgt-firewall-reconcile.service\n"
            "policy apply\nstart skynet-mgt-firewall-reconcile.timer\npolicy check\n"
        )
        assert (persistent / "policy.json").read_bytes() == (handoff / "policy-before.json").read_bytes()
        assert (persistent / "policy.json").stat().st_mode & 0o777 == 0o600
