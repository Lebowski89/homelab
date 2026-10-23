"""Validate network values used by runtime-neutral Ansible contracts."""

from __future__ import annotations

import re
from ipaddress import IPv4Network, IPv6Address, ip_address, ip_network
from typing import Any


def valid_ipv4_cidr(value: Any) -> bool:
    """Return whether value is an IPv4 address and prefix in CIDR notation."""
    if not isinstance(value, str) or value.count("/") != 1:
        return False
    try:
        return isinstance(ip_network(value, strict=True), IPv4Network)
    except ValueError:
        return False


def valid_remote_ip(value: Any) -> bool:
    """Accept explicit numeric unicast destinations, including mapped IPv4."""
    if not isinstance(value, str) or value != value.strip() or "%" in value:
        return False
    try:
        address = ip_address(value)
    except ValueError:
        return False
    if isinstance(address, IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return not (address.is_loopback or address.is_unspecified or address.is_multicast or address == ip_address("255.255.255.255"))


def valid_dns_zone(value: Any) -> bool:
    """Validate the DNS zone used to construct private service hostnames."""
    if not isinstance(value, str) or value != value.strip():
        return False
    zone = value.removesuffix(".")
    return 0 < len(zone) <= 253 and all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label) for label in zone.split("."))


def valid_tcp_port(value: Any) -> bool:
    """Accept decimal TCP ports using the existing integer/string contract."""
    return (
        not isinstance(value, bool)
        and isinstance(value, (str, int))
        and re.fullmatch(r"[0-9]+", str(value)) is not None
        and 1 <= int(value) <= 65535
    )


class FilterModule:
    """Expose network validation filters to Ansible."""

    def filters(self) -> dict[str, object]:
        return {
            "valid_ipv4_cidr": valid_ipv4_cidr,
            "valid_remote_ip": valid_remote_ip,
            "valid_dns_zone": valid_dns_zone,
            "valid_tcp_port": valid_tcp_port,
        }
