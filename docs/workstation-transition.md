# Workstation transition: mgt to operator workstations

Status: repository preparation only. No workstation has been provisioned, no
NetBox tags applied, no credentials transferred and no OpenTofu state migrated.
Ansible/Skynet acceptance can proceed independently of the unresolved backend.
OpenTofu infrastructure operations on workstations remain blocked.

## Ownership and proposed NetBox changes

Execution and application placement are different identities:

| Identity | Inventory group | Proposed members | Meaning |
| --- | --- | --- | --- |
| Workstation | `tags_workstation` | `blacktop`, later other workstations | Existing workstation role selection; not application placement |
| Application controller | `tags_service_controller` | `mgt` only | Existing service placement, PostgreSQL delegation, routes, firewall and runtime-account ownership |
| Legacy tooling | `tags_ansible_manager` | `mgt` during acceptance | Ubuntu tooling compatibility; no local-connection override |

The committed `terraform/netbox/locals.tf` proposal adds tag name
`service-controller`, slug `service_controller`, to mgt only. No new workstation
category or automation inventory group is introduced. Keep Blacktop's existing
`skynet`, `workstation`, `podman` and `podman_install` tags. Keep every existing mgt
tag during the transition. Do not give workstations `ansible_manager` or
`service_controller`. Do not add `opentofu_pve_user` to workstations.

No API calls or apply were made. The canonical
`services_controller_inventory_group` now requires `tags_service_controller`.
There is no legacy `ansible_manager` fallback. Before ordinary service operations,
apply the proposed application-host tag through the authorised NetBox workflow,
or explicitly select an existing singleton application-host group. Missing or
duplicate application hosts fail the existing validation. Adding several eligible workstations does not affect application placement.
An explicit `services_controller_inventory_group` override remains supported.
After NetBox is available, an operator must apply these exact tag changes through
its existing ownership workflow. The prepared OpenTofu source is not permission
to apply it while state ownership remains unresolved. An explicit, separately
authorised NetBox operator change is an alternative if tags are needed earlier;
reconcile that change with the proposed source during the later state transition.

No Config Context identity/address duplication is needed. Preserve existing
services topology (`public_zone`, `internal_zone`, `lan_cidr`,
`private_https_port`), runtime UID/GIDs, app/data roots, SSH user/port/address,
Tailscale and primary-IP fields. Local tooling paths/enablement belong in
`ansible/host_vars/blacktop.yml`. Once available, NetBox supplies connection
identity; before that, local bootstrap discovers the invoking account from facts.

The previous `ansible_connection: local` tag variable is removed. mgt is now an
SSH target from workstations, and uses its existing managed-host interpreter in
`host_vars/mgt.yml`. Rootless accounts, per-service networks, host mounts,
service firewall code and PostgreSQL operator slices remain on mgt. The native
`postgres-python` hook still runs there and retains its mgt-local Python path.
Historical firewall cutover/evidence scripts are host-specific operator tools;
they are not a general workstation bootstrap path and must not be replayed or
copied with private evidence. This transition does not broaden database or
firewall access to workstations: PostgreSQL preparation still delegates to mgt.
Infisical lookup runs on the execution workstation over existing HTTPS routes.

## Fresh workstation prerequisites

Before Ansible can provision a fresh LMDE workstation, an operator needs:

1. An existing non-root interactive account with sudo; working Python 3 and
   Python venv/pip support. The bootstrap Ansible interpreter must meet the
   repository's Ansible requirement (LMDE 7 / Debian 13 is the initial platform).
2. A trusted repository checkout or worktree containing these changes. Provision
   from it directly; optional cloning is for preparing an absent destination,
   not for acquiring the playbook that must already be running.
3. A minimal initial Ansible installation, installed by the operator into a
   separate temporary/bootstrap venv. Use the Ansible version from the chosen
   checkout's `ansible/requirements.txt`; no global pip installation is required.
4. Package/Galaxy/Git access if installing those components. No container daemon
   or application credentials are needed to install workstation tooling.
