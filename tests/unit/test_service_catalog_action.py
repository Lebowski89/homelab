import importlib.util
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from ansible.errors import AnsibleActionFail

REPO_ROOT = Path(__file__).resolve().parents[2]
ACTION_PATH = REPO_ROOT / "ansible/action_plugins/service_catalog_materialize.py"
SERVICES_DIR = REPO_ROOT / "ansible/group_vars/all/services"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ACTION = load_module(ACTION_PATH, "service_catalog_materialize_action")


def identity(value):
    return value


def test_selective_materialization_preserves_order_and_inputs_and_merges_once():
    services = {
        "first": {
            "runtime": "docker",
            "environment": {"BASE": "first"},
            "targets": {"primary": {"environment": {"TARGET": "primary"}}},
        },
        "second": {"runtime": "podman", "environment": {"BASE": "second"}},
        "unselected": {"runtime": "docker", "environment": {"VALUE": "must-not-be-templated"}},
    }
    selected = [
        {"name": "second", "runtime": "podman", "dispatch_host": "host-a"},
        {"name": "first", "target": "primary", "runtime": "docker", "dispatch_host": "host-a"},
    ]
    original_services = deepcopy(services)
    original_selected = deepcopy(selected)
    merge_calls = []
    template_calls = []

    def tracked_merge(service_cfg, target):
        merge_calls.append((service_cfg, target))
        return ACTION._CANONICAL_MERGE_TARGET(service_cfg, target)

    def tracked_template(config):
        template_calls.append(config)
        return deepcopy(config)

    result = ACTION.materialize_selected(
        services,
        selected,
        tracked_template,
        merge_target=tracked_merge,
    )

    assert [entry["name"] for entry in result] == ["second", "first"]
    assert [target for _, target in merge_calls] == [None, "primary"]
    assert len(merge_calls) == len(selected)
    assert len(template_calls) == len(selected)
    assert all(call is not services["unselected"] for call in template_calls)
    assert result[1]["config"]["environment"] == {"BASE": "first", "TARGET": "primary"}
    assert "targets" not in result[1]["config"]
    assert services == original_services
    assert selected == original_selected
    assert result[0] is not selected[0]


@pytest.mark.parametrize(
    ("services", "selected", "message"),
    [
        ([], [], "services source must be a mapping"),
        ({}, {}, "selected entries must be a list"),
        ({}, ["bad"], "selected entry 0 must be a mapping"),
        ({"app": {}}, [{"name": "app", "config": {}}], "must not already contain config"),
        ({"app": {}}, [{}], "entry 0.name must be a non-empty string"),
        ({"app": {}}, [{"name": "missing"}], "references unknown service 'missing'"),
        ({"app": {}}, [{"name": "app"}], "runtime must be one of: docker, podman"),
        ({"app": {}}, [{"name": "app", "runtime": 1}], "runtime must be one of: docker, podman"),
        ({"app": {}}, [{"name": "app", "runtime": "containerd"}], "runtime must be one of: docker, podman"),
        (
            {"app": {}},
            [{"name": "app", "runtime": "docker", "target": ""}],
            "entry 0.target must be a non-empty string",
        ),
        (
            {"app": {"runtime": "docker", "targets": {"primary": {}}}},
            [{"name": "app", "runtime": "docker", "target": "missing"}],
            "Available targets: primary",
        ),
        (
            {
                "app": {
                    "runtime": "docker",
                    "targets": {"primary": {"targets": {"nested": {}}}},
                }
            },
            [{"name": "app", "runtime": "docker", "target": "primary"}],
            "must not contain nested targets",
        ),
    ],
)
def test_selective_materialization_rejects_invalid_inputs(services, selected, message):
    with pytest.raises(AnsibleActionFail, match=message):
        ACTION.materialize_selected(services, selected, identity)


def portable_services(runtime):
    return {
        "app": {
            "runtime": runtime,
            "environment": {"BASE": "base", "SHARED": "base"},
            "volumes": ["base:/base"],
            "targets": {
                "primary": {
                    "environment": {"TARGET": "target", "SHARED": "target"},
                    "volumes": ["target:/target"],
                }
            },
        }
    }


