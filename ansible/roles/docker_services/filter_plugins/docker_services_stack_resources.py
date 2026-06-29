from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

from ansible.errors import AnsibleFilterError

_VALID_RESOURCE_TYPES = {"networks", "volumes"}


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _as_str(value: Any, *, default: str = "") -> str:
    if value is None:
        return default

    return str(value).strip()


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


def _normalize_resource_type(value: Any) -> str:
    resource_type = _as_str(value)

    if resource_type not in _VALID_RESOURCE_TYPES:
        raise AnsibleFilterError(f"stack_resource_type must be one of {sorted(_VALID_RESOURCE_TYPES)}, got {resource_type!r}.")

    return resource_type


def docker_services_normalize_stack_resources(
    value: Any,
    *,
    default_external: bool = True,
) -> dict[str, dict[str, Any]]:
    """
    Normalize stack-level named networks/volumes into compose resource mappings.

    Supported input:
    - mapping:
        app_net:
          external: true

    - list:
        - app_net
        - shared_net

    List input becomes:
        app_net:
          external: true

    Mapping entries without 'external' get external=true by default.
    Non-mapping mapping values become {'external': true}.
    Empty names are ignored.
    """

    if value is None:
        raise AnsibleFilterError("stack resources must be provided.")

    resources: dict[str, dict[str, Any]] = {}

    if isinstance(value, str):
        raise AnsibleFilterError("stack resources must be a mapping or list of names, not a string.")

    if _is_mapping(value):
        for raw_name, raw_definition in value.items():
            name = _as_str(raw_name)

            if not name:
                continue

            definition = deepcopy(dict(raw_definition)) if _is_mapping(raw_definition) else {}

            if "external" not in definition:
                definition["external"] = default_external

            resources[name] = definition

        return resources

    if isinstance(value, Iterable):
        for raw_name in value:
            name = _as_str(raw_name)

            if not name:
                continue

            resources[name] = {
                "external": default_external,
            }

        return resources

    raise AnsibleFilterError(f"stack resources must be a mapping or list of names, got {type(value).__name__}.")


def docker_services_merge_stack_resources(
    compose_stacks: Any,
    stack_name: Any,
    resource_type: Any,
    resources: Any,
    *,
    default_external: bool = True,
) -> dict[str, Any]:
    """
    Merge named stack networks/volumes into docker_services_compose_stacks.

    Equivalent to:

    compose_stacks[stack_name][resource_type] =
      existing_resources recursive-merged with normalized resources
    """

    if compose_stacks is None:
        compose_stacks = {}

    if not _is_mapping(compose_stacks):
        raise AnsibleFilterError(f"compose_stacks must be a mapping, got {type(compose_stacks).__name__}.")

    stack = _as_str(stack_name)

    if not stack:
        raise AnsibleFilterError("docker_services_stack_name must be a non-empty string.")

    normalized_resource_type = _normalize_resource_type(resource_type)

    new_resources = docker_services_normalize_stack_resources(
        resources,
        default_external=default_external,
    )

    result = deepcopy(dict(compose_stacks))
    existing_stack = result.get(stack, {})

    if existing_stack is None:
        existing_stack = {}

    if not _is_mapping(existing_stack):
        raise AnsibleFilterError(f"compose_stacks[{stack!r}] must be a mapping, got {type(existing_stack).__name__}.")

    existing_stack_dict = deepcopy(dict(existing_stack))
    existing_resources = existing_stack_dict.get(normalized_resource_type, {})

    if existing_resources is None:
        existing_resources = {}

    if not _is_mapping(existing_resources):
        raise AnsibleFilterError(
            f"compose_stacks[{stack!r}][{normalized_resource_type!r}] must be a mapping, got {type(existing_resources).__name__}."
        )

    existing_stack_dict[normalized_resource_type] = _recursive_merge(
        existing_resources,
        new_resources,
    )
    result[stack] = existing_stack_dict

    return result


class FilterModule:
    def filters(self) -> dict[str, Any]:
        return {
            "docker_services_normalize_stack_resources": docker_services_normalize_stack_resources,
            "docker_services_merge_stack_resources": docker_services_merge_stack_resources,
        }
