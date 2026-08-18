locals {
  default_monitor = {
    interval        = 60
    timeout         = 30
    max_retries     = 2
    retry_interval  = 60
    resend_interval = 0
    active          = true
    upside_down     = false
  }

  ################################
  # NETBOX (OUTPUTS)
  ################################

  netbox_host_ips           = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.host_primary_ipv4, {}) : {}
  netbox_cloudflare_zone    = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.cloudflare_zone, "") : ""
  netbox_internal_zone      = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.internal_zone, "") : ""
  netbox_private_https_port = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.private_https_port, null) : null

  cloudflare_zone = trimspace(var.cloudflare_zone) != "" ? trimspace(var.cloudflare_zone) : local.netbox_cloudflare_zone

  internal_zone = trimspace(var.internal_zone) != "" ? trimspace(var.internal_zone) : local.netbox_internal_zone

  private_https_port = coalesce(var.private_https_port, local.netbox_private_https_port, 8443)

  uptime_kuma_endpoint = trimspace(var.uptime_kuma_endpoint) != "" ? trimspace(var.uptime_kuma_endpoint) : "https://uptime-kuma.${local.internal_zone}:${local.private_https_port}"

  gotify_server_url = trimspace(var.gotify_server_url) != "" ? trimspace(var.gotify_server_url) : "https://gotify.${local.internal_zone}:${local.private_https_port}"

  host_ips = merge(
    local.netbox_host_ips,
    var.host_ips,
  )

  ################################
  # SERVICES (PRIVATE)
  ################################

  private_http_services = {
    # ARRs
    bazarr    = { group = "arrs", tag_keys = ["arrs"] }
    lidarr    = { group = "arrs", tag_keys = ["arrs"] }
    prowlarr  = { group = "arrs", tag_keys = ["arrs"] }
    radarr    = { group = "arrs", tag_keys = ["arrs"] }
    radarr-4k = { group = "arrs", tag_keys = ["arrs"] }
    sonarr    = { group = "arrs", tag_keys = ["arrs"] }
    sonarr-4k = { group = "arrs", tag_keys = ["arrs"] }
    sportarr  = { group = "arrs", tag_keys = ["arrs"] }
    whisparr  = { group = "arrs", tag_keys = ["arrs"] }

    # Finance
    wallos = { group = "finance", tag_keys = ["finance"] }

    # Gaming
    romm = { group = "gaming", tag_keys = ["gaming"] }

    # Media
    autobrr   = { group = "media", tag_keys = ["media"] }
    gitea     = { group = "media", tag_keys = ["media"] }
    obsidian  = { group = "media", tag_keys = ["media"] }
    ombi      = { group = "media", tag_keys = ["media"] }
    seerr     = { group = "media", tag_keys = ["media"] }
    stash     = { group = "media", tag_keys = ["media"] }
    thelounge = { group = "media", tag_keys = ["media"] }
    znc       = { group = "media", tag_keys = ["media"] }

    # Automation
    n8n = {
      group                 = "automation"
      tag_keys              = ["automation", "private"]
      url                   = "https://n8n.${local.internal_zone}:${local.private_https_port}/healthz/readiness"
      accepted_status_codes = ["200-299"]
      max_redirects         = 0
    }

    # Monitoring
    dozzle      = { group = "monitoring", tag_keys = ["monitoring"] }
    gotify      = { group = "monitoring", tag_keys = ["monitoring"] }
    grafana     = { group = "monitoring", tag_keys = ["monitoring"] }
    homepage    = { group = "monitoring", tag_keys = ["monitoring"] }
    portainer   = { group = "monitoring", tag_keys = ["monitoring"] }
    prometheus  = { group = "monitoring", tag_keys = ["monitoring"] }
    uptime-kuma = { group = "monitoring", tag_keys = ["monitoring"] }

    # Network
    netbox  = { group = "network", tag_keys = ["network"] }
    traefik = { group = "network", tag_keys = ["network"] }

    # Plex
    tautulli = {
      group                 = "plex"
      tag_keys              = ["plex", "private", "traefik"]
      url                   = "https://tautulli.${local.internal_zone}:${local.private_https_port}/status"
      accepted_status_codes = ["200-299"]
      max_redirects         = 0
    }

    # Torrents
    qbittorrent    = { group = "torrents", tag_keys = ["torrents"] }
    qbittorrent-xs = { group = "torrents", tag_keys = ["torrents"] }
    qui            = { group = "torrents", tag_keys = ["torrents"] }

    # Usenet
    nzbhydra2 = { group = "usenet", tag_keys = ["usenet"] }
    sabnzbd   = { group = "usenet", tag_keys = ["usenet"] }

    # Utilities
    adminer   = { group = "utilities", tag_keys = ["utilities"] }
    czkawka   = { group = "utilities", tag_keys = ["utilities"] }
    infisical = { group = "utilities", tag_keys = ["utilities"] }
    syncthing = { group = "utilities", tag_keys = ["utilities"] }
  }

  private_http_monitors = {
    for service, cfg in local.private_http_services : "${service}-private" => {
      name        = try(cfg.name, "${join(" ", [for word in split("-", service) : title(word)])} [Private]")
      url         = try(cfg.url, "https://${service}.${local.internal_zone}:${local.private_https_port}")
      description = try(cfg.description, "Private Traefik route for ${service}")

      group    = try(cfg.group, "apps")
      tag_keys = try(cfg.tag_keys, ["private"])

      accepted_status_codes = try(cfg.accepted_status_codes, ["200-399", "401", "403"])
      method                = try(cfg.method, "GET")
      ignore_tls            = try(cfg.ignore_tls, true)
      expiry_notification   = try(cfg.expiry_notification, true)
      max_redirects         = try(cfg.max_redirects, 10)
    }
  }

  ################################
  # SERVICES (PUBLIC)
  ################################

  public_http_services = {
    # Public Cloudflare / Traefik routes.

    authelia = {
      group    = "network"
      tag_keys = ["public", "network"]
    }

    opencloud = {
      group    = "media"
      tag_keys = ["public", "media"]
    }

    vaultwarden = {
      group    = "utilities"
      tag_keys = ["public", "utilities"]
    }
  }

  public_http_monitors = {
    for service, cfg in local.public_http_services : "${service}-public" => {
      name        = try(cfg.name, "${join(" ", [for word in split("-", service) : title(word)])} [Public]")
      url         = try(cfg.url, "https://${service}.${local.cloudflare_zone}")
      description = try(cfg.description, "Public Cloudflare/Traefik route for ${service}")

      group    = try(cfg.group, "apps")
      tag_keys = try(cfg.tag_keys, ["public"])

      accepted_status_codes = try(cfg.accepted_status_codes, ["200-399", "401", "403"])
      method                = try(cfg.method, "GET")
      ignore_tls            = try(cfg.ignore_tls, false)
      expiry_notification   = try(cfg.expiry_notification, true)
      max_redirects         = try(cfg.max_redirects, 10)
    }
  }

  ################################
  # SERVICES (DIRECT / SPECIAL)
  ################################

  # Stable host endpoints that intentionally bypass Traefik.
  extra_http_monitors = {
    n8n-direct = {
      name                  = "n8n [Direct]"
      url                   = "http://${local.host_ips["n8n"]}:5678/healthz/readiness"
      description           = "Direct n8n VM readiness endpoint"
      group                 = "automation"
      tag_keys              = ["automation", "direct"]
      accepted_status_codes = ["200-299"]
      method                = "GET"
      ignore_tls            = true
      expiry_notification   = false
      max_redirects         = 0
    }

    plex-direct = {
      name                  = "Plex [Direct]"
      url                   = "http://${local.host_ips["plex"]}:32400/identity"
      description           = "Direct Plex host endpoint"
      group                 = "plex"
      tag_keys              = ["plex", "direct"]
      accepted_status_codes = ["200-299"]
      method                = "GET"
      ignore_tls            = true
      expiry_notification   = false
      max_redirects         = 10
    }

    proxmox = {
      name                  = "Proxmox (Web UI)"
      url                   = "https://${local.host_ips["pve1"]}:8006"
      description           = "Proxmox VE web interface"
      group                 = "infrastructure"
      tag_keys              = ["infrastructure"]
      accepted_status_codes = ["200-399", "401", "403"]
      method                = "GET"
      ignore_tls            = true
      expiry_notification   = false
      max_redirects         = 10
    }
  }

  http_monitors = merge(
    local.private_http_monitors,
    local.public_http_monitors,
    local.extra_http_monitors
  )

  ping_monitors = {
    n8n = {
      name        = "n8n (Host Ping)"
      hostname    = local.host_ips["n8n"]
      description = "Dedicated n8n automation VM"
      group       = "infrastructure"
      tag_keys    = ["automation", "infrastructure"]
    }

    dns03 = {
      name        = "dns03 (Host Ping)"
      hostname    = local.host_ips["dns03"]
      description = "Technitium DNS tertiary, DHCP, and keepalived backup host"
      group       = "infrastructure"
      tag_keys    = ["critical", "dns", "infrastructure"]
    }

    mgt = {
      name        = "mgt (Host Ping)"
      hostname    = local.host_ips["mgt"]
      description = "Primary Swarm manager / Traefik / Technitium primary"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure"]
    }

    unraid = {
      name        = "unraid (Host Ping)"
      hostname    = local.host_ips["unraid"]
      description = "Unraid storage host"
      group       = "infrastructure"
      tag_keys    = ["critical", "storage", "infrastructure"]
    }

    plex = {
      name        = "plex (Host Ping)"
      hostname    = local.host_ips["plex"]
      description = "Plex / secondary DNS host"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure"]
    }

    pve1 = {
      name        = "pve1 (Host Ping)"
      hostname    = local.host_ips["pve1"]
      description = "Proxmox VE host"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure"]
    }

    pg95 = {
      name        = "pg95 (Host Ping)"
      hostname    = local.host_ips["pg95"]
      description = "PostgreSQL database host"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure"]
    }

    pg96 = {
      name        = "pg96 (Host Ping)"
      hostname    = local.host_ips["pg96"]
      description = "PostgreSQL database host"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure"]
    }

    pg97 = {
      name        = "pg97 (Host Ping)"
      hostname    = local.host_ips["pg97"]
      description = "PostgreSQL database host"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure"]
    }
  }

  tcp_monitors = {
    traefik_private_tcp = {
      name        = "Traefik (Private) HTTPS TCP"
      hostname    = local.host_ips["mgt"]
      port        = local.private_https_port
      description = "Traefik private HTTPS entrypoint listener"
      group       = "networking"
      tag_keys    = ["critical", "networking", "traefik"]
    }

    traefik_public_tcp = {
      name        = "Traefik (Public) HTTPS TCP"
      hostname    = local.host_ips["mgt"]
      port        = 443
      description = "Traefik public HTTPS entrypoint listener"
      group       = "networking"
      tag_keys    = ["critical", "networking", "traefik"]
    }

    postgres_pg95_tcp = {
      name        = "pg95 (PostgreSQL TCP)"
      hostname    = local.host_ips["pg95"]
      port        = 5432
      description = "PostgreSQL listener on pg95"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure"]
    }

    postgres_pg96_tcp = {
      name        = "pg96 (PostgreSQL TCP)"
      hostname    = local.host_ips["pg96"]
      port        = 5432
      description = "PostgreSQL listener on pg96"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure"]
    }

    postgres_pg97_tcp = {
      name        = "pg97 (PostgreSQL TCP)"
      hostname    = local.host_ips["pg97"]
      port        = 5432
      description = "PostgreSQL listener on pg97"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure"]
    }
  }

  postgres_monitors = {
    pg95 = {
      name        = "pg95 (PostgreSQL Database Monitoring)"
      description = "PostgreSQL query monitor for pg95"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure", "storage"]
    }

    pg96 = {
      name        = "pg96 (PostgreSQL Database Monitoring)"
      description = "PostgreSQL query monitor for pg96"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure", "storage"]
    }

    pg97 = {
      name        = "pg97 (PostgreSQL Database Monitoring)"
      description = "PostgreSQL query monitor for pg97"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure", "storage"]
    }
  }

  dns_monitors = {
    cloudflare_public = {
      name               = "Cloudflare (Public) resolves public zone"
      hostname           = "opencloud.${local.cloudflare_zone}"
      dns_resolve_server = "1.1.1.1"
      dns_resolve_type   = "A"
      port               = 53
      description        = "Public DNS sanity check"
      group              = "networking"
      tag_keys           = ["dns", "public", "networking"]
    }
  }
}
