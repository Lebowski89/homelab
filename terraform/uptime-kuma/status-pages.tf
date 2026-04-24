locals {
  monitor_ids = merge(
    { for key, monitor in uptimekuma_monitor_http.this : "http.${key}" => monitor.id },
    { for key, monitor in uptimekuma_monitor_ping.this : "ping.${key}" => monitor.id },
    { for key, monitor in uptimekuma_monitor_tcp_port.this : "tcp.${key}" => monitor.id },
    { for key, monitor in uptimekuma_monitor_dns.this : "dns.${key}" => monitor.id },
  )

  status_page_groups = [
    {
      name     = "Infrastructure"
      weight   = 2
      send_url = false
      monitors = [
        "ping.mgt",
        "ping.unraid",
        "ping.plex",
        "ping.pve1",
        "http.proxmox",
        "ping.pg95",
        "ping.pg96",
        "ping.pg97",
      ]
    },
    {
      name     = "Networking"
      weight   = 1
      send_url = false
      monitors = [
        "dns.technitium_primary_internal",
        "dns.technitium_backup_internal",
        "tcp.technitium_primary_tcp",
        "tcp.technitium_backup_tcp",
      ]
    },
    {
      name     = "arrs"
      weight   = 4
      send_url = true
      monitors = [
        "http.bazarr",
        "http.lidarr",
        "http.prowlarr",
        "http.radarr",
        "http.radarr-4k",
        "http.sonarr",
        "http.sonarr-4k",
        "http.sportarr",
        "http.whisparr",
      ]
    },
    {
      name     = "Media"
      weight   = 4
      send_url = true
      monitors = [
        "http.autobrr",
        "http.ombi",
        "http.seerr",
        "http.stash",
        "http.znc",
      ]
    },
    {
      name     = "Monitoring"
      weight   = 3
      send_url = true
      monitors = [
        "http.gotify",
        "http.prometheus",
        "http.uptime-kuma",
      ]
    },
    {
      name     = "Torrents"
      weight   = 3
      send_url = true
      monitors = [
        "http.qbittorrent",
        "http.qbittorrent-xs",
        "http.qui",
      ]
    },
    {
      name     = "Usenet"
      weight   = 3
      send_url = true
      monitors = [
        "http.nzbhydra2",
        "http.sabnzbd",
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
  theme                   = "auto"

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
