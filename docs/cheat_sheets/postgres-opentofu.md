# PostgreSQL OpenTofu roots

Run commands from the repository root on the workstation holding the authoritative
local state and private inputs. A Git checkout alone is not enough. Establish the
state location before any live operation on Blacktop; use the
[state handoff checklist](opentofu-state-handoff.md) when changing workstations.
Never plan from an empty state for these existing VMs or import duplicate bindings.

## Ownership

The three VM roots use independent local states and the default workspace. The
existing Ubuntu 26.04 template root owns the shared guest-agent vendor data, as well
as its existing template VMID 9003 and downloaded image. It has its own existing
local state and credentials. No individual VM root owns the shared snippet.

| Root under `terraform/proxmox` | Managed resource address | Existing VMID |
| --- | --- | --- |
| `vms/pg01` | `module.postgres_vm.proxmox_virtual_environment_vm.this` | 9205 (`pg95`) |
| `vms/pg02` | `module.postgres_vm.proxmox_virtual_environment_vm.this` | 9206 (`pg96`) |
| `vms/pg03` | `module.postgres_vm.proxmox_virtual_environment_vm.this` | 9207 (`pg97`) |
| `templates/ubuntu-2604` | `proxmox_virtual_environment_file.postgres_qemu_guest_agent_cloud_init` | — |

The shared file remains `local:snippets/postgres-qemu-guest-agent.yaml`, with the
same content, filename, storage and Proxmox node. This ownership transfer does not
attach new cloud-init data to the existing template or change guest-agent settings.
Do not destroy the template root while any guest or template requires its snippet.
Destroying one PostgreSQL VM root cannot delete the shared file or the other VMs.
Directory names do not change guest names, OS hostnames, DNS, NetBox, Patroni or
etcd membership.

## Inputs and routine use

Each VM root has `private.auto.tfvars.sample` and `secrets.auto.tfvars.sample`.
For a new workstation, transfer the authoritative private files and states rather
than filling out samples over existing managed VMs. Transfer the current complete
Ubuntu template state too: it includes the existing image, VM9003 and snippet.
A missing local template state does not establish that the template is unmanaged.
Keep its existing credentials separate from the PostgreSQL roots' credentials.

The migration preserves existing private values. Sample memory and addressing are
illustrative, not resize intent. Keep private inputs and states at mode `0600`.
The migrated non-secret VM inputs use `private.auto.tfvars.json`, which OpenTofu
loads automatically. Do not add a second HCL file defining the same inputs.

The single `postgres_vm` object retains the old per-guest fields and adds `name`:

```hcl
# In pg01/private.auto.tfvars (or equivalent private.auto.tfvars.json):
postgres_vm = {
  name                = "pg95"
  vmid                = 9205
  ip                  = "192.0.2.95"
  clone_template_vmid = 9003
  cores               = 2
  sockets             = 1
  memory              = 4096 # Example; preserve existing private sizing.
  disk_size_gb        = 60
}
```

`pg02` uses `pg96` / 9206; `pg03` uses `pg97` / 9207. Common provider, storage,
network and bootstrap inputs are documented in each sample and generated root
reference. `postgres_vm_names` and `postgres_vm_ips` retain their list/map shapes,
now containing only the root's guest; `vm_id` identifies its VMID.

The template owner exports `qemu_guest_agent_vendor_data_file_id`. Each VM reads
that output from `ubuntu_template_state_path`, which defaults to
`../../templates/ubuntu-2604/terraform.tfstate` relative to its root. Paths expand
`~`; no workstation-specific directory is required. Transfer the latest owner
snapshot during a workstation handoff rather than inventing a new file ID.

For an explicit bootstrap without that snapshot, `guest_agent_vendor_data_file_id`
may supply the existing exported ID. A non-null override takes precedence and skips
only the template-state lookup; it does not disable NetBox topology lookup. Empty
overrides are rejected. Normal use leaves this input null and reads the owner output.
The template root never reads VM state, so this introduces no circular dependency.

