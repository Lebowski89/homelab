data "terraform_remote_state" "netbox" {
  count = var.enable_netbox_remote_state ? 1 : 0

  backend = "local"

  config = {
    path = pathexpand(var.netbox_state_path)
  }
}

data "terraform_remote_state" "ubuntu_template" {
  count = var.guest_agent_vendor_data_file_id == null ? 1 : 0

  backend = "local"

  config = {
    path = pathexpand(var.ubuntu_template_state_path)
  }
}
