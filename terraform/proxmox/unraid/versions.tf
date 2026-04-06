terraform {
  required_version = "1.14.8"

  required_providers {
    proxmox = {
      source  = "Telmate/proxmox"
      version = "3.0.2-rc07"
    }
  }
}