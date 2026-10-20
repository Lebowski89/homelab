# Central logging

Grafana is the user-facing log search interface and Loki is the private,
single-node log store. Loki uses TSDB v13 with filesystem storage and retains
seven days. Grafana reaches Loki at its verified-TLS internal HTTPS route; native agents
write through the private `loki.<internal-zone>` Traefik endpoint. The rendered
Loki router uses only the private HTTPS entrypoint and the normal security,
no-index, HSTS, and compression middleware; it has no public route or Authelia
middleware.

## Collection topology

Docker Swarm runs Alloy as a global Linux service. Each task reads only its
local read-only Docker socket, labels events with the Swarm node hostname from
`{{.Node.Hostname}}`, and sends them to `https://loki.{{ services_internal_zone }}:{{ services_private_https_port }}/loki/api/v1/push`.
Remote write uses the corresponding Prometheus internal HTTPS route and `/api/v1/write`. The global service explicitly
excludes the mgt node and retains its `alloy` stack name. Docker keeps its
existing daemon-wide `json-file` policy. The collector also reads an explicit
allowlist of useful local application files through the read-only host-root
mount. Its positions and other state use a local Docker volume on each node.

Every global task receives the same declared file-target list, but Alloy filters
it before `local.file_match` by comparing each target’s inventory-derived owner
with `sys.env("ALLOY_HOST")`. Storage application paths are owned by
`services_storage_host`, Plex-side paths by `services_plex_host`, and controller
application and Traefik paths by `services_controller_host`. Primary and
secondary Technitium paths retain their respective controller and Plex owners.
A task therefore scans only paths owned by its physical node, while one rendered
configuration remains usable by the global service.

The existing Alloy Unix and cAdvisor metric exporters remain enabled on worker
Docker collectors. Their `instance` label is replaced with the same stable node
hostname and their jobs are separated as `alloy-unix` and `alloy-cadvisor`, so
globalizing the service does not create ambiguous node series.

Podman hosts run the package-managed native Alloy service. All managed rootful
and rootless Quadlets explicitly use `LogDriver=journald`. Native Alloy reads
the journal as the unprivileged `alloy` account through `adm` and
`systemd-journal` group membership. It never opens Podman sockets or user
runtime directories. This journal also includes useful non-container host
services, so journal streams deliberately do not receive a blanket
`runtime="podman"` label.

On mgt, these journal duties belong to the native package-managed Alloy agent.
The separate rootful `alloy-mgt` Quadlet reads the declared application files and
runs its selected host/container exporters using `alloy-mgt.alloy.j2`; it does
not replace the native journal collector. Worker Docker Alloy retains its local
Docker stdout/file/exporter responsibilities and excludes mgt. Keep both mgt
collectors and their separate state/configuration; their names alone do not make
either redundant.

Services in the Gluetun stack are treated as privacy-sensitive. JDownloader2
and Mullvad Browser continue writing their normal container output to the local
system journal, and native Alloy continues reading that journal. Before Loki,
Alloy drops container payloads for those two workloads; systemd unit lifecycle
records remain available for startup, shutdown, restart, and crash diagnosis.
Gluetun operational journal output remains available in Loki for VPN and
connectivity troubleshooting.
No application file sources, per-container metrics, request/traffic telemetry,
or activity-specific labels are configured for the stack.

JDownloader's `/config/logs/output.log` remains local and unchanged for manual
troubleshooting. Loki intentionally does not receive this file or every Java
application message, preventing download names, filenames, URLs, and equivalent
activity details from becoming centralized telemetry.

## Labels

Docker stdout uses `host`, `container`, `service`, `runtime="docker"`,
`source="docker"`, and `job="docker"`. Swarm service metadata replaces the
per-task container name where available, keeping the indexed identity stable.

Journal streams use `host` and `source="journal"`. Alloy maps the documented
journal metadata `_SYSTEMD_UNIT`, `_SYSTEMD_USER_UNIT`, `SYSLOG_IDENTIFIER`, and
`PRIORITY` keyword to `unit`, `user_unit`, `syslog_identifier`, and `priority`.
Podman's journald driver supplies `CONTAINER_NAME`, which Alloy exposes as
`__journal_container_name` and maps to `container`. The rootless lookup remains
based on `user_unit`.

File streams use `host`, `service`, `source="file"`, and `log_type`. Traefik
access JSON additionally promotes only the bounded router, upstream service,
and entrypoint fields. URLs, client addresses, headers, IDs, PIDs, and message
contents remain in the payload rather than the Loki index. Alloy automatically
adds a path-derived `filename` label to file targets; Worker Docker and mgt file pipelines
deliberately drop it before Loki. The service label already identifies fixed
files, while dropping it prevents daily Technitium filenames from creating an
avoidable label series.

## Application file allowlist

Container paths below are resolved to their current host-backed service paths
and viewed inside Alloy beneath `/host/rootfs`. Exact active filenames avoid
compressed, backup, debug, trace, and unrelated log trees.

