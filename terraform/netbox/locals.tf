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
  }

  device_types = {
    generic_host = {
      model            = "Generic Homelab Host"
      slug             = "generic-homelab-host"
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

    docker_host_opencloud_puid = {
      name        = "docker_host_opencloud_puid"
      label       = "OpenCloud PUID"
      type        = "text"
      group_name  = "Docker"
      description = "PUID used by OpenCloud on this host."
      weight      = 240
    }

    docker_host_opencloud_pgid = {
      name        = "docker_host_opencloud_pgid"
      label       = "OpenCloud PGID"
      type        = "text"
      group_name  = "Docker"
      description = "PGID used by OpenCloud on this host."
      weight      = 250
    }

    docker_host_opencloud_data_root = {
      name        = "docker_host_opencloud_data_root"
      label       = "OpenCloud data root"
      type        = "text"
      group_name  = "Docker"
      description = "Host path used as the OpenCloud data root."
      weight      = 260
    }
  }

  base_hosts = {
    mgt = {
      description = "Docker Swarm manager, automation host, HAProxy endpoint, Technitium DNS primary"
      role_key    = "server"
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

    pg95 = {
      description = "Postgres / Patroni node"
      role_key    = "server"
      tags = [
        "skynet",
        "opentofu",
        "opentofu_managed",
        "postgres",
      ]
    }

    pg96 = {
      description = "Postgres / Patroni node"
      role_key    = "server"
      tags = [
        "skynet",
        "opentofu",
        "opentofu_managed",
        "postgres",
      ]
    }

    pg97 = {
      description = "Postgres / Patroni node"
      role_key    = "server"
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
      try(length(var.host_private_values[host_key].custom_fields), 0) > 0 ? {
        custom_fields = var.host_private_values[host_key].custom_fields
      } : {}
    )
  }

  reserved_ips = {}
}
