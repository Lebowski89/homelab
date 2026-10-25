mock_provider "proxmox" {}

variables {
  name                 = "offline-firmware-test"
  vm_id                = 99100
  node_name            = "offline-node"
  clone_template_vm_id = 99004
  datastore_id         = "selected-vm-storage"
  ipv4_address         = "192.0.2.10/24"
  ipv4_gateway         = "192.0.2.1"
  dns_servers          = ["192.0.2.53"]
  cloud_init_user      = "testuser"
  ssh_public_keys      = ["ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA offline@example.invalid"]
  qemu_agent_enabled   = false
}

run "existing_callers_leave_hardware_unset" {
  command = plan

  assert {
    condition = (
      proxmox_virtual_environment_vm.this.bios == null &&
      proxmox_virtual_environment_vm.this.machine == null &&
      length(proxmox_virtual_environment_vm.this.efi_disk) == 0
    )
    error_message = "Omitting hardware overrides must leave firmware and machine type unspecified for the provider, without adding an EFI disk."
  }
}

run "q35_can_keep_legacy_firmware" {
  command = plan

  variables {
    bios    = "seabios"
    machine = "q35"
  }

  assert {
    condition = (
      proxmox_virtual_environment_vm.this.bios == "seabios" &&
      proxmox_virtual_environment_vm.this.machine == "q35" &&
      length(proxmox_virtual_environment_vm.this.efi_disk) == 0
    )
    error_message = "Machine selection must remain independent of firmware and must not add EFI storage for SeaBIOS."
  }
}

run "ovmf_manages_persistent_efi_on_selected_storage" {
  command = plan

  variables {
    bios    = "ovmf"
    machine = "q35"
  }

  assert {
    condition = (
      proxmox_virtual_environment_vm.this.bios == "ovmf" &&
      proxmox_virtual_environment_vm.this.machine == "q35" &&
      length(proxmox_virtual_environment_vm.this.efi_disk) == 1 &&
      proxmox_virtual_environment_vm.this.efi_disk[0].datastore_id == var.datastore_id &&
      proxmox_virtual_environment_vm.this.efi_disk[0].type == "4m" &&
      proxmox_virtual_environment_vm.this.efi_disk[0].file_format == "raw" &&
      !proxmox_virtual_environment_vm.this.efi_disk[0].pre_enrolled_keys
    )
    error_message = "OVMF must get persistent EFI variables on the selected VM datastore, without implicitly enabling Secure Boot."
  }
}

run "reject_invalid_firmware" {
  command = plan

  variables {
    bios = "uefi"
  }

  expect_failures = [var.bios]
}

run "reject_empty_machine_override" {
  command = plan

  variables {
    machine = " "
  }

  expect_failures = [var.machine]
}
