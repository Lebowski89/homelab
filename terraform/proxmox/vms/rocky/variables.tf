variable "pm_api_url" {
  description = "Proxmox API URL, for example https://pve.example.com:8006/."
  type        = string
}

variable "pm_api_token" {
  description = "Proxmox API token supplied through private inputs."
  type        = string
  sensitive   = true
}

variable "pm_tls_insecure" {
  description = "Disable Proxmox API TLS certificate verification only for an explicitly accepted untrusted certificate."
  type        = bool
  default     = false
}

variable "pm_ssh_username" {
  description = "Proxmox SSH user for snippet operations; authentication uses the workstation SSH agent."
  type        = string
}

variable "pm_ssh_host" {
  description = "SSH address of the selected Proxmox node."
  type        = string
}

variable "pm_ssh_port" {
  type    = number
  default = 22

  validation {
    condition     = var.pm_ssh_port >= 1 && var.pm_ssh_port <= 65535 && floor(var.pm_ssh_port) == var.pm_ssh_port
    error_message = "pm_ssh_port must be an integer from 1 to 65535."
  }
}

variable "target_node" {
  description = "Proxmox node hosting both the Rocky template and its new clone."
  type        = string
}

variable "clone_template_vm_id" {
  description = "Existing Rocky Linux cloud-init template VMID."
  type        = number
  default     = 9004
}

variable "vm_name" {
  description = "Required distinct staging name; also the NetBox host key for address lookup. Production mgt remains separate."
  type        = string
  nullable    = false

  validation {
    condition     = trimspace(var.vm_name) != "" && lower(trimspace(var.vm_name)) != "mgt"
    error_message = "vm_name must be a non-empty staging name distinct from production mgt; cutover is a separate task."
  }
}

variable "vm_id" {
  description = "Required explicitly selected, verified free VMID for the staged replacement; never VM104 or the source template."
  type        = number
  nullable    = false

  validation {
    condition = (
      var.vm_id >= 100 && var.vm_id <= 999999999 && floor(var.vm_id) == var.vm_id &&
      var.vm_id != 104 && var.vm_id != var.clone_template_vm_id
    )
    error_message = "vm_id must be a valid integer VMID distinct from VM104 and clone_template_vm_id."
  }
}

variable "vm_description" {
  type    = string
  default = "Staged Rocky Linux management VM managed by OpenTofu"
}

variable "vm_storage" {
  description = "Storage for the new clone's system disk, cloud-init drive and EFI variables disk."
  type        = string
}

variable "snippet_storage" {
  description = "Snippet-capable storage on target_node for the module's guest-agent vendor data."
  type        = string
  default     = "local"
}

variable "vm_cpu_cores" {
  type    = number
  default = 4
}

variable "vm_memory_mb" {
  type    = number
  default = 4096
}

variable "vm_disk_size_gb" {
  description = "New system disk size in GiB, at least the Rocky template's 10 GiB virtual size."
  type        = number
  default     = 64

  validation {
    condition     = var.vm_disk_size_gb >= 10 && floor(var.vm_disk_size_gb) == var.vm_disk_size_gb
    error_message = "vm_disk_size_gb must be an integer of at least 10 GiB; shrinking the template disk is unsupported."
  }
}

variable "vm_started" {
  description = "Start the staged VM after a separately authorised apply."
  type        = bool
  default     = true
}

variable "vm_on_boot" {
  description = "Automatically boot the staged VM with its Proxmox node."
  type        = bool
  default     = false
}

variable "vm_protection" {
  type    = bool
  default = false
}

variable "vm_network_bridge" {
  type    = string
  default = "vmbr1"
}

variable "vm_vlan_id" {
  type    = number
  default = null
}

variable "vm_ipv4_address" {
  description = "Explicit staging IPv4 CIDR override; otherwise use NetBox host_primary_cidrs[vm_name]."
  type        = string
  default     = ""
}

variable "vm_ipv4_gateway" {
  description = "Explicit gateway override; otherwise use the NetBox primary IPv4 of vm_gateway_host."
  type        = string
  default     = ""
}

variable "vm_gateway_host" {
  type    = string
  default = "router"
}

variable "vm_nameservers" {
  description = "Explicit DNS server override; otherwise use NetBox DNS VIPs."
  type        = list(string)
  default     = []
}

variable "vm_search_domain" {
  description = "Explicit search-domain override; otherwise use NetBox internal_zone."
  type        = string
  default     = ""
}

variable "cloud_init_user" {
  type    = string
  default = "rocky"
}

variable "ssh_public_key_path" {
  description = "Workstation path to the public key installed for cloud_init_user."
  type        = string
}

variable "enable_netbox_remote_state" {
  description = "Read the existing NetBox state outputs; this root never changes NetBox."
  type        = bool
  default     = true
}

variable "netbox_state_path" {
  description = "Authoritative private NetBox state snapshot supplying inventory-derived network settings."
  type        = string
  default     = "../../../netbox/terraform.tfstate"
}
