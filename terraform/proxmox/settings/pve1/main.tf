locals {
  netbox_dns_ips       = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.dns_ips, {}) : {}
  netbox_internal_zone = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.internal_zone, "") : ""

  # NetBox takes precedence while var.dns_ips can supply missing keys or
  # support operation without NetBox remote state.
  dns_ips = merge(
    var.dns_ips,
    local.netbox_dns_ips,
  )

  dns_vip_servers = distinct(compact([
    trimspace(lookup(local.dns_ips, "dns_vip_a", "")),
    trimspace(lookup(local.dns_ips, "dns_vip_b", "")),
  ]))

  configured_dns_servers = distinct([
    for server in var.dns_servers : trimspace(server)
    if trimspace(server) != ""
  ])

  # Preserve the existing behaviour:
  # - use NetBox DNS VIPs while remote state is enabled;
  # - use explicitly configured servers when remote state is disabled;
  # - fall back to var.dns_ips VIPs when explicit servers are absent.
  use_dns_vips = var.enable_netbox_remote_state || length(local.configured_dns_servers) == 0

  dns_servers = local.use_dns_vips ? local.dns_vip_servers : local.configured_dns_servers

  dns_domain_source = trimspace(local.netbox_internal_zone) != "" ? local.netbox_internal_zone : var.dns_domain

  local_domain_source = trimspace(local.netbox_internal_zone) != "" ? local.netbox_internal_zone : var.local_domain

  dns_domain   = trim(trimspace(local.dns_domain_source), ".")
  local_domain = trim(trimspace(local.local_domain_source), ".")

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
  node_name = local.node_name
  domain    = local.dns_domain
  servers   = local.dns_servers

  lifecycle {
    precondition {
      condition = (
        local.use_dns_vips
        ? length(local.dns_vip_servers) == 2
        : length(local.configured_dns_servers) > 0
      )

      error_message = "Unable to determine valid DNS servers. Ensure NetBox outputs.dns_ips contains distinct dns_vip_a and dns_vip_b values, or provide dns_servers explicitly when NetBox remote state is disabled."
    }
  }
}

resource "proxmox_virtual_environment_time" "timezone" {
  node_name = var.target_node
  time_zone = var.timezone
}
