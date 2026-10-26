output "template_vmid" {
  value = proxmox_virtual_environment_vm.rocky_template.vm_id
}

output "template_name" {
  value = proxmox_virtual_environment_vm.rocky_template.name
}

output "cloud_image_file_id" {
  value = proxmox_download_file.rocky_cloud_image.id
}
