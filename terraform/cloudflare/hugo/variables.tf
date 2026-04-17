variable "cloudflare_api_token" {
  type      = string
  sensitive = true
}

variable "cloudflare_zone_id" {
  type = string
}

variable "apex_name" {
  type    = string
  default = "@"
}

variable "ttl" {
  type    = number
  default = 1
}