provider "proxmox" {
  endpoint  = var.pm_api_url
  api_token = var.pm_api_token
  insecure  = var.pm_tls_insecure

  ssh {
    agent    = true
    username = var.pm_ssh_username

    node {
      name    = var.cloud_image_node_name
      address = var.pm_ssh_host
      port    = 22
    }
  }
}