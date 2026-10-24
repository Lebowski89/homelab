"""Exercise credential setup only in temporary directories with synthetic input."""

from __future__ import annotations

import errno
import fcntl
import importlib.util
import io
import json
import os
import pty
import pwd
import select
import shutil
import stat
import subprocess
import sys
import termios
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / "ansible/roles/workstation"
ANSIBLE = str(Path(sys.executable).with_name("ansible-playbook"))
SPEC = importlib.util.spec_from_file_location("credential_files", ROLE / "library/workstation_credential_files.py")
FILES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FILES)
VAULT = "NONPRODUCTION-existing-vault-pass"
BECOME = "NONPRODUCTION-managed-sudo-pass"
LOCAL = "NONPRODUCTION-local-provisioning-pass"


@pytest.mark.integration
@pytest.mark.parametrize("tmp", [None, "/unused-legacy-action-tmp"])
def test_action_accepts_legacy_tmp_without_forwarding_it(monkeypatch, tmp):
    from ansible.plugins.action import ActionBase

    spec = importlib.util.spec_from_file_location("credential_action", ROLE / "action_plugins/workstation_credentials.py")
    action_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(action_module)
    action = object.__new__(action_module.ActionModule)
    action._task = SimpleNamespace(args={}, check_mode=True)
    variables = {"synthetic": True}

    def base_run(self, *, task_vars):
        assert task_vars is variables
        return {}

    monkeypatch.setattr(ActionBase, "run", base_run)
    monkeypatch.setattr(action, "_execute_module", lambda **kwargs: {"changed": True, "missing": ["vault", "become"]})
    assert action.run(tmp, variables) == {"changed": True, "missing": ["vault", "become"], "created": []}


@pytest.fixture
def parameters(tmp_path):
    account = pwd.getpwuid(os.getuid())
    if account.pw_uid == 0:
        pytest.skip("credential setup deliberately requires a non-root workstation account")
    directory = tmp_path / "private directory"
    return {
        "directory": str(directory),
        "vault_file": str(directory / "vault password"),
        "become_file": str(directory / "sudo password"),
        "owner": account.pw_name,
        "operation": "apply",
        "values": {"vault": VAULT, "become": BECOME},
    }


@pytest.fixture
def managed_home(parameters, tmp_path, monkeypatch):
    home = tmp_path / "managed account/home"
    home.mkdir(parents=True, mode=0o751)
    account = pwd.getpwnam(parameters["owner"])
    substitute = SimpleNamespace(pw_uid=account.pw_uid, pw_gid=account.pw_gid, pw_dir=str(home))
    monkeypatch.setattr(FILES.pwd, "getpwnam", lambda owner: substitute)
    return home


def metadata(destination):
    info = destination.stat()
    return info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)


@pytest.mark.parametrize("destination", ["root", "home", "ancestor"])
@pytest.mark.parametrize("operation,check_mode", [("inspect", False), ("apply", True), ("apply", False)])
def test_private_directory_rejects_home_root_and_ancestors_without_mutation(
    parameters, managed_home, tmp_path, monkeypatch, destination, operation, check_mode
):
    parameters["directory"] = str({"root": Path("/"), "home": managed_home, "ancestor": managed_home.parent}[destination])
    parameters["operation"] = operation
    before = {entry: metadata(entry) for entry in (tmp_path, *tmp_path.rglob("*"))}

    def forbidden(*args, **kwargs):
        pytest.fail("unsafe directory configurations must fail before filesystem mutation")

    for name in ("mkdir", "fchown", "fchmod", "chown", "chmod", "link"):
        monkeypatch.setattr(FILES.os, name, forbidden)
    with pytest.raises(ValueError, match="root|home"):
        FILES.configure(parameters, check_mode)
    assert {entry: metadata(entry) for entry in (tmp_path, *tmp_path.rglob("*"))} == before


