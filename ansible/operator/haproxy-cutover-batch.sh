#!/bin/bash
# Finite operator batch; local execution is restricted to the isolated fixture harness.
set -euo pipefail
umask 077
test "$#" = 2
operation="$1"
root_dir="$2"
case "$root_dir" in /*) ;; *) echo 'An absolute private directory is required' >&2; exit 2 ;; esac
case "$operation" in
  prepare) batch_dir="$root_dir/cutover-batch-04-tested" ;;
  resume|maintenance|continue|rollback) batch_dir="$root_dir" ;;
  *) echo 'Usage: haproxy-cutover-batch.sh prepare HANDOFF | resume PREPARED | maintenance PREPARED | continue PREPARED | rollback PREPARED' >&2; exit 2 ;;
esac
stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
log="$batch_dir/$operation-$stamp.log"
printf 'Private batch directory: %s\nPrivate output log: %s\n' "$batch_dir" "$log"
if [[ "$operation" == prepare ]]; then
  test ! -e "$batch_dir"
  mkdir -m 0700 "$batch_dir"
fi
test -d "$batch_dir"
test ! -e "$log" && test ! -L "$log"
exec 3>&1
(set -o noclobber; : >"$log")
exec >>"$log" 2>&1
repo="$(dirname "$(dirname "${PLAYBOOK:-/opt/homelab/ansible/playbook.yml}")")"
python="${VIRTUAL_ENV:-/opt/ansible/ansible-venv}/bin/python"
native=/usr/local/libexec/skynet-mgt-operator/mgt-operator.py
exclusion_started=false
deployment_started=false
policy_started=false
probe_unit=
continuation_armed=false

announce() { printf '%s\n' "$*"; printf '%s\n' "$*" >&3; }
review() {
  announce "$1"
  local quoted_log
  printf -v quoted_log '%q' "$log"
  announce "Append observed evidence (no credentials) with: printf '%s\\n' '<observed result>' >> $quoted_log"
  printf 'Type ACCEPT only after the stated evidence is recorded; anything else stops: ' >&3
  local response
  read -r response
  test "$response" = ACCEPT
}
haproxy_account() {
  sudo -u podman-haproxy -- env HOME="$HAPROXY_HOME" XDG_RUNTIME_DIR="/run/user/$HAPROXY_UID" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$HAPROXY_UID/bus" \
    /bin/sh -c 'cd "$HOME" || exit; exec "$@"' skynet-haproxy "$@"
}
require_ports_free() {
  local listeners family
  for family in 4 6; do
    listeners=$(sudo ss -H -lnt "-$family" '( sport = :5432 or sport = :18405 )')
    test -z "$listeners"
  done
}
require_haproxy_absent() {
  local load containers
  sudo test ! -e "$HAPROXY_HOME/.config/containers/systemd/haproxy.container"
  load=$(haproxy_account systemctl --user show haproxy.service --value -p LoadState)
  test "$load" = not-found
  containers=$(haproxy_account /usr/bin/podman --remote=false ps --all --filter name='^haproxy$' --format '{{.ID}}')
  test -z "$containers"
}
require_prepared_image() {
  local observed expected
  observed=$(haproxy_account /usr/bin/podman --remote=false image inspect "$HAPROXY_IMAGE" --format '{{.Id}}')
  expected=$(cat "$batch_dir/image-id")
  test -n "$expected" && test "$observed" = "$expected"
}
record_state() {
  declare -p exclusion_started policy_started deployment_started probe_unit >"$batch_dir/rollback-state.sh.tmp"
  mv "$batch_dir/rollback-state.sh.tmp" "$batch_dir/rollback-state.sh"
}
stop_probe() {
  if [[ -n "$probe_unit" ]]; then
    local load
    load=$(sudo systemctl show "$probe_unit" --value -p LoadState)
    if [[ "$load" != not-found ]]; then
      sudo systemctl stop "$probe_unit"
    fi
    probe_unit=
    record_state
  fi
}
rollback() {
  source "$batch_dir/recovery-env.sh"
  stop_probe
  if [[ "$deployment_started" == true ]]; then
    local load
    load=$(haproxy_account systemctl --user show haproxy.service --value -p LoadState)
    if [[ "$load" != not-found ]]; then haproxy_account systemctl --user stop haproxy.service; fi
    local containers
    containers=$(haproxy_account /usr/bin/podman --remote=false ps --filter name='^haproxy$' --format '{{.ID}}')
    if [[ -n "$containers" ]]; then
      # Exactly this account/name, never a store-wide lifecycle action.
      test "$(wc -w <<< "$containers")" = 1
      haproxy_account /usr/bin/podman --remote=false stop "$containers"
    fi
    local quadlet="$HAPROXY_HOME/.config/containers/systemd/haproxy.container"
    if sudo test -e "$quadlet"; then
      sudo test ! -L "$quadlet"
      test ! -e "$batch_dir/failed-haproxy.container"
      sudo mv "$quadlet" "$batch_dir/failed-haproxy.container"
      haproxy_account systemctl --user daemon-reload
    fi
    # Restore only the two recorded paths after withdrawing the new unit. A
    # changed/unexpected file or nonempty new directory stops rollback.
    sudo /usr/bin/python3 - "$HAPROXY_CONFIG_DIR" "$batch_dir" <<'PY'
import json,os,shutil,sys
from pathlib import Path
root=Path(sys.argv[1]); saved=Path(sys.argv[2]); cfg=root/'haproxy.cfg'
entries=json.loads((saved/'config-ownership.json').read_text())
if len(entries)!=2 or {e['path'] for e in entries}!={str(root),str(cfg)}:
    raise SystemExit('ownership manifest does not match the exact configuration paths')
if root.is_symlink() or cfg.is_symlink(): raise SystemExit('unexpected configuration symlink')
original={e['path']:e for e in entries}
allowed=[(saved/'haproxy.cfg').read_bytes()]
if not original[str(cfg)].get('absent'): allowed.append((saved/'haproxy-before.cfg').read_bytes())
if cfg.exists() and cfg.read_bytes() not in allowed:
    raise SystemExit('configuration changed outside this handoff; stop before overwriting')
for path in [cfg,root]:
    e=original[str(path)]
    if e.get('absent'):
        if path.exists(): path.unlink() if path==cfg else path.rmdir()
    else:
        if path==cfg: shutil.copyfile(saved/'haproxy-before.cfg',path)
        os.chown(path,e['uid'],e['gid']); os.chmod(path,int(e['mode'],8))
PY
    deployment_started=false
    record_state
  fi
  local placement
  placement=$(sudo /usr/bin/python3 - "$batch_dir/provider-before.json" "$RECORDED_MGT_EXCLUSION" \
    "$policy_started" "$deployment_started" <<'PY'
import ipaddress,json,re,subprocess,sys
from pathlib import Path
original=json.loads(Path(sys.argv[1]).read_text()); exclusion=sys.argv[2]
docker=['docker','--host','unix:///var/run/docker.sock']
def query(argv):
    result=subprocess.run(argv,text=True,capture_output=True,check=False)
    if result.returncode: raise SystemExit('rollback inspection failed: '+result.stderr.strip())
    return result.stdout
projection='{"id":{{json .ID}},"vips":{{json .Endpoint.VirtualIPs}},"name":{{json .Spec.Name}},"image":{{json .Spec.TaskTemplate.ContainerSpec.Image}},"constraints":{{json .Spec.TaskTemplate.Placement.Constraints}},"configs":{{json .Spec.TaskTemplate.ContainerSpec.Configs}},"ports":{{json .Endpoint.Spec.Ports}}}'
current=json.loads(query(docker+['service','inspect','--format',projection,original['name']]))
for field in ['id','name','image','configs','ports','vips']:
    if current[field]!=original[field]: raise SystemExit('rollback provider '+field+' changed; refusing placement restoration')
before=set(original.get('constraints') or []); now=set(current.get('constraints') or [])
if exclusion in before or now-before not in [set(),{exclusion}] or before-now:
    raise SystemExit('rollback constraints changed outside this handoff')
if exclusion not in now:
    print('unchanged')
elif sys.argv[3:]==['false','false']:
    # A partially applied exclusion can leave the ORIGINAL task/proxy alive.
    # Permit only that exact current service's Docker proxy, never a new listener.
    lines=query(['ss','-Hlnpt','( sport = :5432 or sport = :18405 )']).splitlines()
    if lines:
        ids=query(docker+['ps','--filter','label=com.docker.swarm.service.id='+original['id'],'--format','{{.ID}}']).split()
        addresses=set()
        for identity in ids:
            if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}',identity): raise SystemExit('invalid original task identity')
            fmt='{"pid":{{.State.Pid}},"service":{{json (index .Config.Labels "com.docker.swarm.service.id")}},"addresses":[{{range $i,$n := .NetworkSettings.Networks}}{{if $i}},{{end}}{{json $n.IPAddress}}{{end}}]}'
            record=json.loads(query(docker+['inspect','--format',fmt,identity]))
            if record['pid']<=0 or record['service']!=original['id']: raise SystemExit('original local task identity changed')
            addresses.update(a for a in record['addresses'] if a)
        for line in lines:
            local=line.split()[3]; address,port=local.rsplit(':',1)
            owners=re.findall(r'pid=(\d+)',line)
            if port!='5432' or not owners: raise SystemExit('unqualified competing listener blocks placement restoration')
            for owner in owners:
                process=Path('/proc')/owner
                if (process/'comm').read_text().strip()!='docker-proxy':
                    raise SystemExit('competing listener is not the original Docker proxy')
                argv=(process/'cmdline').read_bytes().decode().split('\0')
                if Path(argv[0]).name!='docker-proxy':
                    raise SystemExit('competing listener is not the original Docker proxy')
                options=dict(zip(argv[1::2],argv[2::2]))
                host=address.strip('[]')
                if host=='*': host=options.get('-host-ip','')
                if (options.get('-proto')!='tcp' or options.get('-host-port')!='5432'
                    or options.get('-container-port')!='5432' or options.get('-container-ip') not in addresses
                    or ipaddress.ip_address(options['-host-ip'])!=ipaddress.ip_address(host)):
                    raise SystemExit('competing listener does not match the exact original task publication')
    print('present')
else:
    print('present')
PY
  )
  # If policy/deployment began, always withdraw every new listener before
  # restoring policy/placement. An unchanged failed exclusion needs no write.
  if [[ "$policy_started" == true || "$deployment_started" == true ]]; then require_ports_free; fi
  if [[ "$policy_started" == true ]]; then
    sudo /usr/bin/python3 "$native" recovery /bin/bash "$batch_dir/haproxy-policy-rollback.sh" "$batch_dir"
    policy_started=false
    record_state
  fi
  if [[ "$exclusion_started" == true ]]; then
    if [[ "$placement" == present ]]; then
      sudo /usr/bin/python3 "$native" recovery /usr/bin/docker --host unix:///var/run/docker.sock \
        service update --constraint-rm "$RECORDED_MGT_EXCLUSION" "$RECORDED_HAPROXY_SERVICE"
    fi
    exclusion_started=false
    record_state
    sudo docker --host unix:///var/run/docker.sock service ps "$RECORDED_HAPROXY_SERVICE" \
      --filter desired-state=running --format '{{.ID}} {{.Node}} {{.CurrentState}}'
  fi
  announce 'Scoped rollback commands completed. Verify original mgt/worker tasks, VIP/config and application recovery.'
}
finish() {
  local status=$?
  trap - EXIT
  # Terminal/log output failures must never prevent rollback or replace status.
  set +e
  if [[ "$status" == 0 ]]; then
    cat "$log" >&3
    status=$?
  fi
  if [[ ( "$operation" == maintenance || ( "$operation" == continue && "$continuation_armed" == true ) ) && "$status" != 0 && "$exclusion_started" == true ]]; then
    announce "Maintenance failed (status $status); applying the recorded scoped offline rollback."
    # A failed rollback stops immediately; never continue to placement removal
    # after an unsafe listener/policy state. Preserve the original failure status.
    local rollback_runner="$batch_dir/haproxy-cutover-batch.sh"
    if [[ "$operation" == continue ]]; then rollback_runner="$repo/ansible/operator/haproxy-cutover-batch.sh"; fi
    /bin/bash "$rollback_runner" rollback "$batch_dir"
    local rollback_status=$?
    if [[ "$rollback_status" != 0 ]]; then
      announce 'ROLLBACK INCOMPLETE: use the saved runbook/console; do not proceed or flush rules.'
    fi
  fi
  if [[ "$status" != 0 ]]; then cat "$log" >&3 || true; fi
  exit "$status"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

collect() {
  local output="$1" stage="$2"
  local file
  for file in "$output" "$output.metadata.json" "$output.pending.json" "$stage"; do
    test ! -e "$file" && test ! -L "$file"
  done
  local -a capture_args=()
  if [[ -n "${HAPROXY_ROUTE_CAPTURE_FILE:-}" ]]; then
    test -r "$HAPROXY_ROUTE_CAPTURE_FILE"
    capture_args+=(-e "haproxy_preflight_capture_metadata=$HAPROXY_ROUTE_CAPTURE_FILE")
  fi
  if [[ "$operation" == resume ]]; then
    capture_args+=(-e '{"haproxy_preflight_window_seconds":180,"haproxy_preflight_sample_interval":0.5}')
    if [[ -n "${HAPROXY_ROUTE_CAPTURE_CALLERS:-}" ]]; then
      local selection
      selection=$("$python" -c 'import json,os; names=json.loads(os.environ["HAPROXY_ROUTE_CAPTURE_CALLERS"]); assert isinstance(names,list) and names and all(isinstance(n,str) and n for n in names), "capture callers must be a nonempty JSON list of names"; print(json.dumps({"haproxy_preflight_capture_callers":names}))')
      capture_args+=(-e "$selection")
    fi
  fi
  export ANSIBLE_LOG_PATH="$output.ansible.log"
  announce "Metadata output: $output; Ansible log: $ANSIBLE_LOG_PATH; inventory projection: $stage"
  local policy_inputs="$batch_dir/policy-before-inputs.json"
  [[ -f "$policy_inputs" ]] || policy_inputs="$batch_dir/homepage-inputs.yml"
  PLAYBOOK="$repo/ansible/operations.yml" skynet raw --tags haproxy_preflight \
    -e "@$policy_inputs" \
    -e "haproxy_preflight_output=$output" -e "haproxy_preflight_stage_output=$stage" "${capture_args[@]}"
}

deploy_and_accept() {
  "$python" "$batch_dir/haproxy-cutover.py" deployment "$batch_dir/deployment-inputs.json" live
  require_prepared_image
  stop_probe
  require_ports_free
  PLAYBOOK="$repo/ansible/playbook.yml" skynet raw --check --tags deploy,mgt-haproxy -e "@$batch_dir/deployment-inputs.json"
  require_ports_free
  deployment_started=true
  # Record partial deployment before calling its lifecycle operation.
  record_state
  PLAYBOOK="$repo/ansible/playbook.yml" skynet raw --tags deploy,mgt-haproxy -e "@$batch_dir/deployment-inputs.json"
  haproxy_account systemctl --user status haproxy.service --no-pager
  sudo /usr/bin/python3 /etc/skynet-mgt-firewall/policy.py check
  sudo "$python" "$batch_dir/haproxy-cutover.py" accept "$batch_dir/working-policy.json" "$batch_dir/stage.json"
  review 'Complete batched real application DB activity (including idle declarations), Forgejo recovery at its unchanged destination, Prometheus /metrics scraping and normal internal HTTPS; repeat allowed/denied access against actual HAProxy. Record evidence before ACCEPT.'
  haproxy_account systemctl --user restart haproxy.service
  sudo /usr/bin/python3 /etc/skynet-mgt-firewall/policy.py check
  sudo "$python" "$batch_dir/haproxy-cutover.py" accept "$batch_dir/working-policy.json" "$batch_dir/stage.json"
  review 'Repeat the focused HAProxy-unit identity/source/application/firewall checks after this named restart. Reuse Homepage lifecycle evidence; defer coordinated reboot. Record final HAProxy acceptance before ACCEPT.'
  announce 'Maintenance sequence completed; retain saved Homepage/rollback material and current Docker caller bindings.'
}

if [[ "$operation" == prepare ]]; then
  for required in sudo skynet getent docker systemctl systemd-run nsenter runuser ip ss iptables iptables-save; do
    if ! command -v "$required" >/dev/null; then
      printf 'Required operator command unavailable: %s\n' "$required" >&2
      exit 1
    fi
  done
  test -x /usr/bin/python3 && test -x /usr/bin/podman && test -x /usr/bin/editor && test -x /usr/bin/less
  for file in homepage-inputs.yml homepage-policy.py homepage-policy.json \
    native-hooks-20261008T145711Z-1717643.log \
    haproxy-candidate-04-20261008T150348Z-1717643.json \
    haproxy-candidate-04-20261008T150348Z-1717643.json.metadata.json \
    haproxy-candidate-04-20261008T150348Z-1717643.json.pending.json; do
    install -m 0600 "$root_dir/$file" "$batch_dir/$file"
  done
  for file in haproxy-cutover.py haproxy-cutover-batch.sh haproxy-policy-rollback.sh mgt-operator.py \
    prepare-native-operator.sh skynet_pg_prepare.slice skynet_pg_recovery.slice; do
    install -m 0600 "$repo/ansible/operator/$file" "$batch_dir/$file"
  done
  cp "$repo/migrator/guides/haproxy.md" "$batch_dir/haproxy-mgt-cutover.md"
  cp "$repo/docs/mgt-native-operator.md" "$batch_dir/"
  cd "$batch_dir"
  sudo /usr/bin/python3 "$native" check
  sudo /usr/bin/python3 /etc/skynet-mgt-firewall/policy.py check
  # Capture the complete installed baseline; Homepage evidence remains scoped.
  sudo cat /etc/skynet-mgt-firewall/policy.py >"$batch_dir/policy-before.py"
  sudo cat /etc/skynet-mgt-firewall/policy.json >"$batch_dir/policy-before.json"
  sudo cmp /etc/skynet-mgt-firewall/policy.py "$batch_dir/policy-before.py"
  sudo cmp /etc/skynet-mgt-firewall/policy.json "$batch_dir/policy-before.json"
  "$python" "$batch_dir/haproxy-cutover.py" baseline-inputs "$batch_dir"
  collect "$batch_dir/before.json" "$batch_dir/stage.json"
  "$python" "$batch_dir/haproxy-cutover.py" working "$batch_dir" "$batch_dir/before.json" \
    "$batch_dir/before.json.metadata.json" "$batch_dir"
  "$python" "$batch_dir/haproxy-cutover.py" render "$batch_dir/stage.json" "$batch_dir/haproxy.cfg"
  HAPROXY_ENTRY=$(getent passwd podman-haproxy)
  IFS=: read -r _ _ HAPROXY_UID HAPROXY_GID _ HAPROXY_HOME _ <<< "$HAPROXY_ENTRY"
  test "$HAPROXY_UID" = 1011
  require_haproxy_absent
  prepared_vars=$("$python" - "$batch_dir/stage.json" "$batch_dir/before.json.metadata.json" <<'PY'
import json,shlex,sys,re
s=json.load(open(sys.argv[1])); reports=json.load(open(sys.argv[2]))
m=next(r for r in reports if r['host']==s['controller'])
p=m['providers']; assert len(p)==1, 'one exact observed HAProxy provider required'
p=p[0]; image=s['definition']['image']; digest=p['image'].split('@')[-1]
with open(sys.argv[1].removesuffix('stage.json')+'provider-collected.json','x') as f: json.dump(p,f)
assert re.fullmatch(r'sha256:[0-9a-f]{64}',digest), 'observed pinned image digest required'
normalize=lambda v:v.removeprefix('docker.io/library/').removeprefix('docker.io/')
assert normalize(p['image'].split('@')[0])==normalize(image), 'catalog/current image mismatch; do not upgrade'
assert [c['ConfigName'] for c in p['configs']]==['haproxy_cfg-3b164cbae242'], 'native config reference changed'
constraint='node.labels.ansible_host != '+s['controller']
assert constraint not in (p['constraints'] or []), 'exclusion already exists; reconcile previous handoff first'
for key,value in {'HAPROXY_IMAGE':image,'HAPROXY_DIGEST':digest,'HAPROXY_CONFIG_DIR':s['definition']['paths'][0]['path'],
                  'RECORDED_HAPROXY_SERVICE':p['name'],'RECORDED_HAPROXY_ID':p['id'],'RECORDED_MGT_EXCLUSION':constraint,
                  'MGT_NODE_ID':m['topology']['swarm']['node_id'],'MGT_ADDRESS':s['policy']['inventory_address']}.items():
    print(key+'='+shlex.quote(value))
PY
  )
  eval "$prepared_vars"
  sudo "$python" "$batch_dir/haproxy-cutover.py" provider "$RECORDED_HAPROXY_SERVICE" >"$batch_dir/provider-before.json"
  controller=$("$python" -c 'import json,sys;print(json.load(open(sys.argv[1]))["controller"])' "$batch_dir/stage.json")
  "$python" "$batch_dir/haproxy-cutover.py" continuity "$batch_dir/provider-collected.json" "$batch_dir/provider-before.json" "$controller" no
  node_host=$(sudo docker --host unix:///var/run/docker.sock node inspect "$MGT_NODE_ID" --format '{{index .Spec.Labels "ansible_host"}}')
  test "$node_host" = "$controller"
  # Record only the two actual config paths. Do not chown/create the application tree.
  sudo /usr/bin/python3 - "$HAPROXY_CONFIG_DIR" >"$batch_dir/config-ownership.json" <<'PY'
import json,sys,stat
from pathlib import Path
root=Path(sys.argv[1]); result=[]
for path in [root,root/'haproxy.cfg']:
    if path.is_symlink(): raise SystemExit('config path is a symlink; resolve ownership before cutover')
    try: s=path.stat()
    except FileNotFoundError: result.append({'path':str(path),'absent':True}); continue
    if not (stat.S_ISDIR(s.st_mode) if path==root else stat.S_ISREG(s.st_mode)):
        raise SystemExit('unexpected configuration path type; stop before interruption')
    result.append({'path':str(path),'uid':s.st_uid,'gid':s.st_gid,'mode':oct(stat.S_IMODE(s.st_mode))})
print(json.dumps(result))
PY
  if sudo test -f "$HAPROXY_CONFIG_DIR/haproxy.cfg"; then
    sudo install -m 0600 -o "$(id -u)" -g "$(id -g)" "$HAPROXY_CONFIG_DIR/haproxy.cfg" "$batch_dir/haproxy-before.cfg"
  fi
  # Exact identity and access metadata only; no environments or container configs.
  sudo docker --host unix:///var/run/docker.sock ps -q | while read -r container; do
    sudo docker --host unix:///var/run/docker.sock inspect --format '{"id":{{json .Id}},"name":{{json .Name}},"swarm":{{json (index .Config.Labels "com.docker.swarm.service.name")}},"project":{{json (index .Config.Labels "com.docker.compose.project")}},"service":{{json (index .Config.Labels "com.docker.compose.service")}},"mounts":[{{range $i,$m := .Mounts}}{{if $i}},{{end}}{"type":{{json $m.Type}},"source":{{json $m.Source}},"destination":{{json $m.Destination}},"rw":{{json $m.RW}}}{{end}}]}' "$container"
  done >"$batch_dir/current-mounts.jsonl"
  "$python" "$batch_dir/haproxy-cutover.py" mounts "$HAPROXY_CONFIG_DIR" "$batch_dir/current-mounts.jsonl"
  HAPROXY_STAGE_DIR="$HAPROXY_HOME/$(basename "$batch_dir")-$stamp"
  sudo test ! -e "$HAPROXY_STAGE_DIR"
  sudo install -d -m 0700 -o "$HAPROXY_UID" -g "$HAPROXY_GID" "$HAPROXY_STAGE_DIR"
  sudo install -m 0600 -o "$HAPROXY_UID" -g "$HAPROXY_GID" "$batch_dir/haproxy.cfg" "$HAPROXY_STAGE_DIR/haproxy.cfg"
  haproxy_account /usr/bin/podman --remote=false pull "$HAPROXY_IMAGE@$HAPROXY_DIGEST"
  haproxy_account /usr/bin/podman --remote=false tag "$HAPROXY_IMAGE@$HAPROXY_DIGEST" "$HAPROXY_IMAGE"
  haproxy_account /usr/bin/podman --remote=false image inspect "$HAPROXY_IMAGE" --format '{{.Id}}' >"$batch_dir/image-id"
  haproxy_account /usr/bin/podman --remote=false run --rm --pull=never --network=none \
    --userns=keep-id:uid=99,gid=99 --user=99:99 -v "$HAPROXY_STAGE_DIR:/usr/local/etc/haproxy:ro" \
    "$HAPROXY_IMAGE" haproxy -c -f /usr/local/etc/haproxy/haproxy.cfg
  {
    declare -p HAPROXY_UID HAPROXY_GID HAPROXY_HOME HAPROXY_IMAGE HAPROXY_DIGEST HAPROXY_CONFIG_DIR \
      HAPROXY_STAGE_DIR RECORDED_HAPROXY_SERVICE RECORDED_HAPROXY_ID RECORDED_MGT_EXCLUSION MGT_NODE_ID MGT_ADDRESS
  } >"$batch_dir/recovery-env.sh"
  bash -n "$batch_dir/recovery-env.sh"
  # No credentials/config values are read. This explicitly replaces ONLY these callers.
  sudo "$python" "$batch_dir/haproxy-cutover.py" hooks "$batch_dir/working-policy.json" "$batch_dir/stage.json" \
    autobrr gotify vaultwarden infisical authelia seerr prometheus forgejo
  review "Trigger normal DB-backed activity using the existing Romm, Authelia, Seerr and Infisical interfaces. Fresh numeric destinations will be recorded by the next collector at $batch_dir/after.json.metadata.json. No environments or credentials."
  collect "$batch_dir/after.json" "$batch_dir/after-stage.json"
  review "Review: /usr/bin/less '$log' and /usr/bin/less '$batch_dir/config-ownership.json'. Edit only evidenced mgt verified/restart_verified/physdev_verified with: /usr/bin/editor '$batch_dir/working-policy.json'. Accept only proved ownership with: /usr/bin/editor '$batch_dir/deployment-inputs.json'. Worker route flags and overall verification stay false; backend ACL stays false."
  # This may report concrete dependency/confirmation blockers. No placement was changed.
  "$python" "$batch_dir/haproxy-cutover.py" ready "$batch_dir/working-policy.json" "$batch_dir/after.json.metadata.json" "$batch_dir/stage.json"
  "$python" "$batch_dir/haproxy-cutover.py" deployment "$batch_dir/deployment-inputs.json" pre
  export ANSIBLE_LOG_PATH="$batch_dir/deployment-plan-$stamp.ansible.log"
  announce "Read-only HAProxy deployment plan; Ansible log: $ANSIBLE_LOG_PATH"
  PLAYBOOK="$repo/ansible/playbook.yml" skynet raw --check --tags deploy,mgt-haproxy -e "@$batch_dir/deployment-inputs.json"
  announce 'Repository inputs and observed pre-window prerequisites passed. Placement, complete policy, runtime and application acceptance remain pending.'
  announce "Next maintenance command: /bin/bash $batch_dir/haproxy-cutover-batch.sh maintenance $batch_dir"
elif [[ "$operation" == resume ]]; then
  # Existing accepted files are inputs, never regenerated or promoted here.
  cd "$batch_dir"
  helper="$repo/ansible/operator/haproxy-cutover.py"
  "$python" "$helper" homepage "$batch_dir/working-policy.json" "$batch_dir/homepage-inputs.yml"
  "$python" "$helper" deployment "$batch_dir/deployment-inputs.json" pre
  "$python" "$helper" preconditions "$batch_dir/working-policy.json" "$batch_dir/after.json.metadata.json" "$batch_dir/stage.json"
  input_hashes=$(sha256sum "$batch_dir/working-policy.json" "$batch_dir/deployment-inputs.json")
  output="$batch_dir/route-capture-$stamp.json"
  stage="$batch_dir/route-capture-stage-$stamp.json"
  announce "Starting simultaneous 180-second host windows. Selected callers: ${HAPROXY_ROUTE_CAPTURE_CALLERS:-all declared PostgreSQL callers}. Trigger their normal DB-backed activity NOW; do not restart/replace callers."
  if [[ -n "${HAPROXY_ROUTE_CAPTURE_FILE:-}" ]]; then
    announce "Retained route evidence: $HAPROXY_ROUTE_CAPTURE_FILE (fresh identities and provider mapping required)."
  fi
  # Visible progress while retaining stderr/stdout in the private batch log.
  collect "$output" "$stage" 2>&1 | tee /dev/fd/3 &
  capture_pid=$!
  while kill -0 "$capture_pid" 2>/dev/null; do
    announce "Route capture running; private Ansible log: $output.ansible.log"
    sleep 5
  done
  wait "$capture_pid"
  test "$(sha256sum "$batch_dir/working-policy.json" "$batch_dir/deployment-inputs.json")" = "$input_hashes"
  "$python" "$helper" resume "$batch_dir" "$output.metadata.json" "$stage" "$batch_dir/resume-$stamp.json"
  source "$batch_dir/recovery-env.sh"
  sudo "$python" "$helper" provider "$RECORDED_HAPROXY_SERVICE" >"$batch_dir/provider-resume-$stamp.json"
  controller=$("$python" -c 'import json,sys;print(json.load(open(sys.argv[1]))["controller"])' "$batch_dir/stage.json")
  "$python" "$helper" continuity "$batch_dir/provider-before.json" "$batch_dir/provider-resume-$stamp.json" "$controller" no
  export ANSIBLE_LOG_PATH="$batch_dir/deployment-plan-resume-$stamp.ansible.log"
  announce "Read-only HAProxy deployment plan; Ansible log: $ANSIBLE_LOG_PATH"
  PLAYBOOK="$repo/ansible/playbook.yml" skynet raw --check --tags deploy,mgt-haproxy -e "@$batch_dir/deployment-inputs.json"
  test "$(sha256sum "$batch_dir/working-policy.json" "$batch_dir/deployment-inputs.json")" = "$input_hashes"
  announce 'Resume gates passed; no placement, policy, image or caller lifecycle changes were made. Worker-only acceptance remains placement-dependent.'
  announce "Maintenance command (separate window): HAPROXY_ROUTE_CAPTURE_FILE='$output.metadata.json' PLAYBOOK='$repo/ansible/playbook.yml' /bin/bash '$repo/ansible/operator/haproxy-cutover-batch.sh' maintenance '$batch_dir'"
elif [[ "$operation" == rollback ]]; then
  # Replay only the transitions recorded before potentially partial operations.
  source "$batch_dir/recovery-env.sh"
  source "$batch_dir/rollback-state.sh"
  rollback
elif [[ "$operation" == continue ]]; then
  cd "$batch_dir"
  helper="$repo/ansible/operator/haproxy-cutover.py"
  # Check the producer before consuming its strictly validated assignments.
  continued_state=$("$python" "$helper" continuation-state "$batch_dir")
  eval "$continued_state"
  source "$batch_dir/recovery-env.sh"
  export PLAYBOOK="$repo/ansible/playbook.yml"
  export ANSIBLE_LOG_PATH="$batch_dir/continue-$stamp.ansible.log"
  announce "Ansible log: $ANSIBLE_LOG_PATH"
  sudo /usr/bin/python3 "$native" check
  sudo "$python" "$helper" continuation-policy "$batch_dir"
  controller=$("$python" -c 'import json,sys;print(json.load(open(sys.argv[1]))["controller"])' "$batch_dir/stage.json")
  sudo "$python" "$helper" provider "$RECORDED_HAPROXY_SERVICE" >"$batch_dir/provider-continue-$stamp.json"
  "$python" "$helper" continuity "$batch_dir/provider-before.json" "$batch_dir/provider-continue-$stamp.json" "$controller" yes
  require_haproxy_absent
  require_prepared_image
  if [[ -n "$probe_unit" ]]; then
    sudo "$python" "$helper" stop-probe "$batch_dir" "$probe_unit"
    probe_unit=
    record_state
  fi
  require_ports_free
  # Guard failures above do not replay unsafe rollback against incompatible state.
  continuation_armed=true
  announce 'Continuation guards passed; entering only HAProxy deployment and remaining live acceptance.'
  deploy_and_accept
else
  cd "$batch_dir"
  source "$batch_dir/recovery-env.sh"
  export MGT_FIREWALL_VARS_FILE="$batch_dir/working-policy.json"
  export PLAYBOOK="$repo/ansible/playbook.yml"
  export ANSIBLE_LOG_PATH="$batch_dir/maintenance-$stamp.ansible.log"
  announce "Ansible log: $ANSIBLE_LOG_PATH"
  sudo /usr/bin/python3 "$native" check
  sudo /usr/bin/python3 /etc/skynet-mgt-firewall/policy.py check
  sudo cmp /etc/skynet-mgt-firewall/policy.json "$batch_dir/policy-before.json"
  sudo cmp /etc/skynet-mgt-firewall/policy.py "$batch_dir/policy-before.py"
  "$python" "$batch_dir/haproxy-cutover.py" homepage "$batch_dir/working-policy.json" "$batch_dir/homepage-inputs.yml"
  collect "$batch_dir/window-before-$stamp.json" "$batch_dir/window-stage-$stamp.json"
  # No changed settings/inventory/config path may reuse previous preparation.
  "$python" - "$batch_dir/stage.json" "$batch_dir/window-stage-$stamp.json" <<'PY'
import json,sys
a,b=[json.load(open(p)) for p in sys.argv[1:]]
for key in ['definition','render','controller','workers']:
    if a[key]!=b[key]: raise SystemExit('prepared inventory/definition changed; repeat preparation before placement')
PY
  "$python" "$batch_dir/haproxy-cutover.py" ready "$batch_dir/working-policy.json" \
    "$batch_dir/window-before-$stamp.json.metadata.json" "$batch_dir/stage.json"
  "$python" "$batch_dir/haproxy-cutover.py" deployment "$batch_dir/deployment-inputs.json" pre
  require_haproxy_absent
  sudo "$python" "$batch_dir/haproxy-cutover.py" provider "$RECORDED_HAPROXY_SERVICE" >"$batch_dir/provider-window-before-$stamp.json"
  controller=$("$python" -c 'import json,sys;print(json.load(open(sys.argv[1]))["controller"])' "$batch_dir/stage.json")
  "$python" "$batch_dir/haproxy-cutover.py" continuity "$batch_dir/provider-before.json" "$batch_dir/provider-window-before-$stamp.json" "$controller" no
  require_prepared_image
  review 'Confirm one maintenance window: exclude ONLY mgt HAProxy, preserve workers/VIP/native config, then staged policy/listener acceptance. Named HAProxy restart only; no host reboot/Docker restart.'
  exclusion_started=true
  record_state
  sudo docker --host unix:///var/run/docker.sock service update --constraint-add "$RECORDED_MGT_EXCLUSION" "$RECORDED_HAPROXY_SERVICE"
  collect "$batch_dir/worker-only-$stamp.json" "$batch_dir/worker-stage-$stamp.json"
  sudo "$python" "$batch_dir/haproxy-cutover.py" provider "$RECORDED_HAPROXY_SERVICE" >"$batch_dir/provider-worker-only-$stamp.json"
  "$python" "$batch_dir/haproxy-cutover.py" continuity "$batch_dir/provider-before.json" "$batch_dir/provider-worker-only-$stamp.json" "$controller" yes
  "$python" "$batch_dir/haproxy-cutover.py" routes "$batch_dir/working-policy.json" \
    "$batch_dir/worker-only-$stamp.json" "$batch_dir/worker-only-$stamp.json.metadata.json" "$batch_dir/stage.json"
  review "Verify worker-only placement, unchanged VIP/image/native config and ALL DB-backed application routes. Review: /usr/bin/less '$batch_dir/worker-route-proposal.json'. Merge only evidenced worker route_verified/verified/restart_verified entries and complete overall verification with: /usr/bin/editor '$batch_dir/working-policy.json'. Unresolved/idle clients STOP."
  "$python" "$batch_dir/haproxy-cutover.py" homepage "$batch_dir/working-policy.json" "$batch_dir/homepage-inputs.yml"
  export ANSIBLE_LOG_PATH="$batch_dir/maintenance-$stamp.ansible.log"
  require_ports_free
  skynet check mgt-firewall
  "$python" "$batch_dir/haproxy-cutover.py" retained-policy "$batch_dir"
  sudo cmp /etc/skynet-mgt-firewall/policy.json "$batch_dir/policy-before.json"
  sudo cmp /etc/skynet-mgt-firewall/policy.py "$batch_dir/policy-before.py"
  policy_started=true
  record_state
  skynet update mgt-firewall
  sudo /usr/bin/python3 /etc/skynet-mgt-firewall/policy.py check
  require_ports_free
  probe_candidate="skynet-haproxy-acceptance-$stamp-$(cat /proc/sys/kernel/random/uuid).service"
  test "$(sudo systemctl show "$probe_candidate" --value -p LoadState)" = not-found
  probe_unit="$probe_candidate"
  record_state
  sudo systemd-run --quiet --collect --unit="$probe_unit" --slice=skynet_pg_recovery.slice \
    --property=User=root --property=UMask=0077 --property=RuntimeMaxSec=240 \
    /usr/bin/python3 "$batch_dir/haproxy-cutover.py" listen 5432 18405
  sleep 2
  sudo systemctl is-active --quiet "$probe_unit"
  sudo "$python" "$batch_dir/haproxy-cutover.py" accept "$batch_dir/working-policy.json" "$batch_dir/stage.json"
  for context in controller recovery; do
    for port in 5432; do
      sudo /usr/bin/python3 "$native" probe "$context" "$MGT_ADDRESS" "$port" 0
    done
  done
  review "Within the bounded handshake-only probe: prove qualified callers/native contexts ALLOWED; another LAN host, Tailscale IPv4/IPv6, alternate mgt addresses and unrelated local root DENIED at both ports. A refusal/no listener is not proof. Record hooks/counters in '$log'; complete only the proved services_mgt_backend_acl_ready with: /usr/bin/editor '$batch_dir/deployment-inputs.json'."
  sudo systemctl is-active --quiet "$probe_unit"
  sudo "$python" "$batch_dir/haproxy-cutover.py" accept "$batch_dir/working-policy.json" "$batch_dir/stage.json"
  deploy_and_accept
fi
