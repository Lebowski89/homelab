variable "pm_api_url" {
  type        = string
  description = "Proxmox API URL, e.g. https://pve.example.com:8006/api2/json"
}

variable "pm_api_token_id" {
  type        = string
  description = "Terraform Proxmox API token ID"
  sensitive   = true
}

variable "pm_api_token_secret" {
  type        = string
  description = "Terraform Proxmox API token secret"
  sensitive   = true
}

variable "pm_tls_insecure" {
  type        = bool
  default     = false
  description = "Set true if using self-signed Proxmox certs"
}

variable "target_node" {
  type        = string
  description = "Proxmox node to place the VMs on"
}

variable "clone_template" {
  type        = string
  description = "Name of the Ubuntu 24.04 Cloud-Init VM template in Proxmox"
}

variable "vm_bridge" {
  type    = string
  default = "vmbr0"
}

variable "vm_gateway" {
  type    = string
  default = "192.168.80.1"
}

variable "vm_cidr" {
  type    = number
  default = 24
}

variable "vm_nameserver" {
  type    = string
  default = "192.168.80.48"
}

variable "vm_searchdomain" {
  type    = string
  default = ""
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
  description = "Proxmox storage name for VM disks and cloud-init disks"
}

variable "postgres_vms" {
  description = "Postgres cluster VM definitions"
  type = map(object({
    vmid         = number
    ip           = string
    cores        = number
    sockets      = number
    memory       = number
    disk_size_gb = number
    vlan_tag     = optional(number)
    onboot       = optional(bool, true)
    ci_user      = optional(string)
  }))
}