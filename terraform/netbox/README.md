<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | ~> 1.11.0 |
| <a name="requirement_netbox"></a> [netbox](#requirement\_netbox) | 5.3.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_netbox"></a> [netbox](#provider\_netbox) | 5.3.0 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [netbox_custom_field.device](https://registry.terraform.io/providers/e-breuninger/netbox/5.3.0/docs/resources/custom_field) | resource |
| [netbox_device.hosts](https://registry.terraform.io/providers/e-breuninger/netbox/5.3.0/docs/resources/device) | resource |
| [netbox_device_interface.mgmt](https://registry.terraform.io/providers/e-breuninger/netbox/5.3.0/docs/resources/device_interface) | resource |
| [netbox_device_primary_ip.hosts](https://registry.terraform.io/providers/e-breuninger/netbox/5.3.0/docs/resources/device_primary_ip) | resource |
| [netbox_device_role.this](https://registry.terraform.io/providers/e-breuninger/netbox/5.3.0/docs/resources/device_role) | resource |
| [netbox_device_type.this](https://registry.terraform.io/providers/e-breuninger/netbox/5.3.0/docs/resources/device_type) | resource |
| [netbox_interface_template.this](https://registry.terraform.io/providers/e-breuninger/netbox/5.3.0/docs/resources/interface_template) | resource |
| [netbox_ip_address.mgmt](https://registry.terraform.io/providers/e-breuninger/netbox/5.3.0/docs/resources/ip_address) | resource |
| [netbox_ip_address.reserved](https://registry.terraform.io/providers/e-breuninger/netbox/5.3.0/docs/resources/ip_address) | resource |
| [netbox_manufacturer.this](https://registry.terraform.io/providers/e-breuninger/netbox/5.3.0/docs/resources/manufacturer) | resource |
| [netbox_prefix.this](https://registry.terraform.io/providers/e-breuninger/netbox/5.3.0/docs/resources/prefix) | resource |
| [netbox_site.this](https://registry.terraform.io/providers/e-breuninger/netbox/5.3.0/docs/resources/site) | resource |
| [netbox_tag.this](https://registry.terraform.io/providers/e-breuninger/netbox/5.3.0/docs/resources/tag) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_host_private_values"></a> [host\_private\_values](#input\_host\_private\_values) | Private per-host values such as LAN IPs, DNS names, and custom fields. | <pre>map(object({<br/>    mgmt_ip       = string<br/>    custom_fields = optional(any, {})<br/>  }))</pre> | `{}` | no |
| <a name="input_internal_zone"></a> [internal\_zone](#input\_internal\_zone) | Private DNS zone used to build NetBox device DNS names. Keep the real value in an uncommitted tfvars file. | `string` | `""` | no |
| <a name="input_netbox_allow_insecure_https"></a> [netbox\_allow\_insecure\_https](#input\_netbox\_allow\_insecure\_https) | Allow self-signed HTTPS certificates. | `bool` | `false` | no |
| <a name="input_netbox_api_token"></a> [netbox\_api\_token](#input\_netbox\_api\_token) | NetBox API token. | `string` | n/a | yes |
| <a name="input_netbox_request_timeout"></a> [netbox\_request\_timeout](#input\_netbox\_request\_timeout) | NetBox API request timeout in seconds. | `number` | `30` | no |
| <a name="input_netbox_server_url"></a> [netbox\_server\_url](#input\_netbox\_server\_url) | NetBox URL, including scheme and port if required. Example: https://netbox.int.example.com:8443 | `string` | n/a | yes |
| <a name="input_netbox_skip_version_check"></a> [netbox\_skip\_version\_check](#input\_netbox\_skip\_version\_check) | Skip provider NetBox version compatibility check. | `bool` | `false` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_host_dns_names"></a> [host\_dns\_names](#output\_host\_dns\_names) | DNS names assigned to managed hosts. |
| <a name="output_host_primary_cidrs"></a> [host\_primary\_cidrs](#output\_host\_primary\_cidrs) | Primary management IPv4 addresses for managed hosts, including CIDR suffix. |
| <a name="output_host_primary_ipv4"></a> [host\_primary\_ipv4](#output\_host\_primary\_ipv4) | Primary management IPv4 addresses for managed hosts, without CIDR suffix. |
| <a name="output_host_tailscale_ipv4"></a> [host\_tailscale\_ipv4](#output\_host\_tailscale\_ipv4) | Tailscale IPv4 addresses for managed hosts. |
| <a name="output_hosts_by_tag"></a> [hosts\_by\_tag](#output\_hosts\_by\_tag) | Managed hosts grouped by local NetBox tag key. |
| <a name="output_managed_device_custom_fields"></a> [managed\_device\_custom\_fields](#output\_managed\_device\_custom\_fields) | Device custom fields managed in NetBox. |
| <a name="output_managed_hosts"></a> [managed\_hosts](#output\_managed\_hosts) | Hosts managed as NetBox devices. |
| <a name="output_managed_prefixes"></a> [managed\_prefixes](#output\_managed\_prefixes) | Prefixes managed in NetBox. |
| <a name="output_managed_reserved_ips"></a> [managed\_reserved\_ips](#output\_managed\_reserved\_ips) | Standalone/reserved IP addresses managed in NetBox. |
| <a name="output_managed_tags"></a> [managed\_tags](#output\_managed\_tags) | Tags managed in NetBox. |
<!-- END_TF_DOCS -->