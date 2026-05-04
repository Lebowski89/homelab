site = {
  name   = "Homelab"
  slug   = "homelab"
  status = "active"
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
    comments         = "Five-port desktop switch with one Gigabit Ethernet port and four SFP+ 10Gbps ports."
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

hosts = {
  mgt = {
    mgmt_ip     = "192.168.80.48/24"
    dns_name    = "mgt.int.nosugarmaxtaste.com"
    description = "Docker Swarm manager, automation host, HAProxy endpoint, Technitium DNS primary"
    role_key    = "server"
  }

  unraid = {
    mgmt_ip         = "192.168.80.20/24"
    dns_name        = "unraid.int.nosugarmaxtaste.com"
    description     = "Unraid storage host, HAProxy endpoint"
    role_key        = "storage"
    device_type_key = "unraid_host"
  }

  plex = {
    mgmt_ip     = "192.168.80.59/24"
    dns_name    = "plex.int.nosugarmaxtaste.com"
    description = "Plex / Docker Swarm worker, HAProxy endpoint, Technitium DNS secondary"
    role_key    = "server"
  }

  pve1 = {
    mgmt_ip         = "192.168.80.80/24"
    dns_name        = "pve1.int.nosugarmaxtaste.com"
    description     = "Proxmox hypervisor"
    role_key        = "hypervisor"
    device_type_key = "proxmox_host"
  }

  pg95 = {
    mgmt_ip     = "192.168.80.95/24"
    dns_name    = "pg95.int.nosugarmaxtaste.com"
    description = "Postgres / Patroni node"
  }

  pg96 = {
    mgmt_ip     = "192.168.80.96/24"
    dns_name    = "pg96.int.nosugarmaxtaste.com"
    description = "Postgres / Patroni node"
  }

  pg97 = {
    mgmt_ip     = "192.168.80.97/24"
    dns_name    = "pg97.int.nosugarmaxtaste.com"
    description = "Postgres / Patroni node"
  }
}

reserved_ips = {}