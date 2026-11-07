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

The guest agent is disabled until a clone installs and starts it. Configure the
clone through the existing system baseline and NetBox inventory; do not put host
identity or OS configuration in service definitions. SELinux and firewalld
retain their distribution policies. Application storage, runtime networking and
protected traffic still require isolated live acceptance.

Only formatting and repository checks have been performed for this stack.
No provider initialization, plan, apply, image import or boot test is implied.
Generated Terraform READMEs remain owned by the documentation workflow.
