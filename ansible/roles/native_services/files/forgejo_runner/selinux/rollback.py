#!/usr/bin/python3
"""Checkpoint/restore only the runner's first confined-policy installation.

Recovery deliberately retains the failed operation's drain receipt. It never
starts a service, registers a runner, reads a credential, or runs acceptance.
"""

import argparse
import base64
import fcntl
import hashlib
import json
import os
import pwd
import re
import stat
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

HOME = Path("/var/lib/forgejo-runner")
OWNER = Path("/var/lib/native_services/forgejo_runner.json")
DRAIN = Path("/etc/forgejo-runner/draining")
CACHE = Path("/var/cache/forgejo-runner/selinux")
UNITS = [Path("/etc/systemd/system") / (name + ".service") for name in ["forgejo-runner", "forgejo-runner-agent"]]
PRIVATE = [
    Path("/etc/forgejo-runner/private") / name
    for name in ["node-key", "provisioning.json", "guest-key", "guest-key.pub", "registration.json"]
]
PRIVATE.append(Path("/etc/forgejo-runner/config.yml"))
RUNTIME = Path("/run/forgejo-runner-agent")
MODULE = "homelab_forgejo_runner"


def require(condition):
    if not condition:
        raise ValueError("Recovery ownership/state check failed; maintenance and evidence retained")


def command(*argv):
    return subprocess.check_output(argv, text=True, stderr=subprocess.PIPE).strip()


def boundary(path):
    for parent in [*reversed(path.parents), path]:
        require(not parent.is_symlink())


def metadata(path, links=False):
    boundary(path.parent if links else path)
    value = path.lstat()
    return {
        "uid": value.st_uid,
        "gid": value.st_gid,
        "mode": stat.S_IMODE(value.st_mode),
        "atime_ns": value.st_atime_ns,
        "mtime_ns": value.st_mtime_ns,
        "kind": stat.S_IFMT(value.st_mode),
        "label": os.getxattr(path, "security.selinux", follow_symlinks=False).hex(),
    }


def read_owned(path):
    info = metadata(path)
    require(info["uid"] == 0 and info["mode"] == 0o600 and path.is_file())
    return path.read_bytes()


def listing():
    return [
        line.split()
        for line in command("semodule", "--list-modules=full", "--checksum").splitlines()
        if len(line.split()) >= 2 and line.split()[1] == MODULE
    ]


def unit_state(unit):
    return dict(line.split("=", 1) for line in command("systemctl", "show", unit.name, "--property=ActiveState,UnitFileState").splitlines())


@contextmanager
def maintenance():
    account = pwd.getpwnam("molecule-ci")
    require(account.pw_uid > 0 and account.pw_dir == str(HOME))
    require(metadata(HOME)["uid"] == account.pw_uid and metadata(HOME)["mode"] == 0o700)
    require(metadata(DRAIN)["uid"] == 0 and metadata(DRAIN)["mode"] == 0o700 and DRAIN.is_dir())
    receipt = read_owned(DRAIN / "owner.json")
    value = json.loads(receipt)
    require(set(value) == {"token"} and re.fullmatch("[0-9a-f]{32}", value["token"]) is not None)
    require(set(DRAIN.iterdir()) == {DRAIN / "owner.json"})
    boundary(HOME / "controller.lock")
    fd = os.open(HOME / "controller.lock", os.O_RDWR | os.O_NOFOLLOW)
    with os.fdopen(fd, "r+") as lock:
        info = os.fstat(lock.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == account.pw_uid and not info.st_mode & 0o077)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield hashlib.sha256(receipt).hexdigest()
        require(read_owned(DRAIN / "owner.json") == receipt)


def owned_record():
    raw = read_owned(OWNER)
    value = json.loads(raw)
    require(value["identity"] == "forgejo_runner" and value["unit"] == "forgejo-runner")
    require(set(map(str, UNITS)) <= set(value["files"]))
    return raw, value


