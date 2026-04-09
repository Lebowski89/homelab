terraform {
  required_version = "1.11.5"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "0.101.1"
    }
  }
}