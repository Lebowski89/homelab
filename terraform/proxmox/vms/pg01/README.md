<!-- BEGIN_TF_DOCS -->
## Modules

| Name | Source | Version |
|------|--------|---------|
| <a name="module_postgres_vm"></a> [postgres\_vm](#module\_postgres\_vm) | ../../modules/cloudinit-vm/initialization-ignored | n/a |

## Resources

| Name | Type |
|------|------|
| [terraform_remote_state.netbox](https://registry.terraform.io/providers/hashicorp/terraform/latest/docs/data-sources/remote_state) | data source |
| [terraform_remote_state.ubuntu_template](https://registry.terraform.io/providers/hashicorp/terraform/latest/docs/data-sources/remote_state) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_ci_user"></a> [ci\_user](#input\_ci\_user) | n/a | `string` | `"ubuntu"` | no |
| <a name="input_clone_template_vmid"></a> [clone\_template\_vmid](#input\_clone\_template\_vmid) | Default Proxmox Cloud-Init template VMID for PostgreSQL nodes | `number` | n/a | yes |
| <a name="input_default_tags"></a> [default\_tags](#input\_default\_tags) | n/a | `string` | `"terraform;postgres;patroni"` | no |
| <a name="input_dns_ips"></a> [dns\_ips](#input\_dns\_ips) | Fallback DNS node/VIP IPs. Normally sourced from terraform/netbox outputs.dns\_ips. | `map(string)` | `{}` | no |
| <a name="input_enable_netbox_remote_state"></a> [enable\_netbox\_remote\_state](#input\_enable\_netbox\_remote\_state) | Read DNS topology data from the terraform/netbox local state. | `bool` | `true` | no |
| <a name="input_guest_agent_vendor_data_file_id"></a> [guest\_agent\_vendor\_data\_file\_id](#input\_guest\_agent\_vendor\_data\_file\_id) | Optional explicit existing vendor-data ID for bootstrap use. Null reads the Ubuntu template owner's output; this root never owns the shared file. | `string` | `null` | no |
| <a name="input_netbox_state_path"></a> [netbox\_state\_path](#input\_netbox\_state\_path) | Path to the terraform/netbox state file. | `string` | `"../../../netbox/terraform.tfstate"` | no |
| <a name="input_pm_api_token"></a> [pm\_api\_token](#input\_pm\_api\_token) | Terraform Proxmox API token in format user@realm!tokenid=secret | `string` | n/a | yes |
| <a name="input_pm_api_url"></a> [pm\_api\_url](#input\_pm\_api\_url) | Proxmox API URL, e.g. https://pve.example.com:8006/ | `string` | n/a | yes |
| <a name="input_pm_ssh_host"></a> [pm\_ssh\_host](#input\_pm\_ssh\_host) | n/a | `string` | n/a | yes |
| <a name="input_pm_ssh_port"></a> [pm\_ssh\_port](#input\_pm\_ssh\_port) | SSH port of the target Proxmox node. | `number` | `22` | no |
| <a name="input_pm_ssh_username"></a> [pm\_ssh\_username](#input\_pm\_ssh\_username) | n/a | `string` | `"root"` | no |
| <a name="input_pm_tls_insecure"></a> [pm\_tls\_insecure](#input\_pm\_tls\_insecure) | Disable Proxmox API TLS certificate verification. Keep false when the Proxmox CA is trusted; set true only for an explicitly accepted self-signed or untrusted certificate. | `bool` | `false` | no |
| <a name="input_postgres_vm"></a> [postgres\_vm](#input\_postgres\_vm) | One existing PostgreSQL VM. Root directory names do not rename the guest. | <pre>object({<br/>    name                = string<br/>    vmid                = number<br/>    ip                  = string<br/>    cores               = number<br/>    sockets             = number<br/>    memory              = number<br/>    disk_size_gb        = number<br/>    clone_template_vmid = optional(number)<br/>    vlan_tag            = optional(number)<br/>    onboot              = optional(bool, true)<br/>    ci_user             = optional(string)<br/>  })</pre> | n/a | yes |
| <a name="input_ssh_public_key_path"></a> [ssh\_public\_key\_path](#input\_ssh\_public\_key\_path) | n/a | `string` | n/a | yes |
| <a name="input_target_node"></a> [target\_node](#input\_target\_node) | Proxmox node on which the VM and its local storage reside | `string` | n/a | yes |
| <a name="input_ubuntu_template_state_path"></a> [ubuntu\_template\_state\_path](#input\_ubuntu\_template\_state\_path) | Authoritative local Ubuntu 26.04 template state exporting qemu\_guest\_agent\_vendor\_data\_file\_id; used unless an explicit vendor-data ID is supplied. | `string` | `"../../templates/ubuntu-2604/terraform.tfstate"` | no |
| <a name="input_vm_bridge"></a> [vm\_bridge](#input\_vm\_bridge) | n/a | `string` | `"vmbr0"` | no |
| <a name="input_vm_cidr"></a> [vm\_cidr](#input\_vm\_cidr) | n/a | `number` | `24` | no |
| <a name="input_vm_gateway"></a> [vm\_gateway](#input\_vm\_gateway) | n/a | `string` | n/a | yes |
| <a name="input_vm_nameserver"></a> [vm\_nameserver](#input\_vm\_nameserver) | Optional space-separated VM DNS nameserver fallback. Ignored while enable\_netbox\_remote\_state is true. | `string` | `""` | no |
| <a name="input_vm_searchdomain"></a> [vm\_searchdomain](#input\_vm\_searchdomain) | Optional VM DNS search domain fallback. Ignored while enable\_netbox\_remote\_state is true. | `string` | `""` | no |
| <a name="input_vm_storage"></a> [vm\_storage](#input\_vm\_storage) | Proxmox datastore for VM disks and cloud-init disks | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_postgres_vm_ips"></a> [postgres\_vm\_ips](#output\_postgres\_vm\_ips) | Configured VM addresses owned by this root (one entry). |
| <a name="output_postgres_vm_names"></a> [postgres\_vm\_names](#output\_postgres\_vm\_names) | VM names owned by this root (one entry; retains the former output shape). |
| <a name="output_vm_id"></a> [vm\_id](#output\_vm\_id) | Existing Proxmox VMID owned by this root. |
<!-- END_TF_DOCS -->