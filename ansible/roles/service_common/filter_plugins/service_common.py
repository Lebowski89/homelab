from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ansible.errors import AnsibleFilterError


def _mapping(value: Any, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AnsibleFilterError(f"{name} must be a mapping")
    return value


def _text(value: Any) -> str:
    return str(value or "").strip()


def _target_hosts(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise AnsibleFilterError("service_common_target_hosts must be a list")
    return [_text(item) for item in value if _text(item)]


def service_common_traefik_context(
    service: Mapping[str, Any],
    name: str,
    target_hosts: Sequence[str],
    base_zone: str,
    inventory_hosts: Mapping[str, Any],
) -> dict[str, Any]:
    service = _mapping(service, name="service_common_service")
    traefik = _mapping(service.get("traefik", {}), name="service_common_service.traefik")
    inventory_hosts = _mapping(inventory_hosts, name="hostvars")
    name = _text(name)
    if not name:
        raise AnsibleFilterError("service_common_name must be non-empty")

    exposure = _text(traefik.get("exposure", "public")) or "public"
    if exposure not in {"private", "public"}:
        raise AnsibleFilterError("traefik.exposure must be private or public")
    private = exposure == "private"

    configured_zone = _text(traefik.get("zone"))
    base_zone = _text(base_zone)
    if not configured_zone and not base_zone:
        raise AnsibleFilterError("service_common_traefik_base_zone or traefik.zone is required")
    zone = configured_zone or (f"int.{base_zone}" if private else base_zone)
    address = f"{_text(traefik.get('subdomain')) or name}.{zone}"

    try:
        port = int(traefik.get("port"))
    except (TypeError, ValueError):
        raise AnsibleFilterError("traefik.port must be a positive integer") from None
    if port < 1:
        raise AnsibleFilterError("traefik.port must be a positive integer")

    backend_mode = _text(traefik.get("backend_mode", "service")) or "service"
    if backend_mode not in {"host", "service"}:
        raise AnsibleFilterError("traefik.backend_mode must be host or service")
    backend_url = _text(traefik.get("backend_url"))
    backend_host = ""

    if not backend_url:
        if backend_mode == "host":
            backend_host = _text(traefik.get("backend_host"))
            if not backend_host:
                hosts = _target_hosts(target_hosts)
                backend_inventory = _text(traefik.get("backend_host_inventory"))
                if not backend_inventory and hosts:
                    backend_inventory = hosts[0]
                if not backend_inventory:
                    raise AnsibleFilterError(
                        "host backend requires traefik.backend_host, traefik.backend_host_inventory, or a common target host"
                    )
                if backend_inventory not in inventory_hosts:
                    raise AnsibleFilterError(f"Traefik backend inventory host {backend_inventory!r} is not in hostvars")
                backend_host_vars = _mapping(
                    inventory_hosts[backend_inventory],
                    name=f"hostvars[{backend_inventory!r}]",
                )
                backend_host = _text(backend_host_vars.get("local_ip"))
                if not backend_host:
                    raise AnsibleFilterError(f"hostvars[{backend_inventory!r}].local_ip is required for a host backend")
        else:
            backend_host = name
        backend_scheme = _text(traefik.get("backend_scheme", "http")) or "http"
        backend_url = f"{backend_scheme}://{backend_host}:{port}"

    themepark = traefik.get("themepark", {}) or {}
    themepark = _mapping(themepark, name="service_common_service.traefik.themepark")
    theme_app = _text(themepark.get("app"))
    theme = _text(themepark.get("theme"))
    theme_enabled = bool(theme_app and theme)
    internal_api_rules = traefik.get("internal_api_rules", []) or []
    if not isinstance(internal_api_rules, Sequence) or isinstance(internal_api_rules, str):
        raise AnsibleFilterError("traefik.internal_api_rules must be a list")

    return {
        "name": name,
        "private": private,
        "entrypoint": _text(traefik.get("entrypoint")) or ("https_private" if private else "https"),
        "address": address,
        "authelia_enabled": _text(traefik.get("sso")) == "authelia",
        "middleware_chain": _text(traefik.get("middleware_chain")) or f"{name}-{'private-' if private else ''}ui-chain",
        "internal_api": bool(traefik.get("internal_api", False)),
        "internal_api_rules": list(internal_api_rules),
        "headers_middleware": _text(traefik.get("headers_middleware")) or "secure-headers@file",
        "theme_enabled": theme_enabled,
        "theme_app": theme_app,
        "theme": theme,
        "backend_url": backend_url,
    }


class FilterModule:
    def filters(self) -> dict[str, Any]:
        return {"service_common_traefik_context": service_common_traefik_context}
