import json
import runpy
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, StrictUndefined

REPO_ROOT = Path(__file__).resolve().parents[2]
ROLE_DIR = REPO_ROOT / "ansible/roles/native_services"
PLAYBOOK_PATH = REPO_ROOT / "ansible/playbook.yml"
SKYNET_TEMPLATE_PATH = REPO_ROOT / "ansible/roles/workstation/templates/skynet.j2"


def task_using(tasks, module):
    return next(task for task in tasks if module in task)


def test_native_alloy_configuration_and_service_permissions_are_safe():
    tasks = yaml.safe_load((ROLE_DIR / "tasks/alloy.yml").read_text())
    handlers = yaml.safe_load((ROLE_DIR / "handlers/alloy.yml").read_text())
    render = task_using(tasks, "ansible.builtin.template")
    service = task_using(tasks, "ansible.builtin.systemd_service")

    assert render["ansible.builtin.template"] == {
        "src": "alloy/config.alloy.j2",
        "dest": "{{ alloy_native_config_path }}",
        "owner": "root",
        "group": "{{ alloy_native_group }}",
        "mode": "0640",
        "validate": "/usr/bin/alloy validate %s",
    }
    assert service["ansible.builtin.systemd_service"]["enabled"] is True
    assert service["ansible.builtin.systemd_service"]["state"] == "started"
    assert task_using(handlers, "ansible.builtin.systemd_service")["ansible.builtin.systemd_service"] == {
        "name": "{{ alloy_native_service_name }}",
        "state": "restarted",
    }


def test_independent_journal_probe_observes_other_units_and_keeps_last_good_sample(tmp_path, monkeypatch):
    probe_path = REPO_ROOT / "ansible/roles/system/files/skynet-alloy-journal-probe.py"
    main = runpy.run_path(probe_path)["main"]
    output = tmp_path / "alloy_journal_probe.prom"
    unit = "skynet-alloy-journal-probe.service"
    monkeypatch.setitem(main.__globals__, "OUTPUT", output)
    activity = [{"UNIT": unit}, {"_SYSTEMD_UNIT": unit}]
    errors = [{"MESSAGE": "failed to read journal entry"}, {"MESSAGE": "unrelated notice"}]

    def query(*args):
        return [json.dumps(entry) for entry in (errors if "--unit=alloy.service" in args else activity)]

    monkeypatch.setitem(main.__globals__, "query", query)
    main()
    assert "skynet_alloy_journal_recent_activity 0\n" in output.read_text()
    activity.append({"_SYSTEMD_UNIT": "example.service"})
    main()
    valid_sample = output.read_text()
    assert "skynet_alloy_journal_recent_activity 1\n" in valid_sample
    assert "skynet_alloy_journal_recent_read_errors 1\n" in valid_sample
    assert "failed to read" not in valid_sample and "unrelated notice" not in valid_sample

    def failed_query(*args):
        raise RuntimeError("journal unavailable")

    monkeypatch.setitem(main.__globals__, "query", failed_query)
    with pytest.raises(RuntimeError, match="journal unavailable"):
        main()
    assert output.read_text() == valid_sample


def test_native_alloy_collects_journal_without_podman_socket_or_root_service_override():
    config = (ROLE_DIR / "templates/alloy/config.alloy.j2").read_text()
    defaults = {
        "alloy_native_" + key: value
        for key, value in yaml.safe_load((REPO_ROOT / "ansible/group_vars/all/services/alloy.yml").read_text())["alloy"]["targets"][
            "native"
        ]["native"]["config"].items()
    }

    assert 'loki.source.journal "system"' in config
    assert 'max_age       = "24h"' in config
    assert "host   = constants.hostname" in config
    assert 'source = "journal"' in config
    assert 'runtime = "podman"' not in config
    assert 'discovery.relabel "journal" {' in config
    assert "targets = []" in config
    for source, target in (
        ("__journal__systemd_unit", "unit"),
        ("__journal__systemd_user_unit", "user_unit"),
        ("__journal_syslog_identifier", "syslog_identifier"),
        ("__journal_priority_keyword", "priority"),
        ("__journal_container_name", "container"),
    ):
        assert f'source_labels = ["{source}"]\n    target_label  = "{target}"' in config
    assert defaults["alloy_native_loki_url"].endswith("/loki/api/v1/push")
    assert "loki.{{ services_internal_zone }}:{{ services_private_https_port }}" in defaults["alloy_native_loki_url"]
    assert "podman.sock" not in config
    assert "/run/user/" not in config
    assert "User=root" not in (ROLE_DIR / "tasks/alloy.yml").read_text()


