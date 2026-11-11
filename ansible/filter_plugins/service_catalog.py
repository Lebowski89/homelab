"""Provide runtime-neutral service catalog filters to Ansible.

These filters build lightweight Docker, Podman and native selection metadata, select
and partition that metadata, plan managed Podman namespace dependencies, and
materialize a canonical base-plus-target configuration only when dispatch needs
it. This keeps shared catalog facts small while giving the runtime adapters
identical target merge semantics.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

from ansible.errors import AnsibleFilterError

VALID_RUNTIMES = {"docker", "podman", "native"}
_NATIVE_FIELDS = {"enabled", "runtime", "tags", "name", "description", "native", "deploy", "operational_requirements"}
_REPLACE_LIST_KEYS = {"command", "entrypoint"}
_PODMAN_RESOURCE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SERVICE_ACTIONS = {"deploy", "update", "remove", "recreate", "bootstrap", "drift"}


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
    if not isinstance(value, str) or not value.strip():
        raise AnsibleFilterError(f"{name} must be a non-empty string containing one of: docker, podman, native; got {value!r}")
    runtime = value
    if runtime not in VALID_RUNTIMES:
        raise AnsibleFilterError(f"{name} must be one of: docker, podman, native; got {runtime!r}")
    return runtime


def _validate_runtime_fields(*, runtime: str, has_systemd: bool, name: str) -> None:
    if has_systemd and runtime != "podman":
        raise AnsibleFilterError(f"{name} declares top-level systemd, which is valid only with runtime: podman; got runtime: {runtime}")


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


def _native_merge(base, target):
    """A native target inherits application identity, never container process/state."""
    if set(target) - _NATIVE_FIELDS:
        raise AnsibleFilterError(f"Native declaration contains unsupported fields: {', '.join(sorted(set(target) - _NATIVE_FIELDS))}")
    for declaration in (base, target) if base["runtime"] == "native" else (target,):
        if "native" in declaration and not isinstance(declaration["native"], Mapping):
            raise AnsibleFilterError("native must be a mapping")
        if "config" in declaration.get("native", {}) and not isinstance(declaration["native"]["config"], Mapping):
            raise AnsibleFilterError("native.config must be a mapping")
    if base["runtime"] == "native":
        if set(base) - _NATIVE_FIELDS:
            raise AnsibleFilterError("Native base contains unsupported container fields")
        merged = _merge_recursive_append_rp(base, target)
        # Native settings are values, including empty lists/maps; they replace.
        if "config" in target.get("native", {}):
            merged["native"]["config"] = {**base.get("native", {}).get("config", {}), **target["native"]["config"]}
    else:
        # Crossing an adapter boundary is explicit. Inherited images, secrets,
        # ports, environment, storage and controller placement are inapplicable.
        merged = {key: base[key] for key in ("enabled", "tags", "description", "operational_requirements") if key in base}
        merged.update(deepcopy(dict(target)))
        merged["tags"] = _unique(_as_list(base.get("tags", [])) + _as_list(target.get("tags", [])))
    native = merged.get("native")
    if not isinstance(native, Mapping) or set(native) - {"application", "config", "update_policy"}:
        raise AnsibleFilterError("native must declare application/config and optional update_policy only")
    if native.get("application") not in {"alloy", "node_exporter", "keepalived", "technitium"}:
        raise AnsibleFilterError("native.application must select alloy, node_exporter, keepalived or technitium")
    if not isinstance(native.get("config"), Mapping):
        raise AnsibleFilterError("native.config must be a mapping")
    deploy = merged.get("deploy", {})
    if not isinstance(deploy, Mapping) or set(deploy) != {"hosts"}:
        raise AnsibleFilterError("Native placement requires deploy.hosts only")
    requirements = merged.get("operational_requirements", {})
    if not isinstance(requirements, Mapping) or requirements.get("acl") or requirements.get("ownership_transition"):
        raise AnsibleFilterError("Protected native endpoints/identity transitions require a verified host-listener firewall adapter")
    return merged


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
        A deep-copied effective service mapping that can be passed to the selected
        runtime adapter.

    Raises:
        AnsibleFilterError: If ``service_cfg`` or ``targets`` is not a mapping,
            the base or explicit target runtime is invalid, the requested
            target is absent or not a mapping, or the target contains nested
            ``targets``, or top-level ``systemd`` survives on a non-Podman
            effective service.

    Note:
        Neither the base definition nor the selected target is mutated.
    """
    if not isinstance(service_cfg, Mapping):
        raise AnsibleFilterError(f"service_catalog_merge_target expected service_cfg to be a mapping, got {type(service_cfg).__name__}")
    if "runtime" not in service_cfg:
        raise AnsibleFilterError("service_catalog_merge_target base service must explicitly declare runtime")
    _runtime(service_cfg["runtime"], name="service_catalog_merge_target service_cfg.runtime")

    base = deepcopy(dict(service_cfg))
    base.pop("targets", None)
    _placement_deploy(base.get("deploy", {}))
    if target_name is None or str(target_name).strip() == "":
        if base["runtime"] == "native":
            return _native_merge(base, {})
        _validate_runtime_fields(
            runtime=base["runtime"], has_systemd="systemd" in base, name="service_catalog_merge_target effective service"
        )
        return base

    normalized_target_name = str(target_name).strip()
    target = _target_config(service_cfg, normalized_target_name)
    _placement_deploy(target.get("deploy", {}))
    if "runtime" in target:
        _runtime(
            target["runtime"],
            name=f"service_catalog_merge_target target {normalized_target_name!r}.runtime",
        )
    if target.get("runtime", base["runtime"]) == "native":
        return _native_merge(base, target)
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

    _validate_runtime_fields(
        runtime=merged["runtime"],
        has_systemd="systemd" in merged,
        name=f"service_catalog_merge_target target {normalized_target_name!r}",
    )

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


