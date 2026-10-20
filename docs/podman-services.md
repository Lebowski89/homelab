# Podman services

Use the
[service-definition option reference](../ansible/group_vars/all/services/README.md)
for canonical fields, defaults, and compatibility. This document focuses on
Podman adapter behavior and operational limits.

The shared service catalogue in `ansible/group_vars/all/services/*.yml` is runtime-aware. Every base service must explicitly declare `runtime: docker` or `runtime: podman`; a missing or unsupported runtime fails catalog validation. Targets inherit the validated base runtime and may explicitly override it with another supported runtime. Podman entries are selected by the same `skynet install|update|check|recreate|remove|drift <service>` interface and dispatched to `podman_services`.

## Operating selectors and recovery

Use an exact service/target for routine changes. `haproxy` and `alloy` select
both worker and mgt targets; `mgt-haproxy` / `mgt-collector` and
`haproxy-workers` / `alloy-workers` select one side. Keep worker placement
exclusions. Authelia's base selector includes its cache; inspect effective target
selection before changing a member. Bootstrap NetBox/Infisical recovery remains
independent through `ansible/bootstrap.yml` and explicit private Vault inputs.

The existing wrapper supports scoped check/drift/install/update/recreate actions.
Raw calls require Ansible arguments, for example
`skynet raw --tags update,mgt-haproxy -e @/secure/accepted-inputs.yml`, using the
operator's actual private file. ACL/data requirements remain strict regardless
of selectors; installing rules is not acceptance and ownership readiness uses
the actual service name. Preserve the current installed firewall union and
unrelated caller bindings.

Future migrations start in [migrator/](../migrator/README.md), with the
[ownership procedure](../migrator/guides/ownership.md), private paired backups,
proved numeric mappings and one reviewed cutover/rollback plan. Completed
migration handoffs and per-run acceptance records belong outside the repository
under `/opt/ansible/migration/`. Do not replay them as current operating commands.
Restoring an old baseline needs a new scoped decision and stopped replacement
writers because it removes post-backup changes. Keep rollback material until an
explicit retention decision.

## Runtime layers

1. The `podman` role supports Ubuntu 26.04+ and Linux Mint Debian Edition 7 (based on Debian 13), requires Podman 5.4.2 or newer, and verifies cgroup v2 plus the system Quadlet generator. The current `podman_services` templates use directives available in Podman 5.4.2 for both system and rootless Quadlets. Ubuntu 24.04 LTS (Noble) remains unsupported because its packaged Podman 4.9 is below this baseline.
2. The linear, globally ordered dispatcher materializes one selected service on its dispatch host before invoking common preparation and its runtime adapter.
3. `service_prepare` owns application validation, generated values, template derivation, and bootstrap requests. Its temporary preparation containers use the selected runtime and are removed before deployed-service lifecycle work.
4. `service_common` prepares runtime-neutral Infisical values, environment, host paths, files, Traefik routes, and PostgreSQL databases from explicit adapter inputs.
5. `podman_services` renders rootful system Quadlets or the deliberately limited rootless user Quadlets described below. It retains Podman image, network, secret, Quadlet-validation, and systemd lifecycle ownership.

Omitting `deploy.execution` keeps the existing rootful behavior. Rootful
Quadlets live in `/etc/containers/systemd`, use root's Podman storage, and run
through the system manager. Rootless Quadlets live in the dedicated account's
`$HOME/.config/containers/systemd`, use that account's separate Podman storage,
and run through its user manager. The dispatcher enables Ansible SSH pipelining
for Podman role tasks so privilege switching does not require a temporary module
file shared with the locked service account. This controller transport setting
is not placed in the application environment.

The runtime package set explicitly includes `passt` for the rootless `pasta`
network backend and `dbus-user-session` for the per-user systemd manager, in
addition to the existing Podman, network-plugin, subordinate-ID, slirp4netns,
and fuse-overlayfs packages.

