resource "uptimekuma_monitor_dns" "this" {
  for_each = local.dns_monitors

  name               = each.value.name
  hostname           = each.value.hostname
  dns_resolve_server = each.value.dns_resolve_server
  dns_resolve_type   = each.value.dns_resolve_type
  port               = each.value.port
  description        = each.value.description
  interval           = 300
  max_retries        = local.default_monitor.max_retries
  retry_interval     = local.default_monitor.retry_interval
  resend_interval    = local.default_monitor.resend_interval
  active             = local.default_monitor.active
  upside_down        = local.default_monitor.upside_down
  parent = coalesce(
    try(uptimekuma_monitor_group.root[each.value.group].id, null),
    try(uptimekuma_monitor_group.child[each.value.group].id, null)
  )
  notification_ids = local.default_notification_ids

  tags = [
    for tag_key in each.value.tag_keys : {
      tag_id = uptimekuma_tag.this[tag_key].id
      value  = ""
    }
  ]
}
