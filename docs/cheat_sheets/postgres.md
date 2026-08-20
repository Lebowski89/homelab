# PostgreSQL Patroni Cheat Sheet

This is a practical command cheat sheet for the Patroni + PostgreSQL cluster.

Assumptions:

- Patroni config: `/etc/patroni/config.yml`
- PostgreSQL port: `5432`
- Patroni REST API port: `8008`
- Admin role: `admin`
- Nodes:
  - `pg95`
  - `pg96`
  - `pg97`

---

## Patroni cluster status

### Show cluster state
```bash
sudo -u postgres patronictl -c /etc/patroni/config.yml list
```

### Show cluster JSON from the local node
```bash
curl http://127.0.0.1:8008/cluster
```

### Show local Patroni node status
```bash
curl http://127.0.0.1:8008/patroni
```

---

## PostgreSQL health checks

### Check whether PostgreSQL is listening locally
```bash
pg_isready -h 127.0.0.1 -p 5432
```

### Check whether the local node is leader or replica
Leader returns `f`, replica returns `t`.

```bash
sudo -u postgres psql -h 127.0.0.1 -d postgres -c "select pg_is_in_recovery();"
```

### Connect to PostgreSQL as admin
```bash
psql -h 127.0.0.1 -U admin -d postgres
```

### Connect to PostgreSQL as postgres superuser over TCP
```bash
psql -h 127.0.0.1 -U postgres -d postgres
```

### Connect as local postgres OS user via socket
```bash
sudo -u postgres psql -d postgres
```

---

## Basic psql inspection

### List databases
```sql
\l
```

### List roles
```sql
\du
```

### List tables in the current database
```sql
\dt
```

### Describe a table
```sql
\d table_name
```

### Show current server version
```sql
select version();
```

### Show current database
```sql
select current_database();
```

### Show current user
```sql
select current_user;
```

---

## Leader / replica verification

### Check leader node
Run on each node:
```bash
sudo -u postgres psql -h 127.0.0.1 -d postgres -c "select pg_is_in_recovery();"
```

Expected:

- leader: `f`
- replicas: `t`

### Check replication state from the leader
```bash
sudo -u postgres psql -h 127.0.0.1 -d postgres -c "select application_name, client_addr, state, sync_state, write_lag, flush_lag, replay_lag from pg_stat_replication;"
```

### Check WAL receiver state on a replica
```bash
sudo -u postgres psql -h 127.0.0.1 -d postgres -c "select status, sender_host, receive_start_lsn, written_lsn, flushed_lsn, latest_end_lsn from pg_stat_wal_receiver;"
```

---

## Test database creation and replication

### Create a test database
```bash
psql -h 127.0.0.1 -U admin -d postgres -c "CREATE DATABASE test_db;"
```

### Create a test table and insert rows
```bash
psql -h 127.0.0.1 -U admin -d test_db -c "CREATE TABLE test_items (id integer primary key, name text, created_at timestamptz default now());"
psql -h 127.0.0.1 -U admin -d test_db -c "INSERT INTO test_items (id, name) VALUES (1, 'alpha'), (2, 'bravo'), (3, 'charlie');"
psql -h 127.0.0.1 -U admin -d test_db -c "SELECT * FROM test_items ORDER BY id;"
```

### Check the restored or replicated data on a replica
```bash
psql -h 127.0.0.1 -U admin -d test_db -c "SELECT * FROM test_items ORDER BY id;"
```

### Drop the test database
```bash
psql -h 127.0.0.1 -U admin -d postgres -c "DROP DATABASE test_db;"
```

---

## Patroni switchover / failover

### Controlled switchover
```bash
sudo -u postgres patronictl -c /etc/patroni/config.yml switchover
```

### Check who is leader after switchover
```bash
sudo -u postgres patronictl -c /etc/patroni/config.yml list
```

### Stop Patroni on the current leader to force failover
```bash
sudo systemctl stop patroni
```

### Start Patroni again on that node
```bash
sudo systemctl start patroni
```

