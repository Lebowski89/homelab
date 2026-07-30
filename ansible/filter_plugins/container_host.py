"""Resolve canonical container-host defaults for Ansible orchestration.

The ``container_host_defaults`` filter reads a host-variable mapping and
returns the small, runtime-neutral set of ownership and storage defaults used
by service dispatch.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from ansible.errors import AnsibleFilterError

_CONTAINER_HOST_FIELDS = {
    "puid": "container_host_puid",
    "pgid": "container_host_pgid",
    "appdata_root": "container_host_appdata_root",
    "data_root": "container_host_data_root",
}


def _present(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def container_host_defaults(host_variables: Any) -> dict[str, Any]:
    """Extract available container ownership and storage defaults for a host.

    ``None``, empty strings, and whitespace-only strings are treated as absent;
    other values, including zero, are retained. Returned values are deep copies,
    so modifying the result does not mutate ``host_variables``.

    Args:
        host_variables: Mapping containing canonical ``container_host_*``
            variables.

    Returns:
        A mapping whose possible keys are ``puid``, ``pgid``,
        ``appdata_root``, and ``data_root``. Keys without a present source value
        are omitted.

    Raises:
        AnsibleFilterError: If ``host_variables`` is not a mapping.
    """
    if not isinstance(host_variables, Mapping):
        raise AnsibleFilterError(f"container_host_defaults expected host variables to be a mapping, got {type(host_variables).__name__}")

    defaults: dict[str, Any] = {}
    for output_name, inventory_name in _CONTAINER_HOST_FIELDS.items():
        value = host_variables.get(inventory_name)
        if _present(value):
            defaults[output_name] = deepcopy(value)
    return defaults


class FilterModule:
    """Register container-host filters with Ansible."""

    def filters(self) -> dict[str, Any]:
        """Return the Jinja filter names exposed by this plugin.

        Returns:
            A mapping exposing ``container_host_defaults`` to Ansible.
        """
        return {"container_host_defaults": container_host_defaults}
