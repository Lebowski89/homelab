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
  type        = string
  description = "GitHub owner/user/org, e.g. Lebowski89."
  default     = "Lebowski89"
}

variable "repository_name" {
  type        = string
  description = "Repository to manage."
  default     = "homelab"
}

variable "repository_description" {
  type        = string
  description = "Repository description. Adjust before importing/applying if GitHub currently differs."
  default     = "Homelab infrastructure as code"
}

variable "repository_visibility" {
  type        = string
  description = "public or private. Must match your existing repo unless you intend to change it."
  default     = "public"

  validation {
    condition     = contains(["public", "private"], var.repository_visibility)
    error_message = "repository_visibility must be public or private."
  }
}

variable "default_branch" {
  type        = string
  description = "Default branch protected by the ruleset."
  default     = "main"
}

variable "has_issues" {
  type    = bool
  default = true
}

variable "has_projects" {
  type    = bool
  default = true
}

variable "has_wiki" {
  type    = bool
  default = false
}

variable "has_discussions" {
  type    = bool
  default = false
}

variable "allow_forking" {
  type        = bool
  description = "Public repos can be forked regardless; this mainly matters for private/org repos."
  default     = true
}

variable "set_workflow_token_permissions" {
  type        = bool
  description = "Use a Terraform local-exec REST call to set Actions GITHUB_TOKEN defaults to read/write. Official provider support is limited here."
  default     = true
}
