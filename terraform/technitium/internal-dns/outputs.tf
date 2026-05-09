output "zone_name" {
  value = technitium_zone.internal.name
}

output "service_fqdns" {
  value = sort([
    for name in keys(technitium_record.service_a) : "${name}.${var.zone_name}"
  ])
}

output "traefik_ipv4" {
  value = var.traefik_ipv4
}
