from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

REPO_ROOT = Path(__file__).resolve().parents[2]
N8N_PATH = REPO_ROOT / "ansible/group_vars/all/services/n8n.yml"
COMPOSE_TEMPLATE_DIR = REPO_ROOT / "ansible/roles/docker_services/templates"
PODMAN_TEMPLATE_DIR = REPO_ROOT / "ansible/roles/podman_services/templates"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


podman = load_module(
    REPO_ROOT / "ansible/roles/podman_services/filter_plugins/podman_services.py",
    "n8n_podman",
)
common = load_module(
    REPO_ROOT / "ansible/roles/service_common/filter_plugins/service_common.py",
    "n8n_common",
)
docker_ports = load_module(
    REPO_ROOT / "ansible/roles/docker_services/filter_plugins/docker_services_ports.py",
    "n8n_docker_ports",
)
docker_volumes = load_module(
    REPO_ROOT / "ansible/roles/docker_services/filter_plugins/docker_services_volumes.py",
    "n8n_docker_volumes",
)
docker_secrets = load_module(
    REPO_ROOT / "ansible/roles/docker_services/filter_plugins/docker_services_secrets.py",
    "n8n_docker_secrets",
)
docker_lists = load_module(
    REPO_ROOT / "ansible/roles/docker_services/filter_plugins/docker_services_list_fields.py",
    "n8n_docker_lists",
)
catalog = load_module(
    REPO_ROOT / "ansible/filter_plugins/service_catalog.py",
    "n8n_catalog",
)


def n8n_config():
    document = yaml.safe_load(N8N_PATH.read_text())
    return document["n8n"]


def resolved_n8n_config():
    cfg = copy.deepcopy(n8n_config())
    cfg["ports"][0]["host_ip"] = "192.0.2.98"
    return cfg


def normalize_both(*, check_mode=False):
    cfg = resolved_n8n_config()
    podman_service = podman.podman_service_normalize(cfg, "n8n")
    common_secrets = common.service_common_infisical_normalize(
        cfg["infisical"]["secrets_map"],
        cfg["infisical"]["fail_on_empty"],
    )
    infisical_values = common.service_common_infisical_check_values(common_secrets) if check_mode else {"cloudflare_zone": "example.test"}
    resolved_environment = common.service_common_environment_resolve(
        cfg["environment"],
        infisical_values,
        common_secrets,
    )
    podman_service["env"] = copy.deepcopy(resolved_environment)
    docker_port_list = docker_ports.docker_services_canonical_ports(
        cfg["ports"],
        stack_deploy_type=cfg["deploy"]["type"],
    )
    docker_volume_list = docker_volumes.docker_services_canonical_volumes(cfg["volumes"])
    docker_attachments = docker_secrets.docker_services_secret_attachments(
        [],
        common_secrets["secret_declarations"],
        cfg["deploy"]["type"],
    )
    docker_mounts = docker_secrets.docker_services_secret_mounts(docker_attachments, "n8n")
    return (
        cfg,
        podman_service,
        common_secrets,
        docker_port_list,
        docker_volume_list,
        docker_attachments,
        docker_mounts,
        resolved_environment,
    )


def test_real_n8n_uses_only_canonical_portable_schema():
    cfg = n8n_config()

    assert cfg["runtime"] == "podman"
    assert {"container", "env", "host_paths", "secrets", "network"}.isdisjoint(cfg)
    assert cfg["deploy"] == {"type": "container", "host": "n8n"}
    assert cfg["runtime_options"]["podman"]["network"]["delete_on_stop"] is True
    assert cfg["runtime_options"]["podman"]["systemd"]["restart"] == "on-failure"


