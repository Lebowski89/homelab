<!-- BEGIN_TF_DOCS -->


## Resources

| Name | Type |
|------|------|

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_allow_forking"></a> [allow\_forking](#input\_allow\_forking) | Public repos can be forked regardless; this mainly matters for private/org repos. | `bool` | `true` | no |
| <a name="input_default_branch"></a> [default\_branch](#input\_default\_branch) | Default branch protected by the ruleset. | `string` | `"main"` | no |
| <a name="input_github_owner"></a> [github\_owner](#input\_github\_owner) | GitHub owner/user/org, e.g. Lebowski89. | `string` | `"Lebowski89"` | no |
| <a name="input_github_token"></a> [github\_token](#input\_github\_token) | GitHub token used by the provider and REST API calls. | `string` | n/a | yes |
| <a name="input_has_discussions"></a> [has\_discussions](#input\_has\_discussions) | n/a | `bool` | `false` | no |
| <a name="input_has_issues"></a> [has\_issues](#input\_has\_issues) | n/a | `bool` | `true` | no |
| <a name="input_has_projects"></a> [has\_projects](#input\_has\_projects) | n/a | `bool` | `true` | no |
| <a name="input_has_wiki"></a> [has\_wiki](#input\_has\_wiki) | n/a | `bool` | `false` | no |
| <a name="input_repository_description"></a> [repository\_description](#input\_repository\_description) | Repository description. Adjust before importing/applying if GitHub currently differs. | `string` | `"Homelab infrastructure as code"` | no |
| <a name="input_repository_name"></a> [repository\_name](#input\_repository\_name) | Repository to manage. | `string` | `"homelab"` | no |
| <a name="input_repository_visibility"></a> [repository\_visibility](#input\_repository\_visibility) | public or private. Must match your existing repo unless you intend to change it. | `string` | `"public"` | no |
| <a name="input_set_workflow_token_permissions"></a> [set\_workflow\_token\_permissions](#input\_set\_workflow\_token\_permissions) | Use a Terraform local-exec REST call to set Actions GITHUB\_TOKEN defaults to read/write. Official provider support is limited here. | `bool` | `true` | no |
| <a name="input_workflow_token_default_permissions"></a> [workflow\_token\_default\_permissions](#input\_workflow\_token\_default\_permissions) | Default permissions granted to GITHUB\_TOKEN for workflows. | `string` | `"read"` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_main_ruleset_id"></a> [main\_ruleset\_id](#output\_main\_ruleset\_id) | n/a |
| <a name="output_repository_full_name"></a> [repository\_full\_name](#output\_repository\_full\_name) | n/a |
| <a name="output_repository_name"></a> [repository\_name](#output\_repository\_name) | n/a |
<!-- END_TF_DOCS -->