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
  type    = bool
  default = false
}

variable "target_node" {
  type = string
}

variable "template_vmid" {
  type    = number
  default = 9003
}

variable "template_name" {
  type    = string
  default = "ubuntu-2604-lts-cloudinit-template"
}

variable "vm_storage" {
  type = string
}

variable "snippet_storage" {
  type    = string
  default = "local"
}

variable "cloud_image_datastore" {
  type    = string
  default = "local"
}

variable "cloud_image_file_name" {
  type    = string
  default = "ubuntu-26.04-server-cloudimg-amd64.img"
}

variable "cloud_image_url" {
  type    = string
  default = "https://cloud-images.ubuntu.com/releases/resolute/release/ubuntu-26.04-server-cloudimg-amd64.img"
}

variable "cloud_image_checksum" {
  description = "SHA-256 checksum matching the pinned Ubuntu cloud image."
  type        = string
  default     = "117816726abbdefc5ef3e38902e81a76f1c76c3610e709999d0885f9d5d9b477"

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
  type    = string
  default = "ubuntu"
}

variable "ssh_public_key_path" {
  type = string
}
