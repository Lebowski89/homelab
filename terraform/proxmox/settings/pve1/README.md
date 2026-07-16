<!-- BEGIN_TF_DOCS -->


## Resources

| Name | Type |
|------|------|
| [terraform_remote_state.netbox](https://registry.terraform.io/providers/hashicorp/terraform/latest/docs/data-sources/remote_state) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_dns_domain"></a> [dns\_domain](#input\_dns\_domain) | Optional Proxmox DNS search domain fallback. Ignored while enable\_netbox\_remote\_state is true. | `string` | `""` | no |
| <a name="input_dns_ips"></a> [dns\_ips](#input\_dns\_ips) | Fallback DNS node/VIP IPs. Normally sourced from terraform/netbox outputs.dns\_ips. | `map(string)` | `{}` | no |
| <a name="input_dns_servers"></a> [dns\_servers](#input\_dns\_servers) | Optional Proxmox DNS servers fallback. Ignored while enable\_netbox\_remote\_state is true. | `list(string)` | `[]` | no |
| <a name="input_enable_netbox_remote_state"></a> [enable\_netbox\_remote\_state](#input\_enable\_netbox\_remote\_state) | Read DNS topology data from the terraform/netbox local state. | `bool` | `true` | no |
| <a name="input_local_domain"></a> [local\_domain](#input\_local\_domain) | Optional local host domain fallback. Ignored while enable\_netbox\_remote\_state is true. | `string` | `""` | no |
| <a name="input_netbox_state_path"></a> [netbox\_state\_path](#input\_netbox\_state\_path) | Path to the terraform/netbox state file. | `string` | `"../../../netbox/terraform.tfstate"` | no |
| <a name="input_network_vmbr0_address"></a> [network\_vmbr0\_address](#input\_network\_vmbr0\_address) | n/a | `string` | n/a | yes |
| <a name="input_network_vmbr0_autostart"></a> [network\_vmbr0\_autostart](#input\_network\_vmbr0\_autostart) | n/a | `bool` | `true` | no |
| <a name="input_network_vmbr0_gateway"></a> [network\_vmbr0\_gateway](#input\_network\_vmbr0\_gateway) | n/a | `string` | n/a | yes |
| <a name="input_network_vmbr0_name"></a> [network\_vmbr0\_name](#input\_network\_vmbr0\_name) | n/a | `string` | `"vmbr0"` | no |
| <a name="input_network_vmbr0_ports"></a> [network\_vmbr0\_ports](#input\_network\_vmbr0\_ports) | n/a | `list(string)` | `[]` | no |
| <a name="input_network_vmbr1_autostart"></a> [network\_vmbr1\_autostart](#input\_network\_vmbr1\_autostart) | n/a | `bool` | `true` | no |
| <a name="input_network_vmbr1_name"></a> [network\_vmbr1\_name](#input\_network\_vmbr1\_name) | n/a | `string` | `"vmbr1"` | no |
| <a name="input_network_vmbr1_ports"></a> [network\_vmbr1\_ports](#input\_network\_vmbr1\_ports) | n/a | `list(string)` | `[]` | no |
| <a name="input_node_management_ip"></a> [node\_management\_ip](#input\_node\_management\_ip) | n/a | `string` | n/a | yes |
| <a name="input_pm_api_token"></a> [pm\_api\_token](#input\_pm\_api\_token) | n/a | `string` | n/a | yes |
| <a name="input_pm_api_url"></a> [pm\_api\_url](#input\_pm\_api\_url) | n/a | `string` | n/a | yes |
| <a name="input_pm_tls_insecure"></a> [pm\_tls\_insecure](#input\_pm\_tls\_insecure) | n/a | `bool` | `true` | no |
| <a name="input_target_node"></a> [target\_node](#input\_target\_node) | n/a | `string` | n/a | yes |
| <a name="input_timezone"></a> [timezone](#input\_timezone) | n/a | `string` | `"Australia/Melbourne"` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_dns_domain"></a> [dns\_domain](#output\_dns\_domain) | n/a |
| <a name="output_dns_servers"></a> [dns\_servers](#output\_dns\_servers) | n/a |
| <a name="output_hosts_node_name"></a> [hosts\_node\_name](#output\_hosts\_node\_name) | n/a |
| <a name="output_timezone"></a> [timezone](#output\_timezone) | n/a |
| <a name="output_vmbr0_name"></a> [vmbr0\_name](#output\_vmbr0\_name) | n/a |
| <a name="output_vmbr1_name"></a> [vmbr1\_name](#output\_vmbr1\_name) | n/a |
<!-- END_TF_DOCS -->