def test_exclusive_creation_and_metadata_only_preservation(parameters, monkeypatch):
    result = FILES.configure(parameters, False)
    assert result["created"] == ["vault", "become"]
    directory = Path(parameters["directory"])
    assert metadata(directory) == (os.getuid(), os.getgid(), 0o700)
    before = {}
    for kind in ("vault", "become"):
        path = Path(parameters[kind + "_file"])
        info = path.stat()
        assert path.read_text() == parameters["values"][kind] + "\n"
        assert (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (os.getuid(), os.getgid(), 0o600)
        before[kind] = (info.st_ino, info.st_mtime_ns)

    def forbidden(*args, **kwargs):
        pytest.fail("preservation must not read password contents")

    monkeypatch.setattr(FILES.os, "read", forbidden)
    monkeypatch.setattr(FILES.os, "pread", forbidden)
    import builtins

    targets = {parameters[kind + "_file"] for kind in ("vault", "become")}
    for api, name in ((builtins, "open"), (io, "open")):
        original = getattr(api, name)

        def guard(file, *args, _original=original, **kwargs):
            if isinstance(file, (str, os.PathLike)) and str(file) in targets:
                forbidden()
            return _original(file, *args, **kwargs)

        monkeypatch.setattr(api, name, guard)
    assert FILES.configure({**parameters, "values": {}}, False) == {"changed": False, "missing": [], "created": []}
    for kind in before:
        info = Path(parameters[kind + "_file"]).stat()
        assert (info.st_ino, info.st_mtime_ns) == before[kind]


def test_file_appearing_after_inspection_is_never_replaced(parameters, monkeypatch):
    link = FILES.os.link

    def race(source, destination, **kwargs):
        if destination == Path(parameters["vault_file"]).name:
            Path(parameters["vault_file"]).write_text("NONPRODUCTION-concurrent-existing-file")
        return link(source, destination, **kwargs)

    monkeypatch.setattr(FILES.os, "link", race)
    assert FILES.configure(parameters, False)["created"] == ["become"]
    assert Path(parameters["vault_file"]).read_text() == "NONPRODUCTION-concurrent-existing-file"
    assert not list(Path(parameters["directory"]).glob(".workstation-credential-*"))


@pytest.mark.parametrize("kind", ["directory", "vault_file", "become_file"])
def test_unsafe_destinations_rejected_before_any_creation(parameters, tmp_path, kind):
    target = tmp_path / "unrelated"
    target.write_text("NONPRODUCTION-do-not-touch")
    destination = Path(parameters[kind])
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(target)
    if kind == "become_file":
        # An invalid second destination must not even secure an existing first
        # file or its dedicated directory during preflight validation.
        first = Path(parameters["vault_file"])
        first.write_text(VAULT + "\n")
        first.chmod(0o640)
        first.parent.chmod(0o750)
        before = (metadata(first), metadata(first.parent))
    with pytest.raises(ValueError, match="Unsafe"):
        FILES.configure(parameters, False)
    assert target.read_text() == "NONPRODUCTION-do-not-touch"
    if kind != "become_file":
        assert not Path(parameters["become_file"]).exists()
    else:
        assert destination.is_symlink()
        assert (metadata(first), metadata(first.parent)) == before
        assert first.read_text() == VAULT + "\n"


def test_check_mode_and_invalid_values_never_write(parameters):
    assert FILES.configure(parameters, True)["missing"] == ["vault", "become"]
    for value in ("", "   ", "invalid\npassword", None):
        with pytest.raises(ValueError, match="missing or invalid"):
            FILES.configure({**parameters, "values": {"vault": value, "become": BECOME}}, False)
    assert not Path(parameters["directory"]).exists()


def test_existing_unreadable_files_are_secured_without_content_access(parameters, monkeypatch):
    FILES.configure(parameters, False)
    for kind in ("vault", "become"):
        Path(parameters[kind + "_file"]).chmod(0o000)

    def forbidden(*args, **kwargs):
        pytest.fail("password contents must not be read")

    monkeypatch.setattr(FILES.os, "read", forbidden)
    assert FILES.configure({**parameters, "values": {}}, False)["changed"]
    for kind in ("vault", "become"):
        assert stat.S_IMODE(Path(parameters[kind + "_file"]).stat().st_mode) == 0o600


def test_separate_configured_password_parents_are_honored(parameters, tmp_path):
    shared = tmp_path / "existing shared ancestor"
    shared.mkdir(mode=0o755)
    before = {entry: metadata(entry) for entry in (tmp_path, shared)}
    parameters["vault_file"] = str(shared / "separate vault/nested/password")
    parameters["become_file"] = str(shared / "separate sudo/password")
    for operation, check_mode in (("inspect", False), ("apply", True)):
        assert FILES.configure({**parameters, "operation": operation}, check_mode) == {
            "changed": True,
            "missing": ["vault", "become"],
            "created": [],
        }
        assert list(shared.iterdir()) == []
        assert not Path(parameters["directory"]).exists()
        assert {entry: metadata(entry) for entry in before} == before
    assert FILES.configure(parameters, False)["changed"]
    for kind in ("vault", "become"):
        target = Path(parameters[kind + "_file"])
        assert target.read_text() == parameters["values"][kind] + "\n"
    created = [Path(parameters["directory"]), *(entry for entry in shared.rglob("*") if entry.is_dir())]
    assert all(metadata(entry) == (os.getuid(), os.getgid(), 0o700) for entry in created)
    assert {entry: metadata(entry) for entry in before} == before
    assert FILES.configure({**parameters, "values": {}}, False) == {"changed": False, "missing": [], "created": []}


def test_existing_home_and_alternate_parents_keep_metadata_and_check_plan(parameters, managed_home, tmp_path, monkeypatch):
    shared = tmp_path / "shared passwords"
    shared.mkdir()
    shared.chmod(0o775)
    private = Path(parameters["directory"])
    private.mkdir(mode=0o700)
    parameters["vault_file"] = str(managed_home / "vault password")
    parameters["become_file"] = str(shared / "sudo password")
    parents = {entry: metadata(entry) for entry in (tmp_path, managed_home.parent, managed_home, shared)}
    parent_ids = {(entry.stat().st_dev, entry.stat().st_ino) for entry in parents}
    for name in ("fchown", "fchmod"):
        original = getattr(FILES.os, name)

        def protect_existing_parents(descriptor, *args, _original=original):
            info = os.fstat(descriptor)
            assert (info.st_dev, info.st_ino) not in parent_ids
            return _original(descriptor, *args)

        monkeypatch.setattr(FILES.os, name, protect_existing_parents)

    def forbidden(*args, **kwargs):
        pytest.fail("inspection and check mode must never mutate the filesystem")

    def plan(changed, missing):
        before = {entry: metadata(entry) for entry in (private, *parents)}
        files = {
            entry: (metadata(entry), entry.stat().st_mtime_ns)
            for entry in (managed_home / "vault password", shared / "sudo password")
            if entry.exists()
        }
        for operation, check_mode in (("inspect", False), ("apply", True)):
            with monkeypatch.context() as guard:
                for name in ("mkdir", "fchown", "fchmod", "chown", "chmod", "link", "unlink"):
                    guard.setattr(FILES.os, name, forbidden)
                assert FILES.configure({**parameters, "operation": operation}, check_mode) == {
                    "changed": changed,
                    "missing": missing,
                    "created": [],
                }
            assert {entry: metadata(entry) for entry in before} == before
            for entry, snapshot in files.items():
                assert (metadata(entry), entry.stat().st_mtime_ns) == snapshot
            assert all(Path(parameters[kind + "_file"]).exists() == (kind not in missing) for kind in ("vault", "become"))

    plan(True, ["vault", "become"])
    assert FILES.configure(parameters, False) == {"changed": True, "missing": [], "created": ["vault", "become"]}
    assert {entry: metadata(entry) for entry in parents} == parents
    plan(False, [])
    assert FILES.configure({**parameters, "values": {}}, False) == {"changed": False, "missing": [], "created": []}

    # Check-mode metadata repairs must match apply without treating a shared
    # parent's different mode as drift, before or after the repair.
    private.chmod(0o750)
    Path(parameters["vault_file"]).chmod(0o640)
    plan(True, [])
    assert FILES.configure({**parameters, "values": {}}, False)["changed"]
    assert metadata(private) == (os.getuid(), os.getgid(), 0o700)
    for kind in ("vault", "become"):
        target = Path(parameters[kind + "_file"])
        assert metadata(target) == (os.getuid(), os.getgid(), 0o600)
        assert target.read_text() == parameters["values"][kind] + "\n"
    assert {entry: metadata(entry) for entry in parents} == parents
    plan(False, [])


def test_explicit_selection_is_required_at_both_include_layers():
    tasks = yaml.safe_load((ROLE / "tasks/main.yml").read_text())
    setup = next(task for task in tasks if task.get("ansible.builtin.include_tasks", {}).get("file") == "credentials.yml")
    assert "workstation_credentials" in setup["tags"]
    assert "workstation_credentials" in setup["ansible.builtin.include_tasks"]["apply"]["tags"]
    assert setup["when"] == "'workstation_credentials' in ansible_run_tags"
    assert tasks.index(setup) < next(i for i, task in enumerate(tasks) if task["name"] == "Workstation | Configure automation tooling")
    secret = next(task for task in yaml.safe_load((ROLE / "tasks/credentials.yml").read_text()) if "block" in task)["block"][0]
    assert secret["no_log"] is True and secret["diff"] is False


@pytest.fixture
def credentials(tmp_path, parameters):
    directory = tmp_path / "operator checkout/ansible"
    directory.mkdir(parents=True)
    shutil.copytree(ROLE, directory / "roles/workstation", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "ansible/tasks", directory / "tasks")
    for filename in ("playbook.yml", "bootstrap.cfg"):
        shutil.copyfile(ROOT / "ansible" / filename, directory / filename)
    # All non-credential installation payloads are harmless sentinels.
    for filename in ("tools", "validate", "timezone", "packages", "development", "vscode", "shell", "desktop"):
        (directory / f"roles/workstation/tasks/{filename}.yml").write_text(
            yaml.safe_dump([{"name": "SYNTHETIC WORKSTATION PAYLOAD", "ansible.builtin.debug": {"msg": filename}}])
        )
    host = os.uname().nodename.split(".")[0]
    hosts = directory / "host_vars"
    hosts.mkdir()
    (hosts / (host + ".yml")).write_text(
        yaml.safe_dump(
            {
                "workstation_user": parameters["owner"],
                "workstation_tools_enabled": True,
                "workstation_secrets_path": parameters["directory"],
                "workstation_vault_pass_file": parameters["vault_file"],
                "workstation_become_pass_file": parameters["become_file"],
            }
        )
    )
    wrapper = tmp_path / "skynet"
    wrapper.write_text(
        Environment(undefined=StrictUndefined)
        .from_string((ROLE / "templates/skynet.j2").read_text())
        .render(
            workstation_repository_path=str(directory.parent),
            workstation_user_home=str(tmp_path / "managed-home"),
            workstation_vault_pass_file=parameters["vault_file"],
            workstation_become_pass_file=parameters["become_file"],
            workstation_skynet_doctor_ping_target="tags_skynet",
            workstation_ansible_venv_path=str(Path(sys.executable).parent.parent),
            workstation_ansible_log_path=str(tmp_path / "ansible.log"),
            workstation_ansible_collections_path=str(tmp_path / "empty-collections"),
        )
    )
    env = {key: value for key, value in os.environ.items() if not key.startswith("ANSIBLE_")}
    env.update(
        ANSIBLE_CONFIG=str(directory / "bootstrap.cfg"),
        ANSIBLE_LOCAL_TEMP=str(tmp_path / "local"),
        ANSIBLE_REMOTE_TEMP=str(tmp_path / "remote"),
        ANSIBLE_LOG_PATH=str(tmp_path / "ansible.log"),
        ANSIBLE_NOCOLOR="true",
        ANSIBLE_COLLECTIONS_SCAN_SYS_PATH="false",
    )

    def run(*, answers=None, tags="workstation_credentials", check=False, skynet=False, record=False, ask_become=False):
        run_env = dict(env)
        if record:
            recorder = tmp_path / "record-playbook"
            recorder.write_text(
                f"#!{sys.executable}\nimport json, os, sys\n"
                "print(json.dumps({'argv': sys.argv[1:], 'config': os.environ['ANSIBLE_CONFIG']}))\n"
            )
            recorder.chmod(0o755)
            run_env["ANSIBLE_PLAYBOOK_BIN"] = str(recorder)
        command = (
            ["bash", str(wrapper), "check" if check else "run", "workstation", "credentials"]
            if skynet
            else [
                ANSIBLE,
                "-i",
                host + ",",
                "-c",
                "local",
                str(directory / "playbook.yml"),
                "-e",
                "workstation_hosts=" + host,
                "--tags",
                tags,
                "--diff",
                "-vvv",
                *(["--check"] if check else []),
            ]
        )
        if ask_become:
            command.append("--ask-become-pass")
        if answers is None:
            result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True, env=run_env, timeout=40)
            output = result.stdout + result.stderr
            code = result.returncode
        else:
            master, slave = pty.openpty()

            def terminal():
                os.setsid()
                fcntl.ioctl(slave, termios.TIOCSCTTY, 0)

            process = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave, env=run_env, preexec_fn=terminal)
            os.close(slave)
            output = ""
            position = 0
            pending = list(answers)
            deadline = time.monotonic() + 45
            try:
                while time.monotonic() < deadline:
                    ready, _, _ = select.select([master], [], [], 0.1)
                    if ready:
                        try:
                            chunk = os.read(master, 65536)
                        except OSError as error:
                            if error.errno != errno.EIO:
                                raise
                            break
                        if not chunk:
                            break
                        output += chunk.decode(errors="replace")
                    if pending and pending[0][0] in output[position:] and not termios.tcgetattr(master)[3] & termios.ECHO:
                        prompt, value = pending.pop(0)
                        position = output.index(prompt, position) + len(prompt)
                        os.write(master, value)
                else:
                    pytest.fail("Credential setup hung waiting for synthetic input")
                code = process.wait(timeout=5)
                assert not pending, output
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                os.close(master)
        log = (tmp_path / "ansible.log").read_text() if (tmp_path / "ansible.log").exists() else ""
        assert all(secret not in output + log for secret in (VAULT, BECOME, LOCAL))
        return code, output

    return parameters, run


