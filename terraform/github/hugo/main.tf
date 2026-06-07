resource "github_repository" "blog" {
  #checkov:skip=CKV_GIT_1:This Hugo blog repository is intentionally public.
  name        = var.repository_name
  description = var.repository_description
  visibility  = var.visibility

  has_issues   = true
  has_projects = true
  has_wiki     = true

  allow_merge_commit = false
  allow_rebase_merge = false
  allow_squash_merge = true

  delete_branch_on_merge = false
  auto_init              = false

  lifecycle {
    prevent_destroy = true

    ignore_changes = [
      merge_commit_message,
      merge_commit_title,
      squash_merge_commit_message,
      squash_merge_commit_title,
    ]
  }
}

resource "github_repository_pages" "blog" {
  repository = github_repository.blog.name

  build_type = "workflow"
  cname      = "drjoyce.blog"
}

resource "github_repository_vulnerability_alerts" "blog" {
  repository = github_repository.blog.name
  enabled    = false
}

resource "github_branch_protection" "blog" {
  #checkov:skip=CKV_GIT_5:This is a personal Hugo blog repository; two approvals are not practical.
  #checkov:skip=CKV_GIT_6:Signed commits are not currently required for this personal Hugo blog repository.
  repository_id = github_repository.blog.node_id
  pattern       = var.default_branch

  enforce_admins         = true
  allows_deletions       = false
  allows_force_pushes    = false
  require_signed_commits = false
}
