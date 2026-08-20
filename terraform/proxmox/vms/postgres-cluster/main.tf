locals {
  netbox_dns_ips       = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.dns_ips, {}) : {}
  netbox_internal_zone = var.enable_netbox_remote_state ? try(data.terraform_remote_state.netbox[0].outputs.internal_zone, "") : ""

  # NetBox takes precedence, while var.dns_ips can provide fallback values
  # when remote state is disabled or incomplete.
  dns_ips = merge(
    var.dns_ips,
    local.netbox_dns_ips,
  )

  dns_vip_nameservers = distinct(compact([
    trimspace(lookup(local.dns_ips, "dns_vip_a", "")),
    trimspace(lookup(local.dns_ips, "dns_vip_b", "")),
  ]))

  configured_vm_nameservers = distinct([
    for nameserver in split(" ", trimspace(var.vm_nameserver)) : trimspace(nameserver)
    if trimspace(nameserver) != ""
  ])

  # Preserve the existing behaviour:
  # - use DNS VIPs while NetBox remote state is enabled;
  # - otherwise use explicitly configured nameservers when supplied;
  # - fall back to var.dns_ips VIPs when no explicit nameservers are supplied.
  use_dns_vips = var.enable_netbox_remote_state || length(local.configured_vm_nameservers) == 0

  vm_nameservers = local.use_dns_vips ? local.dns_vip_nameservers : local.configured_vm_nameservers

  # Prefer the NetBox internal zone when available, but retain the explicit
  # fallback if remote state is disabled or does not contain the output.
  vm_searchdomain_source = trimspace(local.netbox_internal_zone) != "" ? local.netbox_internal_zone : var.vm_searchdomain
  vm_searchdomain        = trim(trimspace(local.vm_searchdomain_source), ".")
}

resource "proxmox_virtual_environment_file" "qemu_guest_agent_cloud_init" {
  content_type = "snippets"
  datastore_id = "local"
  node_name    = var.target_node

  source_raw {
    file_name = "postgres-qemu-guest-agent.yaml"

    data = <<-EOF
      #cloud-config
      package_update: true
      package_upgrade: false

      packages:
        - qemu-guest-agent

      runcmd:
        - systemctl enable --now qemu-guest-agent
    EOF
  }
}

resource "proxmox_virtual_environment_vm" "postgres" {
  for_each = var.postgres_vms

  name        = each.key
  vm_id       = each.value.vmid
  description = "Postgres HA node ${each.key} managed by Terraform"
  node_name   = var.target_node

  lifecycle {
    ignore_changes = [
      initialization,
    ]

    precondition {
      condition = (
        local.use_dns_vips
        ? length(local.dns_vip_nameservers) == 2
        : length(local.configured_vm_nameservers) > 0
      )

      error_message = "Unable to determine valid VM DNS servers. Ensure NetBox outputs.dns_ips contains distinct dns_vip_a and dns_vip_b values, provide them through dns_ips, or set vm_nameserver when NetBox remote state is disabled."
    }
  }

  clone {
    vm_id = coalesce(
      try(each.value.clone_template_vmid, null),
      var.clone_template_vmid,
    )

    full    = true
    retries = 3
  }

  tags = split(";", var.default_tags)

  agent {
    enabled = true
  }

  on_boot       = try(each.value.onboot, true)
  boot_order    = ["scsi0"]
  scsi_hardware = "virtio-scsi-single"

  cpu {
    cores   = each.value.cores
    sockets = each.value.sockets
    type    = "host"
  }

  memory {
    dedicated = each.value.memory
    floating  = 0
  }

  serial_device {
    device = "socket"
  }

  disk {
    datastore_id = var.vm_storage
    interface    = "scsi0"
    size         = each.value.disk_size_gb
    iothread     = true
  }

  initialization {
    datastore_id        = var.vm_storage
    vendor_data_file_id = proxmox_virtual_environment_file.qemu_guest_agent_cloud_init.id

    ip_config {
      ipv4 {
        address = "${each.value.ip}/${var.vm_cidr}"
        gateway = var.vm_gateway
      }
    }

    dns {
      domain  = local.vm_searchdomain
      servers = local.vm_nameservers
    }

    user_account {
      username = coalesce(try(each.value.ci_user, null), var.ci_user, "ubuntu")
      keys     = [trimspace(file(pathexpand(var.ssh_public_key_path)))]
    }
  }

  network_device {
    bridge  = var.vm_bridge
    vlan_id = try(each.value.vlan_tag, null)
  }

  operating_system {
    type = "l26"
  }
}
