from __future__ import annotations

import importlib.util
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ansible.errors import AnsibleFilterError

_SERVICE_CATALOG_PATH = Path(__file__).resolve().parents[3] / "filter_plugins/service_catalog.py"


def _load_canonical_merge():
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
    """Compatibility wrapper around the canonical service-catalog target merge."""
    try:
        return _CANONICAL_MERGE_TARGET(service_cfg, target_name)
    except AnsibleFilterError as error:
        message = str(error).replace("service_catalog_merge_target", "docker_services_merge_target")
        raise AnsibleFilterError(message) from error


class FilterModule:
    def filters(self) -> dict[str, Any]:
        return {
            "docker_services_merge_target": docker_services_merge_target,
        }
