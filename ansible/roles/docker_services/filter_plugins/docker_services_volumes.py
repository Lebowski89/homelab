"""Normalize and merge Docker Compose volume declarations for Ansible.

The Docker role uses these filters to accept named mappings, lists, and legacy
single-volume fields, validate bind, named-volume, and tmpfs requirements, and
combine them with explicit append, replace, or de-duplication behavior.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

from ansible.errors import AnsibleFilterError

_VALID_VOLUME_TYPES = {"bind", "volume", "tmpfs"}
_VALID_ACTIONS = {"append", "replace", "append_unique"}


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _as_list(value: Any, *, name: str) -> list[Any]:
    if value is None:
        return []

    if isinstance(value, str):
        raise AnsibleFilterError(f"{name} must be a list or mapping of volume dicts, not a string.")

    if _is_mapping(value):
        return list(value.values())

    if isinstance(value, Iterable):
        return list(value)

    raise AnsibleFilterError(f"{name} must be a list or mapping of volume dicts.")


def _as_bool(value: Any, *, name: str) -> bool:
    if value is None:
        return False

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return bool(value)

    if isinstance(value, str):
        normalized = value.strip().lower()

        if normalized in {"true", "yes", "on", "1"}:
            return True

        if normalized in {"false", "no", "off", "0", ""}:
            return False

    raise AnsibleFilterError(f"{name} must be boolean-like true/false, got {value!r}.")


def _as_str(value: Any, *, default: str = "") -> str:
    if value is None:
        return default

    return str(value).strip()


def _normalize_tmpfs_options(value: Any, *, name: str) -> dict[str, Any]:
    if value is None:
        return {}

    if not _is_mapping(value):
        raise AnsibleFilterError(f"{name}.tmpfs must be a mapping when provided.")

    tmpfs = deepcopy(dict(value))

    if "size" in tmpfs:
        try:
            tmpfs["size"] = int(tmpfs["size"])
        except (TypeError, ValueError) as exc:
            raise AnsibleFilterError(f"{name}.tmpfs.size must be an integer.") from exc

        if tmpfs["size"] < 0:
            raise AnsibleFilterError(f"{name}.tmpfs.size must be >= 0.")

    return tmpfs


def _volume_key(volume: Mapping[str, Any]) -> tuple[Any, ...]:
    volume_type = _as_str(volume.get("type"), default="bind")

    if volume_type in {"bind", "volume"}:
        return (
            volume_type,
            _as_str(volume.get("source")),
            _as_str(volume.get("target")),
        )

    if volume_type == "tmpfs":
        return (
            "tmpfs",
            _as_str(volume.get("target")),
        )

    return (
        volume_type,
        _as_str(volume.get("target")),
    )


def _validate_existing_volumes(existing: Any) -> list[dict[str, Any]]:
    existing_list = _as_list(existing, name="existing volumes")

    for index, volume in enumerate(existing_list):
        if not _is_mapping(volume):
            raise AnsibleFilterError(f"existing volumes[{index}] must be a mapping, got {type(volume).__name__}.")

    return [deepcopy(dict(volume)) for volume in existing_list]


def _raw_new_volumes(
    volumes: Any,
    volumes_list: Any,
    paths_type: Any,
    paths_host: Any,
    paths_container: Any,
    paths_read_only: Any,
) -> list[Any]:
    if volumes is not None:
        return _as_list(volumes, name="volumes")

    if volumes_list is not None:
        return _as_list(volumes_list, name="volumes_list")

    return [
        {
            "type": _as_str(paths_type, default="bind"),
            "source": _as_str(paths_host),
            "target": _as_str(paths_container),
            "read_only": _as_bool(paths_read_only, name="paths_read_only"),
        }
    ]


def _canonicalize_volume(volume: Any, *, index: int) -> dict[str, Any]:
    if not _is_mapping(volume):
        raise AnsibleFilterError(f"volumes[{index}] must be a mapping, got {type(volume).__name__}.")

    volume_dict = dict(volume)
    volume_type = _as_str(volume_dict.get("type"), default="bind")
    source = _as_str(volume_dict.get("source"))
    target = _as_str(volume_dict.get("target"))

    if volume_type not in _VALID_VOLUME_TYPES:
        raise AnsibleFilterError(f"volumes[{index}].type must be one of {sorted(_VALID_VOLUME_TYPES)}, got {volume_type!r}.")

    if volume_type == "tmpfs":
        if not target:
            raise AnsibleFilterError(f"volumes[{index}].target is required for tmpfs volumes.")

        return {
            "type": "tmpfs",
            "target": target,
            "tmpfs": _normalize_tmpfs_options(
                volume_dict.get("tmpfs", {}),
                name=f"volumes[{index}]",
            ),
        }

    if not source:
        raise AnsibleFilterError(f"volumes[{index}].source is required for {volume_type} volumes.")

    if not target:
        raise AnsibleFilterError(f"volumes[{index}].target is required for {volume_type} volumes.")

    return {
        "type": volume_type,
        "source": source,
        "target": target,
        "read_only": _as_bool(
            volume_dict.get("read_only", False),
            name=f"volumes[{index}].read_only",
        ),
    }


def docker_services_canonical_volumes(
    volumes: Any = None,
    volumes_list: Any = None,
    paths_type: Any = "bind",
    paths_host: Any = "",
    paths_container: Any = "",
    paths_read_only: Any = False,
) -> list[dict[str, Any]]:
    """Normalize new volume declarations into Compose long syntax.

    ``volumes`` takes precedence over ``volumes_list``; when both are absent,
    legacy path arguments create one volume. Named mappings contribute their
    values in mapping order. Bind and named volumes require source and target;
    tmpfs volumes require a target and optionally accept a non-negative integer
    size.

    Args:
        volumes: Preferred list or named mapping of volume dictionaries.
        volumes_list: Legacy list or named mapping fallback.
        paths_type: Legacy type, defaulting to ``bind``.
        paths_host: Legacy source value.
        paths_container: Legacy target value.
        paths_read_only: Legacy boolean-like read-only flag.

    Returns:
        Newly allocated normalized volume dictionaries in declaration order.

    Raises:
        AnsibleFilterError: If declaration shapes, volume type, required fields,
            boolean values, or tmpfs options are invalid.

    Note:
        Input declarations are not mutated.
    """
    raw_volumes = _raw_new_volumes(
        volumes,
        volumes_list,
        paths_type,
        paths_host,
        paths_container,
        paths_read_only,
    )

    return [_canonicalize_volume(volume, index=index) for index, volume in enumerate(raw_volumes)]


def docker_services_merge_volumes(
    existing: Any = None,
    volumes: Any = None,
    volumes_list: Any = None,
    action: str = "append",
    paths_type: Any = "bind",
    paths_host: Any = "",
    paths_container: Any = "",
    paths_read_only: Any = False,
) -> list[dict[str, Any]]:
    """Merge existing and newly normalized Compose volumes.

    Existing entries must be mappings but otherwise remain as declared.
    ``append_unique`` de-duplicates bind and named volumes by type, source, and
    target, and tmpfs volumes by type and target, preserving the first entry.

    Args:
        existing: Existing list or named mapping of volume dictionaries.
        volumes: Preferred new list or named mapping.
        volumes_list: Legacy new-list fallback.
        action: ``append``, ``replace``, or ``append_unique``.
        paths_type: Legacy volume type.
        paths_host: Legacy source value.
        paths_container: Legacy target value.
        paths_read_only: Legacy boolean-like read-only flag.

    Returns:
        A newly allocated list following the requested merge policy.

    Raises:
        AnsibleFilterError: If action, existing entries, or new volume
            declarations are invalid.

    Note:
        Existing and new declarations are not mutated.
    """
    action = _as_str(action, default="append")

    if action not in _VALID_ACTIONS:
        raise AnsibleFilterError(f"volumes_action must be one of {sorted(_VALID_ACTIONS)}, got {action!r}.")

    existing_volumes = _validate_existing_volumes(existing)
    new_volumes = docker_services_canonical_volumes(
        volumes=volumes,
        volumes_list=volumes_list,
        paths_type=paths_type,
        paths_host=paths_host,
        paths_container=paths_container,
        paths_read_only=paths_read_only,
    )

    if action == "replace":
        return new_volumes

    if action == "append":
        return existing_volumes + new_volumes

    seen: set[tuple[Any, ...]] = set()
    merged: list[dict[str, Any]] = []

    for volume in existing_volumes + new_volumes:
        key = _volume_key(volume)

        if key in seen:
            continue

        seen.add(key)
        merged.append(volume)

    return merged


class FilterModule:
    """Register Docker volume filters with Ansible."""

    def filters(self) -> dict[str, Any]:
        """Return the Jinja filters exposed by this plugin.

        Returns:
            A mapping exposing ``docker_services_canonical_volumes`` and
            ``docker_services_merge_volumes``.
        """
        return {
            "docker_services_canonical_volumes": docker_services_canonical_volumes,
            "docker_services_merge_volumes": docker_services_merge_volumes,
        }
