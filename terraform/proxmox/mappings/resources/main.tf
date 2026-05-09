resource "proxmox_hardware_mapping_pci" "unraid_hba" {
  name = var.unraid_hba_mapping_name

  map = [
    {
      node         = var.target_node
      id           = var.unraid_hba_map_id
      path         = var.unraid_hba_map_path
      iommu_group  = var.unraid_hba_iommu_group
      subsystem_id = var.unraid_hba_subsystem_id
    }
  ]
}

resource "proxmox_hardware_mapping_pci" "unraid_nic" {
  name = var.unraid_nic_mapping_name

  map = [
    {
      node         = var.target_node
      id           = var.unraid_nic_map_id
      path         = var.unraid_nic_map_path
      iommu_group  = var.unraid_nic_iommu_group
      subsystem_id = var.unraid_nic_subsystem_id
    }
  ]
}

resource "proxmox_hardware_mapping_pci" "unraid_cache" {
  name = var.unraid_cache_mapping_name

  map = [
    {
      node         = var.target_node
      id           = var.unraid_cache_map_id
      path         = var.unraid_cache_map_path
      iommu_group  = var.unraid_cache_iommu_group
      subsystem_id = var.unraid_cache_subsystem_id
    }
  ]
}

resource "proxmox_hardware_mapping_usb" "unraid_boot" {
  name = var.unraid_boot_usb_mapping_name

  map = [
    {
      node = var.target_node
      id   = var.unraid_boot_usb_map_id
      path = var.unraid_boot_usb_map_path
    }
  ]
}
