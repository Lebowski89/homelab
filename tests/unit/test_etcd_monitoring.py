"""Render real etcd discovery/config; exercise alert expressions with promtool fixtures."""

import importlib.util
import json
import os
import re
import shutil
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


def inventory(member_count=3):
    hosts = {f"pg{i}": {"local_ip": f"192.0.2.{i}"} for i in range(95, 95 + member_count)}
    return {"hostvars": hosts, "groups": {"tags_postgres": list(reversed(hosts))}, "prometheus_patroni_metrics_port": 8008}


def promtool():
    # Use only an explicitly supplied or existing executable; never pull images.
    binary = os.environ.get("PROMTOOL") or shutil.which("promtool")
    if not binary:
        pytest.skip("promtool unavailable; behavioral rule evaluation was not run")
    return binary


@pytest.mark.parametrize("member_count", [3, 4])
def test_member_count_checks_follow_the_file_sd_inventory(member_count):
    env = environment()
    context = inventory(member_count)
    # Other inventory hosts must not count as database-cluster members.
    context["hostvars"]["unrelated"] = {"local_ip": "192.0.2.20"}
    context["prometheus_patroni_metrics_port"] = 18008
    etcd = json.loads(env.get_template("configs/prometheus/file_sd/etcd.json.j2").render(**context))
    patroni = json.loads(env.get_template("configs/prometheus/file_sd/patroni.json.j2").render(**context))
    rules = yaml.safe_load(env.get_template("configs/prometheus/rules/etcd.yml.j2").render(**context))["groups"][0]["rules"]
    alerts = {rule["alert"]: rule for rule in rules if "alert" in rule}
    count_check = r'count\(up\{job="([^"]+)"\}\) != (\d+)'
    assert len(etcd) == len(patroni) == member_count
    assert re.findall(count_check, alerts["EtcdMonitoringIncomplete"]["expr"]) == [
        ("etcd", str(len(etcd))),
        ("etcd-health", str(len(etcd))),
    ]
    assert re.findall(count_check, alerts["PatroniImmediateHealthFailure"]["expr"]) == [("patroni", str(len(patroni)))]


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
    rendered = environment().get_template("configs/prometheus/rules/etcd.yml.j2").render(**inventory())
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
    (tmp_path / "etcd.yml").write_text(environment().get_template("configs/prometheus/rules/etcd.yml.j2").render(**inventory()))
    fixture = tmp_path / "etcd-monitoring.test.yml"
    fixture.write_bytes(FIXTURE.read_bytes())
    result = subprocess.run([promtool(), "test", "rules", str(fixture)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("missing_job", ["etcd", "etcd-health", "patroni"])
def test_promtool_four_members_detects_one_missing_and_recovery(tmp_path, missing_job):
    env = environment()
    context = inventory(4)
    (tmp_path / "etcd.yml").write_text(env.get_template("configs/prometheus/rules/etcd.yml.j2").render(**context))
    metric_values = {
        "etcd": {
            "up": "1+0x8",
            "etcd_mvcc_db_total_size_in_bytes": "100+0x8",
            "etcd_mvcc_db_total_size_in_use_in_bytes": "100+0x8",
            "etcd_server_quota_backend_bytes": "1000+0x8",
            "etcd_server_has_leader": "1+0x8",
        },
        "etcd-health": {"up": "1+0x8", "probe_success": "1+0x8"},
        "patroni": {
            "up": "1+0x8",
            "patroni_postgres_running": "1+0x8",
            "patroni_cluster_unlocked": "0+0x8",
            "patroni_dcs_last_seen": "0+30x8",
            "patroni_primary": "0+0x8",
        },
    }
    series = []
    for job, metrics in metric_values.items():
        source = "patroni" if job == "patroni" else "etcd"
        targets = json.loads(env.get_template(f"configs/prometheus/file_sd/{source}.json.j2").render(**context))
        for index, target in enumerate(targets):
            labels = {"job": job, "instance": target["targets"][0], "host": target["labels"]["host"]}
            suffix = "{" + ",".join(f"{key}={json.dumps(value)}" for key, value in labels.items()) + "}"
            for metric, values in metrics.items():
                # Only this up series disappears; all other telemetry remains.
                # Thus only the expected-count branch can detect the gap.
                if job == missing_job and index == 3 and metric == "up":
                    values = "1 1 stale _ _ _ 1+0x2"
                series.append({"series": metric + suffix, "values": values})
    alert = "PatroniImmediateHealthFailure" if missing_job == "patroni" else "EtcdMonitoringIncomplete"
    checks = []
    for time, firing in [(30, 0), (60, int(missing_job == "patroni")), (120, int(missing_job == "patroni")), (150, 1), (180, 0)]:
        checks.append(
            {
                "expr": f'count(ALERTS{{alertname="{alert}",alertstate="firing"}}) or vector(0)',
                "eval_time": f"{time}s",
                "exp_samples": [{"labels": "{}", "value": firing}],
            }
        )
    fixture = tmp_path / "expanded-inventory.test.yml"
    fixture.write_text(
        yaml.safe_dump(
            {
                "rule_files": ["etcd.yml"],
                "evaluation_interval": "30s",
                "tests": [
                    {
                        "name": f"four members: {missing_job} gap and recovery",
                        "interval": "30s",
                        "input_series": series,
                        "promql_expr_test": checks,
                    }
                ],
            }
        )
    )
    result = subprocess.run([promtool(), "test", "rules", str(fixture)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
