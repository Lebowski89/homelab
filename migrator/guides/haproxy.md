# HAProxy caller and metrics operations

Reusable operator examples for reviewed batches. Historical mgt cutover outcomes,
approval records and logs are archived outside the repository in
`/opt/ansible/migration/`. Do not replay a completed cutover or assume an old
caller identity remains valid.

Use these examples only within a named, approved scope. Resolve current host,
service/container, PID/namespace and provider identities; preserve the current
installed policy union and unrelated bindings. Check mode and collection do not
accept routes, prove SQL operations or authorize deployment. Keep normal no-log
credential handling and [native operator contexts](../../docs/mgt-native-operator.md).

Existing batch commands remain in `ansible/operator/haproxy-cutover-batch.sh`;
inspect the recorded stage before selecting prepare/resume/maintenance/continue
or scoped rollback. Continue only a supported recorded state. Old writers must
stop before new listeners start, with matching database/files rollback material.
No helper is installed or executed by this document.

## Preflight

Set `PREFLIGHT_DIR` to an existing private directory and
`HOMEPAGE_FIREWALL_INPUT` to the reviewed accepted inputs. The helper validates
observed delegated hosts and caller continuity. Preserve every unproved flag.

```bash
(
  set -euo pipefail
  umask 077
  export PLAYBOOK=/opt/homelab/ansible/operations.yml
  PREFLIGHT_DIR="${PREFLIGHT_DIR:-/secure}"
  HOMEPAGE_FIREWALL_INPUT="${HOMEPAGE_FIREWALL_INPUT:-/secure/homepage-firewall-accepted.yml}"
  PREFLIGHT_OUTPUT="$PREFLIGHT_DIR/haproxy-candidate-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
  PREFLIGHT_CHECK_LOG="$PREFLIGHT_OUTPUT.check.log"
  PREFLIGHT_LOG="$PREFLIGHT_OUTPUT.collect.log"
  export ANSIBLE_LOG_PATH="$PREFLIGHT_OUTPUT.ansible.log"
  printf 'Candidate: %s\nMetadata: %s\nPending: %s\nCheck log: %s\nCollection log: %s\nAnsible log: %s\n' \
    "$PREFLIGHT_OUTPUT" "$PREFLIGHT_OUTPUT.metadata.json" "$PREFLIGHT_OUTPUT.pending.json" \
    "$PREFLIGHT_CHECK_LOG" "$PREFLIGHT_LOG" "$ANSIBLE_LOG_PATH"
  for path in "$PREFLIGHT_OUTPUT" "$PREFLIGHT_OUTPUT.metadata.json" "$PREFLIGHT_OUTPUT.pending.json" \
              "$PREFLIGHT_CHECK_LOG" "$PREFLIGHT_LOG" "$ANSIBLE_LOG_PATH"; do
    test ! -e "$path"
  done
  run_preflight() {
    local log_path="$1" status=0
    shift
    skynet raw --tags haproxy_preflight "$@" >"$log_path" 2>&1 || status=$?
    cat "$log_path" || true
    return "$status"
  }
  run_preflight "$PREFLIGHT_CHECK_LOG" --check -e "@$HOMEPAGE_FIREWALL_INPUT" -e "haproxy_preflight_output=$PREFLIGHT_OUTPUT"
  run_preflight "$PREFLIGHT_LOG" -e "@$HOMEPAGE_FIREWALL_INPUT" -e "haproxy_preflight_output=$PREFLIGHT_OUTPUT"
)
```

## Resume preparation

Set `HAPROXY_BATCH` to the reviewed private batch. This resumes bounded route
collection and validation; it does not replay completed caller replacements.

```bash
(
  set -euo pipefail
  umask 077
  batch="${HAPROXY_BATCH:?Set HAPROXY_BATCH to the reviewed private batch directory}"
  stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
  log="$batch/resume-runner-$stamp.log"
  printf 'Existing batch: %s\nPrivate runner log: %s\n' "$batch" "$log"
  (set -o noclobber; : >"$log")
  set +e
  PLAYBOOK=/opt/homelab/ansible/playbook.yml \
  VIRTUAL_ENV=/opt/ansible/ansible-venv \
  /bin/bash /opt/homelab/ansible/operator/haproxy-cutover-batch.sh resume "$batch" \
    2>&1 | tee -a "$log"
  statuses=("${PIPESTATUS[@]}")
  status=${statuses[0]}
  if [[ "$status" = 0 ]]; then status=${statuses[1]}; fi
  printf 'Route capture/resume exited with status %s\n' "$status" | tee -a "$log"
  exit "$status"
)
```

