#!/bin/bash
# Read-only snapshot using the existing saved inventory/SSH projection.
set -euo pipefail
umask 077
test "$#" = 2
batch="$1"
peer="$2"
case "$batch" in /*) ;; *) echo 'Absolute batch path required' >&2; exit 2 ;; esac
repo="$(dirname "$(dirname "${PLAYBOOK:-/opt/homelab/ansible/playbook.yml}")")"
python="${VIRTUAL_ENV:-/opt/ansible/ansible-venv}/bin/python"
output="$batch/address-snapshot-$(date -u +%Y%m%dT%H%M%SZ)-$$"
log="$output/operator.log"
printf 'Private snapshot directory: %s\nPrivate log: %s\nmgt addresses: %s\nPlex addresses: %s\nCoverage: %s\n' \
  "$output" "$log" "$output/mgt.json" "$output/plex.json" "$output/coverage.json"
mkdir -m 0700 "$output"
(set -o noclobber; : >"$log")
set +e
(
  set -euo pipefail
  sudo -v
  sudo -n "$python" -B "$repo/ansible/operator/haproxy-address-snapshot.py" "$batch" "$peer" "$output"
) 2>&1 | tee -a "$log"
statuses=("${PIPESTATUS[@]}")
status=${statuses[0]}
if [[ "$status" = 0 ]]; then status=${statuses[1]}; fi
printf 'Read-only address snapshot exited with status %s\nPrivate log: %s\n' "$status" "$log" | tee -a "$log"
exit "$status"
