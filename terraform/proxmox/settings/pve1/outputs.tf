output "hosts_node_name" {
  value = proxmox_virtual_environment_hosts.hosts.node_name
}

output "vmbr0_name" {
  value = proxmox_network_linux_bridge.vmbr0.name
}

output "vmbr1_name" {
  value = proxmox_network_linux_bridge.vmbr1.name
}

output "dns_domain" {
  value = proxmox_virtual_environment_dns.dns.domain
}

output "dns_servers" {
  value = proxmox_virtual_environment_dns.dns.servers
}

output "timezone" {
  value = proxmox_virtual_environment_time.timezone.time_zone
}
