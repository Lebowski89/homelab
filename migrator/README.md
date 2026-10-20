# Docker to Podman migrator

Reusable workspace for future service migrations. Completed handoffs and
acceptance records are kept outside Git under `/opt/ansible/migration/`. This
directory organizes new batches using the [current Podman operations guide](../docs/podman-services.md),
without replaying an old cutover or moving helpers that retained rollback recipes import.

`migrate.py` creates private draft workspaces, seals exact plans/recipes and
verifies their checksums. These three operations are offline: no inventory API,
secret lookup, runtime query, probe, deployment or acknowledgement promotion.
There is deliberately no generic `execute all` command. A reviewed batch uses
its exact scoped recipes and the existing Ansible runtime adapters.

## Start a batch

Prepare the intended canonical declaration locally, retaining one definition
and explicit targets. Start a workspace with exact service identities. This
example creates a draft for Radarr only; it does not migrate or inspect Radarr:

```bash
(
  set -euo pipefail
  umask 077
  cd /opt/homelab
  root="$(mktemp -d /opt/ansible/.secrets/migrator.XXXXXX)"
  log="$root/operator.log"
  printf 'Private evidence root: %s\nPrivate log: %s\n' "$root" "$log"
  set +e
  /opt/ansible/ansible-venv/bin/python migrator/migrate.py init \
    --name radarr-example --service radarr:radarr --evidence-root "$root" \
    2>&1 | tee -a "$log"
  statuses=("${PIPESTATUS[@]}")
  status=${statuses[0]}
  if [[ "$status" == 0 ]]; then status=${statuses[1]}; fi
  exit "$status"
)
```

Repeat `--service name[:target]` for a bounded batch. Multi-target services require
an explicit target, avoiding accidental worker/controller or variant selection.
`--mode rootful` records a proposed exception; it changes no runtime privileges.
NetBox remains authoritative for actual hosts, addresses, IDs and roots.

The unique private batch contains:

```text
PLAN.md                 scope, evidence, order, acceptance and scoped rollback
catalogue.json          value-limited declaration summary and source hashes
recipes/prepare.sh      draft; fails closed until replaced with reviewed commands
recipes/cutover.sh       draft; fails closed until replaced with reviewed commands
recipes/rollback.sh      draft; fails closed until replaced with reviewed commands
evidence/               runtime/host/caller observations and private logs
backups/                backup receipts/locations; not an automatic data copy
ownership/              numeric maps, per-path translations, ACL/link verification
firewall/               installed union, proposed caller changes, counter evidence
acceptance/             machine results and bundled operator observations
rollback/               retained exact recipes/material and final state
```

The catalogue snapshot is not observed placement, a process identity, an image
staging proof or a permission grant. It excludes environments, settings, secret
values and credential-bearing connection strings. Do not put real secrets in
plans/recipes; use existing no-log Vault/Infisical handling only when authorized.
Keep real evidence outside Git. Do not create a new service batch tag to activate
safeguards: explicit operational requirements remain independent of selectors.

## Existing toolkit and boundaries

Reusable [HAProxy operator examples](guides/haproxy.md), the
[ownership procedure](guides/ownership.md) and tested sanitized
[route-producer templates](examples/route-producers.py) stay here. They are
operational source/examples, not completed-batch record keeping. Historical
logs, approvals and full handoffs remain in the private external archive.

Reusable Ansible task lists are documented in [ansible/tasks](../ansible/tasks/README.md)
and selected explicitly through `ansible/operations.yml`. Executable support
tools and their retained rollback dependencies are described in
[ansible/operator](../ansible/operator/README.md); they are not task-list YAML.
Completed one-off diagnostic launchers and their dedicated tests belong in the
external archive rather than this toolkit.