| Service | Container path | Host-side path or pattern | Format | Rotation owner |
| --- | --- | --- | --- | --- |
| Traefik access | `/etc/traefik/logs/access.log` | `/var/log/skynet/traefik/access.log` | JSON | host logrotate: daily or 25 MiB, seven rotations/seven days |
| qBittorrent alpha | `/config/log/qbittorrent.log` | `<storage-appdata>/qbittorrent-alpha/log/qbittorrent.log` | text | qBittorrent: 5 MiB active file, backups older than one month removed |
| qBittorrent bravo | `/config/log/qbittorrent.log` | `<storage-appdata>/qbittorrent-bravo/log/qbittorrent.log` | text | qBittorrent: 5 MiB active file, backups older than one month removed |
| SABnzbd | `/config/logs/sabnzbd.log` | `<storage-appdata>/sabnzbd/logs/sabnzbd.log` | text | SABnzbd native, five 5 MiB backups |
| Radarr | `/config/logs/radarr.txt` | `<storage-appdata>/radarr/logs/radarr.txt` | text | Servarr native rolling logs |
| Radarr 4K | `/config/logs/radarr.txt` | `<storage-appdata>/radarr-4k/logs/radarr.txt` | text | Servarr native rolling logs |
| Sonarr | `/config/logs/sonarr.txt` | `<storage-appdata>/sonarr/logs/sonarr.txt` | text | Servarr native rolling logs |
| Sonarr 4K | `/config/logs/sonarr.txt` | `<storage-appdata>/sonarr-4k/logs/sonarr.txt` | text | Servarr native rolling logs |
| Lidarr | `/config/logs/lidarr.txt` | `<storage-appdata>/lidarr/logs/lidarr.txt` | text | Servarr native rolling logs |
| Prowlarr | `/config/logs/prowlarr.txt` | `<storage-appdata>/prowlarr/logs/prowlarr.txt` | text | Servarr native rolling logs |
| Whisparr | `/config/logs/whisparr.txt` | `<storage-appdata>/whisparr/logs/whisparr.txt` | text | Servarr native rolling logs |
| Bazarr | `/config/log/bazarr.log` | `<storage-appdata>/bazarr/log/bazarr.log` | text | Bazarr native rolling logs |
| Recyclarr | `/config/logs/debug.log` | `<storage-appdata>/recyclarr/logs/debug.log` | text | Recyclarr native rolling logs |
| NZBHydra2 | `/config/app/logs/nzbhydra2.log` | `<storage-appdata>/nzbhydra2/app/logs/nzbhydra2.log` | text | pinned Hotio/application rolling log |
| NZBHydra2 wrapper | `/config/app/logs/wrapper.log` | `<storage-appdata>/nzbhydra2/app/logs/wrapper.log` | text | pinned Hotio wrapper rolling log |
| Plex | `/config/Library/Application Support/Plex Media Server/Logs/Plex Media Server.log` | `<plex-appdata>/plex/Library/Application Support/Plex Media Server/Logs/Plex Media Server.log` | text | Plex native rolling logs |
| Tautulli | `/config/logs/tautulli.log` | `<plex-appdata>/tautulli/logs/tautulli.log` | text | Tautulli native rolling logs |
| Kometa | `/config/logs/meta.log` | `<plex-appdata>/kometa/logs/meta.log` | text | Kometa run-based history |
| ImageMaid | `/config/logs/imagemaid.log` | `<plex-appdata>/imagemaid/logs/imagemaid.log` | text | ImageMaid v1.2.0 logger |
| Seerr | `/app/config/logs/seerr.log` | `<controller-appdata>/seerr/logs/seerr.log` | text | stable active symlink to Seerr dated log; archives excluded |
| UniFi | `/var/log/unifi/server.log` | `<controller-appdata>/unifi-os/var-log/unifi/server.log` | text | selected active Network Server operational log |
| Technitium | `/etc/dns/logs/*.log` | `<local-appdata>/technitium/logs/*.log` | text | daily application logs; 30-day application default; query logging is not enabled |

The less-obvious selections were checked against the versions pinned by the
catalog: NZBHydra2 Hotio `release-v8.9.0` uses its `/config/app` data folder,
ImageMaid v1.2.0 creates `logs/imagemaid.log`, Seerr v3.4.1 maintains the
`seerr.log` active symlink, UniFi OS Server v1.7.0 persists `/var/log` with the
Network application at `unifi/server.log`, and Technitium 15.5 stores daily logs
under `/etc/dns/logs`. Technitium's query-log option remains disabled in the
repository; its `*.log` pattern excludes compressed archives and Alloy ignores
files older than 24 hours when first discovered. Existing persisted Technitium
settings should still be confirmed after deployment because image environment
defaults do not override an already-created DNS configuration.

