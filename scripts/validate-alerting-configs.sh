#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${OUT_DIR:-$(mktemp -d)}"
PROM_IMAGE="${PROM_IMAGE:-prom/prometheus:v3.12.0}"
ALERTMANAGER_IMAGE="${ALERTMANAGER_IMAGE:-prom/alertmanager:v0.32.2}"

cleanup() {
  if [[ "${KEEP_RENDERED:-0}" != "1" ]]; then
    rm -rf "${OUT_DIR}"
  else
    echo "Rendered configs kept at ${OUT_DIR}"
  fi
}
trap cleanup EXIT

mkdir -p "${OUT_DIR}/rules"
export ROOT_DIR OUT_DIR

python3 - <<'PY'
import os
from pathlib import Path

from jinja2 import Environment
import yaml

root = Path(os.environ["ROOT_DIR"])
out = Path(os.environ["OUT_DIR"])
env = Environment()


def render(src: Path, dest: Path) -> None:
    rendered = env.from_string(src.read_text()).render()
    yaml.safe_load(rendered)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(rendered)


# Basic YAML validation for service definitions that affect the alerting stack.
# The Jinja expressions in these files are YAML scalar values, so raw parsing is
# sufficient here. This is a syntax check, not full schema validation.
for service_yaml in [
    root / "ansible/group_vars/all/services/alertmanager.yml",
    root / "ansible/group_vars/all/services/prometheus.yml",
]:
    yaml.safe_load(service_yaml.read_text())

render(
    root / "ansible/roles/docker_services/templates/configs/prometheus.yml.j2",
    out / "prometheus.yml",
)
render(
    root / "ansible/roles/docker_services/templates/configs/alertmanager/alertmanager.yml.j2",
    out / "alertmanager.yml",
)

rules_dir = root / "ansible/roles/docker_services/templates/configs/prometheus/rules"
for src in sorted(rules_dir.glob("*.yml.j2")):
    render(src, out / "rules" / src.name.removesuffix(".j2"))

# The deployed Prometheus config intentionally points at /etc/prometheus/rules/*.yml.
# For validation, write local/Docker variants whose rule_files path points at the
# rendered rule files in OUT_DIR so promtool check config validates the rendered
# rules instead of a non-existent host /etc/prometheus path.
prometheus_config = yaml.safe_load((out / "prometheus.yml").read_text())

prometheus_config["rule_files"] = [str(out / "rules" / "*.yml")]
(out / "prometheus.local-validation.yml").write_text(
    yaml.safe_dump(prometheus_config, sort_keys=False)
)

prometheus_config["rule_files"] = ["/rendered/rules/*.yml"]
(out / "prometheus.docker-validation.yml").write_text(
    yaml.safe_dump(prometheus_config, sort_keys=False)
)
PY

# Prometheus and Alertmanager containers run as non-root users, while mktemp
# creates OUT_DIR as 0700. Make rendered validation files readable/traversable
# for Docker-based validation.
find "${OUT_DIR}" -type d -exec chmod 0755 {} +
find "${OUT_DIR}" -type f -exec chmod 0644 {} +

run_tool() {
  local image="$1"
  local binary="$2"
  local docker_args="$3"
  shift 3

  if command -v "${binary}" >/dev/null 2>&1; then
    "${binary}" "$@"
  elif command -v docker >/dev/null 2>&1; then
    # shellcheck disable=SC2086
    docker run --rm \
      --entrypoint "${binary}" \
      -v "${OUT_DIR}:/rendered:ro" \
      "${image}" \
      ${docker_args}
  else
    echo "ERROR: neither ${binary} nor docker is available" >&2
    return 127
  fi
}

run_tool \
  "${PROM_IMAGE}" \
  promtool \
  "check config /rendered/prometheus.docker-validation.yml" \
  check config "${OUT_DIR}/prometheus.local-validation.yml"

shopt -s nullglob
rule_files=("${OUT_DIR}"/rules/*.yml)
shopt -u nullglob

if (( ${#rule_files[@]} == 0 )); then
  echo "ERROR: no rendered Prometheus rule files found in ${OUT_DIR}/rules" >&2
  exit 1
fi

for rule_file in "${rule_files[@]}"; do
  rule_name="$(basename "${rule_file}")"
  run_tool \
    "${PROM_IMAGE}" \
    promtool \
    "check rules /rendered/rules/${rule_name}" \
    check rules "${rule_file}"
done

run_tool \
  "${ALERTMANAGER_IMAGE}" \
  amtool \
  "check-config /rendered/alertmanager.yml" \
  check-config "${OUT_DIR}/alertmanager.yml"
