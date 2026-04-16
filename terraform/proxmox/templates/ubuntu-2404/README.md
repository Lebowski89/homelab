<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | ~> 1.11.0 |
| <a name="requirement_proxmox"></a> [proxmox](#requirement\_proxmox) | 0.102.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_proxmox"></a> [proxmox](#provider\_proxmox) | 0.102.0 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [proxmox_download_file.ubuntu_cloud_image](https://registry.terraform.io/providers/bpg/proxmox/0.102.0/docs/resources/download_file) | resource |
| [proxmox_virtual_environment_vm.ubuntu_template](https://registry.terraform.io/providers/bpg/proxmox/0.102.0/docs/resources/virtual_environment_vm) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_cloud_image_datastore"></a> [cloud\_image\_datastore](#input\_cloud\_image\_datastore) | n/a | `string` | `"local"` | no |
| <a name="input_cloud_image_file_name"></a> [cloud\_image\_file\_name](#input\_cloud\_image\_file\_name) | n/a | `string` | `"noble-server-cloudimg-amd64.img"` | no |
| <a name="input_cloud_image_node_name"></a> [cloud\_image\_node\_name](#input\_cloud\_image\_node\_name) | n/a | `string` | n/a | yes |
| <a name="input_cloud_image_url"></a> [cloud\_image\_url](#input\_cloud\_image\_url) | n/a | `string` | `"https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img"` | no |
| <a name="input_pm_api_token"></a> [pm\_api\_token](#input\_pm\_api\_token) | n/a | `string` | n/a | yes |
| <a name="input_pm_api_url"></a> [pm\_api\_url](#input\_pm\_api\_url) | n/a | `string` | n/a | yes |
| <a name="input_pm_ssh_host"></a> [pm\_ssh\_host](#input\_pm\_ssh\_host) | n/a | `string` | n/a | yes |
| <a name="input_pm_ssh_username"></a> [pm\_ssh\_username](#input\_pm\_ssh\_username) | n/a | `string` | n/a | yes |
| <a name="input_pm_tls_insecure"></a> [pm\_tls\_insecure](#input\_pm\_tls\_insecure) | n/a | `bool` | `true` | no |
| <a name="input_snippet_storage"></a> [snippet\_storage](#input\_snippet\_storage) | n/a | `string` | `"local"` | no |
| <a name="input_ssh_public_key_path"></a> [ssh\_public\_key\_path](#input\_ssh\_public\_key\_path) | n/a | `string` | n/a | yes |
| <a name="input_target_node"></a> [target\_node](#input\_target\_node) | n/a | `string` | n/a | yes |
| <a name="input_template_bridge"></a> [template\_bridge](#input\_template\_bridge) | n/a | `string` | `"vmbr0"` | no |
| <a name="input_template_ci_user"></a> [template\_ci\_user](#input\_template\_ci\_user) | n/a | `string` | `"ubuntu"` | no |
| <a name="input_template_cores"></a> [template\_cores](#input\_template\_cores) | n/a | `number` | `2` | no |
| <a name="input_template_memory"></a> [template\_memory](#input\_template\_memory) | n/a | `number` | `2048` | no |
| <a name="input_template_name"></a> [template\_name](#input\_template\_name) | n/a | `string` | `"ubuntu-2404-lts-cloudinit-template"` | no |
| <a name="input_template_vmid"></a> [template\_vmid](#input\_template\_vmid) | n/a | `number` | `9002` | no |
| <a name="input_vm_storage"></a> [vm\_storage](#input\_vm\_storage) | n/a | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_cloud_image_file_id"></a> [cloud\_image\_file\_id](#output\_cloud\_image\_file\_id) | n/a |
| <a name="output_template_name"></a> [template\_name](#output\_template\_name) | n/a |
| <a name="output_template_vmid"></a> [template\_vmid](#output\_template\_vmid) | n/a |
<!-- END_TF_DOCS -->