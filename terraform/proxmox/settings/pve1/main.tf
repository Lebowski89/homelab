resource "proxmox_virtual_environment_hosts" "hosts" {
  node_name = var.target_node

  entry {
    address   = "127.0.0.1"
    hostnames = ["localhost.localdomain", "localhost"]
  }

  entry {
    address   = var.node_management_ip
    hostnames = ["${var.target_node}.${var.local_domain}", var.target_node]
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
  domain    = var.dns_domain
  servers   = var.dns_servers
}

resource "proxmox_virtual_environment_time" "timezone" {
  node_name = var.target_node
  time_zone = var.timezone
}