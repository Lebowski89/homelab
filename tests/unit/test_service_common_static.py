import os
import subprocess
import sys
from pathlib import Path

import yaml

ROLE = Path("ansible/roles/service_common")
OPERATIONAL_FILES = [
    *ROLE.joinpath("defaults").rglob("*.yml"),
    *ROLE.joinpath("tasks").rglob("*.yml"),
    *ROLE.joinpath("filter_plugins").rglob("*.py"),
    ROLE / "templates/traefik/dynamic.yml.j2",
]
OPERATIONAL_TEXT = "\n".join(path.read_text() for path in OPERATIONAL_FILES)
TRAEFIK_TASKS = (ROLE / "tasks/traefik.yml").read_text()
REMOVE_TASKS = (ROLE / "tasks/remove_integrations.yml").read_text()
PLAYBOOK = Path("ansible/playbook.yml").read_text()
GLOBAL_DISPATCH = Path("ansible/tasks/service_catalog_dispatch.yml").read_text()
DOCKER_PREP = Path("ansible/roles/docker_services/tasks/_prep.yml").read_text()
PODMAN_MAIN = Path("ansible/roles/podman_services/tasks/main.yml").read_text()
PODMAN_PREP = Path("ansible/roles/podman_services/tasks/sub_tasks/prepare.yml").read_text()
PODMAN_DISPATCH = Path("ansible/tasks/service_catalog_dispatch_podman.yml").read_text()
DOCKER_SECRET_TASKS = Path("ansible/roles/docker_services/tasks/sub_tasks/prep/infisical/_secrets.yml").read_text()
DOCKER_PREP_TASKS = Path("ansible/roles/docker_services/tasks/_prep.yml").read_text()
DOCKER_COMPOSE_TASKS = Path("ansible/roles/docker_services/tasks/_compose.yml").read_text()
DOCKER_FETCH_TASKS = Path("ansible/roles/docker_services/tasks/sub_tasks/prep/infisical/_fetch.yml").read_text()
DOCKER_RESOLVER_TASKS = Path("ansible/roles/docker_services/tasks/sub_tasks/prep/infisical/_resolver.yml").read_text()
DOCKER_INFISICAL_TASKER = Path("ansible/roles/docker_services/tasks/sub_tasks/prep/infisical/tasker.yml").read_text()
COMMON_PATH_TASKS = (ROLE / "tasks/paths.yml").read_text()
COMMON_COPY_TASKS = (ROLE / "tasks/copies.yml").read_text()
COMMON_TEMPLATE_TASKS = (ROLE / "tasks/templates.yml").read_text()
COMMON_POSTGRES_TASKS = (ROLE / "tasks/postgres.yml").read_text()
COMMON_INFISICAL_TASKS = (ROLE / "tasks/infisical.yml").read_text()
DOCKER_MAIN_TASKS = Path("ansible/roles/docker_services/tasks/main.yml").read_text()
DOCKER_DEPLOY_ALL_TASKS = Path("ansible/roles/docker_services/tasks/sub_tasks/deploy/all.yml").read_text()
DOCKER_DEPLOY_TASKS = Path("ansible/roles/docker_services/tasks/_deploy.yml").read_text()
DOCKER_DRIFT_TASKS = Path("ansible/roles/docker_services/tasks/sub_tasks/drift/image.yml").read_text()
DOCKER_ENV_FILE_TASKS = Path("ansible/roles/docker_services/tasks/sub_tasks/compose/env_file.yml").read_text()
AUTOBRR = Path("ansible/group_vars/all/services/autobrr.yml").read_text()


