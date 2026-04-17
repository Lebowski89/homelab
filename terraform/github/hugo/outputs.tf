output "repository_name" {
  value = github_repository.blog.name
}

output "repository_full_name" {
  value = github_repository.blog.full_name
}

output "repository_ssh_clone_url" {
  value = github_repository.blog.ssh_clone_url
}

output "repository_http_clone_url" {
  value = github_repository.blog.http_clone_url
}