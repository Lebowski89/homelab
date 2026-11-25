"""Private evidence publication and the real delegated task content."""

import errno
import importlib.util
import json
import os
import stat
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("molecule_evidence", ROOT / "ansible/action_plugins/molecule_evidence.py")
EVIDENCE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(EVIDENCE)


def evidence_play(root, directory):
    """Select unchanged evidence tasks; no guest commands or fake copy actions."""
    verify = yaml.safe_load((root / "molecule/node_exporter/verify.yml").read_text())[1]["tasks"]
    diagnostics = yaml.safe_load((root / "molecule/shared/diagnostics.tasks.yml").read_text())
    platform = yaml.safe_load((root / "molecule/shared/diagnostics.yml").read_text())[1]["tasks"]
    tasks = [task for task in verify + diagnostics + platform if "molecule_evidence" in task]
    tasks += [task for parent in diagnostics for task in parent.get("block", []) if "molecule_evidence" in task]
    variables = {
        "molecule_vm_evidence_directory": str(directory),
        "molecule_node_exporter_invocation": {"stdout": "synthetic-first-invocation"},
        "molecule_node_exporter_release": {"stdout": "synthetic-release-one", "stderr": ""},
        "molecule_vm_diagnostic": {
            "results": [{"rc": 1, "stdout": "ordinary failure\nsecret=SYNTHETIC_REDACT", "stderr": "more evidence"}]
        },
        "molecule_vm_fixture_diagnostics": {"results": [{"rc": 1, "stdout": "fixture missing", "stderr": "synthetic failure"}]},
        "molecule_vm_python_modules": {"rc": 0, "stdout": '{"docker":"synthetic-version"}'},
        "molecule_vm_units": {"stdout_lines": ["ActiveState=failed"]},
        "molecule_vm_quadlet_diagnostic": {"rc": 1, "stdout": "ActiveState=failed", "stderr": "synthetic failure"},
        "ansible_facts": {
            "distribution": "Synthetic",
            "distribution_version": "1",
            "kernel": "synthetic-kernel",
            "architecture": "x86_64",
            "processor_vcpus": 2,
            "memtotal_mb": 1024,
            "mounts": [{"mount": "/", "fstype": "synthetic"}],
            "packages": {},
        },
    }
    return [
        {
            "hosts": "subject",
            "gather_facts": False,
            "become": False,
            "vars": variables,
            "tasks": tasks
            + [
                {
                    "ansible.builtin.set_fact": {
                        "molecule_node_exporter_invocation": {"stdout": "synthetic-second-invocation"},
                        "molecule_node_exporter_release": {"stdout": "synthetic-release-two", "stderr": ""},
                        "molecule_vm_diagnostic": {
                            "results": [
                                {
                                    "rc": 2,
                                    "stdout": "ordinary failure updated\nsecret=SYNTHETIC_REDACT_SECOND",
                                    "stderr": "more evidence two",
                                }
                            ]
                        },
                        "molecule_vm_fixture_diagnostics": {
                            "results": [{"rc": 1, "stdout": "fixture missing updated", "stderr": "synthetic failure two"}]
                        },
                        "molecule_vm_quadlet_diagnostic": {"rc": 0, "stdout": "ActiveState=inactive", "stderr": ""},
                        "molecule_vm_units": {"stdout_lines": ["ActiveState=inactive"]},
                    }
                }
            ]
            + tasks,
        }
    ]


