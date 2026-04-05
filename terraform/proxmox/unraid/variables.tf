variable "pm_api_url" {
  type = string
}

variable "pm_api_token_id" {
  type      = string
  sensitive = true
}

variable "pm_api_token_secret" {
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
  type    = string
  default = "order=usb0"
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

variable "unraid_efi_storage" {
  type    = string
  default = "local-zfs"
}

variable "unraid_tpm_storage" {
  type    = string
  default = "local-zfs"
}

variable "unraid_raw_disk_path" {
  type    = string
  default = "/dev/sdj"
}

variable "unraid_uuid" {
  type    = string
  default = "ebfa68e3-e312-42de-8c08-a3c400754edb"
}