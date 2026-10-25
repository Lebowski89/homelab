"""Exercise guest-side installation and the existing role without any live hosts."""

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

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / "ansible/roles/tailscale_bootstrap/tasks/main.yml"
INSTALL = next(
    task
    for task in yaml.safe_load(TASKS.read_text())
    if "https://tailscale.com/install.sh" in str(task.get("vars", {}).get("tailscale_bootstrap_exec_argv", []))
)
ANSIBLE = Path(sys.executable).with_name("ansible-playbook")

# Every package, network, service and guest-agent operation is intercepted. The
# guest PATH contains only these mocks plus mktemp/rm, confined to fixture paths.
MOCK_COMMAND = r"""
import json
import os
import shlex
import stat
import subprocess
import sys
import time
from pathlib import Path

root = Path(os.environ["MOCK_GUEST"])
config_path = root / "config.json"
config = json.loads(config_path.read_text())
command = Path(sys.argv[0]).name
args = sys.argv[1:]
with (root / "commands.jsonl").open("a") as log:
    log.write(json.dumps({"command": command, "args": args,
                          "debian_frontend": os.environ.get("DEBIAN_FRONTEND")}) + "\n")

def guest_arguments(argv):
    if argv[:2] == ["/bin/sh", "-c"]:
        for path in ["/etc/os-release", "/run/ostree-booted",
                     "/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt",
                     "/tmp/tailscale-install.", "/run/tailscale-auth."]:
            argv[2] = argv[2].replace(path, str(root) + path)
    return argv

if command == "ssh":
    assert args[args.index("--") + 1] == "fixtureuser@192.0.2.10", args
    assert "BatchMode=yes" in args and "StrictHostKeyChecking=yes" in args
    assert "ForwardAgent=no" in args and "-T" in args
    if config.get("ssh_exit"):
        sys.exit(config["ssh_exit"])
    remote = shlex.split(args[-1])
    assert remote[:6] == ["sudo", "-n", "--", "/usr/bin/timeout", "--signal=TERM", "--kill-after=5"], remote
    assert 0 < int(remote[6][:-1]) <= 600
    remote[7:] = guest_arguments(remote[7:])
    os.execvpe(remote[0], remote, {**os.environ, "PATH": str(root / "bin")})
elif command == "sudo":
    assert args[:2] == ["-n", "--"], args
    if config.get("sudo_exit"):
        sys.exit(config["sudo_exit"])
    os.execv(args[2], args[2:])
elif command == "qm":
    if args[:2] == ["guest", "cmd"] and args[-1] == "ping":
        sys.exit(0)
    assert args[:2] == ["guest", "exec"] and args[2] == "99100", args
    assert "--timeout" in args and int(args[args.index("--timeout") + 1]) <= 600
    if config.get("qga_exit"):
        sys.exit(config["qga_exit"])
    guest_args = guest_arguments(args[args.index("--") + 1:])
    environment = {**os.environ, "PATH": str(root / "bin")}
    stdin = sys.stdin.read() if "--pass-stdin" in args else None
    result = subprocess.run(guest_args, env=environment, input=stdin, capture_output=True, text=True, timeout=10)
    envelope = {"exited": 1, "exitcode": result.returncode, "out-data": result.stdout, "err-data": result.stderr}
    print(json.dumps(config.get("qga_envelope", envelope)))
elif command in ("apt-get", "dnf"):
    if config.get("package_exit") and args[0] in config.get("package_fail_stages", ["update", "install"]):
        sys.exit(config["package_exit"])
    if "ca-certificates" in args and not config.get("leave_ca_missing"):
        bundle = root / config["bundle"]
        bundle.parent.mkdir(parents=True, exist_ok=True)
        bundle.write_text("NONPRODUCTION CA bundle fixture\n")
    if "curl" in args:
        if not (root / "bin/curl").exists():
            (root / "bin/curl").symlink_to(root / "mock-command")
        config["curl_working"] = True
        config_path.write_text(json.dumps(config))
elif command == "curl":
    if args == ["--version"]:
        print("curl (curl-minimal fixture)")
        sys.exit(0 if config["curl_working"] else 127)
    if config.get("download_exit"):
        sys.exit(config["download_exit"])
    assert "https://tailscale.com/install.sh" in args
    assert "-k" not in args and "--insecure" not in args
    Path(args[args.index("-o") + 1]).write_text("#!/bin/sh\nmock-installer\n")
elif command == "mock-installer":
    time.sleep(config.get("installer_delay", 0))
    if not (root / "bin/tailscale").exists():
        (root / "bin/tailscale").symlink_to(root / "mock-command")
    sys.exit(config.get("installer_exit", 0))
elif command == "tailscale":
    if args == ["status", "--json"]:
        print(json.dumps({"BackendState": config.get("backend", "Running")}))
    elif args == ["ip", "-4"]:
        print(config.get("tailscale_ip", "100.64.0.10"))
    elif args[0] == "up":
        key_file = Path(next(arg.split("file:", 1)[1] for arg in args if arg.startswith("--auth-key=file:")))
        assert key_file.read_text() == "NONPRODUCTION_STDIN_FIXTURE"
        assert stat.S_IMODE(key_file.stat().st_mode) == 0o600
        config["backend"] = "Running"
        config_path.write_text(json.dumps(config))
        # Deliberately echo the stand-in to verify no_log protects derived output.
        print(key_file.read_text())
        sys.exit(config.get("auth_exit", 0))
    else:
        raise AssertionError(args)
elif command != "systemctl":
    raise AssertionError(command)
"""


