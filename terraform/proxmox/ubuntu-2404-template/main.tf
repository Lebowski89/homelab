resource "proxmox_download_file" "ubuntu_cloud_image" {
  content_type = "iso"
  datastore_id = var.cloud_image_datastore
  node_name    = var.cloud_image_node_name
  file_name    = var.cloud_image_file_name
  url          = var.cloud_image_url
  overwrite    = false
}

resource "proxmox_virtual_environment_vm" "ubuntu_template" {
  name        = var.template_name
  description = "Ubuntu 24.04 cloud-init template managed by Terraform"
  vm_id       = var.template_vmid
  node_name   = var.target_node
  tags        = ["terraform", "template", "ubuntu", "cloud-init"]

  template = true
  on_boot  = false
  started  = false

  agent {
    enabled = true
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

  disk {
    datastore_id = var.vm_storage
    interface    = "scsi0"
    file_id      = proxmox_download_file.ubuntu_cloud_image.id
    iothread     = true
  }

  boot_order    = ["scsi0"]
  scsi_hardware = "virtio-scsi-single"
}