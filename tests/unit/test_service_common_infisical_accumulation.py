from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT_PATH = REPO_ROOT / "ansible/tasks/service_catalog_common_preflight.yml"

SYNTHETIC_VALUES = {
    "ALPHA": "SYNTHETIC_ALPHA_VALUE_DO_NOT_LOG",
    "BRAVO": "SYNTHETIC_BRAVO_VALUE_DO_NOT_LOG",
    "CHARLIE": "SYNTHETIC_CHARLIE_VALUE_DO_NOT_LOG",
    "EMPTY": "",
}


def write_fake_infisical_collection(tmp_path: Path) -> Path:
    collections_root = tmp_path / "collections"
    collection_root = collections_root / "ansible_collections/infisical/vault"
    lookup_dir = collection_root / "plugins/lookup"
    lookup_dir.mkdir(parents=True)
    (collection_root / "galaxy.yml").write_text(
        """---
namespace: infisical
name: vault
version: 1.0.0
readme: README.md
authors: [tests]
"""
    )
    (collection_root / "README.md").write_text("Synthetic repository-only test collection.\n")
    (lookup_dir / "read_secrets.py").write_text(
        """from ansible.plugins.lookup import LookupBase


VALUES = {
    "ALPHA": "SYNTHETIC_ALPHA_VALUE_DO_NOT_LOG",
    "BRAVO": "SYNTHETIC_BRAVO_VALUE_DO_NOT_LOG",
    "CHARLIE": "SYNTHETIC_CHARLIE_VALUE_DO_NOT_LOG",
    "EMPTY": "",
}


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        return [{"value": VALUES[kwargs["secret_name"]]}]
"""
    )
    return collections_root


def ansible_environment(tmp_path: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "ANSIBLE_CONFIG": str(REPO_ROOT / "ansible/ansible.cfg"),
            "ANSIBLE_COLLECTIONS_PATH": str(write_fake_infisical_collection(tmp_path)),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible-local"),
            "ANSIBLE_REMOTE_TEMP": str(tmp_path / "ansible-remote"),
        }
    )
    return environment


def run_playbook(tmp_path: Path, source: str):
    playbook = tmp_path / "playbook.yml"
    playbook.write_text(source)
    return subprocess.run(
        [str(Path(sys.executable).with_name("ansible-playbook")), "-i", "manager,dispatch,", str(playbook)],
        cwd=REPO_ROOT,
        env=ansible_environment(tmp_path),
        check=False,
        capture_output=True,
        text=True,
    )


