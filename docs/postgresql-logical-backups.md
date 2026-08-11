# PostgreSQL logical backups

The PostgreSQL role installs the same host-resident logical-backup runner and
systemd job on every host in `tags_postgres`. Each invocation queries the
local Patroni REST endpoint at `127.0.0.1`: the node holding the leader lock
continues, a healthy replica logs a skip and exits successfully, and an
unavailable or unexpected Patroni response fails the job. Timers therefore do
not move during failover.

Patroni replicas provide high availability, not backups.

The optional remote layer copies only completed, checksum-verified backup trees
to a provider-neutral encrypted Restic repository. It is intentionally
disabled until a repository and its backend are selected. WAL archiving,
point-in-time recovery, physical base backups, and automated disposable restore
tests are deliberately deferred.

These local logical backups only become off-host protection when the separate
uploader copies them into the configured encrypted off-host backup repository.

## Configuration

The role defaults are:

| Variable | Default | Purpose |
| --- | --- | --- |
| `postgres_backup_root` | `/var/backups/postgresql` | Protected local backup root |
| `postgres_backup_script_path` | `/usr/local/sbin/postgres-logical-backup` | Installed runner |
| `postgres_backup_manage_timer` | `false` | Enable the timer lifecycle |
| `postgres_backup_timer_name` | `postgres-logical-backup` | Service and timer basename |
| `postgres_backup_timer_on_calendar` | `*-*-* 03:00:00` | systemd calendar |
| `postgres_backup_timer_randomized_delay_sec` | `30m` | Per-node scheduling jitter |
| `postgres_backup_local_retention_days` | `7` | Completed-backup retention |
| `postgres_backup_failed_retention_days` | `2` | Abandoned-staging retention |
| `postgres_backup_metrics_file` | `/var/lib/node_exporter/textfile_collector_postgres/postgres_logical_backup.prom` | Node Exporter metrics file |

The safe role default leaves scheduling disabled. This repository explicitly
sets `postgres_backup_manage_timer: true` in
`ansible/group_vars/tags_postgres.yml`, so all PostgreSQL inventory nodes
receive the enabled timer.

The setup creates the backup root as `postgres:postgres` with mode `0750`,
installs the runner as `root:root` with mode `0755`, and runs the oneshot
service as OS user and group `postgres`. PostgreSQL commands omit `-h` and
use the local Unix socket with peer authentication. No PostgreSQL password is
stored in the script or systemd unit.

## Provider-neutral encrypted remote backups

Local production and remote transfer are separate operations:

```text
local verified logical backup
          |
          v
completed backup + SUCCESS
          |
          v
checksum verification
          |
          v
Restic encrypted remote snapshot
          |
          v
remote retention
```

`postgres-logical-backup` remains PostgreSQL-specific and performs no network
operations. When remote management is enabled, the role installs Restic and a
separate root-run `postgres-logical-backup-remote` runner on every
`tags_postgres` host. Every node needs the uploader because a completed local
backup stays on whichever Patroni member was leader when it was created.

The remote capability is intentionally disabled until a repository/provider is
configured. Its main variables are:

| Variable | Default | Purpose |
| --- | --- | --- |
| `postgres_backup_remote_manage` | `false` | Install and configure the capability |
| `postgres_backup_remote_enabled` | `false` | Enable upload and maintenance timers |
| `postgres_backup_remote_repository` | empty | Provider-neutral Restic repository URL |
| `postgres_backup_remote_password_secret` | `/Restic/Postgres` / `PASSWORD` | Infisical repository-password declaration |
| `postgres_backup_remote_backend_environment` | `{}` | Non-secret backend environment |
| `postgres_backup_remote_backend_secrets` | `[]` | Infisical-backed environment declarations |
| `postgres_backup_remote_secret_files` | `[]` | Root-only Infisical-backed files |
| `postgres_backup_remote_options` | `[]` | Additional non-secret Restic argv elements |
| `postgres_backup_remote_retry_lock` | `10m` | Restic repository-lock retry duration |
| `postgres_backup_remote_maintenance_host` | first sorted PostgreSQL host | Sole maintenance scheduler |
| `postgres_backup_remote_snapshot_host` | `postgres_patroni_scope` | Cluster-stable snapshot host identity |
| `postgres_backup_remote_keep_daily` | `14` | Daily snapshots retained remotely |
| `postgres_backup_remote_keep_weekly` | `8` | Weekly snapshots retained remotely |
| `postgres_backup_remote_keep_monthly` | `12` | Monthly snapshots retained remotely |

