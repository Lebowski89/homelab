resource "proxmox_download_file" "rocky_cloud_image" {
  # Keep the QCOW2 payload but use .img for compatibility with PVE ISO storage.
  content_type       = "iso"
  datastore_id       = var.cloud_image_datastore
  node_name          = var.target_node
  file_name          = var.cloud_image_file_name
  url                = var.cloud_image_url
  checksum           = var.cloud_image_checksum
  checksum_algorithm = "sha256"
  overwrite          = false
}

resource "proxmox_virtual_environment_vm" "rocky_template" {
  name        = var.template_name
  description = "Rocky Linux 10 cloud-init template managed by OpenTofu"
  vm_id       = var.template_vmid
  node_name   = var.target_node
  tags        = ["terraform", "template", "rocky", "cloud-init"]

  template = true
  on_boot  = false
  started  = false

  bios    = "ovmf"
  machine = "q35"

  efi_disk {
    datastore_id      = var.vm_storage
    file_format       = "raw"
    type              = "4m"
    pre_enrolled_keys = false
  }

  agent {
    # Clones must install/start the guest agent before relying on integration.
    enabled = false
  }

  cpu {
    cores   = var.template_cores
    sockets = 1
    type    = "host"
  }

  memory {
    dedicated = var.template_memory
    floating  = 0
  }

  serial_device {
    device = "socket"
  }

  operating_system {
    type = "l26"
  }

  initialization {
    datastore_id = var.vm_storage

    user_account {
      username = var.template_ci_user
      keys     = [trimspace(file(pathexpand(var.ssh_public_key_path)))]
    }
  }

  network_device {
    bridge = var.template_bridge
  }

  # Match the pinned image's virtual size; the provider defaults to 8 GiB.
  disk {
    datastore_id = var.vm_storage
    interface    = "scsi0"
    file_id      = proxmox_download_file.rocky_cloud_image.id
    size         = 10
    iothread     = true
  }

  boot_order    = ["scsi0"]
  scsi_hardware = "virtio-scsi-single"
}