## Collect application activity

Set `HAPROXY_BATCH` to the reviewed batch. Use only when route evidence is
missing; retain valid prior windows through the existing identity/freshness
validator. Application sockets alone do not prove successful SQL operations.

```bash
(
  set -euo pipefail
  umask 077
  batch="${HAPROXY_BATCH:?Set HAPROXY_BATCH to the reviewed private batch directory}"
  out="$batch/live-activity-$(date -u +%Y%m%dT%H%M%SZ)-$$"
  log="$out/operator.log"
  printf 'Private activity directory: %s\nPrivate log: %s\nAnsible log: %s\n' "$out" "$log" "$out/ansible.log"
  mkdir -m 0700 "$out"
  (set -o noclobber; : >"$log")
  printf 'When simultaneous capture-window polling begins, perform the listed normal UI activity within 600 seconds.\n'
  set +e
  PLAYBOOK=/opt/homelab/ansible/operations.yml \
  VIRTUAL_ENV=/opt/ansible/ansible-venv \
  ANSIBLE_LOG_PATH="$out/ansible.log" \
  skynet raw --tags haproxy_preflight -e "@$batch/working-policy.json" \
    -e "haproxy_preflight_output=$out/activity.json" \
    -e "haproxy_preflight_stage_output=$out/stage.json" \
    -e '{"haproxy_preflight_window_seconds":600,"haproxy_preflight_sample_interval":0.5}' \
    2>&1 | tee -a "$log"
  statuses=("${PIPESTATUS[@]}")
  status=${statuses[0]}
  if [[ "$status" = 0 ]]; then status=${statuses[1]}; fi
  printf 'Activity capture exited with status %s\n' "$status" | tee -a "$log"
  exit "$status"
)
```

## Add a scrape to an existing Docker Prometheus

This optional configuration-only play is for a verified **Docker Swarm**
Prometheus instance. It is not the normal update path for already rootless mgt
Prometheus. Use the canonical Podman adapter for that runtime instead. Set
`HAPROXY_BATCH` to the reviewed private log directory/batch before an authorized
Docker configuration update. Preserve the existing scrape and job/instance labels.

```bash
(
  set -euo pipefail
  umask 077
  batch="${HAPROXY_BATCH:?Set HAPROXY_BATCH to the reviewed private batch directory}"
  out="$(mktemp -d "$batch/prometheus-haproxy-scrape.XXXXXX")"
  log="$out/operator.log"
  printf 'Private scrape log: %s\nPrivate Ansible log: %s\n' "$log" "$out/ansible.log"
  (set -o noclobber; : >"$log")
  set +e
  PLAYBOOK=/opt/homelab/ansible/operations.yml \
  VIRTUAL_ENV=/opt/ansible/ansible-venv \
  ANSIBLE_LOG_PATH="$out/ansible.log" \
  skynet raw --tags prometheus_haproxy_scrape 2>&1 | tee -a "$log"
  statuses=("${PIPESTATUS[@]}")
  status=${statuses[0]}
  if [[ "$status" = 0 ]]; then status=${statuses[1]}; fi
  printf 'Prometheus scrape update exited with status %s\n' "$status" | tee -a "$log"
  finish=("${PIPESTATUS[@]}")
  if [[ "$status" = 0 ]]; then status=${finish[0]}; fi
  if [[ "$status" = 0 ]]; then status=${finish[1]}; fi
  exit "$status"
)
```

## Policy transitions and scoped rollback

Prepare all current PostgreSQL/metrics callers before changing placement. Preserve
worker VIP/image/native config/network/port contracts. Prove worker-only routes
before promoting only evidenced worker confirmations, install the complete policy
union before a new mgt listener, and deploy only its target. Missing idle-caller
routes remain pending. Re-resolve replacement identities; never authorize shared
subnets, stale IDs, or unrelated root.

Retain accepted private snapshots and use the matching batch's scoped rollback.
`ansible/operator/haproxy-policy-rollback.sh` requires the prepared native recovery
slice and the complete `policy-before.py` / `policy-before.json` baseline, plus
`haproxy-cutover.py`. Its policy-union/current-state guards run before writes.
It does not rebuild a policy from Homepage alone. Never restore old databases or
placement without stopping competing writers/listeners and checking the recorded
stage. See [mgt policy operations](../../docs/mgt-firewall.md) and the
[native recovery contract](../../docs/mgt-native-operator.md).
