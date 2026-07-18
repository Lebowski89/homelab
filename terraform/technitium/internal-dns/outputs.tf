output "zone_name" {
  value = technitium_zone.internal.name
}

output "service_fqdns" {
  value = sort([
    for name in keys(technitium_record.service_a) : "${name}.${local.zone_name}"
  ])
}

output "traefik_ipv4" {
  value = local.traefik_ipv4
}

output "technitium_server" {
  value = local.technitium_server
}
