# PostgreSQL logical backups

The PostgreSQL role installs the same host-resident logical-backup runner and
systemd job on every host in `tags_postgres`. Each invocation queries the
local Patroni REST endpoint at `127.0.0.1`: the node holding the leader lock
continues, a healthy replica logs a skip and exits successfully, and an
unavailable or unexpected Patroni response fails the job. Timers therefore do
not move during failover.

Patroni replicas provide high availability, not backups.

These are local logical backups only. An encrypted off-host backup repository
is still required to protect against host, cluster, site, and administrative
failure. WAL archiving, point-in-time recovery, physical base backups, and
automated disposable restore tests are deliberately deferred.

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
| `postgres_backup_metrics_file` | `/var/lib/node_exporter/textfile_collector/postgres_logical_backup.prom` | Node Exporter metrics file |

The safe role default leaves scheduling disabled. This repository explicitly
sets `postgres_backup_manage_timer: true` in
`ansible/group_vars/tags_postgres.yml`, so all PostgreSQL inventory nodes
receive the enabled timer.

The setup creates the backup root as `postgres:postgres` with mode `0750`,
installs the runner as `root:root` with mode `0755`, and runs the oneshot
service as OS user and group `postgres`. PostgreSQL commands omit `-h` and
use the local Unix socket with peer authentication. No PostgreSQL password is
stored in the script or systemd unit.

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

Retention only considers direct children of `postgres_backup_root` whose
names exactly match the completed or staging formats. Completed and abandoned
staging directories use their separate retention periods.

## Metrics

Ansible pre-creates only the configured metrics file as
`postgres:postgres 0644`; the Node Exporter collector directory remains
`0755` and is not made writable by `postgres`. The runner overwrites that
single file with these gauges:

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

Selecting the latest backup automatically and proving full recovery in a
disposable restore environment remain follow-up work.
