from __future__ import annotations

import posixpath
import re
from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

from ansible.errors import AnsibleFilterError

_RESOURCE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _resource_name(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or not _RESOURCE_NAME_RE.fullmatch(value.strip()):
        raise AnsibleFilterError(f"{name} must be a valid Docker secret resource name")
    return value.strip()


def _entries(value: Any, *, name: str) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable) and not isinstance(value, Mapping):
        return list(value)
    raise AnsibleFilterError(f"{name} must be a string or list")


def _swarm_target(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not posixpath.isabs(value):
        raise AnsibleFilterError(f"{name} must be an absolute path")
    parent, filename = posixpath.split(value)
    if parent != "/run/secrets" or not filename:
        raise AnsibleFilterError(f"{name} must point directly beneath /run/secrets for Docker Swarm; got {value!r}")
    return filename


def docker_services_secret_attachments(
    legacy_secrets: Any,
    declarations: Any,
    stack_deploy_type: Any = "swarm",
) -> list[Any]:
    deploy_type = str(stack_deploy_type or "swarm").strip()
    if deploy_type not in {"swarm", "container"}:
        raise AnsibleFilterError("stack_deploy_type must be swarm or container")

    attachments: list[Any] = []
    seen: set[str] = set()
    positions: dict[str, int] = {}
    for index, entry in enumerate(_entries(legacy_secrets, name="legacy_secrets")):
        item_name = f"legacy_secrets[{index}]"
        if isinstance(entry, str):
            source = _resource_name(entry, name=item_name)
            positions[source] = len(attachments)
            attachments.append(source)
            seen.add(source)
            continue
        if not isinstance(entry, Mapping):
            raise AnsibleFilterError(f"{item_name} must be a string or mapping")
        unsupported = set(entry) - {"source", "target", "uid", "gid", "mode"}
        if unsupported:
            raise AnsibleFilterError(f"{item_name} contains unsupported fields: {', '.join(sorted(unsupported))}")
        source = _resource_name(entry.get("source"), name=f"{item_name}.source")
        target = entry.get("target")
        if not isinstance(target, str) or not target.strip():
            raise AnsibleFilterError(f"{item_name}.target must be a non-empty string")
        positions[source] = len(attachments)
        attachments.append(deepcopy(dict(entry)))
        seen.add(source)

    if declarations is None:
        declarations = []
    if isinstance(declarations, (str, Mapping)) or not isinstance(declarations, Iterable):
        raise AnsibleFilterError("secret declarations must be a list")
    for index, declaration in enumerate(declarations):
        item_name = f"secret_declarations[{index}]"
        if not isinstance(declaration, Mapping):
            raise AnsibleFilterError(f"{item_name} must be a mapping")
        if "canonical" not in declaration.get("origins", []):
            continue
        source = _resource_name(declaration.get("name"), name=f"{item_name}.name")
        target = declaration.get("target", f"/run/secrets/{source}")
        if deploy_type == "swarm":
            rendered_target = _swarm_target(target, name=f"{item_name}.target")
        else:
            if not isinstance(target, str) or not posixpath.isabs(target):
                raise AnsibleFilterError(f"{item_name}.target must be an absolute path")
            rendered_target = target
        metadata = {field: declaration[field] for field in ("uid", "gid", "mode") if field in declaration}
        if deploy_type == "swarm" and rendered_target == source and not metadata:
            attachment: Any = source
        else:
            attachment = {"source": source, "target": rendered_target, **metadata}
        if source in seen:
            if attachment != source:
                attachments[positions[source]] = attachment
            continue
        positions[source] = len(attachments)
        attachments.append(attachment)
        seen.add(source)
    return attachments


def docker_services_secret_mounts(secrets: Any, stack_name: Any) -> list[dict[str, Any]]:
    stack = _resource_name(str(stack_name), name="stack_name")
    mounts: list[dict[str, Any]] = []
    for index, entry in enumerate(_entries(secrets, name="secrets")):
        item_name = f"secrets[{index}]"
        if isinstance(entry, str):
            source = _resource_name(entry, name=item_name)
            target = f"/run/secrets/{source}"
        elif isinstance(entry, Mapping):
            source = _resource_name(entry.get("source"), name=f"{item_name}.source")
            raw_target = entry.get("target")
            if not isinstance(raw_target, str) or not raw_target.strip():
                raise AnsibleFilterError(f"{item_name}.target must be a non-empty string")
            target = raw_target.strip() if posixpath.isabs(raw_target.strip()) else f"/run/secrets/{raw_target.strip()}"
        else:
            raise AnsibleFilterError(f"{item_name} must be a string or mapping")
        mounts.append(
            {
                "type": "bind",
                "source": f"/opt/stacks/{stack}/secrets/{source}",
                "target": target,
                "read_only": True,
            }
        )
    return mounts


class FilterModule:
    def filters(self) -> dict[str, Any]:
        return {
            "docker_services_secret_attachments": docker_services_secret_attachments,
            "docker_services_secret_mounts": docker_services_secret_mounts,
        }
