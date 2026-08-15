from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, StrictUndefined, meta
from jinja2.nativetypes import NativeEnvironment

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_DIR = REPO_ROOT / "ansible/group_vars/all/services"
SERVICE_HOST_VARS = REPO_ROOT / "ansible/group_vars/all/services.yml"
HOST_CONTRACT_TASKS = REPO_ROOT / "ansible/tasks/services_host_contract.yml"
PLAYBOOK_PATH = REPO_ROOT / "ansible/playbook.yml"
DOCKER_DISPATCH_PATH = REPO_ROOT / "ansible/tasks/service_catalog_dispatch_docker.yml"
PODMAN_DISPATCH_PATH = REPO_ROOT / "ansible/tasks/service_catalog_dispatch_podman.yml"
CATALOG_FILTER_PATH = REPO_ROOT / "ansible/filter_plugins/service_catalog.py"
DOCKER_INIT_PATH = REPO_ROOT / "ansible/roles/docker_services/tasks/sub_tasks/init.yml"
COMMON_VALIDATE_PATH = REPO_ROOT / "ansible/roles/service_common/tasks/validate.yml"
POSTGRES_ROLE_PATH = REPO_ROOT / "ansible/roles/postgres"

LEGACY_SERVICE_HOST_VARIABLES = {
    "docker_services_primary_manager",
    "docker_services_plex_host",
    "docker_services_unraid_host",
    "docker_services_log_root",
}
SWARM_HOST_CONSTRAINTS = {
    "node.labels.docker_services_host == docker_services_primary_manager",
    "node.labels.docker_services_host == docker_services_plex_host",
    "node.labels.docker_services_host == docker_services_unraid_host",
}
DOCKER_SERVICES_VARIABLE_PATTERN = re.compile(r"\bdocker_services_[a-z0-9_]+\b")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SERVICE_CATALOG = load_module(CATALOG_FILTER_PATH, "services_host_contract_catalog")


def load_services():
    services = {}
    for path in sorted((*SERVICES_DIR.glob("*.yml"), *SERVICES_DIR.glob("*.yaml"))):
        services.update(yaml.safe_load(path.read_text()) or {})
    return services


def task_named(tasks, name: str):
    return next(task for task in tasks if task.get("name") == name)


def scalar_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from scalar_strings(key)
            yield from scalar_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from scalar_strings(item)


def render(value, **variables):
    return NativeEnvironment(undefined=StrictUndefined).from_string(value).render(**variables)


def write_inventory(path: Path, *, controllers: list[str], storage_hosts: list[str]):
    all_hosts = [*controllers, *storage_hosts, "plex"]
    inventory = {
        "all": {
            "children": {
                "tags_ansible_manager": {"hosts": {host: {} for host in controllers}},
                "device_roles_storage": {"hosts": {host: {} for host in storage_hosts}},
            },
            "hosts": {host: {} for host in all_hosts},
        }
    }
    path.write_text(yaml.safe_dump(inventory, sort_keys=False))


