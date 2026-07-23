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

variable "template_node_name" {
  type = string
}

variable "template_datastore" {
  type    = string
  default = "local"
}

variable "template_file_name" {
  type    = string
  default = "noble-server-cloudimg-amd64-root.tar.xz"
}

variable "template_url" {
  type    = string
  default = "https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64-root.tar.xz"
}
