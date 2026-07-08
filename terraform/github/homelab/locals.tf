locals {
  workflow_token_permissions = {
    owner       = var.github_owner
    repository  = github_repository.homelab.name
    permissions = var.workflow_token_default_permissions
    approve_prs = false
  }

  workflow_token_permissions_payload = jsonencode({
    default_workflow_permissions     = local.workflow_token_permissions.permissions
    can_approve_pull_request_reviews = local.workflow_token_permissions.approve_prs
  })
}
