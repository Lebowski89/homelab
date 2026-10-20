# etcd quota and health monitoring

The accepted monitoring uses the existing Prometheus, blackbox exporter and
Alertmanager. Canonical Ansible source owns discovery, scrape configuration and
rules; private execution/rollback receipts remain outside Git. A source merge
or this guide does not authorize reloads, maintenance, compaction or deployment.

## Ownership and discovery

`availability_etcd_file_sd` generates `file_sd/etcd.json` from the existing
`tags_postgres` inventory group and each member's `local_ip`. The Prometheus
service templates install this discovery file and `rules/etcd.yml`; its main
configuration includes `etcd-scrape.yml.j2`. Retain all three pieces together so
a later configuration deployment does not drop accepted monitoring.

The `etcd` and `etcd-health` jobs scrape every 30 seconds with a 10-second timeout;
the rule group evaluates every 30 seconds. The health job uses the existing
blackbox `http_2xx` module and `prometheus_blackbox_exporter_address`, preserving
its protected worker publication for the migrated runtime. It checks `/health`
without alarm exclusions or `serializable=true`: NOSPACE/CORRUPT, missing leader
and failed linearizable reads remain failures. No test key is written.

## Escalation and trend rules

| Review | Trigger on any member |
| --- | --- |
| Same day | Allocated backend/quota at least 95%, or estimated time to 95% below 72 hours |
| Immediate | Allocated backend/quota at least 97%, estimated exhaustion below 24 hours, DCS health/leader failure, stale Patroni DCS, observed primary-role transition or missing required telemetry |

Quota uses backend **total allocation**, not filesystem fullness or SSD wear.
Keep in-use bytes and compact revision as separate observations. Forecasts use
the maximum nonnegative slope across 15-minute, one-hour and six-hour windows,
requiring at least 80% of expected samples per window. Warm-up is approximately
12 minutes, 48 minutes and 4.8 hours respectively. These are uncertain linear
estimates: bursts, allocation steps and missing samples limit them. Flat/negative
growth does not establish safety. Missing forecasts after a 20-minute warm-up
produce a warning; inspect trends daily and sooner when growth accelerates.

`EtcdMonitoringIncomplete` retains `for: 90s`, with no `keep_firing_for` extension.
Initial scheduling, a scrape timeout and the next evaluation can take up to
70 seconds; the 90-second persistence allows initialization while detecting
sustained gaps. The expression still rejects missing jobs, wrong member counts,
failed scrapes and missing quota/health metrics. Other DCS/quota incident rules
remain immediate. Patroni missing-series comparisons match `on(job, instance)`
so additional exporter labels do not create false failures.

Existing Alertmanager routing is unchanged: group wait is 30 seconds, group
interval five minutes, critical repeat one hour and warning repeat six hours.
These intervals and evaluation alignment affect delivery timing. A transition
wholly between scrapes can be missed. Counters establish sends, not human receipt.
Neither alerts nor forecasts authorize database or storage maintenance.

## Normal checks and recovery

Through the normal authenticated Prometheus UI, inspect:

```promql
up{job=~"etcd|etcd-health"}
probe_success{job="etcd-health"}
etcd_mvcc_db_total_size_in_bytes{job="etcd"} / etcd_server_quota_backend_bytes{job="etcd"}
etcd:backend_growth_conservative_bytes_per_second
ALERTS{alertname=~"Etcd.*|PatroniDCSStale|PatroniRoleChanged|PatroniImmediateHealthFailure"}
```

Require fresh successful scrapes for each expected inventory member and healthy
rule evaluations. Distinguish startup pending from firing and forecast warm-up
from lost telemetry. For incidents, inspect the actual alarm reason and Patroni
logs through separately authorized read-only operations; Prometheus does not
retain the full health response, alarm list or raft term. Do not silence or
weaken rules to make a qualification pass.

Render/check configuration and run the retained `tests/fixtures/etcd-monitoring.test.yml`
with the selected Prometheus version's `promtool test rules` before any approved
reload. Keep existing targets, labels, receiver routing and retention. Match
rollback configuration to its private receipt and stop on ownership/identity
changes. Do not replay transaction-specific payload paths from historical logs.

Deferred auto-compaction is a separate maintenance proposal. Neither this
monitoring change nor an ordinary PostgreSQL role run should enable it.
