variable "pm_api_url" {
  type = string
}

variable "pm_api_token" {
  type      = string
  sensitive = true
}

variable "pm_ssh_username" {
  type      = string
  sensitive = true
}

variable "pm_ssh_host" {
  type      = string
  sensitive = true
}

variable "pm_tls_insecure" {
  description = "Disable Proxmox API TLS certificate verification. Keep false when the Proxmox CA is trusted; set true only for an explicitly accepted self-signed or untrusted certificate."
  type        = bool
  default     = false
}

variable "target_node" {
  type = string
}

variable "template_vmid" {
  description = "Explicitly selected, verified unused Proxmox template VMID. No automatic allocation or another template's VMID default."
  type        = number
  nullable    = false

  validation {
    condition     = var.template_vmid >= 100 && var.template_vmid <= 999999999 && floor(var.template_vmid) == var.template_vmid
    error_message = "template_vmid must be an explicitly selected integer from 100 to 999999999; automatic allocation is not allowed."
  }
}

variable "template_name" {
  type    = string
  default = "fedora-44-cloudinit-template"
}

variable "vm_storage" {
  type = string
}

variable "cloud_image_datastore" {
  type    = string
  default = "local"
}

variable "cloud_image_file_name" {
  description = "Node-local ISO storage filename; .img retains the original QCOW2 payload."
  type        = string
  default     = "Fedora-Cloud-Base-Generic-44-1.7.x86_64.img"
}

variable "cloud_image_url" {
  type    = string
  default = "https://dl.fedoraproject.org/pub/fedora/linux/releases/44/Cloud/x86_64/images/Fedora-Cloud-Base-Generic-44-1.7.x86_64.qcow2"
}

variable "cloud_image_checksum" {
  description = "Official SHA-256 from Fedora-Cloud-44-1.7-x86_64-CHECKSUM; see docs/fedora-44-template.md."
  type        = string
  default     = "28680fe5b371a5a82ebf43a31926e086a168e59949d03969c5093e7071f90b7f"

  validation {
    condition     = can(regex("^[0-9a-fA-F]{64}$", var.cloud_image_checksum))
    error_message = "cloud_image_checksum must be a 64-character SHA-256 checksum."
  }
}

variable "template_cores" {
  type    = number
  default = 2
}

variable "template_memory" {
  type    = number
  default = 2048
}

variable "template_bridge" {
  type    = string
  default = "vmbr0"
}

variable "template_ci_user" {
  description = "Cloud-init administrative user; Fedora cloud images conventionally use fedora."
  type        = string
  default     = "fedora"
}

variable "ssh_public_key_path" {
  type = string
}
