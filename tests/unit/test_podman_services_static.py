import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
TASKS_DIR = REPO_ROOT / "ansible" / "roles" / "podman_services" / "tasks"
MAIN_TASKS = (TASKS_DIR / "main.yml").read_text()
PREPARE_TASKS = (TASKS_DIR / "sub_tasks" / "prepare.yml").read_text()
SECRET_TASKS = (TASKS_DIR / "sub_tasks" / "secrets" / "materialize.yml").read_text()
REMOVE_TASKS = (TASKS_DIR / "sub_tasks" / "remove.yml").read_text()
NETWORK_TASKS = (TASKS_DIR / "sub_tasks" / "network.yml").read_text()
DRIFT_TASKS = (TASKS_DIR / "sub_tasks" / "drift.yml").read_text()
EXECUTION_PREPARE_TASKS = (TASKS_DIR / "sub_tasks" / "execution_prepare.yml").read_text()
EXECUTION_TRANSITION_TASKS = (TASKS_DIR / "sub_tasks" / "execution_transition.yml").read_text()
LIFECYCLE_TASKS = (TASKS_DIR / "sub_tasks" / "lifecycle.yml").read_text()
SUB_TASK_FILES = (
    "init.yml",
    "execution_prepare.yml",
    "prepare.yml",
    "image.yml",
    "network.yml",
    "lifecycle.yml",
    "remove.yml",
    "drift.yml",
)
TASKS = "\n".join((TASKS_DIR / "sub_tasks" / name).read_text() for name in SUB_TASK_FILES) + "\n" + SECRET_TASKS
N8N = (REPO_ROOT / "ansible/group_vars/all/services/n8n.yml").read_text()
NETWORK_TEMPLATE = (REPO_ROOT / "ansible/roles/podman_services/templates/network.network.j2").read_text()
PODMAN_DEFAULTS = (REPO_ROOT / "ansible/roles/podman/defaults/main.yml").read_text()
PODMAN_TASKS = (REPO_ROOT / "ansible/roles/podman/tasks/main.yml").read_text()
PODMAN_HANDLERS = (REPO_ROOT / "ansible/roles/podman_services/handlers/main.yml").read_text()

MAIN_TASK_LIST = yaml.safe_load(MAIN_TASKS)
PREPARE_TASK_LIST = yaml.safe_load(PREPARE_TASKS)
REMOVE_TASK_LIST = yaml.safe_load(REMOVE_TASKS)
EXECUTION_PREPARE_TASK_LIST = yaml.safe_load(EXECUTION_PREPARE_TASKS)
EXECUTION_TRANSITION_TASK_LIST = yaml.safe_load(EXECUTION_TRANSITION_TASKS)
LIFECYCLE_TASK_LIST = yaml.safe_load(LIFECYCLE_TASKS)
ALL_TASK_LIST = [task for name in SUB_TASK_FILES for task in yaml.safe_load((TASKS_DIR / "sub_tasks" / name).read_text())]
MAIN_TASK_NAMES = [task["name"] for task in MAIN_TASK_LIST]
PREPARE_TASK_NAMES = [task["name"] for task in PREPARE_TASK_LIST]
REMOVE_TASK_NAMES = [task["name"] for task in REMOVE_TASK_LIST]
ALL_TASK_NAMES = [task["name"] for task in ALL_TASK_LIST]
EXECUTION_TRANSITION_TASK_NAMES = [task["name"] for task in EXECUTION_TRANSITION_TASK_LIST]
LIFECYCLE_TASK_NAMES = [task["name"] for task in LIFECYCLE_TASK_LIST]


def test_main_orchestrates_sub_tasks_in_order():
    included_files = [task["ansible.builtin.include_tasks"]["file"] for task in MAIN_TASK_LIST if "ansible.builtin.include_tasks" in task]
    expected = [f"sub_tasks/{name}" for name in SUB_TASK_FILES]
    assert [path for path in included_files if path in expected] == expected
    assert "Podman services | Normalize service" not in MAIN_TASKS
    assert "Podman services | Include removal handler flush" in MAIN_TASKS


def test_quadlet_directory_prerequisite_exists_before_templates():
    directory = next(task for task in PREPARE_TASK_LIST if task["name"] == "Prep | Ensure selected Quadlet directory exists")
    first_template = next(task for task in PREPARE_TASK_LIST if "ansible.builtin.template" in task)

    assert PREPARE_TASK_LIST.index(directory) < PREPARE_TASK_LIST.index(first_template)
    assert directory["ansible.builtin.file"]["path"] == "{{ podman_services_quadlet_dir }}"
    assert directory["ansible.builtin.file"]["mode"] == ("{{ '0700' if podman_services_execution.mode == 'rootless' else '0755' }}")


