variable "github_token" {
  type      = string
  sensitive = true
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