def inputs(vault=True, become=True):
    answers = []
    for enabled, label, value in (
        (vault, "Existing Ansible Vault encryption password", VAULT),
        (become, "Managed-host sudo password supplied by Skynet", BECOME),
    ):
        if enabled:
            answers.extend([(label, (value + "\n").encode()), ("Confirm " + label, (value + "\n").encode())])
    return answers


@pytest.mark.integration
@pytest.mark.parametrize("skynet", [False, True])
def test_real_bootstrap_and_skynet_create_then_preserve(credentials, skynet):
    parameters, run = credentials
    code, output = run(answers=inputs(), skynet=skynet)
    assert code == 0, output
    before = {}
    for kind, expected in (("vault", VAULT), ("become", BECOME)):
        path = Path(parameters[kind + "_file"])
        assert path.read_text() == expected + "\n"
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        before[kind] = path.stat().st_mtime_ns
    code, output = run(skynet=skynet)
    assert code == 0, output
    assert "Confirm Existing" not in output
    assert all(Path(parameters[kind + "_file"]).stat().st_mtime_ns == value for kind, value in before.items())
    assert "Service host contract |" not in output and "Recovery target |" not in output


@pytest.mark.integration
def test_only_the_missing_file_is_prompted(credentials):
    parameters, run = credentials
    directory = Path(parameters["directory"])
    directory.mkdir(mode=0o700)
    path = Path(parameters["vault_file"])
    path.write_text(VAULT + "\n")
    path.chmod(0o600)
    code, output = run(answers=inputs(vault=False))
    assert code == 0, output
    assert "Confirm Existing Ansible" not in output
    assert path.read_text() == VAULT + "\n"


