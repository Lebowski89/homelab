# Native services in the catalogue

`native_services` manages Alloy, Node Exporter, Keepalived and Technitium through
`ansible/group_vars/all/services/`. It retains explicit installation procedures
in `tasks/alloy.yml`, `tasks/node_exporter.yml`, `tasks/keepalived.yml` and
`tasks/technitium.yml`, with application-specific defaults, handlers and templates.
`tasks/main.yml` owns validation and lifecycle dispatch; it does not install all
four applications. Infisical remains Podman bootstrap/recovery orchestration;
PostgreSQL and the other native roles are unchanged.

## Declarations and selection

| Application | Canonical declaration | Native selector / Skynet name | Default inventory group |
| --- | --- | --- | --- |
| Alloy | `alloy.yml`, target `native` | `alloy_native` / `alloy-native` | `tags_podman` |
| Node Exporter | `node_exporter.yml` | `node_exporter` / `node-exporter` | `tags_node_exporter` |
| Keepalived | `keepalived.yml` | `keepalived` | `tags_keepalived` |
| Technitium | `technitium.yml`, target `native` | `technitium_native` / `technitium-native` | `tags_technitium_native` |

Alloy and Technitium keep their existing Docker/Podman targets in the same
application definition. Use their explicit native selectors to select only the
host installation; a bare application name selects its matching catalogue targets.
The old standalone playbook includes are removed, so there is one execution path.
Existing underscore tags and `deploy`, `install`, `run` and check-mode commands
remain deliberate aliases. No old role-directory shims are needed.

A native declaration uses `runtime: native`, `native.application`, typed
`native.config`, `native.update_policy`, and exactly one placement field:
`deploy.hosts` accepts an inventory hostname, group, or list of both. The shared
catalogue resolver expands groups and deduplicates in first-seen order, independently
of the command limit.
Selected hosts must belong to the existing `tags_skynet` play scope; each
materializes its own configuration. `skynet limit <pattern>` restricts that host
set without silently accepting hosts outside that play scope. Configured
`enabled` state is independent of placement: selecting an enabled native service
with a missing/empty group or an empty host list fails with the service identity
and inventory selection. Unselected optional native groups need not exist;
explicitly disabled services retain the normal disabled-selection behavior.
Explicitly unknown hosts fail validation. Native-only selections do not need an application
controller, Infisical or a container runtime. NetBox still owns host identity,
addresses, group membership and Keepalived per-host VRRP priorities.

Crossing from a container base to a native target inherits selection tags,
enabled state, description and operational requirements, but discards container
images, commands, ports, environment, credentials, storage and placement. Explicit
container fields on a native declaration are errors. For native-to-native target
merges, individual `native.config` settings replace base values, including whole
lists/maps and empty values. Container target merge behavior is unchanged.

Operator defaults live in the service declarations. Existing machine-specific
`alloy_native_*`, `node_exporter_*`, `keepalived_*` and `technitium_native_*`
variables remain supported in `host_vars` and extra vars. Ansible resolves those
variables using its usual precedence; each defined value then overrides its
corresponding catalogue setting **before** templating defaults. False, empty and
numeric values are retained without truthy fallback or string conversion, and
invalid values fail validation. Role defaults alias the selected normalized
application configuration; Alloy's RPM repository settings are role-local
installation inputs. Unselected service inputs are not required. Node Exporter's
release URLs, archive paths and checksum URL derive from its selected version and
architecture unless explicitly overridden. Prometheus reads the canonical
Keepalived VIP declarations, retaining its existing explicit instances override.

## Lifecycle

Use `skynet <action> alloy-native`, `node-exporter`, `keepalived` or
`technitium-native`. `skynet run <name> <action>` reaches the same path.

