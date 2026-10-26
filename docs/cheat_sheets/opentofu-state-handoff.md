# OpenTofu state handoff between workstations

Use this when an existing resource is managed from one machine, but a new
workstation proposes creating it again. SSH keys and private tfvars provide
access; the existing state supplies the resource mappings. Retrieve that
authoritative state rather than importing the same resources into another state.

The example moves management of the Ubuntu 26.04 template, VMID **9003**, from
**mgt** to **Blacktop**. Repeat separately for each root; never put Ubuntu's state
in the Rocky root or combine independent state files.

## 1. Establish ownership, backend and workspace

Before exporting:

- Confirm which machine/backend holds the authoritative state. Stop if both
  machines have independently managed resources; do not overwrite one state with
  the other or choose solely by file modification time.
- Pause applies, imports, automation and all other state writers on both machines
  until the handoff and plan review are complete.
- Use matching repository configuration, provider lock file and compatible
  OpenTofu versions. Privately supply the required tfvars, SSH access and trusted
  certificates on the destination. Do not upgrade providers during the handoff.
- Confirm the backend and workspace on both machines. The file-install commands
  below apply only to the **local backend, default workspace, default
  `terraform.tfstate` path**. Resolve custom paths, other workspaces and encryption
  requirements before adapting them.

If the authoritative state is in a shared remote backend, configure Blacktop to
use that same backend and workspace instead. Do not install an exported snapshot
as a second local state. A shared backend with locking is preferable for ongoing
use from multiple machines; this cheatsheet does not perform a backend migration.

On **mgt**, in the existing root:

```bash
cd /opt/homelab/terraform/proxmox/templates/ubuntu-2604
tofu version
tofu workspace show
tofu state list
```

For this example, the workspace should be `default` and the resource list should
include:

```text
proxmox_download_file.ubuntu_cloud_image
proxmox_virtual_environment_vm.ubuntu_template
```

Confirm these mappings belong to the intended existing template and image. A
resource address alone does not prove which VM it represents. Do not paste full
state or `state show` output into chats or logs; state can contain secret values.

## 2. Prepare Blacktop

Run the remaining commands in the same Bash terminal on **Blacktop**. Adjust the
checkout path, SSH destination and source root for other workstation pairs.

```bash
cd ~/Desktop/homelab/terraform/proxmox/templates/ubuntu-2604
tofu version
tofu workspace show
tofu state list
```

Stop if the directory is wrong, the workspace is not `default`, or Blacktop
already has resource mappings that have not been reconciled with mgt. An empty
resource list or missing local state is expected for a fresh destination.
If initialisation is needed, first confirm the intended local backend, then use
`tofu init -lockfile=readonly`; do not use `-upgrade` or accept an unexpected
backend migration prompt.

## 3. Export privately over SSH and inspect the staged snapshot

```bash
umask 077
incoming_state=$(mktemp terraform.tfstate.from-mgt.XXXXXX)

ssh mgt@mgt \
  'cd /opt/homelab/terraform/proxmox/templates/ubuntu-2604 && tofu state pull' \
  > "$incoming_state" &&
  test -s "$incoming_state" &&
  tofu state list -state="$incoming_state"
```

Continue only if the whole command succeeds and the staged resource list matches
the source. If SSH, export or parsing fails, stop; do not install a partial or
empty file. A retry creates a new staging file. `state pull` reads the configured
source state and writes it directly to the private destination file; it does not
refresh infrastructure or modify the source state. It may convert the exported
snapshot to the source OpenTofu version's supported state format.

The staging file has mode `0600`. The names used here match the repository's
`*.tfstate.*` ignore rule. Keep state, backups and private tfvars out of Git and
shared logs even when variables are marked sensitive. The SSH transfer uses
normal host-key verification; do not disable it.

## 4. Back up Blacktop's previous state and install the snapshot

After reviewing the staged resource list, run:

```bash
(
  set -eu
  test -s "$incoming_state"

  if [ -e terraform.tfstate ]; then
    previous_state=$(mktemp terraform.tfstate.before-handoff.XXXXXX)
    install -m 600 terraform.tfstate "$previous_state"
  fi

  install -m 600 "$incoming_state" terraform.tfstate
  tofu state list
)
```

The subshell stops if a backup or installation step fails. Keep the source state,
the staged export and any destination backup until the handoff has been verified.
Do not copy `.terraform/` between machines; initialise the destination with the
checked-in lock file instead.

## 5. Review the plan and switch the active owner

`tofu validate` checks configuration locally. `tofu plan` contacts the configured
infrastructure providers, so run the plan only after the state/private-input
handoff is established and live read access is authorised:

```bash
tofu validate
tofu plan
```

Matching state does not guarantee a no-change plan: code, private inputs or live
configuration may differ. For the Ubuntu example, investigate any attempt to
create VM9003 or its existing downloaded image, and any unexpected replacement,
disk/storage change or deletion. Do not apply merely to finish the handoff.

Once verified, record Blacktop's root directory and local state path as the
active owner. Retain mgt's copy as an inactive backup and disable or redirect any
automation that could still use it. Local state locks do not coordinate separate
copies on different machines. Export the newest active state for a later handoff;
do not copy an old backup over a state that has since advanced. After any apply
on Blacktop, mgt's retained copy is stale.

Do not use `import`, `state rm`, forced state pushes or automatic VM deletion to
work around a handoff mismatch. Import is a separate recovery workflow when the
authoritative mappings are genuinely unavailable.

## References

- [OpenTofu 1.11: state pull](https://opentofu.org/docs/v1.11/cli/commands/state/pull/)
- [OpenTofu 1.11: local backend and state paths](https://opentofu.org/docs/v1.11/language/settings/backends/local/)
- [OpenTofu 1.11: state storage and locking](https://opentofu.org/docs/v1.11/language/state/backends/)