def test_live_lookup_loop_accumulates_all_values_on_dispatch_host_and_resets_next_service(tmp_path):
    result = run_playbook(
        tmp_path,
        f"""---
- name: Exercise dispatch-owned Infisical accumulation
  hosts: all
  connection: local
  gather_facts: false
  strategy: linear
  vars:
    service_catalog_controller_host: manager
    infisical_lookup_default_params: {{}}
  tasks:
    - name: Seed stale manager facts
      when: inventory_hostname == "manager"
      no_log: true
      ansible.builtin.set_fact:
        service_common_infisical_values:
          manager_stale: manager-stale-value
        service_catalog_common_context:
          service_name: manager-stale
          dispatch_host: manager

    - name: Publish first synthetic service
      when: inventory_hostname == "dispatch"
      no_log: true
      ansible.builtin.set_fact:
        service_catalog_dispatch_entry:
          name: accumulation
          runtime: docker
          dispatch_host: dispatch
        service_catalog_materialized_service:
          name: accumulation
          runtime: docker
          dispatch_host: dispatch
          config:
            environment: {{}}
            infisical:
              fail_on_empty: true
              secrets_map:
                - var: alpha
                  path: /Synthetic
                  name: ALPHA
                - var: bravo
                  path: /Synthetic
                  name: BRAVO
                - var: charlie
                  path: /Synthetic
                  name: CHARLIE

    - name: Run first non-mutating preflight
      when: inventory_hostname == "dispatch"
      ansible.builtin.include_tasks: {PREFLIGHT_PATH}

    - name: Snapshot first service results for isolation assertions
      when: inventory_hostname == "dispatch"
      no_log: true
      diff: false
      ansible.builtin.set_fact:
        synthetic_first_service_context: "{{{{ service_catalog_common_context }}}}"

    - name: Publish following empty service
      when: inventory_hostname == "dispatch"
      no_log: true
      ansible.builtin.set_fact:
        service_catalog_dispatch_entry:
          name: following
          runtime: podman
          dispatch_host: dispatch
        service_catalog_materialized_service:
          name: following
          runtime: podman
          dispatch_host: dispatch
          config:
            environment: {{}}
            infisical:
              fail_on_empty: true
              secrets_map: []

    - name: Run following non-mutating preflight
      when: inventory_hostname == "dispatch"
      ansible.builtin.include_tasks: {PREFLIGHT_PATH}

    - name: Verify dispatch ownership, accumulation and next-service reset
      when: inventory_hostname == "manager"
      no_log: true
      ansible.builtin.assert:
        that:
          - hostvars.dispatch.synthetic_first_service_context.lookup_values | length == 3
          - hostvars.dispatch.synthetic_first_service_context.lookup_values.alpha == "{SYNTHETIC_VALUES["ALPHA"]}"
          - hostvars.dispatch.synthetic_first_service_context.lookup_values.bravo == "{SYNTHETIC_VALUES["BRAVO"]}"
          - hostvars.dispatch.synthetic_first_service_context.lookup_values.charlie == "{SYNTHETIC_VALUES["CHARLIE"]}"
          - hostvars.dispatch.synthetic_first_service_context.lookup_values.keys() | list | sort == ['alpha', 'bravo', 'charlie']
          - hostvars.dispatch.service_common_infisical_values == {{}}
          - hostvars.dispatch.service_catalog_common_context.service_name == 'following'
          - hostvars.dispatch.service_catalog_common_context.runtime == 'podman'
          - hostvars.dispatch.service_catalog_common_context.lookup_values == {{}}
          - hostvars.dispatch.service_catalog_common_context.resolved_environment == {{}}
          - hostvars.manager.service_common_infisical_values | length == 1
          - hostvars.manager.service_common_infisical_values.manager_stale == 'manager-stale-value'
          - hostvars.manager.service_catalog_common_context.service_name == 'manager-stale'
""",
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "dispatch -> manager" in output
    for value in SYNTHETIC_VALUES.values():
        if value:
            assert value not in output


def test_failed_infisical_preflight_stops_before_destructive_cleanup(tmp_path):
    result = run_playbook(
        tmp_path,
        f"""---
- name: Exercise recreate preflight failure ordering
  hosts: all
  connection: local
  gather_facts: false
  strategy: linear
  vars:
    service_catalog_controller_host: manager
    infisical_lookup_default_params: {{}}
  tasks:
    - name: Publish failing synthetic service
      when: inventory_hostname == "dispatch"
      no_log: true
      ansible.builtin.set_fact:
        service_catalog_dispatch_entry:
          name: failing
          runtime: docker
          dispatch_host: dispatch
        service_catalog_materialized_service:
          name: failing
          runtime: docker
          dispatch_host: dispatch
          config:
            cleanup:
              enable: true
              force: true
            environment: {{}}
            infisical:
              fail_on_empty: true
              secrets_map:
                - var: required_value
                  path: /Synthetic
                  name: EMPTY

    - name: Run required common preflight before Docker routing
      when: inventory_hostname == "dispatch"
      ansible.builtin.include_tasks: {PREFLIGHT_PATH}

    - name: Synthetic destructive cleanup must never run
      when: inventory_hostname == "dispatch"
      ansible.builtin.fail:
        msg: destructive cleanup marker ran
""",
    )
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "Service common Infisical | Fetch requested values" in output
    assert "Service common Infisical | Enforce empty-value policy" in output
    assert "destructive cleanup marker ran" not in output
