# Availability monitoring

Prometheus is the source of truth for availability state. Blackbox Exporter
provides active HTTP, ICMP, TCP, and DNS probes; postgres_exporter provides
PostgreSQL queryability and replication metrics; Patroni metrics provide HA,
member-role, and streaming state; and Node Exporter provides host metrics.
Alertmanager routes alerts to email and Gotify, while the Grafana Homelab
Availability dashboard provides the operational view.

## Sources of truth

- Private HTTP probes are derived from the enabled service catalogue entries
  that explicitly expose a private Traefik route. A small override map covers
  non-catalogue bootstrap routes, alternate paths, and direct host endpoints.
- ICMP and TCP host addresses come from NetBox-backed inventory `local_ip`
  values.
- PostgreSQL exporter targets come from the `tags_postgres` inventory group.
- Patroni REST metrics targets come from the same `tags_postgres` inventory
  group and expose role, member state, streaming state, and WAL position.
- Existing Technitium probes continue to cover five DNS endpoints over UDP and
  TCP.

Prometheus reads deterministic, secret-free files from
`/etc/prometheus/file_sd/`. Labels are limited to stable service, category,
probe, host, criticality, module, and probe identifiers.

## Probe and alert behaviour

The private HTTP module accepts status codes 200 through 399, 401, and 403,
follows redirects, permits private/self-signed TLS, and times out after 30
seconds. Tautulli retains its strict `/status` 2xx/no-redirect probe; Plex and
Proxmox retain their direct host probes. ICMP uses IPv4 and the blackbox
exporter receives only `NET_RAW` for that purpose.

Dedicated alerts distinguish a blackbox exporter/job failure from a failed
target. Target alerts wait three minutes so transient failures do not page
immediately.
TLS warnings begin below 21 days and become critical below seven days.
PostgreSQL exporter scrape failures and database query failures are separate
alerts.

Replication-safety alerts join postgres_exporter slot metrics to Patroni's
current-primary metric by the stable inventory `host` label. This prevents the
inactive synchronized slot copies on standbys from producing false alerts.
Alerts cover sustained unhealthy member state, leader-reported replica lag,
missing/inactive expected physical slots, bounded WAL headroom, and
`unreserved`/`lost` slot WAL state. Existing Node Exporter filesystem alerts
remain the single disk-capacity signal. Host memory pressure uses
`MemAvailable` rather than free memory: warning fires below 20% available for 15
minutes and critical below 10% for 5 minutes. A critical
`increase(node_vmstat_oom_kill[5m]) > 0` alert reports actual kernel OOM kills on
any node-exporter host.

WAL-headroom alerts and the dashboard use PostgreSQL's directly exported
`safe_wal_size` value for physical slots. When PostgreSQL reports that value as
NULL, postgres_exporter omits the series; collector-failure monitoring remains
the separate signal for an unhealthy scrape.

Alertmanager keeps email delivery and also posts directly to Gotify. The
Gotify application token is read from the Docker secret
`alertmanager_gotify_token_secret`; it is never rendered into Alertmanager's
configuration.

## Privacy boundary

JDownloader2 and Mullvad Browser are not availability probe targets. Do not add
application-specific probes, metrics, request telemetry, destinations, URLs,
filenames, download names, or equivalent activity labels for the privacy
stack. The existing minimal systemd/journald lifecycle and VPN-connectivity
visibility remains the supported diagnostic boundary.

## PostgreSQL monitoring identity

The least-privilege `postgres_monitor` login is the sole application-neutral
PostgreSQL monitoring role. It inherits the built-in `pg_monitor` role and is
used by postgres_exporter against the `postgres` database. Its password is
stored only in the encrypted Ansible vault as `postgres_monitor_role_pass`.

The native exporter follows the [PostgreSQL host platform matrix](postgresql-platforms.md):
Debian 12/13, Ubuntu 22.04/24.04/26.04/26.10, Fedora 43/44 AMD64, and Rocky
9.7+/10.1+ within majors 9/10. Linux/systemd and the appropriate APT or DNF4/DNF5
backend are required; Atomic/OSTree and other derivatives fail before changes.
Fedora 45 remains outside this matrix until PostgreSQL's PGDG path supports it.
The existing [upstream archive](https://github.com/prometheus-community/postgres_exporter/releases/tag/v0.20.1),
version, SHA256 pin and AMD64 default are retained. No exporter repository is added.
An ARM64 host requires explicit `postgres_exporter_arch: arm64` and the matching
`postgres_exporter_checksum`; architecture mismatches and missing pins are rejected.
Release, mirror/download, account, path, database and listener overrides remain.
Unit/configuration paths must be absolute and contain no whitespace, quotes or
systemd specifiers; the password and environment files must be distinct.

Prerequisites are installed with `present`, using APT cache options only on APT.
RPM installs retain signature verification and require an interpreter with the
distribution DNF and SELinux bindings. SELinux keeps its current mode. Only the
managed executable receives an exact `bin_t` mapping and label restoration;
configuration and unit files use distribution default labels. This follows the
[distribution executable policy](https://github.com/fedora-selinux/selinux-policy/blob/rawhide/policy/modules/kernel/corecommands.fc)
and does not introduce a dedicated exporter confinement domain. No broad directory
relabel, SELinux boolean or firewall change is performed. The existing dedicated
account, protected credential files and hardened systemd unit are preserved.
Unchanged configuration does not request a restart or daemon reload.

On an existing PostgreSQL host with NetBox's `tags_postgres`, the existing command is:

```bash
skynet limit <postgres-host> run postgres-exporter install
```

`install`, `deploy` and `run` retain the same `postgres_admin_monitor,postgres_exporter`
selection: they reconcile the monitoring database identity before configuring the
exporter. This requires a configured, reachable Patroni cluster and existing vault
credentials; it is not a packages-only operation. The raw `postgres_exporter` tag
selects the exporter alone when the database identity has already been prepared.
Check mode validates platform and non-sensitive installation inputs, then reports
the plan without resolving/rendering credentials, downloading archives, preparing
accounts/files/labels, connecting to the database or changing service lifecycle.
It does not prove listener readiness, successful scrapes or SELinux access.
After an authorised live run, verify the selected listener's metrics and collector
health, inspect SELinux AVCs, and rerun to confirm convergence. Remote scrape
reachability remains the existing host firewall policy's responsibility.
