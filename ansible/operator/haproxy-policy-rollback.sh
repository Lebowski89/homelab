#!/bin/bash
# Managed by skynet mgt operator contexts; restore only the complete saved policy baseline.
set -euo pipefail
umask 077
test "$EUID" = 0
test "$#" = 1
case "$1" in
  /*) handoff_dir="$1" ;;
  *) echo 'An absolute pre-staged handoff directory is required' >&2; exit 2 ;;
esac
# The caller must use the prepared recovery launcher, not an unrelated root job.
case "$(cut -d: -f3 /proc/self/cgroup)" in
  /skynet_pg_recovery.slice/*) ;;
  *) echo 'Run through the prepared native recovery context' >&2; exit 2 ;;
esac
test -f "$handoff_dir/policy-before.py"
test -f "$handoff_dir/policy-before.json"
/usr/bin/python3 "$handoff_dir/haproxy-cutover.py" rollback-policy "$handoff_dir"
# Validation failures must precede timer/file changes. Apply retains the saved
# helper's identity rediscovery, ownership checks and both-family dry testing.
/usr/bin/python3 "$handoff_dir/policy-before.py" validate --config "$handoff_dir/policy-before.json"
systemctl stop skynet-mgt-firewall-reconcile.timer
systemctl stop skynet-mgt-firewall-reconcile.service
/usr/bin/python3 "$handoff_dir/policy-before.py" apply --config "$handoff_dir/policy-before.json"
install -m 0600 -o root -g root "$handoff_dir/policy-before.py" /etc/skynet-mgt-firewall/policy.py
install -m 0600 -o root -g root "$handoff_dir/policy-before.json" /etc/skynet-mgt-firewall/policy.json
systemctl start skynet-mgt-firewall-reconcile.timer
/usr/bin/python3 /etc/skynet-mgt-firewall/policy.py check
