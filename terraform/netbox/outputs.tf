output "managed_hosts" {
  value       = keys(var.hosts)
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