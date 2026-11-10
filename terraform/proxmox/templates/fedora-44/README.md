<!-- BEGIN_TF_DOCS -->


## Resources

| Name | Type |
|------|------|

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_cloud_image_checksum"></a> [cloud\_image\_checksum](#input\_cloud\_image\_checksum) | Official SHA-256 from Fedora-Cloud-44-1.7-x86\_64-CHECKSUM; see docs/fedora-44-template.md. | `string` | `"28680fe5b371a5a82ebf43a31926e086a168e59949d03969c5093e7071f90b7f"` | no |
| <a name="input_cloud_image_datastore"></a> [cloud\_image\_datastore](#input\_cloud\_image\_datastore) | n/a | `string` | `"local"` | no |
| <a name="input_cloud_image_file_name"></a> [cloud\_image\_file\_name](#input\_cloud\_image\_file\_name) | Node-local ISO storage filename; .img retains the original QCOW2 payload. | `string` | `"Fedora-Cloud-Base-Generic-44-1.7.x86_64.img"` | no |
| <a name="input_cloud_image_url"></a> [cloud\_image\_url](#input\_cloud\_image\_url) | n/a | `string` | `"https://dl.fedoraproject.org/pub/fedora/linux/releases/44/Cloud/x86_64/images/Fedora-Cloud-Base-Generic-44-1.7.x86_64.qcow2"` | no |
| <a name="input_pm_api_token"></a> [pm\_api\_token](#input\_pm\_api\_token) | n/a | `string` | n/a | yes |
| <a name="input_pm_api_url"></a> [pm\_api\_url](#input\_pm\_api\_url) | n/a | `string` | n/a | yes |
| <a name="input_pm_ssh_host"></a> [pm\_ssh\_host](#input\_pm\_ssh\_host) | n/a | `string` | n/a | yes |
| <a name="input_pm_ssh_username"></a> [pm\_ssh\_username](#input\_pm\_ssh\_username) | n/a | `string` | n/a | yes |
| <a name="input_pm_tls_insecure"></a> [pm\_tls\_insecure](#input\_pm\_tls\_insecure) | Disable Proxmox API TLS certificate verification. Keep false when the Proxmox CA is trusted; set true only for an explicitly accepted self-signed or untrusted certificate. | `bool` | `false` | no |
| <a name="input_ssh_public_key_path"></a> [ssh\_public\_key\_path](#input\_ssh\_public\_key\_path) | n/a | `string` | n/a | yes |
| <a name="input_target_node"></a> [target\_node](#input\_target\_node) | n/a | `string` | n/a | yes |
| <a name="input_template_bridge"></a> [template\_bridge](#input\_template\_bridge) | n/a | `string` | `"vmbr0"` | no |
| <a name="input_template_ci_user"></a> [template\_ci\_user](#input\_template\_ci\_user) | Cloud-init administrative user; Fedora cloud images conventionally use fedora. | `string` | `"fedora"` | no |
| <a name="input_template_cores"></a> [template\_cores](#input\_template\_cores) | n/a | `number` | `2` | no |
| <a name="input_template_memory"></a> [template\_memory](#input\_template\_memory) | n/a | `number` | `2048` | no |
| <a name="input_template_name"></a> [template\_name](#input\_template\_name) | n/a | `string` | `"fedora-44-cloudinit-template"` | no |
| <a name="input_template_vmid"></a> [template\_vmid](#input\_template\_vmid) | Explicitly selected, verified unused Proxmox template VMID. No automatic allocation or another template's VMID default. | `number` | n/a | yes |
| <a name="input_vm_storage"></a> [vm\_storage](#input\_vm\_storage) | n/a | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_cloud_image_file_id"></a> [cloud\_image\_file\_id](#output\_cloud\_image\_file\_id) | n/a |
| <a name="output_template_name"></a> [template\_name](#output\_template\_name) | n/a |
| <a name="output_template_vmid"></a> [template\_vmid](#output\_template\_vmid) | n/a |
<!-- END_TF_DOCS -->