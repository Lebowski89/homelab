"""Provide runtime-neutral service catalog filters to Ansible.

These filters build lightweight Docker and Podman selection metadata, select
and partition that metadata, and materialize a canonical base-plus-target
configuration only when dispatch needs it. This keeps shared catalog facts
small while giving both runtime adapters identical target merge semantics.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

from ansible.errors import AnsibleFilterError

VALID_RUNTIMES = {"docker", "podman"}
_REPLACE_LIST_KEYS = {"command", "entrypoint"}


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


def _list_append_rp(base: list[Any], override: list[Any]) -> list[Any]:
    """Return append-rp list semantics without reusing mutable input values.

    Base entries also present in the override are removed before copied override
    entries are appended. Relative ordering within each remaining group is
    preserved.
    """
    result = [deepcopy(item) for item in base if item not in override]
    result.extend(deepcopy(override))
    return result


def _merge_recursive_append_rp(base: Any, override: Any) -> Any:
    """Recursively merge mappings and append-rp lists into independent values."""
    if isinstance(base, Mapping) and isinstance(override, Mapping):
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


def _target_config(service_cfg: Mapping[str, Any], target_name: str) -> Mapping[str, Any]:
    targets = service_cfg.get("targets", {})
    if not isinstance(targets, Mapping):
        raise AnsibleFilterError(f"service_catalog_merge_target expected targets to be a mapping, got {type(targets).__name__}")
    if target_name not in targets:
        available = ", ".join(str(key) for key in targets) or "none"
        raise AnsibleFilterError(f"service_catalog_merge_target target {target_name!r} was not found. Available targets: {available}")
    target = targets[target_name]
    if not isinstance(target, Mapping):
        raise AnsibleFilterError(
            f"service_catalog_merge_target expected target {target_name!r} to be a mapping, got {type(target).__name__}"
        )
    if "targets" in target:
        raise AnsibleFilterError(f"service_catalog_merge_target target {target_name!r} must not contain nested targets")
    return target


def service_catalog_merge_target(service_cfg: Mapping[str, Any], target_name: str | None = None) -> dict[str, Any]:
    """Materialize one canonical base or base-plus-target configuration.

    Mappings merge recursively. Ordinary lists use append-rp behavior, while
    ``command`` and ``entrypoint`` lists replace their base values. A target's
    ``healthcheck.test`` also replaces rather than appends. The result never
    contains the base ``targets`` mapping.

    Args:
        service_cfg: Base service definition, optionally containing a
            ``targets`` mapping.
        target_name: Target to merge. ``None`` and blank names request only the
            base configuration.

    Returns:
        A deep-copied effective service mapping that can be passed to either
        runtime adapter.

    Raises:
        AnsibleFilterError: If ``service_cfg`` or ``targets`` is not a mapping,
            the requested target is absent or not a mapping, or the target
            contains nested ``targets``.

    Note:
        Neither the base definition nor the selected target is mutated.
    """
    if not isinstance(service_cfg, Mapping):
        raise AnsibleFilterError(f"service_catalog_merge_target expected service_cfg to be a mapping, got {type(service_cfg).__name__}")

    base = deepcopy(dict(service_cfg))
    base.pop("targets", None)
    if target_name is None or str(target_name).strip() == "":
        return base

    normalized_target_name = str(target_name).strip()
    target = _target_config(service_cfg, normalized_target_name)
    merged = _merge_recursive_append_rp(base, target)

    for key in _REPLACE_LIST_KEYS:
        if key in target:
            merged[key] = deepcopy(target[key])

    target_healthcheck = target.get("healthcheck")
    if isinstance(target_healthcheck, Mapping) and "test" in target_healthcheck:
        merged_healthcheck = merged.get("healthcheck", {})
        if not isinstance(merged_healthcheck, Mapping):
            merged_healthcheck = {}
        merged_healthcheck = deepcopy(dict(merged_healthcheck))
        merged_healthcheck["test"] = deepcopy(target_healthcheck["test"])
        merged["healthcheck"] = merged_healthcheck

    return merged


def _unique(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    out: list[Any] = []
    for value in values:
        key = str(value)
        if key not in seen:
            seen.add(key)
            out.append(value)
    return out


def _effective_section(
    service_cfg: Mapping[str, Any],
    target_cfg: Mapping[str, Any] | None,
    key: str,
    *,
    name: str,
) -> dict[str, Any]:
    base_value = service_cfg.get(key, {})
    if target_cfg is None or key not in target_cfg:
        value = base_value
    else:
        target_value = target_cfg[key]
        value = (
            _merge_recursive_append_rp(base_value, target_value)
            if isinstance(base_value, Mapping) and isinstance(target_value, Mapping)
            else target_value
        )

    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise AnsibleFilterError(f"{name}.{key} must be a mapping, got {type(value).__name__}")
    return dict(value)


def _dispatch_host(
    service_name: str,
    runtime: str,
    service_cfg: Mapping[str, Any],
    target_cfg: Mapping[str, Any] | None,
    docker_manager: str,
    *,
    name: str,
) -> str:
    """Resolve and validate the inventory host that must process one record.

    Docker Swarm services dispatch to the supplied manager. Standalone Docker
    services use ``deploy.host`` with the manager as fallback. Podman services
    prefer ``deploy.host``, then legacy ``container.host``, then the service
    name.
    """
    deploy = _effective_section(service_cfg, target_cfg, "deploy", name=name)
    container = _effective_section(service_cfg, target_cfg, "container", name=name)

    if runtime == "docker":
        deploy_type = str(deploy.get("type", "swarm") or "swarm").strip()
        raw_host = docker_manager if deploy_type == "swarm" else (deploy.get("host") or docker_manager)
    else:
        raw_host = deploy.get("host") or container.get("host") or service_name

    if not isinstance(raw_host, str) or not raw_host.strip():
        raise AnsibleFilterError(f"{name} dispatch host must be a non-empty string, got {raw_host!r}")
    return raw_host.strip()


def service_catalog_effective(services: Mapping[str, Any], docker_manager: Any) -> list[dict[str, Any]]:
    """Expand service definitions into lightweight dispatch metadata.

    A missing base runtime defaults to Docker. A service without targets
    produces one item; a service with targets produces one item per target.
    Target runtime can override base runtime, target tags extend de-duplicated
    base tags, and base and target enabled states are combined. Dispatch hosts
    are resolved in the current inventory context, but complete service
    configurations are deliberately not embedded.

    Args:
        services: Mapping of service names to canonical service definitions.
        docker_manager: Non-empty inventory hostname used for Docker Swarm and
            as the standalone Docker fallback.

    Returns:
        Ordered metadata records containing ``name``, ``tags``, ``enabled``,
        ``runtime``, and ``dispatch_host``, plus ``target`` where applicable.

    Raises:
        AnsibleFilterError: If the catalog or one of its service/target sections
            has an invalid shape; a runtime, enabled value, or tag value is
            invalid; nested targets are declared; or a dispatch host cannot be
            resolved to a non-empty string.

    Note:
        Input service definitions are not mutated.
    """
    if not isinstance(services, Mapping):
        raise AnsibleFilterError(f"services must be a mapping, got {type(services).__name__}")
    if not isinstance(docker_manager, str) or not docker_manager.strip():
        raise AnsibleFilterError(f"docker_manager must be a non-empty string, got {docker_manager!r}")
    normalized_docker_manager = docker_manager.strip()
    out: list[dict[str, Any]] = []
    for service_name, service_cfg in services.items():
        if not isinstance(service_cfg, Mapping):
            raise AnsibleFilterError(f"Service {service_name!r} must be a mapping, got {type(service_cfg).__name__}")

        service_runtime = _runtime(service_cfg.get("runtime", "docker"), name=f"{service_name}.runtime")
        service_enabled = _as_bool(service_cfg.get("enabled", True), name=f"{service_name}.enabled", default=True)
        service_tags = _unique([service_name] + _as_list(service_cfg.get("tags", []), name=f"{service_name}.tags"))
        targets = service_cfg.get("targets")

        if targets is None:
            out.append(
                {
                    "name": service_name,
                    "tags": service_tags,
                    "enabled": service_enabled,
                    "runtime": service_runtime,
                    "dispatch_host": _dispatch_host(
                        service_name,
                        service_runtime,
                        service_cfg,
                        None,
                        normalized_docker_manager,
                        name=service_name,
                    ),
                }
            )
            continue

        if not isinstance(targets, Mapping):
            raise AnsibleFilterError(f"{service_name}.targets must be a mapping, got {type(targets).__name__}")

        for target_name, target_cfg in targets.items():
            if not isinstance(target_cfg, Mapping):
                raise AnsibleFilterError(f"{service_name}.targets.{target_name} must be a mapping, got {type(target_cfg).__name__}")
            if "targets" in target_cfg:
                raise AnsibleFilterError(f"{service_name}.targets.{target_name} must not contain nested targets")

            target_runtime = _runtime(target_cfg.get("runtime", service_runtime), name=f"{service_name}.targets.{target_name}.runtime")
            target_enabled = _as_bool(target_cfg.get("enabled", True), name=f"{service_name}.targets.{target_name}.enabled", default=True)
            target_tags = _unique(
                service_tags + [target_name] + _as_list(target_cfg.get("tags", []), name=f"{service_name}.targets.{target_name}.tags")
            )
            target_path = f"{service_name}.targets.{target_name}"
            out.append(
                {
                    "name": service_name,
                    "target": target_name,
                    "tags": target_tags,
                    "enabled": service_enabled and target_enabled,
                    "runtime": target_runtime,
                    "dispatch_host": _dispatch_host(
                        service_name,
                        target_runtime,
                        service_cfg,
                        target_cfg,
                        normalized_docker_manager,
                        name=target_path,
                    ),
                }
            )
    return out


def service_catalog_select(
    items: list[Mapping[str, Any]], run_tags: list[str] | None = None, run_all: bool = False, allow_disabled: bool = False
) -> dict[str, Any]:
    """Select catalog metadata by service name, tag, and enabled state.

    An empty requested-tag list matches every supplied item. ``run_all`` also
    matches all items. Disabled matches are retained only when
    ``allow_disabled`` is true.

    Args:
        items: Lightweight catalog records in processing order.
        run_tags: Optional service names or tags to match.
        run_all: Boolean-like value that bypasses name and tag matching.
        allow_disabled: Boolean-like value that includes disabled matches.

    Returns:
        ``matched`` and ``selected`` lists plus ``disabled_only``, which is true
        only when records matched but enabled-state filtering removed all of
        them. Returned lists contain the original item mappings.

    Raises:
        AnsibleFilterError: If an item is not a mapping or a runtime, tag value,
            or boolean-like input is invalid.

    Note:
        The input sequence and its records are not mutated.
    """
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
    """Return catalog records handled by one supported runtime adapter.

    Args:
        items: Catalog records whose ``runtime`` values should be inspected.
        runtime: Requested runtime name, normalized case-insensitively. Supported
            values are ``docker`` and ``podman``.

    Returns:
        Records matching the requested runtime, preserving input order and
        object identity.

    Raises:
        AnsibleFilterError: If the requested runtime or an item's runtime is not
            supported.

    Note:
        The input list and member mappings are not mutated.
    """
    wanted = _runtime(runtime, name="runtime")
    return [item for item in items if _runtime(item.get("runtime", "docker"), name=f"{item.get('name', 'item')}.runtime") == wanted]


class FilterModule:
    """Register runtime-neutral service catalog filters with Ansible."""

    def filters(self) -> dict[str, Any]:
        """Return the Jinja filters exposed by this plugin.

        Returns:
            A mapping exposing ``service_catalog_effective``,
            ``service_catalog_merge_target``, ``service_catalog_select``, and
            ``service_catalog_by_runtime``.
        """
        return {
            "service_catalog_effective": service_catalog_effective,
            "service_catalog_merge_target": service_catalog_merge_target,
            "service_catalog_select": service_catalog_select,
            "service_catalog_by_runtime": service_catalog_by_runtime,
        }