@pytest.mark.integration
@pytest.mark.parametrize(
    ("answers", "message"),
    [
        ([("Existing Ansible Vault encryption password", b"\n")], "Empty or invalid password"),
        (
            [
                ("Existing Ansible Vault encryption password", (VAULT + "\n").encode()),
                ("Confirm Existing Ansible Vault encryption password", b"NONPRODUCTION-mismatch\n"),
            ],
            "did not match",
        ),
        ([("Existing Ansible Vault encryption password", b"\x03")], "cancelled"),
        ([("Existing Ansible Vault encryption password", b"\x04")], "cancelled"),
        (inputs(become=False) + [("Managed-host sudo password supplied by Skynet", b"\x03")], "cancelled"),
    ],
)
def test_rejected_or_cancelled_input_creates_no_password_files(credentials, answers, message):
    parameters, run = credentials
    code, output = run(answers=answers)
    assert code != 0 and message in output, output
    assert not Path(parameters["directory"]).exists()
    assert "NONPRODUCTION-mismatch" not in output


@pytest.mark.integration
@pytest.mark.parametrize("check", [False, True])
@pytest.mark.parametrize("skynet", [False, True])
def test_noninteractive_and_check_mode(credentials, check, skynet):
    parameters, run = credentials
    code, output = run(check=check, skynet=skynet)
    assert (code == 0) == check, output
    assert not Path(parameters["directory"]).exists()
    if check:
        assert "Missing password files" in output and "vault" in output and "become" in output
    else:
        assert "interactive prompting is unavailable" in output and "--tags workstation_credentials" in output


