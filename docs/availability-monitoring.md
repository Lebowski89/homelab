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
remain the single disk-capacity signal.

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
