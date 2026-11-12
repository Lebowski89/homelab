locals {
  node_name       = trimspace(var.target_node)
  vm_name         = trimspace(var.vm_name)
  vm_gateway_host = trimspace(var.vm_gateway_host)

  netbox_host_primary_cidrs = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.host_primary_cidrs, {}) : {}
  netbox_host_primary_ipv4  = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.host_primary_ipv4, {}) : {}
  netbox_dns_ips            = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.dns_ips, {}) : {}
  netbox_internal_zone      = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.internal_zone, "") : ""

  # Explicit staging overrides take precedence over inventory-derived fallbacks.
  explicit_vm_ipv4_address = trimspace(var.vm_ipv4_address)
  vm_ipv4_address = local.explicit_vm_ipv4_address != "" ? local.explicit_vm_ipv4_address : trimspace(
    lookup(local.netbox_host_primary_cidrs, local.vm_name, "")
  )

  explicit_vm_ipv4_gateway = trimspace(var.vm_ipv4_gateway)
  vm_ipv4_gateway = local.explicit_vm_ipv4_gateway != "" ? local.explicit_vm_ipv4_gateway : trimspace(
    lookup(local.netbox_host_primary_ipv4, local.vm_gateway_host, "")
  )

  configured_vm_nameservers = distinct(compact([
    for server in var.vm_nameservers : trimspace(server)
  ]))
  netbox_vm_nameservers = distinct(compact([
    trimspace(lookup(local.netbox_dns_ips, "dns_vip_a", "")),
    trimspace(lookup(local.netbox_dns_ips, "dns_vip_b", "")),
  ]))
  vm_nameservers = length(local.configured_vm_nameservers) > 0 ? local.configured_vm_nameservers : local.netbox_vm_nameservers

  vm_search_domain_source = trimspace(var.vm_search_domain) != "" ? var.vm_search_domain : local.netbox_internal_zone
  vm_search_domain        = trim(trimspace(local.vm_search_domain_source), ".")
}
