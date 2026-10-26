<!-- BEGIN_TF_DOCS -->
## Modules

| Name | Source | Version |
|------|--------|---------|
| <a name="module_rocky_vm"></a> [rocky\_vm](#module\_rocky\_vm) | ../../modules/cloudinit-vm | n/a |

## Resources

| Name | Type |
|------|------|
| [terraform_remote_state.netbox](https://registry.terraform.io/providers/hashicorp/terraform/latest/docs/data-sources/remote_state) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_clone_template_vm_id"></a> [clone\_template\_vm\_id](#input\_clone\_template\_vm\_id) | Existing Rocky Linux cloud-init template VMID. | `number` | `9004` | no |
| <a name="input_cloud_init_user"></a> [cloud\_init\_user](#input\_cloud\_init\_user) | n/a | `string` | `"rocky"` | no |
| <a name="input_enable_netbox_remote_state"></a> [enable\_netbox\_remote\_state](#input\_enable\_netbox\_remote\_state) | Read the existing NetBox state outputs; this root never changes NetBox. | `bool` | `true` | no |
| <a name="input_netbox_state_path"></a> [netbox\_state\_path](#input\_netbox\_state\_path) | Authoritative private NetBox state snapshot supplying inventory-derived network settings. | `string` | `"../../../netbox/terraform.tfstate"` | no |
| <a name="input_pm_api_token"></a> [pm\_api\_token](#input\_pm\_api\_token) | Proxmox API token supplied through private inputs. | `string` | n/a | yes |
| <a name="input_pm_api_url"></a> [pm\_api\_url](#input\_pm\_api\_url) | Proxmox API URL, for example https://pve.example.com:8006/. | `string` | n/a | yes |
| <a name="input_pm_ssh_host"></a> [pm\_ssh\_host](#input\_pm\_ssh\_host) | SSH address of the selected Proxmox node. | `string` | n/a | yes |
| <a name="input_pm_ssh_port"></a> [pm\_ssh\_port](#input\_pm\_ssh\_port) | n/a | `number` | `22` | no |
| <a name="input_pm_ssh_username"></a> [pm\_ssh\_username](#input\_pm\_ssh\_username) | Proxmox SSH user for snippet operations; authentication uses the workstation SSH agent. | `string` | n/a | yes |
| <a name="input_pm_tls_insecure"></a> [pm\_tls\_insecure](#input\_pm\_tls\_insecure) | Disable Proxmox API TLS certificate verification only for an explicitly accepted untrusted certificate. | `bool` | `false` | no |
| <a name="input_snippet_storage"></a> [snippet\_storage](#input\_snippet\_storage) | Snippet-capable storage on target\_node for the module's guest-agent vendor data. | `string` | `"local"` | no |
| <a name="input_ssh_public_key_path"></a> [ssh\_public\_key\_path](#input\_ssh\_public\_key\_path) | Workstation path to the public key installed for cloud\_init\_user. | `string` | n/a | yes |
| <a name="input_target_node"></a> [target\_node](#input\_target\_node) | Proxmox node hosting both the Rocky template and its new clone. | `string` | n/a | yes |
| <a name="input_vm_cpu_cores"></a> [vm\_cpu\_cores](#input\_vm\_cpu\_cores) | n/a | `number` | `4` | no |
| <a name="input_vm_description"></a> [vm\_description](#input\_vm\_description) | n/a | `string` | `"Staged Rocky Linux management VM managed by OpenTofu"` | no |
| <a name="input_vm_disk_size_gb"></a> [vm\_disk\_size\_gb](#input\_vm\_disk\_size\_gb) | New system disk size in GiB, at least the Rocky template's 10 GiB virtual size. | `number` | `64` | no |
| <a name="input_vm_gateway_host"></a> [vm\_gateway\_host](#input\_vm\_gateway\_host) | n/a | `string` | `"router"` | no |
| <a name="input_vm_id"></a> [vm\_id](#input\_vm\_id) | Required explicitly selected, verified free VMID for the staged replacement; never VM104 or the source template. | `number` | n/a | yes |
| <a name="input_vm_ipv4_address"></a> [vm\_ipv4\_address](#input\_vm\_ipv4\_address) | Explicit staging IPv4 CIDR override; otherwise use NetBox host\_primary\_cidrs[vm\_name]. | `string` | `""` | no |
| <a name="input_vm_ipv4_gateway"></a> [vm\_ipv4\_gateway](#input\_vm\_ipv4\_gateway) | Explicit gateway override; otherwise use the NetBox primary IPv4 of vm\_gateway\_host. | `string` | `""` | no |
| <a name="input_vm_memory_mb"></a> [vm\_memory\_mb](#input\_vm\_memory\_mb) | n/a | `number` | `4096` | no |
| <a name="input_vm_name"></a> [vm\_name](#input\_vm\_name) | Required distinct staging name; also the NetBox host key for address lookup. Production mgt remains separate. | `string` | n/a | yes |
| <a name="input_vm_nameservers"></a> [vm\_nameservers](#input\_vm\_nameservers) | Explicit DNS server override; otherwise use NetBox DNS VIPs. | `list(string)` | `[]` | no |
| <a name="input_vm_network_bridge"></a> [vm\_network\_bridge](#input\_vm\_network\_bridge) | n/a | `string` | `"vmbr1"` | no |
| <a name="input_vm_on_boot"></a> [vm\_on\_boot](#input\_vm\_on\_boot) | Automatically boot the staged VM with its Proxmox node. | `bool` | `false` | no |
| <a name="input_vm_protection"></a> [vm\_protection](#input\_vm\_protection) | n/a | `bool` | `false` | no |
| <a name="input_vm_search_domain"></a> [vm\_search\_domain](#input\_vm\_search\_domain) | Explicit search-domain override; otherwise use NetBox internal\_zone. | `string` | `""` | no |
| <a name="input_vm_started"></a> [vm\_started](#input\_vm\_started) | Start the staged VM after a separately authorised apply. | `bool` | `true` | no |
| <a name="input_vm_storage"></a> [vm\_storage](#input\_vm\_storage) | Storage for the new clone's system disk, cloud-init drive and EFI variables disk. | `string` | n/a | yes |
| <a name="input_vm_vlan_id"></a> [vm\_vlan\_id](#input\_vm\_vlan\_id) | n/a | `number` | `null` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_vm_id"></a> [vm\_id](#output\_vm\_id) | Proxmox VMID of the staged Rocky management VM. |
| <a name="output_vm_ipv4_address"></a> [vm\_ipv4\_address](#output\_vm\_ipv4\_address) | Configured IPv4 CIDR; this is not a guest-agent reachability check. |
| <a name="output_vm_name"></a> [vm\_name](#output\_vm\_name) | Proxmox name of the staged Rocky management VM. |
<!-- END_TF_DOCS -->