import re
from pathlib import Path

import yaml

TASKS_DIR = Path("ansible/roles/podman_services/tasks")
MAIN_TASKS = (TASKS_DIR / "main.yml").read_text()
PREPARE_TASKS = (TASKS_DIR / "sub_tasks" / "prepare.yml").read_text()
SECRET_TASKS = (TASKS_DIR / "sub_tasks" / "secrets" / "materialize.yml").read_text()
REMOVE_TASKS = (TASKS_DIR / "sub_tasks" / "remove.yml").read_text()
NETWORK_TASKS = (TASKS_DIR / "sub_tasks" / "network.yml").read_text()
SUB_TASK_FILES = (
    "init.yml",
    "prepare.yml",
    "image.yml",
    "network.yml",
    "lifecycle.yml",
    "remove.yml",
    "drift.yml",
)
TASKS = "\n".join((TASKS_DIR / "sub_tasks" / name).read_text() for name in SUB_TASK_FILES) + "\n" + SECRET_TASKS
N8N = Path("ansible/group_vars/all/services/n8n.yml").read_text()
NETWORK_TEMPLATE = Path("ansible/roles/podman_services/templates/network.network.j2").read_text()
PODMAN_DEFAULTS = Path("ansible/roles/podman/defaults/main.yml").read_text()
PODMAN_TASKS = Path("ansible/roles/podman/tasks/main.yml").read_text()
PODMAN_HANDLERS = Path("ansible/roles/podman_services/handlers/main.yml").read_text()


def test_main_orchestrates_sub_tasks_in_order():
    positions = [MAIN_TASKS.index(f"sub_tasks/{name}") for name in SUB_TASK_FILES]
    assert positions == sorted(positions)
    assert "Podman services | Normalize service" not in MAIN_TASKS
    assert "Podman services | Flush removal daemon-reload handlers" in MAIN_TASKS


def test_quadlet_directory_prerequisite_exists_before_templates():
    dir_pos = TASKS.index("Prep | Ensure system Quadlet directory exists")
    first_template_pos = TASKS.index("ansible.builtin.template")
    assert dir_pos < first_template_pos
    assert 'path: "{{ podman_services_quadlet_dir }}"' in TASKS
    assert 'mode: "0755"' in TASKS


def test_n8n_declares_a_managed_network_without_delete_on_stop():
    n8n = yaml.safe_load(N8N)["n8n"]

    assert n8n["named_networks"] == {"n8n": {"driver": "bridge", "external": False}}
    assert "delete_on_stop" not in N8N
    assert "NetworkDeleteOnStop" not in NETWORK_TEMPLATE


def test_remove_stops_container_before_network_then_removes_files():
    container_stop = TASKS.index("Stop service for removal without deleting data")
    network_stop = TASKS.index("Stop managed network unit for removal")
    exists = TASKS.index("Check managed network still exists for removal")
    remove_network = TASKS.index("Remove managed network if still present")
    remove_files = TASKS.index("Remove generated Quadlet and environment files only")
    assert container_stop < network_stop < exists < remove_network < remove_files


def test_remove_only_orchestration_is_guarded_by_normalized_action():
    tasks = yaml.safe_load(MAIN_TASKS)
    remove_only_tasks = {
        "Podman services | Include removal tasks",
        "Podman services | Remove runtime-neutral integrations",
        "Podman services | Flush removal daemon-reload handlers",
    }

    guarded = set()
    for task in tasks:
        if task["name"] not in remove_only_tasks:
            continue
        guarded.add(task["name"])
        conditions = task.get("when", [])
        if isinstance(conditions, str):
            conditions = [conditions]
        assert "podman_services_common_action == 'remove'" in conditions

    assert guarded == remove_only_tasks


