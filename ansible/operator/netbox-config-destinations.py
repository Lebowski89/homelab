"""Surgical destination transition for the retained LSIO NetBox configuration.

The approved cutover controller calls apply only after a matching verified cold
backup, stopped-writer checks and ownership verification. This module does not
execute configuration, access credentials, manage services or select endpoints.
"""

import ast
import base64
import hashlib
import ipaddress
import os
import re
import stat
import uuid
from pathlib import Path

FIELDS = {
    ("DATABASES", "default", "HOST"): ("database", 0),
    ("DATABASES", "default", "PORT"): ("database", 1),
    ("REDIS", "tasks", "HOST"): ("redis", 0),
    ("REDIS", "tasks", "PORT"): ("redis", 1),
    ("REDIS", "caching", "HOST"): ("redis", 0),
    ("REDIS", "caching", "PORT"): ("redis", 1),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def endpoints(values):
    require(isinstance(values, dict) and set(values) == {"database", "redis"}, "destination set differs")
    result = {}
    for provider, pair in values.items():
        require(isinstance(pair, (list, tuple)) and len(pair) == 2, "destination pair is incomplete")
        host, port = pair
        require(isinstance(host, str) and host and len(host) <= 253, "destination host is invalid")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            require(
                all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label) for label in host.split(".")),
                "destination host is invalid",
            )
        require(type(port) is int and 1 <= port <= 65535, "destination port is invalid")
        result[provider] = (host, port)
    return result


def literals(source):
    try:
        tree = ast.parse(source.decode("utf-8"))
    except (SyntaxError, ValueError, UnicodeError):
        raise ValueError("configuration is not valid Python; source withheld") from None
    roots = {}
    protected = {"DATABASES", "REDIS", "DATABASE"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            require(
                all(alias.name != "*" and (alias.asname or alias.name.split(".")[0]) not in protected for alias in node.names),
                "import can replace destination definitions",
            )
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.arg, ast.ExceptHandler)):
            binding = node.arg if isinstance(node, ast.arg) else node.name
            require(binding not in protected, "configuration binds destination names elsewhere")
    for name in ("DATABASES", "REDIS"):
        references = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == name]
        require(len(references) == 1 and isinstance(references[0].ctx, ast.Store), "configuration overrides or references destinations")
        assignments = [n for n in tree.body if isinstance(n, ast.Assign) and len(n.targets) == 1 and n.targets[0] is references[0]]
        require(len(assignments) == 1, "destination assignment is ambiguous")
        roots[name] = assignments[0].value
    require(not any(isinstance(n, ast.Name) and n.id == "DATABASE" for n in ast.walk(tree)), "legacy database assignment differs")
    require(
        not any(
            (isinstance(n, ast.Name) and n.id in {"exec", "eval", "globals", "locals"})
            or (isinstance(n, ast.Attribute) and n.attr in {"exec", "eval", "globals", "locals"})
            for n in ast.walk(tree)
        ),
        "dynamic configuration cannot establish destination continuity",
    )

    def member(node, key):
        require(isinstance(node, ast.Dict), "destination mapping is not literal")
        keys = [n.value if isinstance(n, ast.Constant) and isinstance(n.value, str) else None for n in node.keys]
        require(None not in keys and len(keys) == len(set(keys)), "destination mapping has ambiguous keys")
        require(key in keys, "required destination field is missing")
        return node.values[keys.index(key)]

    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    result = {}
    for path in FIELDS:
        node = roots[path[0]]
        for key in path[1:]:
            node = member(node, key)
        require(isinstance(node, ast.Constant), "destination value is not literal")
        value = node.value
        if path[-1] == "HOST":
            require(isinstance(value, str), "destination host is not textual")
        else:
            require(type(value) is int or (isinstance(value, str) and value.isascii() and value.isdecimal()), "port type differs")
            require(1 <= int(value) <= 65535, "destination port is invalid")
        result[path] = (value, offsets[node.lineno - 1] + node.col_offset, offsets[node.end_lineno - 1] + node.end_col_offset)
    return result


