<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | ~> 1.11.0 |
| <a name="requirement_cloudflare"></a> [cloudflare](#requirement\_cloudflare) | 5.21.1 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_cloudflare"></a> [cloudflare](#provider\_cloudflare) | 5.21.1 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [cloudflare_dns_record.mx_fwd1](https://registry.terraform.io/providers/cloudflare/cloudflare/5.21.1/docs/resources/dns_record) | resource |
| [cloudflare_dns_record.mx_fwd2](https://registry.terraform.io/providers/cloudflare/cloudflare/5.21.1/docs/resources/dns_record) | resource |
| [cloudflare_dns_record.service_a](https://registry.terraform.io/providers/cloudflare/cloudflare/5.21.1/docs/resources/dns_record) | resource |
| [cloudflare_dns_record.txt_dkim_default](https://registry.terraform.io/providers/cloudflare/cloudflare/5.21.1/docs/resources/dns_record) | resource |
| [cloudflare_dns_record.txt_dmarc](https://registry.terraform.io/providers/cloudflare/cloudflare/5.21.1/docs/resources/dns_record) | resource |
| [cloudflare_dns_record.txt_spf](https://registry.terraform.io/providers/cloudflare/cloudflare/5.21.1/docs/resources/dns_record) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_cloudflare_api_token"></a> [cloudflare\_api\_token](#input\_cloudflare\_api\_token) | n/a | `string` | n/a | yes |
| <a name="input_cloudflare_zone_id"></a> [cloudflare\_zone\_id](#input\_cloudflare\_zone\_id) | n/a | `string` | n/a | yes |
| <a name="input_public_ipv4"></a> [public\_ipv4](#input\_public\_ipv4) | n/a | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_mx_records"></a> [mx\_records](#output\_mx\_records) | n/a |
| <a name="output_service_a_public_ipv4"></a> [service\_a\_public\_ipv4](#output\_service\_a\_public\_ipv4) | n/a |
| <a name="output_service_a_record_fqdns"></a> [service\_a\_record\_fqdns](#output\_service\_a\_record\_fqdns) | n/a |
| <a name="output_service_a_record_ids"></a> [service\_a\_record\_ids](#output\_service\_a\_record\_ids) | n/a |
| <a name="output_service_a_record_names"></a> [service\_a\_record\_names](#output\_service\_a\_record\_names) | n/a |
| <a name="output_txt_record_names"></a> [txt\_record\_names](#output\_txt\_record\_names) | n/a |
<!-- END_TF_DOCS -->