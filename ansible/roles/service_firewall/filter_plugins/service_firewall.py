"""Controller-only helper bundling; never queries hosts or resolves secrets."""

import importlib.util
from pathlib import Path


def service_firewall_helper_source(profile):
    path = Path(__file__).resolve().parents[1] / "files/bundle.py"
    spec = importlib.util.spec_from_file_location("service_firewall_bundle", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.bundled_helper(profile)


class FilterModule:
    def filters(self):
        return {"service_firewall_helper_source": service_firewall_helper_source}
