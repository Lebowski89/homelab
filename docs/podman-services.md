# Podman services and n8n

The shared service catalogue in `ansible/group_vars/all/services/*.yml` is runtime-aware. Entries without `runtime` continue to default to Docker for backwards compatibility. Entries with `runtime: podman` are selected by the same `skynet install|update|check|recreate|remove|drift <service>` interface and dispatched to `podman_services`.

## Runtime layers

1. `podman` installs and validates Podman 5.7+ on Ubuntu 26.04+ hosts tagged `podman`/`podman_install`.
2. `podman_services` renders rootful system Quadlets in `/etc/containers/systemd`, manages host paths, native Podman secrets, image pulls, systemd lifecycle, optional host-backed Traefik files, and optional PostgreSQL database declarations.
3. The shared catalogue selects Docker and Podman services together, then splits the selected items by runtime.

Rootful system Quadlets were chosen first because they are stable for boot-time services and fit the existing system-level Ansible model. Containers still run as non-root users through separate container UID/GID settings. Rootless user-systemd Quadlets can be added later by introducing a scoped Quadlet directory and user lingering management.

## Lifecycle semantics

- `deploy` and `bootstrap` fetch missing secrets, create missing Podman secrets, pull the declared image, render configuration, and start the service if it is not already running.
- `update` replaces configured mutable secrets and restarts the service when material inputs changed; because Podman cannot compare stored secret contents, update recreates/restarts when any mutable secret is declared. If a dedicated network Quadlet changed, the role stops the container, stops the generated network unit, checks `podman network exists <name>`, removes the named network only when it still exists, reloads systemd, and starts the container against the new Quadlet.
- `recreate` replaces configured mutable secrets and always restarts the generated service after rendering current inputs. Dedicated network Quadlet changes follow the same explicit stop/check/remove/reload/start path as `update`.
- `remove` stops the service, stops the generated network unit when present, explicitly removes a dedicated network only when `network.delete_on_stop: true` and `podman network exists <name>` succeeds, and removes generated Quadlets, environment files, and host-backed Traefik routing, but preserves application data and Podman secrets by default.
- `drift` inspects the current container image reference and reports a changed task when it differs from the declared exact image reference. It is reference drift, not registry digest drift.

Generated `.container` files include `[Install] WantedBy=multi-user.target`; the role does not call `systemctl enable` for generated Quadlet services.

For this initial version, any `network` mapping supplied to `podman_services` is treated as a role-managed dedicated network and must set `network.delete_on_stop: true`; validation rejects shared/external network mappings before rendering a Quadlet. `NetworkDeleteOnStop=true` is rendered only from that explicit setting and is appropriate for dedicated per-service networks such as n8n's network. Shared/external networks are not yet managed by this role, and the role must not stop, modify, or remove them. Future schema should add an explicit ownership field such as `ownership: dedicated`/`managed: true` versus `ownership: shared`/`external: true`, allowing services to reference an existing Podman network without owning its lifecycle.

## Secrets and PostgreSQL

Secret values are fetched with the repository-standard `infisical.vault.read_secrets` lookup parameters and the Infisical endpoint on the primary manager. Secrets are stored as native Podman secrets and mounted at `/run/secrets/<name>` with service-declared UID, GID, and mode; secret tasks are `no_log` and `diff: false`. Native Podman secrets keep values out of repository files and generated unit arguments, but the default file-backed secret driver is not encrypted storage and root on the host can access it.

The service schema distinguishes immutable secrets, such as the n8n encryption key, from replaceable secrets, such as the PostgreSQL password. Mutable secrets are replaced only during `update` and `recreate`. A normal `deploy` creates missing secrets without replacement so it cannot silently rotate a secret behind a running container.

`postgres.enable` and `postgres.databases` are declarations only for Podman services. The role deliberately does not create databases, modify PostgreSQL, run Docker database-management tasks, or invoke playbooks automatically. The existing Docker database-preparation task is still coupled to `docker_services` and only consumes Docker-selected service definitions, so `skynet deploy n8n`, `skynet install n8n`, and `podman_services` do not create the `n8n` database. A future refactor should extract the mature Docker PostgreSQL preparation into a small runtime-neutral explicit database/bootstrap action. Until then, create `n8n` before deployment with the existing shared PostgreSQL credentials, for example from an approved admin shell: `PGPASSWORD="$POSTGRES_PASS" createdb --host="$POSTGRES_HOST" --port="$POSTGRES_PORT" --username="$POSTGRES_USER" --owner="$POSTGRES_USER" n8n`.

## n8n

n8n runs on the dedicated `n8n` VM after it is rebuilt or upgraded to Ubuntu 26.04; this role intentionally rejects the current Ubuntu 24.04 VM. n8n is not in Docker Swarm. It uses the pinned official image `docker.io/n8nio/n8n:2.31.4`, stores local application data in `/opt/n8n`, uses PostgreSQL database `n8n` through the shared HAProxy endpoint IP from the primary manager inventory, and is routed privately at `https://n8n.<internal-zone>:8443/`.

The direct backend binds port `5678` to the VM management/LAN address via `host_ip: "{{ local_ip }}"`. That direct port remains reachable by systems on that network and bypasses Traefik TLS and middleware; binding to the LAN address is not firewall isolation.

Required private values before deployment:

- Add `n8n` to `terraform/netbox/private.auto.tfvars` with `192.168.80.98/24` and the real Tailscale IP.
- Create and back up a strong, stable `/N8N/ENCRYPTION_KEY` Infisical value before first launch.

During the first live start, verify `N8N_ENCRYPTION_KEY_FILE` with the selected n8n image without printing the secret. Check that `/run/secrets/n8n_encryption_key_secret` exists and is non-empty inside the container, inspect startup logs for missing-key or encryption-key errors, restart n8n, and confirm it starts successfully again. Never display the secret contents.

Back up the encryption key, PostgreSQL data, and `/opt/n8n`. n8n deliberately does not mount Docker/Podman sockets, host root, SSH keys, or unrelated directories.

Future hardening: add network-level egress policy and evaluate a separate task-runner sidecar when it can be introduced without broadening the initial service.
