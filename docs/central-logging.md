# Central logging

Grafana is the user-facing log search interface and Loki is the private,
single-node log store. Loki uses TSDB v13 with filesystem storage and retains
seven days. Grafana reaches Loki directly at `http://loki:3100`; native agents
write through the private `loki.<internal-zone>` Traefik endpoint. Loki has no
public route or Authelia middleware.

Dozzle remains available as a fallback while this path is validated in normal
operation.

## Collection topology

Docker Swarm runs Alloy as a global Linux service. Each task reads only its
local read-only Docker socket, labels events with the Swarm node hostname from
`{{.Node.Hostname}}`, and sends them over the overlay to Loki. Docker keeps its
existing daemon-wide `json-file` policy. The collector also reads an explicit
allowlist of useful local application files through the read-only host-root
mount. Its positions and other state use a local Docker volume on each node.

The existing Alloy Unix and cAdvisor metric exporters remain enabled on every
collector. Their `instance` label is replaced with the same stable node
hostname and their jobs are separated as `alloy-unix` and `alloy-cadvisor`, so
globalizing the service does not create ambiguous node series.

Podman hosts run the package-managed native Alloy service. All managed rootful
and rootless Quadlets explicitly use `LogDriver=journald`. Native Alloy reads
the journal as the unprivileged `alloy` account through `adm` and
`systemd-journal` group membership. It never opens Podman sockets or user
runtime directories. This journal also includes useful non-container host
services, so journal streams deliberately do not receive a blanket
`runtime="podman"` label.

The one Podman file exception is JDownloader. Its useful Java output is
redirected by the image to `/config/logs/output.log`; native Alloy reads the
corresponding local appdata file under a narrowly scoped ACL on the `logs`
directory. It continues collecting the container and unit journal alongside
that distinct application stream.

## Labels

Docker stdout uses `host`, `container`, `service`, `runtime="docker"`,
`source="docker"`, and `job="docker"`. Swarm service metadata replaces the
per-task container name where available, keeping the indexed identity stable.

Journal streams use `host` and `source="journal"`. Alloy maps
`_SYSTEMD_UNIT`, `_SYSTEMD_USER_UNIT`, `SYSLOG_IDENTIFIER`, the priority
keyword, and Podman `CONTAINER_NAME` metadata to `unit`, `user_unit`,
`syslog_identifier`, `priority`, and `container` respectively.

File streams use `host`, `service`, `source="file"`, and `log_type`. Traefik
access JSON additionally promotes only the bounded router, upstream service,
and entrypoint fields. URLs, client addresses, headers, IDs, PIDs, filenames,
and message contents remain in the payload rather than the Loki index.

## Docker application file allowlist

Container paths below are resolved to their current host-backed service paths
and viewed inside Alloy beneath `/host/rootfs`. Exact active filenames avoid
compressed, backup, debug, trace, and unrelated log trees.

| Service | Container path | Host-side path or pattern | Format | Rotation owner |
| --- | --- | --- | --- | --- |
| Traefik access | `/etc/traefik/logs/access.log` | `/var/log/skynet/traefik/access.log` | JSON | existing host-managed file; verify reopen/rotation policy |
| qBittorrent alpha | `/config/log/qbittorrent.log` | `<storage-appdata>/qbittorrent-alpha/log/qbittorrent.log` | text | qBittorrent native, 5 MiB active limit with backup |
| qBittorrent bravo | `/config/log/qbittorrent.log` | `<storage-appdata>/qbittorrent-bravo/log/qbittorrent.log` | text | qBittorrent native, 5 MiB active limit with backup |
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
| NZBHydra2 | `/config/app/logs/nzbhydra2.log` | `<storage-appdata>/nzbhydra2/app/logs/nzbhydra2.log` | text | NZBHydra2 native rolling logs |
| NZBHydra2 wrapper | `/config/app/logs/wrapper.log` | `<storage-appdata>/nzbhydra2/app/logs/wrapper.log` | text | image/application native rolling logs |
| Plex | `/config/Library/Logs/Plex Media Server/Plex Media Server.log` | `<plex-appdata>/plex/Library/Logs/Plex Media Server/Plex Media Server.log` | text | Plex native rolling logs |
| Tautulli | `/config/logs/tautulli.log` | `<plex-appdata>/tautulli/logs/tautulli.log` | text | Tautulli native rolling logs |
| Kometa | `/config/logs/meta.log` | `<plex-appdata>/kometa/logs/meta.log` | text | Kometa run-based history |
| ImageMaid | `/config/logs/imagemaid.log` | `<plex-appdata>/imagemaid/logs/imagemaid.log` | text | ImageMaid native logging |
| Seerr | `/app/config/logs/seerr.log` | `<controller-appdata>/seerr/logs/seerr.log` | text | Seerr native rolling logs; compressed files excluded |
| UniFi | `/var/log/unifi/server.log` | `<controller-appdata>/unifi-os/var-log/unifi/server.log` | text | UniFi native rolling logs |
| Technitium | `/etc/dns/logs/*.log` | `<local-appdata>/technitium/logs/*.log` | text | Technitium application logging; query logging remains disabled |

All file discovery starts at the current end and ignores files older than 24
hours on first discovery. Persistent Alloy state prevents an agent restart from
replaying complete active files. Application-native rotation remains in place
where the application owns it; archive extensions are not matched. The current
repository does not prove a bounded reopen-safe policy for the Traefik access
file, Technitium log glob, or JDownloader `output.log`. Those three policies
require post-deployment verification; this change does not invent `copytruncate`
or an unsafe external rotation signal. qBittorrent was raised from roughly
65 KiB to 5 MiB because the prior active-file limit was too small for useful
local troubleshooting while its native backup behavior remains bounded.

Authelia is now stdout-only because its former file consumer was retired; its
Docker stream is collected once. Homepage is stdout-only, Uptime Kuma emits
JSON on stdout, and Unpackerr, Autobrr, Syncthing, Vaultwarden, Grafana, Gitea,
OpenCloud, Qui, Stash, and the other ordinary services remain on their runtime
stdout or journal paths to avoid duplicate events.

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
{service="jdownloader2", source="file", log_type="application"}
```

## Post-deployment acceptance

Run these checks only after an operator-approved deployment:

1. In Grafana Explore, run the queries above and confirm the expected physical
   `host` label. Compare one Docker service with Dozzle during the migration.
2. Inspect the global task placement with `docker service ps alloy_alloy` and
   confirm one running task on each intended Linux Swarm node.
3. On a Podman host, use `systemctl status alloy` and
   `journalctl -u alloy --since -10m`; confirm the service runs as its package
   account and reports no journal permission or Loki push errors.
4. Generate one normal request through Traefik, then query
   `{service="traefik", source="file", log_type="access"}`. Confirm the access
   event is separate from `{container="traefik", source="docker"}`.
5. Generate or observe new qBittorrent, one Servarr, Plex, Recyclarr, and
   JDownloader entries. Confirm each appears under the documented file labels
   without moving its application path.
6. Confirm a rootless user unit with
   `{source="journal", user_unit="thelounge.service"}` and a rootful Podman
   unit with its `unit` or `container` label. Verify no Podman socket is mounted
   or opened by Alloy.
7. During a maintenance window, restart one collector and verify old file
   contents are not replayed. Observe a normal native log rotation and verify
   Alloy follows the new active file without ingesting compressed archives.
8. After seven days, inspect Loki storage growth and confirm expected data ages
   out before considering removal of Dozzle.