def test_external_network_is_not_created_or_removed():
    prepare = next(task for task in yaml.safe_load(PREPARE_TASKS) if task["name"] == "Prep | Render network Quadlet")
    remove_tasks = yaml.safe_load(REMOVE_TASKS)
    managed_network_tasks = [
        task
        for task in remove_tasks
        if task["name"]
        in {
            "Remove | Stop managed network unit for removal",
            "Remove | Check managed network still exists for removal",
            "Remove | Remove managed network if still present",
        }
    ]

    assert "not podman_services_service.network.external | bool" in prepare["when"]
    assert len(managed_network_tasks) == 3
    for task in managed_network_tasks:
        assert "not podman_services_service.network.external | bool" in task["when"]


def test_changed_managed_network_is_retained_during_update_and_recreate():
    tasks = yaml.safe_load(NETWORK_TASKS)

    assert [task["name"] for task in tasks] == ["Network | Report retained managed network definition change"]
    assert tasks[0]["changed_when"] is False
    assert "podman network" not in NETWORK_TASKS
    assert "ansible.builtin.systemd_service" not in NETWORK_TASKS


def test_managed_network_quadlet_is_rendered_before_container_quadlet():
    assert PREPARE_TASKS.index("Prep | Render network Quadlet") < PREPARE_TASKS.index("Prep | Render container Quadlet")


def test_no_late_shared_network_migration_fail_after_template_render():
    assert "Refuse implicit shared network migration" not in TASKS
    assert "Coordinate shared network migration" not in TASKS


def test_network_validation_occurs_before_template_rendering():
    normalize = TASKS.index("Init | Normalize service")
    network_template = TASKS.index("Prep | Render network Quadlet")
    assert normalize < network_template


def test_managed_network_remove_failure_is_not_suppressed():
    task = next(task for task in yaml.safe_load(REMOVE_TASKS) if task["name"] == "Remove | Remove managed network if still present")

    assert "failed_when" not in task
    assert "not ansible_check_mode" in task["when"]


def test_secret_skip_existing_semantics_are_explicit():
    assert "skip_existing:" in TASKS
    assert "podman_secret_policy(podman_services_state)" in TASKS


def test_podman_consumes_canonical_dispatch_context_without_owning_lookup():
    assert "podman_services_common_context" in (TASKS_DIR / "sub_tasks" / "init.yml").read_text()
    assert "podman_services_common_values" in (TASKS_DIR / "sub_tasks" / "init.yml").read_text()
    assert "tasks_from: infisical" not in MAIN_TASKS
    assert "infisical.vault.read_secrets" not in TASKS
    assert 'name: "{{ podman_services_secret.name }}"' in TASKS
    assert 'data: "{{ podman_services_effective_secret_values[podman_services_secret.var] }}"' in TASKS
    assert "podman_secret_policy(podman_services_state)).force" in TASKS
    assert "podman_secret_policy(podman_services_state)).skip_existing" in TASKS
    assert "not ansible_check_mode" in TASKS


def test_absent_container_unit_is_checked_before_stop():
    load_state = TASKS.index("Check container unit load state for removal")
    stop = TASKS.index("Stop service for removal without deleting data")
    assert load_state < stop
    assert "--property=LoadState" in TASKS
    assert "stdout | trim != 'not-found'" in TASKS


def test_absent_container_unit_is_checked_before_recreate_preparation_stop():
    tasks = yaml.safe_load(MAIN_TASKS)
    load_state = next(task for task in tasks if task["name"] == "Podman services | Check deployed service unit before recreate preparation")
    stop = next(task for task in tasks if task["name"] == "Podman services | Stop deployed service before recreate preparation")

    assert tasks.index(load_state) < tasks.index(stop)
    assert load_state["ansible.builtin.command"]["argv"] == [
        "systemctl",
        "show",
        "{{ podman_services_unit_name }}",
        "--property=LoadState",
        "--value",
    ]
    assert load_state["changed_when"] is False
    assert load_state["failed_when"] is False
    assert "podman_services_recreate_unit_load_state.stdout | trim != 'not-found'" in stop["when"]


