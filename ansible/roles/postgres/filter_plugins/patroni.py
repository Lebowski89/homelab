"""Build and compare Patroni replication-safety dynamic configuration."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from ansible.errors import AnsibleFilterError

SLOT_NAME_PATTERN = re.compile(r"^[a-z0-9_]{1,63}$")


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AnsibleFilterError(f"{name} must be a mapping, got {type(value).__name__}")
    return value


def _hosts(value: Any) -> list[str]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise AnsibleFilterError("PostgreSQL inventory hosts must be a list")
    hosts = sorted({str(host).strip() for host in value})
    if not hosts or any(not host for host in hosts):
        raise AnsibleFilterError("PostgreSQL inventory hosts must contain non-empty names")
    invalid = [host for host in hosts if SLOT_NAME_PATTERN.fullmatch(host) is None]
    if invalid:
        raise AnsibleFilterError(
            "PostgreSQL member names must already be valid physical slot names "
            f"(lowercase letters, digits, underscores; maximum 63 characters): {invalid}"
        )
    return hosts


def postgres_patroni_permanent_slots(hosts: Any, extra_slots: Any | None = None) -> dict[str, dict[str, Any]]:
    """Return deterministic member physical slots plus declared extra slots.

    The returned mapping is the complete automation-owned top-level ``slots``
    subtree. Live permanent slots not represented here are intentionally
    removed during reconciliation.
    """
    member_hosts = _hosts(hosts)
    extras = _mapping(extra_slots or {}, "postgres_patroni_extra_slots")
    collisions = sorted(set(member_hosts) & {str(name) for name in extras})
    if collisions:
        raise AnsibleFilterError(f"Extra Patroni slots collide with inventory member slots: {collisions}")

    desired: dict[str, dict[str, Any]] = {}
    for raw_name, raw_config in sorted(extras.items(), key=lambda item: str(item[0])):
        name = str(raw_name).strip()
        if SLOT_NAME_PATTERN.fullmatch(name) is None:
            raise AnsibleFilterError(f"Invalid extra Patroni slot name: {name!r}")
        desired[name] = deepcopy(dict(_mapping(raw_config, f"postgres_patroni_extra_slots.{name}")))
    for host in member_hosts:
        desired[host] = {"type": "physical"}
    return dict(sorted(desired.items()))


def postgres_patroni_replication_safety_patch(
    current_config: Any,
    desired_slots: Any,
    wal_keep_size: Any,
    max_slot_wal_keep_size: Any,
) -> dict[str, Any]:
    """Return the minimal Patroni REST PATCH body, or an empty mapping."""
    current = _mapping(current_config, "Patroni dynamic configuration")
    postgresql = _mapping(current.get("postgresql", {}) or {}, "Patroni dynamic configuration postgresql")
    current_parameters = _mapping(postgresql.get("parameters", {}) or {}, "Patroni dynamic PostgreSQL parameters")
    current_slots = _mapping(current.get("slots", {}) or {}, "Patroni dynamic permanent slots")
    desired_slots = _mapping(desired_slots, "postgres_patroni_permanent_slots")
    wal_keep_size = str(wal_keep_size).strip()
    max_slot_wal_keep_size = str(max_slot_wal_keep_size).strip()
    if not wal_keep_size or not max_slot_wal_keep_size:
        raise AnsibleFilterError("Patroni WAL retention settings must be non-empty")

    postgresql_patch: dict[str, Any] = {}
    if postgresql.get("use_slots") is not True:
        postgresql_patch["use_slots"] = True

    parameter_patch = {
        name: desired_value
        for name, desired_value in {
            "wal_keep_size": wal_keep_size,
            "max_slot_wal_keep_size": max_slot_wal_keep_size,
        }.items()
        if current_parameters.get(name) != desired_value
    }
    if parameter_patch:
        postgresql_patch["parameters"] = parameter_patch

    patch: dict[str, Any] = {}
    if postgresql_patch:
        patch["postgresql"] = postgresql_patch

    slot_patch = {name: deepcopy(dict(config)) for name, config in desired_slots.items() if current_slots.get(name) != config}
    slot_patch.update({name: None for name in current_slots if name not in desired_slots})
    if slot_patch:
        patch["slots"] = dict(sorted(slot_patch.items()))

    return patch


class FilterModule:
    """Expose Patroni replication-safety helpers to Ansible."""

    def filters(self) -> dict[str, Any]:
        return {
            "postgres_patroni_permanent_slots": postgres_patroni_permanent_slots,
            "postgres_patroni_replication_safety_patch": postgres_patroni_replication_safety_patch,
        }