class Guest:
    def __init__(self, root, os_id="rocky", *, curl=True, ca=True, installed=False, **options):
        self.root = root
        self.bin = root / "bin"
        self.bin.mkdir()
        (root / "etc").mkdir()
        (root / "run").mkdir()
        (root / "tmp").mkdir()
        (root / "etc/os-release").write_text(f'ID={os_id}\nVERSION_ID="test-release"\n')
        self.manager = "apt-get" if os_id in ("debian", "ubuntu") else "dnf"
        self.bundle = "etc/ssl/certs/ca-certificates.crt" if self.manager == "apt-get" else "etc/pki/tls/certs/ca-bundle.crt"
        config = {"bundle": self.bundle, "curl_working": bool(curl), **options}
        (root / "config.json").write_text(json.dumps(config))
        mock = root / "mock-command"
        mock.write_text(f"#!{sys.executable}\n{MOCK_COMMAND}")
        mock.chmod(0o755)
        commands = ["qm", "ssh", "sudo", self.manager, "mock-installer", "systemctl"]
        if curl:
            commands.append("curl")
        if installed:
            commands.append("tailscale")
        for command in commands:
            (self.bin / command).symlink_to(mock)
        for command in ["mktemp", "rm", "timeout", "cat"]:
            (self.bin / command).symlink_to(shutil.which(command))
        if ca:
            bundle = root / self.bundle
            bundle.parent.mkdir(parents=True, exist_ok=True)
            bundle.write_text("NONPRODUCTION CA bundle fixture\n")
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("ANSIBLE_") and key != "DEBIAN_FRONTEND"}
        self.env.update(MOCK_GUEST=str(root), PATH=f"{self.bin}:/usr/bin:/bin")

    def commands(self, *names):
        path = self.root / "commands.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        return [row for row in rows if not names or row["command"] in names]

    def install(self):
        environment = Environment(undefined=StrictUndefined)
        argv = [
            environment.from_string(str(value)).render(tailscale_bootstrap_vmid_effective=99100)
            for value in INSTALL["vars"]["tailscale_bootstrap_exec_argv"]
        ]
        argv = ["qm", "guest", "exec", "99100", "--timeout", "600", "--", *argv]
        result = subprocess.run(argv, env=self.env, capture_output=True, text=True, timeout=15, check=True)
        return json.loads(result.stdout)

    def role(self, *, check=False, transport=None, overrides=None, extra_vars=None, prompt=False, tags=None, hypervisor_identity=False):
        if not ANSIBLE.exists():
            pytest.skip("ansible-playbook is unavailable in the test environment")
        config = self.root / "ansible.cfg"
        config.write_text("[defaults]\nretry_files_enabled = False\n")
        guest_config = {"vmid": 99100, "hostname": "offline-guest"}
        if transport is not None:
            guest_config["transport"] = transport
        if transport == "ssh":
            guest_config.update(ssh_host="192.0.2.10", ssh_user="fixtureuser")
        guest_config.update(overrides or {})
        host = "hypervisor-fixture" if hypervisor_identity else "localhost"
        inventory = "localhost,"
        if hypervisor_identity:
            inventory_path = self.root / "inventory.yml"
            inventory_path.write_text(
                yaml.safe_dump(
                    {
                        "all": {
                            "hosts": {
                                host: {
                                    "ansible_host": "192.0.2.20",
                                    "ansible_user": "hypervisor-user",
                                    "ansible_connection": "ssh",
                                    "ansible_become": True,
                                    "ansible_become_user": "hypervisor-admin",
                                }
                            }
                        }
                    }
                )
            )
            inventory = str(inventory_path)
        play = self.root / "play.yml"
        play.write_text(
            yaml.safe_dump(
                [
                    {
                        "name": "Offline Tailscale role regression",
                        "hosts": host,
                        "connection": "local",
                        "gather_facts": False,
                        "become": False,
                        "vars": {
                            "ansible_python_interpreter": sys.executable,
                            "ansible_facts": {"distribution": "Debian", "os_family": "Debian"},
                            "tailscale_bootstrap_guest": "offline-guest",
                            "tailscale_bootstrap_guests": {"offline-guest": guest_config},
                            "tailscale_bootstrap_guest_agent_retries": 1,
                            "tailscale_bootstrap_guest_agent_delay": 0,
                        },
                        "tasks": [{"ansible.builtin.import_tasks": str(TASKS), "tags": "tailscale_bootstrap"}],
                    }
                ]
            )
        )
        environment = {
            **self.env,
            "ANSIBLE_CONFIG": str(config),
            "ANSIBLE_LOCAL_TEMP": str(self.root / "ansible-local"),
            "ANSIBLE_REMOTE_TEMP": str(self.root / "ansible-remote"),
            "ANSIBLE_NOCOLOR": "1",
            "ANSIBLE_FILTER_PLUGINS": str(ROOT / "ansible/filter_plugins"),
        }
        if prompt:
            actions = self.root / "actions"
            actions.mkdir()
            (actions / "offline_pause.py").write_text(
                "from pathlib import Path\n"
                "from ansible.plugins.action import ActionBase\n"
                "class ActionModule(ActionBase):\n"
                "    def run(self, tmp=None, task_vars=None):\n"
                "        assert self._task.args.get('echo') is False\n"
                f"        Path({str(self.root / 'prompted')!r}).touch()\n"
                "        return {'changed': False, 'user_input': 'NONPRODUCTION_STDIN_FIXTURE'}\n"
            )
            environment["ANSIBLE_ACTION_PLUGINS"] = str(actions)
            # Mock only terminal input. Preserve the real prompt's condition,
            # echo setting, register and privacy flags, and all command tasks.
            tasks = yaml.safe_load(TASKS.read_text())
            for task in tasks:
                if "ansible.builtin.pause" in task:
                    task["offline_pause"] = task.pop("ansible.builtin.pause")
                if "ansible.builtin.include_tasks" in task:
                    task["ansible.builtin.include_tasks"]["file"] = str(TASKS.parent / "execute.yml")
            prompted_tasks = self.root / "prompted-tasks.yml"
            prompted_tasks.write_text(yaml.safe_dump(tasks))
            plays = yaml.safe_load(play.read_text())
            plays[0]["tasks"][0]["ansible.builtin.import_tasks"] = str(prompted_tasks)
            play.write_text(yaml.safe_dump(plays))
        return subprocess.run(
            [
                str(ANSIBLE),
                "-i",
                inventory,
                str(play),
                *(["--check"] if check else []),
                *(["-e", json.dumps(extra_vars)] if extra_vars else []),
                *(["--tags", tags] if tags else []),
            ],
            cwd=self.root,
            env=environment,
            input="",
            capture_output=True,
            text=True,
            timeout=60,
        )