| Concern | Reuse | Required proof |
| --- | --- | --- |
| Effective service/target | `ansible/filter_plugins/service_catalog.py` | Canonical base-plus-target merge; observed source may still be Docker even when the declaration is already prepared for Podman |
| Accounts, runtime collection, selected maps | `ansible/operator/utility-preparation.py` | Exact supported batch, host identity, account/home/runtime, PID/namespace continuity and selected keep-id mapping |
| Numeric maps | `ansible/operator/znc-mapping-proof.py` | Compare integer triples; map old host owners through the actual old/new maps independently for UID/GID |
| Ownership and archives | `utility-preparation.py` ownership inventory/apply/verify and archive helpers | Stopped writer, exact paths, symlink safeguards, consistent translations, contained hardlink groups, permissions/ACLs/contents/topology and isolated restore |
| Backup progress | `ansible/operator/backup-storage-watchdog.py` | Operation-specific progress, continuity/correlation, independent deadlines/capacity/size limits; D-state alone is not a stall |
| Policy/caller handling | `ansible/operator/haproxy-cutover.py`, mgt/worker firewall roles and [runbooks](../docs/mgt-firewall.md) | Preserve the CURRENT installed union and unrelated bindings; fresh qualified identity, original-destination hooks and owned RETURN/DROP evidence |
| Database preparation/recovery | [native operator contexts](../docs/mgt-native-operator.md), `service_common` | Existing credential policy, exact scoped context and application-owned authenticated checks; TCP is not SQL proof |
| Deployment and restart | `podman_services`, `docker_services`, `service_prepare`, [skynet](../docs/cheat_sheets/skynet.md) | Scoped selectors, no simultaneous writers, bounded readiness and actual listener ownership |
| Bootstrap providers | `ansible/bootstrap.yml`, NetBox/Infisical roles | Independent inventory/credential recovery; do not force these into catalog helpers |

The existing utility collector deliberately supports specific batches. Its
`--services` / `--service-map` allowlists are not a generic collector API. For a
new service, review the projection/preparation handler and add meaningful
coverage for new behavior before invoking it. Do not simply widen an allowlist,
substitute a default user namespace, or reuse historical runtime identities.

Some helpers have historical service names but shared responsibilities. Keep
their existing paths during cleanup: `utility-preparation.py` imports ZNC mapping
code, and saved Technitium rollback imports utility/HAProxy helpers. This initial
workspace does not extract or duplicate those implementations. A future extraction
requires compatibility imports and regression coverage for retained recipes.

## Approve, execute, retain

1. Collect only the batch's authorized observations; resolve every `TODO:` in
   `PLAN.md` and write exact recipes. Reuse unchanged accepted evidence, but refresh
   volatile identities and stopped-writer manifests. Keep all acknowledgements
   false until their applicable proof exists. Preserve policy unions and old
   rollback bindings. Treat version/schema rollback explicitly.
2. Seal the plan, selected recipes and any additional repository dependencies:

   ```text
   /opt/ansible/ansible-venv/bin/python /opt/homelab/migrator/migrate.py seal PRIVATE_BATCH \
     --recipe recipes/prepare.sh --recipe recipes/cutover.sh \
     --recipe recipes/rollback.sh --source ansible/operator/haproxy-cutover.py
   ```

   Run this with the repository venv. `PRIVATE_BATCH` is the returned workspace;
   list the actual helper/role/template dependencies used by these recipes with
   repeated `--source`. Sealing fails on draft placeholders or changed canonical
   sources. New seals are unique files; existing approved manifests are preserved.
   If canonical preparation changes after init, create a refreshed workspace and
   reference retained evidence from the old one rather than overwriting it.
3. Present one complete plan and the printed manifest SHA256 for approval before
   the first service disruption. A checksum is not approval. Approved execution
   covers the included bounded sequence and necessary scoped rollback, without
   repeated per-command permission prompts.
4. Immediately before execution, use `verify PRIVATE_BATCH --manifest FILENAME
   --sha256 REVIEWED_SHA256`. It checks the separately supplied hash plus every
   sealed recipe/source. Recheck live state guards using the approved recipes;
   offline integrity is not live readiness. Stop on a mismatch or scope change.
5. Execute the approved recipes through the existing account/escalation workflow.
   Each needs unique private logs printed before work, checked pipeline statuses,
   interruption/output-failure handling, and service-scoped recovery. No host or
   Docker-daemon restart unless separately authorized. Bundle browser checks once.
6. Record only proved machine/human results. Keep paired backups, exact ownership
   manifests, Docker rollback records and dependencies until an explicit retention
   decision. Restoration stops both writers and may discard post-backup changes;
   retain post-cutover material for recovery. No overwrite/delete synchronization.

No batch is approved or executed by installing this workspace. Each future
migration requires its own named scope, current observations and reviewed plan.
