"""Synthetic NSS/boot/proxy metadata only; process and filesystem restrictions stay real."""

import json
import os
import pwd
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

root = Path(os.environ["FIXTURE_ROOT"])
original_text = Path.read_text
original_bytes = Path.read_bytes
original_sleep = time.sleep
original_account = pwd.getpwnam
original_run = subprocess.run


def text(path, *args, **kwargs):
    if str(path) == "/etc/skynet-mgt-firewall/policy.json":
        state = json.loads(original_text(root / "state.json"))
        if state["policy"] != "complete":
            return original_text(root / "installed-policy.json")
        policy = json.loads(original_text(root / "stage.json"))["policy"]
        values = json.loads(original_text(root / "handoff/cutover-batch-04-tested/working-policy.json"))
        policy["callers"] = values["mgt_firewall_callers"]
        policy["inputs_verified"] = values["mgt_firewall_inputs_verified"]
        return json.dumps(policy)
    if str(path) == "/proc/888/cgroup":
        return "0::/skynet_pg_recovery.slice/skynet-haproxy-acceptance-fixture.service\n"
    if str(path) == "/proc/sys/kernel/random/boot_id":
        return "fixture-manager-boot\n"
    if str(path) == "/proc/777/comm":
        return original_text(root / "proxy-comm", *args, **kwargs)
    return original_text(path, *args, **kwargs)


def contents(path):
    if str(path) == "/proc/888/cmdline":
        return b"\0".join(
            os.fsencode(value)
            for value in [
                "/usr/bin/python3",
                str(root / "handoff/cutover-batch-04-tested/haproxy-cutover.py"),
                "listen",
                "5432",
                "18405",
                "",
            ]
        )
    if str(path) == "/proc/777/cmdline":
        return original_bytes(root / "proxy-argv")
    return original_bytes(path)


def account(name):
    if name == "podman-forgejo":
        return SimpleNamespace(pw_uid=1004, pw_gid=1004, pw_dir=str(root / "forgejo"))
    return original_account(name)


def execute(argv, *args, **kwargs):
    if argv == ["/usr/bin/python3", "/etc/skynet-mgt-firewall/policy.py", "check"]:
        state = json.loads(original_text(root / "state.json"))
        return subprocess.CompletedProcess(
            argv, 0, json.dumps({"compliant": state["policy"] == "complete", "families": [4, 6], "pending": []}), ""
        )
    return original_run(argv, *args, **kwargs)


Path.read_text = text
Path.read_bytes = contents
pwd.getpwnam = account
subprocess.run = execute
# Test children have no privileges. Only the helper's operator precondition
# sees synthetic UID 0; kernel Landlock/seccomp/no_new_privs are unaffected.
os.geteuid = lambda: 0
time.sleep = lambda seconds: original_sleep(min(seconds, 0.01))
