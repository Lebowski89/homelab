resource "uptimekuma_notification_gotify" "gotify" {
  count = var.enable_gotify_notification ? 1 : 0

  name              = "Gotify"
  server_url        = var.gotify_server_url
  application_token = var.gotify_application_token
  priority          = var.gotify_priority
  is_active         = true
  is_default        = false
  apply_existing    = false
}

locals {
  default_notification_ids = var.enable_gotify_notification ? [uptimekuma_notification_gotify.gotify[0].id] : []
}