Traefik uses rename/create rotation rather than `copytruncate`. The policy
recreates the active file as mode `0640`, keeps at most seven rotations/seven
days and compresses older rotations. File ownership follows the selected runtime:
the dedicated execution account owns rootless Traefik logs; rootful/Docker
execution retains root ownership. The reopen helper uses the same resolved
account, home and runtime directory for rootless Podman and signals only the
managed Traefik container with `SIGUSR1`. Rootful Podman uses its system runtime.
The retained Docker path selects exactly one local running container by
`com.docker.swarm.service.name=traefik_traefik` and rejects zero/multiple matches.
The signal reopens logs; it does not restart Traefik. Alloy matches only
`access.log`, never rotated or compressed names.

All file discovery starts at the current end and ignores files older than 24
hours on first discovery. Once a target has a saved position, persistent Alloy
state resumes from it after restart. If a positions file is corrupt, Alloy uses
`restart_from_end`, avoiding a large replay at the cost of potentially skipping
unread content. During rename/create rotation Alloy can finish the renamed file
and discover the new active filename; archives are not configured as targets.

qBittorrent retains its native bounded policy: the active file rotates at 5 MiB,
backup logging and old-file deletion remain enabled, and month-based age `1`
removes backups older than one month.

Authelia is stdout-only because the repository has no remaining consumer of its
former duplicate file and no CrowdSec service. Rootless Authelia stdout is
collected once through journald; retained Docker instances use their Docker
stdout collector. Homepage is stdout-only, and Unpackerr, Autobrr, Syncthing, Vaultwarden,
Grafana, OpenCloud, Qui, Stash, and the
other ordinary services remain on their runtime stdout or journal paths to
avoid duplicate events.

Forgejo is stdout-only inside its rootless Podman container. Its managed user
Quadlet uses journald, and native Alloy collects it under
`{source="journal", user_unit="forgejo.service"}` without a dedicated file
target or Docker collector integration.

## LogQL examples

```logql
{runtime="docker"}
{runtime="docker", host="unraid"}
{container="traefik"}
{source="journal", host="blacktop"}
{source="journal", user_unit="thelounge.service"}
{source="journal"} |= "error"
{service="traefik", source="file", log_type="access"}
{service="qbittorrent-alpha", source="file"}
```

## Post-deployment acceptance

Run these checks only after an operator-approved deployment:

1. In Grafana Explore, run the queries above and confirm the expected physical
   `host` label.
2. Inspect the global task placement with `docker service ps alloy_alloy` and
   confirm one running task on each intended Linux Swarm node.
3. On a Podman host, confirm native Alloy runs as its package account and has no
   journal permission or Loki push errors. Verify both a rootless `user_unit`
   and a rootful systemd `unit` label, without opening a Podman socket. Confirm
   JDownloader2 and Mullvad Browser container payloads are absent from Loki
   while their unit lifecycle events and Gluetun VPN-connectivity events remain.
4. Generate one normal request through Traefik and confirm it appears in the
   access file stream separately from Traefik's Docker stream. Force a test
   rotation in a maintenance window; confirm exactly one Traefik task receives
   `SIGUSR1`, the new `access.log` is populated, and Alloy follows it without
   ingesting rotated or compressed files.
5. Generate or observe qBittorrent, one Servarr, Plex, Recyclarr, ImageMaid,
   Seerr, UniFi, and Technitium entries. Confirm each appears under the
   documented file labels and that no `filename` label reaches Loki.
6. Confirm Technitium query logging remains disabled and its persisted
   `maxLogFileDays` is bounded as expected. Confirm the privacy stack has no
   workload-specific file ingestion, metrics, traffic telemetry, or activity
   labels.
7. Restart one collector and verify saved positions resume without replaying old
   file contents. Observe a normal native log rotation and verify Alloy follows
   the new active file without ingesting compressed archives.
8. After seven days, inspect Loki storage growth and confirm expected data ages
   out.

## mgt file and host collector

The rootful `alloy-mgt.service` Quadlet has a bind-backed checkpoint tree at
`<controller-appdata>/alloy/data`. It preserves owner-filtered file collection,
redaction, labels and Unix metrics. It has no Docker socket/storage, Docker
discovery, cAdvisor or journal source. The distinct native `alloy.service` keeps
journal ownership and filtering; node-exporter monitoring is unchanged.
The collector's private UI route remains `alloy.<internal-zone>` while its
container/unit name is `alloy-mgt`. Its clients use the same internal HTTPS URLs as worker/native agents.
The existing private machine routes have no interactive SSO middleware;
certificate verification and the ingress access policy remain enabled. For a checkpoint transfer, stop the selected collector first and use its
observed mountpoint and a consistent preserved copy, following the
[ownership procedure](../migrator/guides/ownership.md). Keep component names and
storage paths stable where supported; verify ingestion because runtime changes
can replay files or introduce a metric discontinuity.
Traefik logrotate addresses only the exact `traefik` Podman container; the
legacy Docker helper still selects one exact Swarm service task.
