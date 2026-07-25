locals {
  netbox_dns_ips           = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.dns_ips, {}) : {}
  netbox_internal_zone     = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.internal_zone, "") : ""
  netbox_host_primary_ipv4 = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.host_primary_ipv4, {}) : {}
  netbox_host_primary_cidrs = var.enable_netbox_remote_state ? try(
    data.terraform_remote_state.netbox[0].outputs.host_primary_cidrs,
    {},
  ) : {}

  vm_name = trimspace(var.vm_name)

  explicit_vm_ipv4_address = trimspace(var.vm_ipv4_address)
  vm_ipv4_address = local.explicit_vm_ipv4_address != "" ? local.explicit_vm_ipv4_address : trimspace(
    lookup(local.netbox_host_primary_cidrs, local.vm_name, "")
  )

  explicit_vm_ipv4_gateway = trimspace(var.vm_ipv4_gateway)
  vm_ipv4_gateway = local.explicit_vm_ipv4_gateway != "" ? local.explicit_vm_ipv4_gateway : trimspace(
    lookup(local.netbox_host_primary_ipv4, var.vm_gateway_host, "")
  )

  dns_ips = merge(
    var.dns_ips,
    local.netbox_dns_ips,
  )

  dns_vip_nameservers = distinct(compact([
    trimspace(lookup(local.dns_ips, "dns_vip_a", "")),
    trimspace(lookup(local.dns_ips, "dns_vip_b", "")),
  ]))

  configured_vm_nameservers = distinct(compact([
    for nameserver in var.vm_nameservers : trimspace(nameserver)
  ]))

  use_dns_vips = var.enable_netbox_remote_state || length(local.configured_vm_nameservers) == 0
  vm_nameservers = (
    local.use_dns_vips
    ? local.dns_vip_nameservers
    : local.configured_vm_nameservers
  )

  vm_search_domain_source = (
    trimspace(local.netbox_internal_zone) != ""
    ? local.netbox_internal_zone
    : var.vm_search_domain
  )
  vm_search_domain = trim(trimspace(local.vm_search_domain_source), ".")
}
