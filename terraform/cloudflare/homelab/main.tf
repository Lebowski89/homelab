locals {
  ipv4_records = [
    "authelia",
    "opencloud",
    "traefik",
    "vaultwarden",
  ]
}

resource "cloudflare_dns_record" "service_a" {
  for_each = toset(local.ipv4_records)

  zone_id = var.cloudflare_zone_id
  name    = each.value
  type    = "A"
  content = var.public_ipv4
  ttl     = 1
  proxied = false
}

resource "cloudflare_dns_record" "mx_fwd1" {
  zone_id  = var.cloudflare_zone_id
  name     = "@"
  type     = "MX"
  content  = "fwd1.porkbun.com"
  priority = 10
  ttl      = 600
  proxied  = false
}

resource "cloudflare_dns_record" "mx_fwd2" {
  zone_id  = var.cloudflare_zone_id
  name     = "@"
  type     = "MX"
  content  = "fwd2.porkbun.com"
  priority = 20
  ttl      = 600
  proxied  = false
}

resource "cloudflare_dns_record" "txt_spf" {
  zone_id = var.cloudflare_zone_id
  name    = "@"
  type    = "TXT"
  content = "v=spf1 include:_spf.porkbun.com ~all"
  ttl     = 300
  proxied = false
}

resource "cloudflare_dns_record" "txt_dkim_default" {
  zone_id = var.cloudflare_zone_id
  name    = "default._domainkey"
  type    = "TXT"
  content = "v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCnjNC/eT4ktfwB2t+WTDa5QMXB6FAVPgkYB0H+rUAFq0l3uUdzH5lcEq/K+jMulD+LhZ9cAOmmPrC6UZflqnRmKRCrx3MNDqSDH1eyPZiuv/ISwUMf4yOvTHBqOVKOG5Tnb+6df2JLozgHJVoImLZGR/4JR6+U4r1Gb0Fb2Nfq1wIDAQAB"
  ttl     = 300
  proxied = false
}

resource "cloudflare_dns_record" "txt_dmarc" {
  zone_id = var.cloudflare_zone_id
  name    = "_dmarc"
  type    = "TXT"
  content = "v=DMARC1; p=quarantine; rua=mailto:25f8c5e6@mxtoolbox.dmarc-report.com; ruf=mailto:25f8c5e6@forensics.dmarc-report.com; fo=1"
  ttl     = 300
  proxied = false
}