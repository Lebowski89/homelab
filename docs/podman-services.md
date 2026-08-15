# Podman services

Use the
[service-definition option reference](../ansible/group_vars/all/services/README.md)
for canonical fields, defaults, and compatibility. This document focuses on
Podman adapter behavior and operational limits.

The shared service catalogue in `ansible/group_vars/all/services/*.yml` is runtime-aware. Every base service must explicitly declare `runtime: docker` or `runtime: podman`; a missing or unsupported runtime fails catalog validation. Targets inherit the validated base runtime and may explicitly override it with another supported runtime. Podman entries are selected by the same `skynet install|update|check|recreate|remove|drift <service>` interface and dispatched to `podman_services`.

## Runtime layers

1. `podman_services` intentionally renders Quadlets using Podman 5.7 syntax and is not compatible with Ubuntu 24.04 LTS (Noble), whose packaged Podman 4.9 lacks the required directives.
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

## Migration guardrails

The Podman adapter validates the complete effective service mapping. It accepts
only catalog metadata, fields it renders or validates itself, runtime-neutral
`service_common` fields, and real `service_prepare` inputs. Any Docker-only or
unknown top-level field fails with every unsupported key listed in sorted order.
Changing only `runtime` is therefore unsafe and rejected when behavior such as a
custom command, entrypoint, config, device, host network, Swarm profile, or
constraint still lacks a Podman implementation.

An explicit canonical `name` controls the Podman container name, generated
`.container` and protected `.env` filenames, and derived `.service` lifecycle
unit. Without it, a base uses its catalog name and a target uses the existing
base-target role prefix. If `deploy.type` is present it must be exactly
`container`; `swarm`, `profile`, and `constraints` are invalid. Portable
`mode: replicated` and `replicas: 1` remain accepted single-instance no-ops.

Rootless execution is intentionally narrower than the general Podman schema.
It requires `deploy.type: container`, a fully qualified exact image, one
role-managed bridge, and unprivileged published TCP ports. A rootless bind mount
must use an exact normalized proper descendant of `/opt` that is also declared
in `paths`, omit explicit path ownership, and provide a validated
`deploy.execution.userns: {mode: keep-id, uid: ..., gid: ...}` mapping. After
the common path exists, the adapter recursively assigns that source to the
dedicated execution account without changing descendant modes. Named volumes,
tmpfs mounts, native secrets, added capabilities, devices, privileged mode,
host networking, and application preparation remain unsupported for rootless
execution. Rootless `copies` and `templates` are supported only when every
destination is a normalized absolute proper descendant of a declared bind
source; explicit file owner/group overrides are rejected so `service_common`
uses the dedicated execution account. Additional `paths` entries are limited to
`state: absent` descendants of a declared bind source, also without ownership
overrides. This intentionally provides managed-file parity inside an existing
bind tree, not general rootless filesystem parity. Unsupported combinations
fail during normalization before account or runtime mutation. Adminer fits the
mount-free subset, The Lounge exercises the bind-backed subset, Homepage uses
confined templates, a static copy, and stale Docker-file cleanup, and n8n
remains rootful.

## Lifecycle semantics

- `deploy` and `bootstrap` fetch missing secrets, create missing Podman secrets, pull the declared image, render configuration, and start the service if it is not already running.
- `update` reconciles secrets marked `update_policy: reconcile` and restarts the service when material inputs changed; because Podman cannot compare stored secret contents, a reconciled secret is recreated and triggers the existing restart path. An owned network remains in place through the restart. If its Quadlet definition changes, use an explicit remove followed by deploy when the network itself must be recreated.
- `recreate` reconciles secrets marked `update_policy: reconcile` and always restarts the generated service after rendering current inputs. It retains the service network.
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

Podman systemd policy is also first-class at top level. The supported fields are
`after`, `restart`, `restart_sec`, and `timeout_start_sec`, rendered as
`After=`, `Restart=`, `RestartSec=`, and optional `TimeoutStartSec=`. The
startup timeout bounds how long systemd waits; it does not delay a service that
starts successfully. Service-level `runtime_options.podman.network` and
`runtime_options.podman.systemd` are retired and fail with migration guidance. Secret update intent is runtime-neutral under `secret.update_policy`; secret-level `runtime_options` is retired and fails with guidance to use that canonical field.

Published ports accept an optional `host_ip` per port. When set, the generated `PublishPort=` entry binds only that address. When omitted, Podman binds the published port on every host interface; this can expose the service on management, LAN, Tailscale, or other reachable networks and can bypass the intended reverse proxy and its middleware. Prefer an explicit trusted bind address and enforce host/network firewall policy whenever direct access is not intended.

## Secrets and PostgreSQL

Canonical materialized secrets are nested in an Infisical map entry:

