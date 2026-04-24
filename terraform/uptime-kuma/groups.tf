locals {
  groups = {
    apps = {
      name        = "Apps"
      description = "General private homelab applications"
    }

    arrs = {
      name        = "ARRs"
      description = "Application monitoring for ARR services"
    }

    core = {
      name        = "Core"
      description = "Core services and management interfaces"
    }

    infrastructure = {
      name        = "Infrastructure"
      description = "Hosts, hypervisors, storage, and management endpoints"
    }

    media = {
      name        = "Media"
      description = "Media services and download stack"
    }

    monitoring = {
      name        = "Monitoring"
      description = "Monitoring, logging, and notification services"
    }

    networking = {
      name        = "Networking"
      description = "DNS, Traefik, auth, and connectivity"
    }

    plex = {
      name        = "Plex"
      description = "Plex ecosystem services and monitoring"
    }

    torrents = {
      name        = "Torrents"
      description = "Torrent clients and automation tools"
    }

    usenet = {
      name        = "Usenet"
      description = "Usenet indexers and automation tools"
    }

    utilities = {
      name        = "Utilities"
      description = "Utility applications and self-hosted services"
    }
  }
}

resource "uptimekuma_monitor_group" "this" {
  for_each = local.groups

  name        = each.value.name
  description = each.value.description
  active      = true
}