@pytest.mark.parametrize("force", [False, True])
def test_new_and_existing_evidence_is_complete_private_and_idempotent(tmp_path, force, monkeypatch):
    destination = tmp_path / "snapshot"
    publish = EVIDENCE.os.replace if force else EVIDENCE.os.link
    seen = []

    def observe(source, target, **kwargs):
        assert Path(source).read_bytes() in [b"first observation", b"second observation"]
        assert Path(source).stat().st_mode & 0o777 == 0o600
        if not seen:
            assert not destination.exists()  # No empty first-observation placeholder.
        seen.append(Path(source).read_bytes())
        return publish(source, target, **kwargs)

    monkeypatch.setattr(EVIDENCE.os, "replace" if force else "link", observe)
    assert EVIDENCE.write_evidence(destination, "first observation", force)
    original = destination.stat()
    assert EVIDENCE.write_evidence(destination, "second observation", force) is force
    expected = b"second observation" if force else b"first observation"
    assert destination.read_bytes() == expected
    current = destination.stat()
    assert current.st_uid == original.st_uid == os.getuid() and current.st_gid == original.st_gid
    assert stat.S_IMODE(current.st_mode) == 0o600 and stat.S_IMODE(tmp_path.stat().st_mode) == 0o700
    if not force:
        assert (original.st_ino, original.st_mtime_ns) == (current.st_ino, current.st_mtime_ns)
    assert not EVIDENCE.write_evidence(destination, expected.decode(), force)
    assert not list(tmp_path.glob(".molecule-evidence-*"))


def test_valid_same_writer_selinux_context_never_requests_a_relabel(tmp_path, monkeypatch):
    destination = tmp_path / "evidence"
    monkeypatch.setattr(EVIDENCE.os, "getxattr", lambda *args: b"user_u:object_r:user_home_t:s0\0")
    monkeypatch.setattr(EVIDENCE.os, "setxattr", lambda *args: pytest.fail("A matching writer context must not be relabeled"))
    EVIDENCE.write_evidence(destination, "new")
    EVIDENCE.write_evidence(destination, "updated")
    assert destination.read_text() == "updated"


def test_first_observation_publication_does_not_overwrite_a_racing_winner(tmp_path, monkeypatch):
    destination = tmp_path / "first"
    gate = Barrier(2, timeout=5)
    link = EVIDENCE.os.link

    def racing_link(*args, **kwargs):
        gate.wait()
        return link(*args, **kwargs)

    monkeypatch.setattr(EVIDENCE.os, "link", racing_link)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda content: EVIDENCE.write_evidence(destination, content, False), ["observation-a", "observation-b"]))
    assert sorted(results) == [False, True] and destination.read_text() in ["observation-a", "observation-b"]
    assert not list(tmp_path.glob(".molecule-evidence-*"))


@pytest.mark.parametrize("existing", [False, True])
def test_failed_staging_preserves_old_or_absent_destination_and_can_retry(tmp_path, monkeypatch, existing):
    destination = tmp_path / "first"
    if existing:
        destination.write_text("original")
        destination.chmod(0o600)
    fsync = EVIDENCE.os.fsync

    def interrupted(descriptor):
        if stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("synthetic publication interruption")
        fsync(descriptor)

    with monkeypatch.context() as patch:
        patch.setattr(EVIDENCE.os, "fsync", interrupted)
        with pytest.raises(OSError):
            EVIDENCE.write_evidence(destination, "complete", existing)
    assert destination.read_text() == "original" if existing else not destination.exists()
    assert EVIDENCE.write_evidence(destination, "complete", existing)
    assert destination.read_text() == "complete" and not list(tmp_path.glob(".molecule-evidence-*"))


@pytest.mark.parametrize("unsafe", ["symlink", "mode", "directory", "parent"])
def test_unsafe_evidence_boundaries_are_rejected_without_changing_foreign_data(tmp_path, unsafe):
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    destination = directory / "snapshot"
    other = tmp_path / "retained"
    other.write_text("original")
    other.chmod(0o600)
    if unsafe == "symlink":
        destination.symlink_to(other)
    elif unsafe == "mode":
        destination.write_text("original")
        destination.chmod(0o644)
    elif unsafe == "directory":
        destination.mkdir()
    else:
        directory.chmod(0o755)
    with pytest.raises((ValueError, OSError)):
        EVIDENCE.write_evidence(destination, "new", False)
    assert other.read_text() == "original"


