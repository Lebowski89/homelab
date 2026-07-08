variable "github_token" {
  description = "GitHub token used by the provider and REST API calls."
  type        = string
  sensitive   = true

  validation {
    condition     = length(trimspace(var.github_token)) > 0
    error_message = "github_token must not be empty."
  }
}

variable "github_owner" {
  type = string
}

variable "repository_name" {
  type    = string
  default = "blog"
}

variable "repository_description" {
  type    = string
  default = "Hugo blog"
}

variable "default_branch" {
  type    = string
  default = "main"
}

variable "visibility" {
  type    = string
  default = "public"
}