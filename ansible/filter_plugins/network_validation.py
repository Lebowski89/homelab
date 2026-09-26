"""Validate network values used by runtime-neutral Ansible contracts."""

from __future__ import annotations

from ipaddress import IPv4Network, ip_network
from typing import Any


def valid_ipv4_cidr(value: Any) -> bool:
    """Return whether value is an IPv4 address and prefix in CIDR notation."""
    if not isinstance(value, str) or value.count("/") != 1:
        return False
    try:
        return isinstance(ip_network(value, strict=True), IPv4Network)
    except ValueError:
        return False


class FilterModule:
    """Expose network validation filters to Ansible."""

    def filters(self) -> dict[str, object]:
        return {"valid_ipv4_cidr": valid_ipv4_cidr}
