# Native PostgreSQL operator contexts

Operational preparation and recovery for narrowly scoped PostgreSQL jobs. Per-run
identity/counter evidence and completed migration records are kept outside Git
under `/opt/ansible/migration/` and the batch's private evidence directory.
Do not treat a historical UID, PID, listener or accepted policy as current proof.

These commands require authorization for the named operation. Preparation does
not install application files or accept firewall/database behavior. Preserve
unrelated bindings and existing confirmations; collect new socket/cgroup/hook
proof only when relevant identity changes require it. The reusable
[HAProxy operations guide](../migrator/guides/haproxy.md) describes staged caller
and complete-policy transitions.

## Actual entry points and identities

Normal catalog deployments run `ansible/playbook.yml` with `become: true`.
Docker and Podman preparation both call `service_common`, whose `prepare.yml`
includes `postgres.yml`. Its one `community.postgresql.postgresql_db` task
loops declared databases, uses the current service's resolved credential
references, and delegates once to `service_common_controller_host` (mgt).
The manager group declares local transport and the Ansible venv interpreter.
The inherited become user is root. No database module runs in check mode.

`service_common_postgres_operator_context: true` now switches **only that
task's delegated interpreter** to
`/usr/local/libexec/skynet-mgt-operator/postgres-python`. Default false retains
the delegate's interpreter. The wrapper runs **after become**, requires real
and effective UID 0, checks the prepared persistent slice, then executes the
same venv Python/module with pipelined stdin and normal stdout/stderr/exit
status. Secrets remain in the existing module transport with `no_log`/`diff`
protection; they are not copied into systemd environment/command arguments.
No whole deployment, sudo/PAM session, SSH daemon or unrelated root task is
moved. Do not override global `ansible_python_interpreter` to select this wrapper.