@pytest.mark.integration
@pytest.mark.parametrize("tags", ["workstation", "workstation_tools"])
def test_ordinary_workstation_runs_do_not_prompt(credentials, tags):
    parameters, run = credentials
    code, output = run(tags=tags)
    assert code == 0, output
    assert not Path(parameters["directory"]).exists()
    assert "Privately confirm" not in output


@pytest.mark.integration
def test_credentials_can_precede_tools_in_the_same_bootstrap(credentials):
    _, run = credentials
    code, output = run(answers=inputs(), tags="workstation_tools,workstation_credentials")
    assert code == 0, output
    assert output.index("Privately confirm missing credentials") < output.index("SYNTHETIC WORKSTATION PAYLOAD")


@pytest.mark.integration
def test_local_become_prompt_is_independent_of_saved_managed_host_password(credentials):
    parameters, run = credentials
    answers = [("BECOME password:", (LOCAL + "\n").encode()), *inputs()]
    code, output = run(answers=answers, ask_become=True)
    assert code == 0, output
    assert Path(parameters["become_file"]).read_text() == BECOME + "\n"


@pytest.mark.integration
def test_unsafe_existing_directory_fails_without_prompting(credentials):
    parameters, run = credentials
    Path(parameters["vault_file"]).mkdir(parents=True)
    code, output = run()
    assert code != 0 and "Unsafe password destination" in output, output
    assert "Existing Ansible Vault encryption password" not in output
    assert not Path(parameters["become_file"]).exists()


