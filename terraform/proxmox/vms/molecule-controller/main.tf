module "controller_vm" {
  source = "../../modules/cloudinit-vm"

  name                 = local.vm_name
  description          = var.vm_description
  vm_id                = var.vm_id
  node_name            = local.node_name
  clone_template_vm_id = var.clone_template_vm_id

  bios    = "ovmf"
  machine = "q35"

  tags         = ["terraform", "rocky", "molecule-controller"]
  on_boot      = var.vm_on_boot
  protection   = var.vm_protection
  started      = var.vm_started
  cpu_cores    = var.vm_cpu_cores
  memory_mb    = var.vm_memory_mb
  datastore_id = var.vm_storage
  disk_size_gb = var.vm_disk_size_gb

  ipv4_address   = local.vm_ipv4_address
  ipv4_gateway   = local.vm_ipv4_gateway
  dns_servers    = local.vm_nameservers
  dns_domain     = local.vm_search_domain
  network_bridge = var.vm_network_bridge
  vlan_id        = var.vm_vlan_id

  cloud_init_user                    = var.cloud_init_user
  ssh_public_keys                    = [trimspace(file(pathexpand(var.ssh_public_key_path)))]
  snippet_datastore_id               = var.snippet_storage
  qemu_agent_enabled                 = true
  qemu_guest_agent_bootstrap_enabled = false
  vendor_data_file_id                = proxmox_virtual_environment_file.bootstrap.id
  cloud_init_upgrade                 = false
}

# A pre-generated dedicated host identity allows strict first-boot SSH trust.
# This root's local state and this snippet contain the private host key.
resource "proxmox_virtual_environment_file" "bootstrap" {
  content_type = "snippets"
  datastore_id = var.snippet_storage
  node_name    = local.node_name
  overwrite    = false
  file_mode    = "0600"
  source_raw {
    file_name = "${local.vm_name}-bootstrap.yaml"
    data = format("#cloud-config\n%s", yamlencode({
      package_update  = true
      package_upgrade = false
      packages        = ["qemu-guest-agent"]
      ssh_keys = {
        ed25519_private = sensitive(file(pathexpand(var.vm_host_key_private_path)))
        ed25519_public  = trimspace(file(pathexpand("${var.vm_host_key_private_path}.pub")))
      }
      runcmd = [["systemctl", "enable", "--now", "qemu-guest-agent"]]
    }))
  }
}
