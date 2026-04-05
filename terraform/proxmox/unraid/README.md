# Unraid VM Terraform Workflow

## Purpose

The Unraid VM is a special-case VM, as:
- it is imported into Terraform, rather than based on a cloud-init template
- it uses a manually attached UnRaid boot USB (aka no vdisk)
- it uses pre-existing resource mappings for HBA/NIC/Cache drive
- it uses settings that require root permissions to be set manually after VM creation.

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

## Proxmox Prerequisites

Before using this Terraform root, create the required Proxmox resource mappings manually.

### Required PCI mappings

The VM uses the following PCI resource mappings in Proxmox:

- `Adaptec-UnRaid` - HBA passthrough
- `X710-UnRaid` - NIC passthrough
- `FireCuda-Swarm` - Cache (NVME) passthrough

**Note: Handle manually _before_ the VM creation.**

### USB boot device

The VM uses a raw passthrough for the UnRaid boot USB

Currently, this mapping is:

```text
usb0: host=6-3
```
**Note: Set manually _after_ VM creation.**

## Terraform workflow

From the `terraform/proxmox/unraid/` directory:

If the VM doesn't exist:

```bash
terraform fmt
terraform init
terraform validate
terraform plan
terraform apply
```

If importing an existing VM:

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
hostpci0: mapping=Adaptec-UnRaid
hostpci1: mapping=X710-UnRaid
hostpci2: mapping=FireCuda-Swarm
usb0: host=6-3
```
