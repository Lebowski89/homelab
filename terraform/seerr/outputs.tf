output "radarr_server_ids" {
  value = {
    for k, v in seerr_radarr_server.this : k => v.server_id
  }
}

output "sonarr_server_ids" {
  value = {
    for k, v in seerr_sonarr_server.this : k => v.server_id
  }
}

output "plex_status_code" {
  value = seerr_plex_settings.this.status_code
}

output "tautulli_status_code" {
  value = seerr_tautulli_settings.this.status_code
}