def service_catalog_resolve_hosts(selections, inventory_groups):
    """Expand exact inventory host/group names using Ansible's full groups map.

    Inventory membership is independent of --limit. Preserve first-seen order
    across selections and group members, removing duplicate inventory names.
    """
    if not isinstance(inventory_groups, Mapping):
        raise AnsibleFilterError("deploy.hosts resolution requires Ansible inventory groups")
    values = [selections] if isinstance(selections, str) else selections
    if not isinstance(values, list) or not values:
        raise AnsibleFilterError("deploy.hosts must be a non-empty hostname, group or list of selections")
    known = {host for members in inventory_groups.values() for host in members}
    hosts = []
    for selection in values:
        if not isinstance(selection, str) or not selection.strip() or selection != selection.strip():
            raise AnsibleFilterError("deploy.hosts selections must be non-empty trimmed inventory names")
        if selection in inventory_groups:
            members = inventory_groups[selection]
            if not members:
                raise AnsibleFilterError(f"deploy.hosts inventory group {selection!r} has no hosts")
            hosts.extend(members)
        elif selection in known:
            hosts.append(selection)
        else:
            raise AnsibleFilterError(f"deploy.hosts selection {selection!r} is not an inventory host or group")
    return _unique(hosts)


def _placement_deploy(deploy):
    if not isinstance(deploy, Mapping):
        raise AnsibleFilterError("deploy must be a mapping")
    retired = set(deploy) & {"host", "group"}
    if retired:
        raise AnsibleFilterError("deploy.host/deploy.group are retired; use deploy.hosts alone (do not combine placement fields)")
    return deploy


def service_catalog_resolve_placement(service, inventory_groups):
    """Return canonical concrete placement, preserving every other deploy field."""
    deploy = _placement_deploy(service.get("deploy", {}))
    hosts = service_catalog_resolve_hosts(deploy.get("hosts"), inventory_groups)
    runtime = service.get("runtime", "docker")
    if (runtime == "podman" or (runtime == "docker" and str(deploy.get("type") or "swarm").strip() != "swarm")) and len(hosts) != 1:
        raise AnsibleFilterError(f"{runtime} standalone placement requires exactly one resolved host; got {hosts}")
    return {**service, "deploy": {**deploy, "hosts": hosts}}


def _effective_value(
    service_cfg: Mapping[str, Any],
    target_cfg: Mapping[str, Any] | None,
    key: str,
    default: Any = None,
) -> Any:
    if target_cfg is not None and key in target_cfg:
        return target_cfg[key]
    return service_cfg.get(key, default)


