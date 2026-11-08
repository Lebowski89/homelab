# Molecule VM pilot

`rocky_node_exporter` tests the real Node Exporter catalogue entry on one
externally provisioned Rocky 10 AMD64 KVM/QEMU VM. It does not provision or destroy
VMs, call NetBox/Proxmox/Infisical, or select a default guest. Existing pytest
fixtures remain responsible for fast contract and simulated-I/O regressions.

The pilot uses Molecule 26.10.0's
[Ansible-native configuration](https://docs.ansible.com/projects/molecule/ansible-native/).
The normal workstation requirements and Skynet interfaces remain unchanged.

## Controller setup

Use a separate virtual environment with the repository's pinned controller
requirements plus Molecule. The existing pinned collections are still required:

```bash
python3 -m venv /tmp/homelab-molecule-venv
/tmp/homelab-molecule-venv/bin/python -m pip install -r molecule/requirements.txt
/tmp/homelab-molecule-venv/bin/ansible-galaxy collection install -r ansible/requirements.yml
export PATH="/tmp/homelab-molecule-venv/bin:$PATH"
```

These commands install tooling; they are separate from scenario execution.
Molecule dependency installation and project prerun are disabled. The scenario
uses explicit role/plugin paths, disables fact injection, retains SSH host-key
checking and excludes automatic application group_vars/vault loading.

## Guest and inventory

Supply one disposable VM with Python, the distribution DNF bindings, systemd,
passwordless sudo for the test account and enforcing SELinux. Verify its SSH host
key through the existing provisioning process. Node Exporter must have no existing
account, binary, collector directory, service unit or catalogue ownership record.
The previous acceptance VM retains installation artifacts and therefore does not
meet this fresh-host condition until recreated.

Copy the sample inventory outside Git, then fill its connection fields from the
VM's verified inventory identity. Do not put passwords, keys or other secrets in
it. The sample address is reserved documentation space, not a runnable target.

```bash
cp molecule/rocky_node_exporter/inventory/hosts.yml.sample /tmp/rocky-node-exporter.yml
# Edit /tmp/rocky-node-exporter.yml for the disposable guest.
export HOMELAB_MOLECULE_INVENTORY=/tmp/rocky-node-exporter.yml
```

The inventory must contain only that guest, its `molecule_node_exporter` group and
its matching `tags_skynet`/`tags_node_exporter` memberships. A real boolean
`molecule_node_exporter_disposable: true` is required. Production dynamic inventory,
extra hosts, local connections and unmarked targets are refused. Use the sample's
isolated inventory alias; do not add application groups or role overrides.
Metrics are explicitly fixed to guest loopback `127.0.0.1:19100`, without firewall
changes. No existing NetBox host values are changed or duplicated in service YAML.

## Run from the repository root

With no inventory override, the checked-in empty inventory permits syntax checks
and refuses execution before a guest connection:

```bash
molecule syntax -s rocky_node_exporter
```

A read-only role plan on an explicitly designated VM is available independently:

```bash
molecule check -s rocky_node_exporter
```

That command has no prepare, cleanup or provider lifecycle phase. It does not
claim that the runtime was installed or verified.

For a complete fresh-guest run, use a fresh controller state directory as well.
Molecule remembers preparation state, while this pilot leaves VM lifecycle to
the operator:

```bash
export MOLECULE_EPHEMERAL_DIRECTORY="$(mktemp -d /tmp/homelab-molecule-node-exporter.XXXXXX)"
molecule test -s rocky_node_exporter
```

The full sequence:

1. Validate the single opted-in target and the conventional Rocky platform.
2. Refuse existing installation/data, ensure signed distribution
   `ca-certificates`, `tar` and `gzip` prerequisites, and claim a root-owned test marker.
3. Run fresh-host check mode through `ansible/playbook.yml --tags node_exporter`.
4. Verify that check mode created no account, binary, collector directory, unit or
   catalogue ownership record.
5. Converge the real catalogue entry and seed one non-sensitive textfile metric.
   Verify actual metrics and boot enablement, rerun for Molecule idempotence, then
   verify the service PID/invocation is unchanged.
6. Remove the owned service through the existing catalogue dispatch. Verify the
   unit and ownership record are gone and the service stopped. Existing binary
   and test metric checksums must be preserved; cleanup also handles partial
   installations where those artifacts were never created.

Every guest-facing action validates the inventory and platform. Cleanup requires this
scenario's root-owned marker and skips an unclaimed installation; it is not a
way to adopt or remove an existing production exporter. A malformed/replaced
marker fails closed. Molecule's automatic failure-path destroy hook is explicitly
a localhost-only message. No VM is destroyed, and no account, binary, collector
data, archive or prerequisite package is erased to make the next run pass.

For iteration before cleanup, keep the same state directory and VM:

```bash
molecule converge -s rocky_node_exporter
molecule idempotence -s rocky_node_exporter
molecule verify -s rocky_node_exporter
molecule cleanup -s rocky_node_exporter
```

Run preparation first (`molecule prepare -s rocky_node_exporter`) if starting
with a fresh VM outside the full test sequence. After cleanup, recreate/restore a
fresh VM and use a fresh state directory for another fresh-install test. Use one
scenario invocation per VM at a time. Do not reset the controller state while
an owned installation still needs cleanup.

## CI and scope

The existing quality job installs the optional pinned Molecule requirements,
lints the scenario and runs syntax checks using the checked-in empty inventory.
It also runs the real CLI against empty and explicitly unmarked synthetic
inventories, with SSH blocked, to verify inventory fallback and override handling:

```bash
python -m pytest tests/molecule -q --tb=short
```

The existing pytest jobs exercise scenario safety with all guest I/O replaced.
CI does not receive a VM inventory, production credentials or infrastructure API
access, and it never runs the live Molecule test sequence.

An actual `molecule test` run is still required on a fresh designated VM to certify
this scenario. Prior manual Node Exporter acceptance is evidence for the role,
not a passing Molecule run. Other OS releases, Docker/Podman installation, reboot,
SELinux/firewall policy changes and multi-host behaviour remain future scenarios.