@pytest.mark.parametrize("os_id", ["debian", "ubuntu", "fedora", "rocky"])
def test_guest_os_selects_prerequisite_manager(tmp_path, os_id):
    guest = Guest(tmp_path, os_id, curl=False, ca=False)
    result = guest.install()
    assert result["exitcode"] == 0, result
    packages = guest.commands("apt-get", "dnf")
    assert {row["command"] for row in packages} == {guest.manager}
    assert packages[-1]["args"][-2:] == ["curl", "ca-certificates"]
    assert all(row["debian_frontend"] == ("noninteractive" if guest.manager == "apt-get" else None) for row in packages)
    assert [row["args"][0] for row in packages] == (["update", "install"] if guest.manager == "apt-get" else ["install"])
    assert len(guest.commands("mock-installer")) == 1
    assert not list((tmp_path / "tmp").iterdir())


@pytest.mark.parametrize("os_id", ["debian", "ubuntu", "fedora", "rocky"])
def test_existing_curl_including_curl_minimal_needs_no_packages(tmp_path, os_id):
    guest = Guest(tmp_path, os_id)
    assert guest.install()["exitcode"] == 0
    assert not guest.commands("apt-get", "dnf")
    assert len(guest.commands("mock-installer")) == 1


def test_nonworking_curl_is_not_treated_as_ready(tmp_path):
    guest = Guest(tmp_path, "ubuntu", curl_working=False)
    assert guest.install()["exitcode"] == 0
    assert guest.commands("apt-get")[-1]["args"][-1] == "curl"