5. For subsequent remote management: verified SSH host keys, operator SSH access
   to each managed host, correct sudo authority, and Tailscale enrollment when
   used. These are operator steps; no key, password or network bootstrap is
   implemented by the role.

No dependency installation was performed during repository preparation.

## Initial provisioning (later operator action)

A checkout and a minimal Ansible installation must exist before the role can run.
Use an existing trusted checkout/worktree on its current branch whenever possible.
For a fresh machine only, install the prerequisites for its platform:

```bash
# Debian / LMDE
sudo apt-get update
sudo apt-get install git python3 python3-venv python3-pip
# Conventional Fedora Desktop/KDE: use this instead of the APT commands
sudo dnf install git python3 python3-pip
```

Use Python 3.12 or newer, as required by the pinned Ansible core. If no checkout
exists, choose an absent destination and clone there:

```bash
git clone https://github.com/Lebowski89/homelab.git "$HOME/src/homelab"
```

Do not run that clone over an existing checkout. Enter the chosen checkout and
install only its pinned Ansible core into a separate initial venv. This is an
operator prerequisite, not a command executed during repository validation:

```bash
checkout="$PWD"  # repository root, including an existing Git worktree
bootstrap_venv="$HOME/.local/share/homelab-bootstrap"
python3 -m venv "$bootstrap_venv"
ansible_core_requirement="$(sed -n '/^ansible-core==/p' "$checkout/ansible/requirements.txt")"
"$bootstrap_venv/bin/python" -m pip install "$ansible_core_requirement"
```

The first play in `ansible/playbook.yml` provisions workstations before NetBox.
Use the actual inventory hostname (`blacktop` here), rather than `localhost`, so
`ansible/host_vars/blacktop.yml` is loaded. The explicit `-i` overrides the normal
NetBox inventory; tags alone cannot prevent inventory parsing:

```bash
ANSIBLE_CONFIG="$checkout/ansible/bootstrap.cfg" \
  "$bootstrap_venv/bin/ansible-playbook" -i blacktop, -c local \
  "$checkout/ansible/playbook.yml" -e workstation_hosts=blacktop \
  -e "workstation_repository_path=$checkout" \
  -e '{"workstation_opentofu_enabled": true}' \
  --tags workstation_tools --ask-become-pass
```

This converges the managed venv with repository-pinned Python dependencies,
collections, Skynet and compatible OpenTofu. The OpenTofu override opts into binary
installation only; all infrastructure/state operations remain blocked. Omit it
if OpenTofu installation is not wanted. Use `--tags workstation` to include the
existing desktop/development baseline, or one granular tag from the
[workstation documentation](workstation.md). Python/collections downloads and
repository/key configuration are skipped in check mode.

`bootstrap.cfg` enables only built-in static inventory parsers. Its group-variable
precedence excludes automatic `group_vars` files, including application-wide
Vault files, while preserving automatic per-host `host_vars`. Inline variables in
a static inventory still work. This config is for workstation bootstrap only;
no NetBox collection, credentials, private application inputs, service-controller
or storage groups, service topology or Infisical access is required. Local facts
are gathered without sudo to resolve the existing account and system; a static
remote inventory should provide its connection user. Never invoke the whole
playbook without workstation-only tags during bootstrap.

For a reusable static inventory, place only the workstation in `tags_workstation`
and set `ansible_connection: local` on that host. Then use
`-i /path/to/workstations.yml --limit blacktop`, without `workstation_hosts`.
Do not add fake homelab groups or topology. For Fedora, use its actual hostname
and the corresponding `host_vars/<hostname>.yml` options. The role detects the
platform from gathered facts and rejects Atomic/image-based systems.

The explicit existing path may point at a worktree on any branch. Persist a
preferred path and optional feature choices in host vars; never put authentication
there. Add `$HOME/.local/bin` to the interactive PATH if needed. Optional repository
cloning applies only to an absent destination and never updates or switches an
existing checkout. CLI boolean overrides should use JSON as above, rather than
string-valued `-e key=true`, because role switches require real booleans.

