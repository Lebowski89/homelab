resource "seerr_main_settings" "this" {
  app_title          = "Seerr"
  application_url    = local.seerr_application_url
  locale             = "en"
  local_login        = true
  media_server_login = true
  new_plex_login     = true
  partial_requests   = true
  hide_available     = false
}

resource "seerr_network_settings" "this" {
  trust_proxy     = false
  csrf_protection = false
}

resource "seerr_plex_settings" "this" {
  ip      = local.seerr_plex.ip
  port    = local.seerr_plex.port
  use_ssl = local.seerr_plex.use_ssl

  lifecycle {
    precondition {
      condition     = trimspace(local.seerr_plex.ip) != ""
      error_message = "Unable to determine the Plex IP. Set plex_ip explicitly or ensure terraform/netbox outputs.host_primary_ipv4 contains the plex host."
    }
  }
}

resource "seerr_tautulli_settings" "this" {
  hostname     = local.seerr_tautulli.hostname
  port         = local.seerr_tautulli.port
  api_key      = local.seerr_tautulli.api_key
  use_ssl      = local.seerr_tautulli.use_ssl
  url_base     = local.seerr_tautulli.url_base
  external_url = local.seerr_tautulli.external_url
}

resource "seerr_notification_gotify" "this" {
  enabled            = local.seerr_gotify.enabled
  embed_poster       = local.seerr_gotify.embed_poster
  notification_types = local.seerr_gotify.notification_types

  gotify = {
    url   = local.seerr_gotify.url
    token = local.seerr_gotify.token
  }
}

resource "seerr_radarr_server" "this" {
  for_each = {
    for server in local.seerr_radarr_servers : tostring(server.id) => server
  }

  name                   = each.value.name
  hostname               = each.value.hostname
  port                   = each.value.port
  api_key                = each.value.api_key
  use_ssl                = each.value.use_ssl
  base_url               = each.value.base_url
  quality_profile_id     = each.value.quality_profile_id
  quality_profile_name   = each.value.quality_profile_name
  active_directory       = each.value.active_directory
  minimum_availability   = each.value.minimum_availability
  is_4k                  = each.value.is_4k
  is_default             = each.value.is_default
  sync_enabled           = each.value.sync_enabled
  enable_scan            = each.value.enable_scan
  prevent_search         = each.value.prevent_search
  tag_requests_with_user = each.value.tag_requests_with_user
  tags                   = each.value.tags
}

resource "seerr_sonarr_server" "this" {
  for_each = {
    for server in local.seerr_sonarr_servers : tostring(server.id) => server
  }

  name                   = each.value.name
  hostname               = each.value.hostname
  port                   = each.value.port
  api_key                = each.value.api_key
  use_ssl                = each.value.use_ssl
  base_url               = each.value.base_url
  quality_profile_id     = each.value.quality_profile_id
  quality_profile_name   = each.value.quality_profile_name
  active_directory       = each.value.active_directory
  active_anime_directory = each.value.active_anime_directory
  is_4k                  = each.value.is_4k
  is_default             = each.value.is_default
  sync_enabled           = each.value.sync_enabled
  enable_scan            = each.value.enable_scan
  prevent_search         = each.value.prevent_search
  tag_requests_with_user = each.value.tag_requests_with_user
  enable_season_folders  = each.value.enable_season_folders
  tags                   = each.value.tags
  anime_tags             = each.value.anime_tags
}