def test_expected_common_dynamic_includes_propagate_required_tags():
    required_tags = {
        ("main.yml", "validate.yml"): {
            "deploy",
            "update",
            "remove",
            "recreate",
            "bootstrap",
            "drift",
        },
        ("main.yml", "prepare.yml"): {
            "deploy",
            "update",
            "recreate",
            "bootstrap",
        },
        ("main.yml", "traefik.yml"): {
            "deploy",
            "update",
            "recreate",
            "bootstrap",
        },
        ("main.yml", "remove_integrations.yml"): {"remove"},
        ("prepare.yml", "validate.yml"): {
            "deploy",
            "update",
            "recreate",
            "bootstrap",
        },
        ("prepare.yml", "postgres.yml"): {
            "deploy",
            "update",
            "recreate",
            "bootstrap",
        },
        ("prepare.yml", "paths.yml"): {
            "deploy",
            "update",
            "recreate",
            "bootstrap",
        },
        ("prepare.yml", "copies.yml"): {
            "deploy",
            "update",
            "recreate",
            "bootstrap",
        },
        ("prepare.yml", "templates.yml"): {
            "deploy",
            "update",
            "recreate",
            "bootstrap",
        },
        ("traefik.yml", "validate.yml"): {
            "deploy",
            "update",
            "recreate",
            "bootstrap",
        },
        ("remove_integrations.yml", "validate.yml"): {"remove"},
    }
    checked = set()

    for path in ROLE.joinpath("tasks").glob("*.yml"):
        tasks = yaml.safe_load(path.read_text()) or []

        for task in tasks:
            if not isinstance(task, dict):
                continue

            include = task.get("ansible.builtin.include_tasks")
            if include is None:
                continue

            include_file = include.get("file") if isinstance(include, dict) else include
            key = (path.name, include_file)

            if key not in required_tags:
                continue

            assert isinstance(include, dict), f"{path}: {include_file} must use mapping syntax to support apply.tags"

            outer_tags = set(task.get("tags", []))
            applied_tags = set(include.get("apply", {}).get("tags", []))
            required = required_tags[key]

            assert required.issubset(outer_tags), (
                f"{path}: {include_file} is missing required selection tags: {sorted(required - outer_tags)}"
            )
            assert required.issubset(applied_tags), (
                f"{path}: {include_file} is missing required apply.tags: {sorted(required - applied_tags)}"
            )

            checked.add(key)

    assert checked == set(required_tags)


def test_common_operational_code_has_no_runtime_role_variables_or_resources():
    assert "docker_services_" not in OPERATIONAL_TEXT
    assert "podman_services_" not in OPERATIONAL_TEXT
    assert "community.docker" not in OPERATIONAL_TEXT
    assert "containers.podman" not in OPERATIONAL_TEXT
    assert "compose.yml" not in OPERATIONAL_TEXT
    assert "quadlet" not in OPERATIONAL_TEXT.lower()


def test_docker_uses_normalized_service_and_effective_filesystem_hosts():
    assert 'service_common_service: "{{ docker_services_svc }}"' in DOCKER_PREP
    assert 'service_common_target_hosts: "{{ docker_services_fs_hosts_effective }}"' in DOCKER_PREP
    prepare = next(
        task for task in yaml.safe_load(DOCKER_PREP) if task["name"] == "Prep - Service common | Prepare files and Traefik integration"
    )
    assert "when" not in prepare


def test_common_filesystem_and_integration_work_has_explicit_delegation():
    for task_file in (COMMON_PATH_TASKS, COMMON_COPY_TASKS, COMMON_TEMPLATE_TASKS):
        tasks = yaml.safe_load(task_file)
        mutating_tasks = [
            task
            for task in tasks
            if any(
                module in task
                for module in (
                    "ansible.builtin.file",
                    "ansible.builtin.copy",
                    "ansible.builtin.template",
                    "ansible.builtin.wait_for",
                )
            )
        ]
        assert mutating_tasks
        assert all(task.get("delegate_to") == "{{ service_common_target_host }}" for task in mutating_tasks)

    traefik_tasks = yaml.safe_load(TRAEFIK_TASKS)
    traefik_mutations = [task for task in traefik_tasks if "ansible.builtin.template" in task or "ansible.builtin.file" in task]
    postgres_tasks = yaml.safe_load(COMMON_POSTGRES_TASKS)
    postgres_mutations = [task for task in postgres_tasks if "community.postgresql.postgresql_db" in task]
    remove_tasks = yaml.safe_load(REMOVE_TASKS)
    remove_mutations = [task for task in remove_tasks if "ansible.builtin.file" in task]
    assert traefik_mutations and postgres_mutations and remove_mutations
    assert all(task.get("delegate_to") == "{{ service_common_controller_host }}" for task in traefik_mutations)
    assert all(task.get("delegate_to") == "{{ service_common_controller_host }}" for task in postgres_mutations)
    assert all(task.get("delegate_to") == "{{ service_common_controller_host }}" for task in remove_mutations)


