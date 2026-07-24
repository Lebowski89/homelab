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
DOCKER_PREP = Path("ansible/roles/docker_services/tasks/_prep.yml").read_text()
PODMAN_MAIN = Path("ansible/roles/podman_services/tasks/main.yml").read_text()
PODMAN_PREP = Path("ansible/roles/podman_services/tasks/sub_tasks/prepare.yml").read_text()
DOCKER_SECRET_TASKS = Path("ansible/roles/docker_services/tasks/sub_tasks/prep/infisical/_secrets.yml").read_text()
DOCKER_PREP_TASKS = Path("ansible/roles/docker_services/tasks/_prep.yml").read_text()
DOCKER_COMPOSE_TASKS = Path("ansible/roles/docker_services/tasks/_compose.yml").read_text()
DOCKER_FETCH_TASKS = Path("ansible/roles/docker_services/tasks/sub_tasks/prep/infisical/_fetch.yml").read_text()
DOCKER_RESOLVER_TASKS = Path("ansible/roles/docker_services/tasks/sub_tasks/prep/infisical/_resolver.yml").read_text()
DOCKER_INFISICAL_TASKER = Path("ansible/roles/docker_services/tasks/sub_tasks/prep/infisical/tasker.yml").read_text()
COMMON_TEMPLATE_TASKS = (ROLE / "tasks/templates.yml").read_text()
COMMON_INFISICAL_TASKS = (ROLE / "tasks/infisical.yml").read_text()
DOCKER_POSTGRES_TASKS = Path("ansible/roles/docker_services/tasks/sub_tasks/prep/postgres.yml").read_text()
DOCKER_MAIN_TASKS = Path("ansible/roles/docker_services/tasks/main.yml").read_text()
DOCKER_DEPLOY_ALL_TASKS = Path("ansible/roles/docker_services/tasks/sub_tasks/deploy/all.yml").read_text()
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
    docker_loop = PLAYBOOK.index("Process each Docker service")
    podman_loop = PLAYBOOK.index("Process each Podman service")
    batch_deploy = PLAYBOOK.index("Deploy all Docker stacks")
    assert docker_loop < podman_loop < batch_deploy


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
    finalize = next(task for task in tasks if "Enforce empty-value policy" in task["name"])
    check_values = next(task for task in tasks if "Build deterministic check-mode values" in task["name"])
    compatibility = next(task for task in tasks if "temporary values compatibility alias" in task["name"])
    resolve = next(task for task in tasks if "Resolve canonical environment" in task["name"])

    reset_facts = reset["ansible.builtin.set_fact"]
    assert reset_facts["service_common_infisical_config"] == {}
    assert reset_facts["service_common_infisical_values"] == {}
    assert reset_facts["service_common_secret_values"] == {}
    assert reset_facts["service_common_secret_declarations"] == []
    assert reset_facts["service_common_resolved_environment"] == {}
    assert tasks.index(reset) < tasks.index(normalize_declarations) < tasks.index(normalize_environment)
    assert tasks.index(normalize_environment) < tasks.index(fetch) < tasks.index(finalize) < tasks.index(resolve)
    assert fetch["when"] == "not ansible_check_mode"
    assert finalize["when"] == "not ansible_check_mode"
    assert check_values["when"] == "ansible_check_mode"
    assert "service_common_infisical_values" in str(compatibility["ansible.builtin.set_fact"])
    fetch_expression = str(fetch["ansible.builtin.set_fact"]["service_common_infisical_values"])
    assert "check_mode_value" not in fetch_expression
    assert "service_common_infisical_item.path" in fetch_expression
    assert "service_common_infisical_item.name" in fetch_expression
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


def test_check_mode_validates_infisical_declarations_without_lookup_or_materialization():
    assert "Prep - Infisical | Include tasker\n  ansible.builtin.include_tasks:" in DOCKER_PREP_TASKS
    assert "Prep - Infisical Fetch | Include tasks\n  when: inventory_hostname" in DOCKER_INFISICAL_TASKER
    assert "Prep - Infisical Resolver | Include tasks on deploy host\n  when:\n    - not ansible_check_mode" in DOCKER_INFISICAL_TASKER
    assert "Prep - Infisical Secrets | Include tasks\n  when:\n    - not ansible_check_mode" in DOCKER_INFISICAL_TASKER
    assert "Resolve common Infisical values and environment" in PODMAN_MAIN
    assert "when: podman_services_common_action in" in PODMAN_MAIN
    assert "Validate and retrieve Infisical values through service common" not in PODMAN_PREP
    assert "ansible_check_mode and service_common_template_item.no_log" in COMMON_TEMPLATE_TASKS
    assert "Prepare docker secret\n  no_log: true\n  diff: false" in DOCKER_POSTGRES_TASKS
    assert "Create database(s) if missing\n  no_log: true\n  diff: false" in DOCKER_POSTGRES_TASKS


def test_docker_validates_attachment_metadata_before_materialization():
    validate = DOCKER_SECRET_TASKS.index("Validate runtime attachment metadata before materialization")
    reject_empty = DOCKER_SECRET_TASKS.index("Reject empty secret values before materialization")
    create_swarm = DOCKER_SECRET_TASKS.index("Create Docker Swarm secrets")
    write_file = DOCKER_SECRET_TASKS.index("Write secret files on deploy host")

    assert validate < reject_empty < create_swarm
    assert validate < write_file


def test_docker_snapshots_service_declarations_before_later_compatibility_lookups():
    snapshot = DOCKER_INFISICAL_TASKER.index("Snapshot value-free service secret declarations")
    resolver = DOCKER_INFISICAL_TASKER.index("Prep - Infisical Resolver | Include tasks on deploy host")

    assert snapshot < resolver
    assert 'docker_services_secret_declarations: "{{ service_common_secret_declarations }}"' in DOCKER_INFISICAL_TASKER
    assert "hostvars[docker_services_primary_manager].docker_services_secret_declarations" in DOCKER_SECRET_TASKS
    assert "hostvars[docker_services_primary_manager].docker_services_secret_declarations" in DOCKER_COMPOSE_TASKS


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


def test_podman_host_selection_treats_empty_hosts_as_missing():
    assert "default(item.name, true)" in PLAYBOOK
    assert "| default(item.name, true),\n                true" in PLAYBOOK


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
