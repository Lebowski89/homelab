locals {
  netbox_host_primary_ipv4 = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.host_primary_ipv4, {}) : {}
  netbox_internal_zone     = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.internal_zone, "") : ""

  zone_name_source = trimspace(var.zone_name) != "" ? var.zone_name : local.netbox_internal_zone
  zone_name        = trim(trimspace(local.zone_name_source), ".")

  technitium_server_host = trimspace(var.technitium_server_host)

  technitium_server_ip = trimspace(
    lookup(local.netbox_host_primary_ipv4, local.technitium_server_host, "")
  )

  explicit_technitium_server = trimspace(var.technitium_server)

  technitium_server = local.explicit_technitium_server != "" ? local.explicit_technitium_server : (
    local.technitium_server_ip != ""
    ? "http://${local.technitium_server_ip}:${var.technitium_server_port}"
    : ""
  )

  traefik_host = trimspace(var.traefik_host)

  traefik_ipv4 = trimspace(var.traefik_ipv4) != "" ? trimspace(var.traefik_ipv4) : trimspace(
    lookup(local.netbox_host_primary_ipv4, local.traefik_host, "")
  )

  technitium_cluster_domain = trim(trimspace(var.technitium_cluster_domain), ".")

  internal_zone_catalog = trimspace(var.internal_zone_catalog) != "" ? trim(
    trimspace(var.internal_zone_catalog),
    "."
    ) : (
    local.technitium_cluster_domain != ""
    ? "cluster-catalog.${local.technitium_cluster_domain}"
    : ""
  )

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
    "n8n",
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

  lifecycle {
    precondition {
      condition     = local.zone_name != ""
      error_message = "Unable to determine the internal DNS zone. Set zone_name explicitly or ensure NetBox exports internal_zone."
    }

    precondition {
      condition     = local.internal_zone_catalog != ""
      error_message = "Unable to determine the Technitium catalog zone. Set internal_zone_catalog explicitly or provide technitium_cluster_domain."
    }
  }
}

resource "technitium_record" "service_a" {
  for_each = toset(local.ipv4_records)

  domain     = "${each.value}.${local.zone_name}"
  type       = "A"
  ttl        = var.ttl
  ip_address = local.traefik_ipv4

  lifecycle {
    precondition {
      condition     = can(cidrhost("${local.traefik_ipv4}/32", 0))
      error_message = "Unable to determine a valid Traefik IPv4 address. Set traefik_ipv4 explicitly or ensure NetBox host_primary_ipv4 contains the configured traefik_host."
    }
  }

  depends_on = [technitium_zone.internal]
}