def _podman_lifecycle_metadata(
    service_name: str,
    target_name: str | None,
    service_cfg: Mapping[str, Any],
    target_cfg: Mapping[str, Any] | None,
    *,
    name: str,
) -> dict[str, Any]:
    default_name = service_name if target_name is None else f"{service_name}-{target_name}"
    container_name = _podman_resource_name(
        _effective_value(service_cfg, target_cfg, "name", default_name),
        name=f"{name}.name",
    )
    raw_network_mode = _effective_value(service_cfg, target_cfg, "network_mode")
    namespace_provider = None
    if raw_network_mode is not None and raw_network_mode not in ("host", "pasta"):
        if not isinstance(raw_network_mode, str):
            raise AnsibleFilterError(f'{name}.network_mode must use the constrained "container:<managed-container-name>" form')
        match = re.fullmatch(r"container:([A-Za-z0-9][A-Za-z0-9_.-]*)", raw_network_mode.strip())
        if match is None:
            raise AnsibleFilterError(f'{name}.network_mode must use the constrained "container:<managed-container-name>" form')
        namespace_provider = _podman_resource_name(
            match.group(1),
            name=f"{name}.network_mode container reference",
        )

    deploy = _effective_section(service_cfg, target_cfg, "deploy", name=name)
    execution = deploy.get("execution", {})
    execution_mode = execution.get("mode", "rootful") if isinstance(execution, Mapping) else "invalid"
    if raw_network_mode == "pasta" and execution_mode != "rootless":
        raise AnsibleFilterError(f"{name}.network_mode pasta requires rootless execution")
    metadata = {
        "container_name": container_name,
        "namespace_provider": namespace_provider,
        "execution_mode": execution_mode,
    }
    if execution_mode == "rootless":
        metadata["execution_account"] = execution.get("host_user")
    systemd = _effective_section(service_cfg, target_cfg, "systemd", name=name)
    start_dependencies = []
    for field in ("requires", "wants", "after"):
        units = systemd.get(field, [])
        if not isinstance(units, list) or any(not isinstance(unit, str) or not unit.strip() for unit in units):
            raise AnsibleFilterError(f"{name}.systemd.{field} must be a list of non-empty unit names")
        start_dependencies.extend(unit.strip() for unit in units)
    if start_dependencies:
        metadata["start_dependencies"] = start_dependencies
    return metadata