After NetBox/private handoff, return to `ansible/ansible.cfg` and the normal
inventory. Skynet workstation commands now use this same `playbook.yml`, with
NetBox and the existing granular tags. A workstation-only selection ends the
homelab play before its always-tagged service assertions; ordinary service
operations retain all those validations. No separate workstation playbook or
`WORKSTATION_PLAYBOOK` override remains.

## Narrow private configuration handoff

Only the operator should select and provision these inputs. This preparation did
not read private configuration, credential values, keys, state or migration
evidence. Do not copy mgt's entire secrets directory, `.terraform` directories,
logs, shell histories, caches, service appdata or historical migration evidence.

| Required item | Destination / handling |
| --- | --- |
| NetBox inventory configuration | Private `ansible/netbox.yml` in the chosen checkout, or a separate `INVENTORY` path. Start with the public sample; supply the existing HTTPS endpoint, token/authentication method, certificate trust and compose rules privately. |
| Encrypted Ansible inputs | Only required encrypted `ansible/group_vars/all/vault/` files and/or encrypted `vault.yml`, or explicit external `-e @...` inputs. Public field declarations are under `ansible/group_vars/all/vault.sample/`. Do not decrypt to inspect the handoff. |
| Vault unlock mechanism | Default `<home>/.config/homelab/.ansible_vault_pass`, or `VAULT_PASS_FILE`; mode 0600 in a mode 0700 user directory, or the existing approved password-client workflow. |
| Managed-host sudo authentication | Default `<home>/.config/homelab/.ansible_become_pass`, or `BECOME_PASS_FILE`, with equivalent protection. Use operator-specific remote authority; the local workstation sudo prompt is a separate concern. |
| Infisical universal-auth declarations | Encrypted inputs `infisical_auth_client_id`, `infisical_auth_client_secret`, `infisical_project_id`. Preserve the existing `https://infisical.<internal-zone>:<private-HTTPS-port>` route and CA trust. No direct plaintext service endpoint. |
| SSH client access | Operator-owned keys/agent and narrowly scoped SSH configuration plus independently verified known_hosts entries. Arrange authorised host access; do not copy mgt's private keys. Keep host-key verification enabled. |
| Recovery configuration | A private static SSH inventory based on `ansible/recovery.yml.sample`, plus only the encrypted NetBox/Infisical bootstrap inputs and approved application-host protection settings. Store separately from application data. |

Inventory/Vault values are not installed or fetched by workstation-tooling tasks;
Skynet installation succeeds before private handoff. Missing password files are
reported by the existing wrapper when a command needs them. Keep private inputs
out of command arguments and logs; arguments may contain paths, never values.
The existing public inventory sample has `validate_certs: false`; that is a
pre-existing example setting, not a direction to weaken an existing private
configuration. Preserve HTTPS and current trust; provision the required CA and
prefer verified certificates. Do not bypass SSH host-key verification or broaden
firewalls to compensate for missing workstation access.

## Bootstrap and recovery isolation

`playbook.yml` NetBox operations select the singleton application group, never
localhost. `bootstrap.yml` selects only `service_recovery` from an explicitly
supplied static inventory. Both validate one explicit remote SSH target, reject
local transport and loopback, and require managed-host path/identity/topology
inputs before entering service roles. There is no hard-coded workstation
interpreter or application-root default in these plays. Workstation provisioning is the first play in `playbook.yml`; workstation-only
tags skip application roles and end the homelab play before service assertions.
Bootstrap inventory and variable-loading isolation come from explicit `-i` and
`bootstrap.cfg`, not from task tags.

When NetBox is unavailable, do not run the dynamic inventory or `INVENTORY=localhost,`.
Use the operator's verified static recovery inventory. Confirm its one target is
mgt with the real remote account/interpreter, primary LAN address, runtime UID/GID,
existing application roots and HTTPS topology. Supply NetBox domain and encrypted
NetBox/Infisical values explicitly using paths to encrypted files. Preserve
`services_bootstrap_acl_ready` and other existing protection assertions; do not
set readiness merely to get past a failure. Preserve the exact NetBox database
major/data mount and external Infisical PostgreSQL/HAProxy endpoints.

