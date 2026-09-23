#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this bootstrap with sudo: sudo $0" >&2
  exit 1
fi

if [[ ! -r /etc/os-release ]]; then
  echo "Unable to identify this operating system." >&2
  exit 1
fi

# shellcheck disable=SC1091
source /etc/os-release

if [[ "${ID_LIKE:-}" != *debian* && "${ID:-}" != "debian" ]]; then
  echo "This bootstrap supports Debian-family workstations only." >&2
  exit 1
fi

apt-get update
apt-get install --yes ansible-core ca-certificates git python3 python3-apt sudo

cat <<'EOF'
Bootstrap complete. From the repository root, run:

  ansible-playbook -i localhost, ansible/workstation.yml --ask-become-pass --tags workstation
EOF