def test_podman_translates_host_paths_and_keeps_quadlets_runtime_owned():
    assert '{"paths": podman_services_service.host_paths}' in PODMAN_MAIN
    assert "Ensure host data paths exist" not in PODMAN_PREP
    assert "Render container Quadlet" in PODMAN_PREP


def test_legacy_traefik_file_is_removed_only_after_canonical_render():
    render_position = TRAEFIK_TASKS.index("Render canonical dynamic configuration")
    legacy_remove_position = TRAEFIK_TASKS.index("Remove distinct legacy Podman configuration after render")
    assert render_position < legacy_remove_position
    assert "service_common_traefik_canonical_render is succeeded" in TRAEFIK_TASKS
    assert 'service_common_runtime == "podman"' in TRAEFIK_TASKS
    assert "service_common_traefik_legacy_path != service_common_traefik_canonical_path" in TRAEFIK_TASKS


def test_remove_deletes_canonical_and_legacy_paths_idempotently():
    assert "{{ service_common_name }}-dynamic.yml" in REMOVE_TASKS
    assert "{{ service_common_name }}.yml" in REMOVE_TASKS
    assert "state: absent" in REMOVE_TASKS
    assert "| unique | list" in REMOVE_TASKS


def test_docker_batch_deployment_remains_after_service_loops():
    global_loop = PLAYBOOK.index("Process globally ordered service catalog")
    batch_deploy = PLAYBOOK.index("Deploy all Docker stacks")
    assert global_loop < batch_deploy


def test_secret_materialization_and_compatibility_paths_remain_adapter_owned():
    assert "Reject empty secret values before materialization" in DOCKER_SECRET_TASKS
    assert "runtime secret creation was stopped" in DOCKER_SECRET_TASKS
    assert "Create Docker Swarm secrets\n  no_log: true\n  diff: false" in DOCKER_SECRET_TASKS
    assert "Write secret files on deploy host\n  no_log: true\n  diff: false" in DOCKER_SECRET_TASKS
    assert "community.docker.docker_secret" in DOCKER_SECRET_TASKS
    assert 'path: "/opt/stacks/{{ docker_services_stack_name }}/secrets"' in DOCKER_SECRET_TASKS
    assert "default('0600')" in DOCKER_SECRET_TASKS
    assert "service_common_infisical_values[infisical_secret_item.var]" in DOCKER_FETCH_TASKS
    assert '"{{ infisical_secret_item.var }}":' in DOCKER_FETCH_TASKS
    assert "Propagate Infisical flattened vars to deploy host\n  no_log: true\n  diff: false" in DOCKER_INFISICAL_TASKER
    assert "Propagate Infisical dict to deploy host\n  no_log: true\n  diff: false" in DOCKER_INFISICAL_TASKER