@pytest.mark.parametrize("os_id", ["debian", "rocky"])
@pytest.mark.parametrize(("curl", "ca", "needed"), [(False, True, "curl"), (True, False, "ca-certificates")])
def test_only_missing_prerequisites_are_installed(tmp_path, os_id, curl, ca, needed):
    guest = Guest(tmp_path, os_id, curl=curl, ca=ca)
    assert guest.install()["exitcode"] == 0
    install = guest.commands(guest.manager)[-1]["args"]
    assert install[-1] == needed
    assert ("curl" in install) == (not curl)
    assert ("ca-certificates" in install) == (not ca)
    assert not set(install) & {"--allowerasing", "--nobest", "swap", "upgrade", "dist-upgrade"}


@pytest.mark.parametrize("os_id", ["debian", "rocky"])
def test_missing_package_manager_is_rejected_before_changes(tmp_path, os_id):
    guest = Guest(tmp_path, os_id, curl=False, ca=False)
    (guest.bin / guest.manager).unlink()
    result = guest.install()
    assert result["exitcode"] != 0
    assert os_id in result["err-data"] and "prerequisite validation" in result["err-data"]
    assert guest.manager in result["err-data"]
    assert not guest.commands("apt-get", "dnf", "mock-installer", "curl")


@pytest.mark.parametrize("os_id", ["debian", "rocky"])
def test_installed_but_nonexecutable_manager_stops_before_changes(tmp_path, os_id):
    guest = Guest(tmp_path, os_id, curl=False, ca=False)
    manager = guest.bin / guest.manager
    manager.unlink()
    manager.write_text("#!/bin/sh\nexit 99\n")
    manager.chmod(0o644)

    result = guest.install()

    assert manager.exists() and not os.access(manager, os.X_OK)
    assert result["exitcode"] == 1
    assert f"{os_id} test-release" in result["err-data"]
    assert f"prerequisite validation ({guest.manager})" in result["err-data"]
    assert f"PATH={guest.bin}" in result["err-data"]
    assert not guest.commands("apt-get", "dnf", "mock-installer", "curl")
    assert not list((tmp_path / "tmp").iterdir())


@pytest.mark.parametrize("unsupported", ["alpine", "missing-release", "ostree-booted", "ostree-version"])
def test_unsupported_guests_are_rejected_before_changes(tmp_path, unsupported):
    guest = Guest(tmp_path, "alpine" if unsupported == "alpine" else "fedora", curl=False, ca=False)
    if unsupported == "missing-release":
        (tmp_path / "etc/os-release").unlink()
    elif unsupported == "ostree-booted":
        (tmp_path / "run/ostree-booted").touch()
    elif unsupported == "ostree-version":
        with (tmp_path / "etc/os-release").open("a") as release:
            release.write('OSTREE_VERSION="test-version"\n')
    result = guest.install()
    assert result["exitcode"] != 0
    assert "unknown" in result["err-data"] if unsupported == "missing-release" else "OS validation" in result["err-data"]
    assert not guest.commands("apt-get", "dnf", "curl", "mock-installer")


