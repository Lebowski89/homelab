from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from ansible.errors import AnsibleFilterError

VALID_RUNTIMES = {"docker", "podman"}


def _as_list(value: Any, *, name: str = "value") -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, Iterable) and not isinstance(value, Mapping):
        return list(value)
    raise AnsibleFilterError(f"{name} must be a string or list, got {type(value).__name__}")


def _as_bool(value: Any, *, name: str = "value", default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "on", "1"}:
            return True
        if normalized in {"false", "no", "off", "0"}:
            return False
    raise AnsibleFilterError(f"{name} must be boolean-like true/false, got {value!r}. Use enabled: true or enabled: false.")


def _runtime(value: Any, *, name: str) -> str:
    runtime = str(value or "docker").strip().lower()
    if runtime not in VALID_RUNTIMES:
        raise AnsibleFilterError(f"{name} must be one of: docker, podman; got {runtime!r}")
    return runtime


def _unique(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    out: list[Any] = []
    for value in values:
        key = str(value)
        if key not in seen:
            seen.add(key)
            out.append(value)
    return out


def service_catalog_effective(services: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(services, Mapping):
        raise AnsibleFilterError(f"services must be a mapping, got {type(services).__name__}")
    out: list[dict[str, Any]] = []
    for service_name, service_cfg in services.items():
        if not isinstance(service_cfg, Mapping):
            raise AnsibleFilterError(f"Service {service_name!r} must be a mapping, got {type(service_cfg).__name__}")
        runtime = _runtime(service_cfg.get("runtime", "docker"), name=f"{service_name}.runtime")
        service_enabled = _as_bool(service_cfg.get("enabled", True), name=f"{service_name}.enabled", default=True)
        service_tags = _unique([service_name] + _as_list(service_cfg.get("tags", []), name=f"{service_name}.tags"))
        targets = service_cfg.get("targets")
        if targets is None:
            out.append({"name": service_name, "tags": service_tags, "enabled": service_enabled, "runtime": runtime})
            continue
        if not isinstance(targets, Mapping):
            raise AnsibleFilterError(f"{service_name}.targets must be a mapping, got {type(targets).__name__}")
        for target_name, target_cfg in targets.items():
            if not isinstance(target_cfg, Mapping):
                raise AnsibleFilterError(f"{service_name}.targets.{target_name} must be a mapping, got {type(target_cfg).__name__}")
            target_runtime = _runtime(target_cfg.get("runtime", runtime), name=f"{service_name}.targets.{target_name}.runtime")
            target_enabled = _as_bool(target_cfg.get("enabled", True), name=f"{service_name}.targets.{target_name}.enabled", default=True)
            target_tags = _unique(
                service_tags + [target_name] + _as_list(target_cfg.get("tags", []), name=f"{service_name}.targets.{target_name}.tags")
            )
            out.append(
                {
                    "name": service_name,
                    "target": target_name,
                    "tags": target_tags,
                    "enabled": service_enabled and target_enabled,
                    "runtime": target_runtime,
                }
            )
    return out


def service_catalog_select(
    items: list[Mapping[str, Any]], run_tags: list[str] | None = None, run_all: bool = False, allow_disabled: bool = False
) -> dict[str, Any]:
    run_tags_set = set(_as_list(run_tags or [], name="run_tags"))
    run_all_bool = _as_bool(run_all, name="run_all", default=False)
    allow_disabled_bool = _as_bool(allow_disabled, name="allow_disabled", default=False)
    matched: list[Mapping[str, Any]] = []
    selected: list[Mapping[str, Any]] = []
    for item in items:
        if not isinstance(item, Mapping):
            raise AnsibleFilterError(f"Selection item must be a mapping, got {type(item).__name__}")
        item_name = str(item.get("name", "")).strip()
        _runtime(item.get("runtime", "docker"), name=f"{item_name}.runtime")
        item_tags = set(_as_list(item.get("tags", []), name=f"{item_name}.tags"))
        if not (run_all_bool or not run_tags_set or item_name in run_tags_set or bool(item_tags.intersection(run_tags_set))):
            continue
        matched.append(item)
        item_enabled = _as_bool(item.get("enabled", True), name=f"{item_name}.enabled", default=True)
        if item_enabled or allow_disabled_bool:
            selected.append(item)
    return {"matched": matched, "selected": selected, "disabled_only": len(matched) > 0 and len(selected) == 0}


def service_catalog_by_runtime(items: list[Mapping[str, Any]], runtime: str) -> list[Mapping[str, Any]]:
    wanted = _runtime(runtime, name="runtime")
    return [item for item in items if _runtime(item.get("runtime", "docker"), name=f"{item.get('name', 'item')}.runtime") == wanted]


class FilterModule:
    def filters(self) -> dict[str, Any]:
        return {
            "service_catalog_effective": service_catalog_effective,
            "service_catalog_select": service_catalog_select,
            "service_catalog_by_runtime": service_catalog_by_runtime,
        }
