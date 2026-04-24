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

  private_http_services = [
    "adminer",
    "authelia",
    "autobrr",
    "bazarr",
    "czkawka",
    "gitea",
    "gotify",
    "homepage",
    "infisical",
    "lidarr",
    "nzbhydra2",
    "obsidian",
    "ombi",
    "portainer",
    "prometheus",
    "prowlarr",
    "qbittorrent",
    "qbittorrent-xs",
    "qui",
    "radarr",
    "radarr-4k",
    "sabnzbd",
    "seerr",
    "sonarr",
    "sonarr-4k",
    "sportarr",
    "stash",
    "tautulli",
    "thelounge",
    "traefik",
    "uptime-kuma",
    "whisparr",
    "znc",
  ]

  # Put anything here that should NOT become a generated HTTPS monitor.
  private_http_monitor_disabled = toset([
    # "alloy",
  ])

  # Per-service overrides while still keeping the generated monitor list compact.
  private_http_monitor_overrides = {
    adminer        = { group = "utilities",  tag_keys = ["utilities",  "private", "traefik"] }
    autobrr        = { group = "media",      tag_keys = ["media",      "private", "traefik"] }
    bazarr         = { group = "arrs",       tag_keys = ["arrs",       "private", "traefik"] }
    gotify         = { group = "monitoring", tag_keys = ["monitoring", "private", "traefik"] }
    lidarr         = { group = "arrs",       tag_keys = ["arrs",       "private", "traefik"] }
    nzbhydra2      = { group = "usenet",     tag_keys = ["usenet",     "private", "traefik"] }
    ombi           = { group = "media",      tag_keys = ["media",      "private", "traefik"] }
    portainer      = { group = "core",       tag_keys = ["core",       "private", "traefik"] }
    prometheus     = { group = "monitoring", tag_keys = ["monitoring", "private", "traefik"] }
    prowlarr       = { group = "arrs",       tag_keys = ["arrs",       "private", "traefik"] }
    qbittorrent    = { group = "torrents",   tag_keys = ["torrents",   "private", "traefik"] }
    qbittorrent-xs = { group = "torrents",   tag_keys = ["torrents",   "private", "traefik"] }
    qui            = { group = "torrents",   tag_keys = ["torrents",   "private", "traefik"] }
    radarr         = { group = "arrs",       tag_keys = ["arrs",       "private", "traefik"] }
    radarr-4k      = { group = "arrs",       tag_keys = ["arrs",       "private", "traefik"] }
    sabnzbd        = { group = "usenet",     tag_keys = ["usenet",     "private", "traefik"] }
    seerr          = { group = "media",      tag_keys = ["media",      "private", "traefik"] }
    sonarr         = { group = "arrs",       tag_keys = ["arrs",       "private", "traefik"] }
    sonarr-4k      = { group = "arrs",       tag_keys = ["arrs",       "private", "traefik"] }
    sportarr       = { group = "arrs",       tag_keys = ["arrs",       "private", "traefik"] }
    stash          = { group = "media",      tag_keys = ["media",      "private", "traefik"] }
    tautulli       = { group = "plex",       tag_keys = ["plex",       "private", "traefik"] }
    uptime-kuma    = { group = "monitoring", tag_keys = ["monitoring", "private", "traefik"] }
    whisparr       = { group = "arrs",       tag_keys = ["arrs",       "private", "traefik"] }
    znc            = { group = "media",      tag_keys = ["media",      "private", "traefik"] }
  }

  private_http_monitors = {
    for service in local.private_http_services : service => merge(
      {
        name                  = join(" ", [for word in split("-", service) : title(word)])
        url                   = "https://${service}.${var.internal_zone}:${var.private_https_port}"
        description           = "Private Traefik route for ${service}"
        group                 = "apps"
        tag_keys              = ["private", "traefik"]
        accepted_status_codes = ["200-399", "401", "403"]
        method                = "GET"
        ignore_tls            = true
        expiry_notification   = true
        max_redirects         = 10
      },
      lookup(local.private_http_monitor_overrides, service, {})
    ) if !contains(local.private_http_monitor_disabled, service)
  }

  # Hand-written monitors for things that are not just https://service.int.zone:8443.
  extra_http_monitors = {
    plex = {
      name                  = "Plex"
      url                   = "http://192.168.80.59:32400/identity"
      description           = "Direct Plex identity endpoint"
      group                 = "media"
      tag_keys              = ["media"]
      accepted_status_codes = ["200-299"]
      method                = "GET"
      ignore_tls            = true
      expiry_notification   = false
      max_redirects         = 10
    }

    proxmox = {
      name                  = "Proxmox Web UI"
      url                   = "https://192.168.80.80:8006"
      description           = "Proxmox VE web interface"
      group                 = "infrastructure"
      tag_keys              = ["critical", "infrastructure"]
      accepted_status_codes = ["200-399", "401", "403"]
      method                = "GET"
      ignore_tls            = true
      expiry_notification   = false
      max_redirects         = 10
    }
  }

  http_monitors = merge(local.private_http_monitors, local.extra_http_monitors)

  ping_monitors = {
    mgt = {
      name        = "mgt"
      hostname    = "192.168.80.48"
      description = "Primary Swarm manager / Traefik / Technitium primary"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure"]
    }

    unraid = {
      name        = "unraid"
      hostname    = "192.168.80.20"
      description = "Unraid storage host"
      group       = "infrastructure"
      tag_keys    = ["critical", "storage", "infrastructure"]
    }

    plex = {
      name        = "plex host"
      hostname    = "192.168.80.59"
      description = "Plex / secondary DNS host"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure"]
    }

    pve1 = {
      name        = "pve1"
      hostname    = "192.168.80.80"
      description = "Proxmox VE host"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure"]
    }

    pg95 = {
      name        = "pg95"
      hostname    = "192.168.80.95"
      description = "PostgreSQL database host"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure"]
    }

    pg96 = {
      name        = "pg96"
      hostname    = "192.168.80.96"
      description = "PostgreSQL database host"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure"]
    }

    pg97 = {
      name        = "pg97"
      hostname    = "192.168.80.97"
      description = "PostgreSQL database host"
      group       = "infrastructure"
      tag_keys    = ["critical", "infrastructure"]
    }
  }

  tcp_monitors = {
    technitium_primary_tcp = {
      name        = "Technitium Primary DNS TCP"
      hostname    = "192.168.80.48"
      port        = 53
      description = "Primary Technitium TCP DNS listener"
      group       = "networking"
      tag_keys    = ["critical", "dns", "networking"]
    }

    technitium_backup_tcp = {
      name        = "Technitium Backup DNS TCP"
      hostname    = "192.168.80.59"
      port        = 53
      description = "Backup Technitium TCP DNS listener"
      group       = "networking"
      tag_keys    = ["critical", "dns", "networking"]
    }
  }

  dns_monitors = {
    technitium_primary_internal = {
      name               = "Technitium Primary resolves internal zone"
      hostname           = "adminer.${var.internal_zone}"
      dns_resolve_server = "192.168.80.48"
      dns_resolve_type   = "A"
      port               = 53
      description        = "Primary DNS should resolve internal Traefik records"
      group              = "networking"
      tag_keys           = ["critical", "dns", "networking"]
    }

    technitium_backup_internal = {
      name               = "Technitium Backup resolves internal zone"
      hostname           = "adminer.${var.internal_zone}"
      dns_resolve_server = "192.168.80.59"
      dns_resolve_type   = "A"
      port               = 53
      description        = "Backup DNS should resolve internal Traefik records"
      group              = "networking"
      tag_keys           = ["critical", "dns", "networking"]
    }

    cloudflare_public = {
      name               = "Cloudflare resolves public zone"
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
