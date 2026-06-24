#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-}"

if [[ -z "${ACTION}" ]]; then
  echo "Usage: $0 <fmt|init|upgrade|validate|plan|apply>"
  exit 1
fi

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

mapfile -t TOFU_DIRS < <(
  find "${ROOT_DIR}/terraform" \
    -path '*/.terraform' -prune -o \
    -name '*.tf' -printf '%h\n' |
    sort -u
)

if [[ "${#TOFU_DIRS[@]}" -eq 0 ]]; then
  echo "No OpenTofu directories found under ${ROOT_DIR}/terraform"
  exit 1
fi

for dir in "${TOFU_DIRS[@]}"; do
  rel="${dir#${ROOT_DIR}/}"

  echo
  echo "============================================================"
  echo "OpenTofu: ${rel}"
  echo "============================================================"

  case "${ACTION}" in
    fmt)
      tofu -chdir="${dir}" fmt -recursive
      ;;

    init)
      tofu -chdir="${dir}" init
      ;;

    upgrade)
      tofu -chdir="${dir}" init -upgrade
      ;;

    validate)
      tofu -chdir="${dir}" validate
      ;;

    plan)
      tofu -chdir="${dir}" plan
      ;;

    apply)
      tofu -chdir="${dir}" apply
      ;;

    *)
      echo "Unknown action: ${ACTION}"
      echo "Usage: $0 <fmt|init|upgrade|validate|plan|apply>"
      exit 1
      ;;
  esac
done