@pytest.mark.parametrize(
    ("os_id", "options", "stage", "exitcode"),
    [
        ("debian", {"package_exit": 17}, "APT metadata refresh", 17),
        ("ubuntu", {"package_exit": 19, "package_fail_stages": ["install"]}, "APT prerequisite installation", 19),
        ("rocky", {"package_exit": 18}, "DNF prerequisite installation", 18),
        ("rocky", {"leave_ca_missing": True}, "prerequisite verification", 1),
        ("rocky", {"download_exit": 22}, "HTTPS installer download", 22),
        ("ubuntu", {"installer_exit": 42}, "official Tailscale installer", 42),
    ],
)
def test_installation_failure_preserves_stage_exitcode_and_cleanup(tmp_path, os_id, options, stage, exitcode):
    guest = Guest(tmp_path, os_id, curl=False, ca=False, **options)
    result = guest.install()
    assert result["exited"] == 1 and result["exitcode"] == exitcode
    assert f"{os_id} test-release" in result["err-data"] and stage in result["err-data"]
    if options.get("leave_ca_missing"):
        assert str(tmp_path / guest.bundle) in result["err-data"]
    assert not list((tmp_path / "tmp").iterdir())
    assert bool(guest.commands("mock-installer")) == (stage == "official Tailscale installer")


def test_installed_connected_rerun_neither_installs_nor_prompts(tmp_path):
    guest = Guest(tmp_path, installed=True)
    # OS detection is unnecessary on an already installed/connected rerun.
    (tmp_path / "etc/os-release").unlink()
    (guest.bin / guest.manager).unlink()
    result = guest.role()
    assert result.returncode == 0, result.stdout + result.stderr
    assert not guest.commands("apt-get", "dnf", "curl", "mock-installer")
    assert not list((tmp_path / "tmp").iterdir())
    assert [row["args"] for row in guest.commands("tailscale")] == [["status", "--json"], ["status", "--json"], ["ip", "-4"]]
    assert guest.commands("systemctl")[-1]["args"] == ["enable", "--now", "tailscaled"]


def test_guest_failure_envelope_stops_role_before_service_or_authentication(tmp_path):
    guest = Guest(tmp_path, "rocky", installer_exit=42)
    result = guest.role()
    assert result.returncode == 2, result.stdout + result.stderr
    assert "rocky test-release" in result.stdout and "official Tailscale installer" in result.stdout
    assert not guest.commands("systemctl", "tailscale")
    assert not list((tmp_path / "tmp").iterdir())


def test_check_mode_refuses_before_any_guest_operation(tmp_path):
    guest = Guest(tmp_path)
    result = guest.role(check=True)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "not ansible_check_mode" in result.stdout
    assert not guest.commands()


def test_ssh_connected_rerun_uses_only_workstation_ssh(tmp_path):
    guest = Guest(tmp_path, installed=True)
    result = guest.role(transport="ssh", tags="tailscale_bootstrap")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not guest.commands("qm", "apt-get", "dnf", "curl", "mock-installer")
    assert guest.commands("ssh") and guest.commands("sudo")
    assert [row["args"] for row in guest.commands("tailscale")] == [["status", "--json"], ["status", "--json"], ["ip", "-4"]]


@pytest.mark.parametrize("transport", [None, "ssh"])
@pytest.mark.parametrize("enable_ssh", [True, False])
def test_authentication_stdin_and_cleanup_are_private(tmp_path, transport, enable_ssh):
    guest = Guest(tmp_path, installed=True, backend="NeedsLogin")
    result = guest.role(transport=transport, prompt=True, overrides={"enable_ssh": enable_ssh})
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "prompted").exists()
    assert "NONPRODUCTION_STDIN_FIXTURE" not in result.stdout + result.stderr
    assert "NONPRODUCTION_STDIN_FIXTURE" not in json.dumps(guest.commands())
    assert not list((tmp_path / "run").iterdir())
    up = [row for row in guest.commands("tailscale") if row["args"][0] == "up"]
    assert len(up) == 1 and ("--ssh" in up[0]["args"]) == enable_ssh
    assert not guest.commands("qm") if transport == "ssh" else not guest.commands("ssh")


@pytest.mark.parametrize("os_id", ["debian", "ubuntu", "fedora", "rocky"])
def test_ssh_installs_using_guest_os_not_hypervisor_facts(tmp_path, os_id):
    guest = Guest(tmp_path, os_id, curl=False, ca=False)
    result = guest.role(transport="ssh")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not guest.commands("qm")
    assert {row["command"] for row in guest.commands("apt-get", "dnf")} == {guest.manager}
    assert len(guest.commands("mock-installer")) == 1


