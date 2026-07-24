from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

from ansible.errors import AnsibleFilterError

_VALID_ACTIONS = {"append", "replace", "append_unique"}
_VALID_STACK_DEPLOY_TYPES = {"swarm", "container"}


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _as_str(value: Any) -> str:
    return str(value).strip()


def _normalize_action(value: Any) -> str:
    action = "append" if value is None else _as_str(value)

    if action not in _VALID_ACTIONS:
        raise AnsibleFilterError(f"list field action must be one of {sorted(_VALID_ACTIONS)}, got {action!r}.")

    return action


def _as_bool(value: Any, *, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value in {0, 1}:
            return bool(value)
        raise AnsibleFilterError(f"{name} must be boolean-like true/false or integer 0/1, got {value!r}")
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "on", "1"}:
            return True
        if normalized in {"false", "no", "off", "0"}:
            return False
    raise AnsibleFilterError(f"{name} must be boolean-like true/false or integer 0/1, got {value!r}")


def docker_services_no_new_privileges_security_opts(
    value: Any,
    stack_deploy_type: Any = "swarm",
) -> list[str]:
    deploy_type = _as_str(stack_deploy_type or "swarm")
    if deploy_type not in _VALID_STACK_DEPLOY_TYPES:
        raise AnsibleFilterError(f"stack_deploy_type must be one of {sorted(_VALID_STACK_DEPLOY_TYPES)}, got {deploy_type!r}.")

    enabled = _as_bool(value, name="no_new_privileges")
    if enabled and deploy_type == "swarm":
        raise AnsibleFilterError("no_new_privileges: true is only supported for Docker container deploys, not Swarm.")

    return ["no-new-privileges:true"] if enabled else []


def docker_services_string_list(value: Any = None) -> list[str]:
    """
    Normalize common compose list fields to list[str].

    Supported input:
    - None -> []
    - string -> [trimmed string], unless empty
    - mapping -> list of trimmed mapping values
    - iterable -> list of trimmed items

    Empty values are removed.
    """

    if value is None:
        return []

    if isinstance(value, str):
        item = value.strip()
        return [item] if item else []

    if _is_mapping(value):
        raw_items = list(value.values())
    elif isinstance(value, Iterable):
        raw_items = list(value)
    else:
        raw_items = [value]

    return [item for item in (_as_str(raw_item) for raw_item in raw_items) if item]


def docker_services_merge_string_list(
    existing: Any = None,
    new: Any = None,
    action: Any = "append",
) -> list[str]:
    """
    Merge common compose string-list fields.

    Actions:
    - append: existing + new
    - replace: new
    - append_unique: existing + new, keeping first occurrence
    """

    merge_action = _normalize_action(action)

    existing_items = docker_services_string_list(existing)
    new_items = docker_services_string_list(new)

    if merge_action == "replace":
        return new_items

    if merge_action == "append":
        return existing_items + new_items

    seen: set[str] = set()
    merged: list[str] = []

    for item in existing_items + new_items:
        if item in seen:
            continue

        seen.add(item)
        merged.append(item)

    return merged


def docker_services_set_service_field(
    compose_services: Any,
    service_name: Any,
    field_name: Any,
    value: Any,
) -> dict[str, Any]:
    """
    Return docker_services_compose_services with one service field updated.

    This mirrors the repeated Ansible combine pattern:

    docker_services_compose_services[service_name][field_name] = value

    Existing service keys are preserved.
    """

    if compose_services is None:
        compose_services = {}

    if not _is_mapping(compose_services):
        raise AnsibleFilterError(f"compose_services must be a mapping, got {type(compose_services).__name__}.")

    service = _as_str(service_name)
    field = _as_str(field_name)

    if not service:
        raise AnsibleFilterError("service_name must be a non-empty string.")

    if not field:
        raise AnsibleFilterError("field_name must be a non-empty string.")

    result = deepcopy(dict(compose_services))
    existing_service = result.get(service, {})

    if existing_service is None:
        existing_service = {}

    if not _is_mapping(existing_service):
        raise AnsibleFilterError(f"compose_services[{service!r}] must be a mapping, got {type(existing_service).__name__}.")

    updated_service = deepcopy(dict(existing_service))
    updated_service[field] = deepcopy(value)
    result[service] = updated_service

    return result


class FilterModule:
    def filters(self) -> dict[str, Any]:
        return {
            "docker_services_string_list": docker_services_string_list,
            "docker_services_merge_string_list": docker_services_merge_string_list,
            "docker_services_no_new_privileges_security_opts": docker_services_no_new_privileges_security_opts,
            "docker_services_set_service_field": docker_services_set_service_field,
        }
