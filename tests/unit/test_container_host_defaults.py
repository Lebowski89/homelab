from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from ast import literal_eval
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
NETBOX_MAIN_PATH = REPO_ROOT / "terraform/netbox/main.tf"
NETBOX_LOCALS_PATH = REPO_ROOT / "terraform/netbox/locals.tf"
NETBOX_PRIVATE_SAMPLE_PATH = REPO_ROOT / "terraform/netbox/private.auto.tfvars.sample"
PLAYBOOK_PATH = REPO_ROOT / "ansible/playbook.yml"
NORMALIZE_TASKS_PATH = REPO_ROOT / "ansible/tasks/container_host_defaults.yml"
SERVICES_DIR = REPO_ROOT / "ansible/group_vars/all/services"
SERVICE_COMMON_DIR = REPO_ROOT / "ansible/roles/service_common"
SERVICE_COMMON_PATHS = REPO_ROOT / "ansible/roles/service_common/tasks/paths.yml"

REMOVED_FIELD_NAMES = {f"{'docker'}_{'host'}_{suffix}" for suffix in ("puid", "pgid", "appdata_root", "data_root")}


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


def hcl_block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    assert match is not None, name
    start = match.end() - 1
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start + 1 : index]
    raise AssertionError(f"Unclosed HCL block: {name}")


def hcl_scalar(block: str, name: str):
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*([^\n]+)$", block)
    assert match is not None, name
    value = match.group(1).strip()
    if value == "null":
        return None
    return literal_eval(value)


def test_netbox_defines_canonical_container_host_fields_with_device_scope_and_validation():
    locals_source = NETBOX_LOCALS_PATH.read_text()
    main_source = NETBOX_MAIN_PATH.read_text()
    expected = {
        "container_host_puid": ("text", 200),
        "container_host_pgid": ("text", 210),
        "container_host_appdata_root": ("text", 220),
        "container_host_data_root": ("text", 230),
    }

    resource = main_source.split('resource "netbox_custom_field" "device" {', maxsplit=1)[1].split("\n}", maxsplit=1)[0]
    assert 'content_types = ["dcim.device"]' in resource
    for field_name, (field_type, weight) in expected.items():
        field = hcl_block(locals_source, field_name)
        assert hcl_scalar(field, "name") == field_name
        assert hcl_scalar(field, "type") == field_type
        assert hcl_scalar(field, "group_name") == "Containers"
        assert "container services" in hcl_scalar(field, "description")
        assert hcl_scalar(field, "weight") == weight
        if field_name in {"container_host_appdata_root", "container_host_data_root"}:
            assert hcl_scalar(field, "validation_regex") == "^/.*"


def test_netbox_container_host_defaults_allow_empty_values():
    defaults = hcl_block(NETBOX_LOCALS_PATH.read_text(), "device_custom_field_defaults")

    assert hcl_scalar(defaults, "container_host_puid") == ""
    assert hcl_scalar(defaults, "container_host_pgid") == ""
    assert hcl_scalar(defaults, "container_host_appdata_root") == ""
    assert hcl_scalar(defaults, "container_host_data_root") == ""


def test_tracked_host_sample_defines_canonical_container_values_only_for_applicable_hosts():
    hosts = hcl_block(NETBOX_PRIVATE_SAMPLE_PATH.read_text(), "host_private_values")
    field_names = (
        "container_host_puid",
        "container_host_pgid",
        "container_host_appdata_root",
        "container_host_data_root",
    )
    expected = {
        "mgt": ("1000", "1000", "/opt", "/opt"),
        "unraid": ("99", "100", "/mnt/user/appdata", "/mnt/user/data"),
        "plex": ("1000", "1000", "/opt", "/opt"),
        "n8n": ("1000", "1000", "/opt", "/opt"),
    }

    for host_name in ("router", "mgt", "unraid", "plex", "n8n", "pve1", "pg95", "pg96", "pg97"):
        custom_fields = hcl_block(hcl_block(hosts, host_name), "custom_fields")
        present_fields = [field_name for field_name in field_names if re.search(rf"(?m)^\s*{field_name}\s*=", custom_fields)]
        if host_name in expected:
            assert present_fields == list(field_names), host_name
            values = tuple(hcl_scalar(custom_fields, field_name) for field_name in field_names)
            assert values == expected[host_name], host_name
            assert isinstance(values[0], str), host_name
            assert isinstance(values[1], str), host_name
        else:
            assert present_fields == [], host_name


