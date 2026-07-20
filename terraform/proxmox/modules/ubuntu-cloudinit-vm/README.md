<!-- BEGIN_TF_DOCS -->


## Resources

| Name | Type |
|------|------|

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_ballooning_memory_mb"></a> [ballooning\_memory\_mb](#input\_ballooning\_memory\_mb) | Minimum ballooned memory in MiB; use 0 to disable ballooning. | `number` | `0` | no |
| <a name="input_clone_retries"></a> [clone\_retries](#input\_clone\_retries) | Number of clone retries requested from the Proxmox provider. | `number` | `3` | no |
| <a name="input_clone_template_vm_id"></a> [clone\_template\_vm\_id](#input\_clone\_template\_vm\_id) | VMID of the cloud-init template to clone. | `number` | n/a | yes |
| <a name="input_cloud_init_user"></a> [cloud\_init\_user](#input\_cloud\_init\_user) | Cloud-init administrative username. | `string` | `"ubuntu"` | no |
| <a name="input_cpu_cores"></a> [cpu\_cores](#input\_cpu\_cores) | Number of virtual CPU cores. | `number` | `2` | no |
| <a name="input_cpu_sockets"></a> [cpu\_sockets](#input\_cpu\_sockets) | Number of virtual CPU sockets. | `number` | `1` | no |
| <a name="input_cpu_type"></a> [cpu\_type](#input\_cpu\_type) | Proxmox CPU type. | `string` | `"host"` | no |
| <a name="input_datastore_id"></a> [datastore\_id](#input\_datastore\_id) | Proxmox datastore used for the VM disk and cloud-init disk. | `string` | n/a | yes |
| <a name="input_description"></a> [description](#input\_description) | Proxmox VM description. | `string` | `"Ubuntu cloud-init VM managed by OpenTofu"` | no |
| <a name="input_disk_size_gb"></a> [disk\_size\_gb](#input\_disk\_size\_gb) | VM system disk size in GiB. | `number` | `24` | no |
| <a name="input_dns_domain"></a> [dns\_domain](#input\_dns\_domain) | DNS search domain supplied through cloud-init. | `string` | `""` | no |
| <a name="input_dns_servers"></a> [dns\_servers](#input\_dns\_servers) | DNS servers supplied through cloud-init. | `list(string)` | n/a | yes |
| <a name="input_ipv4_address"></a> [ipv4\_address](#input\_ipv4\_address) | Static IPv4 address in CIDR notation. | `string` | n/a | yes |
| <a name="input_ipv4_gateway"></a> [ipv4\_gateway](#input\_ipv4\_gateway) | IPv4 default gateway. | `string` | n/a | yes |
| <a name="input_memory_mb"></a> [memory\_mb](#input\_memory\_mb) | Dedicated VM memory in MiB. | `number` | `2048` | no |
| <a name="input_name"></a> [name](#input\_name) | Proxmox VM name. | `string` | n/a | yes |
| <a name="input_network_bridge"></a> [network\_bridge](#input\_network\_bridge) | Proxmox bridge connected to the VM network interface. | `string` | `"vmbr0"` | no |
| <a name="input_node_name"></a> [node\_name](#input\_node\_name) | Proxmox node on which to create the VM. | `string` | n/a | yes |
| <a name="input_on_boot"></a> [on\_boot](#input\_on\_boot) | Start the VM automatically when the Proxmox node boots. | `bool` | `true` | no |
| <a name="input_protection"></a> [protection](#input\_protection) | Enable Proxmox VM protection. | `bool` | `false` | no |
| <a name="input_qemu_agent_enabled"></a> [qemu\_agent\_enabled](#input\_qemu\_agent\_enabled) | Enable the QEMU guest agent integration. | `bool` | `true` | no |
| <a name="input_ssh_public_keys"></a> [ssh\_public\_keys](#input\_ssh\_public\_keys) | SSH public keys installed for the cloud-init user. | `list(string)` | n/a | yes |
| <a name="input_started"></a> [started](#input\_started) | Ensure the VM is started after creation. | `bool` | `true` | no |
| <a name="input_tags"></a> [tags](#input\_tags) | Tags applied to the Proxmox VM. | `list(string)` | <pre>[<br/>  "terraform",<br/>  "ubuntu",<br/>  "cloud-init"<br/>]</pre> | no |
| <a name="input_vendor_data_file_id"></a> [vendor\_data\_file\_id](#input\_vendor\_data\_file\_id) | Optional Proxmox snippets file ID used as cloud-init vendor data. | `string` | `null` | no |
| <a name="input_vlan_id"></a> [vlan\_id](#input\_vlan\_id) | Optional VLAN tag for the VM network interface. | `number` | `null` | no |
| <a name="input_vm_id"></a> [vm\_id](#input\_vm\_id) | Proxmox VMID. | `number` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_id"></a> [id](#output\_id) | Provider resource ID for the VM. |
| <a name="output_ipv4_address"></a> [ipv4\_address](#output\_ipv4\_address) | Configured static IPv4 address in CIDR notation. |
| <a name="output_name"></a> [name](#output\_name) | Proxmox VM name. |
| <a name="output_vm_id"></a> [vm\_id](#output\_vm\_id) | Proxmox VMID. |
<!-- END_TF_DOCS -->