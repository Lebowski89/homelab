"""Render the real transition paths without changing existing scrape identities."""

from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "ansible/roles/service_common/templates"


def render(runtime, **overrides):
    cfg = yaml.safe_load((ROOT / "ansible/group_vars/all/services/prometheus.yml").read_text())["prometheus"]
    cfg = deepcopy(cfg)
    cfg["runtime"] = runtime
    env = Environment(loader=FileSystemLoader(TEMPLATES), undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)
    return yaml.safe_load(
        env.get_template("configs/prometheus/prometheus.yml.j2").render(
            service_common_service=cfg,
            services_controller_host="manager",
            services_internal_zone="internal.example",
            services_private_https_port=8443,
            hostvars={"manager": {"local_ip": "192.0.2.48"}},
            groups={},
            prometheus_blackbox_exporter_address="192.0.2.20:22622",
            prometheus_worker_metrics_address="192.0.2.20:22623",
            **overrides,
        )
    )


def test_transition_preserves_unique_jobs_labels_and_unrelated_scrape_definitions():
    before, after = render("docker"), render("podman")
    jobs_before = {j["job_name"]: j for j in before["scrape_configs"]}
    jobs_after = {j["job_name"]: j for j in after["scrape_configs"]}
    assert len(jobs_after) == len(after["scrape_configs"]) and jobs_after.keys() == jobs_before.keys()
    expected = {"authelia": ("authelia:9959", "/authelia/metrics"), "traefik": ("traefik:8082", "/traefik/metrics")}
    for name, (instance, path) in expected.items():
        old, new = jobs_before[name], jobs_after[name]
        assert old["static_configs"] == [{"targets": [instance]}]
        assert new["static_configs"] == [{"targets": ["192.0.2.20:22623"], "labels": {"instance": instance}}]
        assert new["metrics_path"] == path
        assert {k: v for k, v in new.items() if k not in ("static_configs", "metrics_path")} == {
            k: v for k, v in old.items() if k not in ("static_configs", "metrics_path")
        }
    assert before["alerting"] == after["alerting"]
    for name in jobs_before.keys() - {"authelia", "traefik", "haproxy"}:
        assert jobs_before[name] == jobs_after[name]
    assert jobs_after["prometheus"]["static_configs"][0]["labels"]["instance"] == "prometheus:9090"


def test_authelia_direct_transition_changes_only_transport_and_retains_labels():
    relay = render("podman")
    direct = render("podman", prometheus_authelia_metrics_address="192.0.2.48:19959")
    assert direct["alerting"] == relay["alerting"]
    old_jobs = {row["job_name"]: row for row in relay["scrape_configs"]}
    new_jobs = {row["job_name"]: row for row in direct["scrape_configs"]}
    assert len(new_jobs) == len(direct["scrape_configs"])
    assert old_jobs.keys() == new_jobs.keys()
    for name in old_jobs.keys() - {"authelia"}:
        assert old_jobs[name] == new_jobs[name]
    expected = deepcopy(old_jobs["authelia"])
    expected["metrics_path"] = "/metrics"
    expected["static_configs"][0]["targets"] = ["192.0.2.48:19959"]
    assert new_jobs["authelia"] == expected
    # Older inventories without this opt-in keep the protected relay. Docker
    # keeps its overlay path even when the prepared variable is present.
    assert render("podman", prometheus_authelia_metrics_address="") == relay
    assert render("docker", prometheus_authelia_metrics_address="192.0.2.48:19959") == render("docker")


@pytest.mark.parametrize("proxy", [False, True])
def test_haproxy_worker_relay_is_opted_in_without_changing_postgresql_or_mgt_config(proxy):
    env = Environment(loader=FileSystemLoader(TEMPLATES), undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)
    settings = yaml.safe_load((ROOT / "ansible/group_vars/all/services/haproxy.yml").read_text())["haproxy"]["settings"]
    args = dict(
        service_common_service={"settings": settings}, groups={"tags_postgres": ["pg"]}, hostvars={"pg": {"local_ip": "192.0.2.95"}}
    )
    template = env.get_template("configs/haproxy.cfg.j2")
    original = template.render(args)
    args["service_common_service"]["settings"] = {**settings, "haproxy_overlay_metrics_proxy": proxy}
    candidate = template.render(args)

    def sql_lines(text):
        section = text.split("frontend pg_write", 1)[1].split("resolvers docker_overlay", 1)[0]
        return [line.strip() for line in section.splitlines() if line.strip() and not line.lstrip().startswith("#")]

    assert sql_lines(candidate) == sql_lines(original)
    if not proxy:
        assert candidate == original
    else:
        assert "http-request deny unless { method GET }" in candidate
        for name in ("authelia", "traefik"):
            assert f"use_backend metrics_{name} if {{ path /{name}/metrics }}" in candidate
            assert "http-request set-path /metrics" in candidate.split("backend metrics_" + name, 1)[1]
        assert "resolvers docker_overlay" in candidate and "127.0.0.11:53" in candidate


@pytest.mark.integration
@pytest.mark.parametrize("value,valid", [(None, True), (False, True), (True, True), ("true", False), (1, False)])
def test_actual_haproxy_settings_validation_retains_strict_boolean_contract(tmp_path, value, valid):
    import os
    import subprocess
    import sys

    settings = yaml.safe_load((ROOT / "ansible/group_vars/all/services/haproxy.yml").read_text())["haproxy"]["settings"]
    if value is not None:
        settings["haproxy_overlay_metrics_proxy"] = value
    config = tmp_path / "ansible.cfg"
    config.write_text("[defaults]\ninventory=localhost,\nretry_files_enabled=False\n")
    play = tmp_path / "play.yml"
    play.write_text(
        yaml.safe_dump(
            [
                {
                    "hosts": "localhost",
                    "connection": "local",
                    "gather_facts": False,
                    "vars": {"service_prepare_context": {"service": {"settings": settings}}},
                    "tasks": [
                        {
                            "ansible.builtin.import_tasks": str(
                                ROOT / "ansible/roles/service_prepare/tasks/applications/haproxy/validate.yml"
                            )
                        }
                    ],
                }
            ]
        )
    )
    binary = Path(sys.executable).parent / "ansible-playbook"
    result = subprocess.run(
        [str(binary), "-i", "localhost,", str(play)],
        env={**os.environ, "ANSIBLE_CONFIG": str(config)},
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert "UNREACHABLE!" not in result.stdout
    assert (result.returncode == 0) == valid, result.stdout + result.stderr


def test_traefik_direct_scrape_opt_in_preserves_other_jobs_and_instance():
    relay = render("podman")
    direct = render("podman", prometheus_traefik_metrics_address="192.0.2.48:18084")
    previous = {job["job_name"]: job for job in relay["scrape_configs"]}
    current = {job["job_name"]: job for job in direct["scrape_configs"]}
    assert len(current) == len(direct["scrape_configs"])
    assert previous.keys() == current.keys()
    for name in previous.keys() - {"traefik"}:
        assert current[name] == previous[name]
    expected = deepcopy(previous["traefik"])
    expected["metrics_path"] = "/metrics"
    expected["static_configs"][0]["targets"] = ["192.0.2.48:18084"]
    assert current["traefik"] == expected
    assert direct["alerting"] == relay["alerting"]
    assert render("podman", prometheus_traefik_metrics_address="") == relay
    assert render("docker", prometheus_traefik_metrics_address="192.0.2.48:18084") == render("docker")
