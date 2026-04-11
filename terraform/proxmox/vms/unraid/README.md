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

**Note: I create these via the mappings/resources role**

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