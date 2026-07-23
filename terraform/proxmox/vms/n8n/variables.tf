variable "pm_api_url" {
  description = "Proxmox API URL, for example https://pve.example.com:8006/."
  type        = string
}

variable "pm_api_token" {
  description = "Proxmox API token in user@realm!tokenid=secret format."
  type        = string
  sensitive   = true
}

variable "pm_tls_insecure" {
  description = "Disable Proxmox API TLS certificate verification. Keep false when the Proxmox CA is trusted; set true only for an explicitly accepted self-signed or untrusted certificate."
  type        = bool
  default     = false
}

variable "pm_ssh_username" {
  description = "SSH username used by the Proxmox provider for snippet operations."
  type        = string
  default     = "root"
}

variable "pm_ssh_host" {
  description = "SSH address of the target Proxmox node."
  type        = string
}

variable "pm_ssh_port" {
  description = "SSH port of the target Proxmox node."
  type        = number
  default     = 22
}

variable "target_node" {
  description = "Proxmox node on which to create the n8n VM."
  type        = string
}

variable "clone_template_vm_id" {
  description = "VMID of the Ubuntu 26.04 LTS (Resolute) cloud-init template."
  type        = number
}

variable "vm_storage" {
  description = "Proxmox datastore for VM and cloud-init disks."
  type        = string
}

variable "snippet_storage" {
  description = "Proxmox snippets datastore for optional cloud-init vendor data."
  type        = string
  default     = "local"
}

variable "vm_id" {
  description = "VMID assigned to the n8n VM."
  type        = number
}

variable "vm_name" {
  description = "Proxmox VM name."
  type        = string
  default     = "n8n"
}

variable "vm_description" {
  description = "Proxmox VM description."
  type        = string
  default     = "Isolated n8n automation VM managed by OpenTofu"
}

variable "vm_tags" {
  description = "Tags applied to the n8n VM in Proxmox."
  type        = list(string)
  default     = ["terraform", "ubuntu", "automation", "n8n"]
}

variable "vm_on_boot" {
  description = "Start the n8n VM when the Proxmox node boots."
  type        = bool
  default     = true
}

variable "vm_protection" {
  description = "Enable Proxmox VM protection."
  type        = bool
  default     = false
}

variable "vm_started" {
  description = "Ensure the n8n VM is started after creation."
  type        = bool
  default     = true
}

variable "qemu_agent_enabled" {
  description = "Enable QEMU guest-agent integration."
  type        = bool
  default     = true
}

variable "qemu_guest_agent_bootstrap_enabled" {
  description = "Install qemu-guest-agent during first boot so Proxmox can bootstrap the guest."
  type        = bool
  default     = true
}

variable "vm_cpu_cores" {
  description = "Number of n8n VM virtual CPU cores."
  type        = number
  default     = 2
}

variable "vm_cpu_sockets" {
  description = "Number of n8n VM virtual CPU sockets."
  type        = number
  default     = 1
}

variable "vm_cpu_type" {
  description = "Proxmox CPU type exposed to the n8n VM."
  type        = string
  default     = "host"
}

variable "vm_memory_mb" {
  description = "Dedicated memory for the n8n VM in MiB."
  type        = number
  default     = 2048
}

variable "vm_ballooning_memory_mb" {
  description = "Minimum ballooned memory in MiB; 0 disables ballooning."
  type        = number
  default     = 0
}

variable "vm_disk_size_gb" {
  description = "n8n VM system disk size in GiB."
  type        = number
  default     = 24
}

variable "vm_ipv4_address" {
  description = "Static n8n VM IPv4 address in CIDR notation."
  type        = string
}

variable "vm_ipv4_gateway" {
  description = "IPv4 default gateway for the n8n VM."
  type        = string
}

variable "vm_network_bridge" {
  description = "Proxmox bridge connected to the n8n VM."
  type        = string
  default     = "vmbr0"
}

variable "vm_vlan_id" {
  description = "Optional VLAN tag for the n8n VM."
  type        = number
  default     = null
  nullable    = true
}

variable "vm_nameservers" {
  description = "Fallback DNS servers used when NetBox remote state is disabled."
  type        = list(string)
  default     = []
}

variable "vm_search_domain" {
  description = "Fallback DNS search domain used when NetBox does not supply one."
  type        = string
  default     = ""
}

variable "cloud_init_user" {
  description = "Cloud-init administrative username."
  type        = string
  default     = "ubuntu"
}

variable "ssh_public_key_path" {
  description = "Local path to the SSH public key installed by cloud-init."
  type        = string
}

variable "enable_netbox_remote_state" {
  description = "Read DNS topology from the terraform/netbox local state."
  type        = bool
  default     = true
}

variable "netbox_state_path" {
  description = "Path to the terraform/netbox state file."
  type        = string
  default     = "../../../netbox/terraform.tfstate"
}

variable "dns_ips" {
  description = "Fallback DNS VIP map, normally sourced from NetBox outputs."
  type        = map(string)
  default     = {}
}
