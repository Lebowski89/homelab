vm_name        = "n8n"
vm_description = "Isolated n8n automation VM managed by OpenTofu"

vm_cpu_cores            = 2
vm_cpu_sockets          = 1
vm_memory_mb            = 2048
vm_ballooning_memory_mb = 0
vm_disk_size_gb         = 24

vm_tags = [
  "terraform",
  "ubuntu",
  "automation",
  "n8n",
]

vm_on_boot    = true
vm_protection = false
vm_started    = true

qemu_guest_agent_bootstrap_enabled = true

enable_netbox_remote_state = true
