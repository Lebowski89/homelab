"""Backup-specific progress and correlated storage-pressure decisions.

Device/pool counters are diagnostic context only. Sampling cannot prove a process
was continuously blocked between observations. Independent operation deadlines
remain authoritative even when storage telemetry is inconclusive.
"""

import ast
import copy
import hashlib
import os
import threading
from pathlib import Path


class StorageWatchdog:
    """Consume monotonic, identity-checked samples; never infer progress from I/O."""

    def __init__(self):
        self.phase = None
        self.progress = None
        self.last_progress = None
        self.last_sample = None
        self.pressure_since = None
        self.pressure_samples = 0
        self.host_samples = set()
        self.missing_since = None

    def observe(self, sample):
        t = sample["monotonic"]
        if self.last_sample is not None and t <= self.last_sample:
            raise ValueError("watchdog sample time must advance")
        gap = self.last_sample is not None and t - self.last_sample > 10
        self.last_sample = t
        if sample.get("identity_error"):
            return {"classification": "identity_changed", "abort": True}
        if sample.get("storage_error"):
            return {"classification": "explicit_storage_error", "abort": True}
        phase, progress = sample["phase"], sample["progress"]
        if self.phase != phase:
            self.phase, self.progress, self.last_progress = phase, progress, t
            gap = True
        if progress < self.progress:
            raise ValueError("operation progress regressed within phase")
        advanced = progress > self.progress
        if advanced:
            self.progress, self.last_progress = progress, t
        quiet = t - self.last_progress
        complete = sample.get("telemetry_complete", False)
        if complete:
            self.missing_since = None
        elif self.missing_since is None:
            self.missing_since = t
        correlated = complete and all(sample.get(k, False) for k in ("operation_wait", "guest_wait", "host_wait"))
        if gap or not correlated:
            self.pressure_since = None
            self.pressure_samples = 0
            self.host_samples.clear()
        if correlated:
            if self.pressure_since is None:
                self.pressure_since = t
            self.pressure_samples += 1
            self.host_samples.add(sample["host_sequence"])
        pressure = 0 if self.pressure_since is None else t - self.pressure_since
        missing = 0 if self.missing_since is None else t - self.missing_since
        # 120 seconds without completed operation work, plus at least 60 seconds
        # of closely sampled, stack-qualified pressure at operation/guest/host.
        stalled = quiet >= 120 and pressure >= 60 and self.pressure_samples >= 13 and len(self.host_samples) >= 5
        if not complete:
            classification = "telemetry_unavailable"
        elif stalled:
            classification = "sustained_stall"
        elif correlated:
            classification = "slow_progress" if advanced else "correlated_pressure"
        elif advanced:
            classification = "progressing"
        elif quiet >= 120:
            classification = "no_progress_inconclusive"
        else:
            classification = "waiting"
        return {
            "classification": classification,
            "abort": stalled or missing >= 60,
            "no_progress_seconds": quiet,
            "sampled_pressure_seconds": pressure,
            "missing_telemetry_seconds": missing,
            "guest_samples": self.pressure_samples,
            "distinct_host_samples": len(self.host_samples),
        }


class OperationProgress:
    """Count completed reads/entries only; wall time and device traffic do not count."""

    def __init__(self):
        self.lock = threading.Lock()
        self.phase = "preflight"
        self.completed = 0
        self.bytes_read = 0
        self.entries = 0

    def begin(self, phase):
        with self.lock:
            self.phase = phase
            self.completed = self.bytes_read = self.entries = 0

    def advance(self, *, size=0, entry=False):
        with self.lock:
            self.bytes_read += size
            self.entries += int(entry)
            self.completed += size + int(entry)

    def snapshot(self):
        with self.lock:
            return {"phase": self.phase, "progress": self.completed, "bytes_read": self.bytes_read, "entries": self.entries}

    def file_digest(self, stream, algorithm):
        digest = hashlib.new(algorithm)
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            self.advance(size=len(chunk))
        self.advance(entry=True)
        return digest


