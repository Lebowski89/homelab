"""Build deterministic Prometheus file_sd targets for availability monitoring."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from ansible.errors import AnsibleFilterError


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AnsibleFilterError(f"{name} must be a mapping, got {type(value).__name__}")
    return value


def _sequence(value: Any, name: str) -> Sequence[Any]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise AnsibleFilterError(f"{name} must be a list, got {type(value).__name__}")
    return value


def _merge(base: Any, override: Any) -> Any:
    if isinstance(base, Mapping) and isinstance(override, Mapping):
        result = deepcopy(dict(base))
        for key, value in override.items():
            result[key] = _merge(result[key], value) if key in result else deepcopy(value)
        return result
    if isinstance(base, list) and isinstance(override, list):
        return [deepcopy(item) for item in base if item not in override] + deepcopy(override)
    return deepcopy(override)


def _materialize(services: Mapping[str, Any], entry: Mapping[str, Any]) -> dict[str, Any]:
    service_name = str(entry.get("name", "")).strip()
    if service_name not in services:
        raise AnsibleFilterError(f"availability catalog entry references unknown service {service_name!r}")
    service = _mapping(services[service_name], f"services.{service_name}")
    result = deepcopy(dict(service))
    targets = result.pop("targets", {}) or {}
    target_name = entry.get("target")
    if target_name is not None:
        targets = _mapping(targets, f"services.{service_name}.targets")
        if target_name not in targets:
            raise AnsibleFilterError(f"availability catalog entry references unknown target {service_name}:{target_name}")
        result = _merge(result, _mapping(targets[target_name], f"services.{service_name}.targets.{target_name}"))
    return result


def _file_sd(target: str, labels: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "targets": [target],
        "labels": {key: str(value) for key, value in labels.items() if value is not None and str(value) != ""},
    }


def _category(tags: Sequence[Any], category_tags: Mapping[str, Any], override: Any) -> str:
    if override is not None and str(override).strip():
        return str(override).strip()
    normalized_tags = {str(tag) for tag in tags}
    matches = [str(label) for tag, label in category_tags.items() if str(tag) in normalized_tags]
    if len(matches) != 1:
        raise AnsibleFilterError(f"availability target must resolve to exactly one category, got {matches or 'none'} from tags {tags}")
    return matches[0]


def availability_http_file_sd(
    services: Mapping[str, Any],
    catalog: Sequence[Any],
    internal_zone: str,
    private_port: Any,
    category_tags: Mapping[str, Any],
    exclusions: Sequence[Any] | None = None,
    external_services: Mapping[str, Any] | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return ordinary catalogue-derived and narrowly overridden HTTP probes."""
    services = _mapping(services, "services")
    catalog = _sequence(catalog, "catalog")
    category_tags = _mapping(category_tags, "category_tags")
    external_services = _mapping(external_services or {}, "external_services")
    overrides = _mapping(overrides or {}, "overrides")
    excluded = {str(item) for item in _sequence(exclusions or [], "exclusions")}
    zone = str(internal_zone).strip().rstrip(".")
    if not zone:
        raise AnsibleFilterError("internal_zone must be non-empty")
    try:
        port = int(private_port)
    except (TypeError, ValueError) as error:
        raise AnsibleFilterError("private_port must be an integer") from error

    discovered: list[dict[str, Any]] = []
    for raw_entry in catalog:
        entry = _mapping(raw_entry, "catalog entry")
        if not bool(entry.get("enabled", True)):
            continue
        effective = _materialize(services, entry)
        service = str(effective.get("name") or entry["name"]).strip().replace("_", "-")
        traefik = effective.get("traefik") or {}
        if not isinstance(traefik, Mapping):
            continue
        if traefik.get("enable") is not True or str(traefik.get("exposure", "")) != "private" or service in excluded:
            continue
        override = _mapping(overrides.get(service, {}), f"overrides.{service}")
        path = str(override.get("path", "")).strip()
        if path and not path.startswith("/"):
            raise AnsibleFilterError(f"overrides.{service}.path must begin with /")
        category = _category(effective.get("tags", []), category_tags, override.get("category"))
        module = str(override.get("module", "http_private"))
        discovered.append(
            _file_sd(
                f"https://{service}.{zone}:{port}{path}",
                {
                    "service": service,
                    "category": category,
                    "probe_type": "http",
                    "criticality": override.get("criticality", "standard"),
                    "module": module,
                    "monitor_id": f"http.{service}-private",
                },
            )
        )

    for service, raw_override in external_services.items():
        service = str(service).replace("_", "-")
        override = _mapping(raw_override, f"external_services.{service}")
        catalog_key = str(override.get("catalog_service", service)).replace("-", "_")
        source = services.get(catalog_key) or services.get(service)
        if isinstance(source, Mapping) and source.get("enabled", True) is not True:
            raise AnsibleFilterError(f"external availability service {service!r} is disabled in the catalogue")
        if not isinstance(source, Mapping) and override.get("catalog_required", True) is not False:
            raise AnsibleFilterError(f"external availability service {service!r} is absent or disabled in the catalogue")
        discovered.append(
            _file_sd(
                str(override.get("url") or f"https://{service}.{zone}:{port}"),
                {
                    "service": service,
                    "category": override["category"],
                    "probe_type": "http",
                    "criticality": override.get("criticality", "standard"),
                    "module": override.get("module", "http_private"),
                    "monitor_id": f"http.{service}-private",
                },
            )
        )

    return sorted(discovered, key=lambda item: item["labels"]["monitor_id"])


