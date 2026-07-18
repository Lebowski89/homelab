locals {
  netbox_dns_ips       = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.dns_ips, {}) : {}
  netbox_internal_zone = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.internal_zone, "") : ""

  dns_ips = merge(
    var.dns_ips,
    local.netbox_dns_ips,
  )

  resolved_dns_servers = distinct(compact([
    lookup(local.dns_ips, "dns_vip_a", ""),
    lookup(local.dns_ips, "dns_vip_b", ""),
  ]))

  dns_servers = length(local.resolved_dns_servers) > 0 ? local.resolved_dns_servers : [
    for server in var.dns_servers : trimspace(server)
    if trimspace(server) != ""
  ]

  dns_domain = trim(
    trimspace(local.netbox_internal_zone) != "" ? local.netbox_internal_zone : var.dns_domain,
    "."
  )

  local_domain = trim(
    trimspace(local.netbox_internal_zone) != "" ? local.netbox_internal_zone : var.local_domain,
    "."
  )

  node_name = trimspace(var.target_node)

  node_hostnames = compact([
    local.local_domain != "" ? "${local.node_name}.${local.local_domain}" : "",
    local.node_name,
  ])
}

resource "proxmox_virtual_environment_hosts" "hosts" {
  node_name = local.node_name

  entry {
    address   = "127.0.0.1"
    hostnames = ["localhost.localdomain", "localhost"]
  }

  entry {
    address   = var.node_management_ip
    hostnames = local.node_hostnames
  }

  entry {
    address   = "::1"
    hostnames = ["ip6-localhost", "ip6-loopback"]
  }

  entry {
    address   = "fe00::0"
    hostnames = ["ip6-localnet"]
  }

  entry {
    address   = "ff00::0"
    hostnames = ["ip6-mcastprefix"]
  }

  entry {
    address   = "ff02::1"
    hostnames = ["ip6-allnodes"]
  }

  entry {
    address   = "ff02::2"
    hostnames = ["ip6-allrouters"]
  }

  entry {
    address   = "ff02::3"
    hostnames = ["ip6-allhosts"]
  }
}

resource "proxmox_network_linux_bridge" "vmbr0" {
  node_name = var.target_node
  name      = var.network_vmbr0_name
  address   = var.network_vmbr0_address
  gateway   = var.network_vmbr0_gateway
  ports     = var.network_vmbr0_ports
  autostart = var.network_vmbr0_autostart
}

resource "proxmox_network_linux_bridge" "vmbr1" {
  node_name = var.target_node
  name      = var.network_vmbr1_name
  ports     = var.network_vmbr1_ports
  autostart = var.network_vmbr1_autostart
}

resource "proxmox_virtual_environment_dns" "dns" {
  node_name = var.target_node
  domain    = local.dns_domain
  servers   = local.dns_servers
}

resource "proxmox_virtual_environment_time" "timezone" {
  node_name = var.target_node
  time_zone = var.timezone
}
