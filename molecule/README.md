# Disposable VM acceptance

Molecule exercises the production Ansible installation entry points, catalogue,
adapters and firewall transactions. Pytest retains fast contracts and simulated
failure paths. Passing syntax or mocked guards is **not** guest acceptance.
The recorded matrix is **32/32 passing**, reusing 29 successful cases and replacing
only the three failed Ubuntu cases with fresh full passes. Ubuntu's direct
rootless runtime cases include the explicit guarded pasta prerequisite below.
See the [recorded acceptance summary](#recorded-acceptance). The detailed run
history, versions, durations and cleanup receipts are archived with the private
controller evidence outside Git.

The historical `rocky_node_exporter` scenario is shared across Debian 13,
Fedora 44, Rocky 10.2 and Ubuntu 26.04 AMD64. There is one lifecycle root and one
running guest per approved allocation, rather than a provisioning root per role.
No Tailscale, NetBox registration, production inventory, application credentials
or normal guest SSH configuration is needed.
Molecule automatically loads the shared repository configuration from
`.config/molecule/config.yml`; scenario files contain their operation sequences.

## Controller and allocation

Use the existing pinned collections and an isolated environment containing
`molecule/requirements.txt`; ordinary workstation requirements are unchanged.
Molecule 26.10.0 and OpenTofu 1.11 with bpg/proxmox 0.118.0 are pinned. Configure a
trusted controller profile outside Git with the tooling PATH, a scoped
`PROXMOX_VE_API_TOKEN`, and its approved node SSH agent. Never use public PR code
on a controller with infrastructure access.
Keep tooling, the profile, TLS CA, provider cache and run state on persistent
disk. A controller reboot may clear `/tmp`; only short-lived SSH sockets belong
there. Use a disk-backed `TMPDIR` for provider upload staging.
An optional trusted `TF_CLI_CONFIG_FILE` may select a previously verified provider
mirror; initialization still uses the readonly checksum lock. State/workspace
overrides are removed, and the CLI configuration never enters guest execution.

Copy [allocation.json.sample](vm/allocation.json.sample) outside Git. Have the
operator approve its node, **two unused VMIDs** (stopped template and one guest),
one reserved address outside DHCP, bridge, stores, DNS, gateway, workstation
public key and resource limits. A nonresponsive ping does not reserve an address.
The budget is one running guest, two vCPUs and 2 GiB RAM plus a stopped image
template. `vm/images.json` selects each imported template's `disk_gb` and each
**new** acceptance guest's `guest_disk_gb` (currently 16 GiB). Its Ubuntu
`builder_disk_gb` remains 32 GiB for Fedora image preparation. The existing
32 GiB per-disk ceiling remains enforced; it is not a minimum. Preparation
records the selected guest capacity in the manifest, provider inputs and guest
variables. Saved plans must match both selected template and guest capacities
exactly. A guest smaller than its image is rejected before preparation.
Failed retained runs still consume the pool.

The node's TLS CA and SSH identity must already be verified through a trusted
channel. Before provider access, the controller requires strict SSH verification
against the same user `~/.ssh/known_hosts` used by the pinned
[provider](https://github.com/bpg/terraform-provider-proxmox/blob/v0.118.0/proxmox/ssh/client.go),
which otherwise accepts unknown node keys. Global-only trust is insufficient.
The controller generates a unique guest SSH host key and delivers it in
sensitive cloud-init data over authenticated Proxmox/SSH. Its public half seeds a
private run-specific `known_hosts`; no unverified keyscan or disabled host-key
checking is used. The workstation private key is never copied into the guest.
Bootstrap snippets are created root-only (`0600`), checked through trusted SSH
before accepting the guest, and removed on retirement. Uploads refuse to adopt
or overwrite an existing file. The pinned provider requires root@pam API
authentication for `file_mode`, as it does for the explicit `ciupgrade` setting.
Rocky's disabled `guest-exec` remains disabled; package installation uses
cloud-init, not guest-agent execution.

Proxmox implicitly upgrades all packages at first boot unless `ciupgrade` is
false. The test root explicitly disables it; the shared module's new optional
`cloud_init_upgrade` input defaults to null, preserving existing callers. Setting
it requires root@pam API authentication. Bootstrap installs only declared
prerequisites through supported distribution mechanisms. Cloud-init must finish
without operational errors; Proxmox's legacy `user` deprecation is reported
separately and is not classified as an operational failure.

The pinned Ubuntu image brings `ens18` up in its initrd; renaming that active link
through Proxmox's generated v1 data fails. Its test root supplies standard v2
network data without `set-name`, using the optional `network_data_file_id` module
input. The controller validates its exact approved address, gateway and DNS
before apply and its exact bytes before retirement. Other callers retain
generated IP configuration by default. A DHCP address is never a test fallback.

The guest interpreter is a root-owned `/opt/homelab-molecule-ansible` virtual
environment with distribution site packages, preserving APT/DNF/RPM bindings.
Docker SDK, jsondiff, PyYAML and requests pins come from `ansible/requirements.txt`;
cloud-init installs that small subset from PyPI, without production clients or
EPEL. This explicitly prepares the SDK prerequisite documented for Rocky Swarm
operations; the production Docker installation role still does not supply it.

Runtime/application/network cases explicitly prepare and boot a matching Rocky
kernel plus module supplement when the pinned image's old kernel needs it. This
is disposable OS preparation, recorded separately from production installation.
Fedora bootstrap may select the distribution's nf_tables alternatives only when
the allocation explicitly approves `allow_nf_tables_alternatives: true` (default
false). It verifies the RPM provider, registered alternatives and all six tools.
Production roles still refuse legacy/mixed tools and never switch host
alternatives. SELinux remains enforcing.

Fedora's pinned Cloud image bundles Podman, so it cannot prove fresh runtime
installation. Runtime/application/network cases require a derived **Server 44-1.7**
image: the official runtime-free source and SHA-256 are in
`vm/fedora-source.json`. With separate `allow_image_preparation: true` approval,
the controller creates an Ubuntu builder within the same allocation, installs
libguestfs there, adds cloud-init using signed Fedora repositories, relabels
SELinux and transfers the generic image over verified SSH. It installs no
container runtime and removes none. Source, recipe, output checksum and actual
package versions accompany the private artifact; changed recipes or bytes fail
closed. The builder must retire successfully before the cache is published.
No workstation or Proxmox image tools are installed. Prepare it once:

```bash
python scripts/testing/vm.py prepare-fedora-image --allocation /private/allocation.json \
  --state-root /private/molecule-runs
```

The serial suite invokes this prerequisite automatically when needed. The
original Cloud image remains usable for the historical Node Exporter-only case.
Image preparation is recorded separately from Molecule acceptance.
Use `prepare-fedora-image --rebuild` with the same allocation/state arguments
after an intentional source or recipe change. Previous controller artifacts and
provenance are retained; guest/application data is never purged for freshness.
`--resume-builder /private/molecule-runs/<id>` may retry a failed **image builder**
only while its directory contains the checksum-verified source and no modified
image/export. Earlier attempts remain recorded. Once modification has started,
retire it and create a new builder. This option cannot adopt an acceptance guest
or bypass a Molecule fresh-host guard.

The prepared Server image grows its partition/PV but initially retains a small
root LV. After ownership/platform checks, readiness verifies its single-PV,
single-LV XFS layout and grows that existing volume/filesystem within the approved
selected guest disk, allowing up to 4 GiB for the pinned boot/EFI layout. A
different layout or capacity fails before growth; no formatting is permitted.
`vm/fedora-source.json` selects the capacity of **new** prepared images (16 GiB).
The builder checks the source virtual size before expanding and records and
verifies the output virtual size. Changing that recipe requires a new build;
existing 32 GiB artifacts and provenance remain retained, never resized. Use
their original checkout for recovery. Legacy manifests remain retireable with
their original disk bounds, but cannot resume provisioning through the new root.

## Run

From the repository root, with the trusted controller profile loaded:

```bash
run=$(python scripts/testing/vm.py prepare --allocation /private/allocation.json \
  --state-root /private/molecule-runs --os rocky102 --suite rocky_node_exporter)
python scripts/testing/vm.py provision "$run"
python scripts/testing/vm.py test "$run"
python scripts/testing/vm.py retire "$run" --confirm-run "${run##*/}"
```

`prepare` is offline. `provision` first refuses collisions; interrupted creation
may resume only when remote identities and this run's state agree. Cloud-init,
SSH and test execution have bounded waits. Provisioning also checks controller
space before mutation: at least 64 MiB for state, plus a prepared image's size and
64 MiB in `TMPDIR` for upload staging. Use disk-backed paths for images, unit
fixtures and provider scratch; a small RAM-backed `/tmp` is unsuitable.
On blacktop, private artifacts and upload scratch use
`/home/john/Desktop/homelab-vm-tests`; keep this directory outside Git.
Inventory contains only the disposable
subject and required test-only groups, explicit LAN address/user/port/Python,
and strict SSH settings. Every guest-facing action checks the current run's
root-owned marker, conventional KVM/systemd platform and RPM SELinux enforcement.

`test` invokes actual `molecule test`, with a private controller HOME/state and
an environment allowlist excluding management credentials and agents. It records
image pins, source revision/content fingerprint, exit status and duration.
Executable inputs must stay unchanged during a run; documentation updates are
excluded. A changing source tree cannot receive a passing acceptance result.
Scenarios retain version, process, metric
and packet evidence. Cleanup collects bounded diagnostics **before** owned
application removal. It retains declared data; VM retirement makes the next
fresh installation possible. No data purge is used to satisfy freshness guards.

After failure, inspect the private run, then run its exact retirement command.
No automatic VM destroy hook runs after a failed test. Retirement verifies exact
VM names/IDs/tags/descriptions/disks, exact image/snippet identities and file
contents, destroys only that state, then checks for surviving VMs/files/disks.
After those checks, retirement powers off only verified, state-owned guests
before disk deletion, with a 60-second confirmation bound. It uses the
[Proxmox stop operation](https://lists.proxmox.com/pipermail/pve-devel/2024-April/062924.html)
to overrule that guest's pending graceful shutdown; unrelated locks are retained.
An unresponsive guest agent cannot leave retirement waiting for an OS shutdown.
If interrupted creation lost state for an uploaded snippet, retirement can
recover it only from the validated saved creation plan, after allocated VMs are
absent and trusted node SSH verifies its exact bytes and permissions. Unverified
files and untracked VMs/images remain reported for explicit recovery.
An unconfirmed or interrupted retirement fails and retains state. Do not delete
the run directory or start another guest while recovery remains outstanding.
Raw journal commands are hidden; stored diagnostics omit key/token/auth lines.
Quadlet status before removal is retained separately from later observations.
Private state includes guest host keys and synthetic credentials; **never upload
it or raw provisioning logs as public artifacts**.

For a serial matrix, preview first, then execute on an approved allocation:

```bash
python scripts/testing/suite.py --suite all --os all
python scripts/testing/suite.py --execute --allocation /private/allocation.json \
  --state-root /private/molecule-runs --suite all --os all
```

Use `--suite runtime_install --order podman-first` with `vm.py prepare`, and
`--runtime compose|swarm|rootful|rootless` for individual application cases.
Each case gets new resource names, guest data and controller state. The suite
stops at its first failure, retaining that run and printing exact retirement.
The suite also accepts `--runtime swarm` with `--suite application_lifecycle`,
or `--order podman-first` with `--suite runtime_install`, to rerun one variant
on fresh guests after a correction.

## Recorded acceptance

On **2026-11-10**, the documented AMD64 matrix passed **32/32 cases** across
Debian 13, Fedora 44, Rocky 10.2 and Ubuntu 26.04. The original 29 successful
cases were retained; only the three failed Ubuntu cases received fresh full
acceptance reruns. Ubuntu's direct rootless cases require the guarded pasta
prerequisite below. Their passing Quadlet lifecycle remains separate evidence.
All four follow-up VM pairs, including the diagnostic run, were retired, and
the final allocation audit found no surviving test resources.

Repository checks remain separate from guest acceptance. Focused runs passed
314 and 64 checks. The earlier 41-failure comparison used feature-branch revision
`e49f085db0d1b1113d936cf926836f700aa81dac`, not the PR merge base, and does not
establish that those failures were unrelated to this branch. The PR #726 CI
follow-up and its repository-only validation are recorded in
[the testing guide](../docs/testing.md#pr-726-ci-repairs). Controlled VM CI was
not enabled or executed, and actionlint was unavailable.

The full completion record is archived as `molecule-results.md` in the private
Desktop `homelab-vm-tests` directory alongside the retained run evidence.
Historical failures, exact versions, commands, durations, baseline comparisons
and production-fix reviews remain available there.

## Scope and evidence

| Family | Prepared behavioural checks | Live result |
|---|---|---|
| Native Node Exporter | Fresh check, real playbook/catalogue, metrics, loopback, boot, zero changes, same invocation, retained-data removal | Passed on all four platforms |
| Runtime installation | Both orders, real install-only selections, engines/CLI ownership, rootless mapping, capability gates, no Swarm/apps, daemon preservation | Both orders passed; Ubuntu requires the pasta prerequisite |
| Application lifecycle | Compose, single-node Swarm, rootful/rootless Quadlets; HTTP, UID writes, config/native secrets, converge, failed prepare, recreate including absent, restart/reboot recovery, retained-data removal | All four variants passed on each platform |
| Protected networking | Real dual-stack qualified probes/counters and denial via a separate veth/network namespace; reload, restart, reboot, disappearing Swarm caller, worker ranges | Passed within the platform scope described below |

The isolated namespace has its own network stack and enters through a real veth;
its healthy-listener baseline and matching generated DROP counters are required.
Connection refusal or routing failure cannot pass as denial. This proves that
separate traffic path, not a second physical machine or a multi-node overlay.
Each qualified probe must match the independently observed current caller's
network namespace; caller restart must replace its process.
This focused firewall suite uses Docker callers, including a Swarm task. Podman
bridge/DNS and application lifecycles are separate checks; protected Podman
caller traffic is not certified by this suite.
Reload/restart/boot checks allow bounded recovery by the real production
reconcile timer before auditing rules and traffic. They establish recovery and
steady enforcement, rather than zero downtime during reconfiguration.
Ubuntu 26.04 tests the manager profile; Ubuntu workers remain restricted to 24.04.
Worker-range cases run on the supported Debian/Fedora/Rocky platforms. These
counter checks use the real policy transaction, persistence tasks and
reader, with sources observed on the isolated peer. They do not certify the
temporary migration planner's two-worker placement contract. All six
iptables tools must select nf_tables; production roles fail rather than switch
host alternatives or relax firewalld/SELinux.

Only the synthetic credential *source* is substituted by a controller-only
fixture collection. It refuses production paths/other run IDs and has no network
access. Runtime secret creation, attachments and lifecycle are the production
adapters. This is not Infisical integration acceptance.
Application cases invoke `ansible/playbook.yml` with a single fixture catalogue
as explicit extra vars. Only the selected target is enabled; other variants
cannot reserve its publication. No deployment task or probe is replaced.
Swarm removal is [asynchronous by default](https://docs.docker.com/reference/cli/docker/stack/rm/).
The production adapter uses bounded removal retries and waits for its stack-labelled
networks to retire before replacement; failed cleanup retains the manifest.
Swarm uses scoped shared bind labels and omits unsupported no-new-privileges;
Compose/Quadlet use private labels and enable that option. All fixture variants
run as UID 1000 with every capability dropped. These are explicit runtime
limitations, not bypasses of production validation or host security settings.

The separate VM workflow stays disabled until `MOLECULE_VM_TESTS_ENABLED=true`, a
protected `disposable-vm-tests` environment and a dedicated trusted controller
exist. Its `restricted-disposable-vm-controller` runner group must enforce
[selected-workflow access](https://docs.github.com/en/enterprise-cloud@latest/actions/how-tos/manage-runners/self-hosted-runners/manage-access)
for only `Lebowski89/homelab/.github/workflows/vm-tests.yml@refs/heads/main`.
That server-side boundary is required: public PRs can change other workflows to
target a standing runner, bypassing job conditions and environment declarations.
If the account/platform cannot enforce workflow/ref restrictions, leave this
workflow disabled and invoke the CLI from a trusted external controller. Do not
register an unrestricted runner with this public repository, put one on mgt or
expose a production Docker socket. No runner is installed here.

The controlled lane accepts trusted main-branch push/manual/scheduled work,
serializes the allocation and selects affected families; documentation changes
start no guests. Public CI retains lint/unit/CLI guards and its required
fail-closed aggregate, without infrastructure credentials.

Later suites: Alloy delivery; Technitium DNS/resolver restoration; isolated
**two-VM** Keepalived; PostgreSQL/etcd/Patroni, queries and backup/isolated restore;
selected system/resolver features. Multi-node overlay and Patroni failover need
separate multi-VM allocations. Ordinary VMs cannot certify physical X710 behaviour.
LMDE remains targeted to supported workstation/runtime paths, outside this matrix.

Read-only cached image file IDs may be supplied in `allocation.image_file_ids`.
Their exact bytes are checked against the matrix checksum over trusted node SSH
before provisioning. They are never adopted into test state or deleted. Otherwise
the root downloads a run-owned image and verifies its checksum.

Mixed-runtime cases explicitly
select the existing `podman_docker_iptables_compatibility` opt-in. Its reviewed
Netavark version and nf_tables gates remain unchanged.
Podman-first installs with its distribution provider, installs Docker, then uses
the real configuration-only Podman entry point to select coexistence. That option
deliberately requires existing nf_tables helpers; the test does not make Podman
silently install them or change its production responsibility. Reruns retain the
selected provider and must still produce zero changes.

Ubuntu's direct rootless runtime probe explicitly invokes the separately guarded
`podman_pasta_signal` operation through the real `ansible/operations.yml`, after
installation. This host-security preparation is authorized only for the current
guarded disposable guest. It grants pasta only receipt of SIGTERM from peer
`podman`; it does not change production installation/deployment defaults.
The task supplies reviewed package-profile hashes, retains the static inventory's
controller group despite the operation's `vars_files`, checks zero-change
repetition and requires pasta to remain enforcing. Package/profile drift fails
the existing ownership, hash and parser guards. The real HTTP/cleanup commands
still have to pass, and the current account must have no remaining pasta helper.
The passing systemd-managed rootless Quadlet lifecycle is separate evidence.

The Ubuntu bootstrap leaves the RPM CA-trust `bootcmd` empty. In the pinned
cloud-init 26.1, even that Ubuntu no-op otherwise requests a synchronous early
network wait before sysinit. With native firewalld's network-pre ordering this
deadlocks boot. Emptying the unnecessary command lets cloud-init make its normal
NoCloud network-wait decision; network activation/configuration, static LAN
addressing, firewalld ordering and policy remain unchanged. The reboot bound is
still 300 seconds. Ubuntu's protected-network case also requires completed
post-boot cloud-init without operational errors before checking policy/traffic.
Other distributions retain their existing bootstrap command.
RPM cases also select Docker's existing SELinux opt-in; the role default remains
unchanged, and the guest must stay enforcing throughout verification.

Evidence is stored in `<run>/evidence`, outside Molecule's temporary directory:
Molecule prunes that directory after failure. `vm.py diagnose <run>` can collect
additional read-only evidence before retirement. Firewalld checks compare actual
activity and boot enablement, preserving raw observations; an absent unit and a
systemd `not-found` dependency stub are both inactive, rather than a policy change.


## Dedicated Forgejo controller rollout (preparation, not deployed)

GitHub remains authoritative; its controlled live workflow stays disabled.
The separate private Forgejo CI repository will expose manual selections only.
Repository preparation precedes one rollout approval. Read-only authentication
verified the dedicated non-admin `homelab-ci` account and installed Forgejo
**15.0.9**. The proposed private repository `homelab-ci/homelab-ci` does not exist.
Runner **13.2.0** was downloaded in isolation and its detached signature verified
against the upstream release key; its configuration and workflow parser were
exercised offline. No controller, repository or runner has been created.

Actions enablement on the existing Forgejo instance has separate, explicit
authorization; it does not authorize the controller, CI repository or runner.
The managed maintenance operation freezes the actual 15.0.9 image by repository
digest, disables image pulls and uses temporary `preserve` policies for all four
existing secrets. The canonical image pin and PostgreSQL secret reconciliation
policies remain unchanged. The route renderer matches the live route bytes;
its mapped rootless UID/GID are retained through operation-specific variables.

The first recreation passed HTTPS health, login-form availability and the correct
`POST /api/actions/ping.v1.PingService/Ping`, without changing the image, secrets,
data ownership, route or unrelated service/container identities. A strict
firewall snapshot comparison failed, so the normal scoped lifecycle restored
Actions to disabled. Investigation found 23 duplicate PostgreSQL grant rules
(10 IPv4, 13 IPv6): the existing verified UID 1004 binding and newly recorded
service binding both resolve to `podman-forgejo`. No rule was removed, no distinct
rule predicate or its first-occurrence ordering changed, and the access ledger
added no provider port. The installed policy/persistence audit reports compliant
IPv4/IPv6 rules with no pending items. This is ordinary scoped ownership
reconciliation, not a new firewall permission or a reason to delete baseline
bindings. The original failure and rollback evidence are retained privately at
`.ansible/forgejo-controller-prep/live/attempt-1/` (557.49 seconds including
scoped rollback). The retry passed the same strict preservation checks in
**281.49 seconds**: image ID/version, four secret IDs/content hashes, data mount
and ownership, route bytes/ownership, firewall rules, unrelated container IDs
and system service invocation IDs remained unchanged against the recovered
baseline. The managed run reported 351 successful tasks, four changed, no
failures. A separate read-only installed-policy/persistence check returned
`compliant=true`, `rules_compliant=true`, both families and no pending items.
Normal certificate validation passed; health and login form returned HTTP 200,
with one active administrator. Authenticated administrator password login was
not exercised. The correct Actions Ping returned HTTP 200 with its expected
`Hello, ...!` response. No host, Podman, database or unrelated service was
restarted. The maintenance used `skynet limit mgt raw --tags recreate,forgejo
-e @<private-operation.json>`; the value-free private operation catalogue froze
the existing image and ownership rather than changing production defaults.
Final evidence is `.ansible/forgejo-controller-prep/live/outcome.json`. No CI
repository, runner registration or controller VM has been created.

The runner's 12-hour job bound also requires the Forgejo server's
`ENDLESS_TASK_TIMEOUT` to permit the selected suite. The read-only post-maintenance
inspection confirms `ENABLED=true` and no explicit endless/zombie timeout
overrides in app.ini, so the version's default server bound remains relevant.
Adjusting it would require a separately scoped production change; broad selection
must not silently hit the [default 3-hour server bound](https://forgejo.org/docs/v15.0/admin/config-cheat-sheet/#actions-actions).
Initial acceptance is only the single Rocky case.

The reviewed harness changes must reach GitHub `main` through its normal process
before the first run can certify the new sizing. The workflow always fetches
that trusted branch, records its exact SHA, and checks it out detached. It cannot
exercise uncommitted local changes or an arbitrary supplied ref. This work does
not authorize GitHub commits, pushes or PR changes.

Proposed allocation: `molecule-controller`, candidate VMID **9300**, Rocky
(template **9004**), **192.168.80.41/24**, `pve1`, `vmbr1`, two vCPUs,
4 GiB RAM and a **32 GiB persistent controller disk** on `local-zfs`; snippets on
`local`. VMID 9300 was available during the read-only preparation audit and must
be rechecked before creation. The user reserved .41 and confirmed the separate
disposable .44/24 reservation. The two disposable VMIDs remain 980000/980001;
controller and test resources must have separate state.

Sizing evidence inspected on 2026-11-12:

| Image | Base virtual size | Imported template | New acceptance guest |
|---|---:|---:|---:|
| Debian 13 | 3 GiB | 3 GiB | 16 GiB candidate |
| Fedora Cloud 44 | 5 GiB | 5 GiB | 16 GiB candidate (Node Exporter only) |
| Rocky 10.2 | 10 GiB | 10 GiB | 16 GiB candidate |
| Ubuntu 26.04 | 3.5 GiB | 4 GiB | 16 GiB candidate |
| Fedora Server 44 | 10 GiB | 16 GiB newly prepared image | 16 GiB candidate |

Base sizes came from bounded QCOW2 header reads at the pinned public HTTPS
URLs; those reads do not independently verify full-image checksums. Provisioning
still verifies the full pinned images. The retained Server layout independently
records its original 10 GiB disk. Stopped Debian/Ubuntu import capacities are
rounded base-image ceilings, not runtime budgets; templates never boot. Existing
larger templates are never resized. The existing prepared artifact has a 32 GiB
virtual disk but occupies about **0.96 GiB** as a compressed local QCOW2 file;
that file size does not establish either guest peak usage or Proxmox allocation.

There are 55 retained root-filesystem snapshots: maximum recorded used space is
2.23 GiB Rocky (21 observations), 3.44 GiB Debian (10), 3.31 GiB Ubuntu (13),
and 3.63 GiB Fedora (11). They are diagnostic snapshots, **not continuous peak
measurements**. One failed Fedora root had only a 3.12 GiB LV inside a 32 GiB disk;
that demonstrated missing LV growth, not a need for a 32 GiB disk. The guarded
LV/XFS growth remains. Sixteen GiB is a conservative candidate with substantial
headroom over recorded usage, not new live certification. No smaller
scenario-specific size is selected without stronger evidence. The Ubuntu image
builder retains 32 GiB because its libguestfs installation, source, expanded
image and compressed export can coexist; its peak is not measured sufficiently
to select 16 GiB safely.

The controller has a separate provisional 32 GiB budget: 4 GiB OS, 4 GiB tooling,
8 GiB image/provider/pip caches, 4 GiB checkouts and upload staging, 6 GiB retained
run evidence, and 6 GiB free headroom. These are planning allowances, not measured
peaks. All reside on persistent disk, including `TMPDIR`; only short SSH sockets
may use `/tmp`. Failed evidence is never deleted automatically to make space.
Capacity exhaustion must stop new work and require an operator decision.

The audit reported about **95.4 GiB available**. Saved node filesystem evidence
places `local` (`/var/lib/vz`) and `local-zfs` (`rpool/data`) on the same `rpool`;
their free space must not be added. A normal prepared-Fedora pair has 32 GiB of
logical disks (16 + 16), while the conservative builder pair has 36 GiB (4 + 32).
With a fully allocated 32 GiB controller, the larger pair, a provisional 5 GiB
allowance for node-side cached/uploaded image files, and 15 GiB pool headroom,
the incremental budget is **88 GiB**, plus small EFI/cloud-init disks and
filesystem overhead. This is close to reported availability and is **conditional**,
not approval to overcommit or a guarantee of future free space.

`local-zfs` uses raw ZFS volumes: logical `volsize`, written/allocated blocks and
`refreservation` are different quantities. Neither the API free-space figure nor
a compressed QCOW2 size proves thin provisioning, zero reservation or sufficient
space for outstanding reservations. The existing rollout plan must include one
bounded read-only check immediately before creation: Proxmox storage settings
(including `sparse`), `zpool list`, and `zfs list/get` for `used`, `available`,
`volsize`, `reservation`, `refreservation`, quotas and pool health. Check the
shared backing pool and existing reservations, refresh available RAM and VMID
availability, and budget the selected pair plus image staging and headroom.
If that check cannot substantiate the budget, pause for additional approved
capacity; do not shrink existing VMs, change shared-module defaults, erase old
images/evidence or rely on unverified thin provisioning. No live matrix is
needed for that decision. The first approved acceptance remains one
`rocky_node_exporter` / `rocky102` case, now validating the candidate 16 GiB disk.


### Repository preparation validation

Using the existing Python 3.13.5 / Ansible 2.21.5 environment, with no dependency
installation or upgrade during this work:

- `python -m pytest tests/unit/test_native_services.py tests/unit/test_molecule_vm.py
  tests/unit/test_molecule_fixtures.py tests/unit/test_forgejo_controller.py -q
  --tb=short`: **149 passed, 465.22 seconds**. These are offline entry-point,
  rendering, safety/identity and simulated-host tests, not new live acceptance.
- `python -m pytest tests/unit -m 'not integration and not operator' -q
  --tb=short`: **2,212 passed, six skipped, 1,344 deselected, 43.50 seconds**.
  The six existing PostgreSQL membership cases could not import the collection
  through the local Python namespace. The four complete CI groups were not run.
- Focused Ruff check/format, Ansible lint `--offline` (78 files, production
  profile), localhost-only Fedora preparation syntax, OpenTofu formatting and
  `git diff --check`: passed. The controller root is not initialized and its
  pinned provider is absent locally, so offline `tofu validate` is unavailable;
  validation after approved initialization remains a rollout prerequisite.
- Checkov **3.4.3**, repository configuration against a public-source snapshot:
  **508 passed, zero failed, 25 skipped, zero parsing errors**. The known
  runtime-staged Molecule module path cannot be loaded before staging; source
  modules are scanned separately. Changed-source Gitleaks **8.24.3**: no findings.
  This is not a new historical Git-range scan.
- The signed pinned Runner **13.2.0** accepted its configuration and parsed the
  manual workflow offline; a bounded daemon smoke used only synthetic credentials
  and a closed loopback endpoint. Real registration, controller boot persistence,
  node/API authentication and the new 16 GiB guest remain unverified until rollout.

### Rollout scope and commands, pending approval

- Infrastructure: only the new VM root `terraform/proxmox/vms/molecule-controller`,
  template 9004 clone into verified-free VMID 9300, and the four NetBox resource
  instances for `molecule-controller` (device, interface, address, primary IP).
  No changes to VM104, VM9100, PostgreSQL VMs, their allocations or shared-module
  defaults. The controller boots with its node and has deletion protection.
- Service: `services/forgejo_runner.yml`, controller host_vars and the existing
  `native_services` entry point own installation. Units are `forgejo-runner` and
  `forgejo-runner-agent`; there is no new role or container engine. Ordinary
  `deploy/update/recreate/remove` and check mode use the catalogue dispatcher.
- Forgejo: create only private `homelab-ci/homelab-ci`, initialize its default
  branch, upload only `.forgejo/workflows/molecule.yml`, disable its issue/PR/wiki
  surfaces, and register `molecule-pve1-rocky` **at repository scope**. Initialization
  and workflow upload create private CI bootstrap commits; that requires explicit
  rollout authorization and does not authorize a GitHub commit/push. The
  deployment-side preparation script is
  `.ansible/forgejo-controller-prep/forgejo-prepare.py`; it is not a runner-side
  application. Its retained repository/registration receipts make retries
  idempotent; existing remote registrations without their receipt fail closed.
- Credentials: Infisical `prod`, `/Forgejo/CI_API_TOKEN`, supplies only setup API
  authentication. Its verified account is non-admin and needs `write:repository`,
  `write:user`, `read:misc`, with the All repository-access selector; it owns only
  this CI repository. No organization or instance runner registration is used.
  The VM receives only its UUID/token receipt, a separate PVE API token, dedicated
  node and guest SSH keys, public CA/known-host identities and allocation file.
  No Infisical login, Forgejo setup token, personal SSH key or general admin token
  is copied to it.

Proposed private deployment directory:
`/home/john/.config/homelab/molecule-controller` (0700; private files 0600).
Create fresh, separately named controller-admin, controller-host, bootstrap-node,
node and guest Ed25519 identities after approval; never overwrite existing keys.
The bootstrap-node key is transient, restricted to the workstation source; the
persistent node key is restricted to controller .41 with OpenSSH `restrict`.
Use the existing trusted operator administrator channel only to install these
new public keys and create the dedicated credentials/ACLs; it is not provisioner
authentication on the VM. Preserve an exact private backup and receipts for the
new lines/IDs so rollback never removes unrelated keys or tokens.

The pinned provider/harness still requires **root node SSH**, and a root@pam
API identity for private snippets/explicit cloud-init settings. Use privilege-
separated dedicated tokens, never Administrator/privsep=0 or `ssh.root_ticket`:

| Identity / path | Proposed privilege boundary |
|---|---|
| `root@pam!molecule-vm-acceptance`, `/vms/980000` and `/vms/980001` | VM allocation/audit/power and only CPU, memory, disk, cloud-init, network, hardware/options/CDROM configuration and guest-agent audit needed by the harness |
| Same token, `/vms/980000` only | Clone the owned stopped template |
| Transient `root@pam!molecule-controller-bootstrap`, `/vms/9300` | Corresponding controller lifecycle/configuration privileges |
| Bootstrap token, `/vms/9004` | Template audit and clone only |
| Each token, `/nodes/pve1` | Node audit only |
| Each token, `/storage/local-zfs` and `/storage/local` | Datastore audit, space allocation and template/file allocation |
| Each token, `/sdn/zones/localnetwork/vmbr1` | Bridge audit/use required by the pinned provider |

Confirm exact privilege names against the installed PVE version and actual saved
plan/API requests. A denied operation fails visibly; never fall back to a general
admin token or broaden grants automatically. Storage privileges are not filename
quotas, and root SSH remains root-equivalent beyond API ACLs. The two-VMID/address,
identity, file-byte and disk-budget checks are additional software guards, **not**
Proxmox ACL confinement. Only trusted manual jobs in this private repository may
use this dedicated VM.

After the prerequisites and one approval:

1. Perform the bounded capacity/identity checks above, including VMIDs 9300 and
   980000/980001, .41/.44 reservations, pool reservations/health and available RAM.
   Allow 4 GiB controller + 2 GiB active guest without reducing existing VM memory
   or host protection. Keep all staging on persistent disk. Stop on insufficient
   capacity or an occupied/foreign resource; never adopt it.
2. Add only the controller's private NetBox inputs (.41/24, `rocky`, port 22).
   Plan the four `molecule-controller` instances and their existing dependencies;
   apply only a reviewed create-only saved plan. Verify its primary IP and tags
   (`skynet`, `opentofu_managed`) and updated state outputs. Do not reconcile
   unrelated NetBox objects to make the target plan pass.
3. Generate/provision only the named private keys, dedicated tokens, CA and
   verified SSH entries. The CI allocation uses node `pve1`, LAN SSH/API .80,
   VMIDs 980000/980001, .44/24, vmbr1, local-zfs/local stores, gateway .1 and DNS
   .53/.54. `private_key_path` is the guest key;
   `node_private_key_path` is the different management key. Store only the PVE
   token in `provisioning.json`. Registration credentials are a different file.
4. Run the private Forgejo preparation script with `--approved-rollout` after
   the global Actions prerequisite is satisfied. Inspect repository privacy,
   exact repository-scoped runner ID and the new receipts. No global/account
   registration, automatic triggers, schedules or public/fork execution.
5. Initialize the new root with pinned providers; run offline validation, then
   `tofu -chdir=terraform/proxmox/vms/molecule-controller plan` with the explicit
   private var-file and a private saved plan. Require only controller 9300 and
   its private bootstrap snippet, no replacements/foreign resources. Apply that
   saved plan. Use `SSL_CERT_FILE` with the verified CA and strict SSH preflight
   against the same known_hosts before provider operations. No insecure TLS or
   automatic SSH enrollment. State remains separate from the disposable pool.
6. Build a controller-only private inventory from its NetBox identity, with its
   injected, already-known SSH host key and dedicated admin key. Use normal
   Ansible config and `--limit molecule-controller`. With
   `native_services_forgejo_runner_private_source_dir` in a private vars file,
   run `skynet limit molecule-controller check forgejo_runner`, then
   `skynet limit molecule-controller deploy forgejo_runner`. Generic tags work
   even before the operator wrapper receives the new `forgejo-runner` alias.
   Review and repeat the normal deployment path for idempotency; no desktop or
   production-host plays may execute.
7. Verify HTTPS, private profile/allocation permissions, actual filesystem/free
   capacity, runner scope/label/capacity, units enabled/active and node/API access
   without printing values. Reboot **only controller 9300**, reconnect with strict
   SSH trust, and verify the dedicated SSH agent reloaded its key without an
   interactive workstation agent. Dispatch exactly `rocky_node_exporter` /
   `rocky102` on private CI `main`; record the fetched GitHub SHA, real role result,
   durations and confirmed VM/file retirement. Leave schedules disabled. Revoke
   only the transient bootstrap credentials after scoped recovery is no longer
   needed. Do not declare the new 16 GiB configurations fully certified.

### Operator use and scoped recovery

Open the private Forgejo repository's **Actions → Live VM acceptance → Run
workflow**, using CI branch `main`. Defaults select one Rocky Node Exporter case.
Other choices are the four existing suites and four existing OS pins, or `all`;
use the broad choice only after its capacity and server timeout are verified.
There is one runner slot and one controller lock; requests never cancel active
work. The GitHub controlled live workflow remains disabled.

Job logs contain the GitHub SHA and private evidence location. On the controller,
`/var/lib/forgejo-runner/jobs/<job-id>/source.json` preserves the checkout/SHA;
`runs/<run-id>` holds provider state, manifests and evidence. Each new run gets a
`controller-source.json` mapping to its retained checkout. No private state,
credentials or evidence are uploaded as public artifacts. If a controller process
is killed before it can write that mapping, retain its job receipt and the
run's `ansible.cfg` source paths; recover with the original checkout and private
profile through the existing `vm.py retire` guards, never guess/adopt state.

A failed case stops the suite and retains its allocation. The job prints:

```text
sudo -u molecule-ci homelab-molecule retire <exact-32-hex-run-id>
```

The launcher supplies private provisioning authentication and delegates to the
original checkout's `vm.py retire --confirm-run <id>`. Verify `retired.json` and
absence of the run's exact VMIDs/files before retrying. Do not remove state,
receipts or evidence merely to unlock the allocation.

Runner maintenance is serialized by a root-owned, token-bearing drain directory
across installation changes and handler completion. Acceptance and explicit
retirement both honor it. A failed/interrupted operation retains its marker;
confirm that operation ended, then release only its recorded ownership token
through the [scoped maintenance recovery](../docs/ansible/native-services.md#dedicated-forgejo-runner)
module before retrying. Do not blindly delete the marker or stop an active case.
Removal remains available without provisioning credentials; recreate needs only
resident restart inputs. Neither operation reads a new registration receipt.

Rollback first drains the runner and refuses active work. Retire any failed
owned test run explicitly; then use the ordinary runner removal path. It stops
both owned units and removes only recorded unit/config files, retaining keys,
registration, profile, tooling, checkouts, caches and evidence. Unregister only
the exact new repository runner ID and archive the owned private CI repository
rather than deleting its logs. Export/verify private evidence before any optional
controller destruction. If removal of controller 9300 is approved, clear only
its deletion protection, review/destroy only its new root's state-owned resources,
and retire only its four NetBox objects and newly created ACL/key/token entries.
Never destroy other VM roots, erase prior images/evidence or touch production
PostgreSQL/etcd, the Rocky migration VM or Proxmox services.
