<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | ~> 1.11.0 |
| <a name="requirement_seerr"></a> [seerr](#requirement\_seerr) | 0.19.5 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_seerr"></a> [seerr](#provider\_seerr) | 0.19.5 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [seerr_main_settings.this](https://registry.terraform.io/providers/josh-archer/seerr/0.19.5/docs/resources/main_settings) | resource |
| [seerr_notification_gotify.this](https://registry.terraform.io/providers/josh-archer/seerr/0.19.5/docs/resources/notification_gotify) | resource |
| [seerr_plex_settings.this](https://registry.terraform.io/providers/josh-archer/seerr/0.19.5/docs/resources/plex_settings) | resource |
| [seerr_radarr_server.this](https://registry.terraform.io/providers/josh-archer/seerr/0.19.5/docs/resources/radarr_server) | resource |
| [seerr_sonarr_server.this](https://registry.terraform.io/providers/josh-archer/seerr/0.19.5/docs/resources/sonarr_server) | resource |
| [seerr_tautulli_settings.this](https://registry.terraform.io/providers/josh-archer/seerr/0.19.5/docs/resources/tautulli_settings) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_domain_int"></a> [domain\_int](#input\_domain\_int) | n/a | `string` | n/a | yes |
| <a name="input_gotify_token"></a> [gotify\_token](#input\_gotify\_token) | n/a | `string` | n/a | yes |
| <a name="input_plex_ip"></a> [plex\_ip](#input\_plex\_ip) | n/a | `string` | n/a | yes |
| <a name="input_radarr_4k_api_key"></a> [radarr\_4k\_api\_key](#input\_radarr\_4k\_api\_key) | n/a | `string` | n/a | yes |
| <a name="input_radarr_api_key"></a> [radarr\_api\_key](#input\_radarr\_api\_key) | n/a | `string` | n/a | yes |
| <a name="input_seerr_api_key"></a> [seerr\_api\_key](#input\_seerr\_api\_key) | n/a | `string` | n/a | yes |
| <a name="input_seerr_url"></a> [seerr\_url](#input\_seerr\_url) | n/a | `string` | n/a | yes |
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