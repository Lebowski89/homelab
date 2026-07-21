import importlib.util
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_DIR = REPO_ROOT / "ansible/group_vars/all/services"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_services():
    services = {}
    for path in sorted(SERVICES_DIR.glob("*.yml")):
        data = yaml.safe_load(path.read_text()) or {}
        services.update(data)
    return services


def test_service_catalog_preserves_existing_docker_expansion_ordering():
    docker_filters = load_module(REPO_ROOT / "ansible/filter_plugins/docker_services.py", "docker_services")
    catalog_filters = load_module(REPO_ROOT / "ansible/filter_plugins/service_catalog.py", "service_catalog")
    services = load_services()

    legacy = docker_filters.docker_services_effective(services)
    effective = catalog_filters.service_catalog_effective(services)
    catalog_docker = [
        {key: value for key, value in item.items() if key != "runtime"}
        for item in catalog_filters.service_catalog_by_runtime(effective, "docker")
    ]

    assert catalog_docker == legacy


def selected_without_runtime(items):
    return [{key: value for key, value in item.items() if key != "runtime"} for item in items]


def assert_selector_parity(services, run_tags=None, run_all=False, allow_disabled=False):
    docker_filters = load_module(REPO_ROOT / "ansible/filter_plugins/docker_services.py", "docker_services")
    catalog_filters = load_module(REPO_ROOT / "ansible/filter_plugins/service_catalog.py", "service_catalog")

    legacy_effective = docker_filters.docker_services_effective(services)
    legacy_selected = docker_filters.docker_services_select(legacy_effective, run_tags, run_all, allow_disabled)

    catalog_effective = catalog_filters.service_catalog_effective(services)
    catalog_selected = catalog_filters.service_catalog_select(catalog_effective, run_tags, run_all, allow_disabled)
    catalog_docker_selected = catalog_filters.service_catalog_by_runtime(catalog_selected["selected"], "docker")

    assert selected_without_runtime(catalog_docker_selected) == legacy_selected["selected"]


def test_service_catalog_preserves_docker_selector_parity_for_real_services():
    services = load_services()
    assert_selector_parity(services, run_tags=["authelia"])
    assert_selector_parity(services, run_tags=["media"])
    assert_selector_parity(services, run_tags=["qbittorrent-xs"])
    assert_selector_parity(services, run_all=True)

    disabled_name = next(name for name, cfg in services.items() if cfg.get("runtime", "docker") == "docker" and cfg.get("enabled") is False)
    assert_selector_parity(services, run_tags=[disabled_name], allow_disabled=False)
    assert_selector_parity(services, run_tags=[disabled_name], allow_disabled=True)
