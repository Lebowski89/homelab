import importlib.util
from pathlib import Path

import pytest
from ansible.errors import AnsibleFilterError

MODULE_PATH = Path(__file__).resolve().parents[2] / "ansible" / "filter_plugins" / "service_catalog.py"
spec = importlib.util.spec_from_file_location("service_catalog", MODULE_PATH)
service_catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service_catalog)


def test_missing_runtime_defaults_to_docker():
    items = service_catalog.service_catalog_effective({"app": {"enabled": True}})
    assert items == [{"name": "app", "tags": ["app"], "enabled": True, "runtime": "docker"}]


def test_explicit_podman_runtime():
    items = service_catalog.service_catalog_effective({"n8n": {"runtime": "podman", "tags": ["automation"]}})
    assert items[0]["runtime"] == "podman"
    assert "automation" in items[0]["tags"]


def test_invalid_runtime_fails():
    with pytest.raises(AnsibleFilterError, match="must be one of"):
        service_catalog.service_catalog_effective({"bad": {"runtime": "containerd"}})


def test_mixed_runtime_selection_splits():
    items = service_catalog.service_catalog_effective({"app": {}, "n8n": {"runtime": "podman"}})
    selected = service_catalog.service_catalog_select(items, ["all"], run_all=True)["selected"]
    assert [i["name"] for i in service_catalog.service_catalog_by_runtime(selected, "docker")] == ["app"]
    assert [i["name"] for i in service_catalog.service_catalog_by_runtime(selected, "podman")] == ["n8n"]


def test_target_inherits_parent_runtime():
    items = service_catalog.service_catalog_effective({"svc": {"runtime": "podman", "targets": {"one": {}}}})
    assert items[0]["runtime"] == "podman"


def test_disabled_podman_and_remove_selection():
    items = service_catalog.service_catalog_effective({"n8n": {"runtime": "podman", "enabled": False}})
    assert service_catalog.service_catalog_select(items, ["n8n"])["disabled_only"] is True
    assert service_catalog.service_catalog_select(items, ["n8n"], allow_disabled=True)["selected"][0]["name"] == "n8n"


def test_all_selection_selects_enabled_mixed_services():
    items = service_catalog.service_catalog_effective({"app": {}, "off": {"runtime": "podman", "enabled": False}})
    selected = service_catalog.service_catalog_select(items, run_all=True)["selected"]
    assert [item["name"] for item in selected] == ["app"]
