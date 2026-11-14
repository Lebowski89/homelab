"""Exercise the bounded recovery executable with real temporary files/locks."""

import base64
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "ansible/roles/native_services/files/forgejo_runner/selinux/rollback.py"


@pytest.fixture
def recovery(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("runner_policy_rollback", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name, value in {
        "HOME": tmp_path / "home",
        "OWNER": tmp_path / "owner.json",
        "DRAIN": tmp_path / "drain",
        "CACHE": tmp_path / "cache",
        "RUNTIME": tmp_path / "runtime",
        "UNITS": [tmp_path / "runner.service", tmp_path / "agent.service"],
        "PRIVATE": [tmp_path / "node-key", tmp_path / "provisioning.json", tmp_path / "registration.json"],
    }.items():
        monkeypatch.setattr(mod, name, value)
    for path in [mod.HOME, mod.DRAIN, mod.CACHE]:
        path.mkdir(mode=0o700)
    (mod.HOME / "controller.lock").touch(mode=0o600)
    (mod.HOME / "data").write_text("retained evidence")
    receipt = mod.DRAIN / "owner.json"
    receipt.write_text(json.dumps({"token": "a" * 32}))
    receipt.chmod(0o600)
    owner = {"identity": "forgejo_runner", "unit": "forgejo-runner", "files": list(map(str, mod.UNITS))}
    mod.OWNER.write_text(json.dumps(owner))
    mod.OWNER.chmod(0o600)
    for path in mod.UNITS:
        path.write_bytes(b"original unit\n")
        path.chmod(0o644)
    for path in mod.PRIVATE:
        path.write_text("synthetic-private-material")
        path.chmod(0o600)
    labels = {}
    for path in tmp_path.rglob("*"):
        labels[str(path)] = b"original_label\x00"
    getxattr, setxattr = os.getxattr, os.setxattr
    monkeypatch.setattr(
        mod.os,
        "getxattr",
        lambda path, key, **kw: labels.get(str(path), b"original_label\x00") if key == "security.selinux" else getxattr(path, key, **kw),
    )
    monkeypatch.setattr(
        mod.os,
        "setxattr",
        lambda path, key, value, **kw: labels.update({str(path): value}) if key == "security.selinux" else setxattr(path, key, value, **kw),
    )
    metadata = mod.metadata

    def synthetic_ownership(path, **kwargs):
        info = metadata(path, **kwargs)
        if path in [mod.OWNER, mod.DRAIN, receipt, *mod.UNITS] or path == mod.CACHE or mod.CACHE in path.parents:
            info["uid"] = 0
        return info

    monkeypatch.setattr(mod, "metadata", synthetic_ownership)
    monkeypatch.setattr(mod.os, "chown", lambda *args: None)
    monkeypatch.setattr(mod.pwd, "getpwnam", lambda name: SimpleNamespace(pw_uid=os.getuid(), pw_dir=str(mod.HOME)))
    state = {"module": False, "checksum": "sha256:" + "b" * 64, "active": "inactive"}
    calls = []

    def command(*argv):
        calls.append(argv)
        if argv[0] == "getenforce":
            return "Enforcing"
        if argv[:2] == ("semodule", "--list-modules=full"):
            return "400 homelab_forgejo_runner pp " + state["checksum"] if state["module"] else ""
        if argv[:2] == ("systemctl", "show"):
            return "ActiveState=" + state["active"] + "\nUnitFileState=disabled"
        if argv[:3] == ("systemctl", "disable", "--now"):
            state["active"] = "inactive"
        elif argv == ("semodule", "-X", "400", "-r", "homelab_forgejo_runner"):
            state["module"] = False
        elif argv[0] not in ["restorecon", "systemctl"]:
            pytest.fail("Unexpected recovery command: " + repr(argv))
        return ""

    monkeypatch.setattr(mod, "command", command)
    expected = {str(path): hashlib.sha256(b"candidate unit\n").hexdigest() for path in mod.UNITS}
    monkeypatch.setattr(mod.sys, "stdin", io.StringIO(json.dumps(expected)))
    return mod, state, calls, labels


def install_candidate(mod, state, labels):
    record = json.loads(mod.OWNER.read_text())
    record["selinux"] = {"name": mod.MODULE, "source_sha256": "a" * 64, "checksum": state["checksum"]}
    mod.OWNER.write_text(json.dumps(record))
    state["module"] = True
    for path in mod.UNITS:
        path.write_bytes(b"candidate unit\n")
    labels.update({path: b"candidate_label\x00" for path in labels})


def test_policy_rollback_restores_exact_units_metadata_labels_and_offline_state(recovery):
    mod, state, calls, labels = recovery
    original_owner = mod.OWNER.read_bytes()
    original_receipt = (mod.DRAIN / "owner.json").read_bytes()
    original_private = {path: path.read_bytes() for path in mod.PRIVATE}
    os.setxattr(mod.UNITS[0], "user.recovery-note", b"original metadata")
    mod.checkpoint("a" * 64)
    snapshot = json.loads((mod.CACHE / ("a" * 64) / "rollback.json").read_text())
    assert "synthetic-private-material" not in json.dumps(snapshot)
    assert base64.b64decode(snapshot["files"][str(mod.UNITS[0])]["bytes"]) == b"original unit\n"
    install_candidate(mod, state, labels)
    os.setxattr(mod.UNITS[0], "user.recovery-note", b"changed metadata")
    os.setxattr(mod.UNITS[0], "user.new-attribute", b"remove on rollback")
    calls.clear()
    mod.rollback("a" * 64)
    assert mod.OWNER.read_bytes() == original_owner
    assert all(path.read_bytes() == b"original unit\n" and path.stat().st_mode & 0o777 == 0o644 for path in mod.UNITS)
    assert all(path.read_bytes() == value for path, value in original_private.items())
    assert all(labels[name] == bytes.fromhex(saved["label"]) for name, saved in snapshot["labels"].items())
    assert (mod.DRAIN / "owner.json").read_bytes() == original_receipt
    assert (mod.HOME / "data").read_text() == "retained evidence"
    assert os.getxattr(mod.UNITS[0], "user.recovery-note") == b"original metadata"
    assert "user.new-attribute" not in os.listxattr(mod.UNITS[0])
    assert mod.UNITS[0].stat().st_mtime_ns == snapshot["files"][str(mod.UNITS[0])]["metadata"]["mtime_ns"]
    removal = calls.index(("semodule", "-X", "400", "-r", mod.MODULE))
    assert all(("systemctl", "disable", "--now", unit.name) in calls[:removal] for unit in mod.UNITS)
    assert not any("start" in argv or "restart" in argv or "enable" in argv for argv in calls)
    mod.rollback("a" * 64)
    assert not state["module"]


@pytest.mark.parametrize("foreign", ["receipt", "policy", "unit", "symlink", "lock"])
def test_policy_rollback_rejects_changed_ownership_before_mutation(recovery, foreign):
    mod, state, calls, labels = recovery
    mod.checkpoint("a" * 64)
    install_candidate(mod, state, labels)
    lock = (mod.HOME / "controller.lock").open("r+")
    if foreign == "receipt":
        (mod.DRAIN / "owner.json").write_text(json.dumps({"token": "c" * 32}))
    elif foreign == "policy":
        state["checksum"] = "sha256:" + "c" * 64
    elif foreign == "unit":
        mod.UNITS[0].write_text("foreign unit")
    elif foreign == "symlink":
        mod.UNITS[0].unlink()
        mod.UNITS[0].symlink_to(mod.UNITS[1])
    else:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    calls.clear()
    before = {path: path.read_bytes() for path in [mod.OWNER, *mod.UNITS, *mod.PRIVATE]}
    try:
        with pytest.raises((ValueError, BlockingIOError)):
            mod.rollback("a" * 64)
    finally:
        lock.close()
    assert before == {path: path.read_bytes() for path in before}
    assert not any(argv[0] == "restorecon" or "-r" in argv or "disable" in argv for argv in calls)
    assert mod.DRAIN.is_dir()


def test_interrupted_policy_rollback_keeps_checkpoint_and_receipt_for_retry(recovery, monkeypatch):
    mod, state, calls, labels = recovery
    mod.checkpoint("a" * 64)
    install_candidate(mod, state, labels)
    original = mod.command

    def fail_remove(*argv):
        if argv == ("semodule", "-X", "400", "-r", mod.MODULE):
            raise OSError("synthetic policy-store failure")
        return original(*argv)

    monkeypatch.setattr(mod, "command", fail_remove)
    with pytest.raises(OSError):
        mod.rollback("a" * 64)
    assert state["active"] == "inactive" and mod.DRAIN.is_dir()
    assert (mod.CACHE / ("a" * 64) / "rollback.json").is_file()
    monkeypatch.setattr(mod, "command", original)
    mod.rollback("a" * 64)
    assert not state["module"] and mod.DRAIN.is_dir()


@pytest.mark.parametrize("tampered", [None, "package", "checksum"])
def test_armed_package_proves_interrupted_install_without_native_checksum_receipt(recovery, monkeypatch, tampered):
    mod, state, calls, labels = recovery
    mod.checkpoint("a" * 64)
    folder = mod.CACHE / ("a" * 64)
    package = folder / (mod.MODULE + ".pp")
    package.write_bytes(b"synthetic public policy package")
    package.chmod(0o600)
    intent = folder / "installation-intent.json"
    intent.write_text(json.dumps({"identity": "forgejo_runner", "name": mod.MODULE, "priority": 400, "source_sha256": "a" * 64}))
    intent.chmod(0o600)
    monkeypatch.setattr(mod.subprocess, "run", lambda argv, **kwargs: SimpleNamespace(stdout=b"synthetic CIL"))
    mod.arm("a" * 64)
    state["checksum"] = "sha256:" + hashlib.sha256(b"synthetic CIL").hexdigest()
    install_candidate(mod, state, labels)
    # Installation succeeded, but the native ownership update never completed.
    record = json.loads(mod.OWNER.read_text())
    del record["selinux"]
    mod.OWNER.write_text(json.dumps(record))
    if tampered == "package":
        package.write_bytes(b"changed package")
    elif tampered == "checksum":
        state["checksum"] = "sha256:" + "c" * 64
    calls.clear()
    if tampered:
        with pytest.raises(ValueError):
            mod.rollback("a" * 64)
        assert not any("-r" in argv or "disable" in argv for argv in calls)
    else:
        mod.rollback("a" * 64)
        assert not state["module"] and mod.DRAIN.is_dir()


def test_policy_checkpoint_rejects_online_state_and_never_overwrites(recovery):
    mod, state, _, _ = recovery
    state["active"] = "active"
    with pytest.raises(ValueError):
        mod.checkpoint("a" * 64)
    state["active"] = "inactive"
    mod.checkpoint("a" * 64)
    snapshot = mod.CACHE / ("a" * 64) / "rollback.json"
    original = snapshot.read_bytes()
    mod.sys.stdin.seek(0)
    with pytest.raises(FileExistsError):
        mod.checkpoint("a" * 64)
    assert snapshot.read_bytes() == original
