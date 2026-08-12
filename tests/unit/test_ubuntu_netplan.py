import importlib.util
from pathlib import Path

import pytest
import yaml
from ansible.plugins.filter.core import FilterModule
from ansible.plugins.test.core import TestModule as AnsibleTestModule
from jinja2 import Environment, FileSystemLoader

REPO_ROOT = Path(__file__).resolve().parents[2]
UBUNTU_ROLE = REPO_ROOT / "ansible/roles/ubuntu"
MAIN_TASKS = yaml.safe_load((UBUNTU_ROLE / "tasks/main.yml").read_text())
NETPLAN_TASKS = yaml.safe_load((UBUNTU_ROLE / "tasks/sub_tasks/netplan.yml").read_text())
VENV_TASKS = yaml.safe_load((UBUNTU_ROLE / "tasks/sub_tasks/venv.yml").read_text())
VENV_FILTER_PATH = UBUNTU_ROLE / "filter_plugins/ubuntu_venv.py"
VENV_FILTER_SPEC = importlib.util.spec_from_file_location("ubuntu_venv", VENV_FILTER_PATH)
ubuntu_venv = importlib.util.module_from_spec(VENV_FILTER_SPEC)
assert VENV_FILTER_SPEC.loader is not None
VENV_FILTER_SPEC.loader.exec_module(ubuntu_venv)
NETPLAN_TEMPLATE_PATH = UBUNTU_ROLE / "templates/netplan-config.yaml.j2"
NETPLAN_TEMPLATE = NETPLAN_TEMPLATE_PATH.read_text()
ANSIBLE_BOOL = FilterModule().filters()["bool"]
ANSIBLE_MATCH = AnsibleTestModule().tests()["match"]


def task_named(tasks, name):
    return next(task for task in tasks if task["name"] == name)


def ansible_environment():
    environment = Environment()
    environment.filters["bool"] = ANSIBLE_BOOL
    environment.tests["match"] = ANSIBLE_MATCH
    return environment


def normalize_netplan_values(
    local_ip,
    requested_interface,
    discovered_interface,
    gateway="192.0.2.1",
    prefix=24,
):
    environment = ansible_environment()
    values = {
        "local_ip": local_ip,
        "ubuntu_defaults_netplan_gateway": gateway,
        "ubuntu_netplan_interface": requested_interface,
        "ubuntu_netplan_prefix": prefix,
        "ansible_facts": {
            "default_ipv4": {
                "interface": discovered_interface,
            }
        },
    }

    for task_name in (
        "Normalize Netplan address and interface inputs",
        "Resolve effective Netplan interface",
    ):
        task = task_named(NETPLAN_TASKS, task_name)
        normalized = {
            key: environment.from_string(expression).render(**values) for key, expression in task["ansible.builtin.set_fact"].items()
        }
        values.update(normalized)

    return values


def validate_netplan_values(*args, **kwargs):
    environment = ansible_environment()
    values = normalize_netplan_values(*args, **kwargs)
    task = task_named(NETPLAN_TASKS, "Assert Netplan inputs are valid")
    failed = [condition for condition in task["ansible.builtin.assert"]["that"] if not environment.compile_expression(condition)(**values)]
    if failed:
        raise AssertionError(task["ansible.builtin.assert"]["fail_msg"])
    return values


def netplan_include_selected(enabled, virtualization_type, opentofu_managed=False):
    task = task_named(MAIN_TASKS, "Ubuntu | Configure Netplan")
    environment = ansible_environment()
    variables = {
        "ubuntu_netplan_enabled": enabled,
        "ansible_facts": {"virtualization_type": virtualization_type},
        "tags_opentofu_managed": ["localhost"] if opentofu_managed else [],
        "inventory_hostname": "localhost",
    }
    return all(environment.compile_expression(condition)(**variables) for condition in task["when"])


def test_netplan_normalization_trims_local_ip():
    values = normalize_netplan_values("  192.0.2.10  ", "ens18", "ens19")

    assert values["ubuntu_netplan_ipv4_address"] == "192.0.2.10"


def test_netplan_normalization_trims_gateway():
    values = normalize_netplan_values(
        "192.0.2.10",
        "ens18",
        "ens19",
        gateway="  192.0.2.1  ",
    )

    assert values["ubuntu_netplan_ipv4_gateway"] == "192.0.2.1"


def test_netplan_normalization_trims_explicit_interface():
    values = normalize_netplan_values("192.0.2.10", "  ens18  ", "ens19")

    assert values["ubuntu_netplan_requested_interface"] == "ens18"
    assert values["ubuntu_netplan_effective_interface"] == "ens18"


def test_whitespace_only_explicit_interface_falls_back_to_trimmed_discovery():
    values = normalize_netplan_values("192.0.2.10", "   ", "  ens19  ")

    assert values["ubuntu_netplan_requested_interface"] == ""
    assert values["ubuntu_netplan_discovered_interface"] == "ens19"
    assert values["ubuntu_netplan_effective_interface"] == "ens19"


