variable "pm_api_url" {
  type = string
}

variable "pm_api_token" {
  type      = string
  sensitive = true
}

variable "pm_tls_insecure" {
  type    = bool
  default = true
}

variable "target_node" {
  type = string
}

variable "unraid_hba_mapping_name" {
  type    = string
  default = "UnRaid-HBA"
}

variable "unraid_nic_mapping_name" {
  type    = string
  default = "UnRaid-NIC"
}

variable "unraid_cache_mapping_name" {
  type    = string
  default = "UnRaid-Cache"
}

variable "unraid_boot_usb_mapping_name" {
  type    = string
  default = "UnRaid-Boot"
}

variable "unraid_hba_map_id" {
  type = string
}

variable "unraid_hba_map_path" {
  type = string
}

variable "unraid_hba_iommu_group" {
  type = number
}

variable "unraid_nic_map_id" {
  type = string
}

variable "unraid_nic_map_path" {
  type = string
}

variable "unraid_nic_iommu_group" {
  type = number
}

variable "unraid_cache_map_id" {
  type = string
}

variable "unraid_cache_map_path" {
  type = string
}

variable "unraid_cache_iommu_group" {
  type = number
}

variable "unraid_boot_usb_map_id" {
  type = string
}

variable "unraid_boot_usb_map_path" {
  type = string
}

variable "unraid_hba_subsystem_id" {
  type = string
}

variable "unraid_nic_subsystem_id" {
  type = string
}

variable "unraid_cache_subsystem_id" {
  type = string
}