def run_host_contract(
    tmp_path: Path,
    *,
    controllers: list[str],
    storage_hosts: list[str],
    plex_host: str = "plex",
):
    inventory = tmp_path / "inventory.yml"
    playbook = tmp_path / "host-contract.yml"
    write_inventory(inventory, controllers=controllers, storage_hosts=storage_hosts)
    playbook.write_text(
        f"""---
- name: Exercise runtime-neutral service host contract
  hosts: all
  connection: local
  gather_facts: false
  vars:
    services_controller_inventory_group: tags_ansible_manager
    services_storage_inventory_group: device_roles_storage
    services_plex_host: {plex_host}
    services_log_root: /var/log/skynet
  tasks:
    - name: Validate service host contract
      ansible.builtin.include_tasks:
        file: {HOST_CONTRACT_TASKS}

    - name: Confirm canonical and compatibility values
      ansible.builtin.assert:
        that:
          - services_controller_host == 'controller'
          - services_storage_host == 'storage'
          - docker_services_primary_manager == services_controller_host
"""
    )
    environment = os.environ.copy()
    environment.update(
        {
            "ANSIBLE_CONFIG": str(REPO_ROOT / "ansible/ansible.cfg"),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible-local"),
        }
    )
    return subprocess.run(
        [str(Path(sys.executable).with_name("ansible-playbook")), "-i", str(inventory), str(playbook), "--check"],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_repository_service_host_contract_uses_real_netbox_groups_and_explicit_plex_limit():
    variables = yaml.safe_load(SERVICE_HOST_VARS.read_text())
    inventory = yaml.safe_load((REPO_ROOT / "ansible/netbox.yml.sample").read_text())
    netbox_locals = (REPO_ROOT / "terraform/netbox/locals.tf").read_text()

    assert variables == {
        "services_controller_inventory_group": "tags_ansible_manager",
        "services_storage_inventory_group": "device_roles_storage",
        "services_plex_host": "plex",
        "services_log_root": "/var/log/skynet",
    }
    assert set(inventory["group_by"]) >= {"device_roles", "tags"}
    assert 'slug        = "ansible_manager"' in netbox_locals
    assert 'slug      = "storage"' in netbox_locals
    assert "services_plex_host: plex" in SERVICE_HOST_VARS.read_text()


def test_all_real_services_use_neutral_host_variables_and_keep_explicit_runtimes():
    offenders = {}
    for path in sorted((*SERVICES_DIR.glob("*.yml"), *SERVICES_DIR.glob("*.yaml"))):
        source_without_swarm_label_values = path.read_text()
        for constraint in SWARM_HOST_CONSTRAINTS:
            source_without_swarm_label_values = source_without_swarm_label_values.replace(constraint, "")
        matches = sorted(variable for variable in LEGACY_SERVICE_HOST_VARIABLES if variable in source_without_swarm_label_values)
        if matches:
            offenders[path.name] = matches

    services = load_services()
    runtimes = Counter(service["runtime"] for service in services.values())

    assert offenders == {}
    assert len(services) == 53
    assert runtimes == {"docker": 49, "podman": 4}
    assert services["adminer"]["runtime"] == "podman"
    assert services["n8n"]["runtime"] == "podman"
    assert services["thelounge"]["runtime"] == "podman"


def test_real_service_hosts_paths_and_base_target_inheritance_are_preserved():
    services = load_services()
    hostvars = {
        "mgt": {
            "local_ip": "192.0.2.10",
            "container_host_appdata_root": "/opt/appdata",
        },
        "plex": {
            "local_ip": "192.0.2.20",
            "container_host_appdata_root": "/opt/plex-appdata",
        },
        "unraid": {
            "local_ip": "192.0.2.30",
            "container_host_appdata_root": "/mnt/user/appdata",
            "container_host_data_root": "/mnt/user/data",
        },
    }
    variables = {
        "services_controller_host": "mgt",
        "services_plex_host": "plex",
        "services_storage_host": "unraid",
        "services_log_root": "/var/log/skynet",
        "hostvars": hostvars,
    }

    grafana = SERVICE_CATALOG.service_catalog_merge_target(services["grafana"])
    plex = SERVICE_CATALOG.service_catalog_merge_target(services["plex"])
    crowdsec = SERVICE_CATALOG.service_catalog_merge_target(services["crowdsec"])

    assert render(grafana["deploy"]["host"], **variables) == "mgt"
    assert render(grafana["paths"][0]["path"], **variables) == "/opt/appdata/grafana"
    assert render(plex["deploy"]["host"], **variables) == "plex"
    assert render(plex["paths"][0]["path"], **variables) == "/opt/plex-appdata/plex"
    assert render(plex["named_volumes"]["media_nfs"]["driver_opts"]["o"], **variables).startswith("addr=192.0.2.30,")
    assert render(crowdsec["paths"][4]["path"], **variables) == "/var/log/skynet"

    for service_name, target_name, api_var, path_suffix in (
        ("radarr", "radarr", "radarr_api", "/radarr"),
        ("radarr", "radarr_4k", "radarr_4k_api", "/radarr-4k"),
        ("sonarr", "sonarr", "sonarr_api", "/sonarr"),
        ("sonarr", "sonarr_4k", "sonarr_4k_api", "/sonarr-4k"),
    ):
        effective = SERVICE_CATALOG.service_catalog_merge_target(services[service_name], target_name)
        declarations = [entry["var"] for entry in effective["infisical"]["secrets_map"]]

        assert effective["runtime"] == "docker"
        assert render(effective["deploy"]["host"], **variables) == "unraid"
        assert any(render(path["path"], **variables).endswith(path_suffix) for path in effective["paths"])
        assert declarations.count("postgres_user") == 1
        assert declarations.count("postgres_pass") == 1
        assert declarations.count(api_var) == 1


def test_adapter_aliases_flow_only_from_canonical_values_and_podman_has_no_docker_coupling():
    contract = yaml.safe_load(HOST_CONTRACT_TASKS.read_text())
    aliases = task_named(contract, "Service host contract | Publish Docker adapter compatibility alias")["ansible.builtin.set_fact"]
    docker_vars = task_named(
        yaml.safe_load(DOCKER_DISPATCH_PATH.read_text()),
        "Service catalog dispatch | Include Docker service role",
    )["vars"]
    podman_vars = task_named(
        yaml.safe_load(PODMAN_DISPATCH_PATH.read_text()),
        "Service catalog dispatch | Include Podman service role",
    )["vars"]

    assert aliases == {
        "docker_services_primary_manager": "{{ services_controller_host }}",
    }
    assert {key: docker_vars[key] for key in aliases} == aliases
    assert podman_vars["podman_services_controller_host"] == "{{ services_controller_host }}"
    assert "docker_services_primary_manager" not in (REPO_ROOT / "ansible/roles/podman_services/defaults/main.yml").read_text()
    assert not any(legacy in SERVICE_HOST_VARS.read_text() for legacy in LEGACY_SERVICE_HOST_VARIABLES)

    neutral_orchestration_paths = [
        PLAYBOOK_PATH,
        REPO_ROOT / "ansible/tasks/drift_notification_preflight.yml",
        REPO_ROOT / "ansible/tasks/service_catalog_common_preflight.yml",
        REPO_ROOT / "ansible/group_vars/all/prometheus.yml",
        REPO_ROOT / "ansible/roles/hugo/defaults/main.yml",
        REPO_ROOT / "ansible/roles/podman_services/defaults/main.yml",
    ]
    assert all(legacy not in path.read_text() for path in neutral_orchestration_paths for legacy in LEGACY_SERVICE_HOST_VARIABLES)


def test_postgres_role_has_no_docker_services_variable_dependencies():
    offenders = {}
    for path in sorted(POSTGRES_ROLE_PATH.rglob("*")):
        if path.suffix in {".yaml", ".yml"}:
            document = yaml.safe_load(path.read_text())
            dependencies = {
                match.group(0) for scalar in scalar_strings(document) for match in DOCKER_SERVICES_VARIABLE_PATTERN.finditer(scalar)
            }
        elif path.suffix == ".j2":
            parsed_template = Environment().parse(path.read_text())
            dependencies = {
                variable
                for variable in meta.find_undeclared_variables(parsed_template)
                if DOCKER_SERVICES_VARIABLE_PATTERN.fullmatch(variable)
            }
        else:
            continue

        if dependencies:
            offenders[str(path.relative_to(POSTGRES_ROLE_PATH))] = sorted(dependencies)

    assert offenders == {}


def test_host_contract_precedes_other_preparation_and_linear_dispatch_remains_explicit():
    playbook = yaml.safe_load(PLAYBOOK_PATH.read_text())
    play = next(item for item in playbook if item.get("name") == "Deploy homelab services")

    assert play["strategy"] == "linear"
    assert play["pre_tasks"][0]["name"] == "Include runtime-neutral service host contract validation"
    assert play["pre_tasks"][0]["tags"] == "always"
    assert play["pre_tasks"][0]["ansible.builtin.include_tasks"]["apply"]["tags"] == "always"


def test_filesystem_hosts_are_validated_before_adapter_or_common_mutation():
    docker_init = yaml.safe_load(DOCKER_INIT_PATH.read_text())
    docker_validate = task_named(docker_init, "Initialize | Validate filesystem hosts")
    docker_defaults = task_named(docker_init, "Initialize | Build container host defaults")
    common_validate = task_named(
        yaml.safe_load(COMMON_VALIDATE_PATH.read_text()),
        "Service common | Validate target hosts",
    )

    assert docker_init.index(docker_validate) < docker_init.index(docker_defaults)
    assert docker_validate["loop_control"]["loop_var"] == "docker_services_fs_host"
    assert "docker_services_fs_host in hostvars" in docker_validate["ansible.builtin.assert"]["that"]
    assert "docker_services_fs_host in ansible_play_hosts_all" in docker_validate["ansible.builtin.assert"]["that"]
    assert "service_common_target_host in hostvars" in common_validate["ansible.builtin.assert"]["that"]
    assert "service_common_target_host in ansible_play_hosts_all" in common_validate["ansible.builtin.assert"]["that"]


def test_singleton_group_resolution_and_aliases_succeed_with_one_host(tmp_path: Path):
    result = run_host_contract(
        tmp_path,
        controllers=["controller"],
        storage_hosts=["storage"],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Confirm canonical and compatibility values" in result.stdout


@pytest.mark.parametrize(
    ("controllers", "storage_hosts"),
    [
        ([], ["storage"]),
        (["controller", "controller-two"], ["storage"]),
        (["controller"], []),
        (["controller"], ["storage", "storage-two"]),
    ],
)
def test_singleton_group_validation_rejects_zero_or_multiple_matches(
    tmp_path: Path,
    controllers: list[str],
    storage_hosts: list[str],
):
    result = run_host_contract(tmp_path, controllers=controllers, storage_hosts=storage_hosts)
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "require exactly one host" in output
    assert "Publish Docker adapter compatibility alias" not in output


def test_canonical_host_validation_rejects_unknown_explicit_plex_before_aliases(tmp_path: Path):
    result = run_host_contract(
        tmp_path,
        controllers=["controller"],
        storage_hosts=["storage"],
        plex_host="missing-plex",
    )
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "must be non-empty active inventory hosts" in output
    assert "Publish Docker adapter compatibility alias" not in output
