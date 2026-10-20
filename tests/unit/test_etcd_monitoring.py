"""Render real etcd discovery/config; exercise alert expressions with promtool fixtures."""

import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "ansible/roles/service_common/templates"
RULES = TEMPLATES / "configs/prometheus/rules/etcd.yml.j2"
FIXTURE = ROOT / "tests/fixtures/etcd-monitoring.test.yml"


def environment():
    spec = importlib.util.spec_from_file_location("etcd_availability", ROOT / "ansible/filter_plugins/availability.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    env = Environment(loader=FileSystemLoader(TEMPLATES), undefined=StrictUndefined)
    env.filters.update(module.FilterModule().filters())
    env.filters["to_nice_json"] = json.dumps
    return env


def test_etcd_discovery_uses_inventory_and_rejects_missing_identity():
    env = environment()
    hosts = {name: {"local_ip": f"192.0.2.{i}"} for i, name in enumerate(["pg95", "pg96", "pg97"], 1)}
    template = env.get_template("configs/prometheus/file_sd/etcd.json.j2")
    targets = json.loads(template.render(hostvars=hosts, groups={"tags_postgres": list(reversed(hosts))}))
    assert [t["labels"]["host"] for t in targets] == sorted(hosts)
    assert [t["targets"] for t in targets] == [[f"192.0.2.{i}:2379"] for i in range(1, 4)]
    assert all(t["labels"]["probe_type"] == "etcd" for t in targets)
    with pytest.raises(Exception, match="no local_ip"):
        template.render(hostvars={"pg95": {}}, groups={"tags_postgres": ["pg95"]})


def test_scrapes_use_existing_blackbox_without_alarm_exclusions_or_new_module():
    rendered = (
        environment().get_template("configs/prometheus/etcd-scrape.yml.j2").render(prometheus_blackbox_exporter_address="192.0.2.20:22622")
    )
    jobs = yaml.safe_load(rendered)
    assert [j["job_name"] for j in jobs] == ["etcd", "etcd-health"]
    assert all(j["scrape_interval"] == "30s" and j["scrape_timeout"] == "10s" for j in jobs)
    health = jobs[1]
    assert health["params"] == {"module": ["http_2xx"]}
    relabels = {r["target_label"]: r for r in health["relabel_configs"]}
    assert relabels["__param_target"]["replacement"] == "http://${1}/health"
    assert relabels["__address__"]["replacement"] == "192.0.2.20:22622"
    assert jobs[0]["file_sd_configs"] == health["file_sd_configs"]


def test_real_service_wires_monitoring_files_and_preserves_immediate_escalation():
    service = yaml.safe_load((ROOT / "ansible/group_vars/all/services/prometheus.yml").read_text())["prometheus"]
    sources = {v["src"] for v in service["templates"]}
    assert {"configs/prometheus/file_sd/etcd.json.j2", "configs/prometheus/rules/etcd.yml.j2"} <= sources
    rendered = environment().get_template("configs/prometheus/rules/etcd.yml.j2").render()
    rules = yaml.safe_load(rendered)["groups"][0]
    assert rules["interval"] == "30s"
    alerts = {r["alert"]: r for r in rules["rules"] if "alert" in r}
    for name, rule in alerts.items():
        if name not in {"EtcdQuotaForecastUnavailable", "EtcdMonitoringIncomplete"}:
            assert "for" not in rule
    assert alerts["EtcdMonitoringIncomplete"]["for"] == "90s"
    assert "keep_firing_for" not in alerts["EtcdMonitoringIncomplete"]
    assert alerts["EtcdQuotaImmediateReview"]["labels"]["severity"] == "critical"
    assert alerts["EtcdQuotaSameDayReview"]["labels"]["severity"] == "warning"


def test_promtool_behavior(tmp_path):
    # CI/operators can supply the existing installed version; do not install tools.
    binary = os.environ.get("PROMTOOL")
    if not binary:
        pytest.skip("PROMTOOL not supplied; run the retained fixture with installed promtool")
    (tmp_path / "etcd.yml").write_text(environment().get_template("configs/prometheus/rules/etcd.yml.j2").render())
    fixture = tmp_path / "etcd-monitoring.test.yml"
    fixture.write_bytes(FIXTURE.read_bytes())
    result = subprocess.run([binary, "test", "rules", str(fixture)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
