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

variable "traefik_ipv4" {
  type    = string
  default = "192.168.80.48"
}

variable "ttl" {
  type    = number
  default = 300
}