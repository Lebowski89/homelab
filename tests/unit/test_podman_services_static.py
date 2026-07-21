from pathlib import Path

TASKS = Path("ansible/roles/podman_services/tasks/main.yml").read_text()
N8N = Path("ansible/group_vars/all/services/n8n.yml").read_text()
NETWORK_TEMPLATE = Path("ansible/roles/podman_services/templates/network.network.j2").read_text()


def test_quadlet_directory_prerequisite_exists_before_templates():
    dir_pos = TASKS.index("Podman | Ensure system Quadlet directory exists")
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
    normalize = TASKS.index("Podman services | Normalize service")
    network_template = TASKS.index("Podman services | Render network Quadlet")
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


def test_absent_container_unit_is_checked_before_stop():
    load_state = TASKS.index("Check container unit load state for removal")
    stop = TASKS.index("Stop service for removal without deleting data")
    assert load_state < stop
    assert "--property=LoadState" in TASKS
    assert "stdout | trim != 'not-found'" in TASKS