`manage` controls package, configuration, runner, state, and unit management.
`enabled` controls scheduled network activity. A repository is not required
while both remain false, and this repository does not enable either variable in
`tags_postgres.yml`.

The role writes `/etc/restic/postgres-logical-backup` as `root:root 0700`.
The repository, password, backend environment, and optional backend secret
files are `root:root 0600`. The repository password and backend secrets are
looked up through
`hostvars[services_controller_host].infisical_lookup_default_params` on the
controller. They are never placed in the runner, a systemd unit, or command
arguments. The runner exports `RESTIC_REPOSITORY_FILE` and
`RESTIC_PASSWORD_FILE` and safely sources the protected backend environment.

Backend environment keys must be shell identifiers. Secret files must be
direct children of the protected Restic config directory and use mode `0600`.
Additional Restic options are individual array arguments, never a shell command
and never evaluated with `eval`; keep credentials in Infisical-backed
environment or files instead. Do not embed provider credentials in the
repository URL.

The role records only its declared provider secret-file paths in the root-only
`.managed-secret-files` manifest. When a provider configuration changes, files
that were previously recorded but are no longer declared are removed. Other
administrator-created files in the protected configuration directory are not
scanned or deleted.

### Upload eligibility and snapshot identity

The uploader considers only direct children of `postgres_backup_root` whose
names exactly match `YYYYMMDDTHHMMSSZ` and contain `SUCCESS`. It ignores
staging directories, lock/retention files, arbitrary names, and incomplete
backups. Before upload it runs `sha256sum --check SHA256SUMS` inside the
candidate. A checksum or Restic failure leaves the local backup untouched and
does not create an uploaded-state marker.

Each successful `restic backup` creates one snapshot and then atomically writes
a root-only marker under
`/var/lib/postgres-logical-backup-remote/uploaded/<repository-id>/<backup-id>`.
The namespace is Restic's unique repository ID from `restic cat config`, so
switching providers or recreating a repository at the same URL automatically
makes locally retained backups eligible for the new repository. Marker
directories for prior repositories are preserved. Missing markers retry on
later runs; existing markers skip duplicates for that repository. A separate
local flock prevents overlapping upload processes without changing metrics on
a clean overlap skip. Restic operations also use
`postgres_backup_remote_retry_lock: 10m` by default so short-lived shared
repository lock contention is retried by Restic itself.

Snapshots use the Patroni scope as their stable Restic host and carry these
tags:

- `postgres-logical-backup`
- `cluster=<patroni-scope>`
- `backup-id=<timestamp>`
- `source-member=<inventory-host>`

The source member is diagnostic only. Retention scopes to the stable host and
`postgres-logical-backup` tag, then groups by host so changing source paths and
leaders remain one logical cluster stream. This prevents maintenance from
touching unrelated snapshots if the repository is shared.

Upload timers are rendered on all PostgreSQL nodes. A separate Sunday
maintenance timer is rendered only on
`postgres_backup_remote_maintenance_host`; it applies 14 daily, 8 weekly, and
12 monthly retention by default and performs the repository prune. Upload runs
never call `forget` or `prune`.

### Activation workflow

The future administrator must provide the repository URL/server, create a
strong random Restic repository password in Infisical, add any provider
credentials to Infisical, and provide any safe provider options. Then:

1. Set `postgres_backup_remote_repository`.
2. Configure `postgres_backup_remote_backend_environment`, secret environment
   declarations, secret files, or non-secret options required by the backend.
