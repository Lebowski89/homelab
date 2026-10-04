# Service secret delivery audit

This audit follows repository code and public upstream sources. It does not
inspect deployed containers, retrieve Infisical values or verify live host
versions. The repository requires Podman 5.4.2+; its installed collection
supports account-scoped native secrets and content comparison at that baseline.

## Resolution and transport

Both adapters receive current-service declarations and values from
`service_common/tasks/infisical.yml`. Its `infisical.vault.read_secrets` lookup
uses the declared path/name and configured controller. Lookup, resolution and
value handoff use `no_log: true` and `diff: false`; check mode substitutes
deterministic synthetic values without contacting Infisical. Adapters reset
their per-service state and never infer credentials from another application.

An entry's `secret.name` requests runtime materialization and attachment;
`value_from.infisical` instead requests direct environment injection. A lookup
alone requests neither. These mechanisms are distinct even when the source is
the same Infisical entry.

The adapter has no separate `LoadCredential=`/`SetCredential=` or encrypted
systemd-credential path. Managed application templates can also persist resolved
values, as Homepage does; native-secret delivery does not change those files.

| Delivery | Generated configuration | Runtime and disk exposure |
| --- | --- | --- |
| Docker Swarm native secret | Compose references an external secret and its container target; no secret value is embedded by this mechanism. | Docker receives the value through its API, persists encrypted Swarm state and mounts a secret file, normally beneath `/run/secrets`. Runtime inspection exposes attachment metadata, not contents. Authorized container processes can read the file. |
| Standalone Docker secret fallback | Compose renders a read-only bind path. | Adapter writes plaintext under `/opt/stacks/<stack>/secrets`, directory `0700`, file mode `0400` by default with configured runtime ownership. Host backups and privileged readers can access it. |
| Podman `value_from.infisical` | `.container` references an execution-account-owned `0600` `.env` file. | The file contains plaintext. Quadlet converts `[Container] EnvironmentFile=` to `--env-file PATH`, not systemd environment injection. Container environment/configuration metadata contains the value, retrievable through `podman inspect` and by permitted process-environment readers. |
| Podman native `secret` | Quadlet `Secret=` and application file paths contain names/metadata only. | Module sends data on stdin to `podman secret create NAME -` in the execution account's store. Default local storage is unencrypted/recoverable by that account or host root. Mounted files default to `0400` and container UID/GID; ordinary container inspection shows references, not file contents. `podman secret inspect --showsecret` can retrieve them. |

The Podman `.container` file is `0644` within a `0700` rootless Quadlet directory.
It does not embed resolved environment values. Generated unit command lines
contain `--env-file PATH` or secret references, not values; the role does not
import application credentials into the systemd manager environment. Ordinary
argument-only process listings therefore do not reveal them. Environment-aware
inspection can reveal environment-delivered values. Podman's local secret
store and container-mounted copies remain sensitive disk material.

Ansible suppresses value-carrying tasks and diffs. Journald is not intentionally
given credentials: it records application console output. Application logging,
crash dumps, debug tooling and image initialization can still expose or persist
values. Neither file delivery nor Infisical makes a compromised application or
privileged host safe to hold secrets.

## Docker application consumption

Lidarr, Radarr, Sonarr and Prowlarr declare `/Postgres/USER` and `/Postgres/PASS`
with native-secret metadata. Their `FILE__...` environment variables contain
`/run/secrets/postgres_user_secret` and `/run/secrets/postgres_pass_secret`,
not values. Grafana similarly uses its image's file-reading mechanism. The
adapter attaches files; application/image initialization owns consumption and
may copy contents into its own configuration or process environment. This
audit does not claim Docker secret delivery prevents such application behavior.

The Docker helper preserves immutable-secret replacement protections; no Docker
adapter behavior was changed. Direct environment injection is available for
Docker too and retains its broader exposure model.

## Rootless Podman changes

Native secret creation already switches to the selected execution account with
its HOME/XDG/user-manager context; Quadlet `Secret=` and user-service restart
were already implemented. The rootless normalization prohibition was removed
without adding a second schema, manual Quadlets, systemd credentials or wrapper
scripts. File and environment mechanisms remain distinct, as documented in
[Podman services](podman-services.md#secrets-and-postgresql).

`preserve` keeps existing secrets; `reconcile` compares/replaces on update or
recreate. At the supported baseline the installed `podman_secret` module uses
`inspect --showsecret` internally under `no_log`, compares contents and reports
changes. Unchanged reconciliation alone now leaves the selected service running;
changed secrets restart/replace it so its container receives new mounted data.
Explicit recreate still restarts. Unrelated services are not selected. Check
mode never creates secrets or invokes a runtime. Removal keeps native secrets
with application data/user storage, following the existing retention contract;
obsolete secret retirement remains an explicit operator action.

Forgejo uses the shared PostgreSQL sources but retains its `forgejo` database.
Its username uses the image's `USER__FILE` conversion and is written to
`app.ini`. Password, `SECRET_KEY` and `INTERNAL_TOKEN` use Forgejo's native
file URI settings, keeping those contents out of generated environment files
and persistent direct configuration keys. The dedicated cryptographic sources
remain `/Forgejo/SECRET_KEY` and `/Forgejo/INTERNAL_TOKEN`, with preserve policy.
See [Forgejo](forgejo.md) for deployment and existing-state prerequisites.

## Other consumers and deferred work

Among current effective Podman services, Gluetun is the other direct
`value_from.infisical` consumer: `/PIA/USER` and `/PIA/PASS` become
`OPENVPN_USER` and `OPENVPN_PASSWORD` in its protected rootful environment file
and container metadata. Review migration to its supported
`OPENVPN_USER_SECRETFILE` / `OPENVPN_PASSWORD_SECRETFILE` inputs separately;
its current behavior was preserved. Gluetun unsets sensitive process environment
values after loading them, but that does not remove the adapter's environment
file or Podman's stored container metadata. See its
[native secret documentation](https://github.com/qdm12/gluetun-wiki/blob/main/setup/advanced/docker-secrets.md).
Autobrr also uses typed
Infisical environment values, but remains a Docker service. Homepage uses
Infisical values in managed application templates, a separate disk exposure
path; audit/backup those files as sensitive. Adminer, The Lounge, JDownloader2
and Mullvad Browser currently declare no Infisical environment credentials.

Live Podman versions, generated units, file ownership and redacted container
inspection remain operator validation steps. No live inspection was performed.

## Upstream references

- [Podman 5.4.2 Quadlet environment files and secrets](https://docs.podman.io/en/v5.4.2/markdown/podman-systemd.unit.5.html)
- [Podman 5.4.2 native secret creation](https://docs.podman.io/en/v5.4.2/markdown/podman-secret-create.1.html)
- [Docker Swarm secret storage and consumption](https://docs.docker.com/engine/swarm/secrets/)
- [Forgejo 15 file URI settings](https://forgejo.org/docs/v15.0/admin/config-cheat-sheet/)
- [Forgejo 15.0.9 environment-to-configuration implementation](https://codeberg.org/forgejo/forgejo/src/tag/v15.0.9/modules/setting/config_env.go)
- [Forgejo 15.0.9 secret reader](https://codeberg.org/forgejo/forgejo/src/tag/v15.0.9/modules/setting/security.go)
