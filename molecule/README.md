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

The reusable `node_exporter` scenario selects its OS separately with `--os`:
`debian13`, `fedora44`, `rocky102` or `ubuntu2604`. All use the same scenario and
real native-service catalogue entry point. The pinned image metadata selects
platform/version/package-manager checks and SELinux enforcement; preparation uses
APT or DNF only where required. Historical evidence retains the former
`rocky_node_exporter` name; the rename does not certify another distribution.
There is one lifecycle root and one running guest per approved allocation, rather than a provisioning root per role.
Scenario playbooks remain in the repository after a run. Retirement removes only
that run's verified disposable VMs/artifacts, retaining its private evidence and
original source checkout. Scenario cleanup still removes its owned guest service
before VM retirement.
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
  --state-root /private/molecule-runs --os rocky102 --suite node_exporter)
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


## Dedicated Forgejo controller rollout (in progress)

GitHub remains authoritative; its controlled live workflow stays disabled.
The private Forgejo CI repository exposes manual selections only.
The approved rollout created `homelab-ci/homelab-ci` and its repository-scoped
runner **ID 1**; retain and reuse that registration rather than registering again.
The dedicated non-admin setup identity is `homelab-ci`; installed Forgejo is
**15.0.9**.
Runner **13.2.0** was downloaded in isolation and its detached signature verified
against the upstream release key; its configuration and workflow parser were
exercised offline. On 2026-11-14, the approved controller VM9300 was created
in **72.15 seconds**, reusing its owned bootstrap snippet unchanged. Its actual
configuration is `vmbr1`, 2 CPUs, 4096 MiB RAM, 32 GiB disk, on-boot and protected.
Template 9004's configuration hash is unchanged. Strict first-boot SSH and the
guest agent passed; cloud-init completed without execution errors but reports
the PVE-generated string `user` field's deprecation. That warning is retained,
not described as a clean cloud-init result. Runner ID 1 is now online under the
approved mount amendment below, with a successful named restart. Its first
Rocky case stopped at strict SSH readiness and retained its owned resources;
Node Exporter production-role execution and acceptance retirement are not certified.

The original clone failure and partial state are retained privately under
`~/.config/homelab/molecule-controller/controller-stopped-1794584390423879413/`.
The source-bridge grant below resolved that failure without changing template
9004. First-install prerequisite failures are retained in the private
`controller-service-deploy-*/` evidence. The native runner installs `acl` before
switching to its unprivileged tooling account. Controller host variables select
parallel Python 3.14 for the pinned Ansible 2.22 tooling, retaining `/usr/bin/python3`
for host modules and Rocky's packaged bindings. No system Python replacement is
required. The normal OpenTofu key host returned HTTP 403; this controller selects
the armored copy from the official distribution repository at an immutable
revision. Its fingerprints match that revision's binary key. Both signing keys,
package-signature verification and normal TLS verification remain enabled.


The original rollout stopped on an additional, then-unapproved security-policy requirement:
SELinux in enforcing mode denies `init_t` **execute** access to
`ssh_agent_exec_t` when systemd starts `/usr/bin/ssh-agent` (`203/EXEC`). At that
checkpoint no allow rule, relabel, permissive mode or hardening relaxation had
been applied. After
verifying the native ownership record and unit bytes, only the newly owned agent
was stopped and disabled to end its retry loop. At that original checkpoint
the runner was inactive/disabled and its failed-operation marker was retained.
Runner ID 1 was offline, no acceptance job had been dispatched and the disposable
VMIDs were absent. Those historical checks did not prove boot persistence,
authentication or a Rocky acceptance pass; current results are recorded below. The subsequently approved candidate was attempted and
rolled back as recorded below. Any further policy permission requires review;
do not generate broad policy from the new AVC. A host reboot is not authorized.

### SELinux policy: initial rollback and approved mount amendment

Read-only inspection of the installed policy established that `init_t` cannot
execute `ssh_agent_exec_t` or transition directly to the existing login-user
agent domain with `NoNewPrivileges`. The stock user unit is not a safe automatic
replacement: this controller's default login mapping is unconfined. Also, the
default system-service transition for the runner's `bin_t` binary is
`unconfined_service_t`. Moving the unit or changing its Unix user alone would not
establish confinement. Both existing system services and the dedicated Unix
account are retained in the proposed correction.

The exact candidate is
`ansible/roles/native_services/files/forgejo_runner/selinux/homelab_forgejo_runner.te`
with the role template `homelab_forgejo_runner.fc.j2`. It creates the
application-specific agent domain `homelab_forgejo_agent_t`, runtime-file type
`homelab_forgejo_agent_run_t` and four named credential-file types. The module permits systemd's explicit confined
transition, including its `NoNewPrivileges` transition, and the existing
`env`/`ssh-add` post-start command in that same domain. The agent inherits the
installed SSH-agent, NSS and logging baseline attributes; its additional socket
permissions cover its own runtime type and confined `user_t`/`ssh_t` clients.
There are no explicit unconfined attributes, permissive declarations or denial
suppression in this module. Its inherited permissions are broader than its
explicit allow statements: the linked candidate has SELinux `setgid` permission
from `ssh_agent_type`, TCP/UDP DNS and TCP DNSSEC access, enabled Kerberos/OCSP
access, and route-netlink socket access through the NSS baseline. LDAP and NIS
rules are present but their booleans are currently disabled. Node/interface
permissions are generic, not restricted to particular destination IPs. Generic
packet/peer/IPsec and inherited AFS socket permissions also remain. This is not
a network-isolated agent. SELinux `setgid` permission does not itself supply a
Linux capability; the units retain their existing capability configuration.
`bin_t` execution remains broader than just the named env/ssh-add commands. The
runner uses generic `user_t` permissions and its SSH transition permission is
controller-wide. No system executable is copied or relabeled.

The runner explicitly uses existing `user_u:user_r:user_t:s0`; the agent uses
`system_u:system_r:homelab_forgejo_agent_t:s0`. The module additionally permits
`user_t` to make its existing confined `ssh_t` transition under
`NoNewPrivileges`. This permission applies to that domain pair on the controller,
not just one PID. Home, descendant and `.ssh` labels become respectively
`user_home_dir_t`, `user_home_t` and `ssh_home_t` only beneath the configured
controller home; `/run/forgejo-runner-agent` receives the private runtime type.
Unix ownership, `0700` directories, `0600` keys and all existing unit hardening
remain unchanged. The agent changes to `Type=forking`: installed OpenSSH's agent
binds its socket before the parent exits, so post-start key loading follows
socket readiness without polling or a fixed sleep.

Only these credential filenames receive new labels; their parent directories
retain their labels and Unix permissions:

| Files | SELinux type | Agent read/open | Runner `user_t` | Client `ssh_t` |
| --- | --- | --- | --- | --- |
| `/etc/forgejo-runner/private/node-key` | `homelab_forgejo_node_key_t` | Yes | Yes | Yes |
| `/etc/forgejo-runner/private/provisioning.json` | `homelab_forgejo_provisioning_t` | No | Yes | No |
| `/etc/forgejo-runner/private/registration.json`, `/etc/forgejo-runner/config.yml` | `homelab_forgejo_registration_t` | No | Yes | No |
| `/etc/forgejo-runner/private/guest-key`, `guest-key.pub` | `homelab_forgejo_guest_key_t` | No | Yes | Yes |

The node identity remains readable by the existing provisioner/SSH paths; this
does not change the harness's authentication contract. The new credential types
have only `file_type`, without generic configuration/home attributes. An isolated
link against the installed policy confirms no agent read/open allow rules for
provisioning, registration/configuration or guest keys, even among conditional
rules. An explicit `neverallow` checks that boundary when linking. This is a
file-access boundary, not complete isolation of processes
sharing a Unix account or protection against a privileged policy administrator.

The approved existing native lifecycle builds and installs only
`homelab_forgejo_runner` at priority **400**, using root-owned `0700` storage under
`/var/cache/forgejo-runner/selinux/<source-digest>/`. Source, file contexts,
package and installation intent are retained. The existing native ownership
receipt records the payload digest and installed module checksum before labels
or units change. Foreign or modified modules are rejected before maintenance;
an unchanged deployment does not rebuild/reinstall the module. Check mode only
inspects and plans. Interrupted installation retains its intent and maintenance
ownership for review rather than silently adopting policy.

Every policy installation or replacement checkpoints before rewriting native
ownership, policy, labels or units: the retained legacy migration, a fresh
installation, and an owned C0 → C1 upgrade all use the same recovery executable.
An unchanged installed policy skips checkpointing, building and arming. The role-owned
`files/forgejo_runner/selinux/rollback.py` executable is installed root-owned,
mode `0700`, at `/var/cache/forgejo-runner/selinux/rollback.py`. Its immutable,
root-only `<source-digest>/rollback.json` stores exact old unit/native-receipt
bytes (or their verified absence), UID/GID, modes, timestamps and extended
attributes, unit enablement states, pre-existing home and named-file labels,
enforcing state and the prior module identity. For upgrades, `previous.pp` is a
private copy of the prior owned package; its package hash and compiler-derived
CIL checksum must match the installed C0 module before checkpointing and are
checked again before recovery. Missing or mismatched prior packages fail closed.
Credential contents are never copied into the snapshot. The legacy migration
still requires offline/disabled units, no previous module and no retained agent
runtime directory. A fresh installation records absent ownership/units without
claiming existing foreign files or services. Upgrades require matching prior
native policy ownership. Existing snapshots are never overwritten or rebound to
a later maintenance receipt.

The legacy migration intentionally retains maintenance ownership after handler completion
until the named agent/runner checks pass. Only then may the operator release that
same receipt through the existing maintenance module. For the initial matching operation on
**molecule-controller only**, the historical rollback command was:

