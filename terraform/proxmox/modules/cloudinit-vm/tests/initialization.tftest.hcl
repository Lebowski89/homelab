mock_provider "proxmox" {}

variables {
  name                 = "offline-initialization-test"
  vm_id                = 99101
  node_name            = "offline-node"
  clone_template_vm_id = 99003
  datastore_id         = "selected-vm-storage"
  ipv4_address         = "192.0.2.10/24"
  ipv4_gateway         = "192.0.2.1"
  dns_servers          = ["192.0.2.53"]
  cloud_init_user      = "testuser"
  ssh_public_keys      = ["ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA offline@example.invalid"]
  qemu_agent_enabled   = false
}

# Mock applies create only in-memory test state; no Proxmox API is contacted.
run "create_with_managed_initialization" {
  command = apply
}

run "existing_entry_point_still_manages_initialization" {
  command = plan

  variables {
    dns_servers = ["192.0.2.54"]
  }

  assert {
    condition     = proxmox_virtual_environment_vm.this.initialization[0].dns[0].servers == tolist(["192.0.2.54"])
    error_message = "The existing module entry point must still plan cloud-init updates."
  }
}

run "create_with_creation_only_initialization" {
  command = apply

  module {
    source = "./initialization-ignored"
  }
}

run "ignore_initialization_but_still_manage_vm_hardware" {
  command = plan

  module {
    source = "./initialization-ignored"
  }

  variables {
    dns_servers = ["192.0.2.54"]
    cpu_cores   = 4
  }

  assert {
    condition = (
      proxmox_virtual_environment_vm.this.initialization[0].dns[0].servers == tolist(["192.0.2.53"]) &&
      proxmox_virtual_environment_vm.this.cpu[0].cores == 4
    )
    error_message = "Creation-only cloud-init must preserve prior initialization while continuing to plan hardware changes."
  }
}

run "creation_only_entry_point_retains_safety_checks" {
  command = plan

  module {
    source = "./initialization-ignored"
  }

  variables {
    dns_servers = []
  }

  expect_failures = [proxmox_virtual_environment_vm.this]
}
