from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
N8N_TOFU_DIR = REPO_ROOT / "terraform/proxmox/vms/n8n"
LOCALS = (N8N_TOFU_DIR / "locals.tf").read_text()
MAIN = (N8N_TOFU_DIR / "main.tf").read_text()


def single_line_assignments(source):
    assignments = {}
    for line in source.splitlines():
        if line.startswith("  ") and not line.startswith("    ") and "=" in line:
            key, value = line.split("=", 1)
            assignments[key.strip()] = value.strip()
    return assignments


def test_n8n_tofu_structurally_wires_normalized_names_and_network_values():
    local_assignments = single_line_assignments(LOCALS)
    module_inputs = single_line_assignments(MAIN)

    assert local_assignments["vm_name"] == "trimspace(var.vm_name)"
    assert local_assignments["vm_gateway_host"] == "trimspace(var.vm_gateway_host)"
    assert "lookup(local.netbox_host_primary_cidrs, local.vm_name" in LOCALS
    assert "lookup(local.netbox_host_primary_ipv4, local.vm_gateway_host" in LOCALS
    assert "lookup(local.netbox_host_primary_ipv4, var.vm_gateway_host" not in LOCALS
    assert module_inputs["name"] == "local.vm_name"
    assert module_inputs["ipv4_address"] == "local.vm_ipv4_address"
    assert module_inputs["ipv4_gateway"] == "local.vm_ipv4_gateway"


def test_n8n_tofu_preserves_explicit_network_value_precedence():
    assert ('vm_ipv4_address = local.explicit_vm_ipv4_address != "" ? local.explicit_vm_ipv4_address : trimspace(') in LOCALS
    assert ('vm_ipv4_gateway = local.explicit_vm_ipv4_gateway != "" ? local.explicit_vm_ipv4_gateway : trimspace(') in LOCALS
    assert "lookup(local.netbox_host_primary_cidrs, local.vm_name" in LOCALS
    assert "lookup(local.netbox_host_primary_ipv4, local.vm_gateway_host" in LOCALS
