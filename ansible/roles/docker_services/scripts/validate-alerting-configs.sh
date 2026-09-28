#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${ROOT_DIR:-$(git -C "${SCRIPT_DIR}" rev-parse --show-toplevel 2>/dev/null || (cd "${SCRIPT_DIR}/../../../.." && pwd))}"
OUT_DIR="${OUT_DIR:-$(mktemp -d)}"
PROM_IMAGE="${PROM_IMAGE:-prom/prometheus:v3.14.0}"
ALERTMANAGER_IMAGE="${ALERTMANAGER_IMAGE:-prom/alertmanager:v0.34.1}"
BLACKBOX_IMAGE="${BLACKBOX_IMAGE:-prom/blackbox-exporter:v0.28.0}"
PYTHON_BIN="${PYTHON_BIN:-/opt/ansible/ansible-venv/bin/python}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN=python3
fi

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

"${PYTHON_BIN}" - <<'PY'
import importlib.util
import json
import os
import re
from pathlib import Path

from jinja2 import Environment
import yaml

root = Path(os.environ["ROOT_DIR"])
out = Path(os.environ["OUT_DIR"])
env = Environment()


def read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def first_existing(*paths: Path) -> Path:
    for path in paths:
        if path.exists():
            return path

    wanted = "\n".join(f"  - {path}" for path in paths)
    raise FileNotFoundError(f"None of the expected paths exist:\n{wanted}")


service_alertmanager = root / "ansible/group_vars/all/services/alertmanager.yml"
service_prometheus = root / "ansible/group_vars/all/services/prometheus.yml"

# Basic YAML validation for service definitions that affect the alerting stack.
# This is a syntax check, not full schema validation.
alertmanager_service_vars = read_yaml(service_alertmanager)
prometheus_service_vars = read_yaml(service_prometheus)

prometheus_group_vars = read_yaml(root / "ansible/group_vars/all/prometheus.yml")
availability = load_module(root / "ansible/filter_plugins/availability.py", "validator_availability")
catalog = load_module(root / "ansible/filter_plugins/service_catalog.py", "validator_service_catalog")
services = {}
for service_path in sorted((root / "ansible/group_vars/all/services").glob("*.yml")):
    services.update(read_yaml(service_path))
service_catalog_effective = catalog.service_catalog_effective(services, "mgt")

# The validation script renders templates outside a real Ansible inventory, so
# provide a small CI-safe context for templates that normally depend on NetBox
# hostvars/groups or Infisical-provided SMTP variables.
node_groups = prometheus_group_vars.get("prometheus_node_exporter_inventory_groups", [])
groups = {}
hostvars = {}

for idx, group in enumerate(node_groups, start=1):
    host = f"ci-{group.replace('_', '-')}"
    groups[group] = [host]
    hostvars[host] = {"local_ip": f"192.0.2.{idx}"}

availability_hosts = ["dns01", "dns02", "dns03", "mgt", "unraid", "plex", "pve1", "pg95", "pg96", "pg97"]
for idx, host in enumerate(availability_hosts, start=20):
    hostvars[host] = {"local_ip": f"192.0.2.{idx}"}
groups["tags_postgres"] = ["pg95", "pg96", "pg97"]

prometheus_group_vars["prometheus_blackbox_dns_targets"] = {
    "dns_vip_a": "192.0.2.240",
    "dns_vip_b": "192.0.2.241",
    "dns01": hostvars["dns01"]["local_ip"],
    "dns02": hostvars["dns02"]["local_ip"],
    "dns03": hostvars["dns03"]["local_ip"],
}
prometheus_group_vars["prometheus_blackbox_dns_query_name"] = "adminer.internal.example"
prometheus_group_vars["prometheus_blackbox_dns_expected_a"] = hostvars["mgt"]["local_ip"]
prometheus_group_vars["prometheus_availability_direct_http_targets"] = {
    "plex-direct": {
        "service": "plex",
        "category": "Plex",
        "module": "http_2xx",
        "url": f"http://{hostvars['plex']['local_ip']}:32400/identity",
    },
    "proxmox": {
        "service": "proxmox",
        "category": "Infrastructure",
        "criticality": "critical",
        "module": "http_private",
        "url": f"https://{hostvars['pve1']['local_ip']}:8006",
    },
}
prometheus_group_vars["prometheus_availability_tcp_targets"] = {
    "traefik_private_tcp": {"service": "traefik", "host": "mgt", "port": 8443, "category": "Networking"},
    **{
        f"postgres_{host}_tcp": {"host": host, "port": 5432, "category": "Infrastructure"}
        for host in groups["tags_postgres"]
    },
}