def rewrite(source, before, after):
    """Return changed bytes and state; never evaluate or log the configuration."""
    require(isinstance(source, bytes), "configuration must be bytes")
    before, after = endpoints(before), endpoints(after)
    fields = literals(source)

    def matches(values):
        return all(
            (value if path[-1] == "HOST" else int(value)) == values[FIELDS[path][0]][FIELDS[path][1]]
            for path, (value, _, _) in fields.items()
        )

    if matches(after):
        return source, False
    require(matches(before), "persisted destinations changed or contain a mixed transition")
    rewritten = source
    for path, (value, start, end) in sorted(fields.items(), key=lambda row: row[1][1], reverse=True):
        replacement = after[FIELDS[path][0]][FIELDS[path][1]]
        if isinstance(value, str):
            replacement = str(replacement)
        rewritten = rewritten[:start] + repr(replacement).encode("ascii") + rewritten[end:]
    parsed = literals(rewritten)
    require(
        all((v if path[-1] == "HOST" else int(v)) == after[FIELDS[path][0]][FIELDS[path][1]] for path, (v, _, _) in parsed.items()),
        "rewritten destinations differ",
    )
    return rewritten, True


def read_snapshot(path):
    """Reject aliases and return the exact single-file identity and metadata."""
    path = Path(path)
    require(path.is_absolute() and path.resolve() == path, "configuration path has an alias")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
        require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size <= 1024 * 1024, "configuration type/link/size differs")
        with os.fdopen(os.dup(fd), "rb") as stream:
            source = stream.read(1024 * 1024 + 1)
        attrs = {k: base64.b64encode(os.getxattr(fd, k)).decode("ascii") for k in os.listxattr(fd)}
        end = os.fstat(fd)

        def stable(s):
            return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)

        require(stable(st) == stable(end) == stable(path.lstat()), "configuration changed during inspection")
        snapshot = {
            "identity": [st.st_dev, st.st_ino],
            "owner": [st.st_uid, st.st_gid],
            "mode": stat.S_IMODE(st.st_mode),
            "nlink": st.st_nlink,
            "size": st.st_size,
            "mtime_ns": st.st_mtime_ns,
            "ctime_ns": st.st_ctime_ns,
            "sha256": hashlib.sha256(source).hexdigest(),
            "xattrs": attrs,
        }
        return source, snapshot
    finally:
        os.close(fd)


def apply(path, expected, before, after):
    """Replace only the verified file, preserving owner, mode and every xattr/ACL."""
    path = Path(path)
    source, observed = read_snapshot(path)
    require(observed == expected, "configuration identity or metadata changed")
    rewritten, changed = rewrite(source, before, after)
    if not changed:
        return observed, False
    temp = path.with_name(".skynet-netbox-destinations-" + uuid.uuid4().hex)
    created = None
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        created = (os.fstat(fd).st_dev, os.fstat(fd).st_ino)
        with os.fdopen(fd, "wb") as stream:
            stream.write(rewritten)
            stream.flush()
            if [os.fstat(stream.fileno()).st_uid, os.fstat(stream.fileno()).st_gid] != observed["owner"]:
                os.fchown(stream.fileno(), *observed["owner"])
            os.fchmod(stream.fileno(), observed["mode"])
            for key, value in observed["xattrs"].items():
                os.setxattr(stream.fileno(), key, base64.b64decode(value))
            os.fsync(stream.fileno())
        replacement, meta = read_snapshot(temp)
        require(replacement == rewritten, "replacement contents differ")
        require(all(meta[k] == observed[k] for k in ("owner", "mode", "nlink", "xattrs")), "replacement metadata differs")
        require(read_snapshot(path)[1] == observed, "configuration changed before replacement")
        os.replace(temp, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        final, metadata = read_snapshot(path)
        require(final == rewritten and all(metadata[k] == meta[k] for k in meta if k != "ctime_ns"), "installed configuration differs")
        return metadata, True
    finally:
        try:
            leftover = temp.lstat()
        except FileNotFoundError:
            pass
        else:
            require(created == (leftover.st_dev, leftover.st_ino) and stat.S_ISREG(leftover.st_mode), "temporary file identity differs")
            temp.unlink()