def test_container_host_defaults_extracts_canonical_values_without_mutating_input():
    host_variables = {
        "container_host_puid": "2000",
        "container_host_pgid": "2001",
        "container_host_appdata_root": "/srv/apps",
        "container_host_data_root": "/srv/data",
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
def test_container_host_defaults_omits_missing_or_empty_canonical_values(empty_value):
    assert (
        CONTAINER_HOST.container_host_defaults(
            {
                "container_host_puid": empty_value,
                "container_host_pgid": empty_value,
                "container_host_appdata_root": empty_value,
                "container_host_data_root": empty_value,
            }
        )
        == {}
    )


def test_container_host_defaults_retains_zero_ids():
    assert CONTAINER_HOST.container_host_defaults({"container_host_puid": 0, "container_host_pgid": 0}) == {
        "puid": 0,
        "pgid": 0,
    }


def test_container_host_defaults_omits_absent_values_and_rejects_non_mapping_input():
    assert CONTAINER_HOST.container_host_defaults({}) == {}
    with pytest.raises(AnsibleFilterError, match="host variables to be a mapping"):
        CONTAINER_HOST.container_host_defaults([])


@pytest.mark.parametrize(
    ("field", "canonical"),
    [
        ("container_host_puid", "2000"),
        ("container_host_pgid", "2001"),
        ("container_host_appdata_root", "/srv/apps"),
        ("container_host_data_root", "/srv/data"),
    ],
)
def test_netbox_inventory_composition_exports_canonical_values_and_omits_absent(field, canonical):
    compose = yaml.safe_load(NETBOX_INVENTORY_SAMPLE.read_text())["compose"]
    expression = compose[field]
    omitted = object()

    canonical_result = render_expression(expression, custom_fields={field: canonical}, omit=omitted)
    assert str(canonical_result) == canonical
    assert render_expression(expression, custom_fields={field: ""}, omit=omitted) is omitted
    assert render_expression(expression, custom_fields={}, omit=omitted) is omitted
    assert expression == f"custom_fields['{field}'] | default(omit, true)"


def test_netbox_inventory_preserves_unrelated_connection_grouping_and_priority_contracts():
    inventory = yaml.safe_load(NETBOX_INVENTORY_SAMPLE.read_text())
    compose = inventory["compose"]

    assert compose["ansible_host"] == ("custom_fields['tailscale_ip'] | default(primary_ip4.address | regex_replace('/.*', ''), true)")
    assert compose["ansible_user"] == "custom_fields['ansible_user'] | default('mgt', true)"
    assert compose["ansible_port"] == "custom_fields['ssh_port'] | default('22', true)"
    assert compose["local_ip"] == "primary_ip4.address | regex_replace('/.*', '')"
    assert compose["keepalived_priority_dns_vip_a"] == ("custom_fields['keepalived_priority_dns_vip_a'] | default(omit, true)")
    assert compose["keepalived_priority_dns_vip_b"] == ("custom_fields['keepalived_priority_dns_vip_b'] | default(omit, true)")
    assert inventory["group_by"] == ["device_roles", "tags"]
    assert inventory["query_filters"] == [{"has_primary_ip": "true"}]
    assert inventory["interfaces"] is True
    assert inventory["virtual_chassis"] is False


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


def test_synthetic_inventory_normalizes_canonical_values_and_keeps_adapter_facts_host_local(tmp_path):
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(
        """---
all:
  hosts:
    manager:
      ansible_connection: local
      container_host_puid: "2000"
      container_host_pgid: "2001"
      container_host_appdata_root: /srv/apps
      container_host_data_root: /srv/data
    storage:
      ansible_connection: local
      container_host_puid: "99"
      container_host_pgid: "100"
      container_host_appdata_root: /mnt/user/appdata
      container_host_data_root: /mnt/user/data
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

    - name: Resolve Docker defaults for the filesystem host
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

    - name: Resolve Podman defaults for the same host
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

    - name: Verify Podman and Docker derive equivalent canonical defaults
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
def test_real_arr_targets_use_canonical_host_values_and_preserve_inheritance(service_name, target_name, api_var, path_suffix):
    services = yaml.safe_load((SERVICES_DIR / f"{service_name}.yml").read_text())
    service = SERVICE_CATALOG.service_catalog_merge_target(services[service_name], target_name)
    common_variables = {
        "services_storage_host": "storage",
        "services_controller_host": "manager",
        "timezone": "Australia/Melbourne",
    }
    rendered = render_structure(
        service,
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
    declarations = [entry["var"] for entry in rendered["infisical"]["secrets_map"]]

    assert rendered["environment"]["PUID"] == 99
    assert rendered["environment"]["PGID"] == 100
    assert any(path["path"] == f"/mnt/user/appdata{path_suffix}" for path in rendered["paths"])
    assert rendered["postgres"]["enable"] is True
    assert declarations.count("postgres_user") == 1
    assert declarations.count("postgres_pass") == 1
    assert declarations.count(api_var) == 1


def test_removed_container_host_field_names_are_absent_from_tracked_repository():
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
        if (REPO_ROOT / path).is_file() and any(name in (REPO_ROOT / path).read_text(errors="ignore") for name in REMOVED_FIELD_NAMES)
    }

    assert references == set()


def test_service_common_operational_code_has_no_runtime_or_legacy_host_variables():
    operational_files = [
        path for path in SERVICE_COMMON_DIR.rglob("*") if path.is_file() and path.name != "README.md" and "__pycache__" not in path.parts
    ]
    source = "\n".join(path.read_text(errors="ignore") for path in operational_files)

    assert "docker_" + "host_" not in source
    assert "docker_services_" not in source
    assert "podman_services_" not in source


def test_podman_operational_code_has_no_legacy_container_host_dependency():
    podman_root = REPO_ROOT / "ansible/roles/podman_services"
    operational_files = [
        path for path in podman_root.rglob("*") if path.is_file() and path.name != "README.md" and "__pycache__" not in path.parts
    ]

    assert all("docker_" + "host_" not in path.read_text(errors="ignore") for path in operational_files)


def test_opencloud_specific_host_custom_fields_are_not_reintroduced():
    forbidden = ("docker_" + "host_" + "opencloud_", "container_host_" + "opencloud_")
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    offenders = []

    for relative_path in tracked:
        path = REPO_ROOT / relative_path
        if not path.is_file():
            continue
        source = path.read_text(errors="ignore")
        if any(marker in source for marker in forbidden):
            offenders.append(relative_path)

    assert offenders == []
