variable "name" {
  description = "Proxmox VM name."
  type        = string

  validation {
    condition     = trimspace(var.name) != ""
    error_message = "name must not be empty."
  }
}

variable "description" {
  description = "Proxmox VM description."
  type        = string
  default     = "Ubuntu cloud-init VM managed by OpenTofu"
}

variable "vm_id" {
  description = "Proxmox VMID."
  type        = number

  validation {
    condition     = var.vm_id >= 100
    error_message = "vm_id must be at least 100."
  }
}

variable "node_name" {
  description = "Proxmox node on which to create the VM."
  type        = string
}

variable "clone_template_vm_id" {
  description = "VMID of the cloud-init template to clone."
  type        = number
}

variable "clone_retries" {
  description = "Number of clone retries requested from the Proxmox provider."
  type        = number
  default     = 3
}

variable "tags" {
  description = "Tags applied to the Proxmox VM."
  type        = list(string)
  default     = ["terraform", "ubuntu", "cloud-init"]
}

variable "on_boot" {
  description = "Start the VM automatically when the Proxmox node boots."
  type        = bool
  default     = true
}

variable "protection" {
  description = "Enable Proxmox VM protection."
  type        = bool
  default     = false
}

variable "started" {
  description = "Ensure the VM is started after creation."
  type        = bool
  default     = true
}

variable "snippet_datastore_id" {
  description = "Proxmox datastore used for generated cloud-init snippets."
  type        = string
  default     = "local"
}

variable "qemu_guest_agent_bootstrap_enabled" {
  description = "Install and start qemu-guest-agent through non-secret cloud-init vendor data."
  type        = bool
  default     = true
}

variable "qemu_agent_enabled" {
  description = "Enable the QEMU guest agent integration."
  type        = bool
  default     = true
}

variable "qemu_guest_agent_snippet_file_name" {
  description = "Optional filename override for the generated QEMU guest-agent cloud-init snippet."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition = (
      var.qemu_guest_agent_snippet_file_name == null ||
      trimspace(var.qemu_guest_agent_snippet_file_name) != ""
    )
    error_message = "qemu_guest_agent_snippet_file_name must be null or a non-empty filename."
  }
}

variable "cpu_cores" {
  description = "Number of virtual CPU cores."
  type        = number
  default     = 2

  validation {
    condition     = var.cpu_cores >= 1
    error_message = "cpu_cores must be at least 1."
  }
}

variable "cpu_sockets" {
  description = "Number of virtual CPU sockets."
  type        = number
  default     = 1

  validation {
    condition     = var.cpu_sockets >= 1
    error_message = "cpu_sockets must be at least 1."
  }
}

variable "cpu_type" {
  description = "Proxmox CPU type."
  type        = string
  default     = "host"
}

variable "memory_mb" {
  description = "Dedicated VM memory in MiB."
  type        = number
  default     = 2048

  validation {
    condition     = var.memory_mb >= 512
    error_message = "memory_mb must be at least 512 MiB."
  }
}

variable "ballooning_memory_mb" {
  description = "Minimum ballooned memory in MiB; use 0 to disable ballooning."
  type        = number
  default     = 0

  validation {
    condition     = var.ballooning_memory_mb >= 0
    error_message = "ballooning_memory_mb must not be negative."
  }
}

variable "datastore_id" {
  description = "Proxmox datastore used for the VM disk and cloud-init disk."
  type        = string
}

variable "disk_size_gb" {
  description = "VM system disk size in GiB."
  type        = number
  default     = 24

  validation {
    condition     = var.disk_size_gb >= 8
    error_message = "disk_size_gb must be at least 8 GiB."
  }
}

variable "vendor_data_file_id" {
  description = "Optional Proxmox snippets file ID used as cloud-init vendor data."
  type        = string
  default     = null
  nullable    = true
}

variable "ipv4_address" {
  description = "Static IPv4 address in CIDR notation."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{1,3}(\\.[0-9]{1,3}){3}/[0-9]{1,2}$", var.ipv4_address)) && can(cidrhost(var.ipv4_address, 0))
    error_message = "ipv4_address must be valid CIDR notation, for example 192.168.80.50/24."
  }
}

variable "ipv4_gateway" {
  description = "IPv4 default gateway."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{1,3}(\\.[0-9]{1,3}){3}$", var.ipv4_gateway)) && can(cidrhost("${var.ipv4_gateway}/32", 0))
    error_message = "ipv4_gateway must be an IPv4 address."
  }
}

variable "dns_servers" {
  description = "DNS servers supplied through cloud-init."
  type        = list(string)
}

variable "dns_domain" {
  description = "DNS search domain supplied through cloud-init."
  type        = string
  default     = ""
}

variable "cloud_init_user" {
  description = "Cloud-init administrative username."
  type        = string
  default     = "ubuntu"
}

variable "ssh_public_keys" {
  description = "SSH public keys installed for the cloud-init user."
  type        = list(string)
}

variable "network_bridge" {
  description = "Proxmox bridge connected to the VM network interface."
  type        = string
  default     = "vmbr0"
}

variable "vlan_id" {
  description = "Optional VLAN tag for the VM network interface."
  type        = number
  default     = null
  nullable    = true

  validation {
    condition     = var.vlan_id == null || (var.vlan_id >= 1 && var.vlan_id <= 4094)
    error_message = "vlan_id must be null or between 1 and 4094."
  }
}