List the intended recovery target first (read-only; static inventory only):

```bash
INVENTORY="$HOME/.config/homelab/recovery.yml" \
PLAYBOOK="$PWD/ansible/bootstrap.yml" skynet raw --list-hosts --tags netbox_deploy
```

Actual recovery, only after separate authorisation, uses that same inventory and
playbook with `--tags netbox_deploy` or `infisical_deploy` plus explicit encrypted
`-e @/absolute/path/to/bootstrap-vault.yml` inputs. Neither a role's check mode nor
a list command proves database backup recoverability or service health.

## OpenTofu state gate and proposed backend

All 14 committed root modules have `required_version = "~> 1.11.0"` and no explicit
backend declaration. That implies local state for a fresh checkout; it does not
prove where existing private state is or whether local overrides are in use.
`tofu-all.sh` can initialise and apply multiple roots, so do not use its init,
upgrade, plan or apply actions on a workstation during this gate.

Operator-controlled handoff must account for each root's authoritative state,
backup, workspace choice, private backend overrides and required private variable
files. Identify paths and ownership privately without publishing contents:

| Root under `terraform/` | Committed private-variable samples |
| --- | --- |
| `cloudflare/homelab`, `cloudflare/hugo` | `secrets.auto.tfvars.sample` |
| `github/homelab`, `github/hugo` | `secrets.auto.tfvars.sample` |
| `netbox` | `private.auto.tfvars.sample`, `secrets.auto.tfvars.sample` |
| `proxmox/containers/dns03` | `secrets.auto.tfvars.sample` |
| `proxmox/mappings/resources` | `private.auto.tfvars.sample`, `secrets.auto.tfvars.sample` |
| `proxmox/settings/pve1` | `private.auto.tfvars.sample`, `secrets.auto.tfvars.sample` |
| `proxmox/templates/ubuntu-2404-lxc`, `proxmox/templates/ubuntu-2604` | `private.auto.tfvars.sample`, `secrets.auto.tfvars.sample` |
| `proxmox/vms/postgres-cluster`, `proxmox/vms/unraid` | `private.auto.tfvars.sample`, `secrets.auto.tfvars.sample` |
| `seerr`, `technitium/internal-dns` | `secrets.auto.tfvars.sample` |

The reusable `proxmox/modules/ubuntu-cloudinit-vm` module is not an independent
state root. For each active root the operator must account for `terraform.tfstate`,
`terraform.tfstate.backup` and, if used, `terraform.tfstate.d/<workspace>/`, explicit
state paths, backend configuration and ignored override files. This is a handoff
checklist, not an assertion that any of those private files exist here. Preserve
committed provider locks. Do not copy `.terraform` credential/backend caches or
create another active local state copy on each workstation.

Five committed `terraform_remote_state.netbox` consumers explicitly use the local
backend: `proxmox/containers/dns03`, `proxmox/settings/pve1`,
`proxmox/vms/postgres-cluster`, `seerr`, and `technitium/internal-dns`. Their
`netbox_state_path` defaults are relative to their roots, pointing to
`terraform/netbox/terraform.tfstate`. A later backend migration must update all
five readers in the same staged transition, or deliberately replace them with
explicit operator-provided inputs where supported. Merely moving root backend
state leaves those local readers stale or missing.

