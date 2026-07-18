locals {
  ################################
  # NETBOX (OUTPUTS)
  ################################

  netbox_host_ips      = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.host_primary_ipv4, {}) : {}
  netbox_internal_zone = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.internal_zone, "") : ""

  domain_int = trimspace(var.domain_int) != "" ? trimspace(var.domain_int) : local.netbox_internal_zone

  private_https_port = var.private_https_port

  seerr_url = trimspace(var.seerr_url) != "" ? trimspace(var.seerr_url) : "https://seerr.${local.domain_int}:${local.private_https_port}"

  plex_ip = trimspace(var.plex_ip) != "" ? trimspace(var.plex_ip) : lookup(local.netbox_host_ips, "plex", "")

  ################################
  # SEERR SETTINGS
  ################################

  seerr_application_url = local.seerr_url

  seerr_plex = {
    ip      = local.plex_ip
    port    = 32400
    use_ssl = false
  }

  seerr_tautulli = {
    hostname     = "tautulli.${local.domain_int}"
    port         = local.private_https_port
    api_key      = var.tautulli_api_key
    use_ssl      = true
    url_base     = ""
    external_url = "https://tautulli.${local.domain_int}:${local.private_https_port}"
  }

  seerr_gotify = {
    enabled      = true
    embed_poster = false
    notification_types = [
      "MEDIA_PENDING",
      "MEDIA_APPROVED",
      "MEDIA_AVAILABLE",
      "ISSUE_CREATED",
      "ISSUE_COMMENT",
      "ISSUE_RESOLVED"
    ]
    url   = "https://gotify.${local.domain_int}:${local.private_https_port}"
    token = var.gotify_token
  }

  seerr_radarr_servers = [
    {
      id                     = 0
      name                   = "Radarr"
      hostname               = "radarr.${local.domain_int}"
      port                   = local.private_https_port
      api_key                = var.radarr_api_key
      use_ssl                = true
      base_url               = ""
      quality_profile_id     = 8
      quality_profile_name   = "Remux + WEB 1080p"
      active_directory       = "/data/media/movies"
      minimum_availability   = "released"
      is_4k                  = false
      is_default             = true
      sync_enabled           = true
      enable_scan            = true
      prevent_search         = false
      tag_requests_with_user = false
      tags                   = []
    },
    {
      id                     = 1
      name                   = "Radarr-4K"
      hostname               = "radarr-4k.${local.domain_int}"
      port                   = local.private_https_port
      api_key                = var.radarr_4k_api_key
      use_ssl                = true
      base_url               = ""
      quality_profile_id     = 8
      quality_profile_name   = "Remux + WEB 2160p"
      active_directory       = "/data/media/movies-4k"
      minimum_availability   = "released"
      is_4k                  = true
      is_default             = true
      sync_enabled           = true
      enable_scan            = true
      prevent_search         = false
      tag_requests_with_user = false
      tags                   = []
    }
  ]

  seerr_sonarr_servers = [
    {
      id                     = 0
      name                   = "Sonarr"
      hostname               = "sonarr.${local.domain_int}"
      port                   = local.private_https_port
      api_key                = var.sonarr_api_key
      use_ssl                = true
      base_url               = ""
      quality_profile_id     = 10
      quality_profile_name   = "WEB-1080p (Alternative)"
      active_directory       = "/data/media/tv"
      active_anime_directory = "/data/media/tv"
      is_4k                  = false
      is_default             = true
      sync_enabled           = true
      enable_scan            = true
      prevent_search         = false
      tag_requests_with_user = false
      enable_season_folders  = false
      tags                   = []
      anime_tags             = []
    },
    {
      id                     = 1
      name                   = "Sonarr-4K"
      hostname               = "sonarr-4k.${local.domain_int}"
      port                   = local.private_https_port
      api_key                = var.sonarr_4k_api_key
      use_ssl                = true
      base_url               = ""
      quality_profile_id     = 9
      quality_profile_name   = "WEB-2160p"
      active_directory       = "/data/media/tv-4k"
      active_anime_directory = "/data/media/tv-4k"
      is_4k                  = true
      is_default             = true
      sync_enabled           = true
      enable_scan            = true
      prevent_search         = false
      tag_requests_with_user = false
      enable_season_folders  = false
      tags                   = []
      anime_tags             = []
    }
  ]
}
