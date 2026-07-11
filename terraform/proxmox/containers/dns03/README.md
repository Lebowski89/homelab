<!-- BEGIN_TF_DOCS -->


## Resources

| Name | Type |
|------|------|

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_container_bridge"></a> [container\_bridge](#input\_container\_bridge) | n/a | `string` | `"vmbr0"` | no |
| <a name="input_container_cores"></a> [container\_cores](#input\_container\_cores) | n/a | `number` | `1` | no |
| <a name="input_container_description"></a> [container\_description](#input\_container\_description) | n/a | `string` | `"Technitium DNS tertiary LXC managed by OpenTofu"` | no |
| <a name="input_container_disk_size"></a> [container\_disk\_size](#input\_container\_disk\_size) | n/a | `number` | `8` | no |
| <a name="input_container_dns_domain"></a> [container\_dns\_domain](#input\_container\_dns\_domain) | n/a | `string` | `"skynet"` | no |
| <a name="input_container_dns_servers"></a> [container\_dns\_servers](#input\_container\_dns\_servers) | n/a | `list(string)` | n/a | yes |
| <a name="input_container_gateway"></a> [container\_gateway](#input\_container\_gateway) | n/a | `string` | n/a | yes |
| <a name="input_container_hostname"></a> [container\_hostname](#input\_container\_hostname) | n/a | `string` | `"dns03"` | no |
| <a name="input_container_ip"></a> [container\_ip](#input\_container\_ip) | n/a | `string` | n/a | yes |
| <a name="input_container_memory"></a> [container\_memory](#input\_container\_memory) | n/a | `number` | `512` | no |
| <a name="input_container_protection"></a> [container\_protection](#input\_container\_protection) | n/a | `bool` | `false` | no |
| <a name="input_container_storage"></a> [container\_storage](#input\_container\_storage) | n/a | `string` | n/a | yes |
| <a name="input_container_swap"></a> [container\_swap](#input\_container\_swap) | n/a | `number` | `512` | no |
| <a name="input_container_vmid"></a> [container\_vmid](#input\_container\_vmid) | n/a | `number` | `253` | no |
| <a name="input_pm_api_token"></a> [pm\_api\_token](#input\_pm\_api\_token) | n/a | `string` | n/a | yes |
| <a name="input_pm_api_url"></a> [pm\_api\_url](#input\_pm\_api\_url) | n/a | `string` | n/a | yes |
| <a name="input_pm_ssh_host"></a> [pm\_ssh\_host](#input\_pm\_ssh\_host) | n/a | `string` | n/a | yes |
| <a name="input_pm_ssh_username"></a> [pm\_ssh\_username](#input\_pm\_ssh\_username) | n/a | `string` | `"root"` | no |
| <a name="input_pm_tls_insecure"></a> [pm\_tls\_insecure](#input\_pm\_tls\_insecure) | n/a | `bool` | `false` | no |
| <a name="input_ssh_public_key_path"></a> [ssh\_public\_key\_path](#input\_ssh\_public\_key\_path) | n/a | `string` | n/a | yes |
| <a name="input_tailscale_auth_key"></a> [tailscale\_auth\_key](#input\_tailscale\_auth\_key) | n/a | `string` | n/a | yes |
| <a name="input_target_node"></a> [target\_node](#input\_target\_node) | n/a | `string` | n/a | yes |
| <a name="input_template_file_id"></a> [template\_file\_id](#input\_template\_file\_id) | n/a | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_dns03_container_id"></a> [dns03\_container\_id](#output\_dns03\_container\_id) | n/a |
| <a name="output_dns03_hostname"></a> [dns03\_hostname](#output\_dns03\_hostname) | n/a |
| <a name="output_dns03_ipv4"></a> [dns03\_ipv4](#output\_dns03\_ipv4) | n/a |
| <a name="output_dns03_vmid"></a> [dns03\_vmid](#output\_dns03\_vmid) | n/a |
<!-- END_TF_DOCS -->