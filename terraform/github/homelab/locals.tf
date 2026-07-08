locals {
  workflow_token_permissions = {
    owner       = var.github_owner
    repository  = github_repository.homelab.name
    permissions = "write"
    approve_prs = false
  }
}
