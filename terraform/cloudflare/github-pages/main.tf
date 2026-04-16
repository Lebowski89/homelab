locals {
  github_pages_ipv4 = [
    "185.199.108.153",
    "185.199.109.153",
    "185.199.110.153",
    "185.199.111.153",
  ]

  github_pages_ipv6 = [
    "2606:50c0:8000::153",
    "2606:50c0:8001::153",
    "2606:50c0:8002::153",
    "2606:50c0:8003::153",
  ]
}

resource "cloudflare_dns_record" "github_pages_a" {
  for_each = toset(local.github_pages_ipv4)

  zone_id = var.cloudflare_zone_id
  name    = var.apex_name
  type    = "A"
  content = each.value
  ttl     = var.ttl
  proxied = false
}

resource "cloudflare_dns_record" "github_pages_aaaa" {
  for_each = toset(local.github_pages_ipv6)

  zone_id = var.cloudflare_zone_id
  name    = var.apex_name
  type    = "AAAA"
  content = each.value
  ttl     = var.ttl
  proxied = false
}