`deploy.execution.host_user` is the host account that owns a rootless Podman
instance. It must use the reserved `podman-` prefix and is separate from
top-level `user: "UID:GID"`, which selects the identity inside the container.
Before creating anything, the role inspects the account, primary group, home,
and root-owned service marker. It creates them only when all four are absent,
or reuses an account only when its full locked-account contract and persisted
service ownership match exactly. Each account has a dedicated primary group,
no supplementary groups, a non-interactive shell, at least 65,536 subordinate
UIDs and GIDs, and systemd linger. The user manager receives explicit `HOME`,
`XDG_RUNTIME_DIR`, and `DBUS_SESSION_BUS_ADDRESS` values without relying on an
interactive login.

## Logging

Every normalized Podman service carries `log_driver`. It defaults to the only
currently supported value, `journald`, and the container Quadlet renders
`LogDriver=journald` through the native Quadlet field. Arbitrary drivers and
`PodmanArgs` are rejected. This contract is identical for rootful system units,
rootless user units, and containers sharing another managed container network
namespace.

A package-managed native Alloy agent on hosts in the `tags_podman` inventory
group reads the system journal as its dedicated `alloy` account. Membership in
the locally available `adm` and `systemd-journal` groups supplies journal access;
the agent does not run as root and does not connect to system or per-user Podman
sockets. Rootless service logs are therefore collected through their systemd
user units without sharing `/run/user/<uid>` runtime directories. See
[Central logging](central-logging.md) for labels, topology, and queries.

## Migration guardrails

The Podman adapter validates the complete effective service mapping. It accepts
only catalog metadata, fields it renders or validates itself, runtime-neutral
`service_common` fields, and real `service_prepare` inputs. Any Docker-only or
unknown top-level field fails with every unsupported key listed in sorted order.
Changing only `runtime` is therefore unsafe and rejected when behavior such as an
entrypoint, Swarm config, privileged mode, profile, or constraint still lacks a
Podman implementation. Supported fields must preserve their real behavior.

An explicit canonical `name` controls the Podman container name, generated
`.container` and protected `.env` filenames, and derived `.service` lifecycle
unit. Without it, a base uses its catalog name and a target uses the existing
base-target role prefix. If `deploy.type` is present it must be exactly
`container`; `swarm`, `profile`, and `constraints` are invalid. Portable
`mode: replicated` and `replicas: 1` remain accepted single-instance no-ops.

Rootful execution additionally supports three constrained native Quadlet
features. Canonical `devices` entries use
`HOST_DEVICE[:CONTAINER_DEVICE[:PERMISSIONS]]` syntax with normalized paths
below `/dev` and render as `AddDevice=`. Canonical `shm_size` accepts a
positive byte-size value such as `1gb` and renders as `ShmSize=`.
`network_mode` accepts `host` or `container:<managed-container-name>`, cannot be
combined with `named_networks`, and renders the corresponding native `Network=`
field. Host networking cannot declare published ports. No arbitrary `PodmanArgs` or
generic pod support is implied by these fields.

Rootless execution requires a dedicated account, fully qualified exact images
and unprivileged published TCP ports. It uses one owned bridge by default.
Explicit `network_mode: pasta` selects direct pasta for source-preserving ingress;
it cannot be combined with a named network or arbitrary network options. This
mode is rootless-only and introduces no managed namespace dependency. Bind sources must
be declared directory roots under `/opt`; their managed subdirectories/files
and minimal parent layout are supported without arbitrary host-path access.
A validated `keep-id` UID/GID mapping preserves the application identity;
explicit `user` also preserves container-root initialization when needed.
Generated files omit owner/group and use the dedicated account. The adapter
never recursively changes a bind tree's ownership. Initial existing-data transitions
require the documented per-image mapping, consistent backups and per-service
`services_rootless_data_ready[<actual effective service name>]: true` when
`operational_requirements.ownership_transition: true` is declared.

For ordinary deploy/update/recreate, the preflight reuses owned execution state,
the dedicated account marker/current NSS identity and the generated Quadlet's
publication, user, keep-id mapping and bind contract. An unchanged managed store
needs no repeated ownership acknowledgement. Missing or replaced managed data
bind roots stop maintenance for consistent restoration. New/changed mappings or binds,
unmanaged stores and legacy state without sufficient ownership evidence retain
the explicit per-service transition gate; do not set it until the transition is
actually proved. A running unit or a path's existence alone grants no exemption.

