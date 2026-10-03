import re
from pathlib import Path

import yaml
from jinja2 import Environment, StrictUndefined

REPO_ROOT = Path(__file__).resolve().parents[2]
NODE_RULES_PATH = REPO_ROOT / "ansible/roles/service_common/templates/configs/prometheus/rules/node-exporter.yml.j2"
HAPROXY_TEMPLATE_PATH = REPO_ROOT / "ansible/roles/docker_services/templates/configs/haproxy.cfg.j2"
UBUNTU_DEFAULTS_PATH = REPO_ROOT / "ansible/roles/ubuntu/defaults/main.yml"
UBUNTU_TASKS_PATH = REPO_ROOT / "ansible/roles/ubuntu/tasks/main.yml"
SWAP_TASKS_PATH = REPO_ROOT / "ansible/roles/ubuntu/tasks/sub_tasks/postgres_emergency_swap.yml"
POSTGRES_VARS_PATH = REPO_ROOT / "ansible/group_vars/tags_postgres.yml"
POSTGRES_TFVARS_SAMPLE_PATH = REPO_ROOT / "terraform/proxmox/vms/postgres-cluster/private.auto.tfvars.sample"
SKYNET_TEMPLATE_PATH = REPO_ROOT / "ansible/roles/ubuntu/templates/skynet.j2"


def task_named(tasks, name):
    return next(task for task in tasks if task.get("name") == name)


def test_node_memory_pressure_and_kernel_oom_alerts_are_host_wide_and_actionable():
    rendered = Environment(undefined=StrictUndefined).from_string(NODE_RULES_PATH.read_text()).render()
    rules = {rule["alert"]: rule for rule in yaml.safe_load(rendered)["groups"][0]["rules"]}

    warning = rules["HostMemoryHigh"]
    critical = rules["HostMemoryCritical"]
    oom = rules["HostKernelOomKill"]

    for rule in (warning, critical):
        assert 'node_memory_MemAvailable_bytes{job="node-exporter"}' in rule["expr"]
        assert 'node_memory_MemTotal_bytes{job="node-exporter"}' in rule["expr"]
        assert "MemFree" not in rule["expr"]

    assert warning["labels"]["severity"] == "warning"
    assert warning["for"] == "15m"
    assert "< 20" in warning["expr"]
    assert critical["labels"]["severity"] == "critical"
    assert critical["for"] == "5m"
    assert "< 10" in critical["expr"]
    assert oom["expr"] == 'increase(node_vmstat_oom_kill{job="node-exporter"}[5m]) > 0'
    assert oom["labels"]["severity"] == "critical"
    assert "kernel OOM killer has killed one or more processes" in oom["annotations"]["description"]
    assert "database failure" in oom["annotations"]["description"]


def test_haproxy_postgres_backends_start_fully_down_until_primary_checks_pass():
    rendered = (
        Environment(undefined=StrictUndefined)
        .from_string(HAPROXY_TEMPLATE_PATH.read_text())
        .render(
            docker_services_svc={"settings": {}},
            postgres_patroni_restapi_port=8008,
            postgres_patroni_postgres_port=5432,
            groups={"tags_postgres": ["pg95", "pg96", "pg97"]},
            hostvars={
                "pg95": {"local_ip": "192.0.2.95"},
                "pg96": {"local_ip": "192.0.2.96"},
                "pg97": {"local_ip": "192.0.2.97"},
            },
        )
    )
    backend = rendered.split("backend pg_primary", maxsplit=1)[1]

    assert "GET /primary HTTP/1.1" in backend
    assert "tcp-check expect rstring ^HTTP/1\\.[01][[:space:]]+200" in backend
    assert "default-server inter 2s fall 3 rise 2 init-state fully-down on-marked-down shutdown-sessions" in backend
    assert backend.index("init-state fully-down") < backend.index("server pg95")


def test_postgres_emergency_swap_is_scoped_idempotent_and_check_mode_safe():
    defaults = yaml.safe_load(UBUNTU_DEFAULTS_PATH.read_text())
    postgres_vars = yaml.safe_load(POSTGRES_VARS_PATH.read_text())
    role_tasks = yaml.safe_load(UBUNTU_TASKS_PATH.read_text())
    swap_tasks = yaml.safe_load(SWAP_TASKS_PATH.read_text())

    include = task_named(role_tasks, "Ubuntu | Configure PostgreSQL emergency swap")
    active = task_named(swap_tasks, "PostgreSQL emergency swap | Discover active swap sources")
    persistent = task_named(swap_tasks, "PostgreSQL emergency swap | Discover persistent swap sources")
    preserve = task_named(swap_tasks, "PostgreSQL emergency swap | Preserve administrator-provided swap")
    reconcile = task_named(swap_tasks, "PostgreSQL emergency swap | Reconcile managed swap file")
    nested = {task["name"]: task for task in reconcile["block"]}
    rescue = task_named(reconcile["rescue"], "PostgreSQL emergency swap | Stop after reconciliation failure")

    assert defaults["ubuntu_postgres_emergency_swap_enabled"] is False
    assert postgres_vars["ubuntu_postgres_emergency_swap_enabled"] is True
    assert postgres_vars["ubuntu_postgres_emergency_swap_size_mb"] == 2048
    assert defaults["ubuntu_sysctl_settings"]["vm.swappiness"] == 10
    assert "'tags_postgres' in group_names" in include["when"]
    assert "ubuntu_postgres_swap" in include["tags"]
    assert active["check_mode"] is False and active["changed_when"] is False
    assert persistent["check_mode"] is False and persistent["changed_when"] is False
    assert "alternate_sources | length > 0" in preserve["when"]
    assert "alternate_sources | length == 0" in reconcile["when"]
    assert nested["PostgreSQL emergency swap | Allocate managed file"]["ansible.builtin.command"]["creates"]
    assert nested["PostgreSQL emergency swap | Protect managed file"]["ansible.builtin.file"]["mode"] == "0600"
    assert "not ansible_check_mode" in nested["PostgreSQL emergency swap | Format newly allocated file"]["when"]
    assert nested["PostgreSQL emergency swap | Persist managed file"]["ansible.builtin.lineinfile"]["path"] == "/etc/fstab"
    assert "not ansible_check_mode" in nested["PostgreSQL emergency swap | Activate managed file"]["when"]
    assert "ansible.builtin.fail" in rescue


def test_postgres_emergency_swap_has_friendly_skynet_mapping():
    skynet = SKYNET_TEMPLATE_PATH.read_text()

    assert 'ubuntu:postgres-swap)           echo "ubuntu_postgres_swap"' in skynet
    assert "postgres-swap -> ubuntu_postgres_swap" in skynet


def test_postgres_proxmox_vm_definitions_use_four_gib_each():
    tfvars = POSTGRES_TFVARS_SAMPLE_PATH.read_text()

    for host in ("pg95", "pg96", "pg97"):
        match = re.search(r"^  " + re.escape(host) + r" = {(?P<body>.*?)^  }", tfvars, flags=re.MULTILINE | re.DOTALL)
        assert match is not None
        memory = re.search(r"^    memory\s*=\s*(\d+)$", match.group("body"), flags=re.MULTILINE)
        assert memory is not None
        assert int(memory.group(1)) == 4096
