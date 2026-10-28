from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ROLE_DIR = REPO_ROOT / "ansible/roles/native_services"
PLAYBOOK_PATH = REPO_ROOT / "ansible/playbook.yml"
SKYNET_TEMPLATE_PATH = REPO_ROOT / "ansible/roles/workstation/templates/skynet.j2"


def task_using(tasks, module):
    return next(task for task in tasks if module in task)


def test_native_alloy_role_uses_official_repository_and_package_service_account():
    defaults = yaml.safe_load((ROLE_DIR / "defaults/alloy.yml").read_text())
    tasks = yaml.safe_load((ROLE_DIR / "tasks/alloy.yml").read_text())

    key = task_using(tasks, "ansible.builtin.get_url")
    repository = task_using(tasks, "ansible.builtin.apt_repository")
    user = task_using(tasks, "ansible.builtin.user")

    assert key["ansible.builtin.get_url"]["url"] == "{{ alloy_native_repo_url }}/gpg-full.key"
    assert "signed-by={{ alloy_native_keyring_file }}" in repository["ansible.builtin.apt_repository"]["repo"]
    assert repository["ansible.builtin.apt_repository"]["update_cache"] is True
    assert defaults["alloy_native_repo_url"] == "https://apt.grafana.com"
    assert defaults["alloy_native_packages"] == ["alloy"]
    assert user["ansible.builtin.user"]["name"] == "{{ alloy_native_user }}"
    assert user["ansible.builtin.user"]["append"] is True
    assert defaults["alloy_native_journal_groups"] == ["adm", "systemd-journal"]


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
    }
    assert service["ansible.builtin.systemd_service"]["enabled"] is True
    assert service["ansible.builtin.systemd_service"]["state"] == "started"
    assert task_using(handlers, "ansible.builtin.systemd_service")["ansible.builtin.systemd_service"] == {
        "name": "{{ alloy_native_service_name }}",
        "state": "restarted",
    }


def test_native_alloy_collects_journal_without_podman_socket_or_root_service_override():
    config = (ROLE_DIR / "templates/alloy/config.alloy.j2").read_text()
    defaults = yaml.safe_load((ROLE_DIR / "defaults/alloy.yml").read_text())

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
    defaults = yaml.safe_load((ROLE_DIR / "defaults/alloy.yml").read_text())
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
    assert "prometheus." not in config
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


def test_native_alloy_playbook_targeting_preserves_lazy_fact_gathering():
    playbook = yaml.safe_load(PLAYBOOK_PATH.read_text())
    play = next(item for item in playbook if item.get("hosts") == "tags_skynet")
    setup = next(task for task in play["tasks"] if "ansible.builtin.setup" in task and "alloy_native" in task.get("tags", []))
    include = next(task for task in play["tasks"] if task.get("ansible.builtin.include_role", {}).get("tasks_from") == "alloy")

    assert play["gather_facts"] is False
    assert "tags_podman" in setup["when"]
    assert setup["tags"] == ["alloy_native"]
    assert include["when"] == setup["when"]
    assert include["tags"] == ["alloy_native"]
    assert include["ansible.builtin.include_role"]["name"] == "native_services"
    assert include["ansible.builtin.include_role"]["apply"]["tags"] == ["alloy_native"]


def test_skynet_exposes_explicit_alloy_native_target_without_global_rollout():
    wrapper = SKYNET_TEMPLATE_PATH.read_text()

    for action in ("deploy", "install", "run"):
        assert f"alloy-native:{action})" in wrapper
    assert wrapper.count('echo "alloy_native" ;;') >= 3
    assert "  alloy-native:" in wrapper
    assert "skynet check alloy-native" in wrapper