@pytest.mark.integration
@pytest.mark.parametrize("check", [False, True])
def test_skynet_credentials_dispatch_uses_local_bootstrap_without_password_arguments(credentials, check):
    parameters, run = credentials
    # Even existing files must not be passed to Ansible for setup to read.
    directory = Path(parameters["directory"])
    directory.mkdir(mode=0o700)
    for kind in ("vault", "become"):
        Path(parameters[kind + "_file"]).write_text("NONPRODUCTION-existing-file")
    code, output = run(skynet=True, check=check, record=True)
    assert code == 0, output
    observed = json.loads(output.splitlines()[-1])
    args = observed["argv"]
    assert args[:2] == ["-i", os.uname().nodename.split(".")[0] + ","]
    assert args[2].endswith("/ansible/playbook.yml")
    assert args[args.index("--tags") + 1] == "workstation_credentials"
    assert args[args.index("-c") + 1] == "local"
    paths = json.loads(args[args.index("-e") + 1])
    assert paths["workstation_vault_pass_file"] == parameters["vault_file"]
    assert paths["workstation_become_pass_file"] == parameters["become_file"]
    assert "--vault-password-file" not in args and "--become-password-file" not in args
    assert ("--check" in args) == check
    assert observed["config"].endswith("/ansible/bootstrap.cfg")
