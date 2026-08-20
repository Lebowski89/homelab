variable "pm_api_url" {
  type        = string
  description = "Proxmox API URL, e.g. https://pve.example.com:8006/"
}

variable "pm_api_token" {
  type        = string
  description = "Terraform Proxmox API token in format user@realm!tokenid=secret"
  sensitive   = true
}

variable "pm_tls_insecure" {
  description = "Disable Proxmox API TLS certificate verification. Keep false when the Proxmox CA is trusted; set true only for an explicitly accepted self-signed or untrusted certificate."
  type        = bool
  default     = false
}

variable "pm_ssh_username" {
  type    = string
  default = "root"
}

variable "pm_ssh_host" {
  type = string
}

variable "pm_ssh_port" {
  description = "SSH port of the target Proxmox node."
  type        = number
  default     = 22
  nullable    = false

  validation {
    condition = (
      var.pm_ssh_port >= 1 &&
      var.pm_ssh_port <= 65535 &&
      floor(var.pm_ssh_port) == var.pm_ssh_port
    )
    error_message = "pm_ssh_port must be an integer between 1 and 65535."
  }
}

variable "target_node" {
  type        = string
  description = "Proxmox node to place the VMs on"
}

variable "clone_template_vmid" {
  type        = number
  description = "Default Proxmox Cloud-Init template VMID for PostgreSQL nodes"
}

variable "vm_bridge" {
  type    = string
  default = "vmbr0"
}

variable "vm_gateway" {
  type = string
}

variable "vm_cidr" {
  type    = number
  default = 24
}

variable "vm_nameserver" {
  description = "Optional space-separated VM DNS nameserver fallback. Ignored while enable_netbox_remote_state is true."
  type        = string
  default     = ""
}

variable "vm_searchdomain" {
  description = "Optional VM DNS search domain fallback. Ignored while enable_netbox_remote_state is true."
  type        = string
  default     = ""
}

variable "ci_user" {
  type    = string
  default = "ubuntu"
}

variable "ssh_public_key_path" {
  type = string
}

variable "default_tags" {
  type    = string
  default = "terraform;postgres;patroni"
}

variable "vm_storage" {
  type        = string
  description = "Proxmox datastore for VM disks and cloud-init disks"
}

variable "postgres_vms" {
  description = "Postgres cluster VM definitions"
  type = map(object({
    vmid                = number
    ip                  = string
    cores               = number
    sockets             = number
    memory              = number
    disk_size_gb        = number
    clone_template_vmid = optional(number)
    vlan_tag            = optional(number)
    onboot              = optional(bool, true)
    ci_user             = optional(string)
  }))
}

variable "enable_netbox_remote_state" {
  description = "Read DNS topology data from the terraform/netbox local state."
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
