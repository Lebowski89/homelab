locals {
  netbox_host_primary_ipv4 = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.host_primary_ipv4, {}) : {}
  netbox_internal_zone     = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.internal_zone, "") : ""

  zone_name = trimspace(var.zone_name) != "" ? trimspace(var.zone_name) : local.netbox_internal_zone

  technitium_server_ip = lookup(local.netbox_host_primary_ipv4, var.technitium_server_host, "")

  technitium_server = trimspace(var.technitium_server) != "" ? trimspace(var.technitium_server) : "http://${local.technitium_server_ip}:${var.technitium_server_port}"

  traefik_ipv4 = trimspace(var.traefik_ipv4) != "" ? trimspace(var.traefik_ipv4) : lookup(local.netbox_host_primary_ipv4, var.traefik_host, "")

  internal_zone_catalog = trimspace(var.internal_zone_catalog) != "" ? trimspace(var.internal_zone_catalog) : "cluster-catalog.${var.technitium_cluster_domain}"

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
  name    = local.zone_name
  type    = "Primary"
  catalog = local.internal_zone_catalog
}

resource "technitium_record" "service_a" {
  for_each = toset(local.ipv4_records)

  domain     = "${each.value}.${local.zone_name}"
  type       = "A"
  ttl        = var.ttl
  ip_address = local.traefik_ipv4

  depends_on = [technitium_zone.internal]
}
