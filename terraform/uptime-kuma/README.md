<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | ~> 1.11.0 |
| <a name="requirement_uptimekuma"></a> [uptimekuma](#requirement\_uptimekuma) | 0.3.1 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_terraform"></a> [terraform](#provider\_terraform) | n/a |
| <a name="provider_uptimekuma"></a> [uptimekuma](#provider\_uptimekuma) | 0.3.1 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [uptimekuma_monitor_dns.this](https://registry.terraform.io/providers/breml/uptimekuma/0.3.1/docs/resources/monitor_dns) | resource |
| [uptimekuma_monitor_group.child](https://registry.terraform.io/providers/breml/uptimekuma/0.3.1/docs/resources/monitor_group) | resource |
| [uptimekuma_monitor_group.root](https://registry.terraform.io/providers/breml/uptimekuma/0.3.1/docs/resources/monitor_group) | resource |
| [uptimekuma_monitor_http.this](https://registry.terraform.io/providers/breml/uptimekuma/0.3.1/docs/resources/monitor_http) | resource |
| [uptimekuma_monitor_ping.this](https://registry.terraform.io/providers/breml/uptimekuma/0.3.1/docs/resources/monitor_ping) | resource |
| [uptimekuma_monitor_postgres.this](https://registry.terraform.io/providers/breml/uptimekuma/0.3.1/docs/resources/monitor_postgres) | resource |
| [uptimekuma_monitor_tcp_port.this](https://registry.terraform.io/providers/breml/uptimekuma/0.3.1/docs/resources/monitor_tcp_port) | resource |
| [uptimekuma_notification_gotify.gotify](https://registry.terraform.io/providers/breml/uptimekuma/0.3.1/docs/resources/notification_gotify) | resource |
| [uptimekuma_status_page.homelab](https://registry.terraform.io/providers/breml/uptimekuma/0.3.1/docs/resources/status_page) | resource |
| [uptimekuma_tag.this](https://registry.terraform.io/providers/breml/uptimekuma/0.3.1/docs/resources/tag) | resource |
| [terraform_remote_state.netbox](https://registry.terraform.io/providers/hashicorp/terraform/latest/docs/data-sources/remote_state) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_cloudflare_zone"></a> [cloudflare\_zone](#input\_cloudflare\_zone) | Parent Cloudflare zone/domain. | `string` | n/a | yes |
| <a name="input_enable_gotify_notification"></a> [enable\_gotify\_notification](#input\_enable\_gotify\_notification) | Create and attach the Gotify notification channel to monitors by default. | `bool` | `true` | no |
| <a name="input_enable_netbox_remote_state"></a> [enable\_netbox\_remote\_state](#input\_enable\_netbox\_remote\_state) | Read host/IP data from the terraform/netbox local state. | `bool` | `true` | no |
| <a name="input_gotify_application_token"></a> [gotify\_application\_token](#input\_gotify\_application\_token) | Gotify application token for Uptime Kuma notifications. | `string` | `null` | no |
| <a name="input_gotify_priority"></a> [gotify\_priority](#input\_gotify\_priority) | Gotify message priority. | `number` | `8` | no |
| <a name="input_gotify_server_url"></a> [gotify\_server\_url](#input\_gotify\_server\_url) | Gotify URL as reached by Uptime Kuma. | `string` | n/a | yes |
| <a name="input_host_ips"></a> [host\_ips](#input\_host\_ips) | Fallback or override private host IPs used by direct, ping, TCP, and DNS monitors. | `map(string)` | `{}` | no |
| <a name="input_internal_zone"></a> [internal\_zone](#input\_internal\_zone) | Internal/private DNS zone used by Traefik private routes. | `string` | n/a | yes |
| <a name="input_netbox_state_path"></a> [netbox\_state\_path](#input\_netbox\_state\_path) | Path to the terraform/netbox state file. | `string` | `"../netbox/terraform.tfstate"` | no |
| <a name="input_postgres_monitor_connection_strings"></a> [postgres\_monitor\_connection\_strings](#input\_postgres\_monitor\_connection\_strings) | PostgreSQL connection strings for Uptime Kuma PostgreSQL monitors. These are sensitive and will be stored in OpenTofu state. | `map(string)` | `{}` | no |
| <a name="input_private_https_port"></a> [private\_https\_port](#input\_private\_https\_port) | Traefik private HTTPS entrypoint port. | `number` | `8443` | no |
| <a name="input_uptime_kuma_endpoint"></a> [uptime\_kuma\_endpoint](#input\_uptime\_kuma\_endpoint) | Base URL for Uptime Kuma. Example: https://uptime-kuma.somedomain.com | `string` | n/a | yes |
| <a name="input_uptime_kuma_max_retries"></a> [uptime\_kuma\_max\_retries](#input\_uptime\_kuma\_max\_retries) | Provider connection max\_retries as a Go duration string. | `string` | `"5"` | no |
| <a name="input_uptime_kuma_password"></a> [uptime\_kuma\_password](#input\_uptime\_kuma\_password) | Uptime Kuma password. Can also be supplied with TF\_VAR\_uptime\_kuma\_password. | `string` | n/a | yes |
| <a name="input_uptime_kuma_per_attempt_timeout"></a> [uptime\_kuma\_per\_attempt\_timeout](#input\_uptime\_kuma\_per\_attempt\_timeout) | Provider connection per\_attempt\_timeout as a Go duration string. | `string` | `"20s"` | no |
| <a name="input_uptime_kuma_timeout"></a> [uptime\_kuma\_timeout](#input\_uptime\_kuma\_timeout) | Provider connection timeout as a Go duration string. | `string` | `"2m"` | no |
| <a name="input_uptime_kuma_username"></a> [uptime\_kuma\_username](#input\_uptime\_kuma\_username) | Uptime Kuma username. Can also be supplied with TF\_VAR\_uptime\_kuma\_username. | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_dns_monitor_ids"></a> [dns\_monitor\_ids](#output\_dns\_monitor\_ids) | DNS monitor IDs keyed by monitor key. |
| <a name="output_group_ids"></a> [group\_ids](#output\_group\_ids) | Created Uptime Kuma group IDs. |
| <a name="output_http_monitor_ids"></a> [http\_monitor\_ids](#output\_http\_monitor\_ids) | HTTP monitor IDs keyed by monitor key. |
| <a name="output_ping_monitor_ids"></a> [ping\_monitor\_ids](#output\_ping\_monitor\_ids) | Ping monitor IDs keyed by monitor key. |
| <a name="output_postgres_monitor_ids"></a> [postgres\_monitor\_ids](#output\_postgres\_monitor\_ids) | PostgreSQL monitor IDs keyed by monitor key. |
| <a name="output_tag_ids"></a> [tag\_ids](#output\_tag\_ids) | Uptime Kuma tag IDs. |
| <a name="output_tcp_monitor_ids"></a> [tcp\_monitor\_ids](#output\_tcp\_monitor\_ids) | TCP monitor IDs keyed by monitor key. |
<!-- END_TF_DOCS -->