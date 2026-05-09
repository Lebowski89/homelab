variable "seerr_url" {
  type = string
}

variable "seerr_api_key" {
  type      = string
  sensitive = true
}

variable "domain_int" {
  type = string
}

variable "plex_ip" {
  type = string
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