def checkpoint(digest):
    with maintenance() as receipt_hash:
        raw, record = owned_record()
        require(not record.get("selinux") and not listing())
        require(not RUNTIME.exists() and not RUNTIME.is_symlink())
        for path in PRIVATE:
            if path.exists() or path.is_symlink():
                info = metadata(path)
                require(path.is_file() and info["uid"] == metadata(HOME)["uid"] and info["mode"] == 0o600)
        states = {str(unit): unit_state(unit) for unit in UNITS}
        require(all(value["ActiveState"] in ["inactive", "failed"] and value["UnitFileState"] == "disabled" for value in states.values()))
        # Snapshot labels only, never credential contents. Do not traverse symlinks.
        expected_units = json.load(sys.stdin)
        require(set(expected_units) == set(map(str, UNITS)))
        require(all(re.fullmatch("[0-9a-f]{64}", value) for value in expected_units.values()))
        paths = [HOME, *PRIVATE, RUNTIME]
        for root, directories, files in os.walk(HOME, followlinks=False):
            paths.extend(Path(root) / name for name in directories + files)
        labels = {str(path): metadata(path, links=True) for path in paths if path.exists() or path.is_symlink()}
        files = {
            str(path): {
                "metadata": metadata(path),
                "bytes": base64.b64encode(path.read_bytes()).decode(),
                "xattrs": {key: os.getxattr(path, key, follow_symlinks=False).hex() for key in os.listxattr(path)},
            }
            for path in [OWNER, *UNITS]
        }
        require(all(files[str(unit)]["metadata"]["uid"] == 0 and files[str(unit)]["metadata"]["mode"] == 0o644 for unit in UNITS))
        folder = CACHE / digest
        boundary(folder)
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        require(metadata(folder)["uid"] == 0 and metadata(folder)["mode"] == 0o700)
        payload = {
            "digest": digest,
            "receipt_sha256": receipt_hash,
            "files": files,
            "labels": labels,
            "states": states,
            "expected_units": expected_units,
            "policy": [],
            "enforcing": command("getenforce"),
        }
        require(payload["enforcing"] == "Enforcing")
        # Never replace an earlier checkpoint, including an interrupted operation.
        with (folder / "rollback.json").open("x") as stream:
            os.chmod(stream.fileno(), 0o600)
            json.dump(payload, stream)
            stream.flush()
            os.fsync(stream.fileno())


def restore_file(path, saved):
    boundary(path)
    require(path.is_file() and metadata(path)["uid"] == 0)
    value = saved["metadata"]
    # Services are stopped and the controller lock is held. Keep inode/label
    # handling explicit; no restore of credentials or persistent application data.
    with path.open("wb") as stream:
        stream.write(base64.b64decode(saved["bytes"], validate=True))
        stream.flush()
        os.fsync(stream.fileno())
    os.chown(path, value["uid"], value["gid"])
    os.chmod(path, value["mode"])
    os.setxattr(path, "security.selinux", bytes.fromhex(value["label"]))
    for key in os.listxattr(path):
        if key not in saved["xattrs"]:
            os.removexattr(path, key)
    for key, data in saved["xattrs"].items():
        os.setxattr(path, key, bytes.fromhex(data))
    os.utime(path, ns=(value["atime_ns"], value["mtime_ns"]), follow_symlinks=False)


def package_proof(digest):
    package = CACHE / digest / (MODULE + ".pp")
    require(metadata(package)["uid"] == 0 and package.is_file() and not metadata(package)["mode"] & 0o022)
    payload = package.read_bytes()
    # Use the same installed HLL compiler as semodule. Its CIL SHA256 is the
    # installed module checksum, including the packaged file-context statements.
    cil = subprocess.run(["/usr/libexec/selinux/hll/pp"], input=payload, capture_output=True, check=True).stdout
    require(bool(cil))
    return {"package_sha256": hashlib.sha256(payload).hexdigest(), "checksum": "sha256:" + hashlib.sha256(cil).hexdigest()}


def arm(digest):
    with maintenance() as receipt_hash:
        snapshot = json.loads(read_owned(CACHE / digest / "rollback.json"))
        require(snapshot["digest"] == digest and snapshot["receipt_sha256"] == receipt_hash and not listing())
        intent_path = CACHE / digest / "installation-intent.json"
        intent = json.loads(read_owned(intent_path))
        require(
            intent["identity"] == "forgejo_runner"
            and intent["name"] == MODULE
            and intent["priority"] == 400
            and intent["source_sha256"] == digest
        )
        intent.update(package_proof(digest), receipt_sha256=receipt_hash)
        temporary = intent_path.with_name("armed-intent.json")
        with temporary.open("x") as stream:
            os.chmod(stream.fileno(), 0o600)
            json.dump(intent, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, intent_path)