| Action | Native behavior |
| --- | --- |
| `deploy` | Ensure declared installation/configuration and enable/start the service. |
| `update` | Reconcile configuration and apply the declared update policy only to this application. |
| `recreate` | Enable/restart the selected installed service; no reinstall or data deletion. Keepalived peer/VRRP validation and Technitium readiness checks still run. |
| `check` | Check-mode deploy with diff. Download/extraction, installer execution, restarts and listener/DNS verification have explicit limitations; it is not a runtime health check. |
| `remove` | Stop/disable the selected installed unit, retire recorded configuration and restore owned resolver integration. Retain persistent data and installation artifacts. |

Alloy and Keepalived default to `update_policy: present`. `latest` is an explicit
opt-in: Alloy updates only its declared package list; Keepalived updates only
`keepalived`, not `dnsutils` or other packages. Node Exporter uses `pinned`:
change `version`/`arch` (or its existing download overrides) to update it.
Technitium uses `present`: the existing installer marker prevents unattended
upgrades. Updating the installer download does not upgrade an existing server.
Native `bootstrap` and image `drift` operations are unsupported. Broad/mixed
container operations select only their supported Docker/Podman entries before
materialization, so optional native groups/defaults are not required. A selector
that explicitly requests a native-only name/tag still fails clearly, including
when combined with container selectors. Application/category selectors shared
with container targets (for example `alloy` or `monitoring`) retain their container
action semantics.

Installation ordering remains application-specific: Alloy uses its package-created
account and available journal reader groups; Node Exporter verifies its archive
and installs the declared binary/collectors; Keepalived validates inventory peers
and VRRP priorities before mutation; Technitium downloads its installer before
changing the resolver, flushes resolver handlers before installation, and checks
DNS/listeners afterwards. Notifications are flushed before the next native entry
can replace their configuration context.

## Removal ownership and recovery

A private `/var/lib/native_services/<application>.json` record identifies the
catalogue owner, unit and exact managed configuration files. Deploy/update records
resolver recovery state before installation and claims each managed file only
after its successful copy/template task. A failed package/download operation
cannot claim an unrelated pre-existing file; partially adopted files remain
removable. Competing identities or changed unit names fail before mutation;
remove the previous declaration before moving ownership. Managed file paths
cannot be directories. Removal never recursively removes application directories.

Owned configuration is Alloy's config file, Node Exporter's custom systemd unit,
Keepalived's config and DNS-check script, or Technitium's resolved drop-in.
Technitium also records the original `/etc/resolv.conf` symlink or regular file
before first managing it. Removal verifies that the resolver is still role-owned
(or already restored), removes the drop-in, restores the original link/content
and restarts resolved. A missing resolver path during an interrupted restore
can be retried from the retained record; there is no existing file/link to
replace in that case. A conflicting existing resolver change fails before
stopping DNS; the recovery record is retained. Check mode reports the plan without restoring
or restarting the resolver.

An installation from before this catalogue phase has no ownership record.
Removal can stop/disable its explicitly selected service, but leaves unclaimed
files/resolver state intact. Deploy once to adopt configuration before removing
it. On an already-native Technitium host, its original pre-native resolver state
cannot be reconstructed: deployment records the current link as its starting
state, and removal preserves that link while retiring the managed drop-in.

Packages, package sources/signing keys, downloaded installers/archives, binaries,
accounts and Alloy journal group memberships are intentionally retained: they may
pre-exist or be shared. `/etc/dns`, `/opt/technitium`, Alloy data and Node Exporter
textfile data are retained. No uninstall or purge action is implied.

## Protection and platform limits

These native services have no existing catalogue endpoint ACL declarations;
this phase preserves DNS, monitoring and VRRP reachability. Native dispatch reuses
common requirement validation and firewall classification without invoking
container preparation. Container protection plans exclude native identities.

**Protected native endpoints/callers are blocked before mutation.** The current
firewall lifecycle verifies Docker/Podman container identities/publications; it
cannot verify a native host listener and its exclusive caller identity. Native
`ports`, non-empty ACL/ownership-transition requirements and native references in
protected provider caller lists therefore fail clearly. Do not substitute a
container identity, silently skip a protection requirement, or mark a host listener
protected without a verified host-listener/identity adapter. Such an adapter is
required before adding protected native declarations; no firewall entries are
created or retired for these currently unprotected native services.

