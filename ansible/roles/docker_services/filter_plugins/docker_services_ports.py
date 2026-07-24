from __future__ import annotations

import ipaddress
from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

from ansible.errors import AnsibleFilterError

_VALID_ACTIONS = {"append", "replace", "append_unique"}
_VALID_PROTOCOLS = {"tcp", "udp"}
_VALID_STACK_DEPLOY_TYPES = {"swarm", "container"}


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _as_str(value: Any, *, default: str = "") -> str:
    if value is None:
        return default

    return str(value).strip()


def _as_int(value: Any, *, name: str) -> int:
    raw = _as_str(value)

    if not raw:
        raise AnsibleFilterError(f"{name} must be a non-empty integer.")

    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise AnsibleFilterError(f"{name} must be an integer, got {value!r}.") from exc


def _as_list(value: Any, *, name: str) -> list[Any]:
    if value is None:
        return []

    if isinstance(value, str):
        raise AnsibleFilterError(f"{name} must be a list or mapping of port dicts, not a string.")

    if _is_mapping(value):
        return list(value.values())

    if isinstance(value, Iterable):
        return list(value)

    raise AnsibleFilterError(f"{name} must be a list or mapping of port dicts.")


def _normalize_stack_deploy_type(value: Any) -> str:
    deploy_type = _as_str(value, default="swarm")

    if deploy_type not in _VALID_STACK_DEPLOY_TYPES:
        raise AnsibleFilterError(f"stack_deploy_type must be one of {sorted(_VALID_STACK_DEPLOY_TYPES)}, got {deploy_type!r}.")

    return deploy_type


def _normalize_action(value: Any) -> str:
    action = _as_str(value, default="append")

    if action not in _VALID_ACTIONS:
        raise AnsibleFilterError(f"ports_action must be one of {sorted(_VALID_ACTIONS)}, got {action!r}.")

    return action


def _normalize_protocol(value: Any, *, name: str) -> str:
    protocol = _as_str(value, default="tcp").lower()

    if protocol not in _VALID_PROTOCOLS:
        raise AnsibleFilterError(f"{name}.protocol must be one of {sorted(_VALID_PROTOCOLS)}, got {protocol!r}.")

    return protocol


def _normalize_host_ip(value: Any, *, name: str) -> str:
    host_ip = _as_str(value)

    if not host_ip:
        raise AnsibleFilterError(f"{name}.host_ip must be a valid IPv4 address.")

    try:
        address = ipaddress.ip_address(host_ip)
    except ValueError as exc:
        raise AnsibleFilterError(f"{name}.host_ip must be a valid IPv4 address.") from exc

    if address.version != 4:
        raise AnsibleFilterError(f"{name}.host_ip must be IPv4 for this compatibility phase.")

    return str(address)


def _raw_new_ports(
    ports: Any,
    ports_list: Any,
    ports_container: Any,
    ports_host: Any,
    ports_protocol: Any,
    ports_mode: Any,
) -> list[Any]:
    if ports is not None:
        return _as_list(ports, name="ports")

    if ports_list is not None:
        return _as_list(ports_list, name="ports_list")

    return [
        {
            "target": ports_container,
            "published": ports_host,
            "protocol": _as_str(ports_protocol, default="tcp"),
            "mode": _as_str(ports_mode, default="ingress"),
        }
    ]


def _canonicalize_port(
    port: Any,
    *,
    index: int,
    stack_deploy_type: str,
    existing: bool = False,
) -> dict[str, Any] | None:
    if not _is_mapping(port):
        if existing:
            return None

        raise AnsibleFilterError(f"ports[{index}] must be a mapping, got {type(port).__name__}.")

    port_dict = dict(port)

    if "target" not in port_dict or "published" not in port_dict:
        if existing:
            return None

        raise AnsibleFilterError(f"ports[{index}] must include both 'target' and 'published'.")

    item: dict[str, Any] = {
        "target": _as_int(port_dict.get("target"), name=f"ports[{index}].target"),
        "published": _as_int(port_dict.get("published"), name=f"ports[{index}].published"),
        "protocol": _normalize_protocol(port_dict.get("protocol", "tcp"), name=f"ports[{index}]"),
    }

    if stack_deploy_type == "swarm":
        if "host_ip" in port_dict:
            raise AnsibleFilterError(f"ports[{index}].host_ip is only supported for Docker container deploys, not Swarm.")
        item["mode"] = _as_str(port_dict.get("mode"), default="ingress")
    elif "host_ip" in port_dict:
        item["host_ip"] = _normalize_host_ip(port_dict["host_ip"], name=f"ports[{index}]")

    return item


def docker_services_canonical_ports(
    ports: Any = None,
    ports_list: Any = None,
    *,
    stack_deploy_type: Any = "swarm",
    ports_container: Any = None,
    ports_host: Any = None,
    ports_protocol: Any = "tcp",
    ports_mode: Any = "ingress",
) -> list[dict[str, Any]]:
    deploy_type = _normalize_stack_deploy_type(stack_deploy_type)

    raw_ports = _raw_new_ports(
        ports,
        ports_list,
        ports_container,
        ports_host,
        ports_protocol,
        ports_mode,
    )

    canonical_ports: list[dict[str, Any]] = []

    for index, port in enumerate(raw_ports):
        canonical = _canonicalize_port(
            port,
            index=index,
            stack_deploy_type=deploy_type,
            existing=False,
        )

        if canonical is not None:
            canonical_ports.append(canonical)

    return canonical_ports


def _canonical_existing_ports(
    existing: Any,
    *,
    stack_deploy_type: str,
) -> list[dict[str, Any]]:
    existing_ports = _as_list(existing, name="existing ports")
    canonical_ports: list[dict[str, Any]] = []

    for index, port in enumerate(existing_ports):
        canonical = _canonicalize_port(
            port,
            index=index,
            stack_deploy_type=stack_deploy_type,
            existing=True,
        )

        if canonical is not None:
            canonical_ports.append(canonical)

    return canonical_ports


def _port_key(port: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        int(port["published"]),
        int(port["target"]),
        _as_str(port.get("protocol"), default="tcp").lower(),
        _as_str(port.get("mode")),
        _as_str(port.get("host_ip")),
    )


def docker_services_merge_ports(
    existing: Any = None,
    ports: Any = None,
    ports_list: Any = None,
    action: Any = "append",
    stack_deploy_type: Any = "swarm",
    ports_container: Any = None,
    ports_host: Any = None,
    ports_protocol: Any = "tcp",
    ports_mode: Any = "ingress",
) -> list[dict[str, Any]]:
    deploy_type = _normalize_stack_deploy_type(stack_deploy_type)
    merge_action = _normalize_action(action)

    existing_ports = _canonical_existing_ports(
        existing,
        stack_deploy_type=deploy_type,
    )

    new_ports = docker_services_canonical_ports(
        ports=ports,
        ports_list=ports_list,
        stack_deploy_type=deploy_type,
        ports_container=ports_container,
        ports_host=ports_host,
        ports_protocol=ports_protocol,
        ports_mode=ports_mode,
    )

    if merge_action == "replace":
        return new_ports

    if merge_action == "append":
        return existing_ports + new_ports

    seen: set[tuple[Any, ...]] = set()
    merged: list[dict[str, Any]] = []

    for port in existing_ports + new_ports:
        key = _port_key(port)

        if key in seen:
            continue

        seen.add(key)
        merged.append(deepcopy(port))

    return merged


class FilterModule:
    def filters(self) -> dict[str, Any]:
        return {
            "docker_services_canonical_ports": docker_services_canonical_ports,
            "docker_services_merge_ports": docker_services_merge_ports,
        }
