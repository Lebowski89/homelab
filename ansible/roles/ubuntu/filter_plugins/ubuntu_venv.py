"""Classify Ansible virtualenv recovery for the Ubuntu role.

The role feeds stat and interpreter-probe results into this filter before it
chooses whether to preserve, create, or recreate its managed virtualenv.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ansible.errors import AnsibleFilterError


def _boolean(value: Any, *, name: str) -> bool:
    if not isinstance(value, bool):
        raise AnsibleFilterError(f"{name} must be a boolean")
    return value


def _abi(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AnsibleFilterError(f"{name} must be a non-empty string")
    return value.strip()


def ubuntu_venv_recovery_action(status: Any) -> str:
    """Return the required recovery action for a managed virtualenv.

    Args:
        status: Mapping containing ``python_exists``, ``site_packages_exists``,
            ``probe_rc``, ``probe_abi``, and ``controller_abi`` probe results.

    Returns:
        ``create`` when no interpreter exists, ``recreate`` when the probe or
        ABI layout is incompatible, otherwise ``preserve``.

    Raises:
        AnsibleFilterError: If required decision inputs have invalid shapes.

    Note:
        The status mapping and filesystem are not modified.
    """
    if not isinstance(status, Mapping):
        raise AnsibleFilterError("virtualenv recovery status must be a mapping")
    python_exists = _boolean(status.get("python_exists"), name="python_exists")
    _abi(status.get("controller_abi"), name="controller_abi")
    if not python_exists:
        return "create"

    site_packages_exists = _boolean(status.get("site_packages_exists"), name="site_packages_exists")
    if not site_packages_exists:
        return "recreate"

    probe_rc = status.get("probe_rc")
    if isinstance(probe_rc, bool) or not isinstance(probe_rc, int):
        raise AnsibleFilterError("probe_rc must be an integer")
    if probe_rc != 0:
        return "recreate"

    probe_abi = _abi(status.get("probe_abi"), name="probe_abi")
    controller_abi = _abi(status.get("controller_abi"), name="controller_abi")
    return "preserve" if probe_abi == controller_abi else "recreate"


class FilterModule:
    """Register Ubuntu virtualenv recovery filters with Ansible."""

    def filters(self) -> dict[str, Any]:
        """Return the virtualenv recovery filter mapping."""
        return {"ubuntu_venv_recovery_action": ubuntu_venv_recovery_action}