def test_real_n8n_podman_normalization_preserves_behavior():
    cfg, service, _, _, _, _, _, resolved_environment = normalize_both()

    assert service["image"] == "docker.io/n8nio/n8n:2.31.4"
    assert service["container"]["uid"] == "1000"
    assert service["container"]["gid"] == "1000"
    assert service["container"]["host"] == "n8n"
    assert service["env"] == resolved_environment
    assert set(service["env"]) == {
        "DB_TYPE",
        "DB_POSTGRESDB_HOST",
        "DB_POSTGRESDB_PORT",
        "DB_POSTGRESDB_DATABASE",
        "DB_POSTGRESDB_USER_FILE",
        "DB_POSTGRESDB_PASSWORD_FILE",
        "N8N_ENCRYPTION_KEY_FILE",
        "TZ",
        "GENERIC_TIMEZONE",
        "N8N_HOST",
        "N8N_PROTOCOL",
        "N8N_PORT",
        "N8N_EDITOR_BASE_URL",
        "WEBHOOK_URL",
        "N8N_PROXY_HOPS",
        "N8N_SECURE_COOKIE",
        "N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS",
        "N8N_BLOCK_ENV_ACCESS_IN_NODE",
        "N8N_DIAGNOSTICS_ENABLED",
        "N8N_PERSONALIZATION_ENABLED",
        "N8N_METRICS",
        "EXECUTIONS_DATA_PRUNE",
        "EXECUTIONS_DATA_MAX_AGE",
        "NODES_EXCLUDE",
    }
    assert service["env"]["DB_POSTGRESDB_USER_FILE"] == "/run/secrets/postgres_user_secret"
    assert service["env"]["DB_POSTGRESDB_PASSWORD_FILE"] == "/run/secrets/postgres_pass_secret"
    assert service["env"]["N8N_ENCRYPTION_KEY_FILE"] == "/run/secrets/n8n_encryption_key_secret"
    assert service["container"]["ports"] == [
        {
            "host_ip": "192.0.2.98",
            "host": 5678,
            "container": 5678,
            "protocol": "tcp",
        }
    ]
    assert service["container"]["mounts"] == [
        {
            "source": "/opt/n8n",
            "target": "/home/node/.n8n",
            "read_only": False,
        }
    ]
    assert service["host_paths"] == cfg["paths"]
    assert service["container"]["healthcheck"]["interval"] == "30s"
    assert service["container"]["healthcheck"]["timeout"] == "10s"
    assert service["container"]["healthcheck"]["retries"] == 5
    assert service["container"]["healthcheck"]["start_period"] == "90s"
    assert "healthz/readiness" in service["container"]["healthcheck"]["command"]
    assert service["container"]["cap_add"] == []
    assert service["container"]["cap_drop"] == ["all"]
    assert service["container"]["no_new_privileges"] is True
    assert service["network"] == {
        "name": "n8n",
        "driver": "bridge",
        "delete_on_stop": True,
    }
    assert service["container"]["systemd"] == {
        "after": ["network-online.target"],
        "restart": "on-failure",
        "restart_sec": "15s",
    }
    assert service["postgres"] == cfg["postgres"]
    assert service["traefik"] == cfg["traefik"]
    assert [(secret["name"], secret["immutable"], secret["replace"]) for secret in service["secrets"]] == [
        ("postgres_user_secret", True, False),
        ("postgres_pass_secret", False, True),
        ("n8n_encryption_key_secret", True, False),
    ]


def test_runtime_only_copy_is_accepted_by_docker_port_volume_secret_and_catalog_paths():
    cfg, _, common_secrets, ports, volumes, attachments, mounts, resolved_environment = normalize_both()
    docker_cfg = copy.deepcopy(cfg)
    docker_cfg["runtime"] = "docker"

    docker_item = catalog.service_catalog_effective({"n8n": docker_cfg}, "manager")[0]
    assert docker_item["runtime"] == "docker"
    docker_service = catalog.service_catalog_merge_target(docker_cfg)
    assert docker_service["image"] == docker_cfg["image"]
    assert docker_service["environment"] == docker_cfg["environment"]
    assert resolved_environment["N8N_HOST"] == "n8n.int.example.test"
    assert docker_service["healthcheck"] == docker_cfg["healthcheck"]
    assert ports == [
        {
            "target": 5678,
            "published": 5678,
            "protocol": "tcp",
            "host_ip": "192.0.2.98",
        }
    ]
    assert volumes == [
        {
            "type": "bind",
            "source": "/opt/n8n",
            "target": "/home/node/.n8n",
            "read_only": False,
        }
    ]
    assert [declaration["name"] for declaration in common_secrets["secret_declarations"]] == [
        "postgres_user_secret",
        "postgres_pass_secret",
        "n8n_encryption_key_secret",
    ]
    assert [attachment["source"] for attachment in attachments] == [
        "postgres_user_secret",
        "postgres_pass_secret",
        "n8n_encryption_key_secret",
    ]
    assert [mount["target"] for mount in mounts] == [
        "/run/secrets/postgres_user_secret",
        "/run/secrets/postgres_pass_secret",
        "/run/secrets/n8n_encryption_key_secret",
    ]


