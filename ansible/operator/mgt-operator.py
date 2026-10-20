#!/usr/bin/python3
"""Managed by skynet mgt operator contexts; no inventory or credential lookup.

Only the delegated PostgreSQL interpreter and explicit local recovery jobs
enter these slices. Do not wrap a whole normal deployment or an SSH daemon.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path

SLICES = {"controller": "skynet_pg_prepare.slice", "recovery": "skynet_pg_recovery.slice"}
PYTHON = "/opt/ansible/ansible-venv/bin/python"
SYSTEMD = Path("/etc/systemd/system")
MARKER = "# Managed by skynet mgt operator contexts\n"


def require_root():
    if os.getuid() != 0 or os.geteuid() != 0:
        raise ValueError("native operator execution requires root after become")


def require_slice(context):
    """Never let systemd-run silently create an unprepared transient slice."""
    unit = SLICES[context]
    path = SYSTEMD / unit
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_gid != 0 or info.st_mode & 0o022:
        raise ValueError(f"{unit}: expected an owned, non-writable persistent unit")
    if not path.read_text().startswith(MARKER):
        raise ValueError(f"{unit}: refusing an unowned unit")
    result = subprocess.run(
        ["/usr/bin/systemctl", "show", unit, "--no-pager", "-p", "ActiveState", "-p", "ControlGroup", "-p", "FragmentPath"],
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    if result.returncode:
        raise RuntimeError(f"{unit}: systemctl show failed: {result.stderr.strip()}")
    observed = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if observed != {"ActiveState": "active", "ControlGroup": "/" + unit, "FragmentPath": str(path)}:
        raise ValueError(f"{unit}: persistent slice must be active at its exact root cgroup path")
    return unit


def command(context, program):
    if not program or not Path(program[0]).is_absolute():
        raise ValueError("operator command must name an absolute executable")
    unit = SLICES[context]
    return [
        "/usr/bin/systemd-run",
        "--quiet",
        "--wait",
        "--pipe",
        "--collect",
        "--service-type=exec",
        "--slice=" + unit,
        "--property=User=root",
        "--property=Group=root",
        "--property=UMask=0077",
        "--property=WorkingDirectory=" + os.getcwd(),
        "--",
        *program,
    ]


def launch(context, program):
    require_root()
    require_slice(context)
    # exec preserves stdin (including Ansible pipelining), stdout/stderr and the
    # systemd-run --wait exit status. Never relay credentials through --setenv.
    os.execv("/usr/bin/systemd-run", command(context, program))


def identity(context):
    require_root()
    lines = Path("/proc/self/cgroup").read_text().splitlines()
    paths = [line.removeprefix("0::/") for line in lines if line.startswith("0::/")]
    if len(paths) != 1 or not paths[0].startswith(SLICES[context] + "/"):
        raise ValueError("operator process is outside its prepared cgroup-v2 slice")
    return {"pid": os.getpid(), "process_uid": os.getuid(), "cgroup": paths[0], "binding_cgroup": SLICES[context]}


def socket_uid(connection):
    inode = str(os.fstat(connection.fileno()).st_ino)
    table = "tcp6" if connection.family == socket.AF_INET6 else "tcp"
    for line in Path("/proc/self/net", table).read_text().splitlines()[1:]:
        fields = line.split()
        if len(fields) > 9 and fields[9] == inode:
            return int(fields[7])
    raise ValueError("cannot establish ownership of the actual probe socket")


def probe(context, address, port, hold):
    """Open one bounded TCP connection; send/read no database payload."""
    observed = identity(context)
    ip = ipaddress.ip_address(address)
    if ip.is_unspecified or ip.is_multicast or not 1 <= port <= 65535 or not 0 <= hold <= 30:
        raise ValueError("probe needs a unicast address, TCP port and hold of 0–30 seconds")
    with socket.create_connection((str(ip), port), timeout=5) as connection:
        observed.update(socket_uid=socket_uid(connection), source=connection.getsockname(), destination=connection.getpeername())
        if observed["socket_uid"] != 0:
            raise ValueError("actual native socket UID must match the proposed root binding")
        print(json.dumps(observed, sort_keys=True), flush=True)
        time.sleep(hold)


def main():
    # Ansible calls this symlink as its interpreter only on postgresql_db.
    if Path(sys.argv[0]).name == "postgres-python":
        launch("controller", [PYTHON, *sys.argv[1:]])
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["check", "recovery", "probe", "_probe"])
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.operation == "check":
        if args.arguments:
            parser.error("check takes no arguments")
        print(json.dumps({context: require_slice(context) for context in SLICES}, sort_keys=True))
    elif args.operation == "recovery":
        launch("recovery", args.arguments)
    else:
        if len(args.arguments) != 4 or args.arguments[0] not in SLICES:
            parser.error("probe requires controller|recovery ADDRESS PORT HOLD_SECONDS")
        if args.operation == "_probe":
            probe(args.arguments[0], args.arguments[1], int(args.arguments[2]), int(args.arguments[3]))
        else:
            launch(args.arguments[0], ["/usr/bin/python3", str(Path(__file__).resolve()), "_probe", *args.arguments])


if __name__ == "__main__":
    try:
        main()
    except (KeyError, OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"skynet-mgt-operator: {error}", file=sys.stderr)
        sys.exit(1)
