"""Real filesystem and flock boundaries for the runner's cross-task maintenance."""

import fcntl
import importlib.util
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "runner_maintenance", ROOT / "ansible/roles/native_services/library/forgejo_runner_maintenance.py"
)
MAINTENANCE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MAINTENANCE)


def test_two_maintenance_operations_cannot_overlap_or_release_each_others_state(tmp_path):
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    drain = tmp_path / "draining"
    start = Barrier(2)

    def attempt():
        start.wait()
        try:
            return MAINTENANCE.acquire(drain, home, os.getuid(), owner=os.getuid())
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        tokens = list(pool.map(lambda _: attempt(), range(2)))
    assert sum(token is not None for token in tokens) == 1
    token = next(token for token in tokens if token)
    with pytest.raises(ValueError, match="token does not own"):
        MAINTENANCE.release(drain, "another-operation", owner=os.getuid())
    assert drain.exists()
    # An interrupted owner leaves the exclusion in place; no silent stale takeover.
    with pytest.raises(ValueError, match="interrupted maintenance"):
        MAINTENANCE.acquire(drain, home, os.getuid(), owner=os.getuid())
    MAINTENANCE.release(drain, token, owner=os.getuid())
    assert not drain.exists()
    next_token = MAINTENANCE.acquire(drain, home, os.getuid(), owner=os.getuid())
    MAINTENANCE.release(drain, next_token, owner=os.getuid())


def test_active_acceptance_or_retirement_is_never_stopped_and_releases_only_failed_acquisition(tmp_path):
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    lock_path = home / "controller.lock"
    lock_path.touch(mode=0o600)
    drain = tmp_path / "draining"
    with lock_path.open("a") as active:
        fcntl.flock(active, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match="Acceptance or retirement is active"):
            MAINTENANCE.acquire(drain, home, os.getuid(), owner=os.getuid())
        assert not drain.exists()
        # The operation did not release the active caller's descriptor.
        with lock_path.open("a") as contender, pytest.raises(BlockingIOError):
            fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_symlinked_runtime_lock_cannot_redirect_root_maintenance(tmp_path):
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    foreign = tmp_path / "foreign"
    foreign.write_text("retained")
    (home / "controller.lock").symlink_to(foreign)
    drain = tmp_path / "draining"
    with pytest.raises(OSError):
        MAINTENANCE.acquire(drain, home, os.getuid(), owner=os.getuid())
    assert foreign.read_text() == "retained"
    assert not drain.exists()


@pytest.mark.parametrize("failure", ["open", "stream", "write"])
def test_receipt_failure_removes_only_its_incomplete_marker_and_allows_retry(tmp_path, monkeypatch, failure):
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    drain = tmp_path / "draining"
    error = OSError("synthetic receipt failure")
    real_open = os.open

    def fail_open(path, *args, **kwargs):
        if Path(path) == drain / "owner.json":
            raise error
        return real_open(path, *args, **kwargs)

    def fail_write(value, stream):
        stream.write('{"token":')
        raise error

    def fail_stream(fd, *args, **kwargs):
        raise error

    with monkeypatch.context() as patch:
        if failure == "open":
            patch.setattr(MAINTENANCE.os, "open", fail_open)
        elif failure == "stream":
            patch.setattr(MAINTENANCE.os, "fdopen", fail_stream)
        else:
            patch.setattr(MAINTENANCE.json, "dump", fail_write)
        with pytest.raises(OSError) as caught:
            MAINTENANCE.acquire(drain, home, os.getuid(), owner=os.getuid())
    assert caught.value is error
    assert not drain.exists()
    assert not (home / "controller.lock").exists()
    token = MAINTENANCE.acquire(drain, home, os.getuid(), owner=os.getuid())
    MAINTENANCE.release(drain, token, owner=os.getuid())


@pytest.mark.parametrize("replacement", ["directory", "receipt"])
def test_failed_receipt_write_cannot_clean_up_replacement_state(tmp_path, monkeypatch, replacement):
    drain = tmp_path / "draining"
    error = OSError("synthetic receipt failure")

    def fail_write(value, stream):
        stream.write('{"token":')
        if replacement == "directory":
            drain.rename(tmp_path / "retained-original-marker")
            drain.mkdir(mode=0o700)
        else:
            (drain / "owner.json").unlink()
        receipt = drain / "owner.json"
        receipt.touch(mode=0o600)
        receipt.write_text('{"token":"another-operation"}')
        raise error

    monkeypatch.setattr(MAINTENANCE.json, "dump", fail_write)
    with pytest.raises(OSError) as caught:
        MAINTENANCE.acquire(drain, tmp_path / "absent-home", os.getuid(), owner=os.getuid())
    assert caught.value is error
    assert (drain / "owner.json").read_text() == '{"token":"another-operation"}'


def test_incomplete_marker_cleanup_error_does_not_replace_receipt_error(tmp_path, monkeypatch):
    drain = tmp_path / "draining"
    error = OSError("synthetic receipt failure")
    real_rmdir = Path.rmdir

    def fail_write(value, stream):
        stream.write('{"token":')
        raise error

    def fail_cleanup(path):
        if path == drain:
            raise PermissionError("synthetic cleanup failure")
        return real_rmdir(path)

    monkeypatch.setattr(MAINTENANCE.json, "dump", fail_write)
    monkeypatch.setattr(Path, "rmdir", fail_cleanup)
    with pytest.raises(OSError) as caught:
        MAINTENANCE.acquire(drain, tmp_path / "absent-home", os.getuid(), owner=os.getuid())
    assert caught.value is error
    assert drain.is_dir()
    assert not (drain / "owner.json").exists()
