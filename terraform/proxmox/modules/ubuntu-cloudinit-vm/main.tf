resource "proxmox_virtual_environment_vm" "this" {
  name        = var.name
  description = var.description
  vm_id       = var.vm_id
  node_name   = var.node_name

  tags       = var.tags
  on_boot    = var.on_boot
  protection = var.protection
  started    = var.started

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
    datastore_id        = var.datastore_id
    vendor_data_file_id = var.vendor_data_file_id

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