### Restart Patroni on a node
```bash
sudo systemctl restart patroni
```

### Check Patroni service logs
```bash
sudo journalctl -u patroni -n 200 --no-pager
```

### Follow Patroni logs live
```bash
sudo journalctl -u patroni -f
```

---

## etcd checks

### Bootstrap mode during node replacement

`postgres_etcd_initial_cluster_state` defaults to `new` for a fresh cluster or
full-cluster bootstrap. Set it to `existing` only as an explicit, temporary
host-scoped override for one replacement member joining surviving etcd members,
then remove the override after that replacement.

### Check etcd endpoint health
```bash
etcdctl --endpoints=http://192.168.80.95:2379,http://192.168.80.96:2379,http://192.168.80.97:2379 endpoint health
```

### Show etcd endpoint status
```bash
etcdctl --endpoints=http://192.168.80.95:2379,http://192.168.80.96:2379,http://192.168.80.97:2379 endpoint status -w table
```

### Show etcd member list
```bash
etcdctl --endpoints=http://192.168.80.95:2379,http://192.168.80.96:2379,http://192.168.80.97:2379 member list -w table
```

---

## Logical backup inspection

See [PostgreSQL logical backups](../postgresql-logical-backups.md) for the
architecture, completion contract, retention, metrics, and operation tags.

### Logical backup status and operations

Preview or configure the backup machinery, then run a backup on the current
Patroni leader:

```bash
skynet check postgres backup-setup
skynet run postgres backup-setup
skynet run postgres backup-run
```

Check the timer schedule and service state:

```bash
systemctl status postgres-logical-backup.timer
systemctl status postgres-logical-backup.service
systemctl list-timers --all postgres-logical-backup.timer
```

Inspect the service journal:

```bash
journalctl -u postgres-logical-backup.service
journalctl -u postgres-logical-backup.service -n 100 --no-pager
```

Inspect the Node Exporter textfile metrics:

```bash
sudo cat /var/lib/node_exporter/textfile_collector_postgres/postgres_logical_backup.prom
```

### List completed and staging backups

```bash
sudo ls -lah /var/backups/postgresql
```

### Inspect a completed backup

```bash
sudo ls -lah /var/backups/postgresql/YYYYMMDDTHHMMSSZ
sudo cat /var/backups/postgresql/YYYYMMDDTHHMMSSZ/manifest.txt
sudo test -f /var/backups/postgresql/YYYYMMDDTHHMMSSZ/SUCCESS \
  && echo "SUCCESS marker present"
```

### Verify payload checksums

```bash
cd /var/backups/postgresql/YYYYMMDDTHHMMSSZ
sudo sha256sum --check SHA256SUMS
```

### Inspect a custom-format dump

```bash
sudo -u postgres pg_restore --list \
  /var/backups/postgresql/YYYYMMDDTHHMMSSZ/databases/test_db.dump
```

---

## Quick validation checklist

### Cluster healthy
```bash
sudo -u postgres patronictl -c /etc/patroni/config.yml list
```

Expected:

- 1 leader
- 2 replicas
- replicas in `streaming`

### Local role check
```bash
sudo -u postgres psql -h 127.0.0.1 -d postgres -c "select pg_is_in_recovery();"
```

Expected:

- leader: `f`
- replicas: `t`

### Replication check on leader
```bash
sudo -u postgres psql -h 127.0.0.1 -d postgres -c "select application_name, client_addr, state from pg_stat_replication;"
```

### Replica WAL receiver check
```bash
sudo -u postgres psql -h 127.0.0.1 -d postgres -c "select status, sender_host from pg_stat_wal_receiver;"
```

---

## Notes

- Using `-h 127.0.0.1` forces TCP auth, so PostgreSQL may prompt for a password.
- If you want local socket auth as the `postgres` OS user, omit `-h 127.0.0.1`.
- `patronictl list` is your quickest cluster-health command.
- For normal operational restores, prefer per-database `.dump` files over `pg_dumpall`.