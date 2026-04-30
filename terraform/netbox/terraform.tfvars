site = {
  name   = "Homelab"
  slug   = "homelab"
  status = "active"
}

device_role = {
  name      = "server"
  slug      = "server"
  color_hex = "9e9e9e"
}

device_type = {
  model = "Generic Homelab Host"
  slug  = "generic-homelab-host"
}

prefixes = {
  lan = {
    prefix      = "192.168.80.0/24"
    description = "Primary homelab LAN"
  }
}

hosts = {
  mgt = {
    mgmt_ip  = "192.168.80.48/24"
    dns_name = "mgt.home.arpa"
    description = "Docker swarm manager and primary automation host"
  }

  unraid = {
    mgmt_ip  = "192.168.80.20/24"
    dns_name = "unraid.home.arpa"
  }

  plex = {
    mgmt_ip  = "192.168.80.59/24"
    dns_name = "plex.home.arpa"
  }

  pve1 = {
    mgmt_ip  = "192.168.80.80/24"
    dns_name = "pve1.home.arpa"
    description = "Proxmox hypervisor"
  }

  pg95 = {
    mgmt_ip  = "192.168.80.95/24"
    dns_name = "pg95.home.arpa"
  }

  pg96 = {
    mgmt_ip  = "192.168.80.96/24"
    dns_name = "pg96.home.arpa"
  }

  pg97 = {
    mgmt_ip  = "192.168.80.97/24"
    dns_name = "pg97.home.arpa"
  }
}