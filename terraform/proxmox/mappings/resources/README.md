<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | ~> 1.11.0 |
| <a name="requirement_proxmox"></a> [proxmox](#requirement\_proxmox) | 0.108.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_proxmox"></a> [proxmox](#provider\_proxmox) | 0.108.0 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [proxmox_hardware_mapping_pci.unraid_cache](https://registry.terraform.io/providers/bpg/proxmox/0.108.0/docs/resources/hardware_mapping_pci) | resource |
| [proxmox_hardware_mapping_pci.unraid_hba](https://registry.terraform.io/providers/bpg/proxmox/0.108.0/docs/resources/hardware_mapping_pci) | resource |
| [proxmox_hardware_mapping_pci.unraid_nic](https://registry.terraform.io/providers/bpg/proxmox/0.108.0/docs/resources/hardware_mapping_pci) | resource |
| [proxmox_hardware_mapping_usb.unraid_boot](https://registry.terraform.io/providers/bpg/proxmox/0.108.0/docs/resources/hardware_mapping_usb) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_pm_api_token"></a> [pm\_api\_token](#input\_pm\_api\_token) | n/a | `string` | n/a | yes |
| <a name="input_pm_api_url"></a> [pm\_api\_url](#input\_pm\_api\_url) | n/a | `string` | n/a | yes |
| <a name="input_pm_tls_insecure"></a> [pm\_tls\_insecure](#input\_pm\_tls\_insecure) | n/a | `bool` | `true` | no |
| <a name="input_target_node"></a> [target\_node](#input\_target\_node) | n/a | `string` | n/a | yes |
| <a name="input_unraid_boot_usb_map_id"></a> [unraid\_boot\_usb\_map\_id](#input\_unraid\_boot\_usb\_map\_id) | n/a | `string` | n/a | yes |
| <a name="input_unraid_boot_usb_map_path"></a> [unraid\_boot\_usb\_map\_path](#input\_unraid\_boot\_usb\_map\_path) | n/a | `string` | n/a | yes |
| <a name="input_unraid_boot_usb_mapping_name"></a> [unraid\_boot\_usb\_mapping\_name](#input\_unraid\_boot\_usb\_mapping\_name) | n/a | `string` | `"UnRaid-Boot"` | no |
| <a name="input_unraid_cache_iommu_group"></a> [unraid\_cache\_iommu\_group](#input\_unraid\_cache\_iommu\_group) | n/a | `number` | n/a | yes |
| <a name="input_unraid_cache_map_id"></a> [unraid\_cache\_map\_id](#input\_unraid\_cache\_map\_id) | n/a | `string` | n/a | yes |
| <a name="input_unraid_cache_map_path"></a> [unraid\_cache\_map\_path](#input\_unraid\_cache\_map\_path) | n/a | `string` | n/a | yes |
| <a name="input_unraid_cache_mapping_name"></a> [unraid\_cache\_mapping\_name](#input\_unraid\_cache\_mapping\_name) | n/a | `string` | `"UnRaid-Cache"` | no |
| <a name="input_unraid_cache_subsystem_id"></a> [unraid\_cache\_subsystem\_id](#input\_unraid\_cache\_subsystem\_id) | n/a | `string` | n/a | yes |
| <a name="input_unraid_hba_iommu_group"></a> [unraid\_hba\_iommu\_group](#input\_unraid\_hba\_iommu\_group) | n/a | `number` | n/a | yes |
| <a name="input_unraid_hba_map_id"></a> [unraid\_hba\_map\_id](#input\_unraid\_hba\_map\_id) | n/a | `string` | n/a | yes |
| <a name="input_unraid_hba_map_path"></a> [unraid\_hba\_map\_path](#input\_unraid\_hba\_map\_path) | n/a | `string` | n/a | yes |
| <a name="input_unraid_hba_mapping_name"></a> [unraid\_hba\_mapping\_name](#input\_unraid\_hba\_mapping\_name) | n/a | `string` | `"UnRaid-HBA"` | no |
| <a name="input_unraid_hba_subsystem_id"></a> [unraid\_hba\_subsystem\_id](#input\_unraid\_hba\_subsystem\_id) | n/a | `string` | n/a | yes |
| <a name="input_unraid_nic_iommu_group"></a> [unraid\_nic\_iommu\_group](#input\_unraid\_nic\_iommu\_group) | n/a | `number` | n/a | yes |
| <a name="input_unraid_nic_map_id"></a> [unraid\_nic\_map\_id](#input\_unraid\_nic\_map\_id) | n/a | `string` | n/a | yes |
| <a name="input_unraid_nic_map_path"></a> [unraid\_nic\_map\_path](#input\_unraid\_nic\_map\_path) | n/a | `string` | n/a | yes |
| <a name="input_unraid_nic_mapping_name"></a> [unraid\_nic\_mapping\_name](#input\_unraid\_nic\_mapping\_name) | n/a | `string` | `"UnRaid-NIC"` | no |
| <a name="input_unraid_nic_subsystem_id"></a> [unraid\_nic\_subsystem\_id](#input\_unraid\_nic\_subsystem\_id) | n/a | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_unraid_boot_usb_mapping_name"></a> [unraid\_boot\_usb\_mapping\_name](#output\_unraid\_boot\_usb\_mapping\_name) | n/a |
| <a name="output_unraid_cache_mapping_name"></a> [unraid\_cache\_mapping\_name](#output\_unraid\_cache\_mapping\_name) | n/a |
| <a name="output_unraid_hba_mapping_name"></a> [unraid\_hba\_mapping\_name](#output\_unraid\_hba\_mapping\_name) | n/a |
| <a name="output_unraid_nic_mapping_name"></a> [unraid\_nic\_mapping\_name](#output\_unraid\_nic\_mapping\_name) | n/a |
<!-- END_TF_DOCS -->