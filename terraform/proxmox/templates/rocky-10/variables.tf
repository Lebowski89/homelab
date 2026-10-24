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
  description = "Explicitly selected, verified unused Proxmox template VMID. No automatic allocation or Ubuntu VMID default."
  type        = number
  nullable    = false

  validation {
    condition     = var.template_vmid >= 100 && var.template_vmid <= 999999999 && floor(var.template_vmid) == var.template_vmid
    error_message = "template_vmid must be an explicitly selected integer from 100 to 999999999; automatic allocation is not allowed."
  }
}

variable "template_name" {
  type    = string
  default = "rocky-10-cloudinit-template"
}

variable "vm_storage" {
  type = string
}

variable "snippet_storage" {
  description = "Snippet datastore setting retained for parity with Ubuntu; this template does not create snippets."
  type        = string
  default     = "local"
}

variable "cloud_image_datastore" {
  type    = string
  default = "local"
}

variable "cloud_image_file_name" {
  description = "Node-local ISO storage filename; .img retains the original QCOW2 payload."
  type        = string
  default     = "Rocky-10-GenericCloud-Base-10.2-20260525.0.x86_64.img"
}

variable "cloud_image_url" {
  type    = string
  default = "https://download.rockylinux.org/pub/rocky/10.2/images/x86_64/Rocky-10-GenericCloud-Base-10.2-20260525.0.x86_64.qcow2"
}

variable "cloud_image_checksum" {
  description = "Official SHA-256 from the pinned Rocky image's .qcow2.CHECKSUM file; see docs/rocky-10-template.md."
  type        = string
  default     = "9fc9e9ff16888bb68ac39b0392e25c9c92684d50c85f1cce6ab549363bbc4b48"

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
  description = "Cloud-init administrative user; Rocky cloud images conventionally use rocky."
  type        = string
  default     = "rocky"
}

variable "ssh_public_key_path" {
  type = string
}
