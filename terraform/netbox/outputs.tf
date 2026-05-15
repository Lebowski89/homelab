output "managed_hosts" {
  value       = sort(keys(local.hosts))
  description = "Hosts managed as NetBox devices."
}

output "managed_prefixes" {
  value       = { for k, p in netbox_prefix.this : k => p.prefix }
  description = "Prefixes managed in NetBox."
}

output "managed_reserved_ips" {
  value       = { for k, ip in netbox_ip_address.reserved : k => ip.ip_address }
  description = "Standalone/reserved IP addresses managed in NetBox."
}

output "host_primary_ipv4" {
  value = {
    for host_key, ip in netbox_ip_address.mgmt :
    host_key => split("/", ip.ip_address)[0]
  }

  description = "Primary management IPv4 addresses for managed hosts, without CIDR suffix."
}

output "host_primary_cidrs" {
  value = {
    for host_key, ip in netbox_ip_address.mgmt :
    host_key => ip.ip_address
  }

  description = "Primary management IPv4 addresses for managed hosts, including CIDR suffix."
}

output "host_tailscale_ipv4" {
  value = {
    for host_key, host in local.hosts :
    host_key => try(host.custom_fields.tailscale_ip, null)
    if try(host.custom_fields.tailscale_ip, null) != null
  }

  description = "Tailscale IPv4 addresses for managed hosts."
}

output "host_dns_names" {
  value = {
    for host_key, host in local.hosts :
    host_key => try(host.dns_name, null)
  }

  description = "DNS names assigned to managed hosts."
}

output "hosts_by_tag" {
  value = {
    for tag_key in keys(local.netbox_tags) :
    tag_key => sort([
      for host_key, host in local.hosts :
      host_key
      if contains(try(host.tags, []), tag_key)
    ])
  }

  description = "Managed hosts grouped by local NetBox tag key."
}

output "managed_tags" {
  value       = { for k, tag in netbox_tag.this : k => tag.slug }
  description = "Tags managed in NetBox."
}

output "managed_device_custom_fields" {
  value       = { for k, field in netbox_custom_field.device : k => field.name }
  description = "Device custom fields managed in NetBox."
}