3. Set `postgres_backup_remote_manage: true`.
4. Run `skynet run postgres backup-remote-setup`.
5. After independently confirming the destination, explicitly run
   `skynet run postgres backup-remote-init` once.
6. Run `skynet run postgres backup-remote-run` and inspect snapshots and
   metrics.
7. Set `postgres_backup_remote_enabled: true`, rerun setup, and verify both
   timers.

Normal role execution and setup never initialize, upload, forget, or prune.
All remote actions first probe `restic cat config`. Explicit initialization
runs `restic init` only when that probe returns the precise missing-repository
exit code `10`. An existing repository returns success; wrong-password exit
`12` and every connectivity/backend failure fail without initialization.
Upload and maintenance use the same probe but never initialize. Check-mode
variants render and validate configuration, substitute deterministic secret
stand-ins, and print the planned action without contacting Infisical or Restic.

### Conceptual backend examples

These examples use placeholders and do not recommend a provider.

Unconfigured safe state:

```yaml
postgres_backup_remote_manage: false
postgres_backup_remote_enabled: false
postgres_backup_remote_repository: ""
```

Conceptual SFTP state:

```yaml
postgres_backup_remote_repository: sftp:backup@example.invalid:/srv/restic/postgres
postgres_backup_remote_secret_files:
  - path: /etc/restic/postgres-logical-backup/backend-key
    infisical:
      path: /Restic/Postgres
      name: SFTP_PRIVATE_KEY
    mode: "0600"
postgres_backup_remote_options:
  - --option
  - sftp.command=ssh -i /etc/restic/postgres-logical-backup/backend-key
```

Before using SFTP, independently verify the server host key and install it in a
root-readable known-hosts file. Do not disable strict host-key checking and do
not automatically trust the first presented key.

Conceptual S3-compatible state:

```yaml
postgres_backup_remote_repository: s3:https://objects.example.invalid/backups/postgres
postgres_backup_remote_backend_environment:
  AWS_DEFAULT_REGION: example-region-1
postgres_backup_remote_backend_secrets:
  - env: AWS_ACCESS_KEY_ID
    path: /Restic/Postgres
    name: S3_ACCESS_KEY_ID
  - env: AWS_SECRET_ACCESS_KEY
    path: /Restic/Postgres
    name: S3_SECRET_ACCESS_KEY
```

No provider URL, account, credentials, or SSH host key is committed by this
phase.

## Backup contents and completion contract

At runtime, the leader queries `pg_database` and includes every database that
is connectable and is not a template. The retired Ansible
`postgres_backup_dbs` allowlist no longer controls either scheduled or manual
backups. Discovered names must match the runner's safe filename convention
(`A-Z`, `a-z`, digits, underscore, period, and hyphen); an unsafe name fails
the whole run rather than being interpolated into a path.

A completed backup has this layout:

```text
/var/backups/postgresql/
└── 20260811T013000Z/
    ├── databases/
    │   ├── gotify.dump
    │   └── postgres.dump
    ├── globals.sql
    ├── manifest.txt
    ├── SHA256SUMS
    └── SUCCESS
```

Each database is written with `pg_dump --format=custom` and immediately
checked with `pg_restore --list`. `pg_dumpall --globals-only` captures roles
and other cluster globals; treat `globals.sql` as sensitive because it can
contain password hashes. The manifest records timestamps, host/member,
PostgreSQL version, format, discovered database mapping, globals status, and
verification status. `SHA256SUMS` deterministically covers all dumps,
`globals.sql`, and `manifest.txt`.

Work remains in `.staging-<UTC timestamp>-<pid>` until every dump,
verification, globals capture, manifest, and checksum succeeds. Only then is
`SUCCESS` created and the directory renamed to its final UTC timestamp. A
failure exits non-zero and leaves identifiable staging data. The runner uses a
local `flock` file to prevent overlaps.

Only after promotion does retention consider direct children of
`postgres_backup_root` whose names exactly match the completed or staging
formats. Completed and abandoned staging directories use their separate
retention periods, so a failed pre-promotion backup cannot remove an older
completed backup.

## Metrics