def test_netplan_template_renders_only_normalized_address_and_interface():
    environment = Environment(
        loader=FileSystemLoader(NETPLAN_TEMPLATE_PATH.parent),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    rendered = environment.get_template(NETPLAN_TEMPLATE_PATH.name).render(
        ubuntu_netplan_ipv4_address="192.0.2.10",
        ubuntu_netplan_effective_interface="ens18",
        ubuntu_netplan_prefix=24,
        ubuntu_netplan_ipv4_gateway="192.0.2.1",
        ubuntu_defaults_netplan_nameservers=["192.0.2.53"],
        ubuntu_netplan_search_domains=["example.test"],
        local_ip="  198.51.100.20  ",
        ubuntu_netplan_interface="  raw-interface  ",
    )
    config = yaml.safe_load(rendered)

    assert set(config["network"]["ethernets"]) == {"ens18"}
    interface = config["network"]["ethernets"]["ens18"]
    assert interface["addresses"] == ["192.0.2.10/24"]
    assert interface["dhcp4"] is False
    assert interface["dhcp6"] is False
    assert interface["routes"] == [{"to": "default", "via": "192.0.2.1"}]
    assert "198.51.100.20" not in rendered
    assert "raw-interface" not in rendered
    assert "local_ip" not in NETPLAN_TEMPLATE
    assert "ubuntu_netplan_interface" not in NETPLAN_TEMPLATE
    assert "ubuntu_defaults_netplan_gateway" not in NETPLAN_TEMPLATE


@pytest.mark.parametrize("address", ["999.0.2.10", "not-an-address"])
def test_netplan_validation_rejects_malformed_address(address):
    with pytest.raises(AssertionError, match="plain static IPv4 address"):
        validate_netplan_values(address, "ens18", "ens19")


def test_netplan_validation_rejects_address_with_cidr():
    with pytest.raises(AssertionError, match="without CIDR syntax"):
        validate_netplan_values("192.0.2.10/24", "ens18", "ens19")


def test_netplan_validation_rejects_invalid_gateway():
    with pytest.raises(AssertionError, match="IPv4.*gateway"):
        validate_netplan_values("192.0.2.10", "ens18", "ens19", gateway="192.0.2.999")


@pytest.mark.parametrize("prefix", [0, 33])
def test_netplan_validation_rejects_invalid_prefix(prefix):
    with pytest.raises(AssertionError, match="prefix between 1 and 32"):
        validate_netplan_values("192.0.2.10", "ens18", "ens19", prefix=prefix)


def test_netplan_validation_rejects_missing_interface():
    with pytest.raises(AssertionError, match="default IPv4 interface"):
        validate_netplan_values("192.0.2.10", "   ", "   ")


def test_netplan_validation_precedes_all_file_mutations():
    validation = task_named(NETPLAN_TASKS, "Assert Netplan inputs are valid")
    mutating_tasks = [
        task
        for task in NETPLAN_TASKS
        if "ansible.builtin.copy" in task
        or "ansible.builtin.file" in task
        or "ansible.builtin.template" in task
        or "ansible.builtin.meta" in task
    ]

    assert mutating_tasks
    assert all(NETPLAN_TASKS.index(validation) < NETPLAN_TASKS.index(task) for task in mutating_tasks)


def test_post_apply_verification_uses_normalized_ipv4_address():
    task = task_named(
        NETPLAN_TASKS,
        "Verify expected static IPv4 address is assigned",
    )

    assert task["ansible.builtin.assert"]["that"] == ["ubuntu_netplan_ipv4_address in (ansible_facts.all_ipv4_addresses | default([]))"]
    fail_msg = task["ansible.builtin.assert"]["fail_msg"]
    assert "{{ ubuntu_netplan_ipv4_address }}" in fail_msg
    assert "{{ local_ip }}" not in fail_msg


def test_cloud_init_network_disable_file_has_true_and_false_lifecycle_paths():
    create = task_named(NETPLAN_TASKS, "Disable cloud-init network configuration")
    remove = task_named(
        NETPLAN_TASKS,
        "Remove cloud-init network configuration disablement",
    )
    path = "/etc/cloud/cloud.cfg.d/99-disable-network-config.cfg"

    assert create["when"] == "ubuntu_netplan_disable_cloud_init_networking | bool"
    assert create["ansible.builtin.copy"]["dest"] == path
    assert remove["when"] == "not (ubuntu_netplan_disable_cloud_init_networking | bool)"
    assert remove["ansible.builtin.file"] == {"path": path, "state": "absent"}
    assert "notify" not in remove
    assert "tags" not in create
    assert "tags" not in remove


@pytest.mark.parametrize("enabled", [True, "true"])
def test_netplan_include_accepts_ansible_true_values(enabled):
    assert netplan_include_selected(enabled, "kvm") is True


@pytest.mark.parametrize("enabled", [False, "false"])
def test_netplan_include_rejects_ansible_false_values(enabled):
    assert netplan_include_selected(enabled, "kvm") is False


def test_netplan_include_excludes_lxc():
    assert netplan_include_selected(True, "lxc") is False


@pytest.mark.parametrize("virtualization_type", ["kvm", "qemu"])
def test_opentofu_inventory_tag_does_not_exclude_supported_vm(virtualization_type):
    task = task_named(MAIN_TASKS, "Ubuntu | Configure Netplan")
    conditions = " ".join(task["when"])

    assert netplan_include_selected(True, virtualization_type, opentofu_managed=True) is True
    assert "tags_opentofu_managed" not in conditions
    assert task["ansible.builtin.include_tasks"]["file"] == "sub_tasks/netplan.yml"
    assert set(task["ansible.builtin.include_tasks"]["apply"]["tags"]) == {
        "ubuntu",
        "ubuntu_netplan",
    }
    assert set(task["tags"]) == {"ubuntu", "ubuntu_netplan"}


def test_venv_detects_python_abi_drift_before_mutating_the_environment():
    determine = task_named(VENV_TASKS, "Determine controller Python ABI directory")
    interpreter = task_named(VENV_TASKS, "Check existing Ansible virtualenv interpreter")
    site_packages = task_named(VENV_TASKS, "Check matching Ansible virtualenv site-packages")
    probe = task_named(VENV_TASKS, "Probe existing Ansible virtualenv interpreter")
    recreate = task_named(VENV_TASKS, "Recreate Ansible virtualenv after Python ABI drift")

    assert (
        VENV_TASKS.index(determine)
        < VENV_TASKS.index(interpreter)
        < VENV_TASKS.index(site_packages)
        < VENV_TASKS.index(probe)
        < VENV_TASKS.index(recreate)
    )
    assert determine["changed_when"] is False
    assert determine["check_mode"] is False
    assert site_packages["ansible.builtin.stat"]["path"] == (
        "{{ ubuntu_ansible_venv_path }}/lib/{{ ubuntu_controller_python_abi.stdout | trim }}/site-packages"
    )
    assert probe["changed_when"] is False
    assert probe["failed_when"] is False
    assert probe["check_mode"] is False


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ({"python_exists": False, "controller_abi": "python3.14"}, "create"),
        (
            {
                "python_exists": True,
                "site_packages_exists": True,
                "probe_rc": 0,
                "probe_abi": "python3.14",
                "controller_abi": "python3.14",
            },
            "preserve",
        ),
        (
            {
                "python_exists": True,
                "site_packages_exists": True,
                "probe_rc": 126,
                "probe_abi": "",
                "controller_abi": "python3.14",
            },
            "recreate",
        ),
        (
            {
                "python_exists": True,
                "site_packages_exists": False,
                "probe_rc": 0,
                "probe_abi": "python3.14",
                "controller_abi": "python3.14",
            },
            "recreate",
        ),
        (
            {
                "python_exists": True,
                "site_packages_exists": True,
                "probe_rc": 0,
                "probe_abi": "python3.13",
                "controller_abi": "python3.14",
            },
            "recreate",
        ),
    ],
)
def test_venv_recovery_decision_covers_missing_compatible_and_drifted_states(status, expected):
    original = status.copy()

    assert ubuntu_venv.ubuntu_venv_recovery_action(status) == expected
    assert status == original


