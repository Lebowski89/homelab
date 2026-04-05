resource "proxmox_vm_qemu" "unraid" {
  name        = var.unraid_name
  vmid        = var.unraid_vmid
  target_node = var.target_node

  agent                  = 1
  define_connection_info = false
  protection             = true

  balloon = 0
  bios    = var.unraid_bios
  boot    = var.unraid_boot_order
  machine = var.unraid_machine
  memory  = var.unraid_memory
  qemu_os = var.unraid_qemu_os
  scsihw  = var.unraid_scsihw

  cpu {
    cores   = var.unraid_cores
    sockets = var.unraid_sockets
    type    = "host"
  }

  disks {
    sata {
      sata0 {
        passthrough {
          file    = var.unraid_raw_disk_path
          discard = true
        }
      }
    }
  }

  pcis {
    pci0 {
      mapping {
        mapping_id = "Adaptec-UnRaid"
      }
    }

    pci1 {
      mapping {
        mapping_id = "X710-UnRaid"
      }
    }

    pci2 {
      mapping {
        mapping_id = "FireCuda-Swarm"
      }
    }
  }

  smbios {
    uuid = var.unraid_uuid
  }

  lifecycle {
    prevent_destroy = true

    ignore_changes = [
      args,
      full_clone,
      define_connection_info,
      description,
      target_nodes,
      bootdisk,
      startup_shutdown,

      skip_ipv4,
      skip_ipv6,
      additional_wait,
      agent_timeout,
      automatic_reboot,
      automatic_reboot_severity,
      ciupgrade,
      clone_wait,

      disks,
      pcis,
      usbs,
      smbios
    ]
  }
}