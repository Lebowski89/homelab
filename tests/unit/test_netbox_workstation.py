from __future__ import annotations

import re
from ast import literal_eval
from pathlib import Path

import yaml
from jinja2 import StrictUndefined
from jinja2.nativetypes import NativeEnvironment

REPO_ROOT = Path(__file__).resolve().parents[2]
NETBOX_LOCALS_PATH = REPO_ROOT / "terraform/netbox/locals.tf"
NETBOX_MAIN_PATH = REPO_ROOT / "terraform/netbox/main.tf"
NETBOX_PRIVATE_SAMPLE_PATH = REPO_ROOT / "terraform/netbox/private.auto.tfvars.sample"
NETBOX_INVENTORY_SAMPLE_PATH = REPO_ROOT / "ansible/netbox.yml.sample"
WORKSTATION_HOST = "blacktop"

CONTAINER_HOST_FIELDS = {
    "container_host_puid",
    "container_host_pgid",
    "container_host_appdata_root",
    "container_host_data_root",
}


def hcl_block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    assert match is not None, name
    start = match.end() - 1
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start + 1 : index]
    raise AssertionError(f"Unclosed HCL block: {name}")


def hcl_scalar(block: str, name: str):
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*([^\n]+)$", block)
    assert match is not None, name
    return literal_eval(match.group(1).strip())


def hcl_list(block: str, name: str) -> list[str]:
    match = re.search(rf"(?ms)^\s*{re.escape(name)}\s*=\s*(\[.*?^\s*\])", block)
    assert match is not None, name
    return literal_eval(match.group(1))


def render_inventory_expression(expression: str, **variables):
    environment = NativeEnvironment(undefined=StrictUndefined)
    environment.filters["regex_replace"] = lambda value, pattern, replacement: re.sub(pattern, replacement, value)
    return environment.from_string("{{ " + expression + " }}").render(**variables)


def test_netbox_defines_workstation_role_tag_and_generic_laptop_type():
    source = NETBOX_LOCALS_PATH.read_text()
    role = hcl_block(hcl_block(source, "device_roles"), "workstation")
    tag = hcl_block(hcl_block(source, "netbox_tags"), "workstation")
    device_type = hcl_block(hcl_block(source, "device_types"), "generic_laptop")

    assert hcl_scalar(role, "name") == "Workstation"
    assert hcl_scalar(role, "slug") == "workstation"
    assert hcl_scalar(tag, "name") == "workstation"
    assert hcl_scalar(tag, "slug") == "workstation"
    assert hcl_scalar(tag, "description") == "Interactive workstation hosts managed by Ansible."
    assert hcl_scalar(device_type, "model") == "Generic Laptop"
    assert hcl_scalar(device_type, "slug") == "generic-laptop"
    assert hcl_scalar(device_type, "manufacturer_key") == "homelab"


def test_netbox_workstation_host_uses_workstation_and_podman_infrastructure_tags():
    base_hosts = hcl_block(NETBOX_LOCALS_PATH.read_text(), "base_hosts")
    workstation = hcl_block(base_hosts, WORKSTATION_HOST)

    assert hcl_scalar(workstation, "role_key") == "workstation"
    assert hcl_scalar(workstation, "device_type_key") == "generic_laptop"
    assert hcl_list(workstation, "tags") == ["skynet", "workstation", "podman", "podman_install"]
    assert base_hosts.count('role_key        = "workstation"') == 1
    assert base_hosts.count('device_type_key = "generic_laptop"') == 1


def test_workstation_private_sample_has_connection_and_container_host_fields():
    private_hosts = hcl_block(NETBOX_PRIVATE_SAMPLE_PATH.read_text(), "host_private_values")
    workstation = hcl_block(private_hosts, WORKSTATION_HOST)
    custom_fields = hcl_block(workstation, "custom_fields")

    assert hcl_scalar(workstation, "mgmt_ip") == "192.168.xx.xx/24"
    assert hcl_scalar(custom_fields, "ansible_user") == "user"
    assert hcl_scalar(custom_fields, "ssh_port") == "22"
    assert hcl_scalar(custom_fields, "tailscale_ip") == "100.xx.xx.xx"
    expected_container_values = {
        "container_host_puid": "1000",
        "container_host_pgid": "1000",
        "container_host_appdata_root": "/opt",
        "container_host_data_root": "/opt",
    }
    assert {field_name: hcl_scalar(custom_fields, field_name) for field_name in CONTAINER_HOST_FIELDS} == expected_container_values


def test_netbox_inventory_keeps_lan_primary_ip_and_prefers_tailscale_for_ansible():
    inventory = yaml.safe_load(NETBOX_INVENTORY_SAMPLE_PATH.read_text())
    compose = inventory["compose"]
    primary_ip4 = {"address": "192.0.2.25/24"}
    custom_fields = {
        "ansible_user": "workstation-user",
        "ssh_port": "22",
        "tailscale_ip": "100.64.0.25",
    }

    assert render_inventory_expression(compose["ansible_host"], custom_fields=custom_fields, primary_ip4=primary_ip4) == "100.64.0.25"
    assert render_inventory_expression(compose["ansible_host"], custom_fields={}, primary_ip4=primary_ip4) == "192.0.2.25"
    assert render_inventory_expression(compose["ansible_user"], custom_fields=custom_fields) == "workstation-user"
    assert str(render_inventory_expression(compose["ansible_port"], custom_fields=custom_fields)) == "22"
    assert render_inventory_expression(compose["local_ip"], primary_ip4=primary_ip4) == "192.0.2.25"
    assert inventory["query_filters"] == [{"has_primary_ip": "true"}]
    assert inventory["group_by"] == ["device_roles", "tags"]


def test_workstation_uses_shared_netbox_primary_ip_resource_chain():
    locals_source = NETBOX_LOCALS_PATH.read_text()
    main_source = NETBOX_MAIN_PATH.read_text()

    assert "mgmt_ip = var.host_private_values[host_key].mgmt_ip" in locals_source
    assert 'resource "netbox_device_interface" "mgmt"' in main_source
    assert 'resource "netbox_ip_address" "mgmt"' in main_source
    assert "ip_address          = each.value.mgmt_ip" in main_source
    assert 'resource "netbox_device_primary_ip" "hosts"' in main_source
    assert "ip_address_id      = netbox_ip_address.mgmt[each.key].id" in main_source
