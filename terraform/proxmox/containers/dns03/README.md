<!-- BEGIN_TF_DOCS -->


## Resources

| Name | Type |
|------|------|
| [terraform_remote_state.netbox](https://registry.terraform.io/providers/hashicorp/terraform/latest/docs/data-sources/remote_state) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_container_bridge"></a> [container\_bridge](#input\_container\_bridge) | Proxmox bridge used by the dns03 LXC. | `string` | `"vmbr0"` | no |
| <a name="input_container_cores"></a> [container\_cores](#input\_container\_cores) | CPU cores assigned to the dns03 LXC. | `number` | `1` | no |
| <a name="input_container_description"></a> [container\_description](#input\_container\_description) | Description shown in Proxmox for the dns03 LXC. | `string` | `"Technitium DNS tertiary LXC managed by OpenTofu"` | no |
| <a name="input_container_disk_size"></a> [container\_disk\_size](#input\_container\_disk\_size) | Root disk size for the dns03 LXC. | `number` | `8` | no |
| <a name="input_container_dns_domain"></a> [container\_dns\_domain](#input\_container\_dns\_domain) | Optional container DNS search domain fallback. Ignored while enable\_netbox\_remote\_state is true. | `string` | `""` | no |
| <a name="input_container_dns_servers"></a> [container\_dns\_servers](#input\_container\_dns\_servers) | Optional container DNS servers fallback. Ignored while enable\_netbox\_remote\_state is true. | `list(string)` | `[]` | no |
| <a name="input_container_gateway"></a> [container\_gateway](#input\_container\_gateway) | Optional explicit container default gateway fallback. Defaults to cidrhost(container\_ip, container\_gateway\_host\_number). | `string` | `""` | no |
| <a name="input_container_gateway_host_number"></a> [container\_gateway\_host\_number](#input\_container\_gateway\_host\_number) | Host number used to derive the default gateway from container\_ip when container\_gateway is empty. | `number` | `1` | no |
| <a name="input_container_hostname"></a> [container\_hostname](#input\_container\_hostname) | Hostname for the dns03 LXC. Also used as the NetBox host key when deriving the container IP. | `string` | `"dns03"` | no |
| <a name="input_container_ip"></a> [container\_ip](#input\_container\_ip) | Optional explicit dns03 container CIDR address fallback. Defaults to NetBox host\_primary\_ipv4[container\_hostname]/container\_prefix\_length. | `string` | `""` | no |
| <a name="input_container_memory"></a> [container\_memory](#input\_container\_memory) | Memory assigned to the dns03 LXC in MiB. | `number` | `512` | no |
| <a name="input_container_prefix_length"></a> [container\_prefix\_length](#input\_container\_prefix\_length) | CIDR prefix length used when deriving container\_ip from NetBox host\_primary\_ipv4. | `number` | `24` | no |
| <a name="input_container_protection"></a> [container\_protection](#input\_container\_protection) | Enable Proxmox protection on the dns03 LXC. | `bool` | `false` | no |
| <a name="input_container_storage"></a> [container\_storage](#input\_container\_storage) | Proxmox datastore for the dns03 LXC root disk. | `string` | `"local-zfs"` | no |
| <a name="input_container_swap"></a> [container\_swap](#input\_container\_swap) | Swap assigned to the dns03 LXC in MiB. | `number` | `512` | no |
| <a name="input_container_vmid"></a> [container\_vmid](#input\_container\_vmid) | Proxmox VMID for the dns03 LXC. | `number` | `253` | no |
| <a name="input_dns_ips"></a> [dns\_ips](#input\_dns\_ips) | Fallback DNS node/VIP IPs. Normally sourced from terraform/netbox outputs.dns\_ips. | `map(string)` | `{}` | no |
| <a name="input_enable_netbox_remote_state"></a> [enable\_netbox\_remote\_state](#input\_enable\_netbox\_remote\_state) | Read DNS and host topology data from the terraform/netbox local state. | `bool` | `true` | no |
| <a name="input_netbox_state_path"></a> [netbox\_state\_path](#input\_netbox\_state\_path) | Path to the terraform/netbox state file. | `string` | `"../../../netbox/terraform.tfstate"` | no |
| <a name="input_pm_api_port"></a> [pm\_api\_port](#input\_pm\_api\_port) | Proxmox API port. | `number` | `8006` | no |
| <a name="input_pm_api_token"></a> [pm\_api\_token](#input\_pm\_api\_token) | Proxmox API token. | `string` | n/a | yes |
| <a name="input_pm_api_url"></a> [pm\_api\_url](#input\_pm\_api\_url) | Optional explicit Proxmox API URL fallback. Defaults to https://<target\_node\_ip>:<pm\_api\_port>/ from NetBox. | `string` | `""` | no |
| <a name="input_pm_ssh_host"></a> [pm\_ssh\_host](#input\_pm\_ssh\_host) | Optional explicit Proxmox SSH host fallback. Defaults to target\_node IP from NetBox. | `string` | `""` | no |
| <a name="input_pm_ssh_port"></a> [pm\_ssh\_port](#input\_pm\_ssh\_port) | Proxmox SSH port. | `number` | `22` | no |
| <a name="input_pm_ssh_username"></a> [pm\_ssh\_username](#input\_pm\_ssh\_username) | SSH username used to run pct commands on the Proxmox host. | `string` | `"root"` | no |
| <a name="input_pm_tls_insecure"></a> [pm\_tls\_insecure](#input\_pm\_tls\_insecure) | Disable Proxmox API TLS certificate verification. Keep false when the Proxmox CA is trusted; set true only for an explicitly accepted self-signed or untrusted certificate. | `bool` | `false` | no |
| <a name="input_ssh_public_key_path"></a> [ssh\_public\_key\_path](#input\_ssh\_public\_key\_path) | Path to the SSH public key injected into the dns03 LXC. | `string` | n/a | yes |
| <a name="input_tailscale_auth_key"></a> [tailscale\_auth\_key](#input\_tailscale\_auth\_key) | Ephemeral/auth key used to join the dns03 LXC to Tailscale. | `string` | n/a | yes |
| <a name="input_target_node"></a> [target\_node](#input\_target\_node) | Proxmox node that hosts the dns03 LXC. | `string` | `"pve1"` | no |
| <a name="input_template_file_id"></a> [template\_file\_id](#input\_template\_file\_id) | Ubuntu LXC template file ID. | `string` | `"local:vztmpl/noble-server-cloudimg-amd64-root.tar.xz"` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_dns03_container_id"></a> [dns03\_container\_id](#output\_dns03\_container\_id) | n/a |
| <a name="output_dns03_hostname"></a> [dns03\_hostname](#output\_dns03\_hostname) | n/a |
| <a name="output_dns03_ipv4"></a> [dns03\_ipv4](#output\_dns03\_ipv4) | n/a |
| <a name="output_dns03_vmid"></a> [dns03\_vmid](#output\_dns03\_vmid) | n/a |
<!-- END_TF_DOCS -->