def test_podman_role_targets_ubuntu_2604_resolute_and_podman_57():
    assert 'podman_min_version: "5.7.0"' in PODMAN_DEFAULTS
    assert "distribution_version is version('26.04', '>=')" in PODMAN_TASKS
    assert "Ubuntu 26.04 LTS (Resolute)" in PODMAN_TASKS


def test_split_tasks_notify_the_existing_daemon_reload_handler():
    handler_name = "Podman services | daemon reload"
    assert f"- name: {handler_name}" in PODMAN_HANDLERS
    assert TASKS.count(f"notify: {handler_name}") == 5
    assert "notify: Prep | daemon reload" not in TASKS
    assert "notify: Remove | daemon reload" not in TASKS


def test_podman_secret_loop_uses_a_role_prefixed_variable_without_item_references():
    tasks = yaml.safe_load(SECRET_TASKS)
    task = next(task for task in tasks if task["name"] == "Prep | Create or update Podman-native secrets")

    assert task["loop_control"]["loop_var"] == "podman_services_secret"
    assert re.search(r"(?<![A-Za-z0-9_])item(?![A-Za-z0-9_])", str(task)) is None


def test_podman_generated_path_loop_uses_a_role_prefixed_variable_without_item_references():
    tasks = yaml.safe_load(REMOVE_TASKS)
    task = next(task for task in tasks if task["name"] == "Remove | Remove generated Quadlet and environment files only")

    assert task["loop_control"]["loop_var"] == "podman_services_generated_path"
    assert re.search(r"(?<![A-Za-z0-9_])item(?![A-Za-z0-9_])", str(task)) is None


def test_podman_render_tasks_publish_the_normalized_service_to_templates():
    tasks = yaml.safe_load(PREPARE_TASKS)
    template_sources = {"network.network.j2", "env.env.j2", "container.container.j2"}
    render_tasks = [
        task
        for task in tasks
        if isinstance(task.get("ansible.builtin.template"), dict) and task["ansible.builtin.template"].get("src") in template_sources
    ]

    assert {task["ansible.builtin.template"]["src"] for task in render_tasks} == template_sources
    for task in render_tasks:
        assert task["vars"]["podman_service"] == "{{ podman_services_service }}"


def test_podman_common_resolution_precedes_shared_and_runtime_rendering():
    init = TASKS.index("Init | Snapshot dispatch-owned common context")
    native_secret = MAIN_TASKS.index("Materialize Podman-native secrets")
    shared = MAIN_TASKS.index("Prepare runtime-neutral host state")
    prepare = MAIN_TASKS.index("Include preparation tasks")
    env_file = TASKS.index("Render protected environment file")
    quadlet = TASKS.index("Render container Quadlet")

    assert init < env_file
    assert native_secret < shared < prepare
    assert env_file < quadlet
    assert "not ansible_check_mode" in MAIN_TASKS[:shared]


def test_podman_dynamic_includes_propagate_required_tags():
    required_tags = {
        "sub_tasks/init.yml": {"deploy", "update", "remove", "recreate", "drift", "bootstrap"},
        "sub_tasks/prepare.yml": {"deploy", "update", "remove", "recreate", "drift", "bootstrap"},
        "sub_tasks/image.yml": {"deploy", "update", "recreate", "bootstrap"},
        "sub_tasks/network.yml": {"update", "recreate"},
        "sub_tasks/lifecycle.yml": {"deploy", "update", "remove", "recreate", "bootstrap"},
        "sub_tasks/remove.yml": {"remove"},
        "sub_tasks/drift.yml": {"drift"},
    }
    checked = set()

    for task in yaml.safe_load(MAIN_TASKS):
        include = task.get("ansible.builtin.include_tasks")
        if not isinstance(include, dict) or include.get("file") not in required_tags:
            continue
        include_file = include["file"]
        required = required_tags[include_file]
        assert required.issubset(set(task.get("tags", [])))
        assert required.issubset(set(include.get("apply", {}).get("tags", [])))
        checked.add(include_file)

    assert checked == set(required_tags)
