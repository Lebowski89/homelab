"""Build and select legacy Docker service catalog metadata for Ansible.

The filters in this module support the Docker adapter's compatibility path.
They expand Docker service definitions into lightweight base-or-target
selection records and select records by Ansible run tags and enabled state.
They do not merge full target configurations or mutate service declarations.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from ansible.errors import AnsibleFilterError


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


def _unique(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    out: list[Any] = []

    for value in values:
        key = str(value)

        if key in seen:
            continue

        seen.add(key)
        out.append(value)

    return out


def docker_services_effective(services: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Expand Docker service definitions into lightweight selection records.

    A missing runtime defaults to Docker; services whose normalized ``runtime``
    is not ``docker`` are skipped. A service without ``targets`` produces one
    record. A service with targets produces one record per target, combining
    base and target tags and requiring both enabled states for the resulting
    record to be enabled. Tag duplicates are removed while preserving their
    first occurrence.

    Args:
        services: Mapping of service names to service definition mappings.

    Returns:
        Ordered records containing ``name``, ``tags``, and ``enabled`` plus
        ``target`` for target-based services. No full service configuration is
        embedded in a record.

    Raises:
        AnsibleFilterError: If the catalog, a service definition, ``targets``,
            a target definition, an enabled value, or a tag value has an
            unsupported shape or value.

    Note:
        The input mappings are not mutated.
    """
    if not isinstance(services, Mapping):
        raise AnsibleFilterError(f"services must be a mapping, got {type(services).__name__}")

    out: list[dict[str, Any]] = []

    for service_name, service_cfg in services.items():
        if not isinstance(service_cfg, Mapping):
            raise AnsibleFilterError(f"Service {service_name!r} must be a mapping, got {type(service_cfg).__name__}")

        service_runtime = str(service_cfg.get("runtime", "docker")).strip().lower()
        if service_runtime != "docker":
            continue

        service_enabled = _as_bool(
            service_cfg.get("enabled", True),
            name=f"{service_name}.enabled",
            default=True,
        )

        service_tags = _unique([service_name] + _as_list(service_cfg.get("tags", []), name=f"{service_name}.tags"))

        targets = service_cfg.get("targets")

        if targets is None:
            out.append(
                {
                    "name": service_name,
                    "tags": service_tags,
                    "enabled": service_enabled,
                }
            )
            continue

        if not isinstance(targets, Mapping):
            raise AnsibleFilterError(f"{service_name}.targets must be a mapping, got {type(targets).__name__}")

        for target_name, target_cfg in targets.items():
            if not isinstance(target_cfg, Mapping):
                raise AnsibleFilterError(f"{service_name}.targets.{target_name} must be a mapping, got {type(target_cfg).__name__}")

            target_enabled = _as_bool(
                target_cfg.get("enabled", True),
                name=f"{service_name}.targets.{target_name}.enabled",
                default=True,
            )

            target_tags = _unique(
                service_tags
                + [target_name]
                + _as_list(
                    target_cfg.get("tags", []),
                    name=f"{service_name}.targets.{target_name}.tags",
                )
            )

            out.append(
                {
                    "name": service_name,
                    "target": target_name,
                    "tags": target_tags,
                    "enabled": service_enabled and target_enabled,
                }
            )

    return out


def docker_services_select(
    items: list[Mapping[str, Any]],
    run_tags: list[str] | None = None,
    run_all: bool = False,
    allow_disabled: bool = False,
) -> dict[str, Any]:
    """Select effective Docker records by name, tag, and enabled state.

    With ``run_all`` false, an empty ``run_tags`` value matches every record;
    otherwise a record matches when its service name or any of its tags was
    requested. Disabled matches are omitted unless ``allow_disabled`` is true.

    Args:
        items: Effective Docker selection records in desired processing order.
        run_tags: Optional service names or tags to match.
        run_all: Boolean-like value that bypasses name and tag filtering.
        allow_disabled: Boolean-like value that retains disabled matches.

    Returns:
        A mapping with ``matched`` records before enabled-state filtering,
        ``selected`` records after that filtering, and ``disabled_only`` set
        when matches existed but none were selectable. The returned lists
        reference the original item mappings.

    Raises:
        AnsibleFilterError: If an item is not a mapping or a tag or boolean-like
            input cannot be normalized.

    Note:
        Neither ``items`` nor its member mappings are mutated.
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
        item_tags = set(_as_list(item.get("tags", []), name=f"{item_name}.tags"))

        is_match = run_all_bool or not run_tags_set or item_name in run_tags_set or bool(item_tags.intersection(run_tags_set))

        if not is_match:
            continue

        matched.append(item)

        item_enabled = _as_bool(
            item.get("enabled", True),
            name=f"{item_name}.enabled",
            default=True,
        )

        if item_enabled or allow_disabled_bool:
            selected.append(item)

    return {
        "matched": matched,
        "selected": selected,
        "disabled_only": len(matched) > 0 and len(selected) == 0,
    }


class FilterModule:
    """Register Docker compatibility catalog filters with Ansible."""

    def filters(self) -> dict[str, Any]:
        """Return the Jinja filters exposed by this plugin.

        Returns:
            A mapping exposing ``docker_services_effective`` for catalog
            expansion and ``docker_services_select`` for run selection.
        """
        return {
            "docker_services_effective": docker_services_effective,
            "docker_services_select": docker_services_select,
        }
