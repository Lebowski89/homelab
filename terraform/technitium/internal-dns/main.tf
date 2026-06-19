locals {
  ipv4_records = [
    "adminer",
    "alertmanager",
    "alloy",
    "authelia",
    "autobrr",
    "bazarr",
    "czkawka",
    "dozzle",
    "gitea",
    "gotify",
    "grafana",
    "homepage",
    "infisical",
    "lidarr",
    "netbox",
    "notifiarr",
    "nzbhydra2",
    "obsidian",
    "ombi",
    "opencloud",
    "portainer",
    "postgres",
    "prometheus",
    "prowlarr",
    "qbittorrent",
    "qbittorrent-xs",
    "qui",
    "radarr",
    "radarr-4k",
    "romm",
    "sabnzbd",
    "seerr",
    "sonarr",
    "sonarr-4k",
    "sportarr",
    "stash",
    "syncthing",
    "tautulli",
    "technitium",
    "thelounge",
    "traefik",
    "uptime-kuma",
    "vaultwarden",
    "wallos",
    "whisparr",
    "znc",
  ]
}

resource "technitium_zone" "internal" {
  name    = var.zone_name
  type    = "Primary"
  catalog = var.internal_zone_catalog
}

resource "technitium_record" "service_a" {
  for_each = toset(local.ipv4_records)

  domain     = "${each.value}.${var.zone_name}"
  type       = "A"
  ttl        = var.ttl
  ip_address = var.traefik_ipv4

  depends_on = [technitium_zone.internal]
}
