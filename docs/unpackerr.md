# Unpackerr

Unpackerr remains one Docker Swarm replica on the storage host. Its upstream
image is version/digest pinned; the process uses that host's inventory UID:GID.
`/data` and both completed-download paths are unchanged. Do not chown downloads
or start a second extraction writer when maintaining this service.

`<storage-appdata>/unpackerr` is mounted read/write at `/config`. Ansible seeds
`unpackerr.conf` only when absent (`force: false`); the UI owns subsequent saves.
The directory/file are owned by the process user, modes `0750`/`0600`.
Infisical and Docker remain credential owners: preserve every `filepath:` secret
reference when editing settings. Whisparr is a named Radarr instance. Removed
`UN_*`/Hotio `FILE__*` overrides must not be reintroduced, or UI fields become
locked. Extracted file/directory modes are `0644`/`0755`; Hotio's unsupported
`UMASK` environment variable is gone. Verify the inherited process umask during
runtime acceptance rather than introducing an entrypoint wrapper.

The UI uses the normal private HTTPS route and host publication `22624 -> 5656`.
Only Traefik is declared as its backend caller. Proxy trust is the controller's
inventory address, matching the verified worker source path; it is not the old
overlay subnet. Normal Traefik HTTP routing supports WebSocket upgrade requests.
The Technitium record is owned by `terraform/technitium/internal-dns`; apply that
single DNS declaration through its existing owner before browser acceptance.

No Unpackerr target was present in the running Prometheus target list at
migration, and no repository scrape exists. Metrics remain disabled. A future
scrape requires an API key with `system:metrics:read` and protected delivery of
that key; do not enable an unauthenticated scrape. Application logs remain on
stdout, without a duplicate file collector.

## Operator acceptance

Open `https://unpackerr.<internal-zone>:<private-https-port>/`. On a **private
root console on Unraid**, retrieve the migration's bootstrap password without posting it
to chat/logs:

```sh
cat /mnt/user/appdata/.unpackerr-migration-20261028T150455Z/ui-bootstrap-password.txt
```

The first deployment attempt was contained after a firewall end-audit failure.
Because its first-start password log could disappear with that container, the
official `--reset` was run while the service was proved stopped, as the process
UID:GID, with only `/config` mounted and no network or downloads. It exits before
the extraction loop. Its output is retained only in that root-owned `0600` file.

Log in as `admin`, change the bootstrap password, and Save. Confirm the settings
remain after a browser reload. Keep any generated API key private; none is needed
for the current disabled metrics configuration. Do not disable application auth.

In one acceptance session:

1. Test Lidarr, both Radarr instances, both Sonarr instances and Whisparr using
   their UI Test buttons. Confirm their private HTTPS URLs and download paths.
2. Save a harmless setting, reload and confirm it persists. At the next planned
   Unpackerr-only recreate, verify it still persists and was not reseeded.
3. Observe the live queue over its authenticated WebSocket connection.
4. Allow one normal completed download to extract; confirm the importing app
   sees the result and configured file/directory permissions are appropriate.
5. If the Notifiarr hook is enabled, verify the corresponding delivery. Do not
   launch another Unpackerr process to manufacture the event.

## Scoped rollback

The migration preserves a root-only backup on mgt under
`/opt/stacks/.unpackerr-migration-20261028T150455Z` and on Unraid under
`/mnt/user/appdata/.unpackerr-migration-20261028T150455Z`. These include the old
stack/spec/declaration, original config-volume archive and retired image archive.
The original anonymous config volume is retained; its configuration is also
preserved as `legacy-hotio-unpackerr.conf` in the new appdata directory. No history
file existed in that volume at inspection. Keep all backup material.

If rollback is needed, keep the migration declaration in place while running
`skynet remove unpackerr`, so scoped removal can retire its selected publication
and reservation. Stop if ownership/protection checks fail. Only after successful
removal, restore **only** the Unpackerr declaration from the manager backup's
`unpackerr-rollback.yml`, then run `skynet deploy unpackerr`. That rollback input
pins the saved Hotio image and explicitly reattaches the retained anonymous
volume. Preserve the new appdata for later recovery; never restore a whole saved
firewall policy. Image-archive restoration is a fallback if the retained local
image is lost and must be checked before starting rollback. This rollback has
been prepared, not exercised against production.

References: [v1 upgrade](https://unpackerr.zip/docs/install/upgrading/),
[v1.0.0 release](https://github.com/Unpackerr/unpackerr/releases/tag/v1.0.0),
[Web UI](https://unpackerr.zip/docs/install/web-ui/),
[tagged example configuration](https://github.com/Unpackerr/unpackerr/blob/v1.0.0/examples/unpackerr.conf.example).

## Migration verification, 29 October 2026

The first scoped deploy failed at the ending installed-firewall audit after its
TCP probe succeeded. Containment proved the selected writer stopped, retained
protection and released the reservation. A read-only audit then passed in both
families. The original failure is retained in
`/tmp/homelab-unpackerr-deploy-output.log`; its precise transient cause was not
established. No shared lifecycle/firewall code or guard was changed or bypassed.
One ordinary Unpackerr-only deploy retry then passed, including probes, owned
counter increases and the final transaction (`pending=false`, no failure flags).

Read-only verification confirmed the pinned v1 image, one replica, unchanged
Unraid constraint and `/data`, UID:GID `99:100`, umask `0022`, writable `0600`
configuration, readable `0400` secret mounts and unchanged Docker secret IDs.
All seven file references survived startup and the stopped-service password
reset. No superseded environment keys remain. The observed backend peer was
`::ffff:192.168.80.48`, the IPv4-mapped representation of the configured controller
address. Private DNS resolves correctly; HTTPS verifies normally and returns 200.
Unauthenticated API and WebSocket requests return 401. Authenticated WebSocket
behaviour remains part of operator acceptance above.

The worker audit passes for IPv4 and IPv6 and its reconciler is running. Only
port 22624 and Unpackerr's own record were added; unrelated worker records, source
boundary and mgt policy match the saved baseline. Eight saved Arr service
identities/spec versions are unchanged; the two additional 4K Arr services have
not been updated since before migration. The original anonymous volume/config
and private backups remain. `/metrics` currently falls through to the HTML UI
(200 `text/html`), not a Prometheus endpoint; no scrape was added. Notifiarr
delivery and a real completed-download extraction have not been accepted yet.

Repository checks: 57 focused endpoint/catalogue/style tests and 2 existing
create-only-template/real-planner checks passed. The real Docker Compose tasks
rendered with synthetic host IDs and declarations; user, all seven secret mount
owners/modes, one replica, stop-first ordering, constraints, paths and ports were
checked. TOML rendered and parsed with synthetic lookup values. Affected Ansible
lint, localhost-only syntax, Ruff check/format, OpenTofu formatting and whitespace
checks passed. `skynet check unpackerr` passed before execution. No tools were
installed, no provider/state operation was run by the implementation agent, and
nothing was staged, committed or pushed. DNS apply was performed by the operator.
