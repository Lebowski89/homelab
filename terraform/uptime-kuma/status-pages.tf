locals {
  monitor_ids = merge(
    { for key, monitor in uptimekuma_monitor_http.this : "http.${key}" => monitor.id },
    { for key, monitor in uptimekuma_monitor_ping.this : "ping.${key}" => monitor.id },
    { for key, monitor in uptimekuma_monitor_tcp_port.this : "tcp.${key}" => monitor.id },
    { for key, monitor in uptimekuma_monitor_dns.this : "dns.${key}" => monitor.id },
    { for key, monitor in uptimekuma_monitor_postgres.this : "postgres.${key}" => monitor.id },
  )

  status_page_groups = [
    {
      name     = "Infrastructure"
      weight   = 1
      send_url = false
      monitors = [
        "ping.mgt",
        "ping.unraid",
        "ping.plex",
        "ping.pve1",
        "http.proxmox",
        "ping.dns03",
        "ping.pg95",
        "ping.pg96",
        "ping.pg97",
        "tcp.postgres_pg95_tcp",
        "tcp.postgres_pg96_tcp",
        "tcp.postgres_pg97_tcp",
        "postgres.pg95",
        "postgres.pg96",
        "postgres.pg97",
      ]
    },
    {
      name     = "Networking"
      weight   = 2
      send_url = false
      monitors = [
        "dns.cloudflare_public",
        "tcp.traefik_private_tcp",
        "tcp.traefik_public_tcp",
      ]
    },
    {
      name     = "ARRs"
      weight   = 4
      send_url = true
      monitors = [
        "http.bazarr-private",
        "http.bazarr-direct",
        "http.lidarr-private",
        "http.lidarr-direct",
        "http.prowlarr-private",
        "http.prowlarr-direct",
        "http.radarr-private",
        "http.radarr-direct",
        "http.radarr-4k-private",
        "http.radarr-4k-direct",
        "http.sonarr-private",
        "http.sonarr-direct",
        "http.sonarr-4k-private",
        "http.sonarr-4k-direct",
        "http.sportarr-private",
        "http.sportarr-direct",
        "http.whisparr-private",
        "http.whisparr-direct",
      ]
    },
    {
      name     = "Media"
      weight   = 8
      send_url = true
      monitors = [
        "http.autobrr-private",
        "http.autobrr-direct",
        "http.obsidian-private",
        "http.obsidian-direct",
        "http.ombi-private",
        "http.ombi-direct",
        "http.opencloud-direct",
        "http.opencloud-public",
        "http.seerr-private",
        "http.seerr-direct",
        "http.stash-private",
        "http.stash-direct",
        "http.thelounge-private",
        "http.thelounge-direct",
        "http.znc-private",
        "http.znc-direct",
      ]
    },
    {
      name     = "Monitoring"
      weight   = 3
      send_url = true
      monitors = [
        "http.blackbox-exporter-direct",
        "http.gotify-private",
        "http.gotify-direct",
        "http.grafana-private",
        "http.grafana-direct",
        "http.homepage-private",
        "http.homepage-direct",
        "http.portainer-private",
        "http.portainer-direct",
        "http.prometheus-private",
        "http.prometheus-direct",
        "http.uptime-kuma-private",
        "http.uptime-kuma-direct",
      ]
    },
    {
      name     = "Network"
      weight   = 9
      send_url = true
      monitors = [
        "http.authelia-direct",
        "http.authelia-public",
        "http.traefik-direct",
        "http.traefik-public",
      ]
    },
    {
      name     = "Plex"
      weight   = 7
      send_url = true
      monitors = [
        "http.plex-direct",
        "http.tautulli-private",
        "http.tautulli-direct",
      ]
    },
    {
      name     = "Torrents"
      weight   = 5
      send_url = true
      monitors = [
        "http.qbittorrent-private",
        "http.qbittorrent-direct",
        "http.qbittorrent-xs-private",
        "http.qbittorrent-xs-direct",
        "http.qui-private",
        "http.qui-direct",
      ]
    },
    {
      name     = "Usenet"
      weight   = 6
      send_url = true
      monitors = [
        "http.nzbhydra2-private",
        "http.nzbhydra2-direct",
        "http.sabnzbd-private",
        "http.sabnzbd-direct",
      ]
    },
    {
      name     = "Utilities"
      weight   = 10
      send_url = true
      monitors = [
        "http.adminer-private",
        "http.adminer-direct",
        "http.czkawka-private",
        "http.czkawka-direct",
        "http.gitea-private",
        "http.gitea-direct",
        "http.infisical-direct",
        "http.infisical-private",
        "http.vaultwarden-direct",
        "http.vaultwarden-public",
      ]
    }
  ]
}

resource "uptimekuma_status_page" "homelab" {
  slug                    = "homelab"
  title                   = "Homelab Status"
  description             = "Internal homelab service status"
  published               = true
  show_tags               = true
  show_certificate_expiry = true
  show_powered_by         = false
  theme                   = "dark"

  public_group_list = [
    for group in local.status_page_groups : {
      name   = group.name
      weight = group.weight

      monitor_list = [
        for monitor_key in group.monitors : {
          id       = local.monitor_ids[monitor_key]
          send_url = group.send_url
        }
      ]
    }
  ]
}
