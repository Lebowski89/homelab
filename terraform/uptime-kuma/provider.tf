provider "uptimekuma" {
  endpoint            = local.uptime_kuma_endpoint
  username            = var.uptime_kuma_username
  password            = var.uptime_kuma_password
  timeout             = var.uptime_kuma_timeout
  per_attempt_timeout = var.uptime_kuma_per_attempt_timeout
  max_retries         = var.uptime_kuma_max_retries
}
