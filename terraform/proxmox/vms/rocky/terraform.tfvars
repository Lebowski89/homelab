vm_name = "rocky"
vm_id   = 9100

target_node          = "pve1"
clone_template_vm_id = 9004
vm_storage           = "local-zfs"
snippet_storage      = "local"

vm_cpu_cores    = 4
vm_memory_mb    = 4096
vm_disk_size_gb = 64

vm_started    = true
vm_on_boot    = false
vm_protection = false

vm_network_bridge   = "vmbr1"
cloud_init_user     = "rocky"
ssh_public_key_path = "~/.ssh/proxmox_terraform.pub"

