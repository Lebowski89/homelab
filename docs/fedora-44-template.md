# Fedora 44 AMD64 cloud template

`terraform/proxmox/templates/fedora-44` follows the existing Ubuntu/Rocky
template stacks. It creates a stopped UEFI/Q35 template from the conventional
Fedora Cloud Base image, with an explicit unused VMID and node-local download
storage. It does not create a VM clone, change NetBox or deploy applications.
Fedora 44 is selected because it overlaps the implemented PostgreSQL platform
boundary; this does not certify the entire application catalog on Fedora.

The pinned image is
`Fedora-Cloud-Base-Generic-44-1.7.x86_64.qcow2`, from Fedora's
[official release directory](https://dl.fedoraproject.org/pub/fedora/linux/releases/44/Cloud/x86_64/images/).
Its SHA-256 is taken from the official
[signed checksum file](https://dl.fedoraproject.org/pub/fedora/linux/releases/44/Cloud/x86_64/images/Fedora-Cloud-44-1.7-x86_64-CHECKSUM).
The QCOW2 header declares a 5 GiB virtual disk; clones may grow it. The `.img`
storage filename retains the QCOW2 payload, following the existing PVE storage
convention. Review the URL and checksum together when updating the image.

Supply the existing provider inputs privately: `pm_api_url`, `pm_api_token`,
`pm_ssh_username`, `pm_ssh_host`, plus `target_node`, `vm_storage`,
`template_vmid` and `ssh_public_key_path`. The default cloud user is `fedora`.
TLS verification stays enabled unless explicitly overridden. Never reuse an
existing VMID or treat a template change as permission to replace a VM.

The adjacent `terraform.tfvars.sample`, `private.auto.tfvars.sample` and
`secrets.auto.tfvars.sample` provide the template inputs. Copy them to their
corresponding ignored names without `.sample` and supply connection credentials
privately. Local inputs have been prepared from the Rocky template, using
`fedora-44-cloudinit-template`, user `fedora` and template VMID `9005` to match
the Fedora clone. This VMID is not a verified allocation; confirm it is unused.
Rocky's template and its state remain separate. The Fedora image URL/checksum
defaults are retained; no Rocky image or provider cache is copied.

Provision the template root before the VM root:

```bash
cd terraform/proxmox/templates/fedora-44
tofu init
tofu plan
tofu apply
```

Run those commands only when deliberately provisioning, using the repository's
pinned OpenTofu version. They have not been run as part of input preparation.

The guest agent is disabled until a clone installs and starts it. Configure the
clone through the existing system baseline and NetBox inventory; do not put host
identity or OS configuration in service definitions. SELinux and firewalld
retain their distribution policies. Application storage, runtime networking and
protected traffic still require isolated live acceptance.

Only formatting and repository checks have been performed for this stack.
No provider initialization, plan, apply, image import or boot test is implied.
Generated Terraform READMEs remain owned by the documentation workflow.

## Test VM clone

`terraform/proxmox/vms/fedora` clones this template using the existing shared
cloud-init VM module. It retains Rocky's UEFI/Q35, storage/network configuration
and guest-agent bootstrap, with the `fedora` cloud user and a separate state root.
It does not manage NetBox membership, Ansible roles, Swarm or applications.

Copy `terraform.tfvars.sample` to the ignored `terraform.tfvars` and supply the
private connection inputs using the adjacent samples. The proposed VMID 9101
and template VMID 9005 are explicit examples, not verified allocations: confirm
availability and build the Fedora template with the matching template VMID first.
Keep the template and VM on the same Proxmox node when using node-local storage.

The requested local VM address is `192.168.80.44/24`, using Rocky's existing
network prefix. Set it through the ignored `private.auto.tfvars`; gateway, DNS
and connection settings can be copied from Rocky's private inputs. Never copy
its Terraform state or provider cache. Explicit network inputs take precedence
over optional NetBox state fallbacks, as in the Rocky root. No remote state is
read when `enable_netbox_remote_state = false`.

Review VMIDs and the resulting plan before a separately authorized apply. The
repository checks do not establish successful clone provisioning or boot
validation; generated READMEs remain CI-owned.
