terraform {
  required_version = "~> 1.11.0"

  required_providers {
    uptimekuma = {
      source  = "breml/uptimekuma"
      version = "0.3.1"
    }
  }
}
