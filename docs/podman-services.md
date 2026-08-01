# Podman services and n8n

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
5. `podman_services` renders rootful system Quadlets in `/etc/containers/systemd` and retains native Podman secrets, image pulls, Quadlet validation, and systemd lifecycle.

Rootful system Quadlets were chosen first because they are stable for boot-time services and fit the existing system-level Ansible model. Containers still run as non-root users through separate container UID/GID settings. Rootless user-systemd Quadlets can be added later by introducing a scoped Quadlet directory and user lingering management.

## Lifecycle semantics

- `deploy` and `bootstrap` fetch missing secrets, create missing Podman secrets, pull the declared image, render configuration, and start the service if it is not already running.
- `update` reconciles secrets marked `update_policy: reconcile` and restarts the service when material inputs changed; because Podman cannot compare stored secret contents, a reconciled secret is recreated and triggers the existing restart path. An owned network remains in place through the restart. If its Quadlet definition changes, use an explicit remove followed by deploy when the network itself must be recreated.
- `recreate` reconciles secrets marked `update_policy: reconcile` and always restarts the generated service after rendering current inputs. It retains the service network.
- `remove` stops the service first, then stops and removes an owned network when it still exists. It removes generated Quadlets, environment files, and host-backed Traefik routing, but preserves application data and Podman secrets by default. Externally owned networks are never stopped, removed, or represented by a generated network Quadlet.
- `drift` inspects the current container image reference and reports a changed task when it differs from the declared exact image reference. It is reference drift, not registry digest drift.

Generated `.container` files include `[Install] WantedBy=multi-user.target`; the role does not call `systemctl enable` for generated Quadlet services.

Both adapters consume the top-level `named_networks` mapping. Podman currently
supports exactly one attached named network. `external: false` makes the role
responsible for its network Quadlet and explicit remove lifecycle;
`external: true` attaches the container directly to an existing network and
never creates or deletes it. `delete_on_stop` is not supported: ordinary
stops, updates, recreates, and systemd restarts retain an owned network.

Podman systemd policy is also first-class at top level. The supported fields are
`after`, `restart`, and `restart_sec`, rendered as `After=`, `Restart=`,
and `RestartSec=`. Service-level `runtime_options.podman.network` and
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

n8n is the first service migrated to the portable Docker-shaped schema. Its declaration uses top-level `image`, `user`, `environment`, `named_networks`, canonical ports/volumes/paths, `deploy`, `systemd`, health/security fields, canonical Infisical secrets, PostgreSQL, and Traefik. `runtime: podman` selects this adapter. Further Podman adoption remains incremental: migrate and validate one portable service at a time rather than changing the repository runtime wholesale.

n8n runs on the dedicated `n8n` VM after it is rebuilt or upgraded to Ubuntu 26.04. The selected host must already have the runtime required by the declaration: changing `runtime` to Docker is schema-valid for the tested portable subset but does not install Docker or establish live parity. The proof covers the trusted-address `host_ip` bind in both generated Docker standalone Compose and Podman Quadlet output. Static tests do not replace a live migration test.


The service uses pinned image `docker.io/n8nio/n8n:2.31.4`, UID/GID 1000:1000, application data in `/opt/n8n`, PostgreSQL database `n8n` through the shared HAProxy endpoint, and private routing at `https://n8n.int.<cloudflare-zone>:8443/`. The direct backend binds port 5678 to the VM management/LAN address; that direct port remains reachable on that network and bypasses Traefik TLS and middleware.

Its three canonical secrets preserve their lifecycle intent: the PostgreSQL username and n8n encryption key use the default `preserve` policy, while the PostgreSQL password uses `reconcile` during update/recreate. Shared preparation ensures the `n8n` database exists before the Podman service starts.


Required private values before deployment:

- Add `n8n` to `terraform/netbox/private.auto.tfvars` with `192.168.80.98/24` and the real Tailscale IP.
- Create and back up a strong, stable `/N8N/ENCRYPTION_KEY` Infisical value before first launch.

During the first live start, verify `N8N_ENCRYPTION_KEY_FILE` with the selected n8n image without printing the secret. Check that `/run/secrets/n8n_encryption_key_secret` exists and is non-empty inside the container, inspect startup logs for missing-key or encryption-key errors, restart n8n, and confirm it starts successfully again. Never display the secret contents.

Back up the encryption key, PostgreSQL data, and `/opt/n8n`. n8n deliberately does not mount Docker/Podman sockets, host root, SSH keys, or unrelated directories.

Future hardening: add network-level egress policy and evaluate a separate task-runner sidecar when it can be introduced without broadening the initial service.