context = {
    **prometheus_group_vars,
    "groups": groups,
    "hostvars": hostvars,
    "svcfiles": services,
    "service_catalog_effective": service_catalog_effective,
    "services_internal_zone": "internal.example",
    "services_private_https_port": 8443,
    "services_controller_host": "mgt",
    "services_plex_host": "plex",
    "docker_services_svc": prometheus_service_vars.get("prometheus", {}),
    "service_common_infisical_values": {
        "smtp_email": "alerts@example.com",
        "smtp_host": "smtp.example.com",
        "smtp_port": "587",
        "smtp_username": "alertmanager@example.com",
    },
}

env.filters.update(
    {
        "availability_http_file_sd": availability.availability_http_file_sd,
        "availability_direct_http_file_sd": availability.availability_direct_http_file_sd,
        "availability_icmp_file_sd": availability.availability_icmp_file_sd,
        "availability_tcp_file_sd": availability.availability_tcp_file_sd,
        "availability_postgres_file_sd": availability.availability_postgres_file_sd,
        "regex_escape": re.escape,
        "to_nice_json": lambda value: json.dumps(value, indent=2, sort_keys=True),
    }
)


def render(src: Path, dest: Path) -> None:
    rendered = env.from_string(src.read_text()).render(**context)
    yaml.safe_load(rendered)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(rendered)


prometheus_template = first_existing(
    root / "ansible/roles/service_common/templates/configs/prometheus/prometheus.yml.j2",
)

render(prometheus_template, out / "prometheus.yml")
render(
    root / "ansible/roles/service_common/templates/configs/alertmanager.yml.j2",
    out / "alertmanager.yml",
)
render(
    root / "ansible/roles/docker_services/templates/configs/prometheus/blackbox.yml.j2",
    out / "blackbox.yml",
)

file_sd_dir = root / "ansible/roles/service_common/templates/configs/prometheus/file_sd"
for src in sorted(file_sd_dir.glob("*.j2")):
    rendered = env.from_string(src.read_text()).render(**context)
    parsed = json.loads(rendered)
    assert isinstance(parsed, list) and parsed, f"{src.name} did not render a non-empty file_sd list"
    destination = out / "file_sd" / src.name.removesuffix(".j2")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(rendered)

rules_dir = root / "ansible/roles/service_common/templates/configs/prometheus/rules"
for src in sorted(rules_dir.glob("*.yml.j2")):
    render(src, out / "rules" / src.name.removesuffix(".j2"))

# The deployed Prometheus config intentionally points at /etc/prometheus/rules/*.yml.
# For validation, write local/Docker variants whose rule_files path points at the
# rendered rule files in OUT_DIR so promtool check config validates the rendered
# rules instead of a non-existent host /etc/prometheus path.
prometheus_config = yaml.safe_load((out / "prometheus.yml").read_text())

prometheus_config["rule_files"] = [str(out / "rules" / "*.yml")]
for scrape_config in prometheus_config.get("scrape_configs", []):
    for file_sd_config in scrape_config.get("file_sd_configs", []):
        file_sd_config["files"] = [
            path.replace("/etc/prometheus/file_sd", str(out / "file_sd"))
            for path in file_sd_config.get("files", [])
        ]
(out / "prometheus.local-validation.yml").write_text(
    yaml.safe_dump(prometheus_config, sort_keys=False)
)

prometheus_config["rule_files"] = ["/rendered/rules/*.yml"]
for scrape_config in prometheus_config.get("scrape_configs", []):
    for file_sd_config in scrape_config.get("file_sd_configs", []):
        file_sd_config["files"] = [
            path.replace(str(out / "file_sd"), "/rendered/file_sd")
            for path in file_sd_config.get("files", [])
        ]
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

run_tool \
  "${BLACKBOX_IMAGE}" \
  blackbox_exporter \
  "--config.file=/rendered/blackbox.yml --config.check" \
  --config.file="${OUT_DIR}/blackbox.yml" --config.check
