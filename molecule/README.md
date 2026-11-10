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
The default budget is one running guest, two vCPUs, 2 GiB RAM and a 32 GiB guest
disk plus a stopped image template. Failed retained runs still consume the pool.

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
32 GiB disk. A different layout fails before growth; no formatting is permitted.

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
314 and 64 checks. All 41 reported unit-suite failures reproduced on base
`e49f085db0d1b1113d936cf926836f700aa81dac` under equivalent execution conditions;
the complete unit suite remains unresolved. Controlled CI was not enabled or
executed, and actionlint was unavailable.

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