```sh
sudo /usr/bin/python3 /var/cache/forgejo-runner/selinux/rollback.py rollback \
  09dc0755c8eb9c24da44fbd3f38e6801ca394e14e20ebf68e0d41aa4be6a2c32
```

The executable verifies hostname, account/home ownership, root-only snapshot,
matching maintenance-receipt hash and native ownership. It holds `controller.lock`
non-blockingly throughout recovery and rejects unexpected unit bytes, symlinks,
foreign module priorities/checksums or a changed receipt before mutation. It
stops/disables only the owned units, restores the verified prior priority-400
module (or removes the proven candidate when no prior module existed), restores
base labels on newly created paths and exact recorded labels on retained paths,
restores old units and native ownership metadata, and reloads systemd. Previously
enabled units regain enablement without being started; legacy units remain
offline/disabled. For fresh installs, only verified candidate unit/ownership
files are removed; newly created credentials, home and evidence are retained.
It does not start a retry
loop, release maintenance, remove registration/credentials, delete run evidence,
or invoke normal service removal. Failed/interrupted recovery retains its
checkpoint and receipt for inspection/retry. File restoration stages a replacement
in the destination directory, verifies its complete bytes and metadata, syncs
the file, atomically replaces the live path, and syncs the directory. Recorded
timestamps are restored after systemd reload and synced again. Interruption
leaves each live file wholly old or wholly restored; retries accept those exact
unit hashes, never arbitrary partial files. Checkpoints and maintenance receipts
are retained throughout.

Before **every** policy installation the checkpoint owner arms the intent with the exact staged
package hash and CIL checksum from the installed HLL compiler. Recovery can
therefore cover interruption before the native checksum receipt write: it must
match the same maintenance receipt, source digest, retained package hash,
recomputed CIL checksum and installed module checksum. A generic intent without
this proof, or any mismatch, fails closed before mutation. This covers C0 still
being recorded after C1 installation, and a fresh installation whose preliminary
receipt has no policy yet. Recovery can be retried after some unit/ownership
replacements have already completed or after the prior policy was restored.
Ordinary successful fresh installs/upgrades release their own maintenance receipt
after handlers as before; failure retains it. The legacy migration keeps its
explicit validation/release boundary. Check mode never checkpoints, arms,
installs, relabels, or changes service state.

Focused validation links the candidate against this controller's installed CIL
in an isolated temporary directory, queries the resulting binary policy and
removes the compiler files without loading it. The active module listing stays
unchanged and enforcement stays enabled. Filesystem/lock rollback tests exercise
restoration, changed ownership, symlinks, active acceptance and interrupted
recovery with synthetic systemd/policy commands. Role-entrypoint regressions
cover checkpoint ordering, retained maintenance, foreign policy rejection,
failed install, idempotency and check mode. These do not prove live systemd or
SELinux rollback. The candidate was subsequently installed through the real role and rolled back
after its startup failure. Named restart, actual process/key access, runner ID 1
online, managed maintenance release and the one Rocky case remain unverified.

The approved live attempt used payload digest
`09dc0755c8eb9c24da44fbd3f38e6801ca394e14e20ebf68e0d41aa4be6a2c32`.
Preflight confirmed enforcing mode, exact old unit bytes, the original failed
maintenance receipt, no jobs/runs, and effective permissions matching the retained
review. The isolated rebuild and staged package matched these fingerprints:

| Artifact | SHA256 |
| --- | --- |
| Policy source | `42f0db437a8829a074afc44c111d1e891b4b1fe0a33333b5d61307e3a25f3c2d` |
| Rendered file contexts | `7e119f82b30112589d3ec2007155d4b985f4df5f18236b2ad5b54a6cb0f14496` |
| Package | `289e14382d7c5630e8a005ab8b6a25ece3696e9e081e9e28e900e3459d839d11` |
| CIL / armed module checksum | `134e4327c90146c30acd552900e561941171b50a528d8f657c99082399c78475` |

The managed checkpoint saved **22,256** label records before installation. The
old failed receipt and checkpoint were archived privately before a guarded
maintenance handoff; the full native lifecycle then created its own checkpoint
and retained its own receipt. The controller-only Skynet deployment failed in
**126.54 seconds** (`ok=189 changed=14 failed=1`, with dispatcher failure
propagation). Agent startup hit this new enforcing AVC:

```text
avc: denied { mounton } comm="(sh-agent)"
path="/run/systemd/mount-rootfs/run/forgejo-runner-agent"
scontext=system_u:system_r:init_t:s0
tcontext=system_u:object_r:homelab_forgejo_agent_run_t:s0
tclass=dir permissive=0
```

Systemd exited with **226/NAMESPACE** while preparing the protected runtime mount,
before executing the agent. This demonstrates a missing namespace mount permission
in the candidate, not a successful agent-domain transition or key load. No policy
permission was added after failure. The narrowly indicated additional permission
is `init_t` `mounton` on only `homelab_forgejo_agent_run_t:dir`; it remains a
proposal requiring review, not an installed or automatically accepted correction.
Further runtime requirements remain unproven.

The failure handler stopped/disabled only the owned units and executed the
checksum/receipt-guarded rollback. A separate read-only audit verified exact old
unit bytes/UID/GID/mode/mtime, all **22,256** saved labels, the original native
ownership receipt and unchanged registration/credential/configuration hashes.
The custom module is absent; both services are inactive/disabled, SELinux is
Enforcing, and the failed migration's maintenance receipt remains held. No
acceptance job or disposable VM was created; runner ID 1 was not brought online.
No restart validation or fresh acceptance capacity check was attempted after
failure. No Proxmox grant, template, VM allocation or unrelated service was
changed by this attempt.

Private evidence is under
`~/.config/homelab/molecule-controller/selinux-approved-1794637570135986147/`
(`before.json`, `package-proof.json`, `checkpoint-verified.json`,
`guarded-handoff.json`, `failure-rollback.json`, `failure-audit.json`). The
original managed failure is retained at
`controller-service-deploy-1794637967358174134/run.log`. A concurrent staged
inspection observed the module after rollback removal; that incomplete inspection
is retained and is not presented as a successful active-module check. The retained
package and armed intent were independently matched to the preflight proof.

The approved `mounton` amendment adds only
`allow init_t homelab_forgejo_agent_run_t:dir mounton;` and its required dir-class
permission. Its active payload digest is
`3f0f3172c174668f47a1c0171b27b2c30b49bb1b20f13ca97609113220053bb4`:

| Artifact | SHA256 |
| --- | --- |
| Policy source | `4efa8f984ead4cd587d83d935eafb9b8123990bd65de9b25430d6ae20d1e85e5` |
| Rendered file contexts | `7e119f82b30112589d3ec2007155d4b985f4df5f18236b2ad5b54a6cb0f14496` |
| Package | `7b8bba9480172ba85b7ab80db5e394540fb833adedd7f4b410eaf3f7bc93b7c9` |
| Active priority-400 CIL checksum | `3b688a4234dd69d67e92b072b3339f1eeb60fc67158ea52a9db9155d1f1312c9` |

Fresh isolated linking confirmed the agent's credential restrictions, neverallow,
network and capability permissions unchanged. The first amended deployment
succeeded in 127.89 seconds, but a diagnostic used `runuser` without `/usr/sbin`
in its PATH and triggered the conservative rollback. That instrumentation error
was corrected to an absolute executable path. All evidence was retained; the
identical approved candidate was then deployed successfully in **122.74 seconds**
(`ok=193 changed=15 failed=0`). Both attempts had no new AVCs.

Actual processes were verified in `homelab_forgejo_agent_t` and `user_t`, with
exactly one dedicated node key loaded, private runtime/socket permissions,
unchanged credential hashes and zero effective Linux capabilities. The named
`systemctl restart forgejo-runner-agent.service forgejo-runner.service` replaced
both PIDs and passed the same checks with no new AVCs. Enforcing mode,
`ProtectSystem=strict`, `PrivateTmp`, `ProtectHome`, `NoNewPrivileges` and `0077`
umasks remained intact. No reboot was performed. Forgejo confirmed repository
runner **ID 1**, `repo_id=1`, `owner_id=0`, version `v13.2.0`, idle before and
after the restart. Forgejo reports selector `molecule-pve1-rocky`; its configured
`:host` executor suffix is separately verified in the private config, along
with capacity 1 and `insecure: false`. Maintenance was then released through the
original guarded module.

Fresh capacity checks found `local-zfs` **sparse=1**, a healthy shared `rpool`,
99,598,848,000 bytes available and 7,578,882,048 bytes free RAM. The conservative
82,411,089,920-byte requirement included the **10 + 16 GiB** selected Rocky pair,
the controller's 31,945,224,192 bytes of remaining unreserved logical space,
5 GiB staging, 15 GiB pool headroom and 1 GiB metadata allowance. The two storage
IDs share backing capacity and were not added together. Controller staging is
persistent XFS, with 30,106,439,680 bytes free. This was a fresh single-run budget,
not a guarantee against future unrelated thin-volume growth.

