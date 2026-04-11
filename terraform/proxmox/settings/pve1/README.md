<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | 1.11.5 |
| <a name="requirement_proxmox"></a> [proxmox](#requirement\_proxmox) | 0.101.1 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_proxmox"></a> [proxmox](#provider\_proxmox) | 0.101.1 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [proxmox_network_linux_bridge.vmbr0](https://registry.terraform.io/providers/bpg/proxmox/0.101.1/docs/resources/network_linux_bridge) | resource |
| [proxmox_network_linux_bridge.vmbr1](https://registry.terraform.io/providers/bpg/proxmox/0.101.1/docs/resources/network_linux_bridge) | resource |
| [proxmox_virtual_environment_dns.dns](https://registry.terraform.io/providers/bpg/proxmox/0.101.1/docs/resources/virtual_environment_dns) | resource |
| [proxmox_virtual_environment_hosts.hosts](https://registry.terraform.io/providers/bpg/proxmox/0.101.1/docs/resources/virtual_environment_hosts) | resource |
| [proxmox_virtual_environment_time.timezone](https://registry.terraform.io/providers/bpg/proxmox/0.101.1/docs/resources/virtual_environment_time) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_dns_domain"></a> [dns\_domain](#input\_dns\_domain) | n/a | `string` | `"home.arpa"` | no |
| <a name="input_dns_servers"></a> [dns\_servers](#input\_dns\_servers) | n/a | `list(string)` | `[]` | no |
| <a name="input_local_domain"></a> [local\_domain](#input\_local\_domain) | n/a | `string` | `"home.arpa"` | no |
| <a name="input_network_vmbr0_address"></a> [network\_vmbr0\_address](#input\_network\_vmbr0\_address) | n/a | `string` | `"192.168.80.80/24"` | no |
| <a name="input_network_vmbr0_autostart"></a> [network\_vmbr0\_autostart](#input\_network\_vmbr0\_autostart) | n/a | `bool` | `true` | no |
| <a name="input_network_vmbr0_gateway"></a> [network\_vmbr0\_gateway](#input\_network\_vmbr0\_gateway) | n/a | `string` | `"192.168.80.1"` | no |
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