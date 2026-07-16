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

variable "pm_ssh_username" {
  type      = string
  default   = "root"
  sensitive = true
}

variable "pm_ssh_host" {
  type      = string
  sensitive = true
}

variable "tailscale_auth_key" {
  type      = string
  sensitive = true
}

variable "target_node" {
  type = string
}

variable "container_vmid" {
  type    = number
  default = 253
}

variable "container_hostname" {
  type    = string
  default = "dns03"
}

variable "container_description" {
  type    = string
  default = "Technitium DNS tertiary LXC managed by OpenTofu"
}

variable "container_protection" {
  type    = bool
  default = false
}

variable "container_storage" {
  type = string
}

variable "template_file_id" {
  type = string
}

variable "container_bridge" {
  type    = string
  default = "vmbr0"
}

variable "container_ip" {
  type = string
}

variable "container_gateway" {
  type = string
}

variable "container_dns_domain" {
  description = "Optional container DNS search domain fallback. Ignored while enable_netbox_remote_state is true."
  type        = string
  default     = ""
}

variable "container_dns_servers" {
  description = "Optional container DNS servers fallback. Ignored while enable_netbox_remote_state is true."
  type        = list(string)
  default     = []
}

variable "container_cores" {
  type    = number
  default = 1
}

variable "container_memory" {
  type    = number
  default = 512
}

variable "container_swap" {
  type    = number
  default = 512
}

variable "container_disk_size" {
  type    = number
  default = 8
}

variable "ssh_public_key_path" {
  type = string
}

variable "enable_netbox_remote_state" {
  description = "Read DNS topology data from the terraform/netbox local state."
  type        = bool
  default     = true
}

variable "netbox_state_path" {
  description = "Path to the terraform/netbox state file."
  type        = string
  default     = "../../../netbox/terraform.tfstate"
}

variable "dns_ips" {
  description = "Fallback DNS node/VIP IPs. Normally sourced from terraform/netbox outputs.dns_ips."
  type        = map(string)
  default     = {}
}