def test_venv_tasks_consume_recovery_decision_without_check_mode_mutation(tmp_path):
    recreate = task_named(VENV_TASKS, "Recreate Ansible virtualenv after Python ABI drift")
    create = task_named(VENV_TASKS, "Create missing Ansible virtualenv")
    pip = task_named(VENV_TASKS, "Upgrade pip tooling in virtualenv")
    fixture = tmp_path / "synthetic-venv"
    fixture.mkdir()
    marker = fixture / "preserved.txt"
    marker.write_text("synthetic fixture")
    before = {path.name: path.read_bytes() for path in fixture.iterdir()}

    action = ubuntu_venv.ubuntu_venv_recovery_action(
        {
            "python_exists": True,
            "site_packages_exists": False,
            "probe_rc": 0,
            "probe_abi": "python3.14",
            "controller_abi": "python3.14",
        }
    )

    assert action == "recreate"
    assert {path.name: path.read_bytes() for path in fixture.iterdir()} == before
    assert recreate["when"][0] == "not ansible_check_mode"
    assert create["when"][0] == "not ansible_check_mode"
    assert "ubuntu_venv_recovery_action" in recreate["when"][1]
    assert "ubuntu_venv_recovery_action" in create["when"][1]
    assert recreate["ansible.builtin.command"]["argv"] == [
        "python3",
        "-m",
        "venv",
        "--clear",
        "{{ ubuntu_ansible_venv_path }}",
    ]
    assert create["ansible.builtin.command"]["argv"] == [
        "python3",
        "-m",
        "venv",
        "{{ ubuntu_ansible_venv_path }}",
    ]
    pip_module = pip["ansible.builtin.pip"]
    packages = pip_module["name"]

    assert [package.split("==", 1)[0] for package in packages] == ["pip", "setuptools", "wheel"]
    assert all(package.count("==") == 1 and package.split("==", 1)[1] for package in packages)
    assert pip_module["state"] == "present"
    assert pip_module["virtualenv"] == "{{ ubuntu_ansible_venv_path }}"
    assert VENV_TASKS.index(recreate) < VENV_TASKS.index(create) < VENV_TASKS.index(pip)
