variable "uptime_kuma_endpoint" {
  description = "Base URL for Uptime Kuma. Example: https://uptime-kuma.somedomain.com"
  type        = string
}

variable "uptime_kuma_username" {
  description = "Uptime Kuma username. Can also be supplied with TF_VAR_uptime_kuma_username."
  type        = string
  sensitive   = true
}

variable "uptime_kuma_password" {
  description = "Uptime Kuma password. Can also be supplied with TF_VAR_uptime_kuma_password."
  type        = string
  sensitive   = true
}

variable "uptime_kuma_timeout" {
  description = "Provider connection timeout as a Go duration string."
  type        = string
  default     = "2m"
}

variable "uptime_kuma_per_attempt_timeout" {
  description = "Provider connection per_attempt_timeout as a Go duration string."
  type        = string
  default     = "20s"
}

variable "uptime_kuma_max_retries" {
  description = "Provider connection maximum retry count."
  type        = number
  default     = 5
}

variable "cloudflare_zone" {
  description = "Parent Cloudflare zone/domain."
  type        = string
}

variable "internal_zone" {
  description = "Internal/private DNS zone used by Traefik private routes."
  type        = string
}

variable "private_https_port" {
  description = "Traefik private HTTPS entrypoint port."
  type        = number
  default     = 8443
}

variable "postgres_monitor_connection_strings" {
  description = "PostgreSQL connection strings for Uptime Kuma PostgreSQL monitors. These are sensitive and will be stored in OpenTofu state."
  type        = map(string)
  sensitive   = true
  default     = {}
}

variable "enable_gotify_notification" {
  description = "Create and attach the Gotify notification channel to monitors by default."
  type        = bool
  default     = true
}

variable "gotify_server_url" {
  description = "Gotify URL as reached by Uptime Kuma."
  type        = string
}

variable "gotify_application_token" {
  description = "Gotify application token for Uptime Kuma notifications."
  type        = string
  sensitive   = true
  default     = null
}

variable "gotify_priority" {
  description = "Gotify message priority."
  type        = number
  default     = 8
}

variable "enable_netbox_remote_state" {
  description = "Read host/IP and DNS topology data from the terraform/netbox local state."
  type        = bool
  default     = true
}

variable "netbox_state_path" {
  description = "Path to the terraform/netbox state file."
  type        = string
  default     = "../netbox/terraform.tfstate"
}

variable "host_ips" {
  description = "Fallback or override private host management IPs used by direct, ping, and TCP monitors. Normally sourced from terraform/netbox outputs.host_primary_ipv4."
  type        = map(string)
  default     = {}
}

variable "dns_ips" {
  description = "Fallback or override DNS node/VIP IPs used by DNS-related monitors. Normally sourced from terraform/netbox outputs.dns_ips."
  type        = map(string)
  default     = {}
}
