resource "netbox_site" "homelab" {
  name   = var.site.name
  slug   = var.site.slug
  status = var.site.status
}

resource "netbox_device_role" "homelab" {
  name  = var.device_role.name
  slug  = var.device_role.slug
  color = var.device_role.color_hex
}

resource "netbox_manufacturer" "homelab" {
  name = "Homelab"
  slug = "homelab"
}

resource "netbox_device_type" "homelab" {
  model           = var.device_type.model
  slug            = var.device_type.slug
  manufacturer_id = netbox_manufacturer.homelab.id
}

resource "netbox_prefix" "this" {
  for_each = var.prefixes

  prefix      = each.value.prefix
  status      = each.value.status
  site_id     = netbox_site.homelab.id
  description = try(each.value.description, null)
  is_pool     = each.value.is_pool
}

resource "netbox_device" "hosts" {
  for_each = var.hosts

  name           = each.key
  site_id        = netbox_site.homelab.id
  device_role_id = netbox_device_role.homelab.id
  device_type_id = netbox_device_type.homelab.id
  status         = each.value.status
  description    = try(each.value.description, null)
}

resource "netbox_interface" "mgmt" {
  for_each = var.hosts

  name      = "mgmt0"
  device_id = netbox_device.hosts[each.key].id
  type      = "1000base-t"
  enabled   = true
}

resource "netbox_ip_address" "mgmt" {
  for_each = var.hosts

  ip_address   = each.value.mgmt_ip
  status       = "active"
  assigned_object_type = "dcim.interface"
  assigned_object_id   = netbox_interface.mgmt[each.key].id
  dns_name     = try(each.value.dns_name, null)
  description  = "Management IP for ${each.key}"
}

resource "netbox_device_primary_ip" "hosts" {
  for_each = var.hosts

  device_id = netbox_device.hosts[each.key].id
  ip4_id    = netbox_ip_address.mgmt[each.key].id
}