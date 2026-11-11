output "vm_id" {
  description = "Proxmox VMID of the Fedora compatibility-test VM."
  value       = module.fedora_vm.vm_id
}

output "vm_name" {
  description = "Proxmox name of the Fedora compatibility-test VM."
  value       = module.fedora_vm.name
}

output "vm_ipv4_address" {
  description = "Configured IPv4 CIDR; this is not a guest-agent reachability check."
  value       = module.fedora_vm.ipv4_address
}
