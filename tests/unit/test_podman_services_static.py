import re
from pathlib import Path

import yaml

TASKS_DIR = Path("ansible/roles/podman_services/tasks")
MAIN_TASKS = (TASKS_DIR / "main.yml").read_text()
PREPARE_TASKS = (TASKS_DIR / "sub_tasks" / "prepare.yml").read_text()
SECRET_TASKS = (TASKS_DIR / "sub_tasks" / "secrets" / "materialize.yml").read_text()
REMOVE_TASKS = (TASKS_DIR / "sub_tasks" / "remove.yml").read_text()
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


def test_n8n_explicitly_enables_dedicated_network_delete_on_stop():
    assert "delete_on_stop: true" in N8N
    assert "NetworkDeleteOnStop=true" in NETWORK_TEMPLATE
    assert "default(false)" in NETWORK_TEMPLATE


def test_remove_stops_container_before_network_then_removes_files():
    container_stop = TASKS.index("Stop service for removal without deleting data")
    network_stop = TASKS.index("Stop generated network unit for removal")
    exists = TASKS.index("Check dedicated network still exists for removal")
    remove_network = TASKS.index("Remove dedicated network if still present")
    remove_files = TASKS.index("Remove generated Quadlet and environment files only")
    assert container_stop < network_stop < exists < remove_network < remove_files


def test_remove_shared_network_is_not_explicitly_removed():
    check = TASKS.index("Check dedicated network still exists for removal")
    remove = TASKS.index("Remove dedicated network if still present")
    assert "podman_services_service.network.delete_on_stop | default(false) | bool" in TASKS[check:remove]


def test_changed_dedicated_network_lifecycle_checks_and_removes_before_reload_and_start():
    container_stop = TASKS.index("Stop container before changed dedicated network lifecycle")
    network_stop = TASKS.index("Stop generated dedicated network after changed lifecycle")
    exists = TASKS.index("Check changed dedicated network still exists")
    remove = TASKS.index("Remove changed dedicated network if still present")
    reload_pos = TASKS.index("Flush Quadlet daemon-reload handlers before lifecycle")
    start_pos = TASKS.index("Restart service when update inputs changed")
    assert container_stop < network_stop < exists < remove < reload_pos < start_pos
    assert "argv: [podman, network, exists" in TASKS
    assert "argv: [podman, network, rm" in TASKS
    assert "podman_services_changed_network_exists.rc == 0" in TASKS


def test_changed_dedicated_network_absent_is_idempotent():
    exists = TASKS.index("Check changed dedicated network still exists")
    remove = TASKS.index("Remove changed dedicated network if still present")
    assert exists < remove
    assert "failed_when: podman_services_changed_network_exists.rc not in [0, 1]" in TASKS
    assert "changed_when: false" in TASKS[exists:remove]


def test_no_late_shared_network_migration_fail_after_template_render():
    assert "Refuse implicit shared network migration" not in TASKS
    assert "Coordinate shared network migration" not in TASKS


def test_network_validation_occurs_before_template_rendering():
    normalize = TASKS.index("Init | Normalize service")
    network_template = TASKS.index("Prep | Render network Quadlet")
    assert normalize < network_template


def test_false_to_true_delete_on_stop_transition_removes_remaining_network():
    stop = TASKS.index("Stop generated dedicated network after changed lifecycle")
    exists = TASKS.index("Check changed dedicated network still exists")
    remove = TASKS.index("Remove changed dedicated network if still present")
    assert stop < exists < remove
    assert "podman_services_service.network.delete_on_stop | default(false) | bool" in TASKS[stop:remove]


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