Managed endpoints are compared with the current installed firewall policy and
its expected callers before secret preflight, file preparation or runtime stops.
The existing helper then audits both kernel families, current caller identities
and persistence. Changed ports, placement or caller contracts, missing policy,
and noncompliant audits stop maintenance with a reconciliation error. Flags
cannot override a failed maintenance audit. No ordinary application operation
installs or extends policy. This verifies mechanical prerequisites, not completed
application acceptance.

A **prerequisite proof** is the result of checks for one service operation, matched to
its exact service/target metadata. It stays in that operation's common context and is
not saved as application acceptance. Recreate checks before stopping the old runtime,
then reuses those checks while starting the replacement; existing runtime ownership,
caller reconciliation and post-start checks remain. Bootstrap checks every
provider/consumer before stopping any and retains each result by service name. Static
local bootstrap uses the trusted installed policy identity and verifies its local
address, without depending on NetBox, the catalog or Infisical lookup.

Requirements remain independent of tags. Check mode validates and reports a
plan without inspecting live protection. Drift/removal remain available without
deployment acknowledgements. Explicit account-only deploy/update/bootstrap
preparation returns before application file/image/secret/container work. Supplied
acknowledgements retain strict boolean typing. See the
[operational requirement reference](../ansible/group_vars/all/services/README.md#operational-requirements).

Select the worktree explicitly when using its implementation; launching from a
worktree does not change the installed skynet default:

```bash
worktree=/opt/ansible/migration/merge-preparation-wdsnkwea/worktrees/mgt-podman
PLAYBOOK="$worktree/ansible/playbook.yml" \
ANSIBLE_CONFIG="$worktree/ansible/ansible.cfg" \
skynet recreate whisparr
```

This is an operator maintenance command, not an offline validation command. For
offline syntax checks use an isolated localhost inventory/config with vars
plugins disabled; never load the NetBox inventory merely to check syntax.

Rootless standalone tmpfs uses the same constrained options as rootful tmpfs.
Added capabilities, devices, host/container network modes, named volumes and
shm_size remain unsupported here. HAProxy validation-only preparation,
Authelia's short-lived generators, and Vaultwarden's persistent token preparation
are supported; other preparation contracts still fail explicitly. Podman
preparation start/inspect/logs/cleanup all use the adapter's explicit execution
account and runtime environment, retain guaranteed cleanup and never run in
check mode. Mounted configurations use directories so atomic file replacement
is visible; single-file bind sources are not accepted as directory roots.

Traefik additionally confines its declared log tree to `/var/log/skynet` and
allowlists exactly its root-owned host logrotate policy and reopen helper.
ACME touch preserves timestamps. Logrotate creates logs for the dedicated
account; the helper invokes Podman through `runuser` without a login shell.
`podman_services_prepare_execution_only: true` is an explicit strict-boolean
account-preparation option for deploy/update/bootstrap. It returns after
execution setup, before data/file/image/secret/container work. It does not permit
remove/recreate/drift and does not make a catalog call independent of inventory.

Every dedicated rootless account receives one role-owned Podman configuration
drop-in at
`/var/lib/<host_user>/.config/containers/containers.conf.d/20-podman-services-network.conf`.
The role never replaces the account's operator-managed `containers.conf` and
does not change global `/etc/containers` configuration. This corrects a pasta
same-host routing failure: pasta normally copies the host primary-interface
addresses, so a container resolving a canonical internal FQDN to that host's
real LAN address can treat the destination as its own address and refuse the
connection. Podman's documented account-specific `containers.conf.d` loading
and pasta behavior are described in the upstream
[`containers.conf(5)` documentation](https://github.com/containers/common/blob/main/docs/containers.conf.5.md)
and [`podman-run(1)` network documentation](https://docs.podman.io/en/latest/markdown/podman-run.1.html#network-mode-networks).

The managed `[network]` table uses the documented private IPv4 pasta shape:

```toml
pasta_options = [
  "--ipv4-only",
  "-a", "10.0.2.0",
  "-n", "24",
  "-g", "10.0.2.2",
  "--dns-forward", "10.0.2.3",
  "--no-ndp",
  "--no-dhcpv6",
  "--no-dhcp",
]
```

For ordinary bridge services, this deliberately disables IPv6 in the account's rootless pasta namespace so
neither address family copies a host-interface address. Podman still owns
interface setup and port forwarding; the role does not override pasta's MTU or
TCP/UDP forwarding behavior. Before live account or file mutation, the role
validates the RFC 1918 subnet/gateway/DNS-forward tuple and rejects overlap with
any non-default host IPv4 route. The same range is safe for separate dedicated
accounts because each account has distinct rootless runtime state and an extra
rootless network namespace. Internal DNS remains unchanged, applications keep
using canonical internal FQDNs, and `host.containers.internal` remains available
as a diagnostic address rather than an application configuration convention.
Rootful Podman is unaffected.

Explicit direct-pasta ingress uses a private dual-stack profile in that same
account-owned drop-in. The existing IPv4 tuple is retained; IPv6 defaults to
`fd00:2::2/64` with gateway `fd00:2::1`. These are private namespace addresses,
not additional host publications or host interface configuration. The profile
omits `--ipv4-only` and `--no-ndp`, adds the IPv6 address/gateway and `--no-ra`,
and retains `--no-dhcpv6`/`--no-dhcp`. Neighbour discovery must remain enabled
for replies through the private IPv6 gateway. Before mutation, both families'
non-default host routes must not overlap the selected private subnets. Missing
or malformed route observations fail validation; check mode performs no route
query. Other accounts retain the existing IPv4-only profile.

Direct pasta is necessary for Traefik's observed Podman 5.7.0 ingress behavior:
the managed bridge rewrites incoming source addresses, while direct pasta
preserved the original IPv4/IPv6 peers in isolated tests. Wildcard publication
retains its current address-family coverage; private metrics remains bound to
the inventory LAN IPv4 address. Source-preservation and host publication are
separate from firewall caller authorization, which still requires live proof.
See the [ingress authorization runbook](mgt-firewall.md). This does not claim execution on the
stated minimum Podman 5.4.2.

The drop-in is managed only during deploy, update, recreate, and bootstrap.
Check mode validates and reports its exact intended path without creating an
account, directory, or file. A changed drop-in takes effect when the selected
service's rootless networking namespace is re-established, so use an explicit
service recreate; the role does not restart other rootless accounts. Ordinary
remove preserves the dedicated account, home, Podman storage, and this network
drop-in. Account and configuration retirement remain a separate deliberate
operator procedure.

## Lifecycle semantics

- `deploy` and `bootstrap` fetch missing secrets, create missing Podman secrets, pull the declared image, render configuration, and start the service if it is not already running.
- `update` compares secrets marked `update_policy: reconcile` and replaces the rootful container or restarts the rootless user service when material inputs changed, including a changed secret or restart-requiring managed application file. An unchanged reconciled secret alone does not trigger a restart. An owned network remains in place through the replacement. If its Quadlet definition changes, use an explicit remove followed by deploy when the network itself must be recreated.
- `recreate` reconciles secrets marked `update_policy: reconcile`, stops the rootful unit, removes its exact stale container object, and starts the generated service after rendering current inputs. It retains the service network. Rootless recreate keeps its existing user-service restart behavior.
- `remove` uses the last successfully persisted execution owner even when the declaration now requests another mode. It stops that service first, then stops and removes only a network whose persisted metadata proves role ownership. It removes exact generated Quadlets, environment files, and host-backed Traefik routing, but preserves application data, Podman secrets, images, the dedicated rootless account, its linger configuration, home, and user storage. Externally owned and unproven legacy networks are retained.
- `drift` inspects the current container image reference and reports a changed task when it differs from the declared exact image reference. It is reference drift, not registry digest drift.

Generated rootful `.container` files use
`[Install] WantedBy=multi-user.target`; rootless files use
`WantedBy=default.target`. Quadlet generators connect them to the appropriate
system or user manager, so the role does not separately enable each generated
service.

The role records the successfully started execution owner and its non-sensitive
generated-resource metadata in root-owned state. `remove` and `drift` use that
active owner; deploy-like actions use the desired owner. When the mode or
rootless account changes, the role prepares and validates the destination
first, stops only the exact old service unit, starts and verifies the new unit,
and only then removes exact stale generated files bearing the Ansible marker.
Old network cleanup uses only the name and ownership recorded for the previous
Podman store; older state without that evidence deliberately leaves the network
in place. A failed start reports safe systemctl return codes and error text,
stops the failed destination, and restores the previously active unit when
possible. It never prunes images, user storage, or volume data. To return a
service to rootful execution, remove `deploy.execution` (or set `mode: rootful`
without `host_user`) and run the normal recreate operation.

Ordinary removal is intentionally not account retirement. Retiring a dedicated
rootless account is a separate operator procedure after the service has been
removed: verify that no persisted service marker refers to the account, inspect
its Podman storage for data that must be retained, disable linger, stop its user
manager, and only then remove the account, primary group, home, subordinate-ID
entries, and storage deliberately. The role does not automate those destructive
steps.

Both adapters consume the top-level `named_networks` mapping. Podman currently
supports exactly one attached named network. `external: false` makes the role
responsible for its network Quadlet and explicit remove lifecycle;
`external: true` attaches the container directly to an existing network and
never creates or deletes it. Before any live deploy, update, recreate, or
bootstrap mutation, the role runs `podman network exists` for the exact validated
name and fails if it is absent. Check mode validates the declaration without a
runtime call. `delete_on_stop` is not supported: ordinary
stops, updates, recreates, and systemd restarts retain an owned network.

Docker and Podman keep separate network stores; a Docker network with a matching
name does not satisfy this Podman preflight. Prefer a managed Podman network for
an isolated service. Cross-runtime communication must use published host
endpoints or another deliberately designed network path.

For shared network namespaces, the referenced `.container` suffix lets Quadlet
derive the systemd dependency on the provider container unit. The provider must
be deployed first; a child start fails if that unit or its network namespace is
unavailable. Publish every host-facing port on the provider because namespace
children cannot publish ports independently.

The service catalog also treats `network_mode: container:<provider>` as a
lifecycle dependency when `<provider>` resolves to the effective container name
of another managed rootful Podman service on the same host. It validates the
whole managed graph before dispatch: self-dependencies, cycles, cross-host
references to a managed provider, and rootless namespace sharing fail without
runtime mutation. A reference with no managed Podman match remains an external
container reference and keeps its previous behavior. Docker services are never
considered Podman namespace providers.

Deploy, bootstrap, update, recreate, and drift dispatch managed providers before
their consumers. A provider recreate, execution-mode change, or update that
actually requires a restart records the active state of every transitive managed
consumer, stops every loaded consumer unit in reverse dependency order, replaces
each exact consumer container object with `podman rm --force --ignore`, stops
and removes the exact provider object, then starts and verifies the provider.
Only consumers that were active are restored, in forward dependency order.
Loaded inactive or failed consumers are cleaned but remain inactive; units that
have not been deployed are skipped. Cleanup never uses recursive `--depend`
removal, so only planner-provided managed container names are touched. Selecting
only a provider uses this transaction transparently. Selecting only a consumer
does not stop or restart its provider. If the transaction fails after
dependent services are stopped, the failure remains visible and those
consumers remain stopped rather than being started against an unavailable
provider.

Remove is deliberately stricter. Selecting a managed provider for removal
requires selecting its complete transitive dependent closure; otherwise catalog
validation fails before dispatch with the missing dependents. A valid removal is
ordered consumer-first. Unmanaged external namespace providers cannot receive
this orchestration, so their replacement remains an operator responsibility.

Podman systemd policy is also first-class at top level. The supported fields are
`after`, `restart`, `restart_sec`, and `timeout_start_sec`, rendered as
`After=`, `Restart=`, `RestartSec=`, and optional `TimeoutStartSec=`. The
startup timeout bounds how long systemd waits; it does not delay a service that
starts successfully. Service-level `runtime_options.podman.network` and
`runtime_options.podman.systemd` are retired and fail with migration guidance. Secret update intent is runtime-neutral under `secret.update_policy`; secret-level `runtime_options` is retired and fails with guidance to use that canonical field.

Named publication aliases with identical normalized host address, host port,
container port and protocol render one `PublishPort=` binding. Every alias is
validated before deduplication; distinct publications retain their order.

Published ports accept an optional `host_ip` per port. When set, the generated `PublishPort=` entry binds only that address. When omitted, Podman binds the published port on every host interface; this can expose the service on management, LAN, Tailscale, or other reachable networks and can bypass the intended reverse proxy and its middleware. Prefer an explicit trusted bind address and enforce host/network firewall policy whenever direct access is not intended.

## Secrets and PostgreSQL

Canonical materialized secrets use the same nested Infisical declaration for
rootful and rootless execution:

```yaml
environment:
  APP_PASSWORD_FILE: /run/secrets/app_password_secret
infisical:
  secrets_map:
    - var: app_password
      path: /App
      name: PASSWORD
      secret:
        name: app_password_secret
        target: /run/secrets/app_password_secret
        uid: "1000"
        gid: "1000"
        mode: "0400"
        update_policy: reconcile
    - var: lookup_only
      path: /App
      name: TEMPLATE_VALUE
```

`service_common` validates the lookup and value-free declaration metadata, resets all outputs per service, and retrieves lookup-only and secret-backed values into `service_common_infisical_values`, keyed by `var`. `fail_on_empty` defaults to true; setting it to false is an exceptional opt-out for declarations that intentionally permit empty values. Entries without `secret` remain lookup-only. It also resolves the canonical environment before Podman renders its protected environment file or Quadlets. Check mode validates declarations and references without contacting Infisical or creating a native secret, using an optional declaration-owned `check_mode_value` when present and deterministic redacted stand-ins otherwise.

`podman_services` remains responsible for `containers.podman.podman_secret` and Quadlet attachment. It reads the value through the declaration's `var`, creates the declared native Podman secret name in the selected execution account's store, and preserves target, UID, GID, and mode in `Secret=`. The module sends the value over stdin, not the command line. Value-carrying tasks use `no_log: true` and `diff: false`; values never enter generated Quadlets. The mount defaults to mode `0400` and the configured container UID/GID. Native Podman secrets keep values out of container environment metadata when the application consumes the file directly. The default file-backed secret driver is not encrypted storage; the execution account and host root can retrieve its contents. Ordinary removal deliberately preserves these resources with user storage; secret retirement requires an operator's explicit cleanup after checking consumers.

`secret.update_policy` accepts exactly `preserve` or `reconcile` and defaults to `preserve`. Both policies create a missing native secret and preserve an existing one during deploy/bootstrap. Podman translates reconcile during update/recreate to `force: true` and `skip_existing: false`; preserve always uses `force: false` and `skip_existing: true`. At the repository's Podman 5.4.2+ baseline, the installed collection compares existing content and replaces only changed secrets. A changed result follows the selected service's replacement/restart path, because mounts are populated when its container is created. Explicit recreate still restarts regardless of changes. Legacy runtime-specific secret policy blocks are rejected.

The canonical PostgreSQL declaration is shared by Docker and Podman:

```yaml
postgres:
  enable: true
  databases: [app]
  port: 5432
  user_var: postgres_user
  password_var: postgres_pass
  # Optional: host or host_inventory, but never both.
```

When neither address field is supplied, `host_inventory` defaults to `service_common_controller_host` and resolves that inventory host `local_ip`. An explicit `host` skips inventory lookup. After common Infisical resolution, live deploy/update/recreate/bootstrap operations delegate idempotent `postgresql_db state=present` reconciliation to the controller before Quadlet rendering and lifecycle. Check mode validates the schema, references, inventory, and resolved address without authenticating or connecting, then prints a non-sensitive plan.

## Canonical environment values

Portable services may use ordinary scalar environment values, direct `value_from.infisical` references, or `value_template` strings containing one or more `${identifier}` references. Every reference must match a `var` declared by that service. Substitution is deliberately single-pass and does not evaluate Jinja or shell expressions; `$$` represents a literal dollar sign. `service_common` produces the final scalar mapping consumed by the Podman adapter.

Docker and Podman now consume the same common-resolved environment. The former exact `__INFISICAL__:var` Docker placeholder has been removed after repository services migrated to typed references. Existing Docker `env_file` behaviour is unchanged. Runtime-native secrets remain separate: only an Infisical entry with `secret` metadata creates and attaches a Podman secret.

`value_from.infisical` means plaintext environment injection, not a runtime
secret mount. Podman stores that value in the execution-account-owned `0600`
environment file and container environment metadata; `podman inspect` can
retrieve it. Quadlet's `[Container] EnvironmentFile=` becomes Podman's
`--env-file` argument, so values do not enter the generated unit command line
or systemd manager environment. Environment-only applications remain supported.
See [Service secret delivery audit](service-secret-delivery.md) for the
Docker comparison and disk/runtime exposure boundaries.

## Adminer

Adminer is the first deliberately rootless Quadlet service. It runs on
`services_controller_host` under the locked `podman-adminer` host account. Its
former Docker stack, external overlay, Swarm profile, and placement constraint
are not carried into Podman. Its Quadlets live under
`/var/lib/podman-adminer/.config/containers/systemd`, and its image, container,
and managed `adminer.network` bridge live only in that account's Podman storage.
It publishes container port 8080 as host port 18080 on the controller
`local_ip`. The common Traefik route uses that host endpoint, so it does not
depend on cross-runtime network attachment.

The declaration has no persistent volume or native secret. Its Infisical entry
remains lookup-only for the private route zone. `systemd` retains the intended
on-failure restart policy with a ten-second delay. Repository tests prove the
effective catalog selection, common check-mode lookup shape, host-backed
Traefik address, generated user Quadlet, account isolation, and transition
ordering. Because the backend binds the controller's management/LAN address,
clients on that network can bypass Traefik and its middleware by reaching port
18080 directly. A future firewall rule should allow only the Traefik source
address to TCP/18080 and reject other LAN sources after the source address is
confirmed from live traffic.

## The Lounge

The Lounge runs on `services_controller_host` under the locked
`podman-thelounge` account. It publishes container port 9000 as host port
19000 on the controller `local_ip`; Traefik uses that host endpoint rather
than a cross-runtime overlay.

Its existing `/opt/thelounge` application-data source remains mounted at `/config`.
The declared `keep-id` user namespace maps the dedicated execution account to
the configured application PUID/GID. An explicit container `user: "0:0"`
keeps LinuxServer's s6 initialization running as container root; that identity
maps to an unprivileged subordinate host ID, not host root. s6 can therefore
apply `PUID`, `PGID`, and `UMASK` before dropping The Lounge to container
UID/GID 1000, which maps back to `podman-thelounge`.

Before Quadlet rendering, the adapter manages the bind root's declared mode
and account ownership without recursively changing descendants. Preserve an
already transitioned tree; any new ownership transition must use the operator
procedure and the effective container UID/GID mapping. Its
`systemd.timeout_start_sec: 900s` setting allows a
slow first container creation to complete; it only bounds systemd's wait and does
not delay later successful starts.

Remove the old Docker Swarm stack while the Docker declaration is still active,
then deploy the Podman declaration. The runtime adapters deliberately do not
remove one another's deployed resources. Back up the configuration first; a
later Docker rollback will need ownership reconvergence by the rootful
LinuxServer container or an explicit operator correction.

The managed `thelounge.network` bridge is private to this account's Podman
store. The host-backed Traefik route and direct TCP/19000 exposure have the same
firewall consideration as Adminer's direct backend.

## mgt shared bridge and bootstrap

The `podman` role owns `/etc/containers/systemd/mgt-services.network` centrally.
Its explicit `NetworkName=mgt-services` matches catalog attachments. Run
`skynet install podman-network` (or `skynet raw --tags podman_network`) after
installing the supported runtime. It has no application remove action. Rootful
bridge consumers declare it external and require `mgt-services-network.service`;
application stop/update/recreate/remove retains it. No fixed subnet is assigned.
All migrated ordinary services and five bootstrap containers use separate
rootless accounts/bridges. Rootless services never attach to the root bridge.
The four pre-existing accounts/networks retain their ownership.

Production NetBox and Infisical bootstrap reuse `podman_services` with explicit
Vault-backed context and no catalog, dynamic inventory, or Infisical lookup.
`ansible/bootstrap.yml` is the localhost recovery entry point. NetBox retains
its local PostgreSQL major, database tree, `/var/lib/postgresql` mount, cache,
and LSIO configuration. Infisical retains its external HAProxy/PostgreSQL path,
keys and direct port 8066. NetBox adds an inventory-bound recovery port 18000.
Both roles require `services_bootstrap_acl_ready: true` before live deployment.
The experimental Infisical owner is retired; old wrapper aliases resolve to the
production role. See the [migrator workspace](../migrator/README.md).

## Process, environment and dependencies

`command` is a nonempty list of nonempty literal argv strings. String shell
commands and control characters are rejected. Use `[sh, -c, '...']` explicitly
for shell operations. Quadlet `Exec=` quoting preserves spaces, quotes,
backslashes, dollars and systemd percent specifiers through generation.
Credentials belong in native files or protected environments, not resolved argv.
The Valkey services derive a mode-0600 configuration in their private `/tmp`
tmpfs from a native secret, then exec the server with only that file path.

Podman `env_file` is an ordered list of normalized absolute paths. The adapter
reads the files after common templates, parses a literal single-line dotenv
subset, merges later files over earlier ones, then applies explicit resolved
`environment` last. Single/double delimiter quotes are removed; quoted escaped
quotes/backslashes/dollars are decoded. Comments, blank lines and empty values
are supported. Export/unset, multiline values and unsupported escapes fail
without logging input values. Shell substitution/interpolation is never
performed. The final raw Podman environment file is mode 0600; its values are
not shell-quoted and are not doubled for Compose or systemd. Check mode does
not read these files or overwrite secret-bearing generated environments and
reports content comparison as deferred.

Rootful and rootless standalone `tmpfs` accept normalized absolute paths with optional allowlisted
`exec`, `noexec`, `nosuid`, `nodev`, `rw`, `ro`, numeric `size` and octal `mode`
options. Rootful `cgroup: host` is the narrow systemd-container contract: fixed
`--cgroupns=host --systemd=always` and `Delegate=yes`. It does not enable arbitrary
Podman arguments or privileged mode. UniFi uses this contract with its pinned
upstream mounts, capabilities and tmpfs; live compatibility requires its
controlled smoke test.

`systemd.requires` and `systemd.wants` take valid service/target unit names and
render both the dependency and `After=`. `notify_healthy: true` requires a
healthcheck and renders `Notify=healthy`, so successful start waits for health.
Shell health checks use a JSON argument array containing `/bin/sh`, `-c` and the
complete normalized command. This preserves closing quotes, substitutions and
literal percent signs through Quadlet and systemd; disabled checks remain
`HealthCmd=none`. Generation alone does not establish a healthy running service.
Managed service dependencies must share the host and system manager or the
same rootless account/user manager. Cross-account dependencies are not rendered;
use application retries, readiness verification and explicit deployment sequencing. Required shared-network units use Requires. Restart=always,
a delay and disabled start-rate limiting provide retries for late database/cache
availability; After alone is ordering, not readiness. The catalog orders selected
same-manager managed Requires/Wants/After providers before consumers (consumer-first
for removal) and rejects cycles
or dependencies crossing execution stores. Namespace-sharing transactions retain
their stricter existing stop/restart semantics. Bootstrap recreate stops its
consumer units first and starts providers first.

Common copies/templates default to `restart: true`; the common role reports
material changes and each adapter immediately snapshots its own flag. Podman
update includes that flag in restart decisions. Set `restart: false` for watched
Traefik dynamic files; route-only changes do not restart the routed app. Existing
Docker lifecycle remains unchanged. Invalid restart policy and application
settings are validated before Podman execution preparation.

## Ubuntu pasta/AppArmor prerequisite

The mgt migration required a separately approved permission in the package's
`/etc/apparmor.d/usr.bin.pasta` profile:

```apparmor
signal (receive) set=(term) peer=podman,
```

It permits Podman to terminate its pasta helper. It grants no broader signal or
peer access. This is a retained host-profile prerequisite; this repository does
not assert that a later package now supplies it. A clean rebuild must inspect the
installed profile/package and qualify helper cleanup before any application stop.
The native journal collector and the rootful `alloy-mgt` file/exporter collector
remain separate consumers; neither applies this host-security permission.

The existing approved repair is reproducible through `ansible/operations.yml`
with the explicit `podman_pasta_signal` tag. Its task requires root-owned mode
`0644`, exact reviewed before/after SHA256 hashes, parser validation without kernel
loading, a pasta-only reload after a change and guarded restoration on failure.
Check mode is read-only. It is not included in default Podman installation,
application deployment or `--tags all`, and running it requires separate host-
security authorization. Do not reuse migration-era profile hashes after a
package/profile change or infer permission from this source change. Historical
execution/cleanup receipts remain in the private migration handoff.