def test_adapters_resolve_equivalent_portable_runtime_values():
    cfg, podman_service, _, docker_port_list, docker_volume_list, _, docker_mounts, resolved_environment = normalize_both()

    assert podman_service["image"] == cfg["image"]
    assert podman_service["env"] == resolved_environment
    assert resolved_environment["N8N_EDITOR_BASE_URL"] == "https://n8n.int.example.test:8443/"
    assert podman_service["container"]["ports"][0]["host"] == docker_port_list[0]["published"]
    assert podman_service["container"]["ports"][0]["container"] == docker_port_list[0]["target"]
    assert podman_service["container"]["mounts"][0] == {key: docker_volume_list[0][key] for key in ("source", "target", "read_only")}
    assert [(item["name"], item["target"]) for item in podman_service["secrets"]] == [
        (Path(mount["source"]).name, mount["target"]) for mount in docker_mounts
    ]


def render_compose(stack_type, service):
    env = Environment(loader=FileSystemLoader(COMPOSE_TEMPLATE_DIR), trim_blocks=True, lstrip_blocks=True)
    env.globals["lookup"] = lambda *_args, **_kwargs: ""
    env.filters["to_json"] = json.dumps
    env.filters["bool"] = bool
    return env.get_template("compose.yml.j2").render(
        deploy_stack_type=stack_type,
        docker_services_compose_services={"n8n": service},
    )


def docker_compose_service_from_real_n8n():
    cfg, _, _, ports, volumes, _, mounts, resolved_environment = normalize_both()
    docker_cfg = copy.deepcopy(cfg)
    docker_cfg["runtime"] = "docker"
    normalized = catalog.service_catalog_merge_target(docker_cfg)
    security_opt = docker_lists.docker_services_merge_string_list(
        normalized.get("security_opt", []),
        docker_lists.docker_services_no_new_privileges_security_opts(
            normalized["no_new_privileges"],
            normalized["deploy"]["type"],
        ),
        "append_unique",
    )
    service = {
        "image": normalized["image"],
        "logging": {"driver": "json-file", "options": {}},
        "user": normalized["user"],
        "environment": resolved_environment,
        "ports": ports,
        "volumes": volumes + mounts,
        "cap_drop": docker_lists.docker_services_string_list(normalized["cap_drop"]),
        "security_opt": security_opt,
        "healthcheck": normalized["healthcheck"],
    }
    return cfg, service


def test_real_n8n_docker_copy_renders_all_portable_fields_without_podman_options():
    cfg, compose_service = docker_compose_service_from_real_n8n()
    rendered = render_compose("container", compose_service)
    document = yaml.safe_load(rendered)
    service = document["services"]["n8n"]

    assert service["image"] == cfg["image"]
    assert service["user"] == cfg["user"]
    assert all(not isinstance(value, dict) for value in service["environment"].values())
    for key, value in cfg["environment"].items():
        if not isinstance(value, dict):
            assert service["environment"][key] == value
    assert service["environment"]["N8N_HOST"] == "n8n.int.example.test"
    assert service["environment"]["N8N_EDITOR_BASE_URL"] == "https://n8n.int.example.test:8443/"
    assert service["environment"]["WEBHOOK_URL"] == "https://n8n.int.example.test:8443/"
    assert service["ports"] == ["192.0.2.98:5678:5678"]
    assert rendered.count("192.0.2.98:5678:5678") == 1
    assert rendered.count("5678:5678") == 1
    assert "/opt/n8n:/home/node/.n8n" in service["volumes"]
    assert service["cap_drop"] == ["all"]
    assert service["security_opt"] == ["no-new-privileges:true"]
    assert service["healthcheck"] == cfg["healthcheck"]

    for name in ("postgres_user_secret", "postgres_pass_secret", "n8n_encryption_key_secret"):
        assert f"/opt/stacks/n8n/secrets/{name}:/run/secrets/{name}:ro" in service["volumes"]

    assert "runtime_options" not in rendered
    assert "delete_on_stop" not in rendered
    assert "restart_sec" not in rendered
    assert "immutable" not in rendered
    assert "replace" not in rendered


