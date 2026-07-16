provider "proxmox" {
  endpoint  = local.pm_api_url
  api_token = var.pm_api_token
  insecure  = var.pm_tls_insecure

  ssh {
    agent    = true
    username = var.pm_ssh_username

    node {
      name    = var.target_node
      address = local.pm_ssh_host
      port    = var.pm_ssh_port
    }
  }
}