def service_catalog_effective(
    services: Mapping[str, Any], docker_manager: Any, inventory_groups=None, resolve_hosts=True, runtimes=None
) -> list[dict[str, Any]]:
    """Expand service definitions into lightweight dispatch metadata.

    Every base service must explicitly select Docker, Podman or native. A service
    without targets produces one item; a service with targets produces one item
    per target. Target runtime can override or inherit the validated base
    runtime, target tags extend de-duplicated base tags, and base and target
    enabled states are combined. Dispatch hosts are resolved in the current
    inventory context, but complete service configurations are deliberately not
    embedded.

    Args:
        services: Mapping of service names to canonical service definitions.
        docker_manager: Inventory hostname used to dispatch Docker Swarm deployments. May be empty for an identity-only index.
        inventory_groups: Ansible's complete inventory group membership for placement.
        resolve_hosts: False builds only identity/tag/runtime metadata before
            selecting runtime prerequisites; no placement variables are read.
        runtimes: Optional runtime restriction before reading placement.


    Returns:
        Ordered metadata records containing ``name``, ``tags``, ``enabled``,
        ``runtime``, ``resolved_hosts`` and ``dispatch_host``, plus ``target`` where applicable.
        Podman records also contain compact ``podman_lifecycle`` identity and
        namespace-reference metadata; unresolved placement carries a
        deferred ``placement_error`` without changing configured ``enabled``.
        Complete configurations are never embedded.

    Raises:
        AnsibleFilterError: If the catalog or one of its service/target sections
            has an invalid shape; a runtime, enabled value, or tag value is
            invalid; ``targets`` is explicitly empty; nested targets are
            declared; top-level ``systemd`` applies to a non-Podman effective
            service; or retired placement fields are declared. Inventory resolution errors
            are deferred until selection.

    Note:
        Input service definitions are not mutated.
    """
    if not isinstance(services, Mapping):
        raise AnsibleFilterError(f"services must be a mapping, got {type(services).__name__}")
    if not isinstance(resolve_hosts, bool):
        raise AnsibleFilterError("resolve_hosts must be a boolean")
    if not isinstance(docker_manager, str) or (resolve_hosts and not docker_manager.strip()):
        raise AnsibleFilterError(f"docker_manager must be a non-empty string, got {docker_manager!r}")
    normalized_docker_manager = docker_manager.strip()
    out: list[dict[str, Any]] = []
    inventory_groups = inventory_groups or {}

    def placement(item, service_cfg, target_cfg):
        if runtimes is not None and item["runtime"] not in runtimes:
            return None
        if not resolve_hosts:
            return item
        deploy = _effective_section(service_cfg, target_cfg, "deploy", name=item["name"])
        try:
            resolved = service_catalog_resolve_placement({"runtime": item["runtime"], "deploy": deploy}, inventory_groups)
            item["resolved_hosts"] = resolved["deploy"]["hosts"]
        except AnsibleFilterError as error:
            item["resolved_hosts"] = []
            identity = _catalog_label(_catalog_identity(item))
            item["placement_error"] = f"Service {identity!r}: {error}"
        item["dispatch_host"] = (
            normalized_docker_manager
            if item["runtime"] == "docker" and str(deploy.get("type") or "swarm").strip() == "swarm"
            else next(iter(item["resolved_hosts"]), "")
        )
        if item["runtime"] == "podman":
            item["podman_lifecycle"] = _podman_lifecycle_metadata(
                item["name"], item.get("target"), service_cfg, target_cfg, name=item["name"]
            )
        return item

    for service_name, service_cfg in services.items():
        if not isinstance(service_cfg, Mapping):
            raise AnsibleFilterError(f"Service {service_name!r} must be a mapping, got {type(service_cfg).__name__}")

        if "runtime" not in service_cfg:
            raise AnsibleFilterError(f"Service {service_name!r} must explicitly declare runtime as one of: docker, podman")
        _placement_deploy(service_cfg.get("deploy", {}))
        service_runtime = _runtime(service_cfg["runtime"], name=f"{service_name}.runtime")
        service_enabled = _as_bool(service_cfg.get("enabled", True), name=f"{service_name}.enabled", default=True)
        service_tags = _unique([service_name] + _as_list(service_cfg.get("tags", []), name=f"{service_name}.tags"))
        targets = service_cfg.get("targets")

        if targets is None:
            _validate_runtime_fields(runtime=service_runtime, has_systemd="systemd" in service_cfg, name=f"Service {service_name!r}")
            item = {
                "name": service_name,
                "tags": service_tags,
                "enabled": service_enabled,
                "runtime": service_runtime,
            }
            resolved = placement(item, service_cfg, None)
            if resolved is not None:
                out.append(resolved)
            continue

        if not isinstance(targets, Mapping):
            raise AnsibleFilterError(f"{service_name}.targets must be a mapping, got {type(targets).__name__}")
        if not targets:
            _validate_runtime_fields(
                runtime=service_runtime,
                has_systemd="systemd" in service_cfg,
                name=f"Service {service_name!r}",
            )
            raise AnsibleFilterError(f"{service_name}.targets must contain at least one target; omit targets for a base-only service")

        for target_name, target_cfg in targets.items():
            if not isinstance(target_cfg, Mapping):
                raise AnsibleFilterError(f"{service_name}.targets.{target_name} must be a mapping, got {type(target_cfg).__name__}")
            if "targets" in target_cfg:
                raise AnsibleFilterError(f"{service_name}.targets.{target_name} must not contain nested targets")

            _placement_deploy(target_cfg.get("deploy", {}))
            target_runtime = _runtime(target_cfg.get("runtime", service_runtime), name=f"{service_name}.targets.{target_name}.runtime")
            _validate_runtime_fields(
                runtime=target_runtime,
                has_systemd=("systemd" in service_cfg or "systemd" in target_cfg)
                if target_runtime != "native"
                else "systemd" in target_cfg,
                name=f"Service {service_name!r} target {target_name!r}",
            )
            target_enabled = _as_bool(target_cfg.get("enabled", True), name=f"{service_name}.targets.{target_name}.enabled", default=True)
            target_tags = _unique(
                service_tags + [target_name] + _as_list(target_cfg.get("tags", []), name=f"{service_name}.targets.{target_name}.tags")
            )
            item = {
                "name": service_name,
                "target": target_name,
                "tags": target_tags,
                "enabled": service_enabled and target_enabled,
                "runtime": target_runtime,
            }
            resolved = placement(item, service_cfg, target_cfg)
            if resolved is not None:
                out.append(resolved)
    return out


