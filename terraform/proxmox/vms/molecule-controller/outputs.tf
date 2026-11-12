output "vm_id" {
  description = "Proxmox VMID of the dedicated Molecule controller VM."
  value       = module.controller_vm.vm_id
}

output "vm_name" {
  description = "Proxmox name of the dedicated Molecule controller VM."
  value       = module.controller_vm.name
}

output "vm_ipv4_address" {
  description = "Configured IPv4 CIDR; this is not a guest-agent reachability check."
  value       = module.controller_vm.ipv4_address
}