def test_legacy_container_without_no_new_privileges_renders_no_security_option():
    rendered = render_compose(
        "container",
        {
            "image": "registry.example.invalid/app:1.0.0",
            "logging": {"driver": "json-file", "options": {}},
            "ports": [{"published": 8080, "target": 8080, "protocol": "tcp"}],
        },
    )

    document = yaml.safe_load(rendered)
    assert "security_opt:" not in rendered
    assert document["services"]["n8n"]["ports"] == ["8080:8080"]


def test_swarm_secret_long_syntax_renders_metadata_and_legacy_compatibility():
    declarations = [
        {
            "name": "metadata_secret",
            "target": "/run/secrets/metadata_secret",
            "uid": "1000",
            "gid": "1001",
            "mode": "0400",
            "runtime_options": {"podman": {"immutable": True, "replace": False}},
            "origins": ["canonical"],
        },
        {
            "name": "metadata_free_secret",
            "target": "/run/secrets/metadata_free_secret",
            "origins": ["canonical"],
        },
    ]
    attachments = docker_secrets.docker_services_secret_attachments(
        ["legacy_secret"],
        declarations,
        "swarm",
    )
    rendered = render_compose(
        "swarm",
        {
            "image": "registry.example.invalid/app:1.0.0",
            "logging": {"driver": "json-file", "options": {}},
            "secrets": attachments,
        },
    )
    secrets = yaml.safe_load(rendered)["services"]["n8n"]["secrets"]

    assert secrets == [
        {"source": "legacy_secret", "target": "legacy_secret"},
        {
            "source": "metadata_secret",
            "target": "metadata_secret",
            "uid": "1000",
            "gid": "1001",
            "mode": 0o400,
        },
        {"source": "metadata_free_secret", "target": "metadata_free_secret"},
    ]
    assert secrets[1]["uid"] == "1000"
    assert secrets[1]["gid"] == "1001"
    assert "        mode: 0400" in rendered
    assert "runtime_options" not in rendered
    assert "immutable" not in rendered
    assert "replace" not in rendered
    assert "super-secret-value" not in rendered


def test_real_n8n_requires_no_docker_only_declaration_for_current_podman_runtime():
    cfg = n8n_config()

    assert {"stack", "named_networks", "networks", "configs", "placement", "constraints"}.isdisjoint(cfg)
    assert cfg["deploy"]["type"] == "container"


def test_n8n_quadlet_contains_all_canonical_secret_mounts_without_values():
    _, service, _, _, _, _, _, _ = normalize_both()
    env = Environment(loader=FileSystemLoader(PODMAN_TEMPLATE_DIR), trim_blocks=True, lstrip_blocks=True)
    rendered = env.get_template("container.container.j2").render(
        podman_service=service,
        podman_services_quadlet_dir="/etc/containers/systemd",
    )

    for secret in service["secrets"]:
        assert (
            f"Secret={secret['name']},target={secret['target']},uid={secret['uid']},gid={secret['gid']},mode={secret['mode']}"
        ) in rendered
    assert "super-secret-value" not in rendered
    assert "do-not-render-secret-values" not in rendered


def test_real_n8n_service_yaml_is_safe_before_infisical_values_exist():
    text = N8N_PATH.read_text()
    cfg = n8n_config()

    assert "internal_zone" not in text
    assert "{{ cloudflare_zone" not in text
    assert cfg["environment"]["N8N_HOST"] == {"value_template": "n8n.int.${cloudflare_zone}"}
    assert cfg["environment"]["N8N_EDITOR_BASE_URL"] == {"value_template": "https://n8n.int.${cloudflare_zone}:8443/"}
    assert cfg["environment"]["WEBHOOK_URL"] == {"value_template": "https://n8n.int.${cloudflare_zone}:8443/"}


def test_real_n8n_declares_cloudflare_zone_as_lookup_only():
    cfg = n8n_config()
    lookup = next(item for item in cfg["infisical"]["secrets_map"] if item["var"] == "cloudflare_zone")
    normalized = common.service_common_infisical_normalize(
        cfg["infisical"]["secrets_map"],
        cfg["infisical"]["fail_on_empty"],
    )

    assert lookup == {
        "var": "cloudflare_zone",
        "path": "/Cloudflare",
        "name": "ZONE",
        "check_mode_value": "check-mode.invalid",
    }
    assert lookup in normalized["secrets_map"]
    assert "secret" not in lookup
    assert "cloudflare_zone" not in {item["var"] for item in normalized["secret_declarations"]}
    assert [item["name"] for item in normalized["secret_declarations"]] == [
        "postgres_user_secret",
        "postgres_pass_secret",
        "n8n_encryption_key_secret",
    ]


