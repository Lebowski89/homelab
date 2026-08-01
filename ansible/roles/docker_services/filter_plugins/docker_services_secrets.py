"""Render Docker secret attachments and standalone bind mounts for Ansible.

The Docker adapter uses these filters after runtime-neutral secret declaration
normalization. Swarm services receive Compose secret attachments, while
standalone services receive read-only bind mounts from the stack's materialized
secret directory. Secret values are never accepted or returned here.
"""

from __future__ import annotations

import json
import posixpath
import re
from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

from ansible.errors import AnsibleFilterError

_RESOURCE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SECRET_ACTIONS = {"deploy", "bootstrap", "update", "recreate", "remove"}


def _resource_name(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or not _RESOURCE_NAME_RE.fullmatch(value.strip()):
        raise AnsibleFilterError(f"{name} must be a valid Docker secret resource name")
    return value.strip()


def docker_services_secret_policy(secret: Any, action: Any, exists: Any = False) -> dict[str, bool]:
    """Translate a canonical secret update policy into Docker task decisions.

    Missing secrets are always materialized. Existing secrets are reconciled
    only when their policy is ``reconcile`` and the action is ``update`` or
    ``recreate``. The ``overwrite`` result is used for standalone secret files;
    Swarm tasks use ``materialize`` to decide whether to invoke Docker's
    content-aware secret module.

    Args:
        secret: Secret declaration containing an optional ``update_policy``.
        action: One of the supported service lifecycle actions.
        exists: Exact boolean indicating whether the runtime resource exists.

    Returns:
        Boolean ``materialize``, ``reconcile``, and ``overwrite`` decisions.

    Raises:
        AnsibleFilterError: If the declaration, policy, action, or existence
            flag is invalid.

    Note:
        Inputs are not mutated and secret values are neither inspected nor
        returned.
    """
    if not isinstance(secret, Mapping):
        raise AnsibleFilterError("secret must be a mapping")
    update_policy = secret.get("update_policy", "preserve")
    if not isinstance(update_policy, str) or update_policy not in {"preserve", "reconcile"}:
        raise AnsibleFilterError('secret.update_policy must be exactly "preserve" or "reconcile"')
    if not isinstance(action, str) or action not in _SECRET_ACTIONS:
        raise AnsibleFilterError("action must be deploy, bootstrap, update, recreate, or remove")
    if not isinstance(exists, bool):
        raise AnsibleFilterError("exists must be a boolean")
    reconcile = update_policy == "reconcile" and action in {"update", "recreate"}
    return {
        "materialize": not exists or reconcile,
        "reconcile": exists and reconcile,
        "overwrite": reconcile,
    }


def docker_services_secret_inspection(result: Any, secret: Any) -> dict[str, Any]:
    """Classify an exact Docker Swarm secret inspection without its value.

    Args:
        result: Result from ``docker secret inspect``.
        secret: Current normalized declaration, used only for its resource name.

    Returns:
        The secret name plus ``exists`` and ``ansible_managed`` booleans.

    Raises:
        AnsibleFilterError: If inputs or successful inspection JSON are invalid.

    Note:
        Docker inspection does not return secret data. The returned mapping and
        all errors contain resource metadata only.
    """
    if not isinstance(result, Mapping):
        raise AnsibleFilterError("Docker secret inspection result must be a mapping")
    if not isinstance(secret, Mapping):
        raise AnsibleFilterError("secret must be a mapping")
    name = _resource_name(secret.get("name"), name="secret.name")
    try:
        rc = int(result.get("rc", 1))
    except (TypeError, ValueError) as exc:
        raise AnsibleFilterError(f"Docker secret inspection for {name!r} has an invalid return code") from exc
    if rc != 0:
        return {"name": name, "exists": False, "ansible_managed": False}
    try:
        payload = json.loads(result.get("stdout", ""))
    except (TypeError, json.JSONDecodeError) as exc:
        raise AnsibleFilterError(f"Docker secret inspection for {name!r} did not return valid JSON") from exc
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], Mapping):
        raise AnsibleFilterError(f"Docker secret inspection for {name!r} did not return one secret")
    spec = payload[0].get("Spec", {})
    if not isinstance(spec, Mapping):
        raise AnsibleFilterError(f"Docker secret inspection for {name!r} has invalid metadata")
    labels = spec.get("Labels") or {}
    if not isinstance(labels, Mapping):
        raise AnsibleFilterError(f"Docker secret inspection for {name!r} has invalid labels")
    return {"name": name, "exists": True, "ansible_managed": "ansible_key" in labels}


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
    """Combine legacy and canonical Docker secret attachments.

    Legacy string or mapping attachments are retained in input order. Only
    declarations marked with the ``canonical`` origin are added. Swarm targets
    must be direct children of ``/run/secrets`` and are rendered as filenames;
    standalone-container targets remain absolute paths. Canonical metadata can
    replace a legacy string attachment for the same source.

    Args:
        legacy_secrets: Existing string or iterable containing string and
            mapping attachment declarations.
        declarations: Iterable of runtime-neutral secret declaration mappings.
        stack_deploy_type: ``swarm`` or ``container``.

    Returns:
        Compose-compatible secret attachment strings and mappings. No secret
        values are included.

    Raises:
        AnsibleFilterError: If deploy type, declaration shapes, resource names,
            targets, or supported attachment metadata are invalid.

    Note:
        Both input collections are left unchanged.
    """
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
    """Convert standalone Docker secret attachments into read-only bind mounts.

    Args:
        secrets: String or iterable of attachment strings/mappings. Relative
            mapping targets are placed directly under ``/run/secrets``.
        stack_name: Stack resource name used to locate materialized files below
            ``/opt/stacks/<stack>/secrets``.

    Returns:
        Bind-mount dictionaries containing source, target, and
        ``read_only: true``.

    Raises:
        AnsibleFilterError: If collection entries, resource names, stack name,
            or mapping targets are invalid.

    Note:
        The input attachment declaration is not mutated.
    """
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
    """Register Docker secret-rendering filters with Ansible."""

    def filters(self) -> dict[str, Any]:
        """Return the Jinja filters exposed by this plugin.

        Returns:
            A mapping exposing Docker secret policy, inspection, attachment,
            and standalone mount filters.
        """
        return {
            "docker_services_secret_policy": docker_services_secret_policy,
            "docker_services_secret_inspection": docker_services_secret_inspection,
            "docker_services_secret_attachments": docker_services_secret_attachments,
            "docker_services_secret_mounts": docker_services_secret_mounts,
        }
