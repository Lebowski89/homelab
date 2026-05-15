<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | ~> 1.11.0 |
| <a name="requirement_github"></a> [github](#requirement\_github) | 6.12.1 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_github"></a> [github](#provider\_github) | 6.12.1 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [github_repository.blog](https://registry.terraform.io/providers/integrations/github/6.12.1/docs/resources/repository) | resource |
| [github_repository_pages.blog](https://registry.terraform.io/providers/integrations/github/6.12.1/docs/resources/repository_pages) | resource |
| [github_repository_vulnerability_alerts.blog](https://registry.terraform.io/providers/integrations/github/6.12.1/docs/resources/repository_vulnerability_alerts) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_default_branch"></a> [default\_branch](#input\_default\_branch) | n/a | `string` | `"main"` | no |
| <a name="input_github_owner"></a> [github\_owner](#input\_github\_owner) | n/a | `string` | n/a | yes |
| <a name="input_github_token"></a> [github\_token](#input\_github\_token) | n/a | `string` | n/a | yes |
| <a name="input_repository_description"></a> [repository\_description](#input\_repository\_description) | n/a | `string` | `"Hugo blog"` | no |
| <a name="input_repository_name"></a> [repository\_name](#input\_repository\_name) | n/a | `string` | `"blog"` | no |
| <a name="input_visibility"></a> [visibility](#input\_visibility) | n/a | `string` | `"public"` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_repository_full_name"></a> [repository\_full\_name](#output\_repository\_full\_name) | n/a |
| <a name="output_repository_http_clone_url"></a> [repository\_http\_clone\_url](#output\_repository\_http\_clone\_url) | n/a |
| <a name="output_repository_name"></a> [repository\_name](#output\_repository\_name) | n/a |
| <a name="output_repository_ssh_clone_url"></a> [repository\_ssh\_clone\_url](#output\_repository\_ssh\_clone\_url) | n/a |
<!-- END_TF_DOCS -->