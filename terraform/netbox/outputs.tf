output "managed_hosts" {
  value       = keys(local.hosts)
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

output "host_primary_ips" {
  value = {
    for k, ip in netbox_ip_address.mgmt : k => ip.ip_address
  }
  description = "Primary management IPs for managed hosts."
}

output "managed_tags" {
  value       = { for k, tag in netbox_tag.this : k => tag.slug }
  description = "Tags managed in NetBox."
}

output "managed_device_custom_fields" {
  value       = { for k, field in netbox_custom_field.device : k => field.name }
  description = "Device custom fields managed in NetBox."
}