Ansible creates a dedicated sibling metrics directory as
`postgres:postgres 0755` and pre-creates the configured file as
`postgres:postgres 0644`. The shared Node Exporter collector directory remains
owned by Node Exporter and is not made writable by `postgres`; Node Exporter
reads both directories through the configured textfile-directory glob. The
runner writes a complete temporary file in its dedicated directory and then
atomically renames it over the `.prom` file. It publishes these gauges:

- `postgres_backup_last_attempt_timestamp_seconds`: last leader attempt, also
  updated when the local Patroni endpoint fails.
- `postgres_backup_last_success_timestamp_seconds`: last fully promoted,
  verified backup.
- `postgres_backup_last_run_success`: `1` for the last completed leader
  attempt, `0` for a failed/in-progress leader attempt.
- `postgres_backup_last_duration_seconds`: duration of the latest leader
  attempt.
- `postgres_backup_last_size_bytes`: size of the latest successful backup.
- `postgres_backup_last_database_count`: database count in the latest
  successful backup.

A normal replica skip and a local overlap skip do not overwrite genuine backup
health. A failed metrics write is visible as a failed systemd invocation; it
cannot turn a failed database backup into a success.

The remote uploader atomically publishes a separate metrics file containing:

- `postgres_backup_remote_last_attempt_timestamp_seconds`: the latest
  non-overlap upload attempt.
- `postgres_backup_remote_last_success_timestamp_seconds`: the latest actual
  successful upload; a successful no-work run preserves it.
- `postgres_backup_remote_last_run_success`: whether the whole uploader run
  completed, including successful no-work runs.
- `postgres_backup_remote_last_duration_seconds`: duration of the latest run.
- `postgres_backup_remote_last_uploaded_count`: backups uploaded by that run.
- `postgres_backup_remote_pending_count`: eligible unmarked backups remaining
  after discovery at completion or failure. It is `0` if a preflight failure
  occurs before local eligibility can be counted.

Repository URLs, hostnames, backup IDs, and credentials are not metric labels.

## Setup, manual runs, and inspection

A normal full play configures the runner and timer but does not run an
immediate backup. The operation tags are:

- `postgres_backup_setup`: configure only.
- `postgres_backup_run`: configure, find the current Patroni leader, invoke
  its installed runner, wait, and report `POSTGRES_BACKUP_RESULT`.
- `postgres_backup`: compatibility alias for configure and run.

Equivalent wrapper commands are:

```bash
skynet run postgres backup-setup
skynet run postgres backup-run
skynet run postgres backup
```

Remote Restic operations use distinct tags and commands:

```bash
skynet run postgres backup-remote-setup
skynet run postgres backup-remote-init
skynet run postgres backup-remote-run
skynet run postgres backup-remote-maintenance
```

The corresponding raw tags are `postgres_backup_remote_setup`,
`postgres_backup_remote_init`, `postgres_backup_remote_run`, and
`postgres_backup_remote_maintenance`. Manual upload runs on all PostgreSQL
nodes; init and maintenance run only on the deterministic maintenance host.

In check mode, `skynet check postgres backup-run` configures and validates the
backup resources, then reports that it would discover the leader and invoke
the runner. It does not query Patroni or run a backup.

The runner repeats the local leader check even after Ansible selected a leader,
so a failover between discovery and execution cannot produce a backup on a
replica.

Inspect the schedule and logs on a PostgreSQL node with:

```bash
systemctl status postgres-logical-backup.timer
systemctl status postgres-logical-backup.service
journalctl -u postgres-logical-backup.service
```

The existing restore workflow accepts custom-format archives. For example, a
specific generated archive can be supplied as an absolute path:

```yaml
postgres_restore_dbs_map:
  - db: gotify
    file: /var/backups/postgresql/20260811T013000Z/databases/gotify.dump
```

Phase 3b.2 remains responsible for automated restore validation: disposable
PostgreSQL environments, restoring globals and databases, application-level
queries, periodic restore tests, and restore-success metrics are not included
here. WAL/PITR and physical backup mechanisms also remain separate future work.
