variable "pm_api_url" {
  type = string
}

variable "pm_api_token" {
  type      = string
  sensitive = true
}

variable "pm_tls_insecure" {
  description = "Disable Proxmox API TLS certificate verification. Keep false when the Proxmox CA is trusted; set true only for an explicitly accepted self-signed or untrusted certificate."
  type        = bool
  default     = false
}

variable "target_node" {
  description = "Proxmox node name."
  type        = string

  validation {
    condition     = trimspace(var.target_node) != ""
    error_message = "target_node must not be empty."
  }
}

variable "node_management_ip" {
  type = string
}

variable "network_vmbr0_name" {
  type    = string
  default = "vmbr0"
}

variable "network_vmbr0_address" {
  type = string
}

variable "network_vmbr0_gateway" {
  type = string
}

variable "network_vmbr0_autostart" {
  type    = bool
  default = true
}

variable "network_vmbr0_ports" {
  type    = list(string)
  default = []
}

variable "network_vmbr1_name" {
  type    = string
  default = "vmbr1"
}

variable "network_vmbr1_ports" {
  type    = list(string)
  default = []
}

variable "network_vmbr1_autostart" {
  type    = bool
  default = true
}

variable "local_domain" {
  description = "Optional local host domain fallback. Ignored while enable_netbox_remote_state is true."
  type        = string
  default     = ""
}

variable "dns_domain" {
  description = "Optional Proxmox DNS search domain fallback. Ignored while enable_netbox_remote_state is true."
  type        = string
  default     = ""
}

variable "dns_servers" {
  description = "Optional Proxmox DNS servers fallback. Ignored while enable_netbox_remote_state is true."
  type        = list(string)
  default     = []
}

variable "timezone" {
  type    = string
  default = "Australia/Melbourne"
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
