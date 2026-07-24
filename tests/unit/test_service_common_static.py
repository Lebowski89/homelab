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

            assert isinstance(include, dict), (
                f"{path}: {include_file} must use mapping syntax to support apply.tags"
            )

            outer_tags = set(task.get("tags", []))
            applied_tags = set(include.get("apply", {}).get("tags", []))
            required = required_tags[key]

            assert required.issubset(outer_tags), (
                f"{path}: {include_file} is missing required selection tags: "
                f"{sorted(required - outer_tags)}"
            )
            assert required.issubset(applied_tags), (
                f"{path}: {include_file} is missing required apply.tags: "
                f"{sorted(required - applied_tags)}"
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


def test_secret_materialization_rejects_empty_values_and_hides_writes():
    assert "Reject empty secret values before materialization" in DOCKER_SECRET_TASKS
    assert "runtime secret creation was stopped" in DOCKER_SECRET_TASKS
    assert "Create Docker Swarm secrets\n  no_log: true\n  diff: false" in DOCKER_SECRET_TASKS
    assert "Write secret files on deploy host\n  no_log: true\n  diff: false" in DOCKER_SECRET_TASKS
    assert "Reject empty Infisical secret values before Podman materialization" in PODMAN_PREP
    assert "Create/update Podman secrets" in PODMAN_PREP
    assert PODMAN_PREP.count("diff: false") >= 2
    assert DOCKER_FETCH_TASKS.count("no_log: true") >= 4
    assert DOCKER_FETCH_TASKS.count("diff: false") >= 2
    assert DOCKER_RESOLVER_TASKS.count("- name:") == DOCKER_RESOLVER_TASKS.count("no_log: true")
    assert "Propagate Infisical flattened vars to deploy host\n  no_log: true\n  diff: false" in DOCKER_INFISICAL_TASKER
    assert "Propagate Infisical dict to deploy host\n  no_log: true\n  diff: false" in DOCKER_INFISICAL_TASKER


def test_check_mode_does_not_enter_docker_infisical_lookup_or_materialization():
    include = "Prep - Infisical | Include tasker\n  when: not ansible_check_mode"
    assert include in DOCKER_PREP_TASKS
    guarded_prep = [
        "Prep - Authelia | Include bootstrap tasks",
        "Prep - Postgres | Create Postgres database",
        "Prep - qBittorrent | Include bootstrap tasks",
        "Prep - Plex | Include bootstrap tasks",
        "Prep - Bazarr | Include bootstrap tasks",
        "Prep - NZBHydra2 | Include bootstrap tasks",
        "Prep - Vaultwarden | Include bootstrap tasks",
    ]
    for name in guarded_prep:
        assert f"{name}\n  when:\n    - not ansible_check_mode" in DOCKER_PREP_TASKS
    assert "ansible_check_mode and service_common_template_item.no_log" in COMMON_TEMPLATE_TASKS
    assert "Prepare docker secret\n  no_log: true\n  diff: false" in DOCKER_POSTGRES_TASKS
    assert "Create database(s) if missing\n  no_log: true\n  diff: false" in DOCKER_POSTGRES_TASKS
