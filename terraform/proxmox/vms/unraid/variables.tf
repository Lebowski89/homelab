variable "pm_api_url" {
  type = string
}

variable "pm_api_token" {
  type      = string
  sensitive = true
}

variable "pm_tls_insecure" {
  type    = bool
  default = false
}

variable "target_node" {
  type = string
}

variable "unraid_vmid" {
  type    = number
  default = 100
}

variable "unraid_name" {
  type    = string
  default = "UnRaid"
}

variable "unraid_cores" {
  type    = number
  default = 8
}

variable "unraid_sockets" {
  type    = number
  default = 1
}

variable "unraid_cpu_flags" {
  type    = list(string)
  default = ["+pcid"]
}

variable "unraid_memory" {
  type    = number
  default = 32045
}

variable "unraid_machine" {
  type    = string
  default = "q35"
}

variable "unraid_bios" {
  type    = string
  default = "seabios"
}

variable "unraid_boot_order" {
  type    = list(string)
  default = ["usb0"]
}

variable "unraid_scsihw" {
  type    = string
  default = "virtio-scsi-single"
}

variable "unraid_qemu_os" {
  type    = string
  default = "l26"
}

variable "unraid_vga_type" {
  type    = string
  default = "qxl"
}

variable "unraid_uuid" {
  type    = string
  default = "ebfa68e3-e312-42de-8c08-a3c400754edb"
}

variable "unraid_boot_mapping" {
  type    = string
  default = "UnRaid-Boot"
}

variable "unraid_hba_mapping" {
  type    = string
  default = "UnRaid-HBA"
}

variable "unraid_nic_mapping" {
  type    = string
  default = "UnRaid-NIC"
}

variable "unraid_cache_mapping" {
  type    = string
  default = "UnRaid-Cache"
}

variable "unraid_kvm_arguments" {
  type    = string
  default = "-device amd-iommu"
}