Use the repository-compatible OpenTofu executable and checked-in provider lockfiles.
The migration was validated with Blacktop's OpenTofu 1.13.2 and `bpg/proxmox` 0.114.0;
initialization must not upgrade the provider.

```bash
tofu -chdir=terraform/proxmox/vms/pg01 init -lockfile=readonly
tofu -chdir=terraform/proxmox/vms/pg01 validate
tofu -chdir=terraform/proxmox/vms/pg01 state list
tofu -chdir=terraform/proxmox/vms/pg01 plan
```

Substitute the appropriate root. Normal plan/apply/destroy operations address its
whole state; no routine `-target` or `-exclude` flags are needed. Review a normal
refreshed plan before a separately authorized apply. State and saved plans can
contain sensitive information; keep recovery material outside tracked source with
`0700` directories and `0600` files. Saved `*.tfplan` files and their JSON are ignored.

## Topology and cloud-init

NetBox local state remains the default source of DNS VIPs and the internal zone.
`netbox_state_path` defaults to `../../../netbox/terraform.tfstate` relative to the
selected VM root. Transfer the correct NetBox state snapshot too, or select an
explicit bootstrap fallback. Public key paths expand `~` on the workstation.

With remote state enabled, NetBox DNS values override `dns_ips` fallbacks, and the
two distinct DNS VIPs are required. With it disabled, an explicit space-separated
`vm_nameserver` takes precedence; if empty, both `dns_ips` VIPs are required. The
NetBox internal zone wins when present, otherwise `vm_searchdomain` is used.
These rules retain the previous topology precedence.

PostgreSQL uses `modules/cloudinit-vm/initialization-ignored`. Its `.tf` symlinks
share the parent module's implementation, variables, outputs and version pins;
a small tracked override retains `ignore_changes = [initialization]`. OpenTofu
requires a static lifecycle list, so a conditional input cannot express this
boundary. The original module entry point, including Rocky's caller, continues
to manage initialization changes. PostgreSQL cloud-init remains creation-only;
it is not reconciled onto existing guests by this ownership transfer.

## State transfer and recovery

The controlled transfer uses OpenTofu `state mv` with explicit `-state` and
`-state-out` paths on verified private local copies. The existing snippet binding
moves to `proxmox_virtual_environment_file.postgres_qemu_guest_agent_cloud_init`
in the template owner's existing state. Its prior image/template bindings, state
lineage and credentials are preserved. The retired snippet-only source has no
managed resources and its complete directory is archived outside tracked source.

Read-only refresh records the owner output. Full refreshed plans for all three VM
roots and the template owner must show no infrastructure changes before retirement
and again after removing the obsolete directory. Existing VMIDs must be bound
exactly once. Do not apply a plan to complete or repair a state handoff.

The private recovery directory contains original source/destination states and
inputs, hashes, sanitized ownership maps, candidate states, private plan logs,
saved plans and the retired directory. Stop concurrent state writers during a
transfer. Treat recovery material as sensitive and keep it inactive; never copy a
backup into another active root or overwrite the destination's existing state
with the former snippet-only state.

If acceptance fails, restore configuration, private inputs and state together
from the verified backup, including the template owner's original bindings. Do
not leave both states active for the same snippet. Recheck exact-once ownership
and normal refreshed plans before resuming operations.

## Intentional VM removal

Before an operator plans removal, establish current Patroni leadership, database
replication and etcd quorum, arrange any required switchover/member maintenance,
and ensure recovery backups exist. Separate VM states do not make losing a quorum
member safe. This migration does not perform those database operations.

Only after those checks and separate authorization, review a destroy plan in the
chosen VM root. An operator retiring `pg95` would plan in `pg01`. The other roots
still own their VMs. Do not remove the shared template/snippet as part of a
single-node retirement.
