locals {
  tags = {
    arrs           = { name = "arrs", color = "#7c3aed" }
    automation     = { name = "automation", color = "#ea4b71" }
    auth           = { name = "auth", color = "#7c3aed" }
    critical       = { name = "critical", color = "#dc2626" }
    direct         = { name = "direct", color = "#6b7280" }
    dns            = { name = "dns", color = "#9333ea" }
    finance        = { name = "finance", color = "#f97316" }
    gaming         = { name = "gaming", color = "#9333ea" }
    infrastructure = { name = "infrastructure", color = "#2563eb" }
    private        = { name = "private", color = "#64748b" }
    public         = { name = "public", color = "#0284c7" }
    media          = { name = "media", color = "#22c55e" }
    monitoring     = { name = "monitoring", color = "#16a34a" }
    network        = { name = "network", color = "#0ea5e9" }
    networking     = { name = "networking", color = "#0ea5e9" }
    plex           = { name = "plex", color = "#d97706" }
    storage        = { name = "storage", color = "#a855f7" }
    torrents       = { name = "torrents", color = "#ca8a04" }
    traefik        = { name = "traefik", color = "#f97316" }
    usenet         = { name = "usenet", color = "#0284c7" }
    utilities      = { name = "utilities", color = "#4b5563" }
  }
}

resource "uptimekuma_tag" "this" {
  for_each = local.tags

  name  = each.value.name
  color = each.value.color
}
