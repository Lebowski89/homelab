output "service_a_record_names" {
  value = sort(keys(cloudflare_dns_record.service_a))
}

output "service_a_record_fqdns" {
  value = sort([
    for record in cloudflare_dns_record.service_a : record.name
  ])
}

output "service_a_record_ids" {
  value = {
    for name, record in cloudflare_dns_record.service_a : name => record.id
  }
}

output "service_a_public_ipv4" {
  value = var.public_ipv4
}

output "mx_records" {
  value = [
    {
      name     = cloudflare_dns_record.mx_fwd1.name
      content  = cloudflare_dns_record.mx_fwd1.content
      priority = cloudflare_dns_record.mx_fwd1.priority
      ttl      = cloudflare_dns_record.mx_fwd1.ttl
    },
    {
      name     = cloudflare_dns_record.mx_fwd2.name
      content  = cloudflare_dns_record.mx_fwd2.content
      priority = cloudflare_dns_record.mx_fwd2.priority
      ttl      = cloudflare_dns_record.mx_fwd2.ttl
    }
  ]
}

output "txt_record_names" {
  value = {
    spf   = cloudflare_dns_record.txt_spf.name
    dkim  = cloudflare_dns_record.txt_dkim_default.name
    dmarc = cloudflare_dns_record.txt_dmarc.name
  }
}