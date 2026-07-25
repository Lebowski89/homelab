module "n8n_vm" {
  source = "../../modules/ubuntu-cloudinit-vm"

  name                 = var.vm_name
  description          = var.vm_description
  vm_id                = var.vm_id
  node_name            = var.target_node
  clone_template_vm_id = var.clone_template_vm_id

  tags                               = var.vm_tags
  on_boot                            = var.vm_on_boot
  protection                         = var.vm_protection
  started                            = var.vm_started
  qemu_agent_enabled                 = var.qemu_agent_enabled
  cpu_cores                          = var.vm_cpu_cores
  cpu_sockets                        = var.vm_cpu_sockets
  cpu_type                           = var.vm_cpu_type
  memory_mb                          = var.vm_memory_mb
  ballooning_memory_mb               = var.vm_ballooning_memory_mb
  datastore_id                       = var.vm_storage
  disk_size_gb                       = var.vm_disk_size_gb
  ipv4_address                       = local.vm_ipv4_address
  ipv4_gateway                       = local.vm_ipv4_gateway
  dns_servers                        = local.vm_nameservers
  dns_domain                         = local.vm_search_domain
  cloud_init_user                    = var.cloud_init_user
  ssh_public_keys                    = [trimspace(file(pathexpand(var.ssh_public_key_path)))]
  snippet_datastore_id               = var.snippet_storage
  qemu_guest_agent_bootstrap_enabled = var.qemu_guest_agent_bootstrap_enabled
  network_bridge                     = var.vm_network_bridge
  vlan_id                            = var.vm_vlan_id
}
