<!-- BEGIN_TF_DOCS -->


## Resources

| Name | Type |
|------|------|

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_pm_api_token"></a> [pm\_api\_token](#input\_pm\_api\_token) | n/a | `string` | n/a | yes |
| <a name="input_pm_api_url"></a> [pm\_api\_url](#input\_pm\_api\_url) | n/a | `string` | n/a | yes |
| <a name="input_pm_ssh_host"></a> [pm\_ssh\_host](#input\_pm\_ssh\_host) | n/a | `string` | n/a | yes |
| <a name="input_pm_ssh_username"></a> [pm\_ssh\_username](#input\_pm\_ssh\_username) | n/a | `string` | n/a | yes |
| <a name="input_pm_tls_insecure"></a> [pm\_tls\_insecure](#input\_pm\_tls\_insecure) | Disable Proxmox API TLS certificate verification. Keep false when the Proxmox CA is trusted; set true only for an explicitly accepted self-signed or untrusted certificate. | `bool` | `false` | no |
| <a name="input_template_datastore"></a> [template\_datastore](#input\_template\_datastore) | n/a | `string` | `"local"` | no |
| <a name="input_template_file_name"></a> [template\_file\_name](#input\_template\_file\_name) | n/a | `string` | `"noble-server-cloudimg-amd64-root.tar.xz"` | no |
| <a name="input_template_node_name"></a> [template\_node\_name](#input\_template\_node\_name) | n/a | `string` | n/a | yes |
| <a name="input_template_url"></a> [template\_url](#input\_template\_url) | n/a | `string` | `"https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64-root.tar.xz"` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_template_download_id"></a> [template\_download\_id](#output\_template\_download\_id) | n/a |
| <a name="output_template_file_id"></a> [template\_file\_id](#output\_template\_file\_id) | n/a |
<!-- END_TF_DOCS -->