@pytest.mark.parametrize("options", [{"ssh_exit": 255}, {"sudo_exit": 1}, {"installer_exit": 42}])
def test_ssh_failure_never_falls_back_or_authenticates(tmp_path, options):
    guest = Guest(tmp_path, **options)
    result = guest.role(transport="ssh")
    assert result.returncode == 2, result.stdout + result.stderr
    assert not guest.commands("qm", "tailscale")
    assert not list((tmp_path / "tmp").iterdir())


@pytest.mark.parametrize("check", [False, True])
def test_invalid_ssh_inputs_or_check_mode_cannot_connect(tmp_path, check):
    guest = Guest(tmp_path, installed=True)
    result = guest.role(transport="ssh", check=check, overrides={} if check else {"ssh_host": "localhost"})
    assert result.returncode == 2, result.stdout + result.stderr
    assert not guest.commands()


@pytest.mark.parametrize(
    "overrides",
    [
        {"transport": "auto"},
        {"ssh_host": ""},
        {"ssh_host": None},
        {"ssh_host": "999.2.3.4"},
        {"ssh_host": "127.0.0.1"},
        {"ssh_host": "guest.tailnet.example"},
        {"ssh_user": "-oProxyCommand=bad"},
        {"ssh_port": True},
        {"ssh_port": "22"},
        {"ssh_port": 65536},
    ],
)
def test_ssh_configuration_is_validated_before_operations(tmp_path, overrides):
    guest = Guest(tmp_path)
    result = guest.role(transport="ssh", overrides=overrides)
    assert result.returncode == 2, result.stdout + result.stderr
    assert not guest.commands()


def test_qga_failure_never_falls_back_to_ssh(tmp_path):
    guest = Guest(tmp_path, qga_exit=29)
    result = guest.role()
    assert result.returncode == 2, result.stdout + result.stderr
    assert guest.commands("qm") and not guest.commands("ssh", "sudo", "tailscale", "mock-installer")


@pytest.mark.parametrize("envelope", [[], {"exited": 0}, {"exited": 1, "exitcode": 0, "out-data": "unusable"}])
def test_invalid_qga_envelopes_cannot_advance(tmp_path, envelope):
    guest = Guest(tmp_path, qga_envelope=envelope)
    result = guest.role()
    assert result.returncode == 2, result.stdout + result.stderr
    assert not guest.commands("ssh", "sudo", "mock-installer", "tailscale")


def test_ssh_uses_workstation_identity_instead_of_hypervisor_credentials(tmp_path):
    guest = Guest(tmp_path, installed=True)
    result = guest.role(transport="ssh", hypervisor_identity=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert guest.commands("ssh") and not guest.commands("qm")
    assert "hypervisor-user" not in json.dumps(guest.commands())
    assert "hypervisor-admin" not in json.dumps(guest.commands())


def test_ssh_authentication_failure_cleans_up_without_exposing_stdin(tmp_path):
    guest = Guest(tmp_path, installed=True, backend="NeedsLogin", auth_exit=23)
    result = guest.role(transport="ssh", prompt=True)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "NONPRODUCTION_STDIN_FIXTURE" not in result.stdout + result.stderr + json.dumps(guest.commands())
    assert not list((tmp_path / "run").iterdir())
    assert not guest.commands("qm")


def test_ssh_remote_timeout_cleans_up_installer(tmp_path):
    guest = Guest(tmp_path, installer_delay=3)
    result = guest.role(transport="ssh", extra_vars={"tailscale_bootstrap_exec_timeout": 1})
    assert result.returncode == 2, result.stdout + result.stderr
    assert not list((tmp_path / "tmp").iterdir())
    assert not guest.commands("qm", "tailscale")


def test_ssh_requires_final_tailscale_ip(tmp_path):
    guest = Guest(tmp_path, installed=True, tailscale_ip="")
    result = guest.role(transport="ssh")
    assert result.returncode == 2, result.stdout + result.stderr
    assert guest.commands("tailscale")[-1]["args"] == ["ip", "-4"]
    assert not guest.commands("qm")
