output "github_pages_a_records" {
  value = [for r in cloudflare_dns_record.github_pages_a : r.content]
}

output "github_pages_aaaa_records" {
  value = [for r in cloudflare_dns_record.github_pages_aaaa : r.content]
}