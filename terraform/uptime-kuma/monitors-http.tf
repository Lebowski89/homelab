resource "uptimekuma_monitor_http" "this" {
  for_each = local.http_monitors

  name                  = each.value.name
  url                   = each.value.url
  method                = each.value.method
  accepted_status_codes = each.value.accepted_status_codes
  ignore_tls            = each.value.ignore_tls
  expiry_notification   = each.value.expiry_notification
  max_redirects         = each.value.max_redirects
  timeout               = local.default_monitor.timeout
  description           = each.value.description
  interval              = local.default_monitor.interval
  max_retries           = local.default_monitor.max_retries
  retry_interval        = local.default_monitor.retry_interval
  resend_interval       = local.default_monitor.resend_interval
  active                = local.default_monitor.active
  upside_down           = local.default_monitor.upside_down
  parent = coalesce(
    try(uptimekuma_monitor_group.root[each.value.group].id, null),
    try(uptimekuma_monitor_group.child[each.value.group].id, null)
  )
  notification_ids = local.default_notification_ids

  tags = [
    for tag_key in each.value.tag_keys : {
      tag_id = uptimekuma_tag.this[tag_key].id
    }
  ]
}