def test_real_n8n_production_and_check_mode_environment_resolution():
    _, _, _, _, _, _, _, production = normalize_both()
    _, _, _, _, _, _, _, check_mode = normalize_both(check_mode=True)

    assert production["N8N_HOST"] == "n8n.int.example.test"
    assert production["N8N_EDITOR_BASE_URL"] == "https://n8n.int.example.test:8443/"
    assert production["WEBHOOK_URL"] == "https://n8n.int.example.test:8443/"
    assert check_mode["N8N_HOST"] == "n8n.int.check-mode.invalid"
    assert check_mode["N8N_EDITOR_BASE_URL"] == "https://n8n.int.check-mode.invalid:8443/"
    assert check_mode["WEBHOOK_URL"] == "https://n8n.int.check-mode.invalid:8443/"


def test_real_n8n_private_traefik_hostname_matches_resolved_application_hostname():
    cfg, _, _, _, _, _, _, environment = normalize_both()
    context = common.service_common_traefik_context(
        cfg,
        "n8n",
        ["n8n"],
        "example.test",
        {"n8n": {"local_ip": "192.0.2.98"}},
    )

    assert context["address"] == environment["N8N_HOST"] == "n8n.int.example.test"
    assert environment["N8N_EDITOR_BASE_URL"].endswith(":8443/")
    assert environment["WEBHOOK_URL"].endswith(":8443/")


def test_real_n8n_resolved_environment_is_scalar_before_podman_env_file_render():
    _, service, _, _, _, _, _, resolved_environment = normalize_both()
    env = Environment(loader=FileSystemLoader(PODMAN_TEMPLATE_DIR), trim_blocks=True, lstrip_blocks=True)
    env.filters["podman_env_file_key"] = podman.podman_env_file_key
    env.filters["podman_env_file_value"] = podman.podman_env_file_value
    rendered = env.get_template("env.env.j2").render(podman_service=service)

    assert service["env"] == resolved_environment
    assert all(not isinstance(value, dict) for value in service["env"].values())
    assert "N8N_HOST=n8n.int.example.test" in rendered
    assert "N8N_EDITOR_BASE_URL=https://n8n.int.example.test:8443/" in rendered
    assert "WEBHOOK_URL=https://n8n.int.example.test:8443/" in rendered
    assert "value_template" not in rendered
    assert "value_from" not in rendered


