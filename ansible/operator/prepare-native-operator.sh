#!/bin/bash
# Managed by skynet mgt operator contexts; run only in an authorized operator window.
set -euo pipefail
umask 077
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
install_dir=/usr/local/libexec/skynet-mgt-operator
case "${1:-}" in
  "") test "$EUID" = 0 ;;
  --check) test "$#" = 1 ;;
  *) echo "usage: $0 [--check]" >&2; exit 2 ;;
esac
# Check ALL existing destinations before writes; never replace an unowned collision.
/usr/bin/python3 - <<'PY'
from pathlib import Path
import stat
import sys
def require(condition, message):
    if not condition:
        sys.exit(message)
root = Path('/usr/local/libexec/skynet-mgt-operator')
paths = [(Path('/etc/systemd/system') / name, b'# Managed by skynet mgt operator contexts\n')
         for name in ['skynet_pg_prepare.slice', 'skynet_pg_recovery.slice']]
paths += [(root / 'mgt-operator.py', b'#!/usr/bin/python3\n"""Managed by skynet mgt operator contexts')]
if root.exists() or root.is_symlink():
    info = root.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == info.st_gid == 0 and not info.st_mode & 0o022, 'unowned operator directory')
for path, marker in paths:
    if path.exists() or path.is_symlink():
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 0 and not info.st_mode & 0o022, 'unowned destination: ' + str(path))
        require(path.read_bytes().startswith(marker), 'unowned destination: ' + str(path))
alias = root / 'postgres-python'
if alias.exists() or alias.is_symlink():
    require(alias.is_symlink() and alias.lstat().st_uid == alias.lstat().st_gid == 0 and str(alias.readlink()) == 'mgt-operator.py', 'unowned interpreter alias')
PY
for source in mgt-operator.py skynet_pg_prepare.slice skynet_pg_recovery.slice; do
  test -f "$source_dir/$source"
done
if [[ "${1:-}" == --check ]]; then
  echo "Plan: prepare only two owned persistent slices and the native operator interpreter; no writes"
  exit 0
fi
install -d -m 0755 -o root -g root "$install_dir"
install -m 0755 -o root -g root "$source_dir/mgt-operator.py" "$install_dir/mgt-operator.py"
ln -sfn mgt-operator.py "$install_dir/postgres-python"
for unit in skynet_pg_prepare.slice skynet_pg_recovery.slice; do
  install -m 0644 -o root -g root "$source_dir/$unit" "/etc/systemd/system/$unit"
done
systemctl daemon-reload
systemctl enable --now skynet_pg_prepare.slice skynet_pg_recovery.slice
/usr/bin/python3 "$install_dir/mgt-operator.py" check
