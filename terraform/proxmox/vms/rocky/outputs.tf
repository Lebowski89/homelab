output "vm_id" {
  description = "Proxmox VMID of the staged Rocky management VM."
  value       = module.rocky_vm.vm_id
}

output "vm_name" {
  description = "Proxmox name of the staged Rocky management VM."
  value       = module.rocky_vm.name
}

output "vm_ipv4_address" {
  description = "Configured IPv4 CIDR; this is not a guest-agent reachability check."
  value       = module.rocky_vm.ipv4_address
}
