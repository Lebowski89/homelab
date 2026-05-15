data "terraform_remote_state" "netbox" {
  count = var.enable_netbox_remote_state ? 1 : 0

  backend = "local"

  config = {
    path = var.netbox_state_path
  }
}
