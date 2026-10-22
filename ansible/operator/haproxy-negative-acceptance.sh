#!/bin/bash
# Operator-only supplement to the paused maintenance prompt; no confirmations change.
set -euo pipefail
umask 077
mode=negative
if [[ "${1:-}" == --actual ]]; then mode=negative-service; shift; fi
test "$#" = 1
batch="$1"
case "$batch" in /*) ;; *) echo 'An absolute prepared batch is required' >&2; exit 2 ;; esac
repo="$(dirname "$(dirname "${PLAYBOOK:-/opt/homelab/ansible/playbook.yml}")")"
python="${VIRTUAL_ENV:-/opt/ansible/ansible-venv}/bin/python"
export ANSIBLE_CONFIG="${ANSIBLE_CONFIG:-$repo/ansible/ansible.cfg}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
output="$batch/$mode-$stamp"
log="$output/operator.log"
printf 'Private negative evidence directory: %s\nPrivate log: %s\nPeer projection: %s\n' "$output" "$log" "$output/peer.json"
mkdir -m 0700 "$output"
(set -o noclobber; : >"$log")
set +e
(
  set -euo pipefail
  sudo -v
  # Use the same NetBox inventory machinery; project transport only. Never dump
  # all host variables or invoke application/secret preparation.
  "$python" - "$repo" "$output/peer.json" <<'PY'
import ipaddress,json,os,pwd,re,sys
from pathlib import Path
from ansible.parsing.dataloader import DataLoader
from ansible.inventory.manager import InventoryManager
from ansible.vars.manager import VariableManager
from ansible.plugins.loader import init_plugin_loader
repo,output=Path(sys.argv[1]),Path(sys.argv[2])
# The direct Python API does not perform CLI.run collection initialization.
init_plugin_loader()
loader=DataLoader()
inventory=InventoryManager(loader=loader,sources=[str(repo/'ansible/netbox.yml')])
host=inventory.get_host('plex')
if host is None:raise SystemExit('Plex inventory peer is missing')
values=VariableManager(loader=loader,inventory=inventory).get_vars(host=host)
if values.get('ansible_connection','ssh') not in ['ssh','ansible.builtin.ssh']:
    raise SystemExit('Plex peer must use its explicit SSH inventory transport')
peer={'inventory_host':host.name,'inventory_address':str(ipaddress.ip_address(values['local_ip'])),
      'ansible_host':str(ipaddress.ip_address(values['ansible_host'])),
      'ansible_user':values['ansible_user'],'ansible_port':int(values.get('ansible_port',22))}
operator=pwd.getpwuid(os.getuid())
if operator.pw_uid <= 0:raise SystemExit('Run the batch as the ordinary operator, not root')
peer['operator']={'uid':operator.pw_uid,'account':operator.pw_name,'home':operator.pw_dir,
                  'ssh_auth_sock':os.environ.get('SSH_AUTH_SOCK')}
if not re.fullmatch(r'[a-zA-Z0-9_-]+',peer['ansible_user']) or not 1<=peer['ansible_port']<=65535:
    raise SystemExit('Invalid projected inventory transport')
with open(output,'x',opener=lambda p,f:os.open(p,f,0o600)) as stream:json.dump(peer,stream)
print('Projected existing inventory peer: plex; no application deployment or secret lookup',flush=True)
PY
  if [[ "$mode" == negative-service ]]; then
    sudo -n "$python" "$repo/ansible/operator/haproxy-cutover.py" accept-native "$batch"
  fi
  sudo -n "$python" "$repo/ansible/operator/haproxy-cutover.py" "$mode" "$batch" "$output/peer.json"
) 2>&1 | tee -a "$log"
statuses=("${PIPESTATUS[@]}")
status=${statuses[0]}
if [[ "$status" = 0 ]]; then status=${statuses[1]}; fi
printf 'Negative acceptance exited with status %s\nPrivate log: %s\n' "$status" "$log" | tee -a "$log"
exit "$status"
