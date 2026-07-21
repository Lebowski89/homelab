output "n8n_vm_id" {
  description = "Proxmox VMID assigned to the n8n VM."
  value       = module.n8n_vm.vm_id
}

output "n8n_vm_name" {
  description = "Proxmox name of the n8n VM."
  value       = module.n8n_vm.name
}

output "n8n_vm_ipv4_address" {
  description = "Static IPv4 address configured for the n8n VM."
  value       = module.n8n_vm.ipv4_address
}