Exactly one manual workflow was dispatched:
[Forgejo run 1](https://forgejo.int.nosugarmaxtaste.com:8443/homelab-ci/homelab-ci/actions/runs/1),
`rocky_node_exporter` / `rocky102`, using trusted GitHub main
`06f3e27f78ea60defc60504221f22e1bea7ee519`. It failed after **389 seconds**
(workflow) / **385.073 seconds** (harness execution), before Molecule tests.
Infrastructure creation succeeded, but readiness waited 301 seconds because SSH
could not open the generated host-pin file. The pin equals the generated guest
public key and inventory selects its exact path; its label at failure was
`user_u:object_r:user_home_t:s0`, UID 993, mode `0600`. A temporary, auto-collected
probe reproduced this under `user_u:user_r:ssh_t:s0`, with strict checking still
on: `load_hostkeys: fopen .../known_hosts: Permission denied`. The installed
policy has no `open` allowance for that type and explicitly dontaudits it, so no
AVC was emitted. This is a controller trust-file labeling failure, not evidence
of a guest firewall defect. Guest-agent exec is disabled by the guest's existing
policy; no agent setting was changed and independent guest boot/key inspection
through that channel remains unavailable.

On 2026-11-15 the approved correction was validated without expanding the custom
policy. `vm.py` now creates/verifies only the current run's exact `known_hosts`
file and sets its existing SELinux context's type to `ssh_home_t` through the
open file descriptor. This uses existing `user_t` relabel permission. Each new
run gets the same labeling step; it does not depend on a file-context mapping or
an operator running `restorecon`. Symlinks, extra hard links, foreign ownership,
incorrect modes and changed pins are rejected. Contents, owner, group, mode
`0600` and the context's user/role/range are preserved. Unexpected label errors
remain fatal; filesystems without SELinux labels continue to work. No generic
SSH access to `user_home_t`, tree relabel, credential-type or policy change was
introduced. The earlier uninstalled filename-transition proposal is superseded.

A fresh managed maintenance receipt and ownership-guarded, label-only rollback
checkpoint were prepared; the old installation receipt was never forced. An
isolated copy of the candidate helper, outside the retained trusted checkout,
validated both the failed run's pin and a newly created representative run pin
under `user_u:user_r:user_t:s0` with the existing service hardening. Both became
`user_u:object_r:ssh_home_t:s0`, UID/GID 993, mode `0600`. Each supported a bounded
SSH connection to the already-owned guest, with `StrictHostKeyChecking=yes`,
only its exact pin file, the dedicated guest key and no agent. SSH ran in
`ssh_t`; both connections returned zero. The combined check took **0.502 seconds**,
with no relevant new AVCs. Credential contents/metadata/labels, the custom
policy checksum and the failed result were unchanged. The representative file
and directory were then verified and removed individually.

After guarded maintenance release, the installed `homelab-molecule retire
88ce902dca0e47f8ac191805f7673ee7` entry point used the original clean checkout
`06f3e27f` and its normal identity, state and file-byte guards. Retirement took
**4.91 seconds** (**5.053 seconds** including service launch). Independent node
queries confirmed VM980000/980001 and all their artifacts absent from `local`
and `local-zfs`; the provider state has no resources. Cached images, protected
controller9300 and source template9004 were preserved. The failed workflow/job
result, logs, manifest, plan, source checkout and state backup remain retained;
`retired.json` records cleanup, not a passing acceptance result.

Initial diagnostic invocations stopped on a context string's trailing NUL,
before labeling, and verified rollback retained maintenance. Two retirement
launches never started: forwarding a private `var_t` output file descriptor to
systemd caused an `init_t` file-write denial. Capturing output through pipes and
then saving it privately resolved that diagnostic issue without changing labels,
policy or hardening. No provider retirement operation was repeated.

At that checkpoint maintenance was held pending the trusted-source update:
GitHub main `334bcd52fc4dbecbc8b32c4edff8169307abb0c6` lacked the fix. The next
attempt required the merged correction, verification of its exact SHA, managed
release of the matching receipt, and fresh capacity/storage checks. No second
workflow had yet been dispatched; production-role acceptance and the new disk
sizes remained uncertified. Clean-checkout and commit guards were
preserved. The focused `test_molecule_vm.py -m 'not integration'` selection passed
**21 cases** in **0.13 seconds**; the exact-main/recovery regression passed
**1 case** in **0.12 seconds**. Ruff and whitespace checks passed. No full Python
suite, live matrix or dependency installation was performed for this correction.

On 2026-11-15, trusted GitHub main was verified at merged PR #744 commit
`e0e2c1c536b28ac18421cb6ef1a2252ad45b38d7`, including the reviewed recovery,
nonblocking pin-open and fixture corrections. The current maintenance receipt
matched its retained proof, both services retained their contexts/hardening,
and runner ID 1 was authenticated and idle. Fresh checks found an ONLINE shared
pool with **99,567,251,456 bytes** available against the conservative
**82,370,469,888-byte** budget, **9,036,247,040 bytes** free node RAM and
**30,050,349,056 bytes** available on controller XFS. Both reserved VMIDs were
absent. Only the matching receipt was released through the managed module.

Exactly one retry was dispatched: [Forgejo run 2](https://forgejo.int.nosugarmaxtaste.com:8443/homelab-ci/homelab-ci/actions/runs/2),
`rocky_node_exporter` / `rocky102`, with the exact GitHub SHA above. It failed
after **5 seconds** (workflow), **2.247 seconds** (harness), creating the stopped
template: the Proxmox create API returned HTTP 403. No VM was created and
Molecule/production-role execution never started. At that failure the acceptance token had
**no effective privileges** on `/vms/980000` or `/vms/980001`; the three declared
VMID ACLs were absent (`MoleculeVM` on both paths and `MoleculeClone` on 980000).
The earlier retirement's API log shows VM deletion with `purge=1`. Inspection of
the installed `/usr/share/perl5/PVE/API2/Qemu.pm` also confirms that VM deletion
calls `PVE::AccessControl::remove_vm_access($vmid)` independently of the purge
option. Disabling purge alone cannot preserve these grants. The existing managed
permission entry point must reconcile the exact declared VMID ACLs before an
allocation is reused; the missing ACLs were not checked before this dispatch.
No grants were changed and no further case was triggered.

Failed run `b448fd8b0f6b42aa9d1a714730712e43` uploaded only its owned bootstrap
snippet. The installed `homelab-molecule retire` entry point used its original
clean `e0e2c1c5` checkout, verified state/file identity, and retired it in
**2.29 seconds** (**2.458 seconds** including service launch). Independent node
queries confirmed both VMIDs and all run-owned artifacts absent from `local`
and `local-zfs`; provider state is empty. Failed result, logs, plan, state backup
and source checkout remain retained. Controller9300, template9004, cached
images, credentials, registration and policy were preserved. SELinux remains
enforcing, runner ID 1 was idle, and fresh managed maintenance was held pending
the permission lifecycle correction. **The platform was not yet accepted at that
checkpoint.** No full matrix or Python suite was repeated.
Run 2 evidence is beneath
`~/.config/homelab/molecule-controller/rocky-retry-1794691919240098107/`;
controller job evidence is `jobs/c3d4922fcbac4583b9a6297757db5154/`, and the
retained run is `runs/b448fd8b0f6b42aa9d1a714730712e43/`. The controller-side
maintenance proof is `retry-b448fd8b-maintenance.json` beneath the existing
`/var/cache/forgejo-runner/hostpins/34344a3fc71047f1aa344e43c855745e/` boundary.

The next approved operation reconciled only the canonical Molecule declarations
through `opentofu_molecule_permissions`. Check mode reported `changed=0`; apply
reported one changed task restoring the three missing ACLs; the unchanged rerun
reported `changed=0` in **13.95 seconds**. Full comparisons preserved all prior
roles/ACLs, token metadata and private credential hashes. Effective acceptance
privileges matched `MoleculeVM` on 980000/980001 plus `VM.Clone` on 980000;
the acceptance token still received HTTP 403 for VM104. Both tokens retain
`privsep=1`. The transient controller-bootstrap API token has expired: its API
access returns HTTP 401, while the operator's permission calculation confirms
no VM104 rights. It was neither renewed nor replaced; the acceptance token is
unexpired and does not use that bootstrap credential.

Fresh maintenance ownership and capacity checks preceded exactly one further
dispatch: [Forgejo run 3](https://forgejo.int.nosugarmaxtaste.com:8443/homelab-ci/homelab-ci/actions/runs/3),
`rocky_node_exporter` / `rocky102`, again fetching trusted GitHub main
`e0e2c1c536b28ac18421cb6ef1a2252ad45b38d7`. Provisioning and strict SSH readiness
passed in **108.08 seconds**. The first production-role deployment completed
(`subject: ok=66 changed=12 failed=0`), but the scenario failed while retaining
`evidence/node-exporter-invocation` on the controller. Ansible attempted to change
the file's SELinux user from `user_u` to `system_u` with type `user_home_t`;
the confined process received `Permission denied`. Delegated diagnostic copies
hit the same failure. This is not a passing acceptance result: Molecule exited
**2** after **64.4 seconds**, the harness exited **1** after **177.387 seconds**,
and the workflow failed after **180 seconds**. Source hashes before/after match
and the retained checkout remains clean. No policy expansion, context bypass,
hardening relaxation or second retry was performed.

Owned run `1fbd62071d9d4b5ca9f06231f1164831` was explicitly retired through its
original trusted checkout in **4.75 seconds** (**4.933 seconds** with service
launch). Independent checks confirmed VM980000/980001 and all run-owned artifacts
absent, empty provider state, and preserved controller9300, template9004 and image
cache. Failed results, logs, plan, state backup and private evidence files remain.
The invocation and diagnostic contents were written before the label failure;
their files remain UID 993, mode `0600`, labeled `user_u:object_r:user_home_t:s0`.
Their presence does not change the recorded diagnostic failure into success.

Readiness was measured **before** repair: both VMID permission sets were empty
again after deletion. The same authorised managed reconciliation restored only
the same three ACLs (check `changed=0`, apply one changed task, unchanged rerun
`changed=0` in **14.41 seconds**). Final effective-permission checks passed and
VM104 remained HTTP 403. Thus the allocation is free and permission-ready after
operator repair, but is **not automatically reusable** after retirement. Fresh
maintenance was held for the separate evidence-copy defect. At that checkpoint
the platform remained unaccepted pending the reviewed correction and a separately
authorised passing case; no full matrix was run.

Run 3 evidence is under
`~/.config/homelab/molecule-controller/rocky-retry-1794693454313950888/`, including
`readiness-before-reconcile.json`, `readiness-after-reconcile.json`, diagnosis,
retirement and final-controller proofs. Managed permission evidence is under
`managed-reconcile-1794692969367099495/` and
`managed-reconcile-1794724804117849311/` beneath that private controller directory.
Controller job evidence is `jobs/2712f5d10a7b4915951ae8ac0dbebb15/`; the retained
run is `runs/1fbd62071d9d4b5ca9f06231f1164831/`. That operation's ownership proof was
`retry-1fbd6207-maintenance.json` beneath the existing root-owned hostpin recovery
boundary. The earlier allocation-reuse regression passed **1 case**, **31.66 seconds**,
with synthetic credentials/HTTPS and the real managed role; Ruff check/format
and whitespace checks passed. No full Python suite was repeated.

The controller evidence correction was prepared for review and subsequently
merged in PR #745; run 6 below exercised it through the real harness. Inspection of
VM9300's pinned Ansible **2.22.0** confirmed that `atomic_move()` chooses the
policy-default SELinux context for a new destination, requesting `system_u`
instead of retaining the confined writer's valid `user_u` identity. The six
delegated evidence writes in the former `rocky_node_exporter/verify.yml`
(now `node_exporter/verify.yml`),
`shared/diagnostics.tasks.yml` and `shared/diagnostics.yml` now use the narrow
`molecule_evidence` action through the existing controller action-plugin path.
It stages complete content as an owned mode-`0600` file inside the owned
mode-`0700` evidence directory, then publishes atomically. Replacement preserves
the existing valid SELinux context; new files inherit the writer's context.
`force: false` uses atomic no-clobber publication and never precreates an empty
destination. Existing first observations, content formatting, diagnostic
redaction and unprivileged localhost delegation are preserved. Unsafe paths or
label errors fail visibly. Controllers without SELinux need no label handling.

A bounded synthetic check executed those six **real task bodies** twice on
VM9300, covering new files, retained first observations and actual updates of
existing destinations. It passed in **0.844 seconds** under
`user_u:user_r:user_t:s0`, `NoNewPrivileges`, zero effective capabilities and the
existing systemd hardening. All files remained UID/GID 993, mode `0600`, context
`user_u:object_r:user_home_t:s0`; the directory stayed `0700`. Enforcement,
policy checksum, Ansible implementation, maintenance receipt and failed-run
evidence hashes were unchanged; no relevant new AVC appeared. The initial
synthetic unit stopped before executing tasks because systemd could not directly
execute the venv's home-labeled Python path. The completed check used the already
supported system-Python entry into `user_t`, then the pinned Ansible CLI; no
policy adjustment was made. Isolated synthetic logs are retained under
`.ansible/evidence-writer-c07f64cfff764ea9bdb388820f8dd50e/` and
`/var/lib/forgejo-runner/tmp/evidence-writer-c07f64cfff764ea9bdb388820f8dd50e/`.
Focused repository checks passed: **23** fast fixture/publication tests, **4**
real local evidence/Quadlet and bounded FIFO cases, **4** owned-cleanup cases, Ruff,
YAML/Ansible lint and localhost-only syntax. Existing long-line/inventory warnings
remain. No credentials, guest VMs, Proxmox operations, policy installation or
maintenance release were involved. Publish the reviewed correction on a GitHub
branch and use the exact candidate selection below for a separately approved
Forgejo attempt; a main merge is not a prerequisite. The failed run records and
current protection remain intact.

Earlier live evidence is beneath
`~/.config/homelab/molecule-controller/selinux-approved-1794645608659470587/`;
capacity is in `acceptance-capacity-1794646871938875471.json`, retained VM
identities in `acceptance-retained-audit-*.json`. Current pin validation, scoped
rollback, retirement and independent absence evidence is in
`~/.config/homelab/molecule-controller/hostpin-operation-1794683676492936205/`.
Its controller-side counterpart is
`/var/cache/forgejo-runner/hostpins/34344a3fc71047f1aa344e43c855745e/`, including
the historical `waiting-for-main-final.json` ownership proof. Run 3's receipt was
recorded by `retry-1fbd6207-maintenance.json` in that same directory. On-controller
job/source evidence is `jobs/6a3078f4eb89449a8f82907af90214a8/` and all failed
provisioning/readiness/state evidence remains in `runs/88ce902dca0e47f8ac191805f7673ee7/`.

Recorded installed versions: Rocky **10.2**, system Python **3.12.15**, tooling
Python **3.14.8** / Ansible Core **2.22.0**, OpenTofu **1.11.14**, Runner **13.2.0**;
`selinux-policy-targeted-42.1.18-4.el10` and OpenSSH clients
`9.9p1-23.el10_2.rocky.0.1`. The controller's staging directory is on persistent
**XFS**, with approximately **28.09 GiB** free after installation. This is a
checkpoint, not measured peak usage for the unrun suite. Normal HTTPS health
(`/api/healthz`, status `pass`) and login return HTTP 200 from the controller;
unauthenticated `/api/v1/version` returns the existing sign-in guard's HTTP 403.
Private checkpoint records are `controller-final-audit-*.json`,
`controller-security-audit-*.json`, `controller-platform-record-*.json` and
`controller-containment-*/` beneath the deployment directory. The temporary
operator bootstrap agent was stopped; recovery credentials, images and evidence
were preserved. No unrelated service or host was restarted.

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
Final Actions-enablement evidence is
`.ansible/forgejo-controller-prep/live/outcome.json`; controller rollout is
tracked separately below.

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
needed for that decision. The originally approved first case was
`rocky_node_exporter` / `rocky102`, validating the candidate 16 GiB disk.
Current source uses selector `node_exporter` for that same focused case.


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

### Rollout scope and commands (approved limits)

The controller, private repository and registration already exist. Infrastructure
creation commands below record the initial rollout; do not recreate those
resources during the current blocked follow-up.

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
| Each token, `/nodes/pve1` | Node audit |
| Acceptance token only, `/nodes/pve1` | `Sys.AccessNetwork` for uncached image downloads; permits node-side URL access, including internal endpoints |
| Each token, `/storage/local-zfs` and `/storage/local` | Datastore audit, space allocation and template/file allocation |
| Each token, `/sdn/zones/localnetwork/vmbr1` | Bridge audit/use required by the pinned provider |

### Reproducible dedicated Proxmox permissions

`ansible/host_vars/pve1.yml` declares the dedicated Molecule roles and token ACLs.
The existing `opentofu` role reconciles them through
`tasks/sub_tasks/pve_user.yml`; private preparation scripts create credentials,
not permission roles or grants. The five preparation-created roles and thirteen
ACLs are retained by these declarations. The additional `MoleculeLocalConfig`
role contains only `Datastore.Allocate`, assigned to the two Molecule tokens on
`/storage/local` only, with propagation enabled like the existing assignments.
No additional configuration-management grant is made on `/storage/local-zfs`.
The existing `MoleculeBridge` role contains only `SDN.Use`. Its additional
`/sdn/zones/localnetwork/vmbr0` ACL is exclusively for
`root@pam!molecule-controller-bootstrap`: Proxmox checks template 9004's source
bridge during clone, before the provider configures the new controller on
`vmbr1`. The acceptance token has no `vmbr0` grant. Preflight rejects an expanded
bridge role or a `vmbr0` ACL for another token or role. Template 9004 is unchanged.

`MoleculeImageDownload` contains only `Sys.AccessNetwork`, assigned exclusively
to `root@pam!molecule-vm-acceptance` on `/nodes/pve1`. PVE's `download-url` API
requires this node permission in addition to `Datastore.AllocateTemplate` on
the destination storage. It allows node-side fetching of arbitrary URLs,
including internal endpoints; it is not restricted to the manifest's URLs by
Proxmox ACLs. The harness still pins image URLs/checksums and validates ownership.
Do not substitute `Sys.Modify` or a root-path grant, or add this privilege to the
bootstrap token or the shared audit-only `MoleculeNode` role. The managed role
rejects expanded download-role privileges, another token or another node path.
An existing checksum-verified `allocation.image_file_ids` entry avoids this API.

The first renamed `node_exporter` / `ubuntu2604` provisioning attempt against
GitHub `80182a24f5dab53a3e7d421ae7e3b0aaa465b63f` reached this previously unexercised
download path and received HTTP 403. Run `6deadea1887541baa3a42e7ae02ddf96`
created only two cloud-init snippets; no VM or Molecule execution occurred.
Its private logs, plan and state must remain available after guarded retirement.
This failure does not establish Ubuntu Node Exporter acceptance.

The download grant was explicitly approved and applied through the managed role
on 2026-11-16: only the new role and its one ACL were added. Check mode left live
permissions unchanged; application changed two tasks, and the unchanged rerun
reported `changed=0` in 15.46 seconds. Existing roles/ACLs, token metadata,
privilege separation and private credential hashes were preserved; acceptance
still received HTTP 403 for VM104. The expired bootstrap token was unchanged.
Guarded retirement through the original clean checkout took 2.852 seconds.
Independent node queries confirmed both reserved VMIDs and the run's artifacts
absent, with failed evidence retained and allocation permissions still ready
without another repair. Fresh pool/RAM/controller-space/address checks passed;
only the matching maintenance receipt was released. No case was retried.
Private operator proofs are under
`~/.config/homelab/molecule-controller/approved-image-download-1794759495962967616/`.
Focused synthetic-HTTPS permission regressions: 21 passed in 96.54 seconds;
Ruff, YAML lint, affected Ansible lint, localhost syntax and whitespace passed.

The source-bridge grant was explicitly approved and applied on 2026-11-14 through
the same managed entry point. Check mode changed nothing; application changed
only one ACL, and the repeat reported `changed=0` in **5.58 seconds**. Effective
`vmbr0` permissions are exactly `SDN.Use` for bootstrap and empty for acceptance.
Both tokens still receive HTTP 403 for VM104. Complete before/after comparisons
preserved all roles, prior ACLs, token metadata and private credential hashes.
Evidence is under
`~/.config/homelab/molecule-controller/managed-bridge-permissions-1794585273334213921/`.

Before retrying, the installed PVE **9.2.21** clone/configuration/resize checks,
source-template configuration and pinned provider **0.120.0** path were reviewed
against the declared privileges. VM configuration, cloud-init, disk growth,
node/storage reads and power operations use the existing scoped grants. No pool
assignment, migration, custom CPU/device mapping, hook script or startup-order
configuration is requested. No other predictable missing Proxmox grant was identified;
an unexpected denial must still stop execution rather than broaden access.

The pinned provider reads the `/storage/local` configuration to locate its
snippet directory. Proxmox requires `Datastore.Allocate` for that read, even
though it also permits storage-configuration changes. Audit, space and template
privileges are insufficient. This coarse permission requires explicit approval;
never substitute the general OpenTofu role, Administrator or a root-path grant.

The optional path is disabled by default. After creating the two dedicated,
privilege-separated tokens through the approved credential procedure, inspect
the plan using the normal bootstrap API authentication and inventory:

```text
skynet limit pve1 raw --tags opentofu_molecule_permissions \
  -e '{"opentofu_pve_molecule_permissions_enabled": true}' --check --diff
```

Only after approval, repeat without `--check --diff` to reconcile the declared
permissions. This tag reaches only the dedicated permission tasks; it does not
run the general OpenTofu user/token lifecycle. Ordinary `opentofu_pve_user` runs
retain their existing behavior and do not require Molecule identities. The API
delegate must trust the Proxmox certificate chain: the new path verifies TLS.
Both tokens must already exist with privilege separation enabled. No token is
created, replaced or modified, and unrelated roles/ACLs are retained.

### Persistent acceptance pool and allocation reuse

VM deletion removes VM-specific ACLs on the installed Proxmox version. The
approved correction uses persistent pool `molecule-acceptance`, managed through
`pve_user.yml` and the existing `opentofu_molecule_permissions` entry point.
**Repository preparation is complete; live migration and two consecutive UI
runs remain pending a published reviewed candidate.** Do not treat the recovery
below as proof that permission repair between jobs has been eliminated.

The three propagated pool ACLs belong only to
`root@pam!molecule-vm-acceptance` on `/pool/molecule-acceptance`:

- `MoleculeVM`: `VM.Allocate`, `VM.Audit`, `VM.Config.CDROM`, `VM.Config.CPU`,
  `VM.Config.Cloudinit`, `VM.Config.Disk`, `VM.Config.HWType`, `VM.Config.Memory`,
  `VM.Config.Network`, `VM.Config.Options`, `VM.PowerMgmt`, `VM.GuestAgent.Audit`.
- `MoleculeClone`: `VM.Audit`, `VM.Clone`.
- `MoleculePoolAudit`: `Pool.Audit`, needed for provider membership reads.

The role validates these exact privileges and reads existing VM/clone/audit
roles before mutation; differing live roles are rejected rather than silently
adopted. Preflight discovers roles through `/access/roles` and reads details
only for listed roles; missing-role detail requests return HTTP 500, which is
not accepted as absence by preflight. Both consumers require
`GET /pools?poolid=molecule-acceptance` to return a list containing exactly one
object with that `poolid`. Empty, duplicate, malformed, mismatched and bare-object
responses fail before ownership/membership checks or mutation.
The role checks an existing pool's ownership comment and rejects storage,
controller9300, production or other non-disposable members. Standard pinned
`community.proxmox.proxmox_pool` creates an empty pool; Ansible never adds VMs
or shared storage. Credential-bearing API session/results are private and
cleared in `always`, including on failure. Check mode performs no role, ACL,
pool or token mutations. Ordinary OpenTofu setup remains unchanged and the
Molecule permission path remains explicitly opt-in.

Pool ACLs replace only the three superseded acceptance-token VMID ACLs after
the pool grants exist. Removing those direct grants makes an initial create or
clone without `pool=molecule-acceptance` fail at the API. All existing node,
storage and bridge restrictions and both tokens' privilege separation remain.
The runner gets no `Pool.Allocate`, `Permissions.Modify`, root-path or bootstrap
administrator grant. The bootstrap token has no pool access.

Both initial create and clone requests must include `pool_id`. The disposable
root supplies it to the template and existing cloudinit-vm module; the shared
module's new optional input defaults to null for all unchanged callers.
`allocation.pool_id` is carried into each new manifest, with matching plan/state
and live membership checks before provisioning, power operations and retirement.
Only the current run's reserved VM980000/980001 may be members; foreign names,
VMIDs, nodes, storage members and reserved VMs outside the pool stop execution.
Retained legacy runs keep their original no-pool retirement contract and source.
The persistent pool is outside disposable OpenTofu state and is never retired
with its guests. Scenarios stay in Git when their disposable VMs are retired.

[Proxmox pool permissions](https://github.com/proxmox/pve-docs/blob/master/pveum.adoc#pools)
are inherited by members. This is API access to **any VMID created in that
pool**, plus clone access to every member, rather than an API limit to the two
reserved VMIDs. Harness IDs/budgets/identity checks still enforce the allocation.
An administrator adding an unrelated VM would expose it to the token;
membership guards reject that condition but do not undo the inherited grant.
The installed create/clone checks and pinned
[provider 0.120.0](https://github.com/bpg/terraform-provider-proxmox/blob/v0.120.0/proxmoxtf/resource/vm/vm.go)
were reviewed: both requests accept the destination pool immediately. Moving
an existing VM between pools is not requested or permitted to the runner.

Rollout and acceptance:

1. Publish a reviewed GitHub candidate branch/commit containing this correction.
   Main `80182a24f5dab53a3e7d421ae7e3b0aaa465b63f` lacks pool support. Use the
   existing exact-SHA candidate selector; do not edit a fetched checkout or merge
   solely to unlock testing. No launcher or private workflow code update is needed.
2. With all old owned runs retired and VMIDs/artifacts independently absent,
   take fresh managed maintenance and checkpoint the current ACLs, tokens,
   private allocation, ownership, labels and evidence. Preserve runner ID 1,
   registration, keys, policy, service hardening and previous failed receipts.
3. From the operator environment, run the existing permission entry with
   `--check --diff`, apply only the approved pool/ACL migration, then require
   an unchanged rerun. Verify exact effective pool privileges, no direct VMID
   grants, no pool/ACL administration, unchanged node/storage/network grants,
   and HTTP403 for protected VM104, controller9300 and template9004.
4. Update only `pool_id` in the private allocation through the existing managed
   native-service path, preserving private permissions/context and other values.
   Verify trusted candidate identity and fresh capacity/address checks, then
   release only the matching managed maintenance receipt. Keep administrator
   authentication on the external operator path.
5. Manually run `node_exporter` / `fedora44`, then `node_exporter` / `rocky102`,
   using the same reviewed branch/full SHA and explicit candidate approval.
   For **each** job, verify real provisioning/Molecule success, source SHA,
   diagnostics and retirement. Independently confirm VMIDs and owned artifacts
   absent and the persistent pool empty with unchanged ACLs. Do not reconcile
   permissions between the jobs. Verify production access remains denied and
   permission readiness persists after the second retirement.

On failure retain exact evidence/resources and use the original checkout for
scoped retirement. For rollback, hold owned maintenance, require the owned pool
empty and all disposable resources absent, and restore the checkpointed
allocation and exactly the prior three VMID ACLs before removing only this
pool's three acceptance-token ACLs and the owned empty pool. Leave shared
roles, credentials and historical evidence intact. Legacy operator-side VMID
reconciliation remains covered by
`test_allocation_reuse_restores_deleted_vm_acls_without_changing_the_permission_boundary`;
it is a recovery option, not the intended normal pooled workflow.

Repository validation covered 106 distinct affected cases across focused runs,
including check mode, exact ACL migration/idempotency, legacy recovery, actual
role expansion, foreign pool members, and pool plan/state/manifest guards.
Six new subprocess-fixture cases initially hit the unit-process boundary;
their integration classification was corrected and all six passed. Ruff,
YAML/Ansible lint, localhost syntax, OpenTofu formatting, and initialized
controller-root/shared-module validation passed using existing pinned tools.
Checkov 3.4.3 scanned tracked public source with pending edits: 512 passed,
zero failed, 25 skipped, zero parsing errors. The one new read-only preflight
block finding was reproduced without its scoped exception; fatal propagation
and `always` credential cleanup were preserved. Normal GitHub CI and the two
live pooled workflow runs remain unverified until candidate publication.

The PR #748 follow-up corrects the synthetic API's former object-shaped pool
response and missing-role HTTP404 model. The earlier 106-case record predates
that correction and did not establish compatibility with those real API
responses. Current regressions exercise list-shaped pool responses, HTTP500
missing roles, initial migration, existing owned members/idempotency, fatal
API failures with credential cleanup, and malformed/foreign pool rejection.
The corrected candidate still requires normal publication and two consecutive
Forgejo workflow runs before claiming live pooled allocation reuse.
The two affected pytest families passed **122 cases in 186.42 seconds**; the
refined case-sensitive role-discovery failure case passed again in 3.88 seconds.
Ruff check/format, YAML/Ansible lint, localhost syntax and whitespace checks
passed. Checkov 3.4.3 on tracked public source reported **513 passed, zero
failed, 25 skipped and zero parsing errors**. These are local synthetic/static
results, not live workflow acceptance or GitHub CI results for a published fix.

The next Fedora attempt (`d422b833c5334682a8dea63678f63098`, source
`80182a24f5dab53a3e7d421ae7e3b0aaa465b63f`) confirmed this reuse defect: VM
creation received HTTP 403 after Ubuntu run `68d3c7d5c58e474b9237cb53eeaf8bbf`
passed Molecule and retired. Both VMID permission sets were empty; node, storage
and bridge grants were intact. The managed operator path restored only the
three declared VMID ACLs; its unchanged rerun reported `changed=0` in 15.05 s.
Fedora's one owned snippet was retired in 2.486 s, with failed evidence unchanged.
Independent cleanup, effective permissions, capacity and address checks passed;
only the matching maintenance receipt was released. No retry was dispatched.

After PR #748 merged, Fedora run `3e8cbd21217a43aa86ed1e18b054d9af`
tested source `bc2f90d1c15bd46a7e9828ddea298fe37d34a816` with Forgejo workflow
`b32d42672ac37310e7b10613b7db1990fa4902e7`. Its retained provisioning log
reported VM-create HTTP403 before Molecule started: the live pool migration
had not been applied and the private allocation still lacked `pool_id`.
On 16 November 2026, the original checkout retired its one owned bootstrap
snippet in 2.420 s; independent checks confirmed both VMIDs and owned artifacts
absent, with failed evidence retained. The managed OpenTofu permission entry
then created the approved pool, `MoleculePoolAudit` role and three pool ACLs.
Check mode preserved live state (14.91 s); apply completed in 19.87 s and an
unchanged rerun reported `changed=0` in 20.67 s. Other roles, ACLs and token
metadata remained unchanged. The existing native-services atomic-copy task,
scoped to `allocation.json`, added only `pool_id: molecule-acceptance`; its
rerun reported `changed=0` in 3.68 s. Private permissions/labels, registration,
credentials, units and enforcing policy were preserved without service restarts.
Both tokens' effective VM104 permissions remained empty; the acceptance token
also received HTTP403 for VM104, VM9300 and template9004. Fresh shared-ZFS,
RAM, persistent-controller-space and guest-address checks passed, the pool was
empty with its grants intact, and only the owned maintenance receipt was
released. No workflow was dispatched. Next, manually run `node_exporter` /
`fedora44`, then `node_exporter` / `rocky102` without intervening permission
repair. At that stage, two consecutive successful pooled runs and
post-retirement permission readiness remained unverified; the deployment alone
did not certify Fedora acceptance.

Forgejo run [14](https://forgejo.int.nosugarmaxtaste.com:8443/homelab-ci/homelab-ci/actions/runs/14)
then used the same GitHub/launcher commits and the configured pool, but failed
while creating the template: `VM.Config.Options` was checked on `/vms/980000`.
Installed `qemu-server 9.2.11` validates creation-time tags **before** adding
the VM to its requested pool. The initial pool allocation check passed; the
later tag check could not yet inherit the existing pool role. The failed
run `4049af0c61204114ad29b961f18b804b` was retired through its original checkout;
its private evidence was retained and managed maintenance held pending candidate
delivery. No additional permissions were granted.

New pooled manifests explicitly defer only the stopped template's tags until
after creation. The controller requires the exact saved template resource,
approved pool membership, run-specific name/description, allocated disks and
stopped template state before its synchronous
`PUT /nodes/{node}/qemu/{vmid}/config` tag update, with the observed configuration
digest to reject concurrent changes. The official
[qemu-server 9.2.11 implementation](https://github.com/proxmox/qemu-server/blob/c5399752ae859ac55148d8568e25c86e68c431ca/src/PVE/API2/Qemu.pm#L2454-L2625)
completes PUT under the configuration lock; POST starts a worker and can return
its task ID before tags are committed. Immediate strict ownership verification
therefore follows PUT. Only this initialization step accepts empty template
tags; foreign nonempty tags are always rejected.
Ordinary ownership/power/removal checks still require both identity tags.
The template resource ignores subsequent tag drift in OpenTofu because the
controller owns and strictly checks those tags. Interrupted initialization
is retryable during provisioning or scoped retirement, including a connection
loss after the update committed. Legacy manifests retain their original path.
No installed launcher/private workflow update is needed: publish the reviewed
candidate, then select its branch, exact SHA and candidate approval for two
consecutive targeted `node_exporter` runs (`fedora44`, then `rocky102`). Verify
each result and retirement independently, with persistent grants intact and
no ACL repair between runs, before claiming pooled workflow reuse. Do not
alter a retained checkout or merge solely to test this correction.
The initial candidate's controller/launcher/scenario regressions passed 140
cases in 30.36 s before the fixture modeled asynchronous POST. With the PUT
correction, controller/launcher regressions passed 113 cases in 3.14 s,
including the corrected race/retry and retirement checks. These local
synthetic results preceded the live acceptance below.

On 16 November 2026, two consecutive manual Forgejo dispatches passed against
merged GitHub main `c2f11e74f454d181b57f5cb428ce3ed7a3b66a49`. The private
Forgejo workflow remained `b32d42672ac37310e7b10613b7db1990fa4902e7`; neither
it nor the installed launcher needed an update. Both runs used `node_exporter`,
executed the production native-service deployment, passed idempotence and
functional metrics/service checks, and collected private diagnostics.
Recovery runs 21/22 below subsequently passed the same checks against that same
GitHub source and Forgejo workflow, without ACL reconciliation.

| Forgejo run | Guest | Provision (s) | Molecule (s) | Retirement (s) | Workflow elapsed (s) |
| --- | --- | ---: | ---: | ---: | ---: |
| [15](https://forgejo.int.nosugarmaxtaste.com:8443/homelab-ci/homelab-ci/actions/runs/15) | Fedora 44 | 111.66 | 99.12 | 4.78 | 224 |
| [16](https://forgejo.int.nosugarmaxtaste.com:8443/homelab-ci/homelab-ci/actions/runs/16) | Rocky 10.2 | 113.90 | 95.56 | 4.91 | 223 |
| [21](https://forgejo.int.nosugarmaxtaste.com:8443/homelab-ci/homelab-ci/actions/runs/21) | Debian 13.7 | 161.13 | 83.25 | 6.70 | 259 |
| [22](https://forgejo.int.nosugarmaxtaste.com:8443/homelab-ci/homelab-ci/actions/runs/22) | Ubuntu 26.04 | 217.10 | 85.90 | 7.56 | 320 |

The workflow column is Forgejo's elapsed time; stage durations were recorded
separately. All four guests ran Node Exporter 1.10.1, built with Go 1.25.3, on
x86_64. Fedora/Rocky guest SELinux was enforcing; Debian/Ubuntu reported their
normal disabled SELinux state. No security-mode changes were made. Observed kernels were Fedora
`6.19.10-300.fc44.x86_64` and Rocky `6.12.0-211.16.1.el10_2.0.1.x86_64`.
Debian reported `6.12.115+deb13.1-amd64`; Ubuntu reported `7.0.0-38-generic`.
The retained controller run directories are
`/var/lib/forgejo-runner/runs/4497d222698243eebec55acca6ecab05` (Fedora) and
`/var/lib/forgejo-runner/runs/c632fda45a9d4a0daf7cc11f408f84b4` (Rocky),
`/var/lib/forgejo-runner/runs/f121e71669124e399df00d1badd21ca0` (Debian) and
`/var/lib/forgejo-runner/runs/49de6d94ddc34e0285e841014eda2576` (Ubuntu).

After each run, independent Proxmox checks confirmed VM980000/VM980001 and
their owned artifacts absent, empty disposable OpenTofu state and an empty
owned pool. Persistent pool grants, all other ACLs/roles and token metadata
matched the saved managed snapshot; **no ACL reconciliation occurred between
runs**. The acceptance token still received HTTP403 for VM104, VM9300 and
template9004, and both tokens' calculated VM104 permissions remained empty.
Runner ID 1, registration, credentials, service units/hardening, policy and
prior failed evidence were unchanged. Controller SELinux remained enforcing,
with no relevant new controller AVCs. Evidence files retained their
private ownership, mode 0600 and valid SELinux labels; all four tested checkouts
were clean and source fingerprints unchanged.

Fresh capacity and guest-address checks passed after each successful retirement.
Only the matching managed maintenance receipts were released. The allocation
was confirmed clear after run 22 without permission repair. These passes cover
Node Exporter on the four existing OS selections, not other scenario families.
Schedules and the controlled GitHub live workflow remain disabled. Private
operator verification evidence is retained under
`~/.config/homelab/molecule-controller/pr749-two-run-1794806560515774110/` and
`~/.config/homelab/molecule-controller/run17-validation-1794816115451813622/`.

Between the two successful pairs, run 17 failed before Molecule while fetching
the uncached Debian image: Proxmox could not resolve `cloud.debian.org`.
Tailscale DNS recorded repeated forwarded SERVFAIL responses in that window;
its observed system upstream was `192.168.80.53`. Runs 18–20 stopped at the
retained-allocation guard and did not execute new guest tests. Run 17's exact
owned bootstrap snippet was retired through its original checkout in 2.539 s,
with failed evidence unchanged. Fresh DNS/HTTPS, capacity and identity checks
preceded recovery run 21, which genuinely downloaded and checksum-verified the
uncached Debian image; run 22 then verified Ubuntu using its existing cache.
Runs 15/16 had used cached images and did not exercise this download path.
No production DNS, firewall or permission changes were made. The underlying
cause of the upstream SERVFAILs remains unestablished; a permanent DNS repair
is not claimed. Successful cases retire automatically; a failed case retains
its allocation until inspected and explicitly retired through the printed
`homelab-molecule retire <run-id>` recovery command and original checkout.

Keep bootstrap administrator/Vault authentication on the operator control path.
Never copy it into the runner or use the acceptance token, its workflow, or the
node SSH credential to grant its own ACLs. No root-path grant,
`Permissions.Modify`, general OpenTofu role or Administrator assignment is
proposed for the acceptance token. The existing node SSH identity remains
root-equivalent; pool API restrictions do not turn that approved SSH channel
into a restricted account. No additional pool/ACL administration capability is
added through it. Normal pooled jobs must consume persistent ACLs without
operator reconciliation between cases.

Repository validation for these changes used the existing environment; no local
tooling was installed or upgraded:

| Check | Result | Elapsed |
| --- | --- | --- |
| `pytest tests/unit/test_opentofu_molecule_permissions.py` | 16 passed | 52.44 s |
| Focused controller/recorded native-runner checks | 17 passed | 95.33 s |
| Real repository preparation, first install and update | 1 passed | 30.06 s |
| `pytest tests/unit/test_workstation_venv.py tests/unit/test_workstation_tooling.py` | 34 passed | 40.50 s |
| `pytest tests/unit -m 'not integration'` | 2230 passed | 50.23 s |
| Ruff check/format, YAML lint, full offline Ansible lint, localhost syntax, whitespace | passed; existing YAML long-line warnings | recorded in private logs |
| Checkov 3.4.3, repository configuration, public source snapshot | 508 passed, 0 failed, 25 skipped, 0 parsing errors | 15.81 s |
| Gitleaks 8.24.3, changed source with repository configuration | 0 findings | 0.52 s |

Elapsed values are command wall time, not summed test durations. Native lifecycle
safety fixtures record host mutations; their passing results do not certify the
blocked live runner. Repository preparation and virtualenv command checks execute
the real Git/filesystem/interpreter paths against temporary inputs. New subprocess
regressions use the existing `integration` selection. An initial validation run
was blocked by the sandbox's local RPC restriction; the same workstation
selection passed outside that restriction. An initial full-tree Gitleaks
*directory* scan reported five matches in unchanged public-key/reference/template
files; historical commit-fingerprint exclusions do not match directory-scan
fingerprints. No exclusions or scanner policy were changed. Changed-source
scanning is clean; this is not a new historical-range scan or a claim about CI.
Operator/other integration groups and the live matrix were not repeated for this
focused correction. Generated READMEs and controlled GitHub CI remain unchanged.

Collection `community.proxmox` 2.1.0 supports role check mode but not ACL check
mode. The entry point therefore reports the declared ACL targets in check mode
and skips the ACL mutation module. An unchanged normal rerun is idempotent.

On 2026-11-14, the explicitly approved correction was applied through this
entry point, limiting its declarations to `MoleculeLocalConfig` and the two
`/storage/local` ACLs. The existing vaulted bootstrap authentication was used
on the operator's localhost delegate with the trusted Proxmox CA; the general
OpenTofu token lacks `Permissions.Modify` and was not broadened. Check mode
made no live changes; application reported two changed tasks, and the unchanged
rerun reported `changed=0` (7.14 seconds). Complete before/after comparisons
confirmed all existing roles, ACLs, token metadata and saved credential files
were preserved. Both tokens can now read the local datastore configuration;
neither has `Datastore.Allocate` on `/storage/local-zfs`, and both receive HTTP
403 reading protected VM104's configuration. Both retain `privsep=1`.
Private evidence is under
`~/.config/homelab/molecule-controller/managed-permissions-1794584138728375641/`.

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
   Reconcile permissions through the repository-managed entry point above after
   its exact grants are approved. The private preparation helper does not create
   roles or assign ACLs. Confirm all existing grants match before provider use.
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
   without printing values. Under the current approval, perform a named restart
   of only the owned runner/agent units and verify dedicated-key reload without
   an interactive workstation agent. Do not reboot the controller or hosts;
   actual reboot persistence remains unverified. For current source, dispatch
   `node_exporter` / `rocky102` on private CI `main`; record the fetched GitHub SHA, real role result,
   durations and confirmed VM/file retirement. Leave schedules disabled. Revoke
   only the transient bootstrap credentials after scoped recovery is no longer
   needed. Do not declare the new 16 GiB configurations fully certified.

### Scenario rename and coordinated delivery

The `node_exporter` rename is prepared for repository review only. The last
verified deployed launcher default and private Forgejo workflow used
`rocky_node_exporter`. Both need a coordinated update: root-owned
`/usr/local/bin/homelab-molecule` from `scripts/testing/forgejo.py`, and only
`.forgejo/workflows/molecule.yml` in private `homelab-ci/homelab-ci`. The GitHub
syntax loop/controlled workflow selectors are updated in source too; controlled
live CI remains disabled pending its separately approved execution.

Pause manual dispatches, verify current ownership/idle state, checkpoint the
owned launcher/workflow, and hold fresh managed maintenance while applying the
paired files from the same approved revision through the existing managed path.
No unit, policy, credential, registration or permission-boundary change is needed.
This document does not authorise that live update. Before a GitHub main merge,
use the published reviewed branch and exact SHA with the new workflow; keep
normal main dispatch paused until main contains the rename. Old source expects
the old selector, and new source rejects it before provisioning. There is no
compatibility alias. Recover retained historical runs only with their original
clean checkout; never rewrite manifests or ownership markers to adopt them.

After that separately approved update, existing external ACL reconciliation,
fresh capacity checks and matched maintenance release, the next targeted command
in the controller's normal confined job environment is:

```bash
homelab-molecule run --suite node_exporter --os rocky102 \
  --source-branch "$REVIEWED_BRANCH" --source-sha "$REVIEWED_SHA" \
  --candidate-approved true
```

`REVIEWED_BRANCH` and `REVIEWED_SHA` must identify the explicitly approved,
published rename candidate in `Lebowski89/homelab`. The equivalent Forgejo manual
inputs are suite `node_exporter`, OS `rocky102` and those exact source inputs.
Changing only `--os` selects the other three existing guest configurations; it
does not establish live acceptance. Direct Molecule calls must also receive the
selected platform's generated `guest-vars.json` via `HOMELAB_MOLECULE_VARS`;
the guest guard no longer defaults a missing OS to Rocky.

The historical run 6 below passed **`rocky_node_exporter` on Rocky 10.2**, before
this rename. No live run has exercised the renamed scenario, and no additional
OS acceptance is claimed. Scenarios stay in Git when their disposable VMs retire.

Repository-only refactor validation passed **140 distinct focused cases** across
the controller, VM selection/configuration, scenario guards/ownership, evidence
writer and existing Molecule CLI/syntax tests. Offline suite selection resolved
all four OS pins to `node_exporter`; the former selector was rejected. Ruff,
formatting, YAML lint, offline Ansible lint with CI's configured plugin paths,
`molecule syntax -s node_exporter` and whitespace checks passed. Focused Checkov
3.4.3 scanning of the public scenario/affected GitHub workflows reported 121 passed,
0 failed, 2 scoped skips and 0 parsing errors. The sandbox's Ansible RPC
restriction required the affected synthetic tests to run outside it.
No dependency changes, live access, dispatch or full matrix were involved.

### Operator use and scoped recovery

Rollout status (2026-11-15): controller VM9300, its owned snippet/state, dedicated
credentials, private CI repository and repository-scoped runner ID 1 exist.
The approved mount amendment is installed at priority 400. Services are active,
enabled and confined; the named restart and dedicated key reload passed.
The first Rocky workflow failed before production-role tests because its public
host-pin file could not be opened in `ssh_t`. The exact-file `ssh_home_t` fix
passed retained/new-file and strict-SSH validation without a policy expansion.
Run 88ce902dca0e47f8ac191805f7673ee7 was retired through the original guarded
entry point; both VMIDs and owned artifacts are independently confirmed absent.
Its failed result and evidence remain. Forgejo run 2 fetched the merged fix from
GitHub main `e0e2c1c5`, but VM creation failed because prior deletion removed
the reserved-VM ACLs; that partial run was retired. The approved managed repair
restored those exact grants, and run 3 provisioned successfully and completed
its first production-role deployment. It then failed on controller evidence
copies attempting a forbidden SELinux user change. That run was also retired,
and independent absence checks passed. Deletion removed the ACLs again; an
authorised operator reconciliation restored them and verified VM104 denial.
The evidence correction and paired launcher/workflow update subsequently passed
run 6 below. The manual Rocky acceptance path is operational; allocation reuse
still requires the external managed permission step described above. This is not
fully automated, and controller reboot persistence remains unverified.

Open the private Forgejo repository's **Actions → Live VM acceptance → Run
workflow**, using CI branch `main`. After the coordinated update below, defaults
select suite `node_exporter` and OS `rocky102`.
Other choices are the four existing suites and four existing OS pins, or `all`;
use the broad choice only after its capacity and server timeout are verified.
There is one runner slot and one controller lock; requests never cancel active
work. The GitHub controlled live workflow remains disabled.

The installed manual candidate path keeps `source_branch: main`, empty `source_sha` and
`candidate_approved: false` as the normal defaults. To test a reviewed candidate,
select its branch **in `Lebowski89/homelab`**, supply its full lowercase
40-character commit SHA, and explicitly approve executing that exact source with
the live acceptance credentials. Only trusted private-repository operators may
make this manual dispatch. The approval is an operator assertion after review;
Git ancestry alone does not prove GitHub review or passing PR checks.
The launcher fetches that fixed repository's explicit `refs/heads/<branch>` and
verifies the requested commit is reachable from the fetched tip. It executes the
requested SHA even if the branch advances; a force-push excluding it is rejected.
No fork, URL, PR-ref or branch-only candidate selection is accepted. Recovery
continues to use the original retained checkout and its clean-tree/SHA guards.

Run 4's saved step log (`actions_log/homelab-ci/homelab-ci/04/4.log.zst`)
was inspected on 2026-11-15. Its exact failure was `Controller is draining for
maintenance; retry after the operator completes it`, then exit 1, **before any
GitHub fetch or VM preparation**. Its Forgejo workflow SHA was
`ae137edab31abbfd51ea6515de8b7b15e0edf755`; it tested no GitHub source SHA.
At that snapshot, read-only checks confirmed receipt hash
`c8c6c681de485e7d5607511e03a99692b6b1f3e64c7cf925c54802dc3c84c10d`,
SELinux enforcing, all three earlier manifests retired, and both disposable
VMIDs/disks absent. These checks are state evidence, not fresh capacity approval.

Scoped launcher/workflow rollout procedure (completed for run 6):

1. Review/publish the candidate on GitHub, record its branch/full SHA and required
   PR-check results. This correction was prepared from main
   `e0e2c1c536b28ac18421cb6ef1a2252ad45b38d7`; use the published candidate
   commit SHA for acceptance, without merging it first.
2. After scoped approval, verify the existing ownership record and maintenance
   receipt on VM9300; checkpoint the installed launcher's exact bytes, metadata,
   xattrs/label and hash, and the private workflow's bytes/blob SHA. Install only
   the reviewed `scripts/testing/forgejo.py` as root-owned mode `0755`
   `/usr/local/bin/homelab-molecule`, using the existing native-services launcher
   copy task under those guards. This file has no restart notification; neither
   unit nor the policy/registration/credential files need replacement.
3. Publish only the reviewed `.forgejo/workflows/molecule.yml` to private
   `homelab-ci/homelab-ci` main, using its recorded blob SHA as a concurrency
   guard. This is a separately authorised **private workflow commit**, not a
   GitHub-main merge. Verify the remote bytes and new Forgejo workflow SHA.
4. Use the external operator's managed `opentofu_molecule_permissions` path to
   reconcile only existing grants; verify effective allocation permissions,
   privilege separation, VM104 denial and an unchanged rerun. Bootstrap
   administrator authentication stays off the runner. Verify absence, fresh
   storage/RAM/address preflights and current maintenance ownership, then release
   only that owner through `forgejo_runner_maintenance`.
5. For current source, manually dispatch **one** `node_exporter` / `rocky102` with the approved
   branch/SHA. Equivalent launcher arguments are `homelab-molecule run --suite
   node_exporter --os rocky102 --source-branch <reviewed-branch>
   --source-sha <exact-sha> --candidate-approved true`. The private workflow passes
   these as quoted arguments. Verify provisioning, real role execution, evidence,
   result and retirement, then independently verify owned VM/file absence and
   post-retirement allocation permissions. Stop and retain evidence on failure;
   use only the original checkout's printed retirement command for scoped recovery.
6. If launcher/workflow installation fails, retain maintenance; restore only the
   verified checkpointed launcher and workflow with ownership/hash/blob guards.
   Do not remove registration, credentials, failed evidence or state. Do not
   trigger a second case automatically. VM deletion still removes VMID ACLs on
   this Proxmox version; readiness requires the documented external reconciliation
   unless a separately approved durable boundary is implemented.

Local candidate-path validation: **23 tests passed** in 0.62 seconds (0.85 seconds
command elapsed), using `python3 .ansible/pr736/run.py candidate-source-reviewed
tests/unit/test_forgejo_controller.py`. This includes real temporary Git branch
fetch/ancestry/detached-checkout execution, retained recovery guards, terminal
source/setup failures and literal workflow argument handling. Ruff check/format,
YAML lint, offline Ansible lint and localhost-only syntax checks passed; existing
long-line/missing-guest-group warnings remain. Checkov 3.4.3's focused file scan
reported 1 passed, 0 failed, 1 scoped skip, 0 parsing errors **for its recognised
Ansible input**; it did not recognise this Forgejo workflow as a GitHub Actions
report. Workflow restrictions were exercised by the focused tests. Gitleaks
8.24.3 found zero findings in the changed-code snapshot; this was not a historical
commit-range scan. Reused the unchanged evidence writer's completed 31 focused
checks and bounded confined-controller check above. No full suite/matrix or
GitHub PR CI was run during that local preparation. Subsequently, PR #745
[CI run 43711602425](https://github.com/Lebowski89/homelab/actions/runs/43711602425)
passed quality, all four pytest groups and the final lint gate; Secret Scan and
the Checkov workflow also completed successfully. That workflow status alone
is not a claim that every scanner finding or review thread is resolved.

On 2026-11-15, the approved continuation installed the merged launcher's exact
bytes on VM9300 using the unchanged native-services launcher copy task with
ownership/drain guards and a complete rollback checkpoint. Check/apply passed;
the unchanged rerun reported `changed=0`. Only that launcher file changed. Both
units kept their existing PIDs, contexts and hardening; policy, registration,
private credential hashes and prior failed evidence remained unchanged. The
private workflow was then updated with its owned blob guard to commit
`03f98ed0c4ebf6605efbb7ba8f08e679860cc7e5`. Runner ID 1 was reused, without a
new registration. Normal verified HTTPS and repository scope checks passed.
Run 5's actual saved step log, like run 4's, reports the maintenance guard before
any source fetch; neither run tested a GitHub commit.

Exactly one new case was dispatched:
[Forgejo run 6](https://forgejo.int.nosugarmaxtaste.com:8443/homelab-ci/homelab-ci/actions/runs/6),
the former `rocky_node_exporter` scenario / `rocky102`, **passed**. Its explicitly
requested and resolved GitHub source was `6604888ca91a23f48441f276f444d15a5db2df69` (merged PR #745),
distinct from the Forgejo workflow commit above. The detached checkout stayed
clean and executable-input fingerprints matched before/after testing. This was
an exact-SHA run after merge; it does not establish a live pre-merge branch run.
The same branch/ancestry selector is covered by the focused temporary-Git tests.

| Actual run 6 phase | Elapsed/result |
| --- | --- |
| Provisioning and strictly verified guest SSH | 110.84 s |
| Molecule scenario | 96.97 s, exit 0; diagnostics collected |
| Owned VM/artifact retirement | 4.82 s; provider state empty |
| Complete launcher / Forgejo job | 220.755 s / 221 s |

The real catalogue/role paths passed check mode, fresh-host validation,
installation, loopback metrics, zero-change idempotence with the same service
invocation, and ownership-gated removal retaining the binary/collector data.
Guest evidence records Rocky 10.2, kernel
`6.12.0-211.16.1.el10_2.0.1.x86_64`, Node Exporter 1.10.1 and enforcing SELinux.
All five controller evidence files are UID/GID 993, mode `0600`, context
`user_u:object_r:user_home_t:s0`; first-observation retention and later writes
completed without a policy expansion or relevant new AVC. No full matrix,
controller reboot or repeated full Python suite was performed.

Independent Proxmox queries confirmed VM980000/980001 and all run-owned artifacts
absent from `local` and `local-zfs`; controller9300, template9004 and the image
cache were preserved. **Before repair**, both allocation permission sets were
empty after retirement. The external managed role restored only the three
already-declared VMID ACLs (check `changed=0`, apply one changed task, unchanged
rerun `changed=0` in 14.41 s). Full role/ACL/token comparisons preserved unrelated
permissions, token secrets and privilege separation; acceptance VM104 access
remained HTTP 403. The expired bootstrap token was not renewed or replaced.
Post-repair independent permissions, resource absence and fresh shared-pool/RAM/
controller capacity passed, and only the matching post-run maintenance owner was
released through the managed module. The allocation is currently ready for
another authorised run, **after external operator reconciliation**.

The manual Forgejo Rocky acceptance path is operational; it is not fully
automated. Repeat the external readiness/reconciliation sequence before reuse
and after retirement. Schedules and automatic triggers remain disabled.
Controller reboot persistence, the other OS/suite combinations and protected
rootless Podman callers are not certified by this single case.

Run 6 controller evidence remains in
`/var/lib/forgejo-runner/runs/07772ccd2bfd496e9f490873257285b2/` and
`jobs/0eb4c7495aba47a6bd25899c004e4d48/`, including the original clean checkout
mapping and retired provider state/backup. Operator proofs, before/after
permission readiness, exact workflow/source records and scoped launcher rollback
are retained under
`~/.config/homelab/molecule-controller/rocky-retry-1794745597307097646/`.
The controller's launcher checkpoint is
`/var/cache/forgejo-runner/launcher/rocky-retry-1794745597307097646/`.
The permission-reuse regression was rerun with synthetic HTTPS and the real
managed role: **1 passed, 16 deselected**, 31.42 s (31.62 s command elapsed).
The initial sandbox invocation could not bind localhost; the unchanged command
passed outside that restriction. Ruff check/format and whitespace checks passed.

Job logs distinguish the Forgejo workflow commit from the requested/resolved
GitHub source SHA and private evidence location. On the controller,
`/var/lib/forgejo-runner/jobs/<job-id>/request.json` records the requested source
and workflow SHA before fetching; `source.json` preserves the resolved source,
branch tip and checkout. `result.json` records the terminal launcher outcome
(including fetch/setup failures) and total elapsed time, separate from the
harness's case duration;
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
