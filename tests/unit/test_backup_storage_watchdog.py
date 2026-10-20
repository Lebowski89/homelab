"""Exercise backup progress decisions without production runtimes or storage."""

import importlib.util
import io
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("backup_watchdog", ROOT / "ansible/operator/backup-storage-watchdog.py")
wd = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wd)


def sample(t, progress=0, **changes):
    return {
        "monotonic": t,
        "phase": "manifest",
        "progress": progress,
        "telemetry_complete": True,
        "operation_wait": True,
        "guest_wait": True,
        "host_wait": True,
        "host_sequence": t // 15,
        **changes,
    }


def test_transient_d_and_quiet_sleep_never_establish_stall():
    guard = wd.StorageWatchdog()
    for t in range(0, 301, 5):
        result = guard.observe(sample(t, host_wait=t % 30 != 0))
        assert not result["abort"]
    assert result["classification"] == "no_progress_inconclusive"
    assert not wd.storage_wait({"state": "D", "stack": "__cv_timedwait_common"}, "host")


def test_slow_completed_reads_prevent_stall_despite_correlated_pressure():
    guard = wd.StorageWatchdog()
    for t in range(0, 601, 5):
        result = guard.observe(sample(t, progress=t // 60))
        assert not result["abort"]
    assert result["classification"] == "slow_progress"


def test_sustained_operation_stall_ignores_unrelated_device_activity():
    guard = wd.StorageWatchdog()
    for t in range(0, 121, 5):
        result = guard.observe(sample(t, device_bytes=t * 10**9))
        assert result["abort"] == (t == 120)
    assert result["classification"] == "sustained_stall"
    assert result["distinct_host_samples"] == 9


def test_duplicate_host_rows_and_sample_gaps_do_not_prove_continuity():
    guard = wd.StorageWatchdog()
    for t in range(0, 151, 5):
        assert not guard.observe(sample(t, host_sequence=1))["abort"]
    guard = wd.StorageWatchdog()
    guard.observe(sample(0))
    assert not guard.observe(sample(120))["abort"]


def test_missing_telemetry_is_a_monitoring_failure_not_a_storage_stall():
    guard = wd.StorageWatchdog()
    for t in range(0, 61, 5):
        result = guard.observe(sample(t, telemetry_complete=False))
        assert result["abort"] == (t == 60)
    assert result["classification"] == "telemetry_unavailable"
    # A recovered sample resets the telemetry grace period.
    assert not guard.observe(sample(65))["abort"]
    assert not guard.observe(sample(70, telemetry_complete=False))["abort"]


@pytest.mark.parametrize("field", ["identity_error", "storage_error"])
def test_explicit_errors_abort_independently_of_progress(field):
    result = wd.StorageWatchdog().observe(sample(0, progress=100, **{field: True}))
    assert result["abort"] and result["classification"] != "sustained_stall"


def test_actual_hash_and_ownership_contracts_report_only_completed_work(tmp_path):
    progress = wd.OperationProgress()
    progress.begin("manifest")
    digest = progress.file_digest(io.BytesIO(b"fixture"), "sha256")
    assert digest.hexdigest() == __import__("hashlib").sha256(b"fixture").hexdigest()
    assert progress.snapshot()["bytes_read"] == 7
    spec = importlib.util.spec_from_file_location("utility", ROOT / "ansible/operator/utility-preparation.py")
    utility = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(utility)
    root = tmp_path / "data"
    root.mkdir()
    file = root / "sample"
    file.write_bytes(b"safe fixture")
    tree = utility.ownership_tree([str(root)])
    rows = [{"path": name, "old": [v["uid"], v["gid"]], "new": [v["uid"], v["gid"]]} for name, v in tree["entries"].items()]
    contracts = wd.instrument_ownership(utility, progress)
    snapshot = contracts["ownership_inventory"](rows, [str(root)])
    assert snapshot == utility.ownership_inventory(rows, [str(root)])
    assert progress.snapshot()["bytes_read"] == 7 + 2 * len(b"safe fixture")
    file.write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        contracts["ownership_verify"](snapshot, translated=False)


def test_kernel_errors_require_new_relevant_device_errors(monkeypatch):
    monkeypatch.setattr(wd.os, "open", lambda *args: 123)
    monkeypatch.setattr(wd.os, "lseek", lambda *args: 0)
    records = iter([b"6,1,1,-;I/O error, dev unrelated0, sector 1", b"6,2,2,-;task txg_sync blocked for more than 122 seconds"])

    def read(*args):
        try:
            return next(records)
        except StopIteration:
            raise BlockingIOError from None

    monkeypatch.setattr(wd.os, "read", read)
    kernel = wd.KernelErrors(["fixture0"])
    assert kernel.sample() == {"available": True, "storage_error": False}
    records = iter([b"3,3,3,-;I/O error, dev fixture0, sector 1"])
    assert kernel.sample() == {"available": True, "storage_error": True}


def test_phase_change_and_missing_stack_break_pressure_continuity():
    guard = wd.StorageWatchdog()
    for t in range(0, 116, 5):
        assert not guard.observe(sample(t))["abort"]
    assert not guard.observe(sample(120, phase="stream"))["abort"]
    assert not guard.observe(sample(125, telemetry_complete=False))["abort"]
    assert not wd.storage_wait({"state": "D", "stack_unavailable": "PermissionError"}, "operation")
