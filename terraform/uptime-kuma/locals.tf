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

    # Media
    autobrr   = { group = "media", tag_keys = ["media"] }
    gitea     = { group = "media", tag_keys = ["media"] }
    obsidian  = { group = "media", tag_keys = ["media"] }
    ombi      = { group = "media", tag_keys = ["media"] }
    seerr     = { group = "media", tag_keys = ["media"] }
    stash     = { group = "media", tag_keys = ["media"] }
    thelounge = { group = "media", tag_keys = ["media"] }
    znc       = { group = "media", tag_keys = ["media"] }

    # Monitoring
    gotify      = { group = "monitoring", tag_keys = ["monitoring"] }
    grafana     = { group = "monitoring", tag_keys = ["monitoring"] }
    homepage    = { group = "monitoring", tag_keys = ["monitoring"] }
    portainer   = { group = "monitoring", tag_keys = ["monitoring"] }
    prometheus  = { group = "monitoring", tag_keys = ["monitoring"] }
    uptime-kuma = { group = "monitoring", tag_keys = ["monitoring"] }

    # Network
    netbox = { group = "network", tag_keys = ["network"] }

    # Plex
    tautulli = {
      group                 = "plex"
      tag_keys              = ["plex", "private", "traefik"]
      url                   = "https://tautulli.${var.internal_zone}:${var.private_https_port}/status"
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
    adminer = { group = "utilities", tag_keys = ["utilities"] }
    czkawka = { group = "utilities", tag_keys = ["utilities"] }
  }

  private_http_monitors = {
    for service, cfg in local.private_http_services : "${service}-private" => {
      name        = try(cfg.name, "${join(" ", [for word in split("-", service) : title(word)])} [Private]")
      url         = try(cfg.url, "https://${service}.${var.internal_zone}:${var.private_https_port}")
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

    infisical = {
      group    = "utilities"
      tag_keys = ["public", "utilities"]
    }

    opencloud = {
      group    = "media"
      tag_keys = ["public", "media"]
    }

    traefik = {
      group    = "network"
      tag_keys = ["public", "network"]
    }

    vaultwarden = {
      group    = "utilities"
      tag_keys = ["public", "utilities"]
    }
  }

  public_http_monitors = {
    for service, cfg in local.public_http_services : "${service}-public" => {
      name        = try(cfg.name, "${join(" ", [for word in split("-", service) : title(word)])} [Public]")
      url         = try(cfg.url, "https://${service}.${var.cloudflare_zone}")
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
  # SERVICES (DIRECT)
  ################################

  # These test Docker overlay/service reachability without Technitium/Traefik.
  direct_http_group_defaults = {
    arrs       = { group = "arrs", tag_keys = ["arrs"] }
    media      = { group = "media", tag_keys = ["media"] }
    monitoring = { group = "monitoring", tag_keys = ["monitoring"] }
    network    = { group = "network", tag_keys = ["network"] }
    plex       = { group = "plex", tag_keys = ["plex"] }
    torrents   = { group = "torrents", tag_keys = ["torrents"] }
    usenet     = { group = "usenet", tag_keys = ["usenet"] }
    utilities  = { group = "utilities", tag_keys = ["utilities"] }
  }

  direct_http_services = {
    # ARRs
    bazarr    = { category = "arrs", port = 6767 }
    lidarr    = { category = "arrs", port = 8686 }
    prowlarr  = { category = "arrs", port = 9696 }
    radarr    = { category = "arrs", port = 7878 }
    radarr-4k = { category = "arrs", port = 7878 }
    sonarr    = { category = "arrs", port = 8989 }
    sonarr-4k = { category = "arrs", port = 8989 }
    sportarr  = { category = "arrs", port = 1867 }
    whisparr  = { category = "arrs", port = 6969 }

    # Media
    autobrr   = { category = "media", port = 7474 }
    obsidian  = { category = "media", port = 8080 }
    ombi      = { category = "media", port = 3579 }
    opencloud = { category = "media", port = 9200 }
    seerr     = { category = "media", port = 5055 }
    stash     = { category = "media", port = 9999 }
    thelounge = { category = "media", port = 9000 }
    znc       = { category = "media", port = 6501 }

    # Monitoring
    alloy = {
      category              = "monitoring"
      port                  = 12345
      path                  = "/-/ready"
      accepted_status_codes = ["200-299"]
    }

    gotify = { category = "monitoring", port = 80 }

    grafana = {
      category = "monitoring"
      port     = 3000
      path     = "/login"
    }

    homepage = { category = "monitoring", port = 3000 }

    loki = {
      category              = "monitoring"
      port                  = 3100
      path                  = "/ready"
      accepted_status_codes = ["200-299"]
    }

    portainer = { category = "monitoring", port = 9000 }

    prometheus = {
      category              = "monitoring"
      port                  = 9090
      path                  = "/-/ready"
      accepted_status_codes = ["200-299"]
    }

    uptime-kuma = { category = "monitoring", port = 3001 }

    # Network
    authelia = {
      category              = "network"
      port                  = 9091
      path                  = "/api/health"
      accepted_status_codes = ["200-299"]
    }

    netbox = {
      category = "network"
      port     = 8080
      path     = "/login/"
    }

    traefik = {
      category              = "network"
      port                  = 8081
      path                  = "/ping"
      accepted_status_codes = ["200-299"]
    }

    # Plex
    autopulse-ui = { category = "plex", port = 2875 }

    plex = {
      category              = "plex"
      hostname              = "192.168.80.59"
      port                  = 32400
      path                  = "/identity"
      accepted_status_codes = ["200-299"]
    }

    tautulli = { category = "plex", port = 8181 }

    # Torrents
    qbittorrent    = { category = "torrents", port = 8090 }
    qbittorrent-xs = { category = "torrents", port = 8091 }
    qui            = { category = "torrents", port = 7476 }
    unpackerr      = { category = "torrents", port = 5656 }

    # Usenet
    nzbhydra2 = { category = "usenet", port = 5076 }
    sabnzbd   = { category = "usenet", port = 8080 }

    # Utilities
    adminer     = { category = "utilities", port = 8080 }
    czkawka     = { category = "utilities", port = 5800 }
    gitea       = { category = "utilities", port = 3000 }
    infisical   = { category = "utilities", port = 8080 }
    vaultwarden = { category = "utilities", port = 80 }
  }

  direct_http_monitors = {
    for service, cfg in local.direct_http_services : "${service}-direct" => {
      name        = "${join(" ", [for word in split("-", service) : title(word)])} [Direct]"
      url         = "http://${try(cfg.hostname, service)}:${cfg.port}${try(cfg.path, "")}"
      description = "Direct backend HTTP check for ${service}"

      group    = local.direct_http_group_defaults[cfg.category].group
      tag_keys = try(cfg.tag_keys, local.direct_http_group_defaults[cfg.category].tag_keys)

      accepted_status_codes = try(cfg.accepted_status_codes, ["200-399", "401", "403"])
      method                = "GET"
      ignore_tls            = true
      expiry_notification   = false
      max_redirects         = 10
    }
  }

  # Hand-written monitors for things that are not just https://service.int.zone:8443
  # or http://service:container_port.
  extra_http_monitors = {
    proxmox = {
      name                  = "Proxmox (Web UI)"
      url                   = "https://192.168.80.80:8006"
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
    local.direct_http_monitors,
    local.public_http_monitors,
    local.extra_http_monitors
  )

  ping_monitors = {
    mgt = {
      name        = "mgt (Host Ping)"
      hostname    = "192.168.80.48"
      description = "Primary Swarm manager / Traefik / Technitium primary"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure"]
    }

    unraid = {
      name        = "unraid (Host Ping)"
      hostname    = "192.168.80.20"
      description = "Unraid storage host"
      group       = "infrastructure"
      tag_keys    = ["critical", "storage", "infrastructure"]
    }

    plex = {
      name        = "plex (Host Ping)"
      hostname    = "192.168.80.59"
      description = "Plex / secondary DNS host"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure"]
    }

    pve1 = {
      name        = "pve1 (Host Ping)"
      hostname    = "192.168.80.80"
      description = "Proxmox VE host"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure"]
    }

    pg95 = {
      name        = "pg95 (Host Ping)"
      hostname    = "192.168.80.95"
      description = "PostgreSQL database host"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure"]
    }

    pg96 = {
      name        = "pg96 (Host Ping)"
      hostname    = "192.168.80.96"
      description = "PostgreSQL database host"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure"]
    }

    pg97 = {
      name        = "pg97 (Host Ping)"
      hostname    = "192.168.80.97"
      description = "PostgreSQL database host"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure"]
    }
  }

  tcp_monitors = {
    traefik_private_tcp = {
      name        = "Traefik (Private) HTTPS TCP"
      hostname    = "192.168.80.48"
      port        = 8443
      description = "Traefik private HTTPS entrypoint listener"
      group       = "networking"
      tag_keys    = ["critical", "networking", "traefik"]
    }

    traefik_public_tcp = {
      name        = "Traefik (Public) HTTPS TCP"
      hostname    = "192.168.80.48"
      port        = 443
      description = "Traefik public HTTPS entrypoint listener"
      group       = "networking"
      tag_keys    = ["critical", "networking", "traefik"]
    }

    technitium_primary_tcp = {
      name        = "Technitium (Primary) DNS TCP"
      hostname    = "192.168.80.48"
      port        = 53
      description = "Primary Technitium TCP DNS listener"
      group       = "networking"
      tag_keys    = ["critical", "dns", "networking"]
    }

    technitium_backup_tcp = {
      name        = "Technitium (Backup) DNS TCP"
      hostname    = "192.168.80.59"
      port        = 53
      description = "Backup Technitium TCP DNS listener"
      group       = "networking"
      tag_keys    = ["critical", "dns", "networking"]
    }

    postgres_pg95_tcp = {
      name        = "pg95 (PostgreSQL TCP)"
      hostname    = "192.168.80.95"
      port        = 5432
      description = "PostgreSQL listener on pg95"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure"]
    }

    postgres_pg96_tcp = {
      name        = "pg96 (PostgreSQL TCP)"
      hostname    = "192.168.80.96"
      port        = 5432
      description = "PostgreSQL listener on pg96"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure"]
    }

    postgres_pg97_tcp = {
      name        = "pg97 (PostgreSQL TCP)"
      hostname    = "192.168.80.97"
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
    technitium_primary_internal = {
      name               = "Technitium (Primary) resolves internal zone"
      hostname           = "adminer.${var.internal_zone}"
      dns_resolve_server = "192.168.80.48"
      dns_resolve_type   = "A"
      port               = 53
      description        = "Primary DNS should resolve internal Traefik records"
      group              = "networking"
      tag_keys           = ["critical", "dns", "networking"]
    }

    technitium_backup_internal = {
      name               = "Technitium (Backup) resolves internal zone"
      hostname           = "adminer.${var.internal_zone}"
      dns_resolve_server = "192.168.80.59"
      dns_resolve_type   = "A"
      port               = 53
      description        = "Backup DNS should resolve internal Traefik records"
      group              = "networking"
      tag_keys           = ["critical", "dns", "networking"]
    }

    cloudflare_public = {
      name               = "Cloudflare (Public) resolves public zone"
      hostname           = "opencloud.${var.cloudflare_zone}"
      dns_resolve_server = "1.1.1.1"
      dns_resolve_type   = "A"
      port               = 53
      description        = "Public DNS sanity check"
      group              = "networking"
      tag_keys           = ["dns", "public", "networking"]
    }
  }
}