def test_common_infisical_tasks_reset_validate_resolve_and_hide_all_values():
    tasks = yaml.safe_load(COMMON_INFISICAL_TASKS)
    reset = next(task for task in tasks if "Reset all per-service outputs" in task["name"])
    normalize_declarations = next(task for task in tasks if "Validate and normalize declarations" in task["name"])
    normalize_environment = next(task for task in tasks if "Validate and normalize canonical environment" in task["name"])
    validate_params = next(task for task in tasks if "Validate lookup parameters" in task["name"])
    fetch = next(task for task in tasks if "Fetch requested values" in task["name"])
    lookup_request = next(task for task in tasks if "Publish current-service lookup request" in task["name"])
    finalize = next(task for task in tasks if "Enforce empty-value policy" in task["name"])
    check_values = next(task for task in tasks if "Build deterministic check-mode values" in task["name"])
    compatibility = next(task for task in tasks if "temporary values compatibility alias" in task["name"])
    resolve = next(task for task in tasks if "Resolve canonical environment" in task["name"])

    reset_facts = reset["ansible.builtin.set_fact"]
    assert reset_facts["service_common_infisical_config"] == {}
    assert reset_facts["service_common_infisical_lookup_request"] == {}
    assert reset_facts["service_common_infisical_values"] == {}
    assert reset_facts["service_common_secret_values"] == {}
    assert reset_facts["service_common_secret_declarations"] == []
    assert reset_facts["service_common_resolved_environment"] == {}
    assert tasks.index(reset) < tasks.index(normalize_declarations) < tasks.index(normalize_environment)
    assert tasks.index(normalize_environment) < tasks.index(fetch) < tasks.index(finalize) < tasks.index(resolve)
    assert fetch["when"] == [
        "not ansible_check_mode",
        "service_common_infisical_config.secrets_map | length > 0",
    ]
    assert lookup_request["when"] == [
        "not ansible_check_mode",
        "service_common_infisical_config.secrets_map | length > 0",
    ]
    assert lookup_request["ansible.builtin.set_fact"]["service_common_infisical_lookup_request"] == {
        "controller_host": "{{ service_common_controller_host | default(inventory_hostname, true) }}",
        "params": "{{ service_common_infisical_lookup_params }}",
        "secrets_map": "{{ service_common_infisical_config.secrets_map }}",
    }
    assert "hostvars[inventory_hostname].service_common_infisical_lookup_request.controller_host" in fetch["delegate_to"]
    assert "default(inventory_hostname, true)" in fetch["delegate_to"]
    assert "delegate_facts" not in fetch
    assert all("delegate_to" not in task for task in tasks if task is not fetch)
    assert finalize["when"] == "not ansible_check_mode"
    assert check_values["when"] == "ansible_check_mode"
    assert "service_common_infisical_values" in str(compatibility["ansible.builtin.set_fact"])
    fetch_expression = str(fetch["ansible.builtin.set_fact"]["service_common_infisical_values"])
    assert "check_mode_value" not in fetch_expression
    assert "service_common_infisical_item.path" in fetch_expression
    assert "service_common_infisical_item.name" in fetch_expression
    assert "hostvars[inventory_hostname].service_common_infisical_values" in fetch_expression
    assert "hostvars[inventory_hostname].service_common_infisical_lookup_request.params" in fetch_expression
    assert "hostvars[inventory_hostname].service_common_infisical_lookup_request.secrets_map" in fetch["loop"]
    assert "default([])" in fetch["loop"]
    assert "infisical.vault.read_secrets" in COMMON_INFISICAL_TASKS
    assert "infisical.vault.read_secrets" not in DOCKER_FETCH_TASKS
    assert "infisical.vault.read_secrets" not in PODMAN_PREP

    for task in tasks:
        assert task["no_log"] is True
        assert task["diff"] is False

    assert validate_params["no_log"] is True


def test_docker_compatibility_facts_are_not_recreated_in_check_mode():
    tasks = yaml.safe_load(DOCKER_FETCH_TASKS)
    compatibility_tasks = [
        task
        for task in tasks
        if task["name"]
        in {
            "Prep - Infisical Fetch | Recreate flattened compatibility facts",
            "Prep - Infisical Fetch | Recreate dictionary compatibility fact",
        }
    ]

    assert len(compatibility_tasks) == 2

    for task in compatibility_tasks:
        assert "not ansible_check_mode" in task["when"]


