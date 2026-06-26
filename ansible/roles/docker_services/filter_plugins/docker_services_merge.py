from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from ansible.errors import AnsibleFilterError


_REPLACE_KEYS = {
    "command",
    "entrypoint",
}


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _list_append_rp(base: list[Any], override: list[Any]) -> list[Any]:
    """
    Approximate Ansible combine(list_merge='append_rp') semantics.

    Keep base entries that are not also present in override, then append override.
    This lets target lists extend parent lists while replacing exact duplicates.
    """
    result = []

    for item in base:
        if item not in override:
            result.append(deepcopy(item))

    result.extend(deepcopy(override))
    return result


def _merge_recursive_append_rp(base: Any, override: Any) -> Any:
    if _is_mapping(base) and _is_mapping(override):
        merged = deepcopy(dict(base))

        for key, override_value in override.items():
            if key in merged:
                merged[key] = _merge_recursive_append_rp(merged[key], override_value)
            else:
                merged[key] = deepcopy(override_value)

        return merged

    if isinstance(base, list) and isinstance(override, list):
        return _list_append_rp(base, override)

    return deepcopy(override)


def _pop_targets(service_cfg: Mapping[str, Any]) -> dict[str, Any]:
    base = deepcopy(dict(service_cfg))
    base.pop("targets", None)
    return base


def _target_cfg(service_cfg: Mapping[str, Any], target_name: str) -> Mapping[str, Any]:
    targets = service_cfg.get("targets", {})

    if not _is_mapping(targets):
        raise AnsibleFilterError(
            f"docker_services_merge_target expected 'targets' to be a mapping, "
            f"got {type(targets).__name__}"
        )

    if target_name not in targets:
        available = ", ".join(str(key) for key in targets.keys()) or "none"
        raise AnsibleFilterError(
            f"docker_services_merge_target target {target_name!r} was not found. "
            f"Available targets: {available}"
        )

    target = targets[target_name]

    if not _is_mapping(target):
        raise AnsibleFilterError(
            f"docker_services_merge_target expected target {target_name!r} to be a mapping, "
            f"got {type(target).__name__}"
        )

    return target


def _copy_if_defined(merged: dict[str, Any], target: Mapping[str, Any], key: str) -> None:
    if key in target:
        merged[key] = deepcopy(target[key])


def _copy_healthcheck_test_if_defined(
    merged: dict[str, Any],
    target: Mapping[str, Any],
) -> None:
    target_healthcheck = target.get("healthcheck")

    if not _is_mapping(target_healthcheck):
        return

    if "test" not in target_healthcheck:
        return

    merged_healthcheck = merged.get("healthcheck")

    if not _is_mapping(merged_healthcheck):
        merged_healthcheck = {}

    merged_healthcheck = deepcopy(dict(merged_healthcheck))
    merged_healthcheck["test"] = deepcopy(target_healthcheck["test"])
    merged["healthcheck"] = merged_healthcheck


def docker_services_merge_target(
    service_cfg: Mapping[str, Any],
    target_name: str | None = None,
) -> dict[str, Any]:
    """
    Merge a docker_services parent service config with one target.

    Behaviour:
    - parent 'targets' key is removed from final service config
    - mappings merge recursively
    - lists append with append_rp-like semantics
    - target command replaces parent command
    - target entrypoint replaces parent entrypoint
    - target healthcheck.test replaces parent healthcheck.test
    """

    if not _is_mapping(service_cfg):
        raise AnsibleFilterError(
            f"docker_services_merge_target expected service_cfg to be a mapping, "
            f"got {type(service_cfg).__name__}"
        )

    base = _pop_targets(service_cfg)

    if target_name is None or str(target_name).strip() == "":
        return base

    target_name = str(target_name).strip()
    target = _target_cfg(service_cfg, target_name)

    merged = _merge_recursive_append_rp(base, target)

    for key in _REPLACE_KEYS:
        _copy_if_defined(merged, target, key)

    _copy_healthcheck_test_if_defined(merged, target)

    return merged


class FilterModule:
    def filters(self) -> dict[str, Any]:
        return {
            "docker_services_merge_target": docker_services_merge_target,
        }
