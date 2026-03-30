output "postgres_vm_names" {
  value = keys(proxmox_vm_qemu.postgres)
}

output "postgres_vm_ips" {
  value = {
    for name, vm in var.postgres_vms : name => vm.ip
  }
}