Concrete proposal (not selected or deployed): use one dedicated AWS S3 bucket
outside mgt's application failure domain, with a key
`homelab/<root-relative-path>/terraform.tfstate` per root. Enable native
`use_lockfile = true`, versioning, encrypted storage, TLS-only access and public
access blocking. Grant operator identities access only to required state and
lock objects; use short-lived credentials and separate recovery authority.
Back up versions independently and rehearse restoration and lock contention
before acceptance. OpenTofu 1.11 supports native S3 lockfiles and recommends
versioning for recovery. [OpenTofu 1.11 S3 backend](https://opentofu.org/docs/v1.11/language/settings/backends/s3/)

Account, region, globally unique bucket name, IAM policy, costs, retention,
break-glass ownership and restore objectives require an operator decision. There
is no backend deployed or enabled by this change. In a separate authorised state
transition, freeze all writers, take a protected backup, migrate each root once,
verify lineage/serial and outputs privately, update the five readers, prove
cross-workstation locking, and mark old local files as inactive protected backups.
Do not publish state or backend credentials in Git, arguments or test fixtures.
If rollback is needed after any remote writes, stop all writers and restore a
single agreed authority; never reactivate a stale local state independently.

Until that decision and migration are complete, workstation OpenTofu init, plan,
apply, imports, refresh, state commands and backend migration are blocked by the
operating procedure. The native `tofu` executable is not technically sandboxed by
this repository. Only version output and formatting are acceptance operations;
no backend commands were run during preparation.

## Read-only acceptance and staged switch

First perform offline acceptance with synthetic inventory and no private handoff:

```bash
skynet versions
skynet targets
skynet tags
"$HOME/.local/share/homelab/ansible-venv/bin/python" -m pytest \
  tests/unit/test_workstation_tooling.py tests/unit/test_workstation.py \
  tests/unit/test_services_host_contract.py tests/unit/test_ubuntu_netplan.py \
  tests/unit/test_netbox_workstation.py
tofu version
tofu fmt -check -recursive terraform
```

Run OpenTofu acceptance commands only if its binary has been installed. Tests use
local fixtures; no credentials are needed. A missing dependency is a reported
failure, not permission to upgrade pins. Skynet's `doctor`, `inventory`, `syntax`
and `ci` with a dynamic inventory query NetBox; they are not offline checks.
`check`, `drift` and `doctor --ping` may contact managed hosts. Do not use them
as an unauthorised local validation shortcut.

After private handoff and explicit permission for read-only live access, the
operator can run `skynet inventory --graph` (avoid `--list`, which can expose
host variables), `skynet doctor`, and
`skynet raw --list-hosts --tags deploy`. Confirm that mgt alone is the application
controller, Blacktop uses its NetBox SSH identity, and other workstations do not
alter placement. Review SSH host-key fingerprints through a trusted channel
before any connection. Any later host ping or check-mode deployment needs its
own authorised scope; do not assume check mode is an offline operation.

Switch in stages:

1. Keep mgt tooling, private configuration and the current state authority intact.
   Provision Blacktop and complete offline tests. Record the chosen checkout,
   tooling paths and revision without publishing private evidence.
2. Complete the narrow private handoff and authorised read-only acceptance.
   Apply the proposed NetBox tag/configuration changes separately. Confirm
   service placement, operator hooks, HTTPS reachability and unchanged firewall
   boundaries. A failed access check pauses the switch; it does not justify ACL
   broadening.
3. Designate Blacktop as the Ansible/Skynet execution machine. Authorise one
   bounded service operation separately, retaining mgt as application host and
   delegated PostgreSQL executor. Observe and accept before expanding. No such
   live operation is part of this preparation.
4. Keep OpenTofu operations frozen on workstations until the separate backend
   transition above is approved and accepted. Additional workstations use the
   same authoritative backend, not copies of mgt state.
5. After acceptance and a rollback window, separately authorise retirement of
   redundant mgt CLI tooling. Retain the mgt interpreter/dependencies required by
   delegated modules and PostgreSQL hooks, runtime accounts, operator units,
   firewall ownership, applications and their data. Update the legacy Ubuntu
   tooling tag/eligibility only in that later phase.

For Ansible/Skynet rollback, stop workstation execution and resume the preserved
mgt wrapper/checkouts with their original environment. The transport is now SSH;
if mgt needs local execution for itself, scope that to a private mgt-only
inventory override, never a global `-e ansible_connection=local`. Revert only
workstation enablement or narrowly scoped tag changes when needed; no application
or data migration is involved. Preserve the new singleton application identity.
OpenTofu rollback follows the single-authority rule above. Nothing is uninstalled,
staged, committed, pushed or deployed by this preparation.

## Repository preparation record

Work began on clean local `main` at `7478eb8d`, matching the cached
`origin/main` ref; no fetch or remote GitHub access was needed. Relevant history
included workstation management (`9f03f36f`), Ubuntu upgrades (`20fa1f75`) and
mgt's Podman migration (`818a263f`). No pre-existing modifications were present.

Changed files are grouped by purpose:

- Workstation tooling: `ansible/roles/workstation/defaults/main.yml`,
  `tasks/main.yml`, `tasks/tools.yml`, `tasks/tools/validate_tools.yml`, `tasks/tools/ansible.yml`,
  `tasks/tools/ansible_python.yml`, `tasks/tools/ansible_collections.yml`, `tasks/tools/repository.yml`,
  `tasks/tools/skynet.yml`, `tasks/tools/opentofu.yml`, `templates/skynet.j2` and
  `filter_plugins/workstation.py`; `ansible/host_vars/blacktop.yml` and
  `ansible/playbook.yml` (first workstation play). Extracted Ubuntu task/filter/template sources are
  removed; `ubuntu/tasks/main.yml` delegates only tooling. OpenTofu's install
  entry point forwards to workstation, and its installation defaults move there.
- Application placement/recovery: `ansible/playbook.yml`, `ansible/bootstrap.yml`,
  `ansible/tasks/recovery_target.yml`, `ansible/recovery.yml.sample`,
  `ansible/group_vars/all/services.yml`, `ansible/group_vars/tags_ansible_manager.yml`,
  `ansible/host_vars/mgt.yml` and `terraform/netbox/locals.tf`. The two existing
  host-local operator projections, `utility-preparation.py` and
  `znc-mapping-proof.py`, resolve only the new application-group selector before
  retaining their existing local-host guards and credential-free projection.
- Paths/documentation/tests: `ansible/ansible.cfg`, this runbook,
  `docs/workstation.md`, `docs/ansible/{netbox,requirements}.md`,
  `docs/cheat_sheets/skynet.md`, `docs/podman-services.md`,
  `tests/unit/test_workstation_tooling.py`, affected workstation/host-contract/
  Ubuntu tests and existing wrapper tests updated to its new source location.

Intentional differences: workstation paths are user-owned; existing checkouts
are preserved instead of updated; Skynet can be installed before credential
handoff; mgt is reached over SSH from a workstation; recovery refuses local
execution; and default OpenTofu installation selects compatible 1.11.x rather
than an unconstrained latest release. Application service placement, runtime
accounts, firewall ownership, PostgreSQL delegation and mgt's host interpreter
remain unchanged. No additional workstation inventory category is introduced.

Validation used `/opt/ansible/ansible-venv` and Ruff 0.17.1, matching
`ansible/requirements.txt`. Final affected checks:

```bash
/opt/ansible/ansible-venv/bin/python -m pytest \
  tests/unit/test_workstation_tooling.py tests/unit/test_workstation.py \
  tests/unit/test_ubuntu_netplan.py tests/unit/test_services_host_contract.py \
  tests/unit/test_netbox_workstation.py \
  --basetemp /tmp/homelab-controller-validation/focused --tb=short -q
/opt/ansible/ansible-venv/bin/ansible-lint --offline \
  ansible/roles/workstation ansible/roles/ubuntu/tasks/main.yml \
  ansible/roles/opentofu ansible/bootstrap.yml ansible/tasks/recovery_target.yml \
  ansible/playbook.yml
/opt/ansible/ansible-venv/bin/yamllint ansible/roles/workstation \
  ansible/bootstrap.yml ansible/playbook.yml ansible/recovery.yml.sample \
  ansible/host_vars/blacktop.yml ansible/host_vars/mgt.yml \
  ansible/tasks/recovery_target.yml
/usr/bin/tofu fmt -check terraform/netbox
git diff --check
```

Focused result: **114 passed**. Offline Ansible lint, YAML lint, formatting and
whitespace checks passed. `ruff check` and `ruff format --check` passed on all 16
affected Python files (the two operator scripts, workstation filter and affected
tests). Localhost-only `ansible-playbook -i localhost, <playbook> --syntax-check`
passed for the then-current entry points. The separate workstation entry point
has since been removed; current bootstrap validation is described below. Syntax checks used an orchestration-only mirror under
`/tmp/homelab-controller-validation/syntax`, with explicit role/plugin paths and
no repository group_vars, private inventory or Vault inputs.

The final full fast-unit run also passed: **2,034 passed, 659 deselected**, using
`/opt/ansible/ansible-venv/bin/python -m pytest tests/unit -m 'not integration'
--basetemp /tmp/homelab-controller-validation/fast --tb=short -q`, with the venv
first on PATH and a task-specific TMPDIR under `/tmp`.

The full unit-suite attempt (`python -m pytest tests/unit -q`, using the configured
venv and offline Go environment) did not pass: the installed Go toolchain lacks
standard-library source packages, and test temporary storage hit disk quota/no
space errors. The final report was truncated by that quota, so no full-suite
pass count is claimed. Task-created full-suite artifacts were removed to allow
focused validation; no user-owned files were cleaned. No dependencies were
installed or changed to bypass these limitations. Docsible was unavailable,
so role READMEs remain for the established generator workflow. No OpenTofu
backend initialization, offline provider validation or live validation was run.

No managed hosts, providers, infrastructure APIs, databases, secret stores or
container/service runtimes were contacted. Only public upstream documentation
was consulted externally. No private credential, key, state or migration-evidence
contents were read or copied. Nothing was staged, committed, pushed, applied,
deployed, removed from mgt, or posted to GitHub.

Suggested commit title: `feat(workstation): prepare operator automation tooling`.


## Bootstrap correction validation

The current bootstrap regression fixture executes the complete `playbook.yml`
with mocked host operations, the real Blacktop host options, a static inventory,
no `netbox.yml`, empty collection search paths and no site-package collection
scanning. A deliberately unreadable synthetic Vault file verifies exclusion of
application group variables. It covers Debian/Fedora selection, unprivileged
fact/user resolution, granular tags and bypass of homelab pre_tasks. A separate
service-selection test confirms the singleton assertions still run. These are
execution/rendering checks, not installation or live acceptance. Docsible remains
owned by `.github/workflows/ansible-docs.yml`; generated role READMEs are not edited.


Checks for this bootstrap correction (repository-only):

- Focused workstation/tooling/service-host/NetBox/Ubuntu tests: **163 passed**
  (`python -m pytest tests/unit/test_workstation.py tests/unit/test_workstation_tooling.py tests/unit/test_services_host_contract.py tests/unit/test_netbox_workstation.py tests/unit/test_ubuntu_netplan.py`).
- Final complete-entry-point bootstrap and ordinary/mixed service-tag checks:
  **12 passed** (`python -m pytest tests/unit/test_workstation.py -k
  'actual_main_bootstrap or inline_bootstrap or normal_service_selection'`).
- Fast repository suite: **2,035 passed, 708 deselected**
  (`python -m pytest tests/unit -m 'not integration'`).
- Offline Ansible lint passed for `ansible/playbook.yml`, the workstation role
  and `ansible/group_vars/all/services.yml`, with explicit localhost inventory,
  bootstrap config and both repository/service-common filter paths.
- The actual main and recovery playbooks passed `--syntax-check` with explicit
  `-i localhost,`, bootstrap config and empty collection paths/site scanning off.
- Ruff check/format passed on all seven affected test files; affected YAML lint
  and `git diff --check` passed.

Successful pytest temporary directories were removed per test with
`-o tmp_path_retention_policy=failed` after earlier runs hit the local disk quota.
Installed Ansible core 2.21.4 / ansible-lint 26.8.0 differ from repository pins
2.21.5 / 26.10.1; exact-pinned-version validation remains unavailable. Ruff 0.17.1
matches its pin. No dependencies were installed or changed. No live installation,
service/API/secret access, infrastructure/state action or Git publication occurred.
Public Ansible documentation was consulted for variable/connection behaviour.
The bootstrap config uses Ansible's configurable
[group-variable precedence](https://docs.ansible.com/projects/ansible/latest/reference_appendices/config.html#variable-precedence);
per-host loading is verified by the execution tests above.
