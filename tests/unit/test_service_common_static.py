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
DOCKER_FETCH_TASKS = Path("ansible/roles/docker_services/tasks/sub_tasks/prep/infisical/_fetch.yml").read_text()
DOCKER_RESOLVER_TASKS = Path("ansible/roles/docker_services/tasks/sub_tasks/prep/infisical/_resolver.yml").read_text()
DOCKER_INFISICAL_TASKER = Path("ansible/roles/docker_services/tasks/sub_tasks/prep/infisical/tasker.yml").read_text()
COMMON_TEMPLATE_TASKS = (ROLE / "tasks/templates.yml").read_text()
COMMON_INFISICAL_TASKS = (ROLE / "tasks/infisical.yml").read_text()
DOCKER_POSTGRES_TASKS = Path("ansible/roles/docker_services/tasks/sub_tasks/prep/postgres.yml").read_text()


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
    assert "docker_secret" not in OPERATIONAL_TEXT
    assert "podman_secret" not in OPERATIONAL_TEXT
    assert "compose.yml" not in OPERATIONAL_TEXT
    assert "quadlet" not in OPERATIONAL_TEXT.lower()


def test_docker_uses_normalized_service_and_effective_filesystem_hosts():
    assert 'service_common_service: "{{ docker_services_svc }}"' in DOCKER_PREP
    assert 'service_common_target_hosts: "{{ docker_services_fs_hosts_effective }}"' in DOCKER_PREP


def test_podman_translates_host_paths_and_keeps_quadlets_runtime_owned():
    assert "{'paths': podman_services_service.host_paths}" in PODMAN_MAIN
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
    assert 'mode: "0600"' in DOCKER_SECRET_TASKS
    assert "service_common_secret_values[infisical_secret_item.var]" in DOCKER_FETCH_TASKS
    assert '"{{ infisical_secret_item.var }}":' in DOCKER_FETCH_TASKS
    assert "Propagate Infisical flattened vars to deploy host\n  no_log: true\n  diff: false" in DOCKER_INFISICAL_TASKER
    assert "Propagate Infisical dict to deploy host\n  no_log: true\n  diff: false" in DOCKER_INFISICAL_TASKER


def test_common_infisical_tasks_reset_output_guard_lookup_and_hide_values():
    tasks = yaml.safe_load(COMMON_INFISICAL_TASKS)
    reset = next(task for task in tasks if "Reset per-service secret output" in task["name"])
    validate_params = next(task for task in tasks if "Validate lookup parameters" in task["name"])
    fetch = next(task for task in tasks if "Fetch requested secret values" in task["name"])
    finalize = next(task for task in tasks if "Enforce empty-value policy" in task["name"])

    assert reset["ansible.builtin.set_fact"]["service_common_secret_values"] == {}
    assert tasks.index(reset) < tasks.index(fetch) < tasks.index(finalize)
    assert fetch["when"] == "not ansible_check_mode"
    assert finalize["when"] == "not ansible_check_mode"
    assert "infisical.vault.read_secrets" in COMMON_INFISICAL_TASKS
    assert "infisical.vault.read_secrets" not in DOCKER_FETCH_TASKS
    assert "infisical.vault.read_secrets" not in PODMAN_PREP

    for task in (reset, validate_params, fetch, finalize):
        assert task["no_log"] is True
        assert task["diff"] is False


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
    assert "Retrieve Infisical values through service common" in PODMAN_PREP
    assert "when: podman_services_state in" in PODMAN_PREP
    assert "ansible_check_mode and service_common_template_item.no_log" in COMMON_TEMPLATE_TASKS
    assert "Prepare docker secret\n  no_log: true\n  diff: false" in DOCKER_POSTGRES_TASKS
    assert "Create database(s) if missing\n  no_log: true\n  diff: false" in DOCKER_POSTGRES_TASKS
