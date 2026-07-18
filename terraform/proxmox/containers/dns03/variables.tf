variable "pm_api_url" {
  description = "Optional explicit Proxmox API URL fallback. Defaults to https://<target_node_ip>:<pm_api_port>/ from NetBox."
  type        = string
  default     = ""
}

variable "pm_api_port" {
  description = "Proxmox API port."
  type        = number
  default     = 8006
}

variable "pm_api_token" {
  description = "Proxmox API token."
  type        = string
  sensitive   = true
}

variable "pm_tls_insecure" {
  description = "Allow insecure TLS when connecting to the Proxmox API."
  type        = bool
  default     = false
}

variable "pm_ssh_username" {
  description = "SSH username used to run pct commands on the Proxmox host."
  type        = string
  default     = "root"
  sensitive   = true
}

variable "pm_ssh_host" {
  description = "Optional explicit Proxmox SSH host fallback. Defaults to target_node IP from NetBox."
  type        = string
  default     = ""
}

variable "pm_ssh_port" {
  description = "Proxmox SSH port."
  type        = number
  default     = 22
}

variable "tailscale_auth_key" {
  description = "Ephemeral/auth key used to join the dns03 LXC to Tailscale."
  type        = string
  sensitive   = true
}

variable "target_node" {
  description = "Proxmox node that hosts the dns03 LXC."
  type        = string
  default     = "pve1"
}

variable "container_vmid" {
  description = "Proxmox VMID for the dns03 LXC."
  type        = number
  default     = 253
}

variable "container_hostname" {
  description = "Hostname for the dns03 LXC. Also used as the NetBox host key when deriving the container IP."
  type        = string
  default     = "dns03"
}

variable "container_description" {
  description = "Description shown in Proxmox for the dns03 LXC."
  type        = string
  default     = "Technitium DNS tertiary LXC managed by OpenTofu"
}

variable "container_protection" {
  description = "Enable Proxmox protection on the dns03 LXC."
  type        = bool
  default     = false
}

variable "container_storage" {
  description = "Proxmox datastore for the dns03 LXC root disk."
  type        = string
  default     = "local-zfs"
}

variable "template_file_id" {
  description = "Ubuntu LXC template file ID."
  type        = string
  default     = "local:vztmpl/noble-server-cloudimg-amd64-root.tar.xz"
}

variable "container_bridge" {
  description = "Proxmox bridge used by the dns03 LXC."
  type        = string
  default     = "vmbr0"
}

variable "container_ip" {
  description = "Optional explicit dns03 container CIDR address fallback. Defaults to NetBox host_primary_ipv4[container_hostname]/container_prefix_length."
  type        = string
  default     = ""
}

variable "container_prefix_length" {
  description = "CIDR prefix length used when deriving container_ip from NetBox host_primary_ipv4."
  type        = number
  default     = 24
}

variable "container_gateway" {
  description = "Optional explicit container default gateway fallback. Defaults to cidrhost(container_ip, container_gateway_host_number)."
  type        = string
  default     = ""
}

variable "container_gateway_host_number" {
  description = "Host number used to derive the default gateway from container_ip when container_gateway is empty."
  type        = number
  default     = 1
}

variable "container_dns_domain" {
  description = "Optional container DNS search domain fallback. Ignored while enable_netbox_remote_state is true."
  type        = string
  default     = ""
}

variable "container_dns_servers" {
  description = "Optional container DNS servers fallback. Ignored while enable_netbox_remote_state is true."
  type        = list(string)
  default     = []
}

variable "container_cores" {
  description = "CPU cores assigned to the dns03 LXC."
  type        = number
  default     = 1
}

variable "container_memory" {
  description = "Memory assigned to the dns03 LXC in MiB."
  type        = number
  default     = 512
}

variable "container_swap" {
  description = "Swap assigned to the dns03 LXC in MiB."
  type        = number
  default     = 512
}

variable "container_disk_size" {
  description = "Root disk size for the dns03 LXC."
  type        = number
  default     = 8
}

variable "ssh_public_key_path" {
  description = "Path to the SSH public key injected into the dns03 LXC."
  type        = string
}

variable "enable_netbox_remote_state" {
  description = "Read DNS and host topology data from the terraform/netbox local state."
  type        = bool
  default     = true
}

variable "netbox_state_path" {
  description = "Path to the terraform/netbox state file."
  type        = string
  default     = "../../../netbox/terraform.tfstate"
}

variable "dns_ips" {
  description = "Fallback DNS node/VIP IPs. Normally sourced from terraform/netbox outputs.dns_ips."
  type        = map(string)
  default     = {}
}
