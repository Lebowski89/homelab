locals {
  qemu_guest_agent_snippet_enabled = (
    var.qemu_agent_enabled &&
    var.qemu_guest_agent_bootstrap_enabled &&
    var.vendor_data_file_id == null
  )

  qemu_guest_agent_snippet_file_name = (
    var.qemu_guest_agent_snippet_file_name != null
    ? var.qemu_guest_agent_snippet_file_name
    : "${var.name}-qemu-guest-agent.yaml"
  )

  qemu_guest_agent_snippet_file_id = (
    "${var.snippet_datastore_id}:snippets/${local.qemu_guest_agent_snippet_file_name}"
  )
}

resource "proxmox_virtual_environment_file" "qemu_guest_agent_cloud_init" {
  count = local.qemu_guest_agent_snippet_enabled ? 1 : 0

  content_type = "snippets"
  datastore_id = var.snippet_datastore_id
  node_name    = var.node_name

  source_raw {
    file_name = local.qemu_guest_agent_snippet_file_name

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

resource "proxmox_virtual_environment_vm" "this" {
  name        = var.name
  description = var.description
  vm_id       = var.vm_id
  node_name   = var.node_name

  tags       = var.tags
  on_boot    = var.on_boot
  protection = var.protection
  started    = var.started

  depends_on = [
    proxmox_virtual_environment_file.qemu_guest_agent_cloud_init,
  ]

  clone {
    vm_id   = var.clone_template_vm_id
    full    = true
    retries = var.clone_retries
  }

  agent {
    enabled = var.qemu_agent_enabled
  }

  cpu {
    cores   = var.cpu_cores
    sockets = var.cpu_sockets
    type    = var.cpu_type
  }

  memory {
    dedicated = var.memory_mb
    floating  = var.ballooning_memory_mb
  }

  serial_device {
    device = "socket"
  }

  disk {
    datastore_id = var.datastore_id
    interface    = "scsi0"
    size         = var.disk_size_gb
    iothread     = true
  }

  initialization {
    datastore_id = var.datastore_id
    vendor_data_file_id = (
      var.vendor_data_file_id != null
      ? var.vendor_data_file_id
      : (
        local.qemu_guest_agent_snippet_enabled
        ? local.qemu_guest_agent_snippet_file_id
        : null
      )
    )

    ip_config {
      ipv4 {
        address = var.ipv4_address
        gateway = var.ipv4_gateway
      }
    }

    dns {
      domain  = var.dns_domain
      servers = var.dns_servers
    }

    user_account {
      username = var.cloud_init_user
      keys     = var.ssh_public_keys
    }
  }

  network_device {
    bridge  = var.network_bridge
    vlan_id = var.vlan_id
  }

  operating_system {
    type = "l26"
  }

  boot_order    = ["scsi0"]
  scsi_hardware = "virtio-scsi-single"

  lifecycle {
    precondition {
      condition     = can(cidrnetmask(var.ipv4_address))
      error_message = "ipv4_address must be a valid IPv4 CIDR."
    }

    precondition {
      condition     = can(cidrnetmask("${var.ipv4_gateway}/32"))
      error_message = "ipv4_gateway must be a valid IPv4 address."
    }

    precondition {
      condition     = length(var.dns_servers) > 0
      error_message = "At least one DNS server must be supplied to the Ubuntu VM module."
    }

    precondition {
      condition     = length(var.ssh_public_keys) > 0
      error_message = "At least one SSH public key must be supplied to the Ubuntu VM module."
    }

    precondition {
      condition     = var.ballooning_memory_mb <= var.memory_mb
      error_message = "ballooning_memory_mb must not exceed memory_mb."
    }
  }
}
