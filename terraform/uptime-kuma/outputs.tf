output "http_monitor_ids" {
  description = "HTTP monitor IDs keyed by monitor key."
  value       = { for key, monitor in uptimekuma_monitor_http.this : key => monitor.id }
}

output "ping_monitor_ids" {
  description = "Ping monitor IDs keyed by monitor key."
  value       = { for key, monitor in uptimekuma_monitor_ping.this : key => monitor.id }
}

output "tcp_monitor_ids" {
  description = "TCP monitor IDs keyed by monitor key."
  value       = { for key, monitor in uptimekuma_monitor_tcp_port.this : key => monitor.id }
}

output "dns_monitor_ids" {
  description = "DNS monitor IDs keyed by monitor key."
  value       = { for key, monitor in uptimekuma_monitor_dns.this : key => monitor.id }
}

output "tag_ids" {
  description = "Uptime Kuma tag IDs."
  value       = { for key, tag in uptimekuma_tag.this : key => tag.id }
}

output "group_ids" {
  description = "Uptime Kuma monitor group IDs."
  value       = { for key, group in uptimekuma_monitor_group.this : key => group.id }
}
