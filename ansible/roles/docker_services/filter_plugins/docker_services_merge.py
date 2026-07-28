"""Expose canonical target merging under the legacy Docker filter name.

The Docker role imports the runtime-neutral service-catalog merger and wraps it
for compatibility with existing Jinja call sites and Docker-prefixed error
messages. No independent Docker merge semantics are implemented here.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ansible.errors import AnsibleFilterError

_SERVICE_CATALOG_PATH = Path(__file__).resolve().parents[3] / "filter_plugins/service_catalog.py"


def _load_canonical_merge():
    """Load the shared target merger from the repository filter plugin."""
    spec = importlib.util.spec_from_file_location("service_catalog_docker_compat", _SERVICE_CATALOG_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load canonical service catalog filter from {_SERVICE_CATALOG_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.service_catalog_merge_target


_CANONICAL_MERGE_TARGET = _load_canonical_merge()


def docker_services_merge_target(
    service_cfg: Mapping[str, Any],
    target_name: str | None = None,
) -> dict[str, Any]:
    """Merge a Docker service target using the canonical catalog contract.

    Args:
        service_cfg: Base service definition, optionally containing targets.
        target_name: Optional target name; ``None`` or blank selects the base.

    Returns:
        The deep-copied effective configuration returned by the shared merger.

    Raises:
        AnsibleFilterError: If the shared merger rejects the service or target.
            Its filter name is rewritten in the message for Docker compatibility.

    Note:
        The input service definition is not mutated.
    """
    try:
        return _CANONICAL_MERGE_TARGET(service_cfg, target_name)
    except AnsibleFilterError as error:
        message = str(error).replace("service_catalog_merge_target", "docker_services_merge_target")
        raise AnsibleFilterError(message) from error


class FilterModule:
    """Register the Docker target-merge compatibility filter with Ansible."""

    def filters(self) -> dict[str, Any]:
        """Return the single Jinja filter exposed by this plugin.

        Returns:
            A mapping exposing ``docker_services_merge_target``.
        """
        return {
            "docker_services_merge_target": docker_services_merge_target,
        }
