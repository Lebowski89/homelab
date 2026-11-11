"""Plan explicit bind-mount labeling without changing host or runtime state."""

from collections.abc import Mapping
from pathlib import PurePosixPath

from ansible.errors import AnsibleFilterError

_MODES = {"preserve", "shared", "private"}


def _items(value):
    return list(value.values()) if isinstance(value, Mapping) else list(value or [])


def service_storage_plan(service, runtime, deployment="container"):
    """Keep legacy mounts unchanged; automatic labeling requires an owned path."""
    if runtime not in {"docker", "podman"}:
        raise AnsibleFilterError("Storage labeling requires the selected Docker or Podman adapter")
    mounts, paths = [], []
    for volume in _items(service.get("volumes", [])):
        if not isinstance(volume, Mapping):
            raise AnsibleFilterError("Storage volumes must be mappings")
        mode = volume.get("selinux", "preserve")
        if not isinstance(mode, str) or mode not in _MODES:
            raise AnsibleFilterError("Bind selinux must be preserve, shared or private")
        if "selinux" in volume and volume.get("type", "bind") != "bind":
            raise AnsibleFilterError("SELinux labeling is supported only for bind mounts")
        if volume.get("type", "bind") != "bind":
            continue
        source = volume.get("source", "")
        mounts.append({"source": source, "target": volume.get("target", ""), "selinux": mode})
        if mode == "preserve":
            continue
        if runtime == "docker" and deployment == "swarm" and mode == "private":
            raise AnsibleFilterError(
                "Docker Swarm cannot apply private bind labels; choose explicit shared host labeling or preserve an operator policy"
            )
        if (
            not isinstance(source, str)
            or not source.startswith("/")
            or str(PurePosixPath(source)) != source
            or ".." in PurePosixPath(source).parts
        ):
            raise AnsibleFilterError("Automatic SELinux labeling requires a normalized absolute bind source")
        owned = [path for path in service.get("paths", []) if isinstance(path, Mapping) and path.get("path") == source]
        owned_files = [
            entry
            for key in ("templates", "copies")
            for entry in service.get(key, [])
            if isinstance(entry, Mapping) and entry.get("dest") == source
        ]
        if not owned and len(owned_files) == 1:
            owned = [{"state": "file"}]
        if len(owned) != 1 or owned[0].get("state", "directory") not in {"directory", "file", "touch"}:
            raise AnsibleFilterError(
                "Automatic SELinux labeling requires one matching owned path or managed file; preserve externally managed/shared storage"
            )
        paths.append(
            {"path": source, "recurse": owned[0].get("state", "directory") == "directory", "setype": "container_file_t", "selevel": "s0"}
        )
    for index, mount in enumerate(mounts):
        for other in mounts[index + 1 :]:
            source, other_source = mount["source"], other["source"]
            if not isinstance(source, str) or not isinstance(other_source, str):
                continue
            overlap = (
                source == other_source
                or source.startswith(other_source.rstrip("/") + "/")
                or other_source.startswith(source.rstrip("/") + "/")
            )
            if overlap and mount["selinux"] != other["selinux"] and "private" in {mount["selinux"], other["selinux"]}:
                raise AnsibleFilterError("Private bind labeling cannot overlap another mount with a different SELinux policy")
    return {
        "mounts": mounts,
        "paths": [path for index, path in enumerate(paths) if path not in paths[:index]],
        "persistent": runtime == "docker" and deployment == "swarm",
    }


class FilterModule:
    def filters(self):
        return {"service_storage_plan": service_storage_plan}