def test_docker_and_podman_materialize_the_same_portable_configuration():
    docker = ACTION.materialize_selected(
        portable_services("docker"),
        [{"name": "app", "target": "primary", "runtime": "docker"}],
        identity,
    )[0]["config"]
    podman = ACTION.materialize_selected(
        portable_services("podman"),
        [{"name": "app", "target": "primary", "runtime": "podman"}],
        identity,
    )[0]["config"]

    assert {key: value for key, value in docker.items() if key != "runtime"} == {
        key: value for key, value in podman.items() if key != "runtime"
    }


def load_arr_services():
    services = {}
    for name in ("radarr", "sonarr"):
        services.update(yaml.safe_load((SERVICES_DIR / f"{name}.yml").read_text()))
    return services


@pytest.mark.parametrize(
    ("service_name", "target_name", "api_var"),
    [
        ("radarr", "radarr", "radarr_api"),
        ("radarr", "radarr_4k", "radarr_4k_api"),
        ("sonarr", "sonarr", "sonarr_api"),
        ("sonarr", "sonarr_4k", "sonarr_4k_api"),
    ],
)
def test_real_arr_targets_retain_base_and_target_infisical_declarations(service_name, target_name, api_var):
    result = ACTION.materialize_selected(
        load_arr_services(),
        [{"name": service_name, "target": target_name, "runtime": "docker"}],
        identity,
    )
    declarations = [entry["var"] for entry in result[0]["config"]["infisical"]["secrets_map"]]

    assert declarations.count("postgres_user") == 1
    assert declarations.count("postgres_pass") == 1
    assert declarations.count(api_var) == 1


def test_action_templates_selected_config_in_dispatch_host_context_only(tmp_path):
    ansible_playbook = Path(sys.executable).with_name("ansible-playbook")
    playbook = tmp_path / "selective-materialization.yml"
    playbook.write_text(
        """---
- name: Exercise selective service materialization
  hosts: localhost
  connection: local
  gather_facts: false
  vars:
    svcfiles:
      selected:
        runtime: docker
        environment:
          ADDRESS: "{{ hostvars[inventory_hostname].local_ip }}"
        targets:
          primary:
            paths:
              - path: "{{ hostvars[inventory_hostname].application_root }}/selected"
      unselected:
        runtime: docker
        environment:
          VALUE: "{{ deliberately_undefined }}"
    selected_entries:
      - name: selected
        target: primary
        runtime: docker
        dispatch_host: localhost
  tasks:
    - name: Publish dispatch-host values
      ansible.builtin.set_fact:
        local_ip: 192.0.2.20
        application_root: /srv/apps

    - name: Materialize selected service
      service_catalog_materialize:
        source_var: svcfiles
        selected: "{{ selected_entries }}"

    - name: Verify concrete selected configuration
      ansible.builtin.assert:
        that:
          - service_catalog_host_materialized | length == 1
          - service_catalog_host_materialized[0].config.environment.ADDRESS == '192.0.2.20'
          - service_catalog_host_materialized[0].config.paths[0].path == '/srv/apps/selected'
"""
    )
    environment = os.environ.copy()
    environment.update(
        {
            "ANSIBLE_CONFIG": str(REPO_ROOT / "ansible/ansible.cfg"),
            "ANSIBLE_ACTION_PLUGINS": str(REPO_ROOT / "ansible/action_plugins"),
            "ANSIBLE_LIBRARY": str(REPO_ROOT / "ansible/library"),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible-local"),
        }
    )

    result = subprocess.run(
        [str(ansible_playbook), "-i", "localhost,", str(playbook), "--check"],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "deliberately_undefined" not in result.stdout + result.stderr


def test_action_reads_source_by_name_without_templating_the_whole_mapping():
    source = ACTION_PATH.read_text()

    assert "task_vars[source_var]" in source
    assert "self._templar.template(config, fail_on_undefined=True)" in source
    assert "self._templar.template(task_vars[source_var]" not in source
