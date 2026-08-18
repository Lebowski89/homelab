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

variable "cloudflare_zone" {
  description = "Public Cloudflare DNS zone used by dependent OpenTofu roots."
  type        = string
  sensitive   = true

  validation {
    condition     = trimspace(var.cloudflare_zone) != ""
    error_message = "cloudflare_zone must be set in terraform/netbox/private.auto.tfvars."
  }
}

variable "internal_zone" {
  type        = string
  description = "Private DNS zone used to build NetBox device DNS names. Keep the real value in an uncommitted tfvars file."
  default     = ""
}

variable "private_https_port" {
  type        = number
  description = "Client-facing HTTPS port for private Traefik application routes."
  default     = 8443

  validation {
    condition     = var.private_https_port >= 1 && var.private_https_port <= 65535
    error_message = "private_https_port must be between 1 and 65535."
  }
}

variable "host_private_values" {
  description = "Private per-host values such as LAN IPs, DNS names, and custom fields."
  type = map(object({
    mgmt_ip       = string
    custom_fields = optional(any, {})
  }))
  default = {}
}

variable "reserved_ip_private_values" {
  description = "Private values for reserved infrastructure IPs, such as Keepalived DNS VIPs."
  type = map(object({
    ip_address = string
  }))

  validation {
    condition = alltrue([
      contains(keys(var.reserved_ip_private_values), "dns_vip_a"),
      contains(keys(var.reserved_ip_private_values), "dns_vip_b"),
    ])
    error_message = "reserved_ip_private_values must include dns_vip_a and dns_vip_b."
  }

  validation {
    condition = alltrue([
      for reserved_ip in var.reserved_ip_private_values :
      can(cidrhost(reserved_ip.ip_address, 0))
    ])
    error_message = "Each reserved_ip_private_values entry must provide ip_address as a valid CIDR address, for example 192.168.80.53/24."
  }
}
