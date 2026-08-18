variable "enable_netbox_remote_state" {
  description = "Read host and DNS topology data from the terraform/netbox local state."
  type        = bool
  default     = true
}

variable "netbox_state_path" {
  description = "Path to the terraform/netbox state file."
  type        = string
  default     = "../netbox/terraform.tfstate"
}

variable "seerr_url" {
  description = "Optional explicit Seerr URL. Defaults to https://seerr.<domain_int>:<private_https_port>."
  type        = string
  default     = ""
}

variable "private_https_port" {
  description = "Optional private HTTPS port override. Defaults to terraform/netbox, then 8443."
  type        = number
  default     = null

  validation {
    condition     = var.private_https_port == null || (var.private_https_port >= 1 && var.private_https_port <= 65535)
    error_message = "private_https_port must be null or between 1 and 65535."
  }
}

variable "seerr_api_key" {
  type      = string
  sensitive = true
}

variable "domain_int" {
  description = "Optional internal DNS zone fallback. Normally sourced from terraform/netbox outputs.internal_zone."
  type        = string
  default     = ""
}

variable "plex_ip" {
  description = "Optional Plex IP fallback. Normally sourced from terraform/netbox outputs.host_primary_ipv4[\"plex\"]."
  type        = string
  default     = ""
}

variable "tautulli_api_key" {
  type      = string
  sensitive = true
}

variable "radarr_api_key" {
  type      = string
  sensitive = true
}

variable "radarr_4k_api_key" {
  type      = string
  sensitive = true
}

variable "sonarr_api_key" {
  type      = string
  sensitive = true
}

variable "sonarr_4k_api_key" {
  type      = string
  sensitive = true
}

variable "gotify_token" {
  type      = string
  sensitive = true
}
