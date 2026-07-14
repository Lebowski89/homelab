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

variable "internal_zone" {
  type        = string
  description = "Private DNS zone used to build NetBox device DNS names. Keep the real value in an uncommitted tfvars file."
  default     = ""
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
  description = "Private values for standalone/reserved IP addresses such as VIPs."
  type = map(object({
    ip_address = string
  }))
  default = {}
}
