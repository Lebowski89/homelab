"""Native catalogue boundaries using the real application declarations."""

import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from ansible.errors import AnsibleFilterError

ROOT = Path(__file__).resolve().parents[2]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CATALOG = load("ansible/filter_plugins/service_catalog.py", "native_catalog")
NATIVE = load("ansible/roles/native_services/filter_plugins/native_services.py", "native_inputs")


def services():
    result = {}
    for path in (ROOT / "ansible/group_vars/all/services").glob("*.yml"):
        result.update(yaml.safe_load(path.read_text()))
    return result


def test_real_native_targets_isolate_container_installation_and_selection():
    source = services()
    original = deepcopy(source)
    groups = {
        "tags_podman": ["one", "two"],
        "tags_node_exporter": ["one", "two"],
        "tags_keepalived": ["dns1", "dns2"],
        "tags_technitium_native": ["dns1", "dns2"],
    }
    index = CATALOG.service_catalog_effective(source, "", resolve_hosts=False)
    selected = CATALOG.service_catalog_select(index, ["alloy_native"])["selected"]
    assert [(entry["name"], entry["runtime"]) for entry in selected] == [("alloy", "native")]
    native = CATALOG.service_catalog_effective(source, "one", groups, runtimes=["native"])
    assert len(native) == 4
    for entry in native:
        cfg = CATALOG.service_catalog_merge_target(source[entry["name"]], entry.get("target"))
        assert "image" not in cfg and "infisical" not in cfg and "environment" not in cfg
        assert "ports" not in cfg and "volumes" not in cfg and "systemd" not in cfg
        assert len(entry["dispatch_hosts"]) == 2
    assert source == original


def test_native_effective_config_replaces_empty_values_and_rejects_unsupported_inputs():
    base = services()["node_exporter"]
    base["targets"] = {"minimal": {"native": {"config": {"enabled_collectors": [], "extra_args": []}}}}
    cfg = CATALOG.service_catalog_merge_target(base, "minimal")
    assert cfg["native"]["config"]["enabled_collectors"] == []
    base["targets"]["minimal"]["image"] = "unused:latest"
    with pytest.raises(AnsibleFilterError, match="unsupported"):
        CATALOG.service_catalog_merge_target(base, "minimal")
    cfg["native"]["config"]["arbitrary_command"] = "unsupported"
    with pytest.raises(AnsibleFilterError, match="unsupported"):
        NATIVE.native_services_inputs(cfg["native"], {})


def test_defined_host_overrides_preserve_values_without_conversion():
    tech = services()["technitium"]["targets"]["native"]["native"]
    values = NATIVE.native_services_inputs(
        tech,
        {
            "technitium_native_disable_resolved_stub": False,
            "technitium_native_resolved_dns_servers": [],
            "technitium_native_web_port": 12345,
        },
    )
    normalized = NATIVE.native_services_normalize({**tech, "config": values})
    assert normalized["disable_resolved_stub"] is False
    assert normalized["resolved_dns_servers"] == []
    assert normalized["web_port"] == 12345 and isinstance(normalized["web_port"], int)
    keepalived = services()["keepalived"]["native"]
    keepalived_values = NATIVE.native_services_inputs(keepalived, {"keepalived_script_weight": 0})
    assert NATIVE.native_services_normalize({**keepalived, "config": keepalived_values})["script_weight"] == 0
    normalized["web_port"] = False
    with pytest.raises(AnsibleFilterError, match="integer"):
        NATIVE.native_services_normalize({**tech, "config": normalized})


def test_native_protection_requirements_fail_closed_without_a_host_identity_adapter():
    base = services()["node_exporter"]
    base["operational_requirements"] = {"acl": ["mgt_backends"]}
    with pytest.raises(AnsibleFilterError, match="host-listener"):
        CATALOG.service_catalog_merge_target(base)


def test_native_firewall_planning_needs_no_container_context_and_rejects_protected_callers(monkeypatch):
    from types import SimpleNamespace

    from ansible.errors import AnsibleActionFail

    firewall = load("ansible/action_plugins/service_firewall_plan.py", "native_firewall")
    monkeypatch.setattr(firewall.ActionBase, "run", lambda *args, **kwargs: {})
    action = object.__new__(firewall.ActionModule)
    source = services()
    cfg = CATALOG.service_catalog_merge_target(source["node_exporter"])
    entry = {"name": "node_exporter", "runtime": "native", "config": cfg}
    action._task = SimpleNamespace(args={"entry": entry, "action": "deploy"})
    result = action.run(task_vars={"svcfiles": source})
    assert result["ansible_facts"]["service_firewall_lifecycle_plan"]["managed"] is False
    source["protected_provider"] = {
        "runtime": "podman",
        "ports": {"api": {"exposure": "private", "callers": ["node_exporter"], "published": 1234, "target": 1234}},
    }
    with pytest.raises(AnsibleActionFail, match="host-listener/identity"):
        action.run(task_vars={"svcfiles": source})
