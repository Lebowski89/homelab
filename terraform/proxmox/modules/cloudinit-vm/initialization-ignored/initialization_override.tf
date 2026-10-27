# PostgreSQL retains its existing ownership boundary: cloud-init is creation-only.
# This entry point shares all implementation files with the parent module.
# OpenTofu requires a static ignore_changes list, so this cannot be an input toggle.
resource "proxmox_virtual_environment_vm" "this" {
  lifecycle {
    ignore_changes = [initialization]
  }
}
