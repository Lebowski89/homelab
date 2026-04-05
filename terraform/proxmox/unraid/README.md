# Unraid VM Terraform Workflow

This document covers the workflow for managing the Unraid VM in Proxmox with Terraform.

## Purpose

The Unraid VM is a special-case VM.

Unlike the PostgreSQL VMs, this VM:

- is imported into Terraform rather than created from a cloud-init template
- uses PCI passthrough via Proxmox resource mappings
- uses a manually attached boot USB device
- requires a manual Proxmox `args` setting

Terraform is used here mainly to:

- track the VM config as code
- document the intended VM layout
- detect drift
- make rebuilds easier if needed

It is not intended for casual destroy/recreate.

## Proxmox prerequisites before Terraform

Before using this Terraform root, create the required Proxmox resource mappings manually.

### Required PCI mappings

Create these PCI resource mappings in Proxmox:

- `Adaptec-UnRaid`
- `X710-UnRaid`
- `FireCuda-Swarm`

These are used by the Unraid VM for:

- HBA passthrough
- NIC passthrough
- other passthrough hardware as currently configured

### USB boot device

Do not use a Proxmox USB resource mapping for the Unraid boot USB.

Use the known-good raw USB passthrough instead:

```text
usb0: host=6-3
```

This is handled manually after the VM exists.

## Terraform workflow

From the `terraform/proxmox/unraid/` directory:

```bash
terraform init
terraform plan
```

If importing the existing VM:

```bash
terraform import proxmox_vm_qemu.unraid pve1/qemu/100
terraform plan
```

## What Terraform manages

Terraform manages and tracks:

- VM name
- VMID
- target node
- CPU and memory
- machine type / BIOS
- PCI resource mappings
- protection flag
- general VM config that is safe to track

## What Terraform does not manage

Terraform intentionally does not manage these parts of the Unraid VM:

- boot USB attachment
- Proxmox `args`
- some hardware-related fields that are intentionally ignored
- other imported/provider-noise fields covered by `ignore_changes`

## Manual steps required after Terraform creates the Unraid VM

If Terraform is used to create a new Unraid VM, do the following manually in Proxmox after creation.

### 1. Attach the Unraid boot USB manually

Power the VM off first, then attach the boot USB using the known-good raw USB path:

```bash
qm set <VMID> --usb0 host=6-3
```

Example:

```bash
qm set 100 --usb0 host=6-3
```

### 2. Set the VM boot order

Set the VM to boot from `usb0`:

```bash
qm set <VMID> --boot order=usb0
```

Example:

```bash
qm set 100 --boot order=usb0
```

### 3. Set the required Proxmox args

This VM requires:

```text
args: -device amd-iommu
```

Set it manually:

```bash
qm set <VMID> --args "-device amd-iommu"
```

Example:

```bash
qm set 100 --args "-device amd-iommu"
```

### 4. Verify the final VM config

Check the important lines:

```bash
qm config <VMID> | egrep 'boot|usb0|args|hostpci'
```

Expected output shape:

```text
args: -device amd-iommu
boot: order=usb0
hostpci0: mapping=Adaptec-UnRaid
hostpci1: mapping=X710-UnRaid
hostpci2: mapping=FireCuda-Swarm
usb0: host=6-3
```

### 5. Start the VM

```bash
qm start <VMID>
```

Example:

```bash
qm start 100
```

## Manual steps required after import

If the VM already exists and is imported into Terraform, verify that these settings remain correct:

```bash
qm config <VMID> | egrep 'boot|usb0|args|hostpci'
```

Expected:

```text
args: -device amd-iommu
boot: order=usb0
hostpci0: mapping=Adaptec-UnRaid
hostpci1: mapping=X710-UnRaid
hostpci2: mapping=FireCuda-Swarm
usb0: host=6-3
```

## Important notes

### Boot USB

Do not switch the Unraid boot USB to a Proxmox USB resource mapping.

The known-good setup is:

```text
usb0: host=6-3
boot: order=usb0
```

### Proxmox args

Terraform does not manage:

```text
args: -device amd-iommu
```

This must remain a manual Proxmox setting.

### Do not hot-change passthrough while running

Do not change these while the VM is running:

- `usb0`
- `hostpci*`
- boot order
- `args`
- raw disk passthrough

Make those changes only while powered off.

## Safety checks after boot

After the VM is back up, verify storage health inside Unraid:

```bash
zpool status
```

Healthy output should show pools `ONLINE` and no known data errors.

## Recommended Terraform workflow for this VM

Use Terraform for:

- import
- tracking
- drift detection
- safe metadata/config tracking

Do not treat this VM like a disposable cloud-init VM.

Always run:

```bash
terraform plan
```

before applying anything.

If Terraform ever wants to replace the VM, stop and review before doing anything.

## Summary

### Manual prerequisites before Terraform

Create PCI resource mappings:

- `Adaptec-UnRaid`
- `X710-UnRaid`
- `FireCuda-Swarm`

### Manual post-create steps after Terraform

Attach boot USB manually:

```bash
qm set <VMID> --usb0 host=6-3
```

Set boot order:

```bash
qm set <VMID> --boot order=usb0
```

Set manual args:

```bash
qm set <VMID> --args "-device amd-iommu"
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
