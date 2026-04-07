locals {
  vm_nameservers = [for ns in split(" ", trimspace(var.vm_nameserver)) : ns if ns != ""]
}

resource "proxmox_virtual_environment_file" "tailscale_cloudinit" {
  content_type = "snippets"
  datastore_id = "local"
  node_name    = var.target_node

  source_raw {
    file_name = "tailscale-bootstrap.yaml"
    data      = <<-EOF
      #cloud-config
      package_update: true
      package_upgrade: false

      runcmd:
        - curl -fsSL https://tailscale.com/install.sh | sh
        - systemctl enable --now tailscaled
        - tailscale up --auth-key='${var.tailscale_auth_key}' --hostname="$(hostname)" --ssh
    EOF
  }
}

resource "proxmox_virtual_environment_vm" "postgres" {
  for_each = var.postgres_vms

  name        = each.key
  vm_id       = each.value.vmid
  description = "Postgres HA node ${each.key} managed by Terraform"
  node_name   = var.target_node

  clone {
    vm_id   = var.clone_template_vmid
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
    vendor_data_file_id = proxmox_virtual_environment_file.tailscale_cloudinit.id


    ip_config {
      ipv4 {
        address = "${each.value.ip}/${var.vm_cidr}"
        gateway = var.vm_gateway
      }
    }

    dns {
      domain  = var.vm_searchdomain
      servers = local.vm_nameservers
    }

    user_account {
      username = try(each.value.ci_user, var.ci_user)
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