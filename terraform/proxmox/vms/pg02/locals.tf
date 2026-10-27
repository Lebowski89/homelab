locals {
  netbox_dns_ips       = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.dns_ips, {}) : {}
  netbox_internal_zone = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.internal_zone, "") : ""

  # NetBox takes precedence, while var.dns_ips can provide fallback values
  # when remote state is disabled or incomplete.
  dns_ips = merge(
    var.dns_ips,
    local.netbox_dns_ips,
  )

  dns_vip_nameservers = distinct(compact([
    trimspace(lookup(local.dns_ips, "dns_vip_a", "")),
    trimspace(lookup(local.dns_ips, "dns_vip_b", "")),
  ]))

  configured_vm_nameservers = distinct([
    for nameserver in split(" ", trimspace(var.vm_nameserver)) : trimspace(nameserver)
    if trimspace(nameserver) != ""
  ])

  # Preserve the existing behaviour:
  # - use DNS VIPs while NetBox remote state is enabled;
  # - otherwise use explicitly configured nameservers when supplied;
  # - fall back to var.dns_ips VIPs when no explicit nameservers are supplied.
  use_dns_vips = var.enable_netbox_remote_state || length(local.configured_vm_nameservers) == 0

  vm_nameservers = local.use_dns_vips ? local.dns_vip_nameservers : local.configured_vm_nameservers

  # Prefer the NetBox internal zone when available, but retain the explicit
  # fallback if remote state is disabled or does not contain the output.
  vm_searchdomain_source = trimspace(local.netbox_internal_zone) != "" ? local.netbox_internal_zone : var.vm_searchdomain
  vm_searchdomain        = trim(trimspace(local.vm_searchdomain_source), ".")

  # Explicit bootstrap input wins; normal use reads the shared template owner.
  guest_agent_vendor_data_file_id = (
    var.guest_agent_vendor_data_file_id != null
    ? trimspace(var.guest_agent_vendor_data_file_id)
    : data.terraform_remote_state.ubuntu_template[0].outputs.qemu_guest_agent_vendor_data_file_id
  )
}
