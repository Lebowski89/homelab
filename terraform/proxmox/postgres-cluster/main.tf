resource "proxmox_vm_qemu" "postgres" {
  for_each = var.postgres_vms

  name        = each.key
  vmid        = each.value.vmid
  description = "Postgres HA node ${each.key} managed by Terraform"
  target_node = var.target_node
  clone       = var.clone_template

  agent              = 1
  start_at_node_boot = try(each.value.onboot, true)
  os_type            = "cloud-init"

  tags = var.default_tags

  cpu {
    cores   = each.value.cores
    sockets = each.value.sockets
    type    = "host"
  }

  memory   = each.value.memory
  scsihw   = "virtio-scsi-single"
  boot     = "order=scsi0"
  bootdisk = "scsi0"

  network {
    id     = 0
    model  = "virtio"
    bridge = var.vm_bridge
    tag    = try(each.value.vlan_tag, null)
  }

  disks {
    ide {
      ide2 {
        cloudinit {
          storage = var.vm_storage
        }
      }
    }

    scsi {
      scsi0 {
        disk {
          storage  = var.vm_storage
          size     = "${each.value.disk_size_gb}G"
          iothread = true
          discard  = true
          backup   = true
        }
      }
    }
  }

  ciuser                 = try(each.value.ci_user, var.ci_user)
  sshkeys                = file(var.ssh_public_key_path)
  nameserver             = var.vm_nameserver
  searchdomain           = var.vm_searchdomain
  ipconfig0              = "ip=${each.value.ip}/${var.vm_cidr},gw=${var.vm_gateway}"
  define_connection_info = false
}