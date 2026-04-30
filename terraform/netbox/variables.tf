variable "netbox_server_url" {
  type        = string
  description = "NetBox URL, e.g. https://netbox.example.com"
}

variable "netbox_api_token" {
  type        = string
  description = "NetBox API token"
  sensitive   = true
}

variable "netbox_allow_insecure_https" {
  type        = bool
  description = "Allow self-signed HTTPS certificates"
  default     = false
}

variable "site" {
  description = "Site details in NetBox"
  type = object({
    name   = string
    slug   = string
    status = string
  })
}

variable "device_role" {
  description = "Device role details"
  type = object({
    name      = string
    slug      = string
    color_hex = string
  })
}

variable "device_type" {
  description = "Single shared device type for homelab hosts"
  type = object({
    model = string
    slug  = string
  })
}

variable "prefixes" {
  description = "IPv4 prefixes to manage"
  type = map(object({
    prefix      = string
    description = optional(string)
    status      = optional(string, "active")
    is_pool     = optional(bool, false)
  }))
}

variable "hosts" {
  description = "Homelab hosts and management IPs"
  type = map(object({
    mgmt_ip     = string
    dns_name    = optional(string)
    description = optional(string)
    status      = optional(string, "active")
  }))
}