def service_catalog_select(
    items: list[Mapping[str, Any]],
    run_tags: list[str] | None = None,
    run_all: bool = False,
    allow_disabled: bool = False,
    action: str | None = None,
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
        action: Optional lifecycle action. Drift/bootstrap select container
            entries only; a selector referring exclusively to native entries
            fails instead of silently ignoring an explicit native request.

    Returns:
        ``matched`` and ``selected`` lists plus ``disabled_only``, which is true
        only when records matched but enabled-state filtering removed all of
        them. Returned lists contain the original item mappings.

    Raises:
        AnsibleFilterError: If an item is not a mapping or a runtime, tag value,
            or boolean-like input is invalid; a selected enabled placement is invalid;
            or a native-only selector requests an unsupported lifecycle action.

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
        _runtime(item.get("runtime"), name=f"{item_name}.runtime")
        item_tags = set(_as_list(item.get("tags", []), name=f"{item_name}.tags"))
        if not (run_all_bool or not run_tags_set or item_name in run_tags_set or bool(item_tags.intersection(run_tags_set))):
            continue
        matched.append(item)
        item_enabled = _as_bool(item.get("enabled", True), name=f"{item_name}.enabled", default=True)
        if item_enabled or allow_disabled_bool:
            selected.append(item)
    if action in {"drift", "bootstrap"}:
        native = [item for item in selected if item["runtime"] == "native"]
        supported = [item for item in selected if item["runtime"] != "native"]
        supported_tags = {tag for item in matched if item["runtime"] != "native" for tag in [item["name"], *item.get("tags", [])]}
        explicit_native = [
            item
            for item in matched
            if item["runtime"] == "native" and not run_all_bool and (run_tags_set - supported_tags) & {item["name"], *item.get("tags", [])}
        ]
        if explicit_native or (native and not supported):
            identities = [item["name"] + (":" + item["target"] if item.get("target") else "") for item in explicit_native or native]
            raise AnsibleFilterError(
                f"Native service selection {', '.join(identities)} does not support {action}; "
                "use deploy, update, recreate or remove (check previews deploy)"
            )
        selected = supported
    for item in selected:
        if item.get("placement_error"):
            raise AnsibleFilterError(item["placement_error"])
    return {"matched": matched, "selected": selected, "disabled_only": len(matched) > 0 and len(selected) == 0}


def service_catalog_by_runtime(items: list[Mapping[str, Any]], runtime: str) -> list[Mapping[str, Any]]:
    """Return catalog records handled by one supported runtime adapter.

    Args:
        items: Catalog records whose ``runtime`` values should be inspected.
        runtime: Exact requested runtime name: ``docker``, ``podman`` or
            ``native``.

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
    return [item for item in items if _runtime(item.get("runtime"), name=f"{item.get('name', 'item')}.runtime") == wanted]


def _catalog_identity(item: Mapping[str, Any]) -> tuple[str, str | None]:
    """Return the stable catalog identity for one lightweight record."""
    name = item.get("name")
    if not isinstance(name, str) or not name.strip():
        raise AnsibleFilterError(f"Catalog item name must be a non-empty string, got {name!r}")
    target = item.get("target")
    if target is not None and (not isinstance(target, str) or not target.strip()):
        raise AnsibleFilterError(f"Catalog item {name!r} target must be a non-empty string, got {target!r}")
    return name.strip(), target.strip() if isinstance(target, str) else None


def _catalog_label(identity: tuple[str, str | None]) -> str:
    return f"{identity[0]}:{identity[1]}" if identity[1] is not None else identity[0]


def _podman_resource_name(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or not _PODMAN_RESOURCE_NAME_RE.fullmatch(value.strip()):
        raise AnsibleFilterError(f"{name} must be a valid Quadlet resource name matching {_PODMAN_RESOURCE_NAME_RE.pattern}; got {value!r}")
    return value.strip()


def service_catalog_podman_lifecycle_plan(
    items: list[Mapping[str, Any]],
    selected: list[Mapping[str, Any]],
    action: str,
) -> dict[str, Any]:
    """Plan managed Podman container-namespace lifecycle dependencies.

    A rootful Podman service using ``network_mode: container:<name>`` depends
    on the same-host managed Podman service whose effective container name is
    ``<name>``. The returned selection is provider-first for ordinary actions
    and consumer-first for remove. Each selected Podman record also carries its
    transitively managed dependent services in recovery order so the runtime
    adapter can stop them before replacing the provider and restore only
    dependents that were active.

    Ordinary same-host Requires/Wants dependencies also order selected starts
    and removals, but never enter the namespace replacement transaction.

    References with no matching managed Podman service remain external and do
    not gain lifecycle edges. Docker records are never namespace providers.
    """
    if not isinstance(items, list):
        raise AnsibleFilterError(f"items must be a list, got {type(items).__name__}")
    if not isinstance(selected, list):
        raise AnsibleFilterError(f"selected must be a list, got {type(selected).__name__}")
    if action not in _SERVICE_ACTIONS:
        raise AnsibleFilterError(f"action must be one of: {', '.join(sorted(_SERVICE_ACTIONS))}; got {action!r}")

    records: dict[tuple[str, str | None], dict[str, Any]] = {}
    podman_ids: list[tuple[str, str | None]] = []
    providers_by_host_name: dict[tuple[str, str], list[tuple[str, str | None]]] = {}
    providers_by_name: dict[str, list[tuple[str, str | None]]] = {}

    for position, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise AnsibleFilterError(f"Catalog item {position} must be a mapping, got {type(item).__name__}")
        identity = _catalog_identity(item)
        if identity in records:
            raise AnsibleFilterError(f"Duplicate catalog identity {_catalog_label(identity)!r}")
        runtime = _runtime(item.get("runtime"), name=f"{_catalog_label(identity)}.runtime")
        record = {
            "item": item,
            "position": position,
            "runtime": runtime,
        }
        records[identity] = record
        if runtime != "podman":
            continue
        if item.get("placement_error"):
            if any(isinstance(entry, Mapping) and _catalog_identity(entry) == identity for entry in selected):
                raise AnsibleFilterError(item["placement_error"])
            continue

        lifecycle = item.get("podman_lifecycle")
        if not isinstance(lifecycle, Mapping):
            raise AnsibleFilterError(f"{_catalog_label(identity)} is missing lightweight Podman lifecycle metadata")
        container_name = _podman_resource_name(lifecycle.get("container_name"), name=f"{_catalog_label(identity)}.name")
        namespace_provider = lifecycle.get("namespace_provider")
        if namespace_provider is not None:
            namespace_provider = _podman_resource_name(
                namespace_provider,
                name=f"{_catalog_label(identity)}.network_mode container reference",
            )
        host = item.get("dispatch_host")
        if not isinstance(host, str) or not host.strip():
            raise AnsibleFilterError(f"{_catalog_label(identity)} dispatch host must be a non-empty string, got {host!r}")
        record.update(
            {
                "container_name": container_name,
                "host": host.strip(),
                "namespace_provider": namespace_provider,
                "execution_mode": lifecycle.get("execution_mode", "rootful"),
                "execution_account": lifecycle.get("execution_account"),
                "start_dependencies": lifecycle.get("start_dependencies", []),
            }
        )
        podman_ids.append(identity)
        providers_by_host_name.setdefault((host.strip(), container_name), []).append(identity)
        providers_by_name.setdefault(container_name, []).append(identity)

    selected_ids: list[tuple[str, str | None]] = []
    for position, item in enumerate(selected):
        if not isinstance(item, Mapping):
            raise AnsibleFilterError(f"Selected item {position} must be a mapping, got {type(item).__name__}")
        identity = _catalog_identity(item)
        if identity not in records:
            raise AnsibleFilterError(f"Selected item {_catalog_label(identity)!r} is not present in the effective catalog")
        selected_ids.append(identity)

    provider_for: dict[tuple[str, str | None], tuple[str, str | None]] = {}
    consumers_for: dict[tuple[str, str | None], list[tuple[str, str | None]]] = {identity: [] for identity in podman_ids}
    dependencies: list[dict[str, str]] = []
    for consumer_id in podman_ids:
        consumer = records[consumer_id]
        provider_name = consumer["namespace_provider"]
        if provider_name is None:
            continue
        if consumer["execution_mode"] != "rootful":
            raise AnsibleFilterError(
                f"{_catalog_label(consumer_id)} container namespace sharing requires rootful Podman; "
                f"got execution mode {consumer['execution_mode']!r}"
            )

        same_host = providers_by_host_name.get((consumer["host"], provider_name), [])
        if len(same_host) > 1:
            labels = ", ".join(_catalog_label(identity) for identity in same_host)
            raise AnsibleFilterError(
                f"{_catalog_label(consumer_id)} container namespace provider {provider_name!r} is ambiguous on "
                f"host {consumer['host']}: {labels}"
            )
        if not same_host:
            remote = providers_by_name.get(provider_name, [])
            if remote:
                locations = ", ".join(f"{_catalog_label(identity)} on {records[identity]['host']}" for identity in remote)
                raise AnsibleFilterError(
                    f"{_catalog_label(consumer_id)} on {consumer['host']} cannot share the host-local network namespace "
                    f"of managed Podman provider {provider_name!r}; it is declared as {locations}"
                )
            continue

        provider_id = same_host[0]
        if provider_id == consumer_id:
            raise AnsibleFilterError(f"{_catalog_label(consumer_id)} must not depend on its own container network namespace")
        provider = records[provider_id]
        if provider["execution_mode"] != "rootful":
            raise AnsibleFilterError(
                f"{_catalog_label(consumer_id)} cannot share managed provider {_catalog_label(provider_id)} because "
                "container namespace sharing requires both services to use rootful Podman"
            )
        provider_for[consumer_id] = provider_id
        consumers_for[provider_id].append(consumer_id)
        dependencies.append(
            {
                "consumer": _catalog_label(consumer_id),
                "provider": _catalog_label(provider_id),
                "host": consumer["host"],
            }
        )

    # Ordinary service dependencies order catalog calls, but do not share a
    # network namespace or require the provider's destructive replacement
    # transaction. Wants+After keeps consumers retrying across provider updates.
    ordering_consumers = {identity: list(consumers_for[identity]) for identity in podman_ids}
    for consumer_id in podman_ids:
        consumer = records[consumer_id]
        for unit in consumer["start_dependencies"]:
            if not isinstance(unit, str) or not unit.endswith(".service"):
                continue
            matches = providers_by_host_name.get((consumer["host"], unit.removesuffix(".service")), [])
            if not matches and providers_by_name.get(unit.removesuffix(".service")):
                raise AnsibleFilterError("Managed systemd dependencies must use the same host and manager")
            for provider_id in matches:
                provider = records[provider_id]
                if provider["execution_mode"] != consumer["execution_mode"] or (
                    consumer["execution_mode"] == "rootless" and provider["execution_account"] != consumer["execution_account"]
                ):
                    raise AnsibleFilterError("Systemd service dependencies cannot cross Podman execution stores or accounts")
                if consumer_id not in ordering_consumers[provider_id]:
                    ordering_consumers[provider_id].append(consumer_id)
    indegree = {identity: 0 for identity in podman_ids}
    for consumers in ordering_consumers.values():
        for consumer_id in consumers:
            indegree[consumer_id] += 1
    ready = [identity for identity in podman_ids if indegree[identity] == 0]
    ordered_ids: list[tuple[str, str | None]] = []
    while ready:
        identity = ready.pop(0)
        ordered_ids.append(identity)
        for consumer_id in ordering_consumers[identity]:
            indegree[consumer_id] -= 1
            if indegree[consumer_id] == 0:
                insert_at = len(ready)
                for index, candidate in enumerate(ready):
                    if records[consumer_id]["position"] < records[candidate]["position"]:
                        insert_at = index
                        break
                ready.insert(insert_at, consumer_id)
    if len(ordered_ids) != len(podman_ids):
        cyclic = [_catalog_label(identity) for identity in podman_ids if indegree[identity] > 0]
        raise AnsibleFilterError(f"Managed Podman dependency cycle detected: {', '.join(cyclic)}")

    topology_position = {identity: index for index, identity in enumerate(ordered_ids)}

    ordering_providers = {identity: [] for identity in podman_ids}
    for provider_id, consumers in ordering_consumers.items():
        for consumer_id in consumers:
            ordering_providers[consumer_id].append(provider_id)
    remove_indegree = {identity: len(ordering_consumers[identity]) for identity in podman_ids}
    remove_ready = [identity for identity in podman_ids if remove_indegree[identity] == 0]
    remove_ordered_ids: list[tuple[str, str | None]] = []
    while remove_ready:
        identity = remove_ready.pop(0)
        remove_ordered_ids.append(identity)
        for provider_id in ordering_providers[identity]:
            remove_indegree[provider_id] -= 1
            if remove_indegree[provider_id] == 0:
                insert_at = len(remove_ready)
                for index, candidate in enumerate(remove_ready):
                    if records[provider_id]["position"] < records[candidate]["position"]:
                        insert_at = index
                        break
                remove_ready.insert(insert_at, provider_id)

    def transitive_dependents(provider_id: tuple[str, str | None]) -> list[tuple[str, str | None]]:
        pending = list(consumers_for[provider_id])
        found: set[tuple[str, str | None]] = set()
        while pending:
            consumer_id = pending.pop(0)
            if consumer_id in found:
                continue
            found.add(consumer_id)
            pending.extend(consumers_for[consumer_id])
        return sorted(found, key=topology_position.__getitem__)

    selected_set = set(selected_ids)
    if action == "remove":
        for provider_id in selected_ids:
            if records[provider_id]["runtime"] != "podman":
                continue
            missing = [identity for identity in transitive_dependents(provider_id) if identity not in selected_set]
            if missing:
                raise AnsibleFilterError(
                    f"Cannot remove managed Podman provider {_catalog_label(provider_id)} without also selecting "
                    f"its dependent shared-network services: {', '.join(_catalog_label(identity) for identity in missing)}"
                )

    action_order = remove_ordered_ids if action == "remove" else ordered_ids
    ordered_selected_podman = [identity for identity in action_order if identity in selected_set]
    ordered_selected_iter = iter(ordered_selected_podman)
    planned_selected: list[dict[str, Any]] = []
    for original in selected:
        original_id = _catalog_identity(original)
        if records[original_id]["runtime"] == "podman":
            identity = next(ordered_selected_iter)
            item = deepcopy(dict(records[identity]["item"]))
            dependents = []
            for dependent_id in transitive_dependents(identity):
                dependent = records[dependent_id]
                descriptor = {
                    "name": dependent_id[0],
                    "container_name": dependent["container_name"],
                    "unit_name": f"{dependent['container_name']}.service",
                    "dispatch_host": dependent["host"],
                }
                if dependent_id[1] is not None:
                    descriptor["target"] = dependent_id[1]
                dependents.append(descriptor)
            item["podman_lifecycle"] = {
                "container_name": records[identity]["container_name"],
                "namespace_dependents": dependents,
            }
            planned_selected.append(item)
        else:
            planned_selected.append(deepcopy(dict(original)))

    return {"selected": planned_selected, "dependencies": dependencies}


class FilterModule:
    """Register runtime-neutral service catalog filters with Ansible."""

    def filters(self) -> dict[str, Any]:
        """Return the Jinja filters exposed by this plugin.

        Returns:
            A mapping exposing ``service_catalog_effective``,
            ``service_catalog_merge_target``, ``service_catalog_select``,
            ``service_catalog_by_runtime``, and
            ``service_catalog_podman_lifecycle_plan``.
        """
        return {
            "service_catalog_effective": service_catalog_effective,
            "service_catalog_resolve_hosts": service_catalog_resolve_hosts,
            "service_catalog_resolve_placement": service_catalog_resolve_placement,
            "service_catalog_merge_target": service_catalog_merge_target,
            "service_catalog_select": service_catalog_select,
            "service_catalog_by_runtime": service_catalog_by_runtime,
            "service_catalog_podman_lifecycle_plan": service_catalog_podman_lifecycle_plan,
        }
