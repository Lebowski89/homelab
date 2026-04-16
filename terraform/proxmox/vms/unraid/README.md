# Unraid VM Terraform Workflow

## Purpose

The Unraid VM is a special-case VM, as:
- it is imported into Terraform, rather than based on a cloud-init template
- it uses pre-existing resource mappings for Boot/HBA/NIC/Cache drive

Terraform manages and tracks:

- VM name
- VMID
- target node
- CPU and memory
- machine type / BIOS
- PCI resource mappings
- protection flag
- general VM config that is safe to track

**What it isn't for: Casual destroy/create.**

### Required PCI mappings

The VM uses the following PCI resource mappings in Proxmox:

- `UnRaid-Boot` - USB Boot Key
- `UnRaid-Cache` - Cache (NVME) passthrough
- `UnRaid-HBA` - SAS HBA passthrough
- `UnRaid-NIC` - SFP+ NIC passthrough

**Note: I create these via the mappings/resources module**

## Terraform workflow

From the `terraform/proxmox/vms/unraid/` directory:

New:

```bash
terraform fmt
terraform init
terraform validate
terraform plan
terraform apply
```

Import existing:

```bash
terraform fmt
terraform init
terraform validate
terraform import proxmox_vm_qemu.unraid pve1/qemu/100
terraform plan
```

## Relevant PVE commands

```bash
qm set <VMID> --usb0 host=6-3  # Attach boot USB manually
qm set <VMID> --boot order=usb0  # Set boot order
qm config <VMID> | egrep 'boot|usb0|args|hostpci'  # Verify boot order
qm set <VMID> --args "-device amd-iommu"  # Set manual args
```

### Known-good final state

```text
args: -device amd-iommu
boot: order=usb0
hostpci0: mapping=UnRaid-Cache
hostpci1: mapping=UnRaid-HBA
hostpci2: mapping=UnRaid-NIC
usb0: mapping=UnRaid-Boot
```

<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | 1.11.6 |
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
| [proxmox_virtual_environment_vm.unraid](https://registry.terraform.io/providers/bpg/proxmox/0.102.0/docs/resources/virtual_environment_vm) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_pm_api_token"></a> [pm\_api\_token](#input\_pm\_api\_token) | n/a | `string` | n/a | yes |
| <a name="input_pm_api_url"></a> [pm\_api\_url](#input\_pm\_api\_url) | n/a | `string` | n/a | yes |
| <a name="input_pm_tls_insecure"></a> [pm\_tls\_insecure](#input\_pm\_tls\_insecure) | n/a | `bool` | `true` | no |
| <a name="input_target_node"></a> [target\_node](#input\_target\_node) | n/a | `string` | n/a | yes |
| <a name="input_unraid_bios"></a> [unraid\_bios](#input\_unraid\_bios) | n/a | `string` | `"seabios"` | no |
| <a name="input_unraid_boot_mapping"></a> [unraid\_boot\_mapping](#input\_unraid\_boot\_mapping) | n/a | `string` | `"UnRaid-Boot"` | no |
| <a name="input_unraid_boot_order"></a> [unraid\_boot\_order](#input\_unraid\_boot\_order) | n/a | `list(string)` | <pre>[<br/>  "usb0"<br/>]</pre> | no |
| <a name="input_unraid_cache_mapping"></a> [unraid\_cache\_mapping](#input\_unraid\_cache\_mapping) | n/a | `string` | `"UnRaid-Cache"` | no |
| <a name="input_unraid_cores"></a> [unraid\_cores](#input\_unraid\_cores) | n/a | `number` | `8` | no |
| <a name="input_unraid_cpu_flags"></a> [unraid\_cpu\_flags](#input\_unraid\_cpu\_flags) | n/a | `list(string)` | <pre>[<br/>  "+pcid"<br/>]</pre> | no |
| <a name="input_unraid_hba_mapping"></a> [unraid\_hba\_mapping](#input\_unraid\_hba\_mapping) | n/a | `string` | `"UnRaid-HBA"` | no |
| <a name="input_unraid_kvm_arguments"></a> [unraid\_kvm\_arguments](#input\_unraid\_kvm\_arguments) | n/a | `string` | `"-device amd-iommu"` | no |
| <a name="input_unraid_machine"></a> [unraid\_machine](#input\_unraid\_machine) | n/a | `string` | `"q35"` | no |
| <a name="input_unraid_memory"></a> [unraid\_memory](#input\_unraid\_memory) | n/a | `number` | `32045` | no |
| <a name="input_unraid_name"></a> [unraid\_name](#input\_unraid\_name) | n/a | `string` | `"UnRaid"` | no |
| <a name="input_unraid_nic_mapping"></a> [unraid\_nic\_mapping](#input\_unraid\_nic\_mapping) | n/a | `string` | `"UnRaid-NIC"` | no |
| <a name="input_unraid_qemu_os"></a> [unraid\_qemu\_os](#input\_unraid\_qemu\_os) | n/a | `string` | `"l26"` | no |
| <a name="input_unraid_scsihw"></a> [unraid\_scsihw](#input\_unraid\_scsihw) | n/a | `string` | `"virtio-scsi-single"` | no |
| <a name="input_unraid_sockets"></a> [unraid\_sockets](#input\_unraid\_sockets) | n/a | `number` | `1` | no |
| <a name="input_unraid_uuid"></a> [unraid\_uuid](#input\_unraid\_uuid) | n/a | `string` | `"ebfa68e3-e312-42de-8c08-a3c400754edb"` | no |
| <a name="input_unraid_vga_type"></a> [unraid\_vga\_type](#input\_unraid\_vga\_type) | n/a | `string` | `"qxl"` | no |
| <a name="input_unraid_vmid"></a> [unraid\_vmid](#input\_unraid\_vmid) | n/a | `number` | `100` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_unraid_vm_name"></a> [unraid\_vm\_name](#output\_unraid\_vm\_name) | n/a |
| <a name="output_unraid_vmid"></a> [unraid\_vmid](#output\_unraid\_vmid) | n/a |
<!-- END_TF_DOCS -->