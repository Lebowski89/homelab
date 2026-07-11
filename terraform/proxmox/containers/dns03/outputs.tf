output "dns03_container_id" {
  value = proxmox_virtual_environment_container.dns03.id
}

output "dns03_vmid" {
  value = proxmox_virtual_environment_container.dns03.vm_id
}

output "dns03_hostname" {
  value = var.container_hostname
}

output "dns03_ipv4" {
  value = proxmox_virtual_environment_container.dns03.ipv4
}
