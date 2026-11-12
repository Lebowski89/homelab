#!/usr/bin/env python3
"""Private Forgejo controller glue; all VM lifecycle/retirement belongs to vm.py.

Installed root-owned as homelab-molecule. Fetch only public GitHub main, retain
its exact checkout with each run, and never expose provisioner auth to Git/pip
or the Forgejo workflow environment. No API registration or VM cleanup here.
"""

import argparse
import fcntl
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid
from pathlib import Path

SOURCE = "https://github.com/Lebowski89/homelab.git"
PROFILE = Path("/etc/forgejo-runner/profile.json")
DRAIN = Path("/etc/forgejo-runner/draining")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_private(path):
    metadata = path.lstat()
    require(
        stat.S_ISREG(metadata.st_mode) and metadata.st_uid in (0, os.getuid()) and metadata.st_mode & 0o077 == 0,
        "Private controller input must be an owned regular file with mode 0600",
    )
    return json.loads(path.read_text())


def profile(path=PROFILE):
    metadata = path.lstat()
    require(
        stat.S_ISREG(metadata.st_mode) and metadata.st_uid == 0 and metadata.st_mode & 0o022 == 0,
        "Controller profile must be a root-owned regular file without group/other write access",
    )
    value = json.loads(path.read_text())
    for key in ("data_dir", "python", "collections", "allocation", "provisioning", "tofurc", "ssh_agent"):
        require(
            isinstance(value[key], str) and Path(value[key]).is_absolute() and ".." not in Path(value[key]).parts,
            "Controller profile paths must be absolute without traversal",
        )
    return value


def public_environment(config):
    """No API token, agent, personal Git configuration or inherited Ansible/TF overrides."""
    home = config["data_dir"]
    return {
        "HOME": home,
        "PATH": str(Path(config["python"]).parent) + ":/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "TMPDIR": home + "/tmp",
        "PIP_CACHE_DIR": home + "/cache/pip",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
    }


def provisioning_environment(config):
    credentials = read_private(Path(config["provisioning"]))
    require(
        set(credentials) == {"PROXMOX_VE_API_TOKEN"}
        and isinstance(credentials["PROXMOX_VE_API_TOKEN"], str)
        and credentials["PROXMOX_VE_API_TOKEN"].strip(),
        "Provisioning file must contain only a non-empty dedicated API token",
    )
    return (
        public_environment(config)
        | credentials
        | {
            "SSH_AUTH_SOCK": config["ssh_agent"],
            "TF_CLI_CONFIG_FILE": config["tofurc"],
            "ANSIBLE_COLLECTIONS_PATH": config["collections"],
            "ANSIBLE_INJECT_FACT_VARS": "false",
        }
    )


def write_record(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
    path.chmod(0o600)


def execute(argv, environment, cwd=None):
    subprocess.run(argv, cwd=cwd, env=environment, check=True)


def checkout_main(directory, environment):
    directory.mkdir(mode=0o700)
    execute(["git", "init", "--quiet", str(directory)], environment)
    execute(["git", "-C", str(directory), "fetch", "--quiet", "--depth=1", SOURCE, "refs/heads/main"], environment)
    sha = subprocess.check_output(["git", "-C", str(directory), "rev-parse", "FETCH_HEAD"], env=environment, text=True).strip()
    require(re.fullmatch(r"[a-f0-9]{40}", sha), "GitHub main did not resolve to an exact commit")
    execute(["git", "-C", str(directory), "checkout", "--quiet", "--detach", sha], environment)
    return sha


def source_checkout(record, config):
    checkout = Path(record["checkout"])
    require(
        checkout.parent == Path(config["data_dir"]) / "checkouts"
        and re.fullmatch(r"[a-f0-9]{32}", checkout.name)
        and checkout.resolve() == checkout,
        "Recovery checkout must remain in the original persistent controller directory",
    )
    sha = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], env=public_environment(config), text=True).strip()
    clean = subprocess.check_output(["git", "-C", str(checkout), "status", "--porcelain"], env=public_environment(config), text=True)
    require(sha == record["sha"] and not clean, "Original source checkout changed; inspect retained evidence before recovery")
    return checkout


