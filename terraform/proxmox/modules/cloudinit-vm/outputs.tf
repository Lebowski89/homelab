output "id" {
  description = "Provider resource ID for the VM."
  value       = proxmox_virtual_environment_vm.this.id
}

output "name" {
  description = "Proxmox VM name."
  value       = proxmox_virtual_environment_vm.this.name
}

output "vm_id" {
  description = "Proxmox VMID."
  value       = proxmox_virtual_environment_vm.this.vm_id
}

output "ipv4_address" {
  description = "Configured static IPv4 address in CIDR notation."
  value       = var.ipv4_address
}
