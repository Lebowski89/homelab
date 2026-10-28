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
`deploy.group` names an inventory group; `deploy.host` names one host or a list.
Selected hosts must belong to the existing `tags_skynet` play scope; each
materializes its own configuration. `skynet limit <pattern>` restricts that host
set without silently accepting hosts outside that play scope. Empty groups disable their entries; explicitly unknown
hosts fail validation. Native-only selections do not need an application
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
invalid values fail validation. Role defaults only alias the selected normalized
configuration. Unselected service inputs are not required. Node Exporter's
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
Native `bootstrap` and image `drift` operations are unsupported and fail clearly.

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
and restarts resolved. A conflicting resolver change fails before stopping DNS;
the recovery record is retained. Check mode reports the plan without restoring
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

Alloy, Keepalived and Technitium retain Debian-family systemd gates. Node Exporter
retains its Linux archive installation without a new OS gate. Rocky/Fedora
support remains deferred: package/repository, account, resolver and systemd
behavior need platform-specific implementation and runtime validation. Alloy's
remaining deprecated `apt_repository` use is separate migration work.

Offline tests verify selection, target isolation, host overrides, rendered
configuration and lifecycle ordering with remote operations replaced by recorders.
They cannot prove package/installer idempotence, DNS recovery, listener readiness,
VRRP failover or systemd behavior on real hosts. Review a check-mode plan and use
an explicitly authorized disposable host before production rollout.
