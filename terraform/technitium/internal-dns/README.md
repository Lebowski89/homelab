<!-- BEGIN_TF_DOCS -->


## Resources

| Name | Type |
|------|------|

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_internal_zone_catalog"></a> [internal\_zone\_catalog](#input\_internal\_zone\_catalog) | Technitium catalog zone used to replicate/share the internal zone across the DNS cluster. | `string` | n/a | yes |
| <a name="input_technitium_api_token"></a> [technitium\_api\_token](#input\_technitium\_api\_token) | n/a | `string` | n/a | yes |
| <a name="input_technitium_server"></a> [technitium\_server](#input\_technitium\_server) | n/a | `string` | n/a | yes |
| <a name="input_traefik_ipv4"></a> [traefik\_ipv4](#input\_traefik\_ipv4) | n/a | `string` | n/a | yes |
| <a name="input_ttl"></a> [ttl](#input\_ttl) | n/a | `number` | `300` | no |
| <a name="input_zone_name"></a> [zone\_name](#input\_zone\_name) | n/a | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_service_fqdns"></a> [service\_fqdns](#output\_service\_fqdns) | n/a |
| <a name="output_traefik_ipv4"></a> [traefik\_ipv4](#output\_traefik\_ipv4) | n/a |
| <a name="output_zone_name"></a> [zone\_name](#output\_zone\_name) | n/a |
<!-- END_TF_DOCS -->