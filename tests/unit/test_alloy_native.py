from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ROLE_DIR = REPO_ROOT / "ansible/roles/alloy_native"
PLAYBOOK_PATH = REPO_ROOT / "ansible/playbook.yml"


def task_named(tasks, name: str):
    return next(task for task in tasks if task.get("name") == name)


def test_native_alloy_role_uses_official_repository_and_package_service_account():
    defaults = yaml.safe_load((ROLE_DIR / "defaults/main.yml").read_text())
    tasks = yaml.safe_load((ROLE_DIR / "tasks/main.yml").read_text())

    key = task_named(tasks, "Alloy native | Download Grafana package signing key")
    repository = task_named(tasks, "Alloy native | Configure Grafana apt repository")
    user = task_named(tasks, "Alloy native | Grant journal access to package service account")

    assert key["ansible.builtin.get_url"]["url"] == "{{ alloy_native_repo_url }}/gpg-full.key"
    assert "signed-by={{ alloy_native_keyring_file }}" in repository["ansible.builtin.apt_repository"]["repo"]
    assert repository["ansible.builtin.apt_repository"]["update_cache"] is True
    assert defaults["alloy_native_repo_url"] == "https://apt.grafana.com"
    assert defaults["alloy_native_packages"] == ["acl", "alloy"]
    assert user["ansible.builtin.user"]["name"] == "{{ alloy_native_user }}"
    assert user["ansible.builtin.user"]["append"] is True
    assert defaults["alloy_native_journal_groups"] == ["adm", "systemd-journal"]


def test_native_alloy_configuration_and_service_permissions_are_safe():
    tasks = yaml.safe_load((ROLE_DIR / "tasks/main.yml").read_text())
    handlers = yaml.safe_load((ROLE_DIR / "handlers/main.yml").read_text())
    render = task_named(tasks, "Alloy native | Render collector configuration")
    service = task_named(tasks, "Alloy native | Enable and start service")

    assert render["ansible.builtin.template"] == {
        "src": "config.alloy.j2",
        "dest": "{{ alloy_native_config_path }}",
        "owner": "root",
        "group": "{{ alloy_native_group }}",
        "mode": "0640",
    }
    assert render["notify"] == "Restart Alloy"
    assert service["ansible.builtin.systemd_service"]["enabled"] is True
    assert service["ansible.builtin.systemd_service"]["state"] == "started"
    assert handlers == [
        {
            "name": "Restart Alloy",
            "ansible.builtin.systemd_service": {
                "name": "{{ alloy_native_service_name }}",
                "state": "restarted",
            },
        }
    ]


def test_native_alloy_collects_journal_without_podman_socket_or_root_service_override():
    config = (ROLE_DIR / "templates/config.alloy.j2").read_text()
    defaults = yaml.safe_load((ROLE_DIR / "defaults/main.yml").read_text())

    assert 'loki.source.journal "system"' in config
    assert 'max_age       = "24h"' in config
    assert "host   = constants.hostname" in config
    assert 'source = "journal"' in config
    assert 'runtime = "podman"' not in config
    assert 'discovery.relabel "journal" {' in config
    assert "targets = []" in config
    assert "__journal__systemd_unit" in config
    assert "__journal__systemd_user_unit" in config
    assert "__journal_syslog_identifier" in config
    assert "__journal_priority_keyword" in config
    assert "__journal_container_name" in config
    assert defaults["alloy_native_loki_url"].endswith("/loki/api/v1/push")
    assert "loki.{{ services_internal_zone }}:{{ services_private_https_port }}" in defaults["alloy_native_loki_url"]
    assert "podman.sock" not in config
    assert "/run/user/" not in config
    assert "User=root" not in (ROLE_DIR / "tasks/main.yml").read_text()


def test_native_alloy_collects_only_jdownloader_file_with_scoped_acl():
    tasks = yaml.safe_load((ROLE_DIR / "tasks/main.yml").read_text())
    config = (ROLE_DIR / "templates/config.alloy.j2").read_text()
    existing_acl = task_named(tasks, "Alloy native | Grant Alloy access to existing JDownloader logs")
    default_acl = task_named(tasks, "Alloy native | Preserve Alloy access on new JDownloader logs")

    assert "{{ alloy_native_jdownloader_log_path }}" in config
    assert 'service   = "jdownloader2"' in config
    assert 'source    = "file"' in config
    assert "tail_from_end           = true" in config
    assert existing_acl["ansible.posix.acl"]["path"] == "{{ alloy_native_jdownloader_logs_dir }}"
    assert existing_acl["ansible.posix.acl"]["recursive"] is True
    assert default_acl["ansible.posix.acl"]["path"] == "{{ alloy_native_jdownloader_logs_dir }}"
    assert default_acl["ansible.posix.acl"]["default"] is True
    defaults = yaml.safe_load((ROLE_DIR / "defaults/main.yml").read_text())
    assert defaults["alloy_native_jdownloader_root"].endswith("/jdownloader-2")
    assert defaults["alloy_native_jdownloader_logs_dir"].endswith("/logs")
    assert defaults["alloy_native_jdownloader_log_path"].endswith("/output.log")


def test_native_alloy_playbook_targeting_preserves_lazy_fact_gathering():
    playbook = yaml.safe_load(PLAYBOOK_PATH.read_text())
    play = next(item for item in playbook if item.get("name") == "Deploy homelab services")
    setup = task_named(play["tasks"], "Gather facts for native Alloy role")
    include = task_named(play["tasks"], "Include native Alloy role")

    assert play["gather_facts"] is False
    assert "tags_podman" in setup["when"]
    assert setup["tags"] == ["alloy_native"]
    assert include["when"] == setup["when"]
    assert include["tags"] == ["alloy_native"]
    assert include["ansible.builtin.include_role"]["name"] == "alloy_native"
    assert include["ansible.builtin.include_role"]["apply"]["tags"] == ["alloy_native"]
