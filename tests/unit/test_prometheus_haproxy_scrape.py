from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "ansible/roles/service_common/templates"


@pytest.mark.parametrize("runtime", ["docker", "podman"])
def test_shared_haproxy_job_preserves_both_instances_across_runtime_transition(runtime):
    env = Environment(loader=FileSystemLoader(TEMPLATES), undefined=StrictUndefined)
    rendered = env.get_template("configs/prometheus/haproxy-scrape.yml.j2").render(
        service_common_service={"runtime": runtime},
        prometheus_worker_metrics_address="192.0.2.20:22623",
        services_controller_host="manager",
        hostvars={"manager": {"local_ip": "192.0.2.48"}},
    )
    job = yaml.safe_load(rendered)[0]
    targets = [target for record in job["static_configs"] for target in record["targets"]]
    assert targets == ["192.0.2.48:18405", "haproxy:8405" if runtime == "docker" else "192.0.2.20:22623"]
    assert job["job_name"] == "haproxy" and job["metrics_path"] == "/metrics"
    instances = [record.get("labels", {}).get("instance", record["targets"][0]) for record in job["static_configs"]]
    assert instances == ["192.0.2.48:18405", "haproxy:8405"]
