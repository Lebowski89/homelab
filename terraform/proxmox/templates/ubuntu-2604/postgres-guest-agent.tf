# Shared cloud-init vendor data used by the PostgreSQL VMs.
# Managed here alongside their source template; referenced by the per-VM roots.
resource "proxmox_virtual_environment_file" "postgres_qemu_guest_agent_cloud_init" {
  content_type = "snippets"
  datastore_id = var.snippet_storage
  node_name    = var.target_node

  source_raw {
    file_name = "postgres-qemu-guest-agent.yaml"

    data = <<-EOF
      #cloud-config
      package_update: true
      package_upgrade: false

      packages:
        - qemu-guest-agent

      runcmd:
        - systemctl enable --now qemu-guest-agent
    EOF
  }
}