def test_check_mode_never_creates_or_replaces_evidence(tmp_path):
    destination = tmp_path / "first"
    assert EVIDENCE.write_evidence(destination, "new", check=True) and not destination.exists()
    EVIDENCE.write_evidence(destination, "old")
    assert EVIDENCE.write_evidence(destination, "new", check=True) and destination.read_text() == "old"
    assert not EVIDENCE.write_evidence(destination, "new", False, check=True)
    assert not list(tmp_path.glob(".molecule-evidence-*"))


@pytest.mark.integration
def test_real_delegated_evidence_tasks_preserve_first_observation_redaction_and_updates(tmp_path):
    from test_podman_rootless_check_mode import run_local_playbook

    directory = tmp_path / "evidence"
    directory.mkdir(mode=0o700)
    result = run_local_playbook(
        tmp_path,
        [
            {
                "hosts": "localhost",
                "gather_facts": False,
                "tasks": [
                    {
                        "ansible.builtin.add_host": {
                            "name": "subject",
                            "ansible_connection": "local",
                            "ansible_python_interpreter": sys.executable,
                        }
                    }
                ],
            },
            *evidence_play(ROOT, directory),
        ],
        check_mode=False,
        extra_env={"ANSIBLE_INVENTORY": "localhost,", "ANSIBLE_ACTION_PLUGINS": str(ROOT / "ansible/action_plugins")},
    )
    # The helper's fixed localhost inventory is augmented via add_host, without
    # any SSH targets or remote guest execution in this evidence-only play.
    assert result.returncode == 0, result.stdout + result.stderr
    assert (directory / "node-exporter-invocation").read_text() == "synthetic-first-invocation"
    assert "synthetic-release-two" in json.loads((directory / "versions.json").read_text())["node_exporter"]
    diagnostic = json.loads((directory / "diagnostics-subject.json").read_text())
    assert "SYNTHETIC_REDACT" not in json.dumps(diagnostic) and "ordinary failure" in json.dumps(diagnostic)
    assert json.loads((directory / "quadlet-current.json").read_text())["stdout"] == "ActiveState=inactive"
    assert json.loads((directory / "docker-fixture-diagnostics.json").read_text())["stdout"] == ["fixture missing updated"]
    assert json.loads((directory / "observed-system.json").read_text())["distribution"] == "Synthetic"
    assert all(path.stat().st_uid == os.getuid() and path.stat().st_mode & 0o777 == 0o600 for path in directory.iterdir())


