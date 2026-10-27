module "postgres_vm" {
  # The creation-only cloud-init entry point shares the existing VM implementation.
  source = "../../modules/cloudinit-vm/initialization-ignored"

  name        = var.postgres_vm.name
  description = "Postgres HA node ${var.postgres_vm.name} managed by Terraform"
  vm_id       = var.postgres_vm.vmid
  node_name   = var.target_node
  clone_template_vm_id = coalesce(
    var.postgres_vm.clone_template_vmid,
    var.clone_template_vmid,
  )
  clone_retries = 3

  tags       = split(";", var.default_tags)
  on_boot    = var.postgres_vm.onboot
  protection = false
  started    = true
  bios       = null
  machine    = null

  cpu_type             = "host"
  cpu_cores            = var.postgres_vm.cores
  cpu_sockets          = var.postgres_vm.sockets
  memory_mb            = var.postgres_vm.memory
  ballooning_memory_mb = 0
  datastore_id         = var.vm_storage
  disk_size_gb         = var.postgres_vm.disk_size_gb
  network_bridge       = var.vm_bridge
  vlan_id              = var.postgres_vm.vlan_tag

  ipv4_address    = "${var.postgres_vm.ip}/${var.vm_cidr}"
  ipv4_gateway    = var.vm_gateway
  dns_servers     = local.vm_nameservers
  dns_domain      = local.vm_searchdomain
  cloud_init_user = coalesce(var.postgres_vm.ci_user, var.ci_user, "ubuntu")
  ssh_public_keys = [trimspace(file(pathexpand(var.ssh_public_key_path)))]

  qemu_agent_enabled                 = true
  qemu_guest_agent_bootstrap_enabled = false
  vendor_data_file_id                = local.guest_agent_vendor_data_file_id
}