def recover(config, run_id):
    require(re.fullmatch(r"[a-f0-9]{32}", run_id), "Supply one exact retained run ID")
    run = Path(config["data_dir"]) / "runs" / run_id
    record = read_private(run / "controller-source.json")
    checkout = source_checkout(record, config)
    # The original controller still enforces allocation, VM/file identity and
    # retirement confirmation. This command supplies only credentials/source.
    execute(
        [config["python"], str(checkout / "scripts/testing/vm.py"), "retire", str(run), "--confirm-run", run_id],
        provisioning_environment(config),
        checkout,
    )


def run(config, suite, platform):
    require(not DRAIN.exists(), "Controller is draining for maintenance; retry after the operator completes it")
    data = Path(config["data_dir"])
    scratch = data / "tmp"
    filesystem = subprocess.check_output(
        ["findmnt", "--noheadings", "--output", "FSTYPE", "--target", str(scratch)], env=public_environment(config), text=True
    ).strip()
    require(filesystem not in {"tmpfs", "ramfs"}, "Controller TMPDIR must be on persistent disk")
    require(
        shutil.disk_usage(data).free >= 6 * 1024**3, "Controller has less than its planned 6 GiB headroom; retain evidence and add capacity"
    )
    state = data / "runs"
    previous = {path.name for path in state.iterdir()}
    for path in state.iterdir():
        if path.is_dir() and (path / "manifest.json").exists():
            require(
                (path / "retired.json").exists(), "A retained run still occupies this allocation; use its scoped retirement command first"
            )
    job_id = uuid.uuid4().hex
    receipt = data / "jobs" / job_id
    receipt.mkdir(mode=0o700)
    checkout = data / "checkouts" / job_id
    environment = public_environment(config)
    sha = checkout_main(checkout, environment)
    record = {"sha": sha, "checkout": str(checkout), "job_id": job_id, "suite": suite, "os": platform}
    write_record(receipt / "source.json", record)
    print(f"Trusted GitHub main: {sha}\nSource and job evidence: {receipt}", flush=True)
    command = [config["python"], str(checkout / "scripts/testing/suite.py"), "--suite", suite, "--os", platform]
    # Use the real suite's choice validation before installing anything or
    # loading provisioner credentials. Inputs are always distinct argv entries.
    execute(command, environment, checkout)
    execute(
        [
            config["python"],
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-input",
            "-r",
            str(checkout / "molecule/requirements.txt"),
        ],
        environment,
        checkout,
    )
    execute(
        [
            str(Path(config["python"]).with_name("ansible-galaxy")),
            "collection",
            "install",
            "-r",
            str(checkout / "ansible/requirements.yml"),
            "-p",
            config["collections"],
        ],
        environment,
        checkout,
    )
    started = time.monotonic()
    code = 1
    try:
        execute(
            command + ["--execute", "--allocation", config["allocation"], "--state-root", str(state)],
            provisioning_environment(config),
            checkout,
        )
        code = 0
    finally:
        for directory in state.iterdir():
            if directory.name not in previous and directory.is_dir() and re.fullmatch(r"[a-f0-9]{32}", directory.name):
                write_record(directory / "controller-source.json", record)
                if not (directory / "retired.json").exists():
                    print(
                        f"Retained run: {directory}\nRetire explicitly: homelab-molecule retire {directory.name}",
                        file=sys.stderr,
                        flush=True,
                    )
        write_record(receipt / "result.json", {"exit_code": code, "duration_seconds": round(time.monotonic() - started, 3)})
    return code


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    selected = sub.add_parser("run")
    selected.add_argument("--suite", default="rocky_node_exporter")
    selected.add_argument("--os", default="rocky102")
    retirement = sub.add_parser("retire")
    retirement.add_argument("run_id")
    args = parser.parse_args()
    config = profile()
    with (Path(config["data_dir"]) / "controller.lock").open("a") as lock:
        # Queue acceptance requests; never cancel an active resource owner.
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.action == "retire":
            recover(config, args.run_id)
            return 0
        return run(config, args.suite, args.os)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        # Exception details may contain credential-bearing provider output.
        if isinstance(error, ValueError):
            print(str(error), file=sys.stderr)
        else:
            print(
                "Controller command failed; inspect private job/run evidence. Resources were not automatically destroyed.", file=sys.stderr
            )
        sys.exit(1)
