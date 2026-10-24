#!/usr/bin/python
"""Inspect metadata only, and publish complete password files without replacement."""

from __future__ import annotations

import contextlib
import errno
import os
import pwd
import stat
import uuid

from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r"""
module: workstation_credential_files
short_description: Preserve or exclusively create workstation password files
description:
  - Internal filesystem half of the workstation credential setup action.
  - Inspection never reads password contents and rejects symlinks in all path components.
  - Existing regular files are never replaced and use mode 0600.
  - Only the configured private directory and newly created directories are secured to their owner with mode 0700.
  - Existing alternate password-file parents retain their ownership and permissions.
options:
  directory:
    type: path
    required: true
    description: Configured private secrets directory, excluding root, the managed user's home and its ancestors.
  vault_file:
    type: path
    required: true
    description: Configured Vault password destination.
  become_file:
    type: path
    required: true
    description: Configured managed-host sudo password destination.
  owner:
    type: str
    required: true
    description: Existing non-root workstation account.
  operation:
    type: str
    choices: [inspect, apply]
    default: inspect
    description: Inspect metadata or publish missing files.
  values:
    type: dict
    default: {}
    description: Private values supplied only by the interactive action.
author: Homelab maintainers
"""
EXAMPLES = """
- name: Inspect configured destinations without reading their contents
  workstation_credential_files:
    directory: /home/operator/.config/homelab
    vault_file: /home/operator/.config/homelab/.ansible_vault_pass
    become_file: /home/operator/.config/homelab/.ansible_become_pass
    owner: operator
"""
RETURN = r"""
missing:
  description: Credential kinds whose files are missing.
  type: list
  returned: always
created:
  description: Credential kinds created by this operation.
  type: list
  returned: always
"""


def path(value):
    if not os.path.isabs(value) or os.path.normpath(value) != value or value == "/" or any(c in value for c in "\x00\r\n"):
        raise ValueError("Credential paths must be normalized absolute paths, excluding the filesystem root.")
    return value


@contextlib.contextmanager
def directory_fd(destination, *, create=False, uid=None, gid=None, created=None):
    """Walk with directory descriptors so no ancestor symlink can be followed."""
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in destination.strip("/").split("/"):
            try:
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    yield None
                    return
                os.mkdir(component, 0o700, dir_fd=descriptor)
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
                os.fchown(child, uid, gid)
                os.fchmod(child, 0o700)
                if created is not None:
                    created.append(True)
            except OSError as error:
                if error.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise ValueError("Unsafe credential directory: symlinks and non-directories are forbidden.") from None
                raise
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


def regular(info):
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("Unsafe password destination: require a regular file with one link; symlinks and directories are forbidden.")


def metadata_differs(info, uid, gid, mode):
    return (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) != (uid, gid, mode)


def inspect(directories, files, uid, gid, private):
    changed = False
    missing = []
    for destination in directories:
        with directory_fd(destination) as descriptor:
            changed |= descriptor is None or (destination == private and metadata_differs(os.fstat(descriptor), uid, gid, 0o700))
    for kind, destination in files.items():
        with directory_fd(os.path.dirname(destination)) as descriptor:
            try:
                info = os.stat(os.path.basename(destination), dir_fd=descriptor, follow_symlinks=False) if descriptor is not None else None
            except FileNotFoundError:
                info = None
            if info is None:
                missing.append(kind)
                changed = True
            else:
                regular(info)
                changed |= metadata_differs(info, uid, gid, 0o600)
    return changed, missing


def secure_file(descriptor, name, uid, gid):
    # O_PATH permits metadata repair even on an unreadable file, without opening its data.
    fd = os.open(name, os.O_PATH | os.O_NOFOLLOW, dir_fd=descriptor)
    try:
        info = os.fstat(fd)
        regular(info)
        changed = metadata_differs(info, uid, gid, 0o600)
        if changed:
            reference = f"/proc/self/fd/{fd}"
            os.chown(reference, uid, gid)
            os.chmod(reference, 0o600)
        return changed
    finally:
        os.close(fd)


def publish(descriptor, name, value, uid, gid):
    temporary = ".workstation-credential-" + uuid.uuid4().hex
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=descriptor)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchown(stream.fileno(), uid, gid)
            os.fchmod(stream.fileno(), 0o600)
            stream.write(value.encode("utf-8") + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            # Unlike rename/copy replacement, link fails if any destination already exists.
            os.link(temporary, name, src_dir_fd=descriptor, dst_dir_fd=descriptor, follow_symlinks=False)
        except FileExistsError:
            return False
        os.fsync(descriptor)
        return True
    finally:
        os.unlink(temporary, dir_fd=descriptor)


def configure(parameters, check_mode):
    account = pwd.getpwnam(parameters["owner"])
    if account.pw_uid == 0:
        raise ValueError("Credential files require an existing non-root workstation account.")
    uid, gid = account.pw_uid, account.pw_gid
    private = path(parameters["directory"])
    if os.path.commonpath((private, os.path.normpath(account.pw_dir))) == private:
        raise ValueError("The private secrets directory cannot be the managed user's home or an ancestor of that home.")
    files = {kind: path(parameters[kind + "_file"]) for kind in ("vault", "become")}
    directories = sorted({private, *(path(os.path.dirname(value)) for value in files.values())})
    if len(set(files.values())) != 2 or any(
        directory == value or directory.startswith(value + "/") for directory in directories for value in files.values()
    ):
        raise ValueError("Vault and become destinations must be distinct files and cannot also be credential directories.")
    # Validate every directory and both destinations before changing any metadata
    # or publishing either password file.
    changed, missing = inspect(directories, files, uid, gid, private)
    if check_mode or parameters["operation"] == "inspect":
        return {"changed": changed, "missing": missing, "created": []}
    values = parameters["values"]
    for kind in missing:
        value = values.get(kind)
        if not isinstance(value, str) or not value.strip() or any(c in value for c in "\x00\r\n"):
            raise ValueError(
                "A required password is missing or invalid; no password files were written. Rerun interactive workstation_credentials setup."
            )
    changed = False
    made_directories = []
    for destination in directories:
        with directory_fd(destination, create=True, uid=uid, gid=gid, created=made_directories) as descriptor:
            if destination == private and metadata_differs(os.fstat(descriptor), uid, gid, 0o700):
                os.fchown(descriptor, uid, gid)
                os.fchmod(descriptor, 0o700)
                changed = True
    created = []
    for kind, destination in files.items():
        with directory_fd(os.path.dirname(destination)) as descriptor:
            name = os.path.basename(destination)
            if kind in missing and publish(descriptor, name, values[kind], uid, gid):
                created.append(kind)
            changed |= secure_file(descriptor, name, uid, gid)
    return {"changed": changed or bool(created) or bool(made_directories), "missing": [], "created": created}


def main():
    module = AnsibleModule(
        argument_spec={
            "directory": {"type": "path", "required": True},
            "vault_file": {"type": "path", "required": True},
            "become_file": {"type": "path", "required": True},
            "owner": {"type": "str", "required": True},
            "operation": {"choices": ["inspect", "apply"], "default": "inspect"},
            "values": {"type": "dict", "default": {}, "no_log": True},
        },
        supports_check_mode=True,
    )
    try:
        result = configure(module.params, module.check_mode)
    except ValueError as error:
        module.fail_json(msg=str(error))
    except (OSError, KeyError):
        module.fail_json(
            msg="Unable to safely access credential destinations as the managed workstation user. Check account permissions and configured paths."
        )
    module.exit_json(**result)


if __name__ == "__main__":
    main()
