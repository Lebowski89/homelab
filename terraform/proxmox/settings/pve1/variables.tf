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

variable "node_management_ip" {
  type = string
}

variable "local_domain" {
  type    = string
  default = "home.arpa"
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

variable "dns_domain" {
  type    = string
  default = "home.arpa"
}

variable "dns_servers" {
  type    = list(string)
  default = []
}

variable "timezone" {
  type    = string
  default = "Australia/Melbourne"
}
