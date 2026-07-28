from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from ansible.errors import AnsibleFilterError
from jinja2 import StrictUndefined
from jinja2.nativetypes import NativeEnvironment

REPO_ROOT = Path(__file__).resolve().parents[2]
FILTER_PATH = REPO_ROOT / "ansible/filter_plugins/container_host.py"
CATALOG_PATH = REPO_ROOT / "ansible/filter_plugins/service_catalog.py"
NETBOX_INVENTORY_SAMPLE = REPO_ROOT / "ansible/netbox.yml.sample"
PLAYBOOK_PATH = REPO_ROOT / "ansible/playbook.yml"
NORMALIZE_TASKS_PATH = REPO_ROOT / "ansible/tasks/container_host_defaults.yml"
SERVICES_DIR = REPO_ROOT / "ansible/group_vars/all/services"
SERVICE_COMMON_DIR = REPO_ROOT / "ansible/roles/service_common"
SERVICE_COMMON_PATHS = REPO_ROOT / "ansible/roles/service_common/tasks/paths.yml"

LEGACY_NAMES = {
    "docker_host_puid",
    "docker_host_pgid",
    "docker_host_appdata_root",
    "docker_host_data_root",
}
LEGACY_REFERENCE_ALLOWLIST = {
    # Runtime compatibility boundaries.
    "ansible/filter_plugins/container_host.py",
    "ansible/netbox.yml.sample",
    # Deferred live NetBox custom-field schema and example values.
    "terraform/netbox/locals.tf",
    "terraform/netbox/private.auto.tfvars.sample",
    # This regression names the legacy compatibility inputs deliberately.
    "tests/unit/test_container_host_defaults.py",
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


CONTAINER_HOST = load_module(FILTER_PATH, "container_host_defaults_test")
SERVICE_CATALOG = load_module(CATALOG_PATH, "container_host_catalog_test")


def render_expression(expression, **variables):
    environment = NativeEnvironment(undefined=StrictUndefined)
    return environment.from_string("{{ " + expression + " }}").render(**variables)


def render_structure(value, variables):
    if isinstance(value, dict):
        return {key: render_structure(item, variables) for key, item in value.items()}
    if isinstance(value, list):
        return [render_structure(item, variables) for item in value]
    if isinstance(value, str) and ("{{" in value or "{%" in value):
        return NativeEnvironment(undefined=StrictUndefined).from_string(value).render(**variables)
    return deepcopy(value)


def test_container_host_defaults_prefers_canonical_values_without_mutating_input():
    host_variables = {
        "container_host_puid": "2000",
        "docker_host_puid": "1000",
        "container_host_pgid": "2001",
        "docker_host_pgid": "1001",
        "container_host_appdata_root": "/srv/apps",
        "docker_host_appdata_root": "/legacy/apps",
        "container_host_data_root": "/srv/data",
        "docker_host_data_root": "/legacy/data",
    }
    original = deepcopy(host_variables)

    assert CONTAINER_HOST.container_host_defaults(host_variables) == {
        "puid": "2000",
        "pgid": "2001",
        "appdata_root": "/srv/apps",
        "data_root": "/srv/data",
    }
    assert host_variables == original


@pytest.mark.parametrize("empty_value", [None, "", "   "])
def test_container_host_defaults_uses_legacy_values_for_missing_or_empty_canonical_values(empty_value):
    assert CONTAINER_HOST.container_host_defaults(
        {
            "container_host_puid": empty_value,
            "docker_host_puid": "99",
            "container_host_pgid": empty_value,
            "docker_host_pgid": "100",
            "container_host_appdata_root": empty_value,
            "docker_host_appdata_root": "/mnt/user/appdata",
            "container_host_data_root": empty_value,
            "docker_host_data_root": "/mnt/user/data",
        }
    ) == {
        "puid": "99",
        "pgid": "100",
        "appdata_root": "/mnt/user/appdata",
        "data_root": "/mnt/user/data",
    }


def test_container_host_defaults_omits_absent_values_and_rejects_non_mapping_input():
    assert CONTAINER_HOST.container_host_defaults({}) == {}
    with pytest.raises(AnsibleFilterError, match="host variables to be a mapping"):
        CONTAINER_HOST.container_host_defaults([])


@pytest.mark.parametrize(
    ("field", "canonical", "legacy"),
    [
        ("container_host_puid", "2000", "1000"),
        ("container_host_pgid", "2001", "1001"),
        ("container_host_appdata_root", "/srv/apps", "/legacy/apps"),
        ("container_host_data_root", "/srv/data", "/legacy/data"),
    ],
)
def test_netbox_inventory_composition_prefers_canonical_then_legacy_and_omits_absent(field, canonical, legacy):
    compose = yaml.safe_load(NETBOX_INVENTORY_SAMPLE.read_text())["compose"]
    expression = compose[field]
    legacy_field = field.replace("container_host_", "docker_host_")
    omitted = object()

    assert str(render_expression(expression, custom_fields={field: canonical, legacy_field: legacy}, omit=omitted)) == canonical
    assert str(render_expression(expression, custom_fields={field: "", legacy_field: legacy}, omit=omitted)) == legacy
    assert str(render_expression(expression, custom_fields={legacy_field: legacy}, omit=omitted)) == legacy
    assert render_expression(expression, custom_fields={}, omit=omitted) is omitted
    assert compose[legacy_field] == f"custom_fields['{legacy_field}'] | default(omit, true)"


def test_playbook_normalizes_host_defaults_before_loading_service_definitions():
    playbook = yaml.safe_load(PLAYBOOK_PATH.read_text())
    play = next(item for item in playbook if item["name"] == "Deploy homelab services")
    host_contract = next(task for task in play["pre_tasks"] if task["name"] == "Include runtime-neutral service host contract validation")
    include = next(task for task in play["pre_tasks"] if task["name"] == "Include runtime-neutral container host default normalization")
    load_services = next(task for task in play["tasks"] if task["name"].startswith("Load all service definitions"))

    assert include["ansible.builtin.include_tasks"]["file"] == "tasks/container_host_defaults.yml"
    assert include["ansible.builtin.include_tasks"]["apply"]["tags"] == "always"
    assert include["tags"] == "always"
    assert play["pre_tasks"].index(host_contract) == 0
    assert play["pre_tasks"].index(include) == 1
    assert load_services in play["tasks"]


def test_synthetic_inventory_normalizes_legacy_values_and_keeps_adapter_facts_host_local(tmp_path):
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(
        """---
all:
  hosts:
    manager:
      ansible_connection: local
      container_host_puid: "2000"
      docker_host_puid: "1000"
      container_host_pgid: "2001"
      docker_host_pgid: "1001"
      container_host_appdata_root: /srv/apps
      docker_host_appdata_root: /legacy/apps
      container_host_data_root: /srv/data
      docker_host_data_root: /legacy/data
    storage:
      ansible_connection: local
      docker_host_puid: "99"
      docker_host_pgid: "100"
      docker_host_appdata_root: /mnt/user/appdata
      docker_host_data_root: /mnt/user/data
    storage_two:
      ansible_connection: local
      container_host_puid: "3000"
      container_host_pgid: "3001"
      container_host_appdata_root: /srv/other-apps
      container_host_data_root: /srv/other-data
"""
    )
    playbook = tmp_path / "container-host-defaults.yml"
    playbook.write_text(
        f"""---
- name: Exercise runtime-neutral container host defaults
  hosts: all
  gather_facts: false
  strategy: linear
  tasks:
    - name: Normalize each inventory host
      ansible.builtin.include_tasks: {NORMALIZE_TASKS_PATH}

    - name: Verify canonical publication and omission
      ansible.builtin.assert:
        that:
          - container_host_defaults is mapping
          - inventory_hostname != 'storage' or container_host_puid == '99'
          - inventory_hostname != 'storage' or container_host_appdata_root == '/mnt/user/appdata'
          - inventory_hostname != 'manager' or container_host_puid == '2000'
          - inventory_hostname != 'manager' or container_host_data_root == '/srv/data'

    - name: Resolve Docker defaults for the legacy-only filesystem host
      when: inventory_hostname == 'manager'
      ansible.builtin.include_tasks: {REPO_ROOT / "ansible/roles/docker_services/tasks/_init.yml"}
      vars:
        docker_services_service_cfg:
          enabled: true
          image: example.invalid/app:1.0.0
          deploy:
            type: swarm
            host: storage
        docker_services_service_cfg_found: true
        docker_services_service_target: base
        docker_services_role_prefix: synthetic
        docker_services_common_context:
          service_name: synthetic
          runtime: docker
          dispatch_host: manager
          controller_host: manager
          lookup_values: {{}}
          resolved_environment: {{}}
          secret_declarations: []
        docker_services_primary_manager: manager
        docker_services_validate: false
        service_cfg: {{}}
        service_target: base
        role_prefix: synthetic
        service_cfg_found: true

    - name: Verify Docker used the filesystem host values
      when: inventory_hostname == 'manager'
      ansible.builtin.assert:
        that:
          - docker_services_common_host_defaults.keys() | list == ['storage']
          - docker_services_common_host_defaults.storage.puid == '99'
          - docker_services_common_host_defaults.storage.appdata_root == '/mnt/user/appdata'
          - docker_services_controller_host == 'manager'

    - name: Resolve Docker defaults for the next service
      when: inventory_hostname == 'manager'
      ansible.builtin.include_tasks: {REPO_ROOT / "ansible/roles/docker_services/tasks/_init.yml"}
      vars:
        docker_services_service_cfg:
          enabled: true
          image: example.invalid/other:1.0.0
          deploy:
            type: container
            host: storage_two
        docker_services_service_cfg_found: true
        docker_services_service_target: base
        docker_services_role_prefix: synthetic-other
        docker_services_common_context:
          service_name: synthetic-other
          runtime: docker
          dispatch_host: manager
          controller_host: manager
          lookup_values: {{}}
          resolved_environment: {{}}
          secret_declarations: []
        docker_services_primary_manager: manager
        docker_services_validate: false
        service_cfg: {{}}
        service_target: base
        role_prefix: synthetic-other
        service_cfg_found: true

    - name: Verify Docker reset service-specific defaults
      when: inventory_hostname == 'manager'
      ansible.builtin.assert:
        that:
          - docker_services_common_host_defaults.keys() | list == ['storage_two']
          - docker_services_common_host_defaults.storage_two.puid == '3000'
          - docker_services_stack_deploy_type == 'container'
          - docker_services_controller_host == 'manager'

    - name: Resolve Podman defaults for the same legacy-only host
      when: inventory_hostname == 'storage'
      ansible.builtin.include_tasks: {REPO_ROOT / "ansible/roles/podman_services/tasks/sub_tasks/init.yml"}
      vars:
        podman_services_service_cfg:
          enabled: true
          runtime: podman
          image: example.invalid/app:1.0.0
          deploy:
            type: container
            host: storage
        podman_services_role_prefix: synthetic
        podman_services_common_context:
          service_name: synthetic
          runtime: podman
          dispatch_host: storage
          controller_host: manager
          lookup_values: {{}}
          resolved_environment: {{}}
          secret_declarations: []
        podman_services_state: check

    - name: Verify Podman and Docker derive equivalent legacy defaults
      when: inventory_hostname == 'storage'
      ansible.builtin.assert:
        that:
          - podman_services_common_host_defaults.storage == container_host_defaults
          - podman_services_common_host_defaults.storage.puid == '99'
          - podman_services_common_host_defaults.storage.data_root == '/mnt/user/data'
          - podman_services_controller_host == 'manager'
"""
    )
    environment = os.environ.copy()
    environment.update(
        {
            "ANSIBLE_CONFIG": str(REPO_ROOT / "ansible/ansible.cfg"),
            "ANSIBLE_FILTER_PLUGINS": os.pathsep.join(
                (
                    str(REPO_ROOT / "ansible/filter_plugins"),
                    str(REPO_ROOT / "ansible/roles/docker_services/filter_plugins"),
                    str(REPO_ROOT / "ansible/roles/podman_services/filter_plugins"),
                )
            ),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible-local"),
        }
    )

    result = subprocess.run(
        [str(Path(sys.executable).with_name("ansible-playbook")), "-i", str(inventory), str(playbook), "--check"],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_explicit_service_and_target_values_override_inventory_defaults_before_adapter_dispatch():
    services = {
        "portable": {
            "runtime": "podman",
            "user": "1100:1101",
            "paths": [{"path": "/opt/portable", "owner": "1100", "group": "1101"}],
            "targets": {
                "alternate": {
                    "user": "2200:2201",
                    "paths": [{"path": "/opt/alternate", "owner": "2200", "group": "2201"}],
                }
            },
        }
    }
    defaults = CONTAINER_HOST.container_host_defaults({"container_host_puid": "3300", "container_host_pgid": "3301"})
    base = SERVICE_CATALOG.service_catalog_merge_target(services["portable"])
    target = SERVICE_CATALOG.service_catalog_merge_target(services["portable"], "alternate")
    path_task = next(
        task
        for task in yaml.safe_load(SERVICE_COMMON_PATHS.read_text())
        if task["name"] == "Service common paths | Apply filesystem state on target host"
    )
    owner_expression = path_task["ansible.builtin.file"]["owner"].removeprefix("{{ ").removesuffix(" }}")
    group_expression = path_task["ansible.builtin.file"]["group"].removeprefix("{{ ").removesuffix(" }}")

    assert base["user"] == "1100:1101"
    assert target["user"] == "2200:2201"
    assert target["paths"][-1]["owner"] == "2200"
    assert target["paths"][-1]["group"] == "2201"
    assert defaults == {"puid": "3300", "pgid": "3301"}
    assert (
        render_expression(
            owner_expression,
            service_common_path_item=target["paths"][-1],
            service_common_path_default_owner=defaults["puid"],
        )
        == 2200
    )
    assert (
        render_expression(
            group_expression,
            service_common_path_item=target["paths"][-1],
            service_common_path_default_group=defaults["pgid"],
        )
        == 2201
    )


@pytest.mark.parametrize(
    ("service_name", "target_name", "api_var", "path_suffix"),
    [
        ("radarr", "radarr", "radarr_api", "/radarr"),
        ("radarr", "radarr_4k", "radarr_4k_api", "/radarr-4k"),
        ("sonarr", "sonarr", "sonarr_api", "/sonarr"),
        ("sonarr", "sonarr_4k", "sonarr_4k_api", "/sonarr-4k"),
    ],
)
def test_real_arr_targets_render_equivalently_and_preserve_inheritance(service_name, target_name, api_var, path_suffix):
    source = (SERVICES_DIR / f"{service_name}.yml").read_text()
    canonical_services = yaml.safe_load(source)
    legacy_services = yaml.safe_load(source.replace("container_host_", "docker_host_"))
    canonical = SERVICE_CATALOG.service_catalog_merge_target(canonical_services[service_name], target_name)
    legacy = SERVICE_CATALOG.service_catalog_merge_target(legacy_services[service_name], target_name)
    common_variables = {
        "services_storage_host": "storage",
        "services_controller_host": "manager",
        "timezone": "Australia/Melbourne",
    }
    canonical_rendered = render_structure(
        canonical,
        {
            **common_variables,
            "hostvars": {
                "storage": {
                    "container_host_puid": "99",
                    "container_host_pgid": "100",
                    "container_host_appdata_root": "/mnt/user/appdata",
                    "container_host_data_root": "/mnt/user/data",
                },
                "manager": {"local_ip": "192.0.2.10"},
            },
        },
    )
    legacy_rendered = render_structure(
        legacy,
        {
            **common_variables,
            "hostvars": {
                "storage": {
                    "docker_host_puid": "99",
                    "docker_host_pgid": "100",
                    "docker_host_appdata_root": "/mnt/user/appdata",
                    "docker_host_data_root": "/mnt/user/data",
                },
                "manager": {"local_ip": "192.0.2.10"},
            },
        },
    )
    declarations = [entry["var"] for entry in canonical_rendered["infisical"]["secrets_map"]]

    assert canonical_rendered == legacy_rendered
    assert canonical_rendered["environment"]["PUID"] == 99
    assert canonical_rendered["environment"]["PGID"] == 100
    assert any(path["path"] == f"/mnt/user/appdata{path_suffix}" for path in canonical_rendered["paths"])
    assert canonical_rendered["postgres"]["enable"] is True
    assert declarations.count("postgres_user") == 1
    assert declarations.count("postgres_pass") == 1
    assert declarations.count(api_var) == 1


def test_service_definitions_use_only_canonical_container_host_names():
    offenders = {}
    for path in sorted(SERVICES_DIR.glob("*.yml")):
        matches = sorted(name for name in LEGACY_NAMES if name in path.read_text())
        if matches:
            offenders[path.name] = matches
    assert offenders == {}


def test_remaining_legacy_references_match_the_documented_compatibility_allowlist():
    tracked = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    references = {
        path
        for path in tracked
        if (REPO_ROOT / path).is_file() and any(name in (REPO_ROOT / path).read_text(errors="ignore") for name in LEGACY_NAMES)
    }

    assert references == LEGACY_REFERENCE_ALLOWLIST


def test_service_common_operational_code_has_no_runtime_or_legacy_host_variables():
    operational_files = [
        path for path in SERVICE_COMMON_DIR.rglob("*") if path.is_file() and path.name != "README.md" and "__pycache__" not in path.parts
    ]
    source = "\n".join(path.read_text(errors="ignore") for path in operational_files)

    assert "docker_host_" not in source
    assert "docker_services_" not in source
    assert "podman_services_" not in source
