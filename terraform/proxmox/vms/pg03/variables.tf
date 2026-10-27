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
  description = "Proxmox node on which the VM and its local storage reside"
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

  validation {
    condition = (
      (var.enable_netbox_remote_state || trimspace(var.vm_nameserver) == "")
      ? length(local.dns_vip_nameservers) == 2
      : trimspace(var.vm_nameserver) != ""
    )
    error_message = "Unable to determine valid VM DNS servers. Ensure NetBox outputs.dns_ips contains distinct dns_vip_a and dns_vip_b values, provide them through dns_ips, or set vm_nameserver when NetBox remote state is disabled."
  }
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

variable "postgres_vm" {
  description = "One existing PostgreSQL VM. Root directory names do not rename the guest."
  type = object({
    name                = string
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
  })
}

variable "guest_agent_vendor_data_file_id" {
  description = "Optional explicit existing vendor-data ID for bootstrap use. Null reads the Ubuntu template owner's output; this root never owns the shared file."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.guest_agent_vendor_data_file_id == null ? true : trimspace(var.guest_agent_vendor_data_file_id) != ""
    error_message = "guest_agent_vendor_data_file_id must be null or a non-empty existing file ID."
  }
}

variable "ubuntu_template_state_path" {
  description = "Authoritative local Ubuntu 26.04 template state exporting qemu_guest_agent_vendor_data_file_id; used unless an explicit vendor-data ID is supplied."
  type        = string
  default     = "../../templates/ubuntu-2604/terraform.tfstate"

  validation {
    condition     = trimspace(var.ubuntu_template_state_path) != ""
    error_message = "ubuntu_template_state_path must not be empty."
  }
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
