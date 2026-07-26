from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
N8N_TOFU_DIR = REPO_ROOT / "terraform/proxmox/vms/n8n"
LOCALS = (N8N_TOFU_DIR / "locals.tf").read_text()
MAIN = (N8N_TOFU_DIR / "main.tf").read_text()


def test_n8n_tofu_normalizes_lookup_names_once():
    assert "vm_name         = trimspace(var.vm_name)" in LOCALS
    assert "vm_gateway_host = trimspace(var.vm_gateway_host)" in LOCALS
    assert "lookup(local.netbox_host_primary_cidrs, local.vm_name" in LOCALS
    assert "lookup(local.netbox_host_primary_ipv4, local.vm_gateway_host" in LOCALS
    assert "lookup(local.netbox_host_primary_ipv4, var.vm_gateway_host" not in LOCALS
    assert "name                 = local.vm_name" in MAIN
    assert "name                 = var.vm_name" not in MAIN


def test_n8n_tofu_preserves_explicit_network_value_precedence():
    assert ('vm_ipv4_address = local.explicit_vm_ipv4_address != "" ? local.explicit_vm_ipv4_address : trimspace(') in LOCALS
    assert ('vm_ipv4_gateway = local.explicit_vm_ipv4_gateway != "" ? local.explicit_vm_ipv4_gateway : trimspace(') in LOCALS
    assert "lookup(local.netbox_host_primary_cidrs, local.vm_name" in LOCALS
    assert "lookup(local.netbox_host_primary_ipv4, local.vm_gateway_host" in LOCALS
