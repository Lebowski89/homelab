resource "proxmox_virtual_environment_vm" "unraid" {
  name      = var.unraid_name
  vm_id     = var.unraid_vmid
  node_name = var.target_node

  protection    = true
  boot_order    = var.unraid_boot_order
  bios          = var.unraid_bios
  machine       = var.unraid_machine
  scsi_hardware = var.unraid_scsihw
  kvm_arguments = var.unraid_kvm_arguments

  agent {
    enabled = false
  }

  cpu {
    cores   = var.unraid_cores
    sockets = var.unraid_sockets
    type    = "host"
    flags   = var.unraid_cpu_flags
  }

  memory {
    dedicated = var.unraid_memory
    floating  = 0
  }

  operating_system {
    type = var.unraid_qemu_os
  }

  hostpci {
    device  = "hostpci0"
    mapping = var.unraid_cache_mapping
  }

  hostpci {
    device  = "hostpci1"
    mapping = var.unraid_hba_mapping
  }

  hostpci {
    device  = "hostpci2"
    mapping = var.unraid_nic_mapping
  }

  usb {
    host = var.unraid_boot_mapping
  }

  smbios {
    uuid = var.unraid_uuid
  }

  vga {
    type = var.unraid_vga_type
  }

  lifecycle {
    prevent_destroy = true

    ignore_changes = [
      agent,
      disk,
      efi_disk,
      tpm_state,
      usb,
      hostpci,
      smbios,
      vga,
      keyboard_layout,
      tags,
      kvm_arguments,
    ]
  }
}