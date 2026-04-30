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