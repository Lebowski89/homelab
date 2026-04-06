pm_api_url      = "https://192.168.80.80:8006/"
pm_tls_insecure = true

target_node   = "pve1"
template_vmid = 9002
template_name = "ubuntu-2404-lts-cloudinit-template"

vm_storage      = "local-zfs"
snippet_storage = "local"

cloud_image_datastore = "local"
cloud_image_node_name = "pve1"

template_cores   = 2
template_memory  = 2048
template_bridge  = "vmbr0"
template_ci_user = "ubuntu"

ssh_public_key_path = "~/.ssh/proxmox_terraform.pub"