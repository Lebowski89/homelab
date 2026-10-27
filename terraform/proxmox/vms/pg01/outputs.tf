output "postgres_vm_names" {
  description = "VM names owned by this root (one entry; retains the former output shape)."
  value       = [module.postgres_vm.name]
}

output "postgres_vm_ips" {
  description = "Configured VM addresses owned by this root (one entry)."
  value       = { (var.postgres_vm.name) = var.postgres_vm.ip }
}

output "vm_id" {
  description = "Existing Proxmox VMID owned by this root."
  value       = module.postgres_vm.vm_id
}