def test_ansible_service_loading_finalizes_n8n_without_infisical_values(tmp_path):
    ansible_playbook = shutil.which("ansible-playbook")
    assert ansible_playbook is not None
    playbook = tmp_path / "n8n-service-loading.yml"
    playbook.write_text(
        """---
- name: Exercise n8n service loading
  hosts: localhost
  connection: local
  gather_facts: false
  vars:
    docker_services_primary_manager: localhost
    local_ip: 192.0.2.10
  tasks:
    - name: Publish localhost inventory address
      ansible.builtin.set_fact:
        local_ip: 192.0.2.10

    - name: Load n8n as svcfiles
      ansible.builtin.include_vars:
        file: __N8N_PATH__
        name: svcfiles

    - name: Use svcfiles as the services mapping
      ansible.builtin.set_fact:
        services: "{{ svcfiles }}"

    - name: Assert typed domain entries remain unevaluated
      ansible.builtin.assert:
        that:
          - services.n8n.environment.N8N_HOST.value_template == "n8n.int.${cloudflare_zone}"
          - services.n8n.environment.N8N_EDITOR_BASE_URL.value_template == "https://n8n.int.${cloudflare_zone}:8443/"
""".replace("__N8N_PATH__", str(N8N_PATH))
    )

    result = subprocess.run(
        [ansible_playbook, "-i", "localhost,", str(playbook), "--check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "undefined" not in result.stderr.lower()


def test_n8n_docker_check_mode_keeps_infisical_facts_on_dispatch_host(tmp_path):
    ansible_playbook = Path(sys.executable).with_name("ansible-playbook")
    playbook = tmp_path / "n8n-docker-infisical-ownership.yml"
    playbook.write_text(
        """---
- name: Exercise Docker Infisical ownership away from the manager
  hosts: all
  strategy: linear
  connection: local
  gather_facts: false
  vars:
    docker_services_primary_manager: manager
    docker_services_deploy_host_effective: dispatch
    docker_services_stack_deploy_type: container
    docker_services_is_deploy_host: true
    infisical_lookup_default_params: must-not-be-used-in-check-mode
    infisical_flatten: true
  tasks:
    - name: Seed manager inventory and deliberately stale common facts
      when: inventory_hostname == "manager"
      ansible.builtin.set_fact:
        local_ip: 192.0.2.10
        service_common_infisical_config:
          secrets_map:
            - var: manager_stale
              path: /Synthetic
              name: STALE
        service_common_infisical_values:
          cloudflare_zone: manager-stale.invalid
          manager_stale: manager-stale-value
        service_common_secret_values:
          manager_stale: manager-stale-value
        service_common_secret_declarations:
          - name: manager_stale_secret
        service_common_resolved_environment:
          N8N_HOST: manager-stale.invalid
        docker_services_infisical_values:
          manager_stale: manager-docker-stale-value
        docker_services_secret_declarations:
          - name: manager_docker_stale_secret
        docker_services_resolved_environment:
          N8N_HOST: manager-docker-stale.invalid

    - name: Seed dispatch-host inventory values
      when: inventory_hostname == "dispatch"
      ansible.builtin.set_fact:
        local_ip: 192.0.2.98

    - name: Load the real n8n declaration on its dispatch host
      when: inventory_hostname == "dispatch"
      ansible.builtin.include_vars:
        file: __N8N_PATH__
        name: n8n_svcfiles

    - name: Switch only the n8n runtime to Docker
      when: inventory_hostname == "dispatch"
      ansible.builtin.set_fact:
        docker_services_svc: >-
          {{ n8n_svcfiles.n8n | combine({"runtime": "docker"}, recursive=true) }}

    - name: Resolve n8n through the Docker Infisical tasker
      when: inventory_hostname == "dispatch"
      ansible.builtin.include_tasks:
        file: __DOCKER_INFISICAL_TASKER__

    - name: Verify dispatch ownership and stale-manager isolation
      when: inventory_hostname == "manager"
      ansible.builtin.assert:
        that:
          - hostvars.dispatch.service_common_infisical_values.cloudflare_zone == "check-mode.invalid"
          - hostvars.dispatch.service_common_secret_values.cloudflare_zone == "check-mode.invalid"
          - hostvars.dispatch.service_common_resolved_environment.N8N_HOST == "n8n.int.check-mode.invalid"
          - hostvars.dispatch.docker_services_infisical_values.cloudflare_zone == "check-mode.invalid"
          - hostvars.dispatch.docker_services_resolved_environment.N8N_HOST == "n8n.int.check-mode.invalid"
          - hostvars.dispatch.docker_services_svc.environment.N8N_HOST == "n8n.int.check-mode.invalid"
          - hostvars.dispatch.docker_services_svc.environment.DB_POSTGRESDB_HOST == "192.0.2.10"
          - hostvars.dispatch.service_common_infisical_config.secrets_map | map(attribute="var") | list == ["cloudflare_zone", "postgres_user", "postgres_pass", "n8n_encryption_key"]
          - hostvars.dispatch.docker_services_secret_declarations | map(attribute="name") | list == ["postgres_user_secret", "postgres_pass_secret", "n8n_encryption_key_secret"]
          - hostvars.manager.service_common_infisical_values.manager_stale == "manager-stale-value"
          - hostvars.manager.service_common_resolved_environment.N8N_HOST == "manager-stale.invalid"
          - hostvars.manager.docker_services_infisical_values.manager_stale == "manager-docker-stale-value"
          - hostvars.manager.docker_services_resolved_environment.N8N_HOST == "manager-docker-stale.invalid"
""".replace("__N8N_PATH__", str(N8N_PATH)).replace(
            "__DOCKER_INFISICAL_TASKER__",
            str(REPO_ROOT / "ansible/roles/docker_services/tasks/sub_tasks/prep/infisical/tasker.yml"),
        )
    )
    environment = os.environ.copy()
    environment.update(
        {
            "ANSIBLE_CONFIG": str(REPO_ROOT / "ansible/ansible.cfg"),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible-local"),
        }
    )

    result = subprocess.run(
        [str(ansible_playbook), "-i", "manager,dispatch,", str(playbook), "--check"],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Service common Infisical | Fetch requested values" in result.stdout
    assert "skipping: [dispatch]" in result.stdout
    assert "undefined" not in (result.stdout + result.stderr).lower()
