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
  default = true
}

variable "target_node" {
  type = string
}

variable "template_vmid" {
  type    = number
  default = 9002
}

variable "template_name" {
  type    = string
  default = "ubuntu-2404-lts-cloudinit-template"
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

variable "cloud_image_node_name" {
  type = string
}

variable "cloud_image_file_name" {
  type    = string
  default = "noble-server-cloudimg-amd64.img"
}

variable "cloud_image_url" {
  type    = string
  default = "https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img"
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
