<!-- BEGIN_TF_DOCS -->
## Modules

| Name | Source | Version |
|------|--------|---------|
| <a name="module_n8n_vm"></a> [n8n\_vm](#module\_n8n\_vm) | ../../modules/ubuntu-cloudinit-vm | n/a |

## Resources

| Name | Type |
|------|------|
| [terraform_remote_state.netbox](https://registry.terraform.io/providers/hashicorp/terraform/latest/docs/data-sources/remote_state) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_clone_template_vm_id"></a> [clone\_template\_vm\_id](#input\_clone\_template\_vm\_id) | VMID of the Ubuntu 26.04 LTS (Resolute) cloud-init template. | `number` | n/a | yes |
| <a name="input_cloud_init_user"></a> [cloud\_init\_user](#input\_cloud\_init\_user) | Cloud-init administrative username. | `string` | `"ubuntu"` | no |
| <a name="input_dns_ips"></a> [dns\_ips](#input\_dns\_ips) | Fallback DNS VIP map, normally sourced from NetBox outputs. | `map(string)` | `{}` | no |
| <a name="input_enable_netbox_remote_state"></a> [enable\_netbox\_remote\_state](#input\_enable\_netbox\_remote\_state) | Read DNS topology from the terraform/netbox local state. | `bool` | `true` | no |
| <a name="input_netbox_state_path"></a> [netbox\_state\_path](#input\_netbox\_state\_path) | Path to the terraform/netbox state file. | `string` | `"../../../netbox/terraform.tfstate"` | no |
| <a name="input_pm_api_token"></a> [pm\_api\_token](#input\_pm\_api\_token) | Proxmox API token in user@realm!tokenid=secret format. | `string` | n/a | yes |
| <a name="input_pm_api_url"></a> [pm\_api\_url](#input\_pm\_api\_url) | Proxmox API URL, for example https://pve.example.com:8006/. | `string` | n/a | yes |
| <a name="input_pm_ssh_host"></a> [pm\_ssh\_host](#input\_pm\_ssh\_host) | SSH address of the target Proxmox node. | `string` | n/a | yes |
| <a name="input_pm_ssh_port"></a> [pm\_ssh\_port](#input\_pm\_ssh\_port) | SSH port of the target Proxmox node. | `number` | `22` | no |
| <a name="input_pm_ssh_username"></a> [pm\_ssh\_username](#input\_pm\_ssh\_username) | SSH username used by the Proxmox provider for snippet operations. | `string` | `"root"` | no |
| <a name="input_pm_tls_insecure"></a> [pm\_tls\_insecure](#input\_pm\_tls\_insecure) | Disable Proxmox API TLS certificate verification. Keep false when the Proxmox CA is trusted; set true only for an explicitly accepted self-signed or untrusted certificate. | `bool` | `false` | no |
| <a name="input_qemu_agent_enabled"></a> [qemu\_agent\_enabled](#input\_qemu\_agent\_enabled) | Enable QEMU guest-agent integration. | `bool` | `true` | no |
| <a name="input_qemu_guest_agent_bootstrap_enabled"></a> [qemu\_guest\_agent\_bootstrap\_enabled](#input\_qemu\_guest\_agent\_bootstrap\_enabled) | Install qemu-guest-agent during first boot so Proxmox can bootstrap the guest. | `bool` | `true` | no |
| <a name="input_snippet_storage"></a> [snippet\_storage](#input\_snippet\_storage) | Proxmox snippets datastore for optional cloud-init vendor data. | `string` | `"local"` | no |
| <a name="input_ssh_public_key_path"></a> [ssh\_public\_key\_path](#input\_ssh\_public\_key\_path) | Local path to the SSH public key installed by cloud-init. | `string` | n/a | yes |
| <a name="input_target_node"></a> [target\_node](#input\_target\_node) | Proxmox node on which to create the n8n VM. | `string` | n/a | yes |
| <a name="input_vm_ballooning_memory_mb"></a> [vm\_ballooning\_memory\_mb](#input\_vm\_ballooning\_memory\_mb) | Minimum ballooned memory in MiB; 0 disables ballooning. | `number` | `0` | no |
| <a name="input_vm_cpu_cores"></a> [vm\_cpu\_cores](#input\_vm\_cpu\_cores) | Number of n8n VM virtual CPU cores. | `number` | `2` | no |
| <a name="input_vm_cpu_sockets"></a> [vm\_cpu\_sockets](#input\_vm\_cpu\_sockets) | Number of n8n VM virtual CPU sockets. | `number` | `1` | no |
| <a name="input_vm_cpu_type"></a> [vm\_cpu\_type](#input\_vm\_cpu\_type) | Proxmox CPU type exposed to the n8n VM. | `string` | `"host"` | no |
| <a name="input_vm_description"></a> [vm\_description](#input\_vm\_description) | Proxmox VM description. | `string` | `"Isolated n8n automation VM managed by OpenTofu"` | no |
| <a name="input_vm_disk_size_gb"></a> [vm\_disk\_size\_gb](#input\_vm\_disk\_size\_gb) | n8n VM system disk size in GiB. | `number` | `24` | no |
| <a name="input_vm_id"></a> [vm\_id](#input\_vm\_id) | VMID assigned to the n8n VM. | `number` | n/a | yes |
| <a name="input_vm_ipv4_address"></a> [vm\_ipv4\_address](#input\_vm\_ipv4\_address) | Static n8n VM IPv4 address in CIDR notation. | `string` | n/a | yes |
| <a name="input_vm_ipv4_gateway"></a> [vm\_ipv4\_gateway](#input\_vm\_ipv4\_gateway) | IPv4 default gateway for the n8n VM. | `string` | n/a | yes |
| <a name="input_vm_memory_mb"></a> [vm\_memory\_mb](#input\_vm\_memory\_mb) | Dedicated memory for the n8n VM in MiB. | `number` | `2048` | no |
| <a name="input_vm_name"></a> [vm\_name](#input\_vm\_name) | Proxmox VM name. | `string` | `"n8n"` | no |
| <a name="input_vm_nameservers"></a> [vm\_nameservers](#input\_vm\_nameservers) | Fallback DNS servers used when NetBox remote state is disabled. | `list(string)` | `[]` | no |
| <a name="input_vm_network_bridge"></a> [vm\_network\_bridge](#input\_vm\_network\_bridge) | Proxmox bridge connected to the n8n VM. | `string` | `"vmbr0"` | no |
| <a name="input_vm_on_boot"></a> [vm\_on\_boot](#input\_vm\_on\_boot) | Start the n8n VM when the Proxmox node boots. | `bool` | `true` | no |
| <a name="input_vm_protection"></a> [vm\_protection](#input\_vm\_protection) | Enable Proxmox VM protection. | `bool` | `false` | no |
| <a name="input_vm_search_domain"></a> [vm\_search\_domain](#input\_vm\_search\_domain) | Fallback DNS search domain used when NetBox does not supply one. | `string` | `""` | no |
| <a name="input_vm_started"></a> [vm\_started](#input\_vm\_started) | Ensure the n8n VM is started after creation. | `bool` | `true` | no |
| <a name="input_vm_storage"></a> [vm\_storage](#input\_vm\_storage) | Proxmox datastore for VM and cloud-init disks. | `string` | n/a | yes |
| <a name="input_vm_tags"></a> [vm\_tags](#input\_vm\_tags) | Tags applied to the n8n VM in Proxmox. | `list(string)` | <pre>[<br/>  "terraform",<br/>  "ubuntu",<br/>  "automation",<br/>  "n8n"<br/>]</pre> | no |
| <a name="input_vm_vlan_id"></a> [vm\_vlan\_id](#input\_vm\_vlan\_id) | Optional VLAN tag for the n8n VM. | `number` | `null` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_n8n_vm_id"></a> [n8n\_vm\_id](#output\_n8n\_vm\_id) | Proxmox VMID assigned to the n8n VM. |
| <a name="output_n8n_vm_ipv4_address"></a> [n8n\_vm\_ipv4\_address](#output\_n8n\_vm\_ipv4\_address) | Static IPv4 address configured for the n8n VM. |
| <a name="output_n8n_vm_name"></a> [n8n\_vm\_name](#output\_n8n\_vm\_name) | Proxmox name of the n8n VM. |
<!-- END_TF_DOCS -->