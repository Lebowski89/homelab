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
