locals {
  sites = {
    homelab = var.site
  }

  host_role_keys = toset([
    for host in values(var.hosts) : try(host.role_key, "server")
  ])

  host_device_type_keys = toset([
    for host in values(var.hosts) : try(host.device_type_key, "generic_host")
  ])
}

resource "netbox_site" "this" {
  for_each = local.sites

  name   = each.value.name
  slug   = each.value.slug
  status = try(each.value.status, "active")
}

resource "netbox_manufacturer" "this" {
  for_each = var.manufacturers

  name = each.value.name
  slug = try(each.value.slug, each.key)
}

resource "netbox_device_role" "this" {
  for_each = var.device_roles

  name      = each.value.name
  slug      = try(each.value.slug, each.key)
  color_hex = try(each.value.color_hex, "9e9e9e")
}

resource "netbox_device_type" "this" {
  for_each = var.device_types

  model           = each.value.model
  slug            = try(each.value.slug, each.key)
  manufacturer_id = netbox_manufacturer.this[try(each.value.manufacturer_key, "homelab")].id
}

resource "netbox_prefix" "this" {
  for_each = var.prefixes

  prefix        = each.value.prefix
  status        = try(each.value.status, "active")
  description   = try(each.value.description, null)
  is_pool       = try(each.value.is_pool, false)
  mark_utilized = try(each.value.mark_utilized, false)
  site_id       = netbox_site.this[try(each.value.site_key, "homelab")].id
}

resource "netbox_device" "hosts" {
  for_each = var.hosts

  name           = each.key
  site_id        = netbox_site.this[try(each.value.site_key, "homelab")].id
  role_id        = netbox_device_role.this[try(each.value.role_key, "server")].id
  device_type_id = netbox_device_type.this[try(each.value.device_type_key, "generic_host")].id
  status         = try(each.value.status, "active")
  description    = try(each.value.description, null)
}

resource "netbox_device_interface" "mgmt" {
  for_each = var.hosts

  name      = try(each.value.interface_name, "mgmt0")
  device_id = netbox_device.hosts[each.key].id
  type      = try(each.value.interface_type, "1000base-t")
  enabled   = true
}

resource "netbox_ip_address" "mgmt" {
  for_each = var.hosts

  ip_address          = each.value.mgmt_ip
  status              = "active"
  device_interface_id = netbox_device_interface.mgmt[each.key].id
  dns_name            = try(each.value.dns_name, null)
  description         = try(each.value.description, "Management IP for ${each.key}")
}

resource "netbox_device_primary_ip" "hosts" {
  for_each = var.hosts

  device_id          = netbox_device.hosts[each.key].id
  ip_address_id      = netbox_ip_address.mgmt[each.key].id
  ip_address_version = 4
}

resource "netbox_ip_address" "reserved" {
  for_each = var.reserved_ips

  ip_address  = each.value.ip_address
  status      = try(each.value.status, "active")
  dns_name    = try(each.value.dns_name, null)
  description = try(each.value.description, null)
}