def availability_direct_http_file_sd(targets: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return the small set of direct HTTP endpoints that intentionally bypass Traefik."""
    result = []
    for name, raw_target in _mapping(targets, "targets").items():
        target = _mapping(raw_target, f"targets.{name}")
        result.append(
            _file_sd(
                str(target["url"]),
                {
                    "service": target.get("service", name),
                    "category": target["category"],
                    "probe_type": "http",
                    "criticality": target.get("criticality", "standard"),
                    "module": target["module"],
                    "monitor_id": f"http.{name}",
                },
            )
        )
    return sorted(result, key=lambda item: item["labels"]["monitor_id"])


def availability_icmp_file_sd(hostvars: Mapping[str, Any], hosts: Sequence[Any]) -> list[dict[str, Any]]:
    """Return IPv4 ICMP targets resolved from inventory hostvars."""
    result = []
    for raw_host in _sequence(hosts, "hosts"):
        host = str(raw_host)
        values = _mapping(_mapping(hostvars, "hostvars").get(host, {}), f"hostvars.{host}")
        address = str(values.get("local_ip", "")).strip()
        if not address:
            raise AnsibleFilterError(f"availability ICMP host {host!r} has no local_ip")
        result.append(
            _file_sd(
                address,
                {
                    "service": host,
                    "host": host,
                    "category": "Infrastructure",
                    "probe_type": "icmp",
                    "criticality": "critical",
                    "module": "icmp_ipv4",
                    "monitor_id": f"ping.{host}",
                },
            )
        )
    return sorted(result, key=lambda item: item["labels"]["monitor_id"])


def availability_tcp_file_sd(hostvars: Mapping[str, Any], targets: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return TCP endpoints using inventory-owned host addresses."""
    result = []
    hostvars = _mapping(hostvars, "hostvars")
    for name, raw_target in _mapping(targets, "targets").items():
        target = _mapping(raw_target, f"targets.{name}")
        host = str(target["host"])
        address = str(_mapping(hostvars.get(host, {}), f"hostvars.{host}").get("local_ip", "")).strip()
        if not address:
            raise AnsibleFilterError(f"availability TCP host {host!r} has no local_ip")
        result.append(
            _file_sd(
                f"{address}:{int(target['port'])}",
                {
                    "service": target.get("service", host),
                    "host": host,
                    "category": target["category"],
                    "probe_type": "tcp",
                    "criticality": target.get("criticality", "critical"),
                    "module": "tcp_connect",
                    "monitor_id": f"tcp.{name}",
                },
            )
        )
    return sorted(result, key=lambda item: item["labels"]["monitor_id"])


def availability_postgres_file_sd(hostvars: Mapping[str, Any], hosts: Sequence[Any], port: Any = 9187) -> list[dict[str, Any]]:
    """Return postgres_exporter scrape targets from the tags_postgres inventory group."""
    result = []
    hostvars = _mapping(hostvars, "hostvars")
    for raw_host in _sequence(hosts, "hosts"):
        host = str(raw_host)
        address = str(_mapping(hostvars.get(host, {}), f"hostvars.{host}").get("local_ip", "")).strip()
        if not address:
            raise AnsibleFilterError(f"PostgreSQL exporter host {host!r} has no local_ip")
        result.append(
            _file_sd(
                f"{address}:{int(port)}",
                {
                    "service": host,
                    "host": host,
                    "category": "Infrastructure",
                    "probe_type": "postgres",
                    "criticality": "critical",
                },
            )
        )
    return sorted(result, key=lambda item: item["labels"]["host"])


class FilterModule:
    """Expose availability target generation filters to Ansible."""

    def filters(self) -> dict[str, Any]:
        return {
            "availability_http_file_sd": availability_http_file_sd,
            "availability_direct_http_file_sd": availability_direct_http_file_sd,
            "availability_icmp_file_sd": availability_icmp_file_sd,
            "availability_tcp_file_sd": availability_tcp_file_sd,
            "availability_postgres_file_sd": availability_postgres_file_sd,
        }
