locals {
  internal_zone = trimspace(var.internal_zone)

  sites = {
    homelab = {
      name   = "Homelab"
      slug   = "homelab"
      status = "active"
    }
  }

  manufacturers = {
    homelab = {
      name = "Homelab"
      slug = "homelab"
    }

    mikrotik = {
      name = "MikroTik"
      slug = "mikrotik"
    }

    tp_link = {
      name = "TP-Link"
      slug = "tp-link"
    }
  }

  device_roles = {
    server = {
      name      = "Server"
      slug      = "server"
      color_hex = "9e9e9e"
    }

    hypervisor = {
      name      = "Hypervisor"
      slug      = "hypervisor"
      color_hex = "ff9800"
    }

    storage = {
      name      = "Storage"
      slug      = "storage"
      color_hex = "4caf50"
    }

    switch = {
      name      = "Switch"
      slug      = "switch"
      color_hex = "2196f3"
    }

    gateway = {
      name      = "Gateway"
      slug      = "gateway"
      color_hex = "9c27b0"
    }
  }

  device_types = {
    generic_host = {
      model            = "Generic Homelab Host"
      slug             = "generic-homelab-host"
      manufacturer_key = "homelab"
    }

    generic_vm = {
      model            = "Generic Virtual Machine"
      slug             = "generic-virtual-machine"
      manufacturer_key = "homelab"
    }

    generic_lxc = {
      model            = "Generic LXC Container"
      slug             = "generic-lxc-container"
      manufacturer_key = "homelab"
    }

    proxmox_host = {
      model            = "Proxmox Host"
      slug             = "proxmox-host"
      manufacturer_key = "homelab"
    }

    unraid_host = {
      model            = "Unraid Host"
      slug             = "unraid-host"
      manufacturer_key = "homelab"
    }

    generic_gateway_device = {
      model            = "Generic Gateway Device"
      slug             = "generic-gateway-device"
      manufacturer_key = "homelab"
    }

    tp_link_archer_ax72 = {
      model            = "Archer AX72"
      slug             = "tp-link-archer-ax72"
      manufacturer_key = "tp_link"
      part_number      = "Archer AX72"
      u_height         = 0
      is_full_depth    = false
      description      = "TP-Link Archer AX72 AX5400 dual-band Wi-Fi 6 router."
    }

    generic_switch_device = {
      model            = "Generic Switch Device"
      slug             = "generic-switch-device"
      manufacturer_key = "homelab"
    }

    mikrotik_crs305 = {
      model            = "CRS305-1G-4S+IN"
      slug             = "mikrotik-crs305-1g-4s-plus-in"
      manufacturer_key = "mikrotik"
      part_number      = "CRS305-1G-4S+"
      is_full_depth    = false
      u_height         = 1
    }
  }

  device_type_interfaces = {
    mikrotik_crs305 = [
      {
        name  = "sfp-sfpplus1"
        label = "SFP+ 1"
        type  = "10gbase-x-sfpp"
      },
      {
        name  = "sfp-sfpplus2"
        label = "SFP+ 2"
        type  = "10gbase-x-sfpp"
      },
      {
        name  = "sfp-sfpplus3"
        label = "SFP+ 3"
        type  = "10gbase-x-sfpp"
      },
      {
        name  = "sfp-sfpplus4"
        label = "SFP+ 4"
        type  = "10gbase-x-sfpp"
      },
      {
        name  = "ether1"
        label = "ETH/BOOT"
        type  = "1000base-t"
      }
    ]

    tp_link_archer_ax72 = [
      {
        name  = "wan"
        label = "WAN"
        type  = "1000base-t"
      },
      {
        name  = "lan1"
        label = "LAN 1"
        type  = "1000base-t"
      },
      {
        name  = "lan2"
        label = "LAN 2"
        type  = "1000base-t"
      },
      {
        name  = "lan3"
        label = "LAN 3"
        type  = "1000base-t"
      },
      {
        name  = "lan4"
        label = "LAN 4"
        type  = "1000base-t"
      }
    ]
  }

  prefixes = {
    lan = {
      prefix      = "192.168.80.0/24"
      description = "Primary homelab LAN"
      status      = "active"
    }
  }

  netbox_tags = {
    skynet = {
      name        = "skynet"
      slug        = "skynet"
      color_hex   = "607d8b"
      description = "Main Ansible inventory group."
    }

    ansible_manager = {
      name        = "ansible-manager"
      slug        = "ansible_manager"
      color_hex   = "673ab7"
      description = "Hosts that run Ansible locally."
    }

    docker = {
      name        = "docker"
      slug        = "docker"
      color_hex   = "2196f3"
      description = "Docker-capable hosts."
    }

    docker_install = {
      name        = "docker-install"
      slug        = "docker_install"
      color_hex   = "03a9f4"
      description = "Hosts where the Docker role installs Docker."
    }

    swarm = {
      name        = "swarm"
      slug        = "swarm"
      color_hex   = "009688"
      description = "Docker Swarm nodes."
    }

    swarm_manager = {
      name        = "swarm-manager"
      slug        = "swarm_manager"
      color_hex   = "4caf50"
      description = "Docker Swarm managers."
    }

    swarm_worker = {
      name        = "swarm-worker"
      slug        = "swarm_worker"
      color_hex   = "8bc34a"
      description = "Docker Swarm workers."
    }

    haproxy = {
      name        = "haproxy"
      slug        = "haproxy"
      color_hex   = "ff9800"
      description = "Hosts participating in HAProxy."
    }

    postgres = {
      name        = "postgres"
      slug        = "postgres"
      color_hex   = "3f51b5"
      description = "Postgres / Patroni nodes."
    }

    opentofu = {
      name        = "opentofu"
      slug        = "opentofu"
      color_hex   = "ff5722"
      description = "Hosts where the OpenTofu role should be included."
    }

    opentofu_install = {
      name        = "opentofu-install"
      slug        = "opentofu_install"
      color_hex   = "ff7043"
      description = "Hosts where OpenTofu should be installed."
    }

    opentofu_managed = {
      name        = "opentofu-managed"
      slug        = "opentofu_managed"
      color_hex   = "795548"
      description = "Hosts managed or provisioned by OpenTofu."
    }

    opentofu_pve_user = {
      name        = "opentofu-pve-user"
      slug        = "opentofu_pve_user"
      color_hex   = "9c27b0"
      description = "Proxmox hosts where the Terraform/OpenTofu API user is managed."
    }

    lan_gateway = {
      name        = "lan_gateway"
      slug        = "lan_gateway"
      description = "Default LAN gateway device."
      color       = "4caf50"
    }

    dns = {
      name        = "dns"
      slug        = "dns"
      description = "Hosts providing DNS services."
      color       = "2196f3"
    }

    technitium = {
      name        = "technitium"
      slug        = "technitium"
      description = "Hosts providing Technitium DNS services."
      color_hex   = "00bcd4"
    }

    technitium_native = {
      name        = "technitium-native"
      slug        = "technitium_native"
      description = "Hosts running Technitium DNS Server natively."
      color_hex   = "00acc1"
    }

    keepalived = {
      name        = "keepalived"
      slug        = "keepalived"
      description = "Hosts participating in keepalived VRRP."
      color_hex   = "4caf50"
    }
  }

  device_custom_fields = {
    ansible_user = {
      name        = "ansible_user"
      label       = "Ansible user"
      type        = "text"
      group_name  = "Ansible"
      description = "SSH username used by Ansible."
      weight      = 100
    }

    ssh_port = {
      name        = "ssh_port"
      label       = "SSH port"
      type        = "text"
      group_name  = "Ansible"
      description = "SSH port used by Ansible."
      weight      = 110
    }

    tailscale_ip = {
      name        = "tailscale_ip"
      label       = "Tailscale IP"
      type        = "text"
      group_name  = "Ansible"
      description = "Tailscale IP used as the preferred Ansible connection address."
      weight      = 120
    }

    docker_host_puid = {
      name        = "docker_host_puid"
      label       = "Docker host PUID"
      type        = "text"
      group_name  = "Docker"
      description = "Default PUID used for Docker services on this host."
      weight      = 200
    }

    docker_host_pgid = {
      name        = "docker_host_pgid"
      label       = "Docker host PGID"
      type        = "text"
      group_name  = "Docker"
      description = "Default PGID used for Docker services on this host."
      weight      = 210
    }

    docker_host_appdata_root = {
      name        = "docker_host_appdata_root"
      label       = "Docker appdata root"
      type        = "text"
      group_name  = "Docker"
      description = "Host path used as the appdata root for Docker services."
      weight      = 220
    }

    docker_host_data_root = {
      name        = "docker_host_data_root"
      label       = "Docker data root"
      type        = "text"
      group_name  = "Docker"
      description = "Host path used as the data root for Docker services."
      weight      = 230
    }

    dns_priority = {
      name        = "dns_priority"
      label       = "DNS priority"
      type        = "text"
      group_name  = "DNS"
      description = "DNS resolver priority. Lower padded values are preferred first, e.g. 010, 020."
      weight      = 300
    }

    keepalived_priority_dns_vip_a = {
      name             = "keepalived_priority_dns_vip_a"
      label            = "Keepalived DNS VIP A priority"
      type             = "text"
      group_name       = "Keepalived"
      description      = "VRRP priority for the first Technitium DNS virtual IP."
      weight           = 310
      validation_regex = "^(?:[1-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-4])$"
    }

    keepalived_priority_dns_vip_b = {
      name             = "keepalived_priority_dns_vip_b"
      label            = "Keepalived DNS VIP B priority"
      type             = "text"
      group_name       = "Keepalived"
      description      = "VRRP priority for the second Technitium DNS virtual IP."
      weight           = 320
      validation_regex = "^(?:[1-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-4])$"
    }
  }

  device_custom_field_defaults = {
    ansible_user             = ""
    ssh_port                 = ""
    tailscale_ip             = ""
    docker_host_puid         = ""
    docker_host_pgid         = ""
    docker_host_appdata_root = ""
    docker_host_data_root    = ""
    dns_priority             = ""
  }

  base_hosts = {
    router = {
      description     = "Primary LAN gateway/router."
      role_key        = "gateway"
      device_type_key = "tp_link_archer_ax72"
      tags = [
        "lan_gateway",
      ]
    }

    mgt = {
      description     = "Docker Swarm manager, automation host, HAProxy endpoint, Technitium DNS primary"
      role_key        = "server"
      device_type_key = "generic_vm"
      tags = [
        "skynet",
        "ansible_manager",
        "docker",
        "docker_install",
        "haproxy",
        "opentofu",
        "opentofu_install",
        "swarm",
        "swarm_manager",
        "dns",
        "technitium",
        "keepalived",
      ]
    }

    unraid = {
      description     = "Unraid storage host, HAProxy endpoint"
      role_key        = "storage"
      device_type_key = "unraid_host"
      tags = [
        "skynet",
        "docker",
        "haproxy",
        "opentofu_managed",
        "swarm",
        "swarm_worker",
      ]
    }

    plex = {
      description = "Plex / Docker Swarm worker, HAProxy endpoint, Technitium DNS secondary"
      role_key    = "server"
      tags = [
        "skynet",
        "docker",
        "docker_install",
        "haproxy",
        "swarm",
        "swarm_worker",
        "dns",
        "technitium",
        "keepalived",
      ]
    }

    pve1 = {
      description     = "Proxmox hypervisor"
      role_key        = "hypervisor"
      device_type_key = "proxmox_host"
      tags = [
        "skynet",
        "opentofu",
        "opentofu_pve_user",
      ]
    }

    dns03 = {
      description     = "Ubuntu LXC on pve1, Technitium DNS tertiary, keepalived backup"
      role_key        = "server"
      device_type_key = "generic_lxc"
      tags = [
        "skynet",
        "opentofu_managed",
        "dns",
        "technitium_native",
        "keepalived",
      ]
    }

    pg95 = {
      description     = "Postgres / Patroni node"
      role_key        = "server"
      device_type_key = "generic_vm"
      tags = [
        "skynet",
        "opentofu",
        "opentofu_managed",
        "postgres",
      ]
    }

    pg96 = {
      description     = "Postgres / Patroni node"
      role_key        = "server"
      device_type_key = "generic_vm"
      tags = [
        "skynet",
        "opentofu",
        "opentofu_managed",
        "postgres",
      ]
    }

    pg97 = {
      description     = "Postgres / Patroni node"
      role_key        = "server"
      device_type_key = "generic_vm"
      tags = [
        "skynet",
        "opentofu",
        "opentofu_managed",
        "postgres",
      ]
    }
  }

  hosts = {
    for host_key, host in local.base_hosts : host_key => merge(
      host,
      {
        mgmt_ip = var.host_private_values[host_key].mgmt_ip
      },
      local.internal_zone != "" ? {
        dns_name = "${host_key}.${local.internal_zone}"
      } : {},
      {
        custom_fields = merge(
          local.device_custom_field_defaults,
          coalesce(try(var.host_private_values[host_key].custom_fields, null), {})
        )
      }
    )
  }

  reserved_ips = {}
}