def instrument_ownership(utility, progress):
    """Retain actual ownership contracts; instrument just completed lstat/hash work.

    Compile isolated copies, rather than patching hashlib or the shared utility.
    This also instruments the verification pass called by ownership_inventory.
    """
    source = ast.parse(Path(utility.__file__).read_text())
    namespace = {**vars(utility), "backup_progress": progress}
    functions = [
        copy.deepcopy(n)
        for n in source.body
        if isinstance(n, ast.FunctionDef) and n.name in {"ownership_tree", "ownership_inventory", "ownership_verify"}
    ]
    hashes = entries = 0
    for function in functions:
        for node in ast.walk(function):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "hashlib"
                and node.func.attr == "file_digest"
            ):
                node.func.value.id = "backup_progress"
                hashes += 1
            if isinstance(node, ast.For):
                for index, statement in enumerate(node.body):
                    if (
                        isinstance(statement, ast.Assign)
                        and isinstance(statement.value, ast.Call)
                        and isinstance(statement.value.func, ast.Attribute)
                        and statement.value.func.attr == "lstat"
                    ):
                        node.body.insert(index + 1, ast.parse("backup_progress.advance(entry=True)").body[0])
                        entries += 1
                        break
    if len(functions) != 3 or hashes != 2 or entries != 1:
        raise ValueError("ownership progress instrumentation no longer matches reviewed contracts")
    module = ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[]))
    exec(compile(module, utility.__file__, "exec"), namespace)
    return {function.name: namespace[function.name] for function in functions}


def process_sample(pid, birth=None):
    """Read safe process identity/stack, never command lines or environments."""
    path = Path("/proc") / str(pid)
    fields = (path / "stat").read_text().rsplit(")", 1)[1].split()
    if birth is not None and fields[19] != birth:
        raise ValueError("storage observation process identity changed")
    result = {
        "pid": int(pid),
        "birth": fields[19],
        "state": fields[0],
        "comm": (path / "comm").read_text().strip(),
        "wchan": (path / "wchan").read_text().strip(),
    }
    try:
        result["stack"] = (path / "stack").read_text()
    except OSError as error:
        result["stack_unavailable"] = type(error).__name__
    return result


def storage_wait(process, kind):
    """Sleeping D threads with timed waits alone are not storage-pressure proof."""
    if process.get("state") != "D" or not process.get("stack"):
        return False
    stack = process["stack"]
    if kind == "host":
        return "zio_wait" in stack and any(value in stack for value in ("spa_sync", "dsl_pool_sync"))
    if kind == "guest":
        return "jbd2_journal_commit_transaction" in stack and "__wait_on_buffer" in stack
    if kind == "operation":
        return any(value in stack for value in ("folio_wait", "io_schedule", "balance_dirty_pages", "wait_on_page", "ext4_", "pipe_write"))
    raise ValueError("unknown storage observation kind")


class KernelErrors:
    """Watch only new kernel records; an overrun is telemetry loss, not a stall."""

    def __init__(self, devices):
        import re

        self.devices = re.compile(r"\b(?:" + "|".join(re.escape(v) for v in devices) + r")\b")
        self.errors = re.compile(r"I/O error|Buffer I/O|EXT4-fs error|blk_update_request.*error|pool.*suspend", re.I)
        self.fd = os.open("/dev/kmsg", os.O_RDONLY | os.O_NONBLOCK)
        os.lseek(self.fd, 0, os.SEEK_END)

    def sample(self):
        matched = False
        for _ in range(256):
            try:
                row = os.read(self.fd, 8192).decode(errors="replace")
            except BlockingIOError:
                return {"available": True, "storage_error": matched}
            if self.devices.search(row) and self.errors.search(row):
                matched = True
        return {"available": False, "storage_error": matched, "reason": "kernel observation read budget exhausted"}
