<!-- BEGIN_TF_DOCS -->


## Resources

| Name | Type |
|------|------|

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_cloudflare_zone"></a> [cloudflare\_zone](#input\_cloudflare\_zone) | Public Cloudflare DNS zone used by dependent OpenTofu roots. | `string` | n/a | yes |
| <a name="input_host_private_values"></a> [host\_private\_values](#input\_host\_private\_values) | Private per-host values such as LAN IPs, DNS names, and custom fields. | <pre>map(object({<br/>    mgmt_ip       = string<br/>    custom_fields = optional(any, {})<br/>  }))</pre> | `{}` | no |
| <a name="input_internal_zone"></a> [internal\_zone](#input\_internal\_zone) | Private DNS zone used to build NetBox device DNS names. Keep the real value in an uncommitted tfvars file. | `string` | `""` | no |
| <a name="input_netbox_allow_insecure_https"></a> [netbox\_allow\_insecure\_https](#input\_netbox\_allow\_insecure\_https) | Allow self-signed HTTPS certificates. | `bool` | `false` | no |
| <a name="input_netbox_api_token"></a> [netbox\_api\_token](#input\_netbox\_api\_token) | NetBox API token. | `string` | n/a | yes |
| <a name="input_netbox_request_timeout"></a> [netbox\_request\_timeout](#input\_netbox\_request\_timeout) | NetBox API request timeout in seconds. | `number` | `30` | no |
| <a name="input_netbox_server_url"></a> [netbox\_server\_url](#input\_netbox\_server\_url) | NetBox URL, including scheme and port if required. Example: https://netbox.int.example.com:8443 | `string` | n/a | yes |
| <a name="input_netbox_skip_version_check"></a> [netbox\_skip\_version\_check](#input\_netbox\_skip\_version\_check) | Skip provider NetBox version compatibility check. | `bool` | `false` | no |
| <a name="input_private_https_port"></a> [private\_https\_port](#input\_private\_https\_port) | Client-facing HTTPS port for private Traefik application routes. | `number` | `8443` | no |
| <a name="input_reserved_ip_private_values"></a> [reserved\_ip\_private\_values](#input\_reserved\_ip\_private\_values) | Private values for reserved infrastructure IPs, such as Keepalived DNS VIPs. | <pre>map(object({<br/>    ip_address = string<br/>  }))</pre> | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_cloudflare_zone"></a> [cloudflare\_zone](#output\_cloudflare\_zone) | Normalized public Cloudflare DNS zone used by dependent OpenTofu roots. |
| <a name="output_dns_ips"></a> [dns\_ips](#output\_dns\_ips) | DNS node and DNS VIP IPv4 addresses without CIDR suffix. |
| <a name="output_host_dns_names"></a> [host\_dns\_names](#output\_host\_dns\_names) | DNS names assigned to managed hosts. |
| <a name="output_host_primary_cidrs"></a> [host\_primary\_cidrs](#output\_host\_primary\_cidrs) | Primary management IPv4 addresses for managed hosts, including CIDR suffix. |
| <a name="output_host_primary_ipv4"></a> [host\_primary\_ipv4](#output\_host\_primary\_ipv4) | Primary management IPv4 addresses for managed hosts, without CIDR suffix. |
| <a name="output_host_tailscale_ipv4"></a> [host\_tailscale\_ipv4](#output\_host\_tailscale\_ipv4) | Tailscale IPv4 addresses for managed hosts. |
| <a name="output_hosts_by_tag"></a> [hosts\_by\_tag](#output\_hosts\_by\_tag) | Managed hosts grouped by local NetBox tag key. |
| <a name="output_internal_zone"></a> [internal\_zone](#output\_internal\_zone) | Private DNS zone used to build NetBox device DNS names. |
| <a name="output_managed_device_custom_fields"></a> [managed\_device\_custom\_fields](#output\_managed\_device\_custom\_fields) | Device custom fields managed in NetBox. |
| <a name="output_managed_hosts"></a> [managed\_hosts](#output\_managed\_hosts) | Hosts managed as NetBox devices. |
| <a name="output_managed_prefixes"></a> [managed\_prefixes](#output\_managed\_prefixes) | Prefixes managed in NetBox. |
| <a name="output_managed_reserved_ips"></a> [managed\_reserved\_ips](#output\_managed\_reserved\_ips) | Standalone/reserved IP addresses managed in NetBox. |
| <a name="output_managed_tags"></a> [managed\_tags](#output\_managed\_tags) | Tags managed in NetBox. |
| <a name="output_private_https_port"></a> [private\_https\_port](#output\_private\_https\_port) | Client-facing HTTPS port for private Traefik application routes. |
<!-- END_TF_DOCS -->