output "template_vmid" {
  value = proxmox_virtual_environment_vm.ubuntu_template.vm_id
}

output "template_name" {
  value = proxmox_virtual_environment_vm.ubuntu_template.name
}

output "cloud_image_file_id" {
  value = proxmox_download_file.ubuntu_cloud_image.id
}

output "qemu_guest_agent_vendor_data_file_id" {
  description = "Existing shared QEMU guest-agent vendor data for PostgreSQL clones; owned by this template root."
  value       = proxmox_virtual_environment_file.postgres_qemu_guest_agent_cloud_init.id
}
