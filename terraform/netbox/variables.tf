variable "netbox_server_url" {
  type        = string
  description = "NetBox URL, including scheme and port if required. Example: https://netbox.int.example.com:8443"
}

variable "netbox_api_token" {
  type        = string
  description = "NetBox API token."
  sensitive   = true
}

variable "netbox_allow_insecure_https" {
  type        = bool
  description = "Allow self-signed HTTPS certificates."
  default     = false
}

variable "netbox_request_timeout" {
  type        = number
  description = "NetBox API request timeout in seconds."
  default     = 30
}

variable "netbox_skip_version_check" {
  type        = bool
  description = "Skip provider NetBox version compatibility check."
  default     = false
}

variable "site" {
  description = "Default site details in NetBox."
  type = object({
    name   = string
    slug   = string
    status = optional(string, "active")
  })
}

variable "manufacturers" {
  description = "Manufacturers to manage."
  type = map(object({
    name = string
    slug = optional(string)
  }))
  default = {
    homelab = {
      name = "Homelab"
      slug = "homelab"
    }
  }
}

variable "device_roles" {
  description = "Device roles to manage."
  type = map(object({
    name      = string
    slug      = optional(string)
    color_hex = optional(string, "9e9e9e")
  }))
}

variable "device_types" {
  description = "Device types to manage."
  type = map(object({
    model            = string
    slug             = optional(string)
    manufacturer_key = optional(string, "homelab")
    part_number      = optional(string)
    is_full_depth    = optional(bool)
    u_height         = optional(number)
  }))
}

variable "device_type_interfaces" {
  description = "Interface templates attached to device types."
  type = map(list(object({
    name  = string
    label = optional(string)
    type  = string
  })))
  default = {}
}

variable "prefixes" {
  description = "IPv4/IPv6 prefixes to manage."
  type = map(object({
    prefix        = string
    status        = optional(string, "active")
    description   = optional(string)
    is_pool       = optional(bool, false)
    mark_utilized = optional(bool, false)
    site_key      = optional(string, "homelab")
  }))
  default = {}
}

variable "hosts" {
  description = "Repo-managed physical/bare-metal hosts to create as NetBox devices."
  type = map(object({
    mgmt_ip         = string
    dns_name        = optional(string)
    description     = optional(string)
    status          = optional(string, "active")
    site_key        = optional(string, "homelab")
    role_key        = optional(string, "server")
    device_type_key = optional(string, "generic_host")
    interface_name  = optional(string, "mgmt0")
    interface_type  = optional(string, "1000base-t")
  }))
  default = {}
}

variable "reserved_ips" {
  description = "Extra IP addresses not assigned to a device interface, such as VIPs, service endpoints, DNS records, or manually managed devices."
  type = map(object({
    ip_address  = string
    status      = optional(string, "active")
    dns_name    = optional(string)
    description = optional(string)
  }))
  default = {}
}