Native Alloy retains its Debian-family APT installation and adds conventional
Fedora 43–45 and Rocky 9/10 using DNF4/DNF5. It requires systemd, Linux AMD64/ARM64
and a supported package manager; Atomic/OSTree hosts and other RPM derivatives
are rejected before installation ownership or package changes. The Linux and
architecture requirements follow [Grafana's supported platforms](https://grafana.com/docs/alloy/latest/set-up/supported-platforms/).
Keepalived and Technitium retain their existing Debian-family APT procedures and
also support conventional Fedora 43–45 and Rocky using DNF4/DNF5, as detailed
below. Node Exporter retains its Linux archive installation without a new OS
gate. Firewall and container application migrations remain separate work.

Alloy uses [Grafana's stable repositories](https://grafana.com/docs/alloy/latest/set-up/install/linux/).
APT repository/keyring settings and existing overrides are retained. RPM hosts
verify package and repository metadata signatures using Grafana's published
signing-key fingerprint. Host variables `alloy_native_rpm_baseurl`,
`alloy_native_rpm_key_url` and `alloy_native_rpm_key_fingerprint` support an
explicit HTTPS mirror; `alloy_native_repo_filename` and `alloy_native_packages`
apply to both package managers. No OS-specific fields are added to the service
declaration. The package-created account, available journal-reader groups,
configuration permissions, Loki destination, privacy filters and removal
ownership are unchanged. SELinux and firewall policy are not modified.

Alloy check mode reports repository/package work without downloading keys,
refreshing metadata or installing packages. It inspects existing accounts;
configuration planning is deferred if the package account is absent. Service
starts and restarts are deferred. Package installation remains `present` except
for an explicit `update` with `native.update_policy: latest`; it never requests a
host-wide upgrade. The existing APT repository format is retained.

For example, after reviewing the plan and authorizing a live run:

```bash
skynet limit rocky check alloy-native
skynet limit rocky run alloy-native
```

RPM package transactions, journal access under enforcing SELinux, service
startup and successful delivery to Loki still require isolated live validation.
Check mode does not establish those capabilities.

## Native DNS on Fedora and Rocky

Both DNS applications require Linux, systemd and a matching package manager;
Atomic/OSTree systems and other RPM derivatives are rejected before ownership or
installation changes. Existing Debian-family installation behavior is retained;
this does not establish support for every derivative or old release.

Keepalived uses distribution `keepalived` and `bind-utils` packages on Fedora
43–45 and Rocky 9/10. Availability is documented by the
[Fedora package catalog](https://packages.fedoraproject.org/pkgs/keepalived/keepalived/)
and [Rocky AppStream](https://dl.rockylinux.org/pub/rocky/10/AppStream/x86_64/os/Packages/k/).
The existing peer addresses, priorities, interface override, VIPs and root-run DNS
check remain unchanged. Templates use the paths' default SELinux labels; the
role does not opt scripts into `keepalived_unconfined_script_t`, enable
`keepalived_connect_any`, install custom allow rules or disable enforcement.
Custom script paths require appropriate operator-managed execute/search policy.
The candidate configuration is checked by Keepalived before replacement.
`update_policy: latest` updates only Keepalived, only during `update`.

Native Technitium's RPM path targets the current .NET 10 portable application on
AMD64/ARM64: Fedora 43–45, Rocky 9.7+ and Rocky 10.1+. Distribution
`aspnetcore-runtime-10.0` supplies the runtime and its dependencies; `bind-utils`
supplies the DNS probe. See [Fedora runtime packages](https://packages.fedoraproject.org/pkgs/dotnet10.0/aspnetcore-runtime-10.0/)
and the Rocky [9.7](https://download.rockylinux.org/vault/rocky/9.7/AppStream/x86_64/os/Packages/a/)
and [10.1](https://download.rockylinux.org/vault/rocky/10.1/AppStream/x86_64/os/Packages/a/)
package catalogs for the release floor. No Microsoft/EPEL/testing repository is
enabled to satisfy an older release.

The RPM path downloads the upstream portable archive and manages a systemd unit
following [Technitium's service definition](https://github.com/TechnitiumSoftware/DnsServer/blob/master/DnsServerApp/systemd.service).
It runs as `dns-server`, with root-owned program files, private writable config/log
directories and only `CAP_NET_BIND_SERVICE`. It retains system crypto policy and
does not provide a new dedicated SELinux domain for Technitium. Existing data is
not recursively chowned or relabeled. A prior installation with incompatible
ownership needs explicit storage maintenance.

The existing application marker prevents archive download/extraction on subsequent
deploy/update runs. `present` never upgrades the application or requests a
host-wide package upgrade. RPM-only host overrides `technitium_native_archive_url`
and optional `technitium_native_archive_checksum` support an HTTPS mirror and a
reviewed `sha256:<digest>` pin. The upstream default URL is mutable and has no
role-default checksum; supply a reviewed pin for reproducible fresh installs.
The existing service-name, config-directory, marker and readiness-port overrides
are retained. Readiness ports do not rewrite an existing Technitium configuration.
Installer-script URL/path overrides remain specific to the Debian procedure.

The RPM path deliberately avoids the upstream installer, which currently stops
resolved, rewrites NetworkManager configuration and replaces resolv.conf. It
leaves NetworkManager DNS and an absent/inactive resolved service untouched. When
`disable_resolved_stub: true` and resolved is running, it validates resolved's
output, records recovery state and manages the existing scoped drop-in/link.
`false` opts out entirely; the operator must arrange a free DNS listener port.
Removal restores only recorded resolver integration and retires the adopted RPM
unit, retaining the runtime, account, program files and application data.
The existing Debian installer procedure and its upstream side effects are
unchanged by this RPM implementation.

Check mode reports package/application work and explicitly defers installer,
archive, runtime and service checks. RPM Technitium does not require a pre-existing
service account or application binary in check mode. It never starts/stops DNS,
changes resolver state or contacts upstream downloads in that mode.

No firewalld rules are added. Before live rollout, arrange approved DNS access and
peer-scoped IP protocol 112 (VRRP), then verify the check script under enforcing
SELinux and failover between actual peers. Starting Keepalived alone does not
prove firewall reachability or safe VIP ownership. Use the existing selectors:

```bash
skynet limit <dns-host> check keepalived
skynet limit <dns-host> run keepalived
skynet limit <dns-host> check technitium-native
skynet limit <dns-host> run technitium-native
```

These commands require matching NetBox native placement/tags; do not select the
bare Technitium application to test only its native target. This phase changes no
placement, VIP, service definition or firewall policy. Package installation,
SELinux access, DNS recovery/readiness and VRRP failover require isolated live
validation before moving existing DNS services.

Offline tests verify selection, target isolation, host overrides, rendered
configuration and lifecycle ordering with remote operations replaced by recorders.
They cannot prove package/installer idempotence, DNS recovery, listener readiness,
VRRP failover or systemd behavior on real hosts. Review a check-mode plan and use
an explicitly authorized disposable host before production rollout.

Fedora 44 AMD64 has passed live installation and zero-change repeat runs for
Alloy, Node Exporter, Technitium and Keepalived under enforcing SELinux. Tests
used a local discard-only log receiver, isolated DNS listeners and a dummy-link
VIP; the real Keepalived health script succeeded. A single VM does not establish
peer failover, production listener reachability or application migration readiness.
All four services recovered after reboot, and their removal paths passed;
Technitium restored its recorded resolver integration while retaining DNS data.