```yaml
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

`podman_services` remains responsible for `containers.podman.podman_secret` and Quadlet attachment. It reads the value through the declaration's `var`, creates the declared native Podman secret name, and preserves target, UID, GID, and mode in `Secret=`. Value-carrying tasks use `no_log: true` and `diff: false`; values never enter generated Quadlets. Native Podman secrets keep values out of repository files and generated unit arguments, but the default file-backed secret driver is not encrypted storage and root on the host can access it.

`secret.update_policy` accepts exactly `preserve` or `reconcile` and defaults to `preserve`. Both policies create a missing native secret and preserve an existing one during deploy/bootstrap. Podman translates reconcile during update/recreate to `force: true` and `skip_existing: false`; preserve always uses `force: false` and `skip_existing: true`. Podman cannot compare stored secret contents, so reconcile recreates the secret and follows the existing restart path. Legacy runtime-specific secret policy blocks are rejected.

The canonical PostgreSQL declaration is shared by Docker and Podman:

```yaml
postgres:
  enable: true
  databases: [n8n]
  port: 5432
  user_var: postgres_user
  password_var: postgres_pass
  # Optional: host or host_inventory, but never both.
```

When neither address field is supplied, `host_inventory` defaults to `service_common_controller_host` and resolves that inventory host `local_ip`. An explicit `host` skips inventory lookup. After common Infisical resolution, live deploy/update/recreate/bootstrap operations delegate idempotent `postgresql_db state=present` reconciliation to the controller before Quadlet rendering and lifecycle. Check mode validates the schema, references, inventory, and resolved address without authenticating or connecting, then prints a non-sensitive plan.

## Canonical environment values

Portable services may use ordinary scalar environment values, direct `value_from.infisical` references, or `value_template` strings containing one or more `${identifier}` references. Every reference must match a `var` declared by that service. Substitution is deliberately single-pass and does not evaluate Jinja or shell expressions; `$$` represents a literal dollar sign. `service_common` produces the final scalar mapping consumed by the Podman adapter.

Docker and Podman now consume the same common-resolved environment. The former exact `__INFISICAL__:var` Docker placeholder has been removed after repository services migrated to typed references. Existing Docker `env_file` behaviour is unchanged. Runtime-native secrets remain separate: only an Infisical entry with `secret` metadata creates and attaches a Podman secret.

## n8n

n8n was the first service migrated to the portable Docker-shaped schema. Its declaration uses top-level `image`, `user`, `environment`, `named_networks`, canonical ports/volumes/paths, `deploy`, `systemd`, health/security fields, canonical Infisical secrets, PostgreSQL, and Traefik. `runtime: podman` selects this adapter. Adminer, The Lounge, and Homepage are the next deliberately migrated services; further adoption remains incremental, one validated service at a time.

n8n runs on the dedicated `n8n` VM after it is rebuilt or upgraded to Ubuntu 26.04. The selected host must already have the runtime required by the declaration. A runtime-only edit is valid only when the complete effective declaration passes the destination adapter; it does not install a runtime or establish live parity. The proof covers the trusted-address `host_ip` bind in both generated Docker standalone Compose and Podman Quadlet output. Static tests do not replace a live migration test.


The service uses pinned image `docker.io/n8nio/n8n:2.31.4`, UID/GID 1000:1000, application data in `/opt/n8n`, PostgreSQL database `n8n` through the shared HAProxy endpoint, and private routing at `https://n8n.int.<cloudflare-zone>:8443/`. The direct backend binds port 5678 to the VM management/LAN address; that direct port remains reachable on that network and bypasses Traefik TLS and middleware.

Its three canonical secrets preserve their lifecycle intent: the PostgreSQL username and n8n encryption key use the default `preserve` policy, while the PostgreSQL password uses `reconcile` during update/recreate. Shared preparation ensures the `n8n` database exists before the Podman service starts.


Required private values before deployment:

- Add `n8n` to `terraform/netbox/private.auto.tfvars` with `192.168.80.98/24` and the real Tailscale IP.
- Create and back up a strong, stable `/N8N/ENCRYPTION_KEY` Infisical value before first launch.

During the first live start, verify `N8N_ENCRYPTION_KEY_FILE` with the selected n8n image without printing the secret. Check that `/run/secrets/n8n_encryption_key_secret` exists and is non-empty inside the container, inspect startup logs for missing-key or encryption-key errors, restart n8n, and confirm it starts successfully again. Never display the secret contents.

Back up the encryption key, PostgreSQL data, and `/opt/n8n`. n8n deliberately does not mount Docker/Podman sockets, host root, SSH keys, or unrelated directories.

Future hardening: add network-level egress policy and evaluate a separate task-runner sidecar when it can be introduced without broadening the initial service.

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

Before Quadlet rendering, the adapter changes the existing bind root to mode
`0750` and recursively assigns that exact source to `podman-thelounge` without
changing descendant modes or replacing content. This ownership transition is
necessary so the rootless application process can retain and update the
existing configuration. Its `systemd.timeout_start_sec: 900s` setting allows a
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
