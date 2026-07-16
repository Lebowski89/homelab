<!-- BEGIN_TF_DOCS -->


## Resources

| Name | Type |
|------|------|
| [terraform_remote_state.netbox](https://registry.terraform.io/providers/hashicorp/terraform/latest/docs/data-sources/remote_state) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_enable_netbox_remote_state"></a> [enable\_netbox\_remote\_state](#input\_enable\_netbox\_remote\_state) | Read DNS topology data from the terraform/netbox local state. | `bool` | `true` | no |
| <a name="input_internal_zone_catalog"></a> [internal\_zone\_catalog](#input\_internal\_zone\_catalog) | Optional explicit Technitium catalog zone. Defaults to cluster-catalog.<technitium\_cluster\_domain>. | `string` | `""` | no |
| <a name="input_netbox_state_path"></a> [netbox\_state\_path](#input\_netbox\_state\_path) | Path to the terraform/netbox state file. | `string` | `"../../netbox/terraform.tfstate"` | no |
| <a name="input_technitium_api_token"></a> [technitium\_api\_token](#input\_technitium\_api\_token) | n/a | `string` | n/a | yes |
| <a name="input_technitium_cluster_domain"></a> [technitium\_cluster\_domain](#input\_technitium\_cluster\_domain) | Technitium DNS cluster domain. Used to derive the catalog zone name. | `string` | `"skynet"` | no |
| <a name="input_technitium_server"></a> [technitium\_server](#input\_technitium\_server) | Optional explicit Technitium API URL fallback. Ignored when empty and NetBox remote state is enabled. | `string` | `""` | no |
| <a name="input_technitium_server_host"></a> [technitium\_server\_host](#input\_technitium\_server\_host) | NetBox host key used to derive the Technitium API server IP. | `string` | `"mgt"` | no |
| <a name="input_technitium_server_port"></a> [technitium\_server\_port](#input\_technitium\_server\_port) | Technitium HTTP API port. | `number` | `5380` | no |
| <a name="input_traefik_host"></a> [traefik\_host](#input\_traefik\_host) | NetBox host key used to derive the Traefik backend IPv4 address for internal service A records. | `string` | `"mgt"` | no |
| <a name="input_traefik_ipv4"></a> [traefik\_ipv4](#input\_traefik\_ipv4) | Optional explicit Traefik IPv4 fallback. Ignored when empty and NetBox remote state is enabled. | `string` | `""` | no |
| <a name="input_ttl"></a> [ttl](#input\_ttl) | n/a | `number` | `300` | no |
| <a name="input_zone_name"></a> [zone\_name](#input\_zone\_name) | Optional explicit DNS zone fallback. Ignored when empty and NetBox remote state provides internal\_zone. | `string` | `""` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_service_fqdns"></a> [service\_fqdns](#output\_service\_fqdns) | n/a |
| <a name="output_technitium_server"></a> [technitium\_server](#output\_technitium\_server) | n/a |
| <a name="output_traefik_ipv4"></a> [traefik\_ipv4](#output\_traefik\_ipv4) | n/a |
| <a name="output_zone_name"></a> [zone\_name](#output\_zone\_name) | n/a |
<!-- END_TF_DOCS -->