def test_native_alloy_keeps_privacy_stack_visibility_to_systemd_lifecycle():
    tasks_text = (ROLE_DIR / "tasks/alloy.yml").read_text()
    defaults = {
        "alloy_native_" + key: value
        for key, value in yaml.safe_load((REPO_ROOT / "ansible/group_vars/all/services/alloy.yml").read_text())["alloy"]["targets"][
            "native"
        ]["native"]["config"].items()
    }
    config = (ROLE_DIR / "templates/alloy/config.alloy.j2").read_text()
    services_dir = REPO_ROOT / "ansible/group_vars/all/services"
    privacy_services = {}
    for path in services_dir.glob("*.yml"):
        for key, service in yaml.safe_load(path.read_text()).items():
            if "gluetun_stack" in service.get("tags", []):
                privacy_services[key] = service

    assert set(privacy_services) == {"gluetun", "jdownloader2", "mullvad_browser"}
    assert {service["name"] for service in privacy_services.values()} == {
        "gluetun",
        "jdownloader2",
        "mullvad-browser",
    }
    assert defaults["alloy_native_packages"] == ["alloy"]
    assert not any(key.startswith("alloy_native_jdownloader") for key in defaults)
    assert "JDownloader" not in tasks_text
    assert "ansible.posix.acl" not in tasks_text
    assert 'loki.source.journal "system"' in config
    assert "forward_to    = [loki.write.default.receiver]" in config
    assert 'source_labels = ["__journal_container_name"]' in config
    assert 'regex         = "jdownloader2|mullvad-browser"' in config
    assert 'action        = "drop"' in config
    assert "loki.process" not in config
    assert "local.file_match" not in config
    assert "loki.source.file" not in config
    template = Environment(undefined=StrictUndefined).from_string(config)
    assert "prometheus." not in template.render(alloy_native_loki_url="https://loki.example.test/loki/api/v1/push")
    monitored = template.render(
        alloy_native_loki_url="https://loki.example.test/loki/api/v1/push",
        alloy_native_prometheus_url="https://prometheus.example.test/api/v1/write",
    )
    assert 'prometheus.scrape "native_metrics"' in monitored
    assert '"127.0.0.1:12345"' in monitored
    assert "https://prometheus.example.test/api/v1/write" in monitored
    assert "insecure_skip_verify" not in monitored
    assert "output.log" not in config

    forbidden_observability_keys = {
        "alloy",
        "loki",
        "metrics",
        "prometheus",
        "telemetry",
        "traefik",
    }
    for service in privacy_services.values():
        assert forbidden_observability_keys.isdisjoint(service)

    jdownloader = privacy_services["jdownloader2"]
    assert jdownloader["volumes"]["config"] == {
        "type": "bind",
        "source": "{{ hostvars['blacktop'].container_host_appdata_root }}/jdownloader-2",
        "target": "/config",
        "read_only": False,
    }


def test_skynet_exposes_explicit_alloy_native_target_without_global_rollout():
    wrapper = SKYNET_TEMPLATE_PATH.read_text()

    for action in ("deploy", "install", "run", "update", "remove", "recreate"):
        assert f"alloy-native:{action}" in wrapper
    assert 'echo "deploy,alloy_native"' in wrapper
    assert "  alloy-native:" in wrapper
    assert "skynet check alloy-native" in wrapper
