resource "github_repository" "homelab" {
  #checkov:skip=CKV_GIT_1:Homelab repo is intentionally public unless repository_visibility is changed.
  #checkov:skip=CKV_GIT_5:Personal homelab repo; zero required approvals keeps solo-maintainer flow practical.
  #checkov:skip=CKV_GIT_6:Signed commits are not currently enforced for this personal repo.

  name        = var.repository_name
  description = var.repository_description
  visibility  = var.repository_visibility

  has_issues      = var.has_issues
  has_projects    = var.has_projects
  has_wiki        = var.has_wiki
  has_discussions = var.has_discussions

  allow_merge_commit  = false
  allow_rebase_merge  = false
  allow_squash_merge  = true
  allow_auto_merge    = false
  allow_update_branch = true

  delete_branch_on_merge = true

  squash_merge_commit_title   = "PR_TITLE"
  squash_merge_commit_message = "BLANK"

  allow_forking = var.allow_forking
  auto_init     = false

  archive_on_destroy = true

  lifecycle {
    prevent_destroy = true

    ignore_changes = [
      homepage_url,
      topics,
      merge_commit_message,
      merge_commit_title,
    ]
  }
}

resource "github_repository_vulnerability_alerts" "homelab" {
  repository = github_repository.homelab.name
}

resource "github_repository_ruleset" "main_clean_history" {
  name        = "main clean history"
  repository  = github_repository.homelab.name
  target      = "branch"
  enforcement = "active"

  conditions {
    ref_name {
      include = ["~DEFAULT_BRANCH"]
      exclude = []
    }
  }

  rules {
    deletion         = true
    non_fast_forward = true

    required_linear_history = true

    pull_request {
      allowed_merge_methods             = ["squash"]
      required_approving_review_count   = 0
      required_review_thread_resolution = true
      dismiss_stale_reviews_on_push     = false
      require_code_owner_review         = false
      require_last_push_approval        = false
    }
  }
}

resource "github_actions_repository_permissions" "homelab" {
  repository      = github_repository.homelab.name
  enabled         = true
  allowed_actions = "all"

  sha_pinning_required = false
}

resource "terraform_data" "workflow_token_permissions" {
  count = var.set_workflow_token_permissions ? 1 : 0

  input            = local.workflow_token_permissions
  triggers_replace = local.workflow_token_permissions

  depends_on = [
    github_actions_repository_permissions.homelab,
  ]

  provisioner "local-exec" {
    interpreter = ["/usr/bin/env", "bash", "-c"]

    environment = {
      GITHUB_TOKEN = var.github_token
      GITHUB_OWNER = var.github_owner
      GITHUB_REPO  = github_repository.homelab.name
    }

    command = <<-EOT
      set -euo pipefail

      curl -fsSL \
        --connect-timeout 10 \
        --max-time 60 \
        -X PUT \
        -H "Accept: application/vnd.github+json" \
        -H "Authorization: Bearer $${GITHUB_TOKEN}" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "https://api.github.com/repos/$${GITHUB_OWNER}/$${GITHUB_REPO}/actions/permissions/workflow" \
        -d '${local.workflow_token_permissions_payload}'
    EOT
  }
}