@pytest.mark.integration
def test_scenario_evidence_tasks_publish_private_snapshots_and_preserve_initial_identities(tmp_path):
    from ansible_task_cases import walk_tasks
    from test_podman_rootless_check_mode import run_local_playbook

    sources = {
        "runtime_install": ["prepare.yml", "verify.yml", "ubuntu-pasta-prerequisite.tasks.yml"],
        "application_lifecycle": ["prepare.yml", "verify.yml", "exercise.yml"],
        "protected_network": ["verify.yml", "worker_counters.yml", "swarm_recovery.yml"],
        "vm": ["prepare-fedora.yml"],
    }
    observations = {
        "molecule_vm_image_kernel": "image-kernel",
        "molecule_vm_kernel_preparation": {"changed": True},
        "molecule_vm_runtime_results": {"results": [{"stdout": "first-daemon-identity"}]},
        "molecule_vm_pasta_profiles": {"stdout_lines": ["pasta (enforce)", "podman (enforce)", "unrelated (enforce)"]},
        "molecule_vm_pasta_packages": {"stdout_lines": ["synthetic-pasta-version"]},
        "molecule_vm_keeper": {"stdout": "keeper-id first-start"},
        "molecule_vm_keeper_rebooted": {"stdout": "keeper-id reboot-start true"},
        "molecule_vm_writer_identity": {"stdout": "first-writer"},
        "molecule_vm_app_data": {"stat": {"checksum": "retained-data-checksum"}},
        "molecule_vm_before_rules": {"results": [{"stdout": "before-rules"}]},
        "molecule_vm_bridge_rules": {"results": [{"stdout": "bridge-denial-rules"}]},
        "molecule_vm_after_rules": {"results": [{"stdout": "after-rules"}]},
        "molecule_vm_handshakes": {"results": [{"connected": True}]},
        "molecule_vm_allowed_pid": {"stdout": "1234"},
        "molecule_vm_allowed_namespace": {"stdout": "net:[synthetic]"},
        "molecule_vm_after_allow": {"counters": {"4:18080": 2}},
        "molecule_vm_worker_before": {"counters": {"4:18080": 0}},
        "molecule_vm_worker_after": {"counters": {"4:18080": 3}},
        "molecule_vm_missing_task": {"stdout": '{"pending":true}'},
        "molecule_vm_pending_audit": {"rc": 1},
        "molecule_vm_recovered_handshakes": {"handshakes": [{"connected": True}]},
        "molecule_vm_image_stat": {"stat": {"checksum": "prepared-image-checksum"}},
        "molecule_vm_image_packages": {"stdout_lines": ["synthetic-base-package"]},
        "molecule_vm_prepared_capacity": {"stdout": '{"virtual-size":17179869184}'},
        "molecule_vm_source_layout": {"stdout_lines": ["synthetic-layout"]},
        "ansible_facts": {
            "distribution": "Rocky",
            "distribution_version": "synthetic-version",
            "kernel": "prepared-kernel",
            "selinux": {"mode": "enforcing"},
            "services": {"firewalld.service": {"state": "running", "status": "enabled"}},
        },
    }
    updated = {
        "molecule_vm_runtime_results": {"results": [{"stdout": "second-daemon-identity"}]},
        "molecule_vm_writer_identity": {"stdout": "recreated-writer"},
        "molecule_vm_keeper_rebooted": {"stdout": "keeper-id second-reboot true"},
        "molecule_vm_before_rules": {"results": [{"stdout": "updated-rules"}]},
        "molecule_vm_worker_after": {"counters": {"4:18080": 4}},
        "molecule_vm_image_stat": {"stat": {"checksum": "updated-image-checksum"}},
    }
    plays = []
    for scenario, filenames in sources.items():
        directory = tmp_path / scenario
        directory.mkdir(mode=0o700)
        tasks = []
        for filename in filenames:
            entries = yaml.safe_load((ROOT / "molecule" / scenario / filename).read_text())
            for entry in entries:
                tasks.extend(task for task in walk_tasks(entry.get("tasks", [entry])) if "molecule_evidence" in task)
        # Run the actual delegated tasks, including their arguments and local
        # become override, without any guest provisioning or runtime commands.
        plays.append(
            {
                "hosts": "localhost",
                "connection": "local",
                "become": True,
                "gather_facts": False,
                "vars": {**observations, "molecule_vm_evidence_directory": str(directory)},
                "tasks": [{"ansible.builtin.set_fact": observations}] + tasks + [{"ansible.builtin.set_fact": updated}] + tasks,
            }
        )
    result = run_local_playbook(
        tmp_path,
        plays,
        check_mode=False,
        extra_env={"ANSIBLE_ACTION_PLUGINS": str(ROOT / "ansible/action_plugins")},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    runtime = tmp_path / "runtime_install"
    assert json.loads((runtime / "kernel-preparation.json").read_text()) == {
        "image_kernel": "image-kernel",
        "running_kernel": "prepared-kernel",
        "package_changes": True,
    }
    assert json.loads((runtime / "security.json").read_text())["firewalld_enabled"] is True
    assert json.loads((runtime / "runtime-identity.json").read_text()) == ["first-daemon-identity"]
    assert json.loads((runtime / "versions.json").read_text())["runtime_outputs"] == ["second-daemon-identity"]
    assert json.loads((runtime / "apparmor-prerequisite.json").read_text()) == {
        "profiles": ["pasta (enforce)", "podman (enforce)"],
        "packages": ["synthetic-pasta-version"],
    }
    application = tmp_path / "application_lifecycle"
    assert (application / "keeper-identity").read_text() == "keeper-id first-start"
    assert (application / "keeper-expected").read_text() == "keeper-id second-reboot"
    assert json.loads((application / "application-first.json").read_text()) == {
        "identity": "first-writer",
        "checksum": "retained-data-checksum",
    }
    assert json.loads((application / "application-expected.json").read_text()) == {
        "identity": "recreated-writer",
        "checksum": "retained-data-checksum",
    }
    network = tmp_path / "protected_network"
    assert json.loads((network / "network-initial.json").read_text())["before"] == ["before-rules"]
    assert json.loads((network / "worker-counters.json").read_text()) == {"before": {"4:18080": 0}, "after": {"4:18080": 4}}
    assert json.loads((network / "swarm-recovery.json").read_text()) == {
        "pending": True,
        "strict_audit_rc": 1,
        "handshakes": [{"connected": True}],
    }
    image = json.loads((tmp_path / "vm/prepared-image.json").read_text())
    assert image["checksum"] == "updated-image-checksum" and image["virtual_size_bytes"] == 17179869184
    assert all(
        path.stat().st_uid == os.getuid() and stat.S_IMODE(path.stat().st_mode) == 0o600
        for path in tmp_path.glob("*/*")
        if path.is_file() and path.parent.name in sources
    )


@pytest.mark.parametrize("label_error", [errno.ENODATA, errno.EACCES])
def test_unlabelled_filesystems_work_but_label_access_denials_remain_fatal(tmp_path, monkeypatch, label_error):
    destination = tmp_path / "evidence"
    EVIDENCE.write_evidence(destination, "old")

    def label(*args):
        raise OSError(label_error, "synthetic label result")

    monkeypatch.setattr(EVIDENCE.os, "getxattr", label)
    monkeypatch.setattr(EVIDENCE.os, "setxattr", lambda *args: pytest.fail("No available context may be invented"))
    if label_error == errno.ENODATA:
        assert EVIDENCE.write_evidence(destination, "new")
        assert destination.read_text() == "new"
    else:
        with pytest.raises(OSError):
            EVIDENCE.write_evidence(destination, "new")
        assert destination.read_text() == "old"


@pytest.mark.parametrize("unsafe", ["remote", "become", "outside", "truthy_force"])
def test_action_rejects_non_controller_or_out_of_scope_writes(tmp_path, monkeypatch, unsafe):
    from types import SimpleNamespace

    from ansible.errors import AnsibleActionFail

    action = EVIDENCE.ActionModule.__new__(EVIDENCE.ActionModule)
    action._task = SimpleNamespace(
        args={"dest": str(tmp_path / "evidence"), "content": "synthetic", "mode": "0600"},
        delegate_to="localhost",
        check_mode=False,
        async_val=0,
        action="molecule_evidence",
    )
    action._play_context = SimpleNamespace(become=False)
    action._connection = SimpleNamespace(_shell=SimpleNamespace(tmpdir="unused"))
    if unsafe == "remote":
        action._task.delegate_to = "subject"
    elif unsafe == "become":
        action._play_context.become = True
    elif unsafe == "outside":
        action._task.args["dest"] = str(tmp_path.parent / "foreign")
    else:
        action._task.args["force"] = "false"
    monkeypatch.setattr(EVIDENCE, "write_evidence", lambda *args: pytest.fail("Rejected input must not touch the filesystem"))
    with pytest.raises(AnsibleActionFail, match="unprivileged localhost delegation"):
        action.run(task_vars={"molecule_vm_evidence_directory": str(tmp_path)})


@pytest.mark.integration
def test_fifo_evidence_is_rejected_with_a_bounded_process(tmp_path):
    destination = tmp_path / "fifo"
    os.mkfifo(destination, 0o600)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import runpy,sys; from pathlib import Path; writer=runpy.run_path(sys.argv[1]); "
            "writer['write_evidence'](Path(sys.argv[2]), 'synthetic')",
            str(ROOT / "ansible/action_plugins/molecule_evidence.py"),
            str(destination),
        ],
        env={**os.environ, "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"), "ANSIBLE_HOME": str(tmp_path / "home")},
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode != 0 and "Evidence must be an owned regular mode-0600 file" in result.stderr
    assert destination.is_fifo()
