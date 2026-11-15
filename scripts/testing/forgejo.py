#!/usr/bin/env python3
"""Private Forgejo controller glue; all VM lifecycle/retirement belongs to vm.py.

Installed root-owned as homelab-molecule. Default to public GitHub main, or an
explicitly approved branch/SHA in that same repository. Retain the exact checkout
with each run, and never expose provisioner auth to Git/pip
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


def validate_source(branch, sha, approved):
    require(
        isinstance(branch, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", branch),
        "Source branch must name a branch in Lebowski89/homelab",
    )
    require(type(approved) is bool, "Candidate approval must be explicit")
    if branch == "main" and not sha:
        require(not approved, "Default main does not require candidate approval")
    else:
        require(approved and re.fullmatch(r"[a-f0-9]{40}", sha), "Candidate requires an explicitly approved exact lowercase GitHub SHA")


def checkout_source(directory, environment, branch="main", sha="", approved=False):
    validate_source(branch, sha, approved)
    reference = "refs/heads/" + branch
    execute(["git", "check-ref-format", reference], environment)
    directory.mkdir(mode=0o700)
    execute(["git", "init", "--quiet", str(directory)], environment)
    # Candidates need the branch's reachable history to prove membership, even
    # when the reviewed SHA precedes its current tip. Main keeps its shallow fetch.
    depth = [] if sha else ["--depth=1"]
    execute(["git", "-C", str(directory), "fetch", "--quiet", "--no-tags", *depth, SOURCE, reference], environment)
    tip = subprocess.check_output(["git", "-C", str(directory), "rev-parse", "FETCH_HEAD"], env=environment, text=True).strip()
    require(re.fullmatch(r"[a-f0-9]{40}", tip), "GitHub branch did not resolve to an exact commit")
    resolved = sha or tip
    if sha:
        membership = subprocess.run(["git", "-C", str(directory), "merge-base", "--is-ancestor", sha, tip], env=environment, check=False)
        require(membership.returncode == 0, "Approved candidate does not belong to the fetched GitHub branch")
        commit = subprocess.check_output(["git", "-C", str(directory), "rev-parse", sha + "^{commit}"], env=environment, text=True).strip()
        require(commit == sha, "Candidate SHA must identify a commit directly")
    execute(["git", "-C", str(directory), "checkout", "--quiet", "--detach", resolved], environment)
    return {
        "source_repository": "Lebowski89/homelab",
        "source_branch": branch,
        "requested_source_sha": sha or None,
        "resolved_source_sha": resolved,
        "branch_tip_sha": tip,
    }


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
    require(not DRAIN.exists() and not DRAIN.is_symlink(), "Controller is draining for maintenance; retirement must wait")
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


def run(config, suite, platform, source_branch="main", source_sha="", candidate_approved=False):
    require(not DRAIN.exists() and not DRAIN.is_symlink(), "Controller is draining for maintenance; retry after the operator completes it")
    validate_source(source_branch, source_sha, candidate_approved)
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
    launcher_sha = os.environ.get("FORGEJO_LAUNCHER_SHA")
    require(launcher_sha is None or re.fullmatch(r"[a-f0-9]{40}", launcher_sha), "Forgejo workflow SHA must be exact")
    job_id = uuid.uuid4().hex
    receipt = data / "jobs" / job_id
    receipt.mkdir(mode=0o700)
    checkout = data / "checkouts" / job_id
    environment = public_environment(config)
    request = {
        "source_repository": "Lebowski89/homelab",
        "source_branch": source_branch,
        "requested_source_sha": source_sha or None,
        "candidate_approved": candidate_approved,
        "forgejo_workflow_sha": launcher_sha,
        "job_id": job_id,
        "suite": suite,
        "os": platform,
    }
    write_record(receipt / "request.json", request)
    record = None
    started = time.monotonic()
    code = 1
    try:
        source = checkout_source(checkout, environment, source_branch, source_sha, candidate_approved)
        sha = source["resolved_source_sha"]
        record = request | source | {"sha": sha, "checkout": str(checkout)}
        write_record(receipt / "source.json", record)
        print(
            f"Forgejo workflow commit: {launcher_sha or 'not supplied (local invocation)'}\n"
            f"GitHub source: Lebowski89/homelab branch={source_branch} requested={source_sha or 'main tip'} resolved={sha}\n"
            f"Source and job evidence: {receipt}",
            flush=True,
        )
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
        execute(
            command + ["--execute", "--allocation", config["allocation"], "--state-root", str(state)],
            provisioning_environment(config),
            checkout,
        )
        code = 0
    finally:
        for directory in state.iterdir():
            if (
                record is not None
                and directory.name not in previous
                and directory.is_dir()
                and re.fullmatch(r"[a-f0-9]{32}", directory.name)
            ):
                write_record(directory / "controller-source.json", record)
                if not (directory / "retired.json").exists():
                    print(
                        f"Retained run: {directory}\nRetire explicitly: homelab-molecule retire {directory.name}",
                        file=sys.stderr,
                        flush=True,
                    )
        write_record(
            receipt / "result.json",
            {
                "exit_code": code,
                "duration_seconds": round(time.monotonic() - started, 3),
                "requested_source_sha": source_sha or None,
                "resolved_source_sha": record["sha"] if record else None,
                "forgejo_workflow_sha": launcher_sha,
            },
        )
    return code


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    selected = sub.add_parser("run")
    selected.add_argument("--suite", default="node_exporter")
    selected.add_argument("--os", default="rocky102")
    selected.add_argument("--source-branch", default="main")
    selected.add_argument("--source-sha", default="")
    selected.add_argument("--candidate-approved", choices=["true", "false"], default="false")
    retirement = sub.add_parser("retire")
    retirement.add_argument("run_id")
    args = parser.parse_args()
    config = profile()
    require(not DRAIN.exists() and not DRAIN.is_symlink(), "Controller is draining for maintenance; retry after the operator completes it")
    with (Path(config["data_dir"]) / "controller.lock").open("a") as lock:
        # Queue acceptance requests; never cancel an active resource owner.
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.action == "retire":
            recover(config, args.run_id)
            return 0
        return run(config, args.suite, args.os, args.source_branch, args.source_sha, args.candidate_approved == "true")


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
