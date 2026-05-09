output "unraid_hba_mapping_name" {
  value = proxmox_hardware_mapping_pci.unraid_hba.name
}

output "unraid_nic_mapping_name" {
  value = proxmox_hardware_mapping_pci.unraid_nic.name
}

output "unraid_cache_mapping_name" {
  value = proxmox_hardware_mapping_pci.unraid_cache.name
}

output "unraid_boot_usb_mapping_name" {
  value = proxmox_hardware_mapping_usb.unraid_boot.name
}