def rollback(digest):
    snapshot = json.loads(read_owned(CACHE / digest / "rollback.json"))
    require(snapshot["digest"] == digest and snapshot["policy"] == [] and snapshot["enforcing"] == "Enforcing")
    with maintenance() as receipt_hash:
        require(receipt_hash == snapshot["receipt_sha256"] and command("getenforce") == "Enforcing")
        _, record = owned_record()
        if record.get("selinux"):
            require(record["selinux"].get("name") == MODULE and record["selinux"].get("source_sha256") == digest)
        current = listing()
        if current:
            policy = record.get("selinux", {})
            require(len(current) == 1 and current[0][:3] == ["400", MODULE, "pp"])
            if not (policy.get("source_sha256") == digest and policy.get("name") == MODULE and policy.get("checksum") == current[0][-1]):
                # This also covers interruption between semodule installation
                # and the native receipt write, without adopting unknown policy.
                intent_path = CACHE / digest / "installation-intent.json"
                require(intent_path.exists())
                intent = json.loads(read_owned(intent_path))
                require(
                    intent["identity"] == "forgejo_runner"
                    and intent["name"] == MODULE
                    and intent["priority"] == 400
                    and intent["source_sha256"] == digest
                    and intent["receipt_sha256"] == receipt_hash
                )
                proof = package_proof(digest)
                require(intent["checksum"] == current[0][-1] == proof["checksum"] and intent["package_sha256"] == proof["package_sha256"])
        # Validate all restore targets before the first mutation.
        require(set(snapshot["files"]) == set(map(str, [OWNER, *UNITS])))
        for name in snapshot["files"]:
            require(metadata(Path(name))["uid"] == 0 and Path(name).is_file())
        for unit in UNITS:
            saved = base64.b64decode(snapshot["files"][str(unit)]["bytes"], validate=True)
            require(
                hashlib.sha256(unit.read_bytes()).hexdigest() in [hashlib.sha256(saved).hexdigest(), snapshot["expected_units"][str(unit)]]
            )
        for name, saved in snapshot["labels"].items():
            path = Path(name)
            require(path in (HOME, RUNTIME) or HOME in path.parents or path in PRIVATE)
            if path.exists() or path.is_symlink():
                info = metadata(path, links=True)
                require(info["uid"] == saved["uid"] and info["kind"] == saved["kind"])
        for unit in UNITS:
            require(snapshot["states"][str(unit)]["UnitFileState"] == "disabled")
            command("systemctl", "disable", "--now", unit.name)
        if current:
            command("semodule", "-X", "400", "-r", MODULE)
        # Reset newly created home objects to base policy, then put back exact
        # pre-change labels for every retained object included in the checkpoint.
        command("restorecon", "-R", str(HOME))
        for path in PRIVATE + [RUNTIME]:
            if path.exists():
                boundary(path)
                command("restorecon", str(path))
        for name, saved in snapshot["labels"].items():
            path = Path(name)
            if path.exists() or path.is_symlink():
                os.setxattr(path, "security.selinux", bytes.fromhex(saved["label"]), follow_symlinks=False)
        for name, saved in snapshot["files"].items():
            restore_file(Path(name), saved)
        command("systemctl", "daemon-reload")
        require(not listing() and command("getenforce") == "Enforcing")
        require(
            all(
                unit_state(unit)["ActiveState"] in ["inactive", "failed"] and unit_state(unit)["UnitFileState"] == "disabled"
                for unit in UNITS
            )
        )
        # daemon-reload can read the restored units. Restore captured timestamps
        # after systemd has consumed the bytes, without starting either unit.
        for name, saved in snapshot["files"].items():
            value = saved["metadata"]
            os.utime(name, ns=(value["atime_ns"], value["mtime_ns"]), follow_symlinks=False)
        # No marker release and no service start, even when rollback succeeds.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["checkpoint", "arm", "rollback"])
    parser.add_argument("digest")
    args = parser.parse_args()
    require(os.geteuid() == 0 and re.fullmatch("[0-9a-f]{64}", args.digest) is not None)
    require(Path("/etc/hostname").read_text().strip().split(".")[0] == "molecule-controller")
    try:
        {"checkpoint": checkpoint, "arm": arm, "rollback": rollback}[args.action](args.digest)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        raise SystemExit("Scoped policy recovery failed; services/maintenance/evidence require review") from None
    print("Scoped policy " + args.action + " completed; maintenance ownership retained")


if __name__ == "__main__":
    main()