def test_n8n_declares_a_managed_network_without_delete_on_stop():
    n8n = yaml.safe_load(N8N)["n8n"]

    assert n8n["named_networks"] == {"n8n": {"driver": "bridge", "external": False}}
    assert "delete_on_stop" not in N8N
    assert "NetworkDeleteOnStop" not in NETWORK_TEMPLATE


def test_remove_stops_container_before_network_then_removes_files():
    ordered = [
        "Remove | Stop service for removal without deleting data",
        "Remove | Stop system managed network unit for removal",
        "Remove | Check proven managed network still exists",
        "Remove | Remove proven managed network if present",
        "Remove | Remove persisted generated files only",
    ]
    assert [REMOVE_TASK_NAMES.index(name) for name in ordered] == sorted(REMOVE_TASK_NAMES.index(name) for name in ordered)


def test_remove_only_orchestration_is_guarded_by_normalized_action():
    tasks = yaml.safe_load(MAIN_TASKS)
    remove_only_tasks = {
        "Podman services | Include removal tasks",
        "Podman services | Remove runtime-neutral integrations",
        "Podman services | Include removal handler flush",
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


def test_external_or_unproven_network_is_not_created_or_removed():
    prepare = next(task for task in yaml.safe_load(PREPARE_TASKS) if task["name"] == "Prep | Render network Quadlet")
    remove_tasks = yaml.safe_load(REMOVE_TASKS)
    managed_network_tasks = [
        task
        for task in remove_tasks
        if task["name"]
        in {
            "Remove | Stop system managed network unit for removal",
            "Remove | Check proven managed network still exists",
            "Remove | Remove proven managed network if present",
        }
    ]

    assert "not podman_services_service.network.external | bool" in prepare["when"]
    assert len(managed_network_tasks) == 3
    for task in managed_network_tasks:
        assert "podman_services_remove_network.managed | default(false) | bool" in task["when"]
    assert "podman_services_service.network.name" not in REMOVE_TASKS


def test_changed_managed_network_is_retained_during_update_and_recreate():
    tasks = yaml.safe_load(NETWORK_TASKS)

    assert [task["name"] for task in tasks] == ["Network | Report retained managed network definition change"]
    assert tasks[0]["changed_when"] is False
    assert "podman network" not in NETWORK_TASKS
    assert "ansible.builtin.systemd_service" not in NETWORK_TASKS


def test_managed_network_quadlet_is_rendered_before_container_quadlet():
    assert PREPARE_TASK_NAMES.index("Prep | Render network Quadlet") < PREPARE_TASK_NAMES.index("Prep | Render container Quadlet")


def test_no_late_shared_network_migration_fail_after_template_render():
    assert "Refuse implicit shared network migration" not in TASKS
    assert "Coordinate shared network migration" not in TASKS


def test_network_validation_occurs_before_template_rendering():
    assert ALL_TASK_NAMES.index("Init | Normalize service") < ALL_TASK_NAMES.index("Prep | Render network Quadlet")


def test_managed_network_remove_failure_is_not_suppressed():
    task = next(task for task in yaml.safe_load(REMOVE_TASKS) if task["name"] == "Remove | Remove proven managed network if present")

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
    assert REMOVE_TASK_NAMES.index("Remove | Check container unit load state for removal") < REMOVE_TASK_NAMES.index(
        "Remove | Stop service for removal without deleting data"
    )
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
    assert f"listen: {handler_name}" in PODMAN_HANDLERS
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
    task = next(task for task in tasks if task["name"] == "Remove | Remove persisted generated files only")

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
    native_secret = MAIN_TASK_NAMES.index("Podman services | Materialize Podman-native secrets")
    shared = MAIN_TASK_NAMES.index("Podman services | Prepare runtime-neutral host state")
    prepare = MAIN_TASK_NAMES.index("Podman services | Include preparation tasks")

    assert (
        ALL_TASK_NAMES.index("Init | Snapshot dispatch-owned common context")
        < ALL_TASK_NAMES.index("Prep | Render protected environment file")
        < ALL_TASK_NAMES.index("Prep | Render container Quadlet")
    )
    assert native_secret < shared < prepare
    native_secret_task = MAIN_TASK_LIST[native_secret]
    assert "not ansible_check_mode" in native_secret_task["when"]


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


def test_remove_handler_flush_is_gated_by_a_conditional_dynamic_include():
    main_tasks = yaml.safe_load(MAIN_TASKS)
    include = next(task for task in main_tasks if task["name"] == "Podman services | Include removal handler flush")
    flush_tasks = yaml.safe_load((TASKS_DIR / "sub_tasks" / "flush_remove_handlers.yml").read_text())

    assert include["when"] == "podman_services_common_action == 'remove'"
    assert include["ansible.builtin.include_tasks"] == {
        "file": "sub_tasks/flush_remove_handlers.yml",
        "apply": {"tags": ["remove"]},
    }
    assert include["tags"] == ["remove"]
    assert "ansible.builtin.meta" not in include
    assert flush_tasks == [
        {
            "name": "Podman services | Flush removal daemon-reload handlers",
            "ansible.builtin.meta": "flush_handlers",
            "tags": ["remove"],
        }
    ]
    assert "when" not in flush_tasks[0]


def test_external_network_preflight_uses_exact_read_only_podman_argv():
    tasks = yaml.safe_load(MAIN_TASKS)
    check = next(task for task in tasks if task["name"] == "Podman services | Check external network exists")
    require = next(task for task in tasks if task["name"] == "Podman services | Require external network")

    assert check["ansible.builtin.command"] == {"argv": ["podman", "network", "exists", "{{ podman_services_service.network.name }}"]}
    assert "ansible.builtin.shell" not in check
    assert check["changed_when"] is False
    assert check["failed_when"] is False
    assert check["register"] == "podman_services_external_network_check"
    assert require["ansible.builtin.assert"]["that"] == ["podman_services_external_network_check.rc == 0"]
    assert "Podman network store" in require["ansible.builtin.assert"]["fail_msg"]


def test_external_network_preflight_is_live_only_and_excludes_remove_and_managed_networks():
    tasks = yaml.safe_load(MAIN_TASKS)
    preflight = [
        task
        for task in tasks
        if task["name"]
        in {
            "Podman services | Check external network exists",
            "Podman services | Require external network",
        }
    ]

    assert len(preflight) == 2
    for task in preflight:
        assert "not ansible_check_mode" in task["when"]
        assert "podman_services_common_action in ['deploy', 'update', 'recreate', 'bootstrap']" in task["when"]
        assert "podman_services_service.network is mapping" in task["when"]
        assert "podman_services_service.network.external | bool" in task["when"]
        assert "remove" not in task["tags"]
        assert "drift" not in task["tags"]


def test_external_network_failure_is_fatal_before_any_mutating_service_work():
    tasks = yaml.safe_load(MAIN_TASKS)
    names = [task["name"] for task in tasks]
    require = names.index("Podman services | Require external network")
    later_mutating_boundaries = [
        "Podman services | Check deployed service unit before recreate preparation",
        "Podman services | Generate runtime-neutral application secrets",
        "Podman services | Materialize Podman-native secrets",
        "Podman services | Prepare runtime-neutral host state",
        "Podman services | Include preparation tasks",
        "Podman services | Include service lifecycle tasks",
    ]

    assert names.index("Podman services | Include initialization tasks") < require
    assert all(require < names.index(name) for name in later_mutating_boundaries)


def test_normalized_unit_name_drives_generated_files_container_name_and_lifecycle_unit():
    init_tasks = yaml.safe_load((TASKS_DIR / "sub_tasks" / "init.yml").read_text())
    prepare_tasks = yaml.safe_load(PREPARE_TASKS)
    lifecycle_tasks = yaml.safe_load((TASKS_DIR / "sub_tasks" / "lifecycle.yml").read_text())
    derive = next(task for task in init_tasks if task["name"] == "Init | Derive normalized systemd unit name")
    env_render = next(task for task in prepare_tasks if task["name"] == "Prep | Render protected environment file")
    container_render = next(task for task in prepare_tasks if task["name"] == "Prep | Render container Quadlet")

    assert derive["ansible.builtin.set_fact"]["podman_services_unit_name"] == ("{{ podman_services_service.unit_name ~ '.service' }}")
    assert env_render["ansible.builtin.template"]["dest"].endswith("/{{ podman_services_service.unit_name }}.env")
    assert container_render["ansible.builtin.template"]["dest"].endswith("/{{ podman_services_service.unit_name }}.container")
    assert "ContainerName={{ podman_service.unit_name }}" in (
        (REPO_ROOT / "ansible/roles/podman_services/templates/container.container.j2").read_text()
    )
    lifecycle_units = [
        task["ansible.builtin.systemd_service"]["name"] for task in lifecycle_tasks if "ansible.builtin.systemd_service" in task
    ]
    assert lifecycle_units
    assert set(lifecycle_units) == {"{{ podman_services_unit_name }}"}


def test_rootless_account_preparation_is_separate_and_safe_in_check_mode():
    tasks = yaml.safe_load(EXECUTION_PREPARE_TASKS)
    account = next(task for task in tasks if task["name"] == "Execution | Provision dedicated rootless account")
    linger = next(task for task in tasks if task["name"] == "Execution | Enable rootless account linger")
    manager = next(task for task in tasks if task["name"] == "Execution | Start rootless user manager")

    assert account["ansible.builtin.user"] == {
        "name": "{{ podman_services_execution.host_user }}",
        "comment": "Managed rootless Podman account for {{ podman_services_service.name }}",
        "home": "{{ podman_services_execution_home }}",
        "create_home": True,
        "shell": "{{ podman_services_nologin_shell }}",
        "password_lock": True,
        "group": "{{ podman_services_execution.host_user }}",
        "groups": "",
        "append": False,
        "state": "present",
    }
    for task in (account, linger, manager):
        assert "not ansible_check_mode" in task["when"]
    assert "podman_services_rootless_account_plan.create | bool" in account["when"]
    assert linger["ansible.builtin.command"]["argv"] == [
        "loginctl",
        "enable-linger",
        "{{ podman_services_execution.host_user }}",
    ]
    assert manager["ansible.builtin.systemd_service"]["name"] == "user@{{ podman_services_execution_uid }}.service"


def test_rootless_runtime_context_is_task_owned_and_reset_per_service():
    init = (TASKS_DIR / "sub_tasks" / "init.yml").read_text()

    assert "podman_services_execution: {}" in init
    assert "podman_services_runtime_environment: {}" in init
    assert "HOME:" in EXECUTION_PREPARE_TASKS
    assert "XDG_RUNTIME_DIR:" in EXECUTION_PREPARE_TASKS
    assert "DBUS_SESSION_BUS_ADDRESS:" in EXECUTION_PREPARE_TASKS
    assert "ansible_facts.getent_passwd" in EXECUTION_PREPARE_TASKS
    assert "{{ getent_passwd" not in EXECUTION_PREPARE_TASKS
    container_template = (REPO_ROOT / "ansible/roles/podman_services/templates/container.container.j2").read_text()
    assert "XDG_RUNTIME_DIR" not in container_template
    assert "DBUS_SESSION_BUS_ADDRESS" not in container_template


def test_rootless_quadlet_paths_and_ownership_are_execution_selected():
    prepare = yaml.safe_load(PREPARE_TASKS)
    directory = next(task for task in prepare if task["name"] == "Prep | Ensure selected Quadlet directory exists")
    renders = [task for task in prepare if "ansible.builtin.template" in task]

    assert directory["ansible.builtin.file"]["path"] == "{{ podman_services_quadlet_dir }}"
    assert "0700" in directory["ansible.builtin.file"]["mode"]
    for task in renders:
        template = task["ansible.builtin.template"]
        assert template["owner"] == "{{ podman_services_execution_owner }}"
        assert template["group"] == "{{ podman_services_execution_group }}"
        assert "not (ansible_check_mode and podman_services_execution.mode == 'rootless')" in task["when"]


def test_rootless_operations_use_selected_account_and_user_manager():
    lifecycle = yaml.safe_load(LIFECYCLE_TASKS)
    user_tasks = [task for task in lifecycle if "user service" in task["name"] or "user systemd" in task["name"]]

    assert user_tasks
    for task in user_tasks:
        assert task["become_user"] == "{{ podman_services_execution.host_user }}"
        assert task["environment"] == "{{ podman_services_runtime_environment }}"
    assert any(task.get("ansible.builtin.systemd_service", {}).get("scope") == "user" for task in user_tasks)
    assert "become_user: \"{{ podman_services_execution.host_user | default('root') }}\"" in (
        (TASKS_DIR / "sub_tasks" / "image.yml").read_text()
    )


def test_transition_validates_target_before_stopping_previous_and_cleans_only_after_success():
    assert MAIN_TASK_NAMES.index("Podman services | Include execution preparation tasks") < MAIN_TASK_NAMES.index(
        "Podman services | Check deployed service unit before recreate preparation"
    )
    assert LIFECYCLE_TASK_NAMES.index("Lifecycle | Validate user Quadlets with Podman generator dry run") < LIFECYCLE_TASK_NAMES.index(
        "Lifecycle | Include safe execution transition"
    )
    assert (
        EXECUTION_TRANSITION_TASK_NAMES.index("Transition | Start and verify desired execution owner")
        < EXECUTION_TRANSITION_TASK_NAMES.index("Transition | Require managed marker before stale deletion")
        < EXECUTION_TRANSITION_TASK_NAMES.index("Transition | Remove exact marked stale generated files")
    )
    transition = next(
        task for task in EXECUTION_TRANSITION_TASK_LIST if task["name"] == "Transition | Start and verify desired execution owner"
    )
    rescue_names = [task["name"] for task in transition["rescue"]]
    report = rescue_names.index("Transition | Report failed transition after rollback")
    assert rescue_names.index("Transition | Restore previous system service") < report
    assert rescue_names.index("Transition | Restore previous user service") < report


def test_transition_targets_exact_unit_and_does_not_prune_podman_state():
    assert "{{ podman_services_unit_name }}" in EXECUTION_TRANSITION_TASKS
    assert "podman network rm" not in EXECUTION_TRANSITION_TASKS
    assert 'argv: [podman, network, rm, "{{ podman_services_previous_network.name }}"]' in EXECUTION_TRANSITION_TASKS
    assert "podman_services_service.network.name" not in EXECUTION_TRANSITION_TASKS
    assert "prune" not in EXECUTION_TRANSITION_TASKS
    assert "--force" not in EXECUTION_TRANSITION_TASKS


def test_rootful_lifecycle_remains_system_scoped_and_rootless_lifecycle_is_user_scoped():
    lifecycle = yaml.safe_load(LIFECYCLE_TASKS)
    rootful = next(task for task in lifecycle if task["name"] == "Lifecycle | Start service for deploy/bootstrap")
    rootless = next(task for task in lifecycle if task["name"] == "Lifecycle | Start user service for deploy/bootstrap")

    assert "scope" not in rootful["ansible.builtin.systemd_service"]
    assert "podman_services_execution.mode == 'rootful'" in rootful["when"]
    assert rootless["ansible.builtin.systemd_service"]["scope"] == "user"
    assert "podman_services_execution.mode == 'rootless'" in rootless["when"]


def test_rootful_and_rootless_generated_file_removal_requires_managed_marker():
    read = next(task for task in REMOVE_TASK_LIST if task["name"] == "Remove | Read existing managed generated files")
    marker = next(task for task in REMOVE_TASK_LIST if task["name"] == "Remove | Require managed marker before generated-file deletion")
    delete = next(task for task in REMOVE_TASK_LIST if task["name"] == "Remove | Remove persisted generated files only")

    for task in (read, marker):
        assert "podman_services_active_execution.mode in ['rootful', 'rootless']" in task["when"]
        assert task["no_log"] is True
        assert task["diff"] is False
    assert "Generated by Ansible" in str(marker["ansible.builtin.assert"]["that"])
    assert delete["loop"] == "{{ podman_services_remove_generated_paths }}"


def test_rootless_account_is_inspected_before_any_account_mutation_and_uses_a_dedicated_group():
    tasks = yaml.safe_load(EXECUTION_PREPARE_TASKS)
    names = [task["name"] for task in tasks]

    decision = names.index("Execution | Decide safe rootless account handling")
    group = names.index("Execution | Provision dedicated rootless primary group")
    account = names.index("Execution | Provision dedicated rootless account")
    assert names.index("Execution | Inspect selected rootless account") < decision < group < account
    assert names.index("Execution | Inspect selected rootless home") < decision
    assert names.index("Execution | Inspect selected account marker") < decision
    assert "podman_rootless_account_contract" in str(tasks[decision])
    assert tasks[group]["ansible.builtin.group"]["name"] == "{{ podman_services_execution.host_user }}"
    assert tasks[account]["ansible.builtin.user"]["group"] == "{{ podman_services_execution.host_user }}"
    assert tasks[account]["ansible.builtin.user"]["groups"] == ""


def test_remove_and_drift_select_persisted_active_owner_without_creating_rootless_state():
    prepare = yaml.safe_load(EXECUTION_PREPARE_TASKS)
    select = next(task for task in prepare if task["name"] == "Execution | Derive selected execution owner")
    account = next(task for task in prepare if task["name"] == "Execution | Provision dedicated rootless account")
    linger = next(task for task in prepare if task["name"] == "Execution | Enable rootless account linger")
    directory = next(task for task in yaml.safe_load(PREPARE_TASKS) if task["name"] == "Prep | Ensure selected Quadlet directory exists")

    assert (
        "podman_services_common_action in ['remove', 'drift']" in select["ansible.builtin.set_fact"]["podman_services_operation_execution"]
    )
    for task in (account, linger):
        assert "podman_services_common_action in ['deploy', 'update', 'recreate', 'bootstrap']" in task["when"]
    assert "podman_services_state != 'remove'" in directory["when"]
    assert "podman_services_active_execution" in REMOVE_TASKS
    assert "podman_services_active_execution" in (TASKS_DIR / "sub_tasks" / "drift.yml").read_text()


def test_execution_state_tracks_exact_generated_resources_and_removal_deletes_state_last():
    lifecycle = yaml.safe_load(LIFECYCLE_TASKS)
    remove = yaml.safe_load(REMOVE_TASKS)
    resources = next(task for task in lifecycle if task["name"] == "Lifecycle | Build successful execution resource metadata")
    persist = next(task for task in lifecycle if task["name"] == "Lifecycle | Persist successful execution owner")
    state_remove = next(task for task in remove if task["name"] == "Remove | Remove persisted execution state after active cleanup")

    assert set(resources["ansible.builtin.set_fact"]["podman_services_execution_resource_state"]) == {
        "network",
        "volumes",
        "generated_files",
    }
    content = persist["ansible.builtin.copy"]["content"]
    assert "version: 2" in content
    assert "quadlet_dir:" in content
    assert "unit_name:" in content
    assert "resources:" in content
    assert remove.index(state_remove) == len(remove) - 1


def test_drift_initializes_a_missing_result_before_optional_active_store_inspection():
    tasks = yaml.safe_load(DRIFT_TASKS)
    names = [task["name"] for task in tasks]
    initialize = next(task for task in tasks if task["name"] == "Drift | Initialize missing active-service inspection")
    inspect = next(task for task in tasks if task["name"] == "Drift | Check current image reference")
    capture = next(task for task in tasks if task["name"] == "Drift | Capture active-service inspection")
    classify = next(task for task in tasks if task["name"] == "Drift | Classify image reference drift")

    assert names.index(initialize["name"]) < names.index(inspect["name"]) < names.index(capture["name"]) < names.index(classify["name"])
    assert initialize["ansible.builtin.set_fact"]["podman_services_drift_inspection_result"] == {"rc": 125, "stdout": ""}
    for task in (inspect, capture):
        assert "not ansible_check_mode" in task["when"]
        assert "podman_services_active_execution.mode in ['rootful', 'rootless']" in task["when"]
    assert inspect["become_user"] == "{{ podman_services_active_execution.host_user | default('root') }}"
    assert inspect["environment"] == "{{ podman_services_runtime_environment }}"
    assert capture["ansible.builtin.set_fact"]["podman_services_drift_inspection_result"] == ("{{ podman_services_drift_inspect_command }}")
    assert "podman_services_drift_inspection_result" in classify["ansible.builtin.set_fact"]["podman_services_image_reference_drift"]
    assert "podman_services_desired_execution" not in DRIFT_TASKS


def test_previous_managed_network_cleanup_is_failure_aware_and_transactional():
    tasks = yaml.safe_load(EXECUTION_TRANSITION_TASKS)
    names = [task["name"] for task in tasks]
    query_unit = next(task for task in tasks if task["name"] == "Transition | Query previous system managed network unit")
    query_user_unit = next(task for task in tasks if task["name"] == "Transition | Query previous user managed network unit")
    require_unit = next(task for task in tasks if task["name"] == "Transition | Require previous managed network unit query")
    stop_units = [
        task
        for task in tasks
        if task["name"]
        in {"Transition | Stop previous system managed network unit", "Transition | Stop previous user managed network unit"}
    ]
    query = next(task for task in tasks if task["name"] == "Transition | Query previous managed network existence")
    remove = next(task for task in tasks if task["name"] == "Transition | Remove proven unused previous managed network")
    verify = next(task for task in tasks if task["name"] == "Transition | Verify previous managed network absence")
    require_absent = next(task for task in tasks if task["name"] == "Transition | Require previous managed network absence")
    delete = next(task for task in tasks if task["name"] == "Transition | Remove exact marked stale generated files")
    persist = next(task for task in yaml.safe_load(LIFECYCLE_TASKS) if task["name"] == "Lifecycle | Persist successful execution owner")

    for unit_query in (query_unit, query_user_unit):
        assert unit_query["failed_when"] is False
        assert unit_query["register"] in str(require_unit["ansible.builtin.assert"]["that"])
    assert len(stop_units) == 2
    assert all("failed_when" not in task for task in stop_units)
    assert "podman_services_previous_system_network_unit.rc | default(1) == 0" in str(require_unit["ansible.builtin.assert"]["that"])
    assert "['loaded', 'not-found']" in str(require_unit["ansible.builtin.assert"]["that"])
    assert query["ansible.builtin.command"]["argv"] == [
        "podman",
        "network",
        "exists",
        "{{ podman_services_previous_network.name }}",
    ]
    assert query["failed_when"] == "podman_services_previous_network_exists.rc not in [0, 1]"
    assert "podman_services_previous_network_exists.rc == 0" in remove["when"]
    assert "failed_when" not in remove
    assert verify["failed_when"] == "podman_services_previous_network_verify.rc not in [0, 1]"
    assert require_absent["ansible.builtin.assert"]["that"] == ["podman_services_previous_network_verify.rc == 1"]
    assert names.index(require_unit["name"]) < names.index(query["name"])
    assert names.index(query["name"]) < names.index(remove["name"]) < names.index(verify["name"])
    assert names.index(verify["name"]) < names.index(require_absent["name"]) < names.index(delete["name"])
    assert "previous files and ownership state are retained" in require_unit["ansible.builtin.assert"]["fail_msg"]
    assert "previous files and ownership state are retained" in require_absent["ansible.builtin.assert"]["fail_msg"]
    lifecycle_include = next(
        task for task in yaml.safe_load(LIFECYCLE_TASKS) if task["name"] == "Lifecycle | Include safe execution transition"
    )
    assert "ignore_errors" not in lifecycle_include
    assert LIFECYCLE_TASK_NAMES.index(lifecycle_include["name"]) < LIFECYCLE_TASK_NAMES.index(persist["name"])


def test_execution_transitions_clean_only_previous_store_and_network_metadata():
    derive = next(task for task in EXECUTION_TRANSITION_TASK_LIST if task["name"] == "Transition | Derive previous execution resources")
    runtime_tasks = [
        next(task for task in EXECUTION_TRANSITION_TASK_LIST if task["name"] == name)
        for name in (
            "Transition | Query previous managed network existence",
            "Transition | Remove proven unused previous managed network",
            "Transition | Verify previous managed network absence",
        )
    ]

    assert "podman_services_previous_execution.resources" in str(derive)
    assert "podman_services_previous_execution.version | default(0) == 2" in str(derive)
    for task in runtime_tasks:
        assert task["ansible.builtin.command"]["argv"][-1] == "{{ podman_services_previous_network.name }}"
        assert "podman_services_previous_execution.host_user" in task["become_user"]
        assert task["environment"] == "{{ podman_services_previous_runtime_environment }}"
    assert "podman_services_service.network.name" not in EXECUTION_TRANSITION_TASKS
    assert "podman_services_runtime_environment" not in str(runtime_tasks)


def test_protocol_normalization_is_not_duplicated():
    source = (REPO_ROOT / "ansible/roles/podman_services/filter_plugins/podman_services.py").read_text()

    assert source.count('protocol = str(port.get("protocol", "tcp")).strip().lower()') == 1


def test_transition_failure_reports_start_stop_and_rollback_diagnostics_without_journal_output():
    tasks = yaml.safe_load(EXECUTION_TRANSITION_TASKS)
    transition = next(task for task in tasks if task["name"] == "Transition | Start and verify desired execution owner")
    report = next(task for task in transition["rescue"] if task["name"] == "Transition | Report failed transition after rollback")
    message = report["ansible.builtin.fail"]["msg"]

    assert "Desired start rc=" in message
    assert "Stopping the failed destination rc=" in message
    assert "Restoring the previous service rc=" in message
    assert "stderr" in message
    assert "journal" not in message.lower()


def test_transition_generated_file_contents_are_not_logged():
    tasks = yaml.safe_load(EXECUTION_TRANSITION_TASKS)
    read = next(task for task in tasks if task["name"] == "Transition | Read exact stale generated files")
    marker = next(task for task in tasks if task["name"] == "Transition | Require managed marker before stale deletion")

    for task in (read, marker):
        assert task["no_log"] is True
        assert task["diff"] is False


def test_execution_preparation_is_included_with_all_service_action_tags():
    include = next(task for task in yaml.safe_load(MAIN_TASKS) if task["name"] == "Podman services | Include execution preparation tasks")
    expected = {"deploy", "update", "remove", "recreate", "drift", "bootstrap"}

    assert set(include["tags"]) == expected
    assert set(include["ansible.builtin.include_tasks"]["apply"]["tags"]) == expected


def test_rootless_check_mode_uses_an_in_memory_render_plan_without_runtime_modules():
    check_tasks = yaml.safe_load((TASKS_DIR / "sub_tasks" / "check_render.yml").read_text())
    include = next(task for task in PREPARE_TASK_LIST if task["name"] == "Prep | Validate rootless Quadlet render plan")
    names = [task["name"] for task in check_tasks]

    assert include["ansible.builtin.include_tasks"]["file"] == "sub_tasks/check_render.yml"
    assert "ansible_check_mode" in include["when"]
    assert "podman_services_execution.mode == 'rootless'" in include["when"]
    assert {
        "Check render | Render managed network in memory",
        "Check render | Render managed volumes in memory",
        "Check render | Render protected environment in memory",
        "Check render | Render container in memory",
        "Check render | Validate in-memory artifact syntax",
        "Check render | Report planned artifact change",
    }.issubset(names)
    rendered = " ".join(str(task.get("ansible.builtin.set_fact", {})) for task in check_tasks)
    for template in ("network.network.j2", "volume.volume.j2", "env.env.j2", "container.container.j2"):
        assert template in rendered
    assert not any(
        module in task
        for task in check_tasks
        for module in (
            "ansible.builtin.command",
            "ansible.builtin.systemd_service",
            "ansible.builtin.file",
            "ansible.builtin.copy",
            "ansible.builtin.template",
        )
    )


def test_execution_owner_and_previous_quadlet_derivations_are_sequential():
    prepare_names = [task["name"] for task in EXECUTION_PREPARE_TASK_LIST]
    active = next(task for task in EXECUTION_PREPARE_TASK_LIST if task["name"] == "Execution | Derive active execution owner")
    previous = next(
        task for task in EXECUTION_PREPARE_TASK_LIST if task["name"] == "Execution | Preserve active execution as previous owner"
    )
    transition_names = [task["name"] for task in EXECUTION_TRANSITION_TASK_LIST]
    directory = next(task for task in EXECUTION_TRANSITION_TASK_LIST if task["name"] == "Transition | Derive previous Quadlet directory")
    resources = next(task for task in EXECUTION_TRANSITION_TASK_LIST if task["name"] == "Transition | Derive previous execution resources")

    assert prepare_names.index(active["name"]) < prepare_names.index(previous["name"])
    assert previous["ansible.builtin.set_fact"]["podman_services_previous_execution"] == ("{{ podman_services_active_execution }}")
    assert transition_names.index(directory["name"]) < transition_names.index(resources["name"])
    assert "podman_services_previous_quadlet_dir" in resources["ansible.builtin.set_fact"]["podman_services_stale_generated_paths"]


def test_execution_state_versions_gate_resource_aware_cleanup():
    version = next(task for task in EXECUTION_PREPARE_TASK_LIST if task["name"] == "Execution | Validate persisted execution state version")
    remove = next(task for task in REMOVE_TASK_LIST if task["name"] == "Remove | Derive persisted active resources")
    facts = remove["ansible.builtin.set_fact"]

    assert "podman_services_execution_state.version is not defined" in str(version["ansible.builtin.assert"]["that"])
    assert "podman_services_execution_state.version is integer" in str(version["ansible.builtin.assert"]["that"])
    assert "podman_services_execution_state.version == 2" in str(version["ansible.builtin.assert"]["that"])
    assert "version | default(0) == 2" in facts["podman_services_remove_network"]
    assert "version | default(0) == 2" in facts["podman_services_remove_generated_paths"]
