"""Expose canonical inventory placement for independent common-role entry points."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_SPEC = spec_from_file_location(
    "service_common_catalog_placement", Path(__file__).resolve().parents[3] / "filter_plugins/service_catalog.py"
)
assert _SPEC is not None and _SPEC.loader is not None
_CATALOG = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CATALOG)


class FilterModule:
    def filters(self):
        # Common prerequisites need only inventory placement, independent of
        # playbook-local discovery or loading a runtime adapter first.
        return {"service_catalog_resolve_placement": _CATALOG.service_catalog_resolve_placement}
