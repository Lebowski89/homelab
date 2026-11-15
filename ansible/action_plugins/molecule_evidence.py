"""Publish private Molecule evidence in the confined controller's valid context.

New files inherit the writer's SELinux identity, not a policy default belonging
to system_u. This action never asks Ansible to relabel a newly published file.
"""

import errno
import os
import stat
import tempfile
from pathlib import Path

from ansible.errors import AnsibleActionFail
from ansible.plugins.action import ActionBase


def private_file(descriptor):
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise ValueError("Evidence must be an owned regular mode-0600 file")
    return info


def selinux_label(descriptor):
    try:
        return os.getxattr(descriptor, "security.selinux")
    except OSError as error:
        if error.errno not in {errno.ENODATA, errno.ENOTSUP, errno.EOPNOTSUPP}:
            raise
        return None


def write_evidence(destination, content, force=True, check=False):
    path = Path(destination)
    for parent in [*path.parents, path]:
        if parent.is_symlink():
            raise ValueError("Evidence paths must not traverse symlinks")
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = None
    try:
        info = os.fstat(directory)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError("Evidence directory must be owned and mode 0700")
        expected = content.encode("utf-8")
        previous = None
        label = None
        try:
            descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        except FileNotFoundError:
            pass
        else:
            with os.fdopen(descriptor, "rb") as stream:
                previous = private_file(stream.fileno())
                if not force or stream.read() == expected:
                    return False
                label = selinux_label(stream.fileno())
        if check:
            return True
        descriptor, name = tempfile.mkstemp(prefix=".molecule-evidence-", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(descriptor, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            if previous and os.fstat(stream.fileno()).st_gid != previous.st_gid:
                os.fchown(stream.fileno(), -1, previous.st_gid)
            if label is not None and selinux_label(stream.fileno()) != label:
                os.setxattr(stream.fileno(), "security.selinux", label)
            if label is not None and selinux_label(stream.fileno()) != label:
                raise ValueError("Evidence label did not preserve the destination context")
            private_file(stream.fileno())
            stream.write(expected)
            stream.flush()
            os.fsync(stream.fileno())
        # No destination is precreated. A losing first-observation publisher
        # retains the winner, including when publication races another writer.
        if not force:
            try:
                os.link(temporary, path, follow_symlinks=False)
            except FileExistsError:
                descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
                with os.fdopen(descriptor, "rb") as stream:
                    private_file(stream.fileno())
                return False
        else:
            if previous is not None and not os.path.samestat(previous, path.lstat()):
                raise ValueError("Evidence destination changed during preparation")
            os.replace(temporary, path)
        temporary.unlink(missing_ok=True)
        temporary = None
        os.fsync(directory)
        return True
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        os.close(directory)


class ActionModule(ActionBase):
    """Only delegated controller evidence writes; no remote or privilege work."""

    _requires_connection = False
    _supports_check_mode = True
    _VALID_ARGS = frozenset({"dest", "content", "mode", "force"})

    def run(self, tmp=None, task_vars=None):
        result = super().run(tmp, task_vars)
        args = self._task.args
        root = task_vars.get("molecule_vm_evidence_directory", task_vars.get("molecule_ephemeral_directory"))
        if (
            self._task.delegate_to != "localhost"
            or self._play_context.become
            or not isinstance(root, str)
            or not isinstance(args.get("dest"), str)
            or not Path(root).is_absolute()
            or Path(args["dest"]).parent != Path(root)
            or not isinstance(args.get("content"), str)
            or args.get("mode", "0600") != "0600"
            or type(args.get("force", True)) is not bool
        ):
            raise AnsibleActionFail(
                "Molecule evidence requires an explicit private controller directory and unprivileged localhost delegation"
            )
        try:
            result["changed"] = write_evidence(args["dest"], args["content"], args.get("force", True), self._task.check_mode)
        except (OSError, ValueError) as error:
            raise AnsibleActionFail("Private evidence publication failed; retain existing evidence for inspection") from error
        return result
