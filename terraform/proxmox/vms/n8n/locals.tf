locals {
  netbox_dns_ips       = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.dns_ips, {}) : {}
  netbox_internal_zone = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.internal_zone, "") : ""

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
