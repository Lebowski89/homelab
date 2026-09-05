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
        "ping.n8n",
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
      name     = "Monitoring"
      weight   = 3
      send_url = true
      monitors = [
        "http.dozzle-private",
        "http.gotify-private",
        "http.grafana-private",
        "http.homepage-private",
        "http.portainer-private",
        "http.prometheus-private",
        "http.uptime-kuma-private",
      ]
    },
    {
      name     = "ARRs"
      weight   = 4
      send_url = true
      monitors = [
        "http.bazarr-private",
        "http.lidarr-private",
        "http.prowlarr-private",
        "http.radarr-private",
        "http.radarr-4k-private",
        "http.sonarr-private",
        "http.sonarr-4k-private",
        "http.sportarr-private",
        "http.whisparr-private",
      ]
    },
    {
      name     = "Torrents"
      weight   = 5
      send_url = true
      monitors = [
        "http.qbittorrent-private",
        "http.qbittorrent-xs-private",
        "http.qui-private",
        "http.upbrr-private",
      ]
    },
    {
      name     = "Usenet"
      weight   = 6
      send_url = true
      monitors = [
        "http.nzbhydra2-private",
        "http.sabnzbd-private",
      ]
    },
    {
      name     = "Plex"
      weight   = 7
      send_url = true
      monitors = [
        "http.plex-direct",
        "http.tautulli-private",
      ]
    },
    {
      name     = "Media"
      weight   = 8
      send_url = true
      monitors = [
        "http.autobrr-private",
        "http.gitea-private",
        "http.obsidian-private",
        "http.ombi-private",
        "http.opencloud-public",
        "http.seerr-private",
        "http.stash-private",
        "http.thelounge-private",
        "http.znc-private",
      ]
    },
    {
      name     = "Gaming"
      weight   = 9
      send_url = true
      monitors = [
        "http.romm-private",
      ]
    },
    {
      name     = "Finance"
      weight   = 10
      send_url = true
      monitors = [
        "http.wallos-private",
      ]
    },
    {
      name     = "Network"
      weight   = 11
      send_url = true
      monitors = [
        "http.authelia-public",
        "http.netbox-private",
        "http.traefik-private",
      ]
    },
    {
      name     = "Utilities"
      weight   = 12
      send_url = true
      monitors = [
        "http.adminer-private",
        "http.czkawka-private",
        "http.infisical-private",
        "http.syncthing-private",
        "http.vaultwarden-public",
      ]
    },
    {
      name     = "Automation"
      weight   = 13
      send_url = true
      monitors = [
        "http.n8n-direct",
        "http.n8n-private",
      ]
    },
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
