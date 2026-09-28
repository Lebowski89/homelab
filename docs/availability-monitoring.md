# Availability monitoring

Prometheus is the long-term source of availability state. During the Phase 1
migration, Uptime Kuma remains deployed so operators can compare both systems
before removing Kuma in a separate change.

## Sources of truth

- Private HTTP probes are derived from the enabled service catalogue entries
  that explicitly expose a private Traefik route. A small override map covers
  non-catalogue bootstrap routes, alternate paths, and direct host endpoints.
- ICMP and TCP host addresses come from NetBox-backed inventory `local_ip`
  values.
- PostgreSQL exporter targets come from the `tags_postgres` inventory group.
- Existing Technitium probes continue to cover five DNS endpoints over UDP and
  TCP.

Prometheus reads deterministic, secret-free files from
`/etc/prometheus/file_sd/`. Labels are limited to stable service, category,
probe, host, criticality, module, and migration monitor identifiers.

## Probe and alert behaviour

The private HTTP module accepts status codes 200 through 399, 401, and 403,
follows redirects, permits private/self-signed TLS, and times out after 30
seconds. Tautulli retains its strict `/status` 2xx/no-redirect probe; Plex and
Proxmox retain their direct host probes. ICMP uses IPv4 and the blackbox
exporter receives only `NET_RAW` for that purpose.

Dedicated alerts distinguish a blackbox exporter/job failure from a failed
target. Target alerts wait three minutes to approximate Kuma's retry intent.
TLS warnings begin below 21 days and become critical below seven days.
PostgreSQL exporter scrape failures and database query failures are separate
alerts.

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

## Phase 1 deployment order

Before deploying, create a dedicated Gotify application token in Infisical at
`/Gotify` as `ALERTMANAGER_APP_TOKEN`. The PostgreSQL exporter temporarily
reuses the existing Kuma database-monitor password while authenticating as the
neutral `postgres_monitor` role; no additional database secret is needed in
Phase 1.

Deploy the neutral database role, the native exporters, blackbox exporter,
Alertmanager, Prometheus, and Grafana in that order. Keep Kuma running until
the target sets, state transitions, email, Gotify firing/resolved delivery,
and the Homelab Availability dashboard have all been compared live.
