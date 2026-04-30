output "managed_hosts" {
  value       = keys(var.hosts)
  description = "Hosts managed in NetBox"
}

output "managed_prefixes" {
  value       = [for p in netbox_prefix.this : p.prefix]
  description = "Prefixes managed in NetBox"
}