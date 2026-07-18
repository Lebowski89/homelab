variable "enable_netbox_remote_state" {
  description = "Read DNS topology data from the terraform/netbox local state."
  type        = bool
  default     = true
}

variable "netbox_state_path" {
  description = "Path to the terraform/netbox state file."
  type        = string
  default     = "../../netbox/terraform.tfstate"
}

variable "technitium_server" {
  description = "Optional explicit Technitium API URL fallback. Ignored when empty and NetBox remote state is enabled."
  type        = string
  default     = ""
}

variable "technitium_server_host" {
  description = "NetBox host key used to derive the Technitium API server IP."
  type        = string
  default     = "mgt"
}

variable "technitium_server_port" {
  description = "Technitium HTTP API port."
  type        = number
  default     = 5380
}

variable "technitium_api_token" {
  type      = string
  sensitive = true
}

variable "zone_name" {
  description = "Optional explicit DNS zone fallback. Ignored when empty and NetBox remote state provides internal_zone."
  type        = string
  default     = ""
}

variable "technitium_cluster_domain" {
  description = "Technitium DNS cluster domain. Used to derive the catalog zone name."
  type        = string
  default     = "skynet"
}

variable "internal_zone_catalog" {
  description = "Optional explicit Technitium catalog zone. Defaults to `cluster-catalog.<technitium_cluster_domain>`."
  type        = string
  default     = ""
}

variable "traefik_host" {
  description = "NetBox host key used to derive the Traefik backend IPv4 address for internal service A records."
  type        = string
  default     = "mgt"
}

variable "traefik_ipv4" {
  description = "Optional explicit Traefik IPv4 fallback. Ignored when empty and NetBox remote state is enabled."
  type        = string
  default     = ""
}

variable "ttl" {
  type    = number
  default = 300
}
