variable "technitium_server" {
  type = string
}

variable "technitium_api_token" {
  type      = string
  sensitive = true
}

variable "zone_name" {
  type    = string
  default = "int.nosugarmaxtaste.com"
}

variable "internal_zone_catalog" {
  type        = string
  description = "Technitium catalog zone used to replicate/share the internal zone across the DNS cluster."
  default     = "cluster-catalog.skynet"
}

variable "traefik_ipv4" {
  type    = string
  default = "192.168.80.48"
}

variable "ttl" {
  type    = number
  default = 300
}