The [offline handoff rollback](../migrator/guides/haproxy.md#policy-transitions-and-scoped-rollback)
uses local NSS, the saved self-contained firewall helper/policy, systemd and
Docker's existing manager. It needs no database connection, Forgejo, NetBox,
Infisical or Ansible. Run its explicitly reviewed local commands through the
separate `recovery` launcher. Native SQL diagnostics, if subsequently approved,
must use that same launcher and already prepared credential-file interfaces;
never supply passwords, environments or connection strings as visible arguments.

`ansible/bootstrap.yml` is a different recovery entry: localhost/local,
`become: true`, explicit cached Vault inputs, production NetBox/Infisical owners,
without dynamic inventory or Infisical lookup. Those roles launch independent
Podman managers. Their database sockets belong to the actual application
accounts/containers, **not** this root recovery slice; retain their separate
bindings/acknowledgements. Do not run bootstrap just to establish a native socket.
The Patroni restore role queries the leader and restores on PostgreSQL nodes;
it is not an mgt HAProxy native SQL entry and is outside this preparation.

## Persistent contexts and preparation

| Principal | Persistent cgroup path, relative to `/sys/fs/cgroup` | Socket UID |
| --- | --- | --- |
| `controller` | `skynet_pg_prepare.slice` | Must be observed as 0 in the actual delegated native module/probe |
| `recovery` | `skynet_pg_recovery.slice` | Must be observed as 0 in the explicit native recovery context/probe |

Underscores keep both slices directly below the cgroup root; do not substitute
a shared `system.slice`, session scope or UID-only binding. Static units are
enabled at `slices.target`, ordered before the mgt firewall guard, and stay
active while empty. They contain no boot command or credentials. The wrapper
refuses absent/unowned/inactive slices instead of materializing a transient
replacement. Short-lived services are collected after each operation; the
persistently active parent slice remains for firewall resolution.

From the **existing mgt operator/console session**, use your printed pre-staged
`HANDOFF_DIR`; paths printed here must remain available without Forgejo. This
runner creates fresh private logs, prints their paths before execution, and
retains command failures. It installs only operator files/units, not application
files, firewall rules or HAProxy placement:

```bash
set -euo pipefail
umask 077
: "${HANDOFF_DIR:?Set the existing local handoff directory}"
NATIVE_DIR="$HANDOFF_DIR/native-operator-$(date -u +%Y%m%dT%H%M%SZ)-$$"
test ! -e "$NATIVE_DIR"
mkdir -m 0700 "$NATIVE_DIR"
cd "$HANDOFF_DIR"
export NATIVE_DIR
printf 'Native preparation log: %s\nController probe log: %s\nRecovery probe log: %s\n' \
  "$NATIVE_DIR/preparation.log" "$NATIVE_DIR/controller-probe.log" "$NATIVE_DIR/recovery-probe.log"
printf 'Preparation plan log: %s\n' "$NATIVE_DIR/preparation-plan.log"
run_native_logged() {
  local log_path="$1" status=0
  shift
  "$@" >"$log_path" 2>&1 || status=$?
  cat "$log_path" || true
  return "$status"
}
# Optional read-only file/collision plan (no unit/file writes):
run_native_logged "$NATIVE_DIR/preparation-plan.log" /bin/bash /opt/homelab/ansible/operator/prepare-native-operator.sh --check
run_native_logged "$NATIVE_DIR/preparation.log" sudo /bin/bash /opt/homelab/ansible/operator/prepare-native-operator.sh
```

Expected: only these owned paths change; both units show active with exact
`ControlGroup=/skynet_pg_prepare.slice` / `/skynet_pg_recovery.slice` and
`FragmentPath=/etc/systemd/system/...`. Repeat preparation is idempotent in
effective files/unit state; it does not restart an application or set any flag.
Keep the helper/units and this document in the local handoff material too:

```bash
cp /opt/homelab/docs/mgt-native-operator.md "$NATIVE_DIR/"
cp /opt/homelab/ansible/operator/{mgt-operator.py,prepare-native-operator.sh,haproxy-policy-rollback.sh} "$NATIVE_DIR/"
cp /opt/homelab/ansible/operator/skynet_pg_prepare.slice /opt/homelab/ansible/operator/skynet_pg_recovery.slice "$NATIVE_DIR/"
sudo systemctl show skynet_pg_prepare.slice skynet_pg_recovery.slice --no-pager \
  -p ActiveState -p ControlGroup -p FragmentPath -p TasksCurrent
test -d /sys/fs/cgroup/skynet_pg_prepare.slice
test -d /sys/fs/cgroup/skynet_pg_recovery.slice
```

## Verify actual sockets without credentials or application deployment

Use the inventory-derived PostgreSQL publication and verify its active
listener before probing. Each probe enters a new service
inside its persistent slice, opens one TCP connection, checks that socket's
inode/UID in `/proc/self/net/tcp*`, reports numeric source/destination and its
actual cgroup, and holds for 15 seconds. It sends/reads **no database payload**.
The socket timeout is five seconds; a failed connection/ownership check exits
nonzero and supplies no successful evidence:

```bash
: "${MGT_PG_ADDRESS:?Set the verified inventory-derived PostgreSQL address}"
run_native_logged "$NATIVE_DIR/controller-probe.log" sudo /usr/bin/python3 \
  /usr/local/libexec/skynet-mgt-operator/mgt-operator.py probe controller "$MGT_PG_ADDRESS" 5432 15
run_native_logged "$NATIVE_DIR/recovery-probe.log" sudo /usr/bin/python3 \
  /usr/local/libexec/skynet-mgt-operator/mgt-operator.py probe recovery "$MGT_PG_ADDRESS" 5432 15
```

In a second pre-staged console, inspect only numeric endpoints/process IDs
while the probe holds: `sudo ss -Hntpe '( dport = :5432 )'`, then
`sudo cat /proc/OBSERVED_PROBE_PID/cgroup`. Compare the reported actual
`socket_uid: 0`, full child path `skynet_pg_*.slice/run-....service` and the
persistent parent used by the binding. Do not inspect process environments,
arguments or full service/container specs. A process UID alone is insufficient.

Use the [existing narrow counter procedure](mgt-firewall.md#operator-preflight-and-commands)
at OUTPUT to prove the **combination** before policy activation; for each
context, insert/count/delete exactly this observation rule, with
`NATIVE_CGROUP` set to the corresponding parent name:

```bash
NATIVE_CGROUP=skynet_pg_prepare.slice  # repeat separately for skynet_pg_recovery.slice
sudo iptables -t mangle -I OUTPUT 1 -p tcp -d "$MGT_PG_ADDRESS" --dport 5432 \
  -m owner --uid-owner 0 -m cgroup --path "$NATIVE_CGROUP" -m comment --comment skynet-mgt-native-observe
# Repeat that context's probe; inspect the exact observation counter.
sudo iptables -t mangle -L OUTPUT -n -v -x
sudo iptables -t mangle -D OUTPUT -p tcp -d "$MGT_PG_ADDRESS" --dport 5432 \
  -m owner --uid-owner 0 -m cgroup --path "$NATIVE_CGROUP" -m comment --comment skynet-mgt-native-observe
```

Repeat at filter OUTPUT using the original destination/port conntrack match,
and with `ip6tables` for any approved/exposed IPv6 native path. Count then
continue: no ACCEPT/DROP exception, packet payload capture or firewall flush.
Unrelated `sudo nc`/Python jobs outside these slices must not increment that
identity counter and must be denied after protected-port policy installation
under active-listener/probe coverage. Remove observation rules even on failure.
Repeat each context to prove a **new** child service retains the parent match.
This establishes transport identity, not database credentials, reconciliation
or application acceptance. Repeat the actual module counter check during an
authorized application batch, after HAProxy handoff.

Candidate bindings for **manual merge** into the prepared stage, retaining all
accepted Homepage/Forgejo/application entries, are:

```yaml
controller:
  - kind: local
    phase: native
    account: root
    uid: 0
    cgroup: skynet_pg_prepare.slice
    verified: false
    restart_verified: false
recovery:
  - kind: local
    phase: native
    account: root
    uid: 0
    cgroup: skynet_pg_recovery.slice
    verified: false
    restart_verified: false
```

Keep overall `mgt_firewall_inputs_verified: false`; neither preparation nor
probing completes a confirmation. Promote only manually accepted native
identity/hook/replacement evidence. Other controller/recovery paths, including
SQL jobs launched outside these contexts, get no exemption.

## Executing the actual operations and offline recovery

For later **authorized** catalog application batches, opt in without changing
the normal entry point, destination, credentials, delegation or become. The
check is read-only; the live example is the existing deployment operation, not
a database-only preparation mode, and must wait for its application gates:

```bash
printf 'Catalog plan: %s\nAnsible log: %s\n' "$NATIVE_DIR/catalog-plan.log" "$NATIVE_DIR/catalog-plan.ansible.log"
export ANSIBLE_LOG_PATH="$NATIVE_DIR/catalog-plan.ansible.log"
run_native_logged "$NATIVE_DIR/catalog-plan.log" env PLAYBOOK=/opt/homelab/ansible/playbook.yml \
  skynet raw --check --tags deploy,vaultwarden -e "@$HAPROXY_GATES" \
  -e '{"service_common_postgres_operator_context":true}'
# Later, only when this application's own ACL/data inputs are accepted:
# export ANSIBLE_LOG_PATH="$NATIVE_DIR/catalog-live.ansible.log"
# run_native_logged "$NATIVE_DIR/catalog-live.log" env PLAYBOOK=/opt/homelab/ansible/playbook.yml \
#   skynet raw --tags deploy,vaultwarden -e @/secure/vaultwarden-accepted-gates.yml \
#   -e '{"service_common_postgres_operator_context":true}'
```

The gate file for HAProxy is not acceptance of Vaultwarden: check mode can
plan, but live invocation must use its own accepted inputs. The current
service's Infisical lookup remains necessary for normal catalog deployment;
**do not run it as offline recovery**. Do not launch a whole ordinary catalog
run in the controller slice to try to move a delegated socket.

During Forgejo's interruption, local firewall audit runs entirely from the
pre-staged material/installed helper, with no inventory or credential lookup:

```bash
printf 'Offline audit log: %s\n' "$NATIVE_DIR/offline-audit.log"
run_native_logged "$NATIVE_DIR/offline-audit.log" sudo /usr/bin/python3 \
  /usr/local/libexec/skynet-mgt-operator/mgt-operator.py recovery \
  /usr/bin/python3 /etc/skynet-mgt-firewall/policy.py check
```

The preparation copies the repository's self-contained `haproxy-policy-rollback.sh`
into `NATIVE_DIR`. It validates the complete `policy-before.py`/`policy-before.json` baseline and
rejects newer unrelated installed policy before stopping the reconcile timer.
It restores that complete baseline, restarts the timer, and audits. Set
`HANDOFF_DIR` to the recorded batch containing the staged `haproxy-cutover.py`,
`stage.json` and `working-policy.json`; the parent handoff or a legacy
Homepage-only snapshot is insufficient.
It requires root inside the recovery slice and no inventory or credentials.
Run it **only when the failed transition requires policy rollback**:

```bash
printf 'Offline policy rollback log: %s\n' "$NATIVE_DIR/offline-policy-rollback.log"
# After reviewing the failure/rollback table; do not run as ordinary preparation:
# run_native_logged "$NATIVE_DIR/offline-policy-rollback.log" sudo /usr/bin/python3 \
#   /usr/local/libexec/skynet-mgt-operator/mgt-operator.py recovery \
#   /bin/bash "$NATIVE_DIR/haproxy-policy-rollback.sh" "$HANDOFF_DIR"
```

This does not stop a listener or restore placement. For failures after a new
unit exists, execute the handoff's recorded per-account stop/Quadlet withdrawal
first, through the explicit recovery context. The saved environment contains
only recorded public paths/placement values and the account helper:

```bash
printf 'Offline listener withdrawal log: %s\n' "$NATIVE_DIR/offline-listener.log"
# Only after deployment created the new unit/source:
# run_native_logged "$NATIVE_DIR/offline-listener.log" sudo /usr/bin/python3 \
#   /usr/local/libexec/skynet-mgt-operator/mgt-operator.py recovery \
#   /bin/bash -s -- "$HANDOFF_DIR" <<'SH'
# set -euo pipefail
# source "$1/recovery-env.sh"
# haproxy_account systemctl --user stop haproxy.service
# haproxy_account /usr/bin/podman ps --filter name='^haproxy$' --format '{{.Names}} {{.Status}}'
# # If an exact leftover running container is reported, stop only that container.
# # If it remains running, stop here; inspect before moving any source.
# test ! -e "$HANDOFF_DIR/failed-haproxy.container"
# mv "$HAPROXY_HOME/.config/containers/systemd/haproxy.container" "$HANDOFF_DIR/failed-haproxy.container"
# haproxy_account systemctl --user daemon-reload
# ss -Hlnpt '( sport = :5432 or sport = :18405 )'
# SH
```

Do not treat unexpected unit/container/source state or a failed command as
success. After proving the new listener cannot return, restore only the
recorded newly added constraint (skip if it was never added):

```bash
printf 'Offline placement restore log: %s\n' "$NATIVE_DIR/offline-placement.log"
# run_native_logged "$NATIVE_DIR/offline-placement.log" sudo /usr/bin/python3 \
#   /usr/local/libexec/skynet-mgt-operator/mgt-operator.py recovery \
#   /bin/bash -s -- "$HANDOFF_DIR" <<'SH'
# set -euo pipefail
# source "$1/recovery-env.sh"
# docker service update --constraint-rm "$RECORDED_MGT_EXCLUSION" "$RECORDED_HAPROXY_SERVICE"
# docker service ps "$RECORDED_HAPROXY_SERVICE" --filter desired-state=running --format '{{.ID}} {{.Node}} {{.CurrentState}}'
# ss -Hlnpt '( sport = :5432 )'
# SH
```

The commented blocks are exact scoped failure operations: uncomment only the
applicable transition after recording the needed state. Keep this document,
helper, rollback script, complete saved policy baseline, scoped Homepage
evidence and `recovery-env.sh` locally before
the window. No checkout or Forgejo connection is needed to run the installed
launcher and those saved files.

Systemd supplies a clean root environment; pass only required public paths
explicitly, not credential values through `--setenv` or argv. Rootless user
unit commands keep the existing direct account home/runtime/bus environment;
their workload sockets do not acquire root native permissions.

If separately required/authorized, use the existing explicit local bootstrap
entry with its pre-staged encrypted inputs and local YAML/localhost inventory;
retain bootstrap ACL/data gates and application identities. No native wrapper
permits bootstrapping unverified workloads or bypasses those gates.

## Scoped context rollback

First finish/abort any reviewed native jobs and withdraw these bindings through
an accepted policy stage (or restore the complete saved baseline using the
pre-staged offline rollback). Never delete an active binding's required slice:
the firewall will fail closed. Preserve unrelated application identities,
destinations, worker policy/config and accepted endpoint protections.

From the original console **outside both slices**, verify they are idle and
only remove the exact owned files after the binding withdrawal:

```bash
sudo systemctl show skynet_pg_prepare.slice skynet_pg_recovery.slice --no-pager -p TasksCurrent
test "$(sudo systemctl show skynet_pg_prepare.slice --value -p TasksCurrent)" = 0
test "$(sudo systemctl show skynet_pg_recovery.slice --value -p TasksCurrent)" = 0
# Check ownership/collisions before stopping either context:
/bin/bash "$NATIVE_DIR/prepare-native-operator.sh" --check
sudo cmp "$NATIVE_DIR/skynet_pg_prepare.slice" /etc/systemd/system/skynet_pg_prepare.slice
sudo cmp "$NATIVE_DIR/skynet_pg_recovery.slice" /etc/systemd/system/skynet_pg_recovery.slice
sudo cmp "$NATIVE_DIR/mgt-operator.py" /usr/local/libexec/skynet-mgt-operator/mgt-operator.py
test "$(sudo readlink /usr/local/libexec/skynet-mgt-operator/postgres-python)" = mgt-operator.py
sudo systemctl disable --now skynet_pg_prepare.slice skynet_pg_recovery.slice
sudo rm /etc/systemd/system/skynet_pg_prepare.slice /etc/systemd/system/skynet_pg_recovery.slice \
  /usr/local/libexec/skynet-mgt-operator/postgres-python /usr/local/libexec/skynet-mgt-operator/mgt-operator.py
sudo systemctl daemon-reload
```

Use the retained installation source if the checkout has since changed; a
failed comparison is a stop, not permission to delete a collision. Disable the
opt-in on subsequent catalog commands; default false retains previous behavior.
Keep local logs/recovery material until final acceptance. Live socket/hook
coverage, actual database preparation, recovery execution and reboot persistence
remain operator acceptance; no helper sets ACL/data or complete-policy flags.