def test_empty_infisical_map_skips_live_lookup_and_keeps_empty_dispatch_owned_outputs(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    ansible_playbook = Path(sys.executable).with_name("ansible-playbook")
    tasker = repo_root / "ansible/roles/docker_services/tasks/sub_tasks/prep/infisical/tasker.yml"
    playbook = tmp_path / "empty-infisical-map.yml"
    playbook.write_text(
        """---
- name: Exercise empty Docker Infisical declarations without check mode
  hosts: all
  strategy: linear
  connection: local
  gather_facts: false
  vars:
    docker_services_primary_manager: manager
    docker_services_deploy_host_effective: dispatch
    docker_services_stack_deploy_type: container
    docker_services_is_deploy_host: true
    infisical_lookup_default_params: must-not-be-used
    infisical_flatten: true
  tasks:
    - name: Seed deliberately stale manager outputs
      when: inventory_hostname == "manager"
      ansible.builtin.set_fact:
        service_common_infisical_values:
          manager_stale: manager-stale-value
        service_common_secret_values:
          manager_stale: manager-stale-value
        service_common_secret_declarations:
          - name: manager_stale_secret
        service_common_resolved_environment:
          OWNER: manager-stale
        docker_services_infisical_values:
          manager_stale: manager-docker-stale-value
        docker_services_secret_declarations:
          - name: manager_docker_stale_secret
        docker_services_resolved_environment:
          OWNER: manager-docker-stale

    - name: Publish synthetic empty-map service on dispatch host
      when: inventory_hostname == "dispatch"
      ansible.builtin.set_fact:
        docker_services_svc:
          name: empty-map
          runtime: docker
          environment:
            OWNER: dispatch-owned
          infisical:
            fail_on_empty: true
            secrets_map: []

    - name: Resolve empty map through the Docker Infisical tasker
      when: inventory_hostname == "dispatch"
      ansible.builtin.include_tasks:
        file: __DOCKER_INFISICAL_TASKER__

    - name: Verify empty outputs remain dispatch-owned
      when: inventory_hostname == "manager"
      ansible.builtin.assert:
        that:
          - hostvars.dispatch.service_common_infisical_config.secrets_map == []
          - hostvars.dispatch.service_common_infisical_lookup_request == {}
          - hostvars.dispatch.service_common_infisical_values == {}
          - hostvars.dispatch.service_common_secret_values == {}
          - hostvars.dispatch.service_common_secret_declarations == []
          - 'hostvars.dispatch.service_common_resolved_environment == {"OWNER": "dispatch-owned"}'
          - hostvars.dispatch.docker_services_infisical_values == {}
          - hostvars.dispatch.docker_services_secret_declarations == []
          - 'hostvars.dispatch.docker_services_resolved_environment == {"OWNER": "dispatch-owned"}'
          - 'hostvars.dispatch.docker_services_svc.environment == {"OWNER": "dispatch-owned"}'
          - hostvars.manager.service_common_infisical_values.manager_stale == "manager-stale-value"
          - hostvars.manager.service_common_resolved_environment.OWNER == "manager-stale"
          - hostvars.manager.docker_services_infisical_values.manager_stale == "manager-docker-stale-value"
          - hostvars.manager.docker_services_resolved_environment.OWNER == "manager-docker-stale"
""".replace("__DOCKER_INFISICAL_TASKER__", str(tasker))
    )
    environment = os.environ.copy()
    environment.update(
        {
            "ANSIBLE_CONFIG": str(repo_root / "ansible/ansible.cfg"),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible-local"),
        }
    )

    result = subprocess.run(
        [str(ansible_playbook), "-i", "manager,dispatch,", str(playbook)],
        cwd=repo_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    fetch_start = output.index("TASK [service_common : Service common Infisical | Fetch requested values]")
    fetch_end = output.index("\nTASK [", fetch_start + 1)
    assert "skipping: [dispatch]" in output[fetch_start:fetch_end]
    assert "undefined" not in output.lower()


def test_check_mode_validates_infisical_declarations_without_lookup_or_materialization():
    assert "Prep - Infisical | Include tasker\n  ansible.builtin.include_tasks:" in DOCKER_PREP_TASKS
    tasker = yaml.safe_load(DOCKER_INFISICAL_TASKER)
    include_fetch = next(task for task in tasker if task["name"] == "Prep - Infisical Fetch | Include tasks")
    assert "when" not in include_fetch
    fetch = yaml.safe_load(DOCKER_FETCH_TASKS)[0]
    assert "delegate_to" not in fetch
    assert "delegate_to" not in fetch["ansible.builtin.include_role"]["apply"]
    assert fetch["vars"]["service_common_controller_host"] == "{{ docker_services_primary_manager }}"
    assert (
        "hostvars[docker_services_primary_manager].infisical_lookup_default_params"
        in fetch["vars"]["service_common_infisical_lookup_params"]
    )
    assert "Prep - Infisical Resolver | Include tasks on deploy host\n  when:\n    - not ansible_check_mode" in DOCKER_INFISICAL_TASKER
    assert "Prep - Infisical Secrets | Include tasks\n  when:\n    - not ansible_check_mode" in DOCKER_INFISICAL_TASKER
    assert "Resolve common Infisical values and environment" in PODMAN_MAIN
    assert "when: podman_services_common_action in" in PODMAN_MAIN
    assert "Validate and retrieve Infisical values through service common" not in PODMAN_PREP
    assert "ansible_check_mode and service_common_template_item.no_log" in COMMON_TEMPLATE_TASKS


def test_docker_validates_attachment_metadata_before_materialization():
    validate = DOCKER_SECRET_TASKS.index("Validate runtime attachment metadata before materialization")
    reject_empty = DOCKER_SECRET_TASKS.index("Reject empty secret values before materialization")
    create_swarm = DOCKER_SECRET_TASKS.index("Create Docker Swarm secrets")
    write_file = DOCKER_SECRET_TASKS.index("Write secret files on deploy host")

    assert validate < reject_empty < create_swarm
    assert validate < write_file


def test_docker_snapshots_service_declarations_before_later_compatibility_lookups():
    snapshot = DOCKER_INFISICAL_TASKER.index("Snapshot common per-service outputs")
    resolver = DOCKER_INFISICAL_TASKER.index("Prep - Infisical Resolver | Include tasks on deploy host")

    assert snapshot < resolver
    assert 'docker_services_infisical_values: "{{ service_common_infisical_values }}"' in DOCKER_INFISICAL_TASKER
    assert 'docker_services_secret_declarations: "{{ service_common_secret_declarations }}"' in DOCKER_INFISICAL_TASKER
    assert 'service_common_infisical_values: "{{ docker_services_infisical_values }}"' in DOCKER_PREP_TASKS
    assert "docker_services_secret_declarations | default([])" in DOCKER_SECRET_TASKS
    assert "docker_services_infisical_values | default({})" in DOCKER_SECRET_TASKS
    assert "docker_services_secret_declarations | default([])" in DOCKER_COMPOSE_TASKS
    assert "hostvars[docker_services_primary_manager].docker_services_secret_declarations" not in DOCKER_SECRET_TASKS
    assert "hostvars[docker_services_primary_manager].docker_services_secret_declarations" not in DOCKER_COMPOSE_TASKS


def test_docker_canonical_no_new_privileges_uses_tagged_append_unique_list_helper():
    tasks = yaml.safe_load(DOCKER_COMPOSE_TASKS)
    task = next(task for task in tasks if task["name"] == "Compose - Runtime | Add canonical no-new-privileges security option")
    include = task["ansible.builtin.include_tasks"]

    assert include["file"] == "sub_tasks/compose/list_field.yml"
    assert set(include["apply"]["tags"]) == {"deploy", "update", "recreate"}
    assert set(task["tags"]) == {"deploy", "update", "recreate"}
    assert task["vars"]["compose_list_field"] == "security_opt"
    assert task["vars"]["compose_list_action"] == "append_unique"
    assert "docker_services_no_new_privileges_security_opts" in str(task["when"])
    assert "docker_services_stack_deploy_type != 'swarm'" in task["when"]


def test_podman_dispatch_is_routed_from_the_single_global_iteration():
    playbook = yaml.safe_load(PLAYBOOK)
    deploy_play = next(play for play in playbook if play.get("name") == "Deploy homelab services")
    dispatch = next(task for task in deploy_play["tasks"] if task.get("name") == "Process globally ordered service catalog")
    dispatcher_tasks = yaml.safe_load(GLOBAL_DISPATCH)
    materialization = next(
        task for task in dispatcher_tasks if task.get("name") == "Service catalog dispatch | Materialize selected entry on dispatch host"
    )
    podman_route = next(task for task in dispatcher_tasks if task.get("name") == "Service catalog dispatch | Process Podman entry")
    dispatch_tasks = yaml.safe_load(PODMAN_DISPATCH)
    podman_role = next(task for task in dispatch_tasks if task.get("name") == "Service catalog dispatch | Include Podman service role")

    assert dispatch["loop"] == "{{ service_catalog_selected }}"
    assert "when" not in dispatch
    assert materialization["when"] == "inventory_hostname == service_catalog_dispatch_entry.dispatch_host"
    assert podman_route["when"] == [
        "inventory_hostname == service_catalog_dispatch_entry.dispatch_host",
        'service_catalog_dispatch_entry.runtime == "podman"',
    ]
    assert "when" not in podman_role


def test_manager_owned_compose_and_drift_state_have_single_ordered_writers():
    compose_tasks = yaml.safe_load(DOCKER_COMPOSE_TASKS)
    compose_init = next(task for task in compose_tasks if task["name"] == "Compose - Init | Ensure docker_services_compose_stacks exists")
    deploy_tasks = yaml.safe_load(DOCKER_DEPLOY_TASKS)
    persist = next(task for task in deploy_tasks if task["name"].startswith("Deploy | Persist compose into"))
    drift_tasks = yaml.safe_load(DOCKER_DRIFT_TASKS)
    drift_append = next(task for task in drift_tasks if task["name"] == "Drift | Add service to drift summary")
    docker_main = yaml.safe_load(DOCKER_MAIN_TASKS)
    drift_include = next(task for task in docker_main if task["name"] == "Drift | Include image drift check")

    for task in (compose_init, persist, drift_append):
        assert task["delegate_to"] == "{{ docker_services_primary_manager }}" or task["delegate_to"] == (
            "{{ docker_services_primary_manager | default('mgt') }}"
        )
        assert task["delegate_facts"] is True

    persist_expression = persist["ansible.builtin.set_fact"]["docker_services_compose_stacks"]
    assert persist_expression.count("hostvars[docker_services_primary_manager].docker_services_compose_stacks") >= 2
    assert "docker_services_stack_name_effective" in persist_expression
    assert "docker_services_compose_services" in persist_expression

    drift_expression = drift_append["ansible.builtin.set_fact"]["docker_services_image_drift"]
    assert "hostvars[docker_services_primary_manager].docker_services_image_drift" in drift_expression
    assert drift_append["run_once"] is True
    assert drift_include["when"] == "docker_services_is_deploy_host | bool"

    global_dispatch = yaml.safe_load(GLOBAL_DISPATCH)
    materialize = next(
        task for task in global_dispatch if task["name"] == "Service catalog dispatch | Materialize selected entry on dispatch host"
    )
    assert materialize["service_catalog_materialize"]["selected"] == ["{{ service_catalog_dispatch_entry }}"]
    assert PLAYBOOK.count('loop: "{{ service_catalog_selected }}"') == 2


def test_no_operational_ansible_file_references_internal_zone():
    operational_files = [path for path in Path("ansible").rglob("*") if path.is_file() and path.suffix in {".yml", ".yaml", ".j2", ".py"}]

    offenders = [str(path) for path in operational_files if "internal_zone" in path.read_text()]
    assert offenders == []


def test_docker_common_resolution_precedes_legacy_adapter_shared_prep_and_compose():
    fetch = DOCKER_INFISICAL_TASKER.index("Prep - Infisical Fetch | Include tasks")
    attach = DOCKER_INFISICAL_TASKER.index("Attach common resolved environment")
    legacy = DOCKER_INFISICAL_TASKER.index("Prep - Infisical Resolver | Include tasks on deploy host")
    native = DOCKER_INFISICAL_TASKER.index("Prep - Infisical Secrets | Include tasks")
    common_prep = DOCKER_PREP_TASKS.index("Prep - Service common | Prepare files and Traefik integration")

    assert fetch < attach < legacy < native
    assert DOCKER_PREP_TASKS.index("Prep - Infisical | Include tasker") < common_prep
    assert "docker_services_resolved_environment" in DOCKER_INFISICAL_TASKER
    assert "service_common_resolved_environment" in DOCKER_INFISICAL_TASKER


def test_docker_legacy_placeholder_and_env_file_compatibility_remain_narrow_and_unchanged():
    assert "__INFISICAL__:autobrr_session" in AUTOBRR
    assert "__INFISICAL__:postgres_user" in AUTOBRR
    assert "__INFISICAL__:postgres_pass" in AUTOBRR
    assert "^__INFISICAL__:.+$" in DOCKER_RESOLVER_TASKS
    assert "^__INFISICAL__:(.+)$" in DOCKER_RESOLVER_TASKS
    assert "value_template" not in DOCKER_RESOLVER_TASKS
    assert "value_from" not in DOCKER_RESOLVER_TASKS
    assert "docker_services_svc.env_file" in DOCKER_ENV_FILE_TASKS
    assert "service_common" not in DOCKER_ENV_FILE_TASKS


def test_value_bearing_runtime_render_paths_are_no_log_and_diff_safe():
    docker_main = yaml.safe_load(DOCKER_MAIN_TASKS)
    for task_name in {"Compose | Include tasks", "Deploy | Include tasks"}:
        task = next(task for task in docker_main if task["name"] == task_name)
        assert task["no_log"] is True
        assert "diff" not in task
        include = task["ansible.builtin.include_tasks"]
        assert include["apply"]["no_log"] is True
        assert include["apply"]["diff"] is False

    podman_main = yaml.safe_load(PODMAN_MAIN)
    resolver = next(task for task in podman_main if "Resolve common Infisical values and environment" in task["name"])
    attach = next(task for task in podman_main if "Attach common resolved environment" in task["name"])
    traefik = next(task for task in podman_main if "Include Traefik tasks" in task["name"])
    assert attach["no_log"] is True
    assert attach["diff"] is False
    for task in (resolver, traefik):
        assert task["no_log"] is True
        assert "diff" not in task
        include = task["ansible.builtin.include_role"]
        assert include["apply"]["no_log"] is True
        assert include["apply"]["diff"] is False


def test_required_docker_dynamic_includes_propagate_selection_tags():
    expectations = [
        (DOCKER_MAIN_TASKS, "Prep | Include tasks", {"deploy", "update", "remove", "recreate", "bootstrap"}),
        (DOCKER_PREP_TASKS, "Prep - Infisical | Include tasker", {"deploy", "update", "recreate", "bootstrap"}),
        (DOCKER_INFISICAL_TASKER, "Prep - Infisical Fetch | Include tasks", {"deploy", "update", "recreate", "bootstrap"}),
        (
            DOCKER_INFISICAL_TASKER,
            "Prep - Infisical Resolver | Include tasks on deploy host",
            {"deploy", "update", "recreate", "bootstrap"},
        ),
        (DOCKER_INFISICAL_TASKER, "Prep - Infisical Secrets | Include tasks", {"deploy", "update", "recreate", "bootstrap"}),
        (DOCKER_DEPLOY_ALL_TASKS, "Deploy - All | Deploy each stack", {"deploy", "update", "recreate"}),
    ]

    for content, task_name, required in expectations:
        task = next(task for task in yaml.safe_load(content) if task["name"] == task_name)
        include = task["ansible.builtin.include_tasks"]
        assert required.issubset(set(task.get("tags", [])))
        assert required.issubset(set(include.get("apply", {}).get("tags", [])))
