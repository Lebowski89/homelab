"""Normalize and merge Docker Compose labels for Ansible tasks.

The Docker role uses these filters to accept mapping or ``key=value`` list
declarations and to combine labels with explicit replacement, uniqueness, and
precedence policies before constructing Compose service dictionaries.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

from ansible.errors import AnsibleFilterError

_VALID_ACTIONS = {"append", "replace", "append_unique"}
_VALID_PRECEDENCE = {"new_wins", "existing_wins"}


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _as_str(value: Any, *, default: str = "") -> str:
    if value is None:
        return default

    return str(value).strip()


def _normalize_action(value: Any) -> str:
    action = _as_str(value, default="append")

    if action not in _VALID_ACTIONS:
        raise AnsibleFilterError(f"labels_action must be one of {sorted(_VALID_ACTIONS)}, got {action!r}.")

    return action


def _normalize_precedence(value: Any) -> str:
    precedence = _as_str(value, default="new_wins")

    if precedence not in _VALID_PRECEDENCE:
        raise AnsibleFilterError(f"labels_precedence must be one of {sorted(_VALID_PRECEDENCE)}, got {precedence!r}.")

    return precedence


def _recursive_merge(base: Any, override: Any) -> Any:
    if _is_mapping(base) and _is_mapping(override):
        merged = deepcopy(dict(base))

        for key, value in override.items():
            if key in merged:
                merged[key] = _recursive_merge(merged[key], value)
            else:
                merged[key] = deepcopy(value)

        return merged

    return deepcopy(override)


def _labels_from_sequence(value: Iterable[Any]) -> dict[str, str]:
    labels: dict[str, str] = {}

    for item in value:
        text = str(item).strip()

        if not text or "=" not in text:
            continue

        key, label_value = text.split("=", 1)
        key = key.strip()

        if not key:
            continue

        labels[key] = label_value.strip()

    return labels


def docker_services_canonical_labels(value: Any = None) -> dict[str, Any]:
    """Normalize one label declaration into a Compose label mapping.

    Mapping keys are stripped and empty keys ignored; values are deep-copied
    without coercion. Iterable declarations are parsed as ``key=value`` strings,
    ignoring malformed or empty entries and retaining the last repeated key.

    Args:
        value: ``None``, a label mapping, or an iterable of ``key=value`` items.

    Returns:
        A new normalized label mapping.

    Raises:
        AnsibleFilterError: If ``value`` is a bare string or is neither a
            mapping nor an iterable.

    Note:
        The input declaration is not mutated.
    """
    if value is None:
        return {}

    if isinstance(value, str):
        raise AnsibleFilterError("labels must be a mapping or list of key=value strings, not a string.")

    if _is_mapping(value):
        labels: dict[str, Any] = {}

        for key, label_value in value.items():
            normalized_key = _as_str(key)

            if not normalized_key:
                continue

            labels[normalized_key] = deepcopy(label_value)

        return labels

    if isinstance(value, Iterable):
        return _labels_from_sequence(value)

    raise AnsibleFilterError(f"labels must be a mapping or list of key=value strings, got {type(value).__name__}.")


def docker_services_merge_labels(
    existing: Any = None,
    labels: Any = None,
    action: Any = "append",
    precedence: Any = "new_wins",
) -> dict[str, Any]:
    """Merge existing and new Compose labels according to explicit policy.

    ``replace`` returns only new labels. ``append_unique`` retains existing
    values for duplicate top-level keys. ``append`` recursively merges nested
    mappings and uses ``precedence`` to choose which side wins conflicts.

    Args:
        existing: Existing label mapping or iterable declaration.
        labels: New label mapping or iterable declaration.
        action: One of ``append``, ``replace``, or ``append_unique``.
        precedence: For ``append``, either ``new_wins`` or ``existing_wins``.

    Returns:
        A newly allocated merged label mapping.

    Raises:
        AnsibleFilterError: If a declaration shape, action, or precedence value
            is unsupported.

    Note:
        Neither input declaration is mutated.
    """
    merge_action = _normalize_action(action)
    merge_precedence = _normalize_precedence(precedence)

    existing_labels = docker_services_canonical_labels(existing)
    new_labels = docker_services_canonical_labels(labels)

    if merge_action == "replace":
        return new_labels

    if merge_action == "append_unique":
        merged = deepcopy(existing_labels)

        for key, value in new_labels.items():
            if key not in merged:
                merged[key] = deepcopy(value)

        return merged

    if merge_precedence == "new_wins":
        return _recursive_merge(existing_labels, new_labels)

    return _recursive_merge(new_labels, existing_labels)


class FilterModule:
    """Register Docker label filters with Ansible."""

    def filters(self) -> dict[str, Any]:
        """Return the Jinja filters exposed by this plugin.

        Returns:
            A mapping exposing ``docker_services_canonical_labels`` and
            ``docker_services_merge_labels``.
        """
        return {
            "docker_services_canonical_labels": docker_services_canonical_labels,
            "docker_services_merge_labels": docker_services_merge_labels,
        }
