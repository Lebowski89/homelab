#!/usr/bin/python
"""Hold a token-owned drain boundary across separate Ansible task processes."""

import fcntl
import json
import os
import stat
import uuid
from pathlib import Path

DOCUMENTATION = r"""
module: forgejo_runner_maintenance
short_description: Serialize the dedicated runner's managed lifecycle
options:
  state:
    type: str
    choices: [present, absent]
    required: true
  data_dir:
    type: path
  uid:
    type: int
  token:
    type: str
supports_check_mode: true
"""

DRAIN = Path("/etc/forgejo-runner/draining")


def owned(metadata, uid):
    if metadata.st_uid != uid or metadata.st_mode & 0o077:
        raise ValueError("Maintenance state has foreign ownership or permissions; retain it for inspection")


def release(path, token, owner=0):
    owned(path.lstat(), owner)
    if not path.is_dir() or path.is_symlink():
        raise ValueError("Maintenance marker is not an owned directory")
    receipt = path / "owner.json"
    with os.fdopen(os.open(receipt, os.O_RDONLY | os.O_NOFOLLOW)) as stream:
        owned(os.fstat(stream.fileno()), owner)
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode) or json.load(stream) != {"token": token}:
            raise ValueError("Maintenance token does not own this operation; marker retained")
    if set(path.iterdir()) != {receipt}:
        raise ValueError("Unexpected maintenance state; marker retained")
    receipt.unlink()
    path.rmdir()


def acquire(path, home, uid, owner=0):
    # mkdir is the exclusive lifecycle lock. Jobs and retirement reject this
    # marker while holding controller.lock, so the flock probe below cannot race
    # with new acceptance/recovery after it releases its descriptor.
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        raise ValueError("Another or interrupted maintenance operation owns the drain marker; inspect its receipt") from None
    token = uuid.uuid4().hex
    with os.fdopen(os.open(path / "owner.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "w") as stream:
        json.dump({"token": token}, stream)
    try:
        if home.exists():
            if uid is None or uid <= 0:
                raise ValueError("The existing controller home requires its verified unprivileged account")
            lock_path = home / "controller.lock"
            try:
                fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                os.fchown(fd, uid, -1)
            except FileExistsError:
                fd = os.open(lock_path, os.O_RDWR | os.O_NOFOLLOW)
            with os.fdopen(fd, "r+") as lock:
                owned(os.fstat(lock.fileno()), uid)
                if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
                    raise ValueError("Controller lock is not an owned regular file")
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise ValueError("Acceptance or retirement is active; no lifecycle mutation is allowed") from None
        return token
    except Exception:
        release(path, token, owner)
        raise


def main():
    from ansible.module_utils.basic import AnsibleModule

    module = AnsibleModule(
        argument_spec=dict(
            state=dict(type="str", choices=["present", "absent"], required=True),
            data_dir=dict(type="path"),
            uid=dict(type="int"),
            token=dict(type="str"),
        ),
        required_if=[("state", "present", ["data_dir"]), ("state", "absent", ["token"])],
        supports_check_mode=True,
    )
    if module.check_mode:
        module.exit_json(changed=False)
    try:
        if module.params["state"] == "present":
            token = acquire(DRAIN, Path(module.params["data_dir"]), module.params["uid"])
            module.exit_json(changed=False, token=token)
        release(DRAIN, module.params["token"])
        module.exit_json(changed=False)
    except (OSError, ValueError):
        module.fail_json(
            msg="Runner maintenance lock could not be acquired/released; active work and retained ownership are preserved. Inspect the drain receipt before scoped recovery."
        )


if __name__ == "__main__":
    main()
