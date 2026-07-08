output "repository_name" {
  value = github_repository.homelab.name
}

output "repository_full_name" {
  value = github_repository.homelab.full_name
}

output "main_ruleset_id" {
  value = github_repository_ruleset.main_clean_history.ruleset_id
}
