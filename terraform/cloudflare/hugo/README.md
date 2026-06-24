<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | ~> 1.11.0 |
| <a name="requirement_cloudflare"></a> [cloudflare](#requirement\_cloudflare) | 5.21.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_cloudflare"></a> [cloudflare](#provider\_cloudflare) | 5.21.0 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [cloudflare_dns_record.github_pages_a](https://registry.terraform.io/providers/cloudflare/cloudflare/5.21.0/docs/resources/dns_record) | resource |
| [cloudflare_dns_record.github_pages_aaaa](https://registry.terraform.io/providers/cloudflare/cloudflare/5.21.0/docs/resources/dns_record) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_apex_name"></a> [apex\_name](#input\_apex\_name) | n/a | `string` | `"@"` | no |
| <a name="input_cloudflare_api_token"></a> [cloudflare\_api\_token](#input\_cloudflare\_api\_token) | n/a | `string` | n/a | yes |
| <a name="input_cloudflare_zone_id"></a> [cloudflare\_zone\_id](#input\_cloudflare\_zone\_id) | n/a | `string` | n/a | yes |
| <a name="input_ttl"></a> [ttl](#input\_ttl) | n/a | `number` | `1` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_github_pages_a_records"></a> [github\_pages\_a\_records](#output\_github\_pages\_a\_records) | n/a |
| <a name="output_github_pages_aaaa_records"></a> [github\_pages\_aaaa\_records](#output\_github\_pages\_aaaa\_records) | n/a |
<!-- END_TF_DOCS -->