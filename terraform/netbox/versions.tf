terraform {
  required_version = "~> 1.11.0"

  required_providers {
    netbox = {
      source  = "e-breuninger/netbox"
      version = "5.5.0"
    }
  }
}