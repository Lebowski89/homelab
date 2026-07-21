# Ansible role: podman_services

Reusable system-level Podman Quadlet service role for Podman 5.7+ rootful system Quadlets. It consumes the shared service catalogue entries with `runtime: podman` while Docker remains the default for entries without a runtime.

Supported schema includes exact image tags, `.container` and optional dedicated `.network`/`.volume` rendering under `/etc/containers/systemd`, bind mounts, protected non-secret env files, Podman secrets sourced from Infisical, capability drops, native `NoNewPrivileges=true`, health checks, lifecycle actions, private Traefik host backends, and PostgreSQL database declarations. Managed network mappings are dedicated-only in this initial version and must set `network.delete_on_stop: true`; shared/external network references are future schema work and are not stopped, modified, or removed by this role.

Secrets are mounted as native Podman secrets under `/run/secrets/<name>` with service-declared UID, GID, and mode. Secret tasks use `no_log` and are skipped in Ansible check mode. Remove and recreate preserve app data and secrets by default. PostgreSQL database creation is not performed by this role.

Limitations: this first version intentionally manages single-host rootful/system Quadlets only; Swarm-only concepts and rootless user Quadlets are future extensions.
