<!-- BEGIN_TF_DOCS -->


## Resources

| Name | Type |
|------|------|
| [terraform_remote_state.netbox](https://registry.terraform.io/providers/hashicorp/terraform/latest/docs/data-sources/remote_state) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_domain_int"></a> [domain\_int](#input\_domain\_int) | Optional internal DNS zone fallback. Normally sourced from terraform/netbox outputs.internal\_zone. | `string` | `""` | no |
| <a name="input_enable_netbox_remote_state"></a> [enable\_netbox\_remote\_state](#input\_enable\_netbox\_remote\_state) | Read host and DNS topology data from the terraform/netbox local state. | `bool` | `true` | no |
| <a name="input_gotify_token"></a> [gotify\_token](#input\_gotify\_token) | n/a | `string` | n/a | yes |
| <a name="input_netbox_state_path"></a> [netbox\_state\_path](#input\_netbox\_state\_path) | Path to the terraform/netbox state file. | `string` | `"../netbox/terraform.tfstate"` | no |
| <a name="input_plex_ip"></a> [plex\_ip](#input\_plex\_ip) | Optional Plex IP fallback. Normally sourced from terraform/netbox outputs.host\_primary\_ipv4["plex"]. | `string` | `""` | no |
| <a name="input_private_https_port"></a> [private\_https\_port](#input\_private\_https\_port) | Optional private HTTPS port override. Defaults to terraform/netbox, then 8443. | `number` | `null` | no |
| <a name="input_radarr_4k_api_key"></a> [radarr\_4k\_api\_key](#input\_radarr\_4k\_api\_key) | n/a | `string` | n/a | yes |
| <a name="input_radarr_api_key"></a> [radarr\_api\_key](#input\_radarr\_api\_key) | n/a | `string` | n/a | yes |
| <a name="input_seerr_api_key"></a> [seerr\_api\_key](#input\_seerr\_api\_key) | n/a | `string` | n/a | yes |
| <a name="input_seerr_url"></a> [seerr\_url](#input\_seerr\_url) | Optional explicit Seerr URL. Defaults to https://seerr.<domain\_int>:<private\_https\_port>. | `string` | `""` | no |
| <a name="input_sonarr_4k_api_key"></a> [sonarr\_4k\_api\_key](#input\_sonarr\_4k\_api\_key) | n/a | `string` | n/a | yes |
| <a name="input_sonarr_api_key"></a> [sonarr\_api\_key](#input\_sonarr\_api\_key) | n/a | `string` | n/a | yes |
| <a name="input_tautulli_api_key"></a> [tautulli\_api\_key](#input\_tautulli\_api\_key) | n/a | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_plex_status_code"></a> [plex\_status\_code](#output\_plex\_status\_code) | n/a |
| <a name="output_radarr_server_ids"></a> [radarr\_server\_ids](#output\_radarr\_server\_ids) | n/a |
| <a name="output_sonarr_server_ids"></a> [sonarr\_server\_ids](#output\_sonarr\_server\_ids) | n/a |
| <a name="output_tautulli_status_code"></a> [tautulli\_status\_code](#output\_tautulli\_status\_code) | n/a |
<!-- END_TF_DOCS -->