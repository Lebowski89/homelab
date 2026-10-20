# Operational helpers

This directory contains executable Python/shell source and native operator slice
definitions, not Ansible task lists or saved migration outcomes. Nothing here
runs automatically. Live use still requires the authorization and guards in the
repository instructions.

| Helpers | Retained purpose |
| --- | --- |
| `utility-preparation.py`, `znc-mapping-proof.py` | Runtime projection, numeric namespace mapping, exact-path ownership and archive verification for explicitly supported services |
| `backup-storage-watchdog.py` | Progress-aware storage observation with independent operation limits |
| `haproxy-cutover.py`, `haproxy-cutover-batch.sh` | Guarded caller/policy transitions, bounded route evidence and scoped recovery; inspect the recorded stage before use |
| `haproxy-address-snapshot.*`, `haproxy-negative-acceptance.sh` | Source/route classification and owned-counter firewall acceptance; distinguish temporary listeners from actual-service testing |
| `mgt-operator.py`, `prepare-native-operator.sh`, `skynet_pg_*.slice`, `haproxy-policy-rollback.sh` | Persistent scoped PostgreSQL preparation/recovery contexts and restoration of the complete saved policy union |
| `alertmanager-delivery-diagnostic.py` | Sanitized receiver/payload/delivery diagnostics |
| `netbox-config-destinations.py` | Allowlisted destination inspection and guarded replacement without copying complete secret-bearing configuration |

These paths remain stable because retained offline rollback recipes import them,
and shared helpers import one another. Moving them requires a separately tested
compatibility change; they are not redundant record keeping. The reusable
[migrator workspace](../../migrator/README.md) uses this toolkit rather than a
second deployment engine. Runtime ownership remains in the existing roles.

The completed Romm socket diagnostic (`romm-socket-diagnostic.py` and `.sh`) and
ZNC-only preparation launcher (`znc-preparation.sh`) have been archived with their
dedicated tests under `/opt/ansible/migration/`. Their absence does not remove the
shared numeric mapping or ownership machinery. Historical plans/logs/outcomes
also belong outside the repository.
