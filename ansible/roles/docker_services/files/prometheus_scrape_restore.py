#!/usr/bin/env python3
"""Restore one verified scrape-file baseline, rejecting concurrent file changes."""

import fcntl
import hashlib
import json
import os
import stat
import sys
import tempfile
from pathlib import Path


def read_owned(path, expected):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    stream = os.fdopen(fd, "rb")
    info = os.fstat(fd)
    if not (stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == expected):
        stream.close()
        raise ValueError("configuration ownership, mode or file type changed")
    return stream, info


def restore(request):
    path = Path(request["path"])
    expected = (request["uid"], request["gid"], int(request["mode"], 8))
    with read_owned(request["backup"], expected)[0] as baseline:
        body = baseline.read()
    if hashlib.sha256(body).hexdigest() != request["baseline_sha256"]:
        raise ValueError("invocation baseline backup changed")
    current, info = read_owned(path, expected)
    with current:
        fcntl.flock(current, fcntl.LOCK_EX | fcntl.LOCK_NB)
        digest = hashlib.sha256(current.read()).hexdigest()
        if digest == request["baseline_sha256"]:
            return {"changed": False}
        if digest != request["candidate_sha256"] or (info.st_dev, info.st_ino, info.st_mtime) != (
            request["dev"],
            request["inode"],
            request["mtime"],
        ):
            raise ValueError("concurrent configuration edit; retained current file and invocation backup")
        fd, temporary = tempfile.mkstemp(prefix=".skynet-haproxy-restore-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(body)
                os.fchown(output.fileno(), *expected[:2])
                os.fchmod(output.fileno(), expected[2])
                output.flush()
                os.fsync(output.fileno())
            latest = path.lstat()
            if (latest.st_dev, latest.st_ino, latest.st_size, latest.st_mtime_ns, latest.st_ctime_ns) != (
                info.st_dev,
                info.st_ino,
                info.st_size,
                info.st_mtime_ns,
                info.st_ctime_ns,
            ):
                raise ValueError("configuration changed during recovery; retained current file")
            os.replace(temporary, path)
            parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return {"changed": True}


if __name__ == "__main__":
    try:
        print(json.dumps(restore(json.load(sys.stdin))))
    except (OSError, ValueError, KeyError) as error:
        sys.exit("Prometheus recovery: " + str(error))
