locals {
  device_type_interfaces_flat = {
    for interface in flatten([
      for device_type_key, interfaces in local.device_type_interfaces : [
        for interface in interfaces : merge(interface, {
          key             = "${device_type_key}.${interface.name}"
          device_type_key = device_type_key
        })
      ]
    ]) : interface.key => interface
  }
}

resource "netbox_site" "this" {
  for_each = local.sites

  name   = each.value.name
  slug   = each.value.slug
  status = try(each.value.status, "active")
}

resource "netbox_manufacturer" "this" {
  for_each = local.manufacturers

  name = each.value.name
  slug = try(each.value.slug, each.key)
}

resource "netbox_device_role" "this" {
  for_each = local.device_roles

  name      = each.value.name
  slug      = try(each.value.slug, each.key)
  color_hex = try(each.value.color_hex, "9e9e9e")
}

resource "netbox_device_type" "this" {
  for_each = local.device_types

  model           = each.value.model
  slug            = try(each.value.slug, each.key)
  manufacturer_id = netbox_manufacturer.this[try(each.value.manufacturer_key, "homelab")].id
  part_number     = try(each.value.part_number, null)
  is_full_depth   = try(each.value.is_full_depth, null)
  u_height        = try(each.value.u_height, null)
}

resource "netbox_interface_template" "this" {
  for_each = local.device_type_interfaces_flat

  device_type_id = netbox_device_type.this[each.value.device_type_key].id
  name           = each.value.name
  label          = try(each.value.label, null)
  type           = each.value.type
}

resource "netbox_tag" "this" {
  for_each = local.netbox_tags

  name        = each.value.name
  slug        = try(each.value.slug, each.key)
  color_hex   = try(each.value.color_hex, "9e9e9e")
  description = try(each.value.description, null)
}

resource "netbox_custom_field" "device" {
  for_each = local.device_custom_fields

  name          = each.value.name
  label         = try(each.value.label, null)
  type          = try(each.value.type, "text")
  content_types = ["dcim.device"]
  weight        = try(each.value.weight, 100)
  description   = try(each.value.description, null)
  group_name    = try(each.value.group_name, null)
  required      = try(each.value.required, false)

  validation_regex   = try(each.value.validation_regex, null)
  validation_minimum = try(each.value.validation_minimum, null)
  validation_maximum = try(each.value.validation_maximum, null)
}

resource "netbox_prefix" "this" {
  for_each = local.prefixes

  prefix        = each.value.prefix
  status        = try(each.value.status, "active")
  description   = try(each.value.description, null)
  is_pool       = try(each.value.is_pool, false)
  mark_utilized = try(each.value.mark_utilized, false)
  site_id       = netbox_site.this[try(each.value.site_key, "homelab")].id
}

resource "netbox_device" "hosts" {
  for_each = local.hosts

  name           = each.key
  site_id        = netbox_site.this[try(each.value.site_key, "homelab")].id
  role_id        = netbox_device_role.this[try(each.value.role_key, "server")].id
  device_type_id = netbox_device_type.this[try(each.value.device_type_key, "generic_host")].id
  status         = try(each.value.status, "active")
  description    = try(each.value.description, null)
  tags           = [for tag_key in try(each.value.tags, []) : try(local.netbox_tags[tag_key].name, tag_key)]
  custom_fields  = try(each.value.custom_fields, null)

  # Ensures NetBox device-type component templates, tags, and custom fields
  # exist before devices are instantiated from those device types.
  depends_on = [
    netbox_interface_template.this,
    netbox_tag.this,
    netbox_custom_field.device,
  ]
}

resource "netbox_device_interface" "mgmt" {
  for_each = local.hosts

  name      = try(each.value.interface_name, "mgmt0")
  device_id = netbox_device.hosts[each.key].id
  type      = try(each.value.interface_type, "1000base-t")
  enabled   = true
}

resource "netbox_ip_address" "mgmt" {
  for_each = local.hosts

  ip_address          = each.value.mgmt_ip
  status              = "active"
  device_interface_id = netbox_device_interface.mgmt[each.key].id
  dns_name            = try(each.value.dns_name, null)
  description         = try(each.value.description, "Management IP for ${each.key}")
}

resource "netbox_device_primary_ip" "hosts" {
  for_each = local.hosts

  device_id          = netbox_device.hosts[each.key].id
  ip_address_id      = netbox_ip_address.mgmt[each.key].id
  ip_address_version = 4
}

resource "netbox_ip_address" "reserved" {
  for_each = local.reserved_ips

  ip_address  = each.value.ip_address
  status      = try(each.value.status, "active")
  dns_name    = try(each.value.dns_name, null)
  description = try(each.value.description, null)
}
