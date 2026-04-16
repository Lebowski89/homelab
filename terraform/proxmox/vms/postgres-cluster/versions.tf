terraform {
  required_version = "1.11.6"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "0.102.0"
    }
  }
}
