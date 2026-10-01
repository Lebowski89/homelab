import importlib.util
import json
import re
from pathlib import Path

import pytest
import yaml
from ansible.errors import AnsibleFilterError
from jinja2 import Environment, StrictUndefined

REPO_ROOT = Path(__file__).resolve().parents[2]
POSTGRES_ROLE = REPO_ROOT / "ansible/roles/postgres"
FILTER_PATH = POSTGRES_ROLE / "filter_plugins/patroni.py"
PATRONI_TEMPLATE_PATH = POSTGRES_ROLE / "templates/patroni.yml.j2"
MAIN_TASKS_PATH = POSTGRES_ROLE / "tasks/main.yml"
RECONCILE_TASKS_PATH = POSTGRES_ROLE / "tasks/sub_tasks/admin/replication_safety.yml"
SKYNET_TEMPLATE_PATH = REPO_ROOT / "ansible/roles/ubuntu/templates/skynet.j2"
SKYNET_DOC_PATH = REPO_ROOT / "docs/cheat_sheets/skynet.md"
RULES_PATH = REPO_ROOT / "ansible/roles/service_common/templates/configs/prometheus/rules/availability.yml.j2"
DASHBOARD_PATH = REPO_ROOT / "ansible/roles/service_common/templates/configs/grafana/dashboards/homelab-availability.json.j2"

# postgres_exporter v0.20.1 collector/pg_replication_slots.go native labels,
# plus the stable scrape labels added by this repository.
POSTGRES_EXPORTER_V0201_SELECTOR_LABELS = {
    "pg_replication_slots_pg_wal_lsn_diff": {"database", "host", "instance", "job", "slot_name"},
    "pg_replication_slots_safe_wal_size_bytes": {"host", "instance", "job", "slot_name", "slot_type"},
}


def metric_selector_labels(expression: str, metric: str) -> list[set[str]]:
    selectors = re.findall(rf"{re.escape(metric)}\{{([^}}]*)\}}", expression)
    return [set(re.findall(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:=~|!~|!=|=)", selector)) for selector in selectors]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PATRONI = load_module(FILTER_PATH, "patroni_replication_safety_filters")


def task_named(tasks, name):
    return next(task for task in tasks if task.get("name") == name)


def test_permanent_member_slots_are_deterministic_physical_and_preserve_declared_extras():
    slots = PATRONI.postgres_patroni_permanent_slots(
        ["pg97", "pg95", "pg96", "pg95"],
        {"archive_slot": {"type": "physical"}},
    )

    assert list(slots) == ["archive_slot", "pg95", "pg96", "pg97"]
    assert all(slots[host] == {"type": "physical"} for host in ("pg95", "pg96", "pg97"))
    assert slots["archive_slot"] == {"type": "physical"}


def test_extra_slots_cannot_ambiguously_override_inventory_member_slots():
    with pytest.raises(AnsibleFilterError, match="collide"):
        PATRONI.postgres_patroni_permanent_slots(["pg95"], {"pg95": {"type": "logical"}})


def test_replication_safety_patch_is_idempotent_minimal_and_uses_top_level_slots():
    slots = PATRONI.postgres_patroni_permanent_slots(["pg95", "pg96", "pg97"])
    current = {
        "ttl": 30,
        "primary_start_timeout": 60,
        "loop_wait": 10,
        "slots": slots,
        "postgresql": {
            "use_slots": True,
            "parameters": {
                "shared_buffers": "1GB",
                "wal_keep_size": "1GB",
                "max_slot_wal_keep_size": "16GB",
            },
        },
    }

    assert PATRONI.postgres_patroni_replication_safety_patch(current, slots, 60, "1GB", "16GB") == {}

    drifted = yaml.safe_load(yaml.safe_dump(current))
    drifted["slots"].pop("pg97")
    drifted["primary_start_timeout"] = 300
    drifted["postgresql"]["parameters"]["max_slot_wal_keep_size"] = "-1"
    patch = PATRONI.postgres_patroni_replication_safety_patch(drifted, slots, 60, "1GB", "16GB")

    assert patch == {
        "primary_start_timeout": 60,
        "postgresql": {"parameters": {"max_slot_wal_keep_size": "16GB"}},
        "slots": {"pg97": {"type": "physical"}},
    }
    assert "slots" not in patch["postgresql"]
    assert "ttl" not in patch
    assert "loop_wait" not in patch
    assert "shared_buffers" not in json.dumps(patch)


def test_replication_safety_patch_adds_complete_top_level_shape_and_removes_stale_slots():
    slots = PATRONI.postgres_patroni_permanent_slots(["pg95", "pg96", "pg97"])
    current = {
        "ttl": 30,
        "slots": {"obsolete_slot": {"type": "physical"}},
        "postgresql": {
            "parameters": {"shared_buffers": "1GB"},
        },
    }

    patch = PATRONI.postgres_patroni_replication_safety_patch(current, slots, 60, "1GB", "16GB")

    assert patch == {
        "primary_start_timeout": 60,
        "postgresql": {
            "use_slots": True,
            "parameters": {
                "wal_keep_size": "1GB",
                "max_slot_wal_keep_size": "16GB",
            },
        },
        "slots": {
            "obsolete_slot": None,
            "pg95": {"type": "physical"},
            "pg96": {"type": "physical"},
            "pg97": {"type": "physical"},
        },
    }
    assert "slots" not in patch["postgresql"]
    assert "ttl" not in patch
    assert "shared_buffers" not in json.dumps(patch)


@pytest.mark.parametrize("invalid_timeout", [0, -1, False, "60"])
def test_primary_start_timeout_must_be_a_positive_integer(invalid_timeout):
    slots = PATRONI.postgres_patroni_permanent_slots(["pg95"])

    with pytest.raises(AnsibleFilterError, match="positive integer"):
        PATRONI.postgres_patroni_replication_safety_patch({}, slots, invalid_timeout, "1GB", "16GB")


def test_nested_postgresql_slots_do_not_satisfy_top_level_slots_comparison():
    slots = PATRONI.postgres_patroni_permanent_slots(["pg95", "pg96", "pg97"])
    wrongly_nested = {
        "postgresql": {
            "use_slots": True,
            "slots": slots,
            "parameters": {
                "wal_keep_size": "1GB",
                "max_slot_wal_keep_size": "16GB",
            },
        }
    }

    patch = PATRONI.postgres_patroni_replication_safety_patch(wrongly_nested, slots, 60, "1GB", "16GB")

    assert patch == {"primary_start_timeout": 60, "slots": slots}
    assert "postgresql" not in patch


def test_new_cluster_template_contains_same_slots_and_retention_as_dynamic_desired_state():
    slots = PATRONI.postgres_patroni_permanent_slots(["pg97", "pg95", "pg96"])
    env = Environment(undefined=StrictUndefined)
    rendered = env.from_string(PATRONI_TEMPLATE_PATH.read_text()).render(
        postgres_patroni_scope="pg-cluster",
        postgres_patroni_namespace="/service",
        postgres_patroni_node_name="pg95",
        postgres_patroni_restapi_port=8008,
        local_ip="192.0.2.95",
        postgres_patroni_etcd_hosts=["192.0.2.95:2379"],
        postgres_patroni_permanent_slots=slots,
        postgres_patroni_replication_name="replicator",
        postgres_patroni_superuser_name="postgres",
        postgres_patroni_admin_role_name="admin",
        postgres_patroni_pg_hba_extra=[],
        postgres_patroni_primary_start_timeout=60,
        postgres_patroni_wal_keep_size="1GB",
        postgres_patroni_max_slot_wal_keep_size="16GB",
        postgres_patroni_postgres_port=5432,
        postgres_patroni_data_dir="/var/lib/postgresql/18/main",
        postgres_patroni_bin_dir="/usr/lib/postgresql/18/bin",
        postgres_patroni_superuser_pass="FAKE_SUPERUSER_PASSWORD",
        postgres_patroni_replication_pass="FAKE_REPLICATION_PASSWORD",
        groups={"tags_postgres": ["pg97", "pg95", "pg96"], "tags_haproxy": []},
        hostvars={
            "pg95": {"local_ip": "192.0.2.95"},
            "pg96": {"local_ip": "192.0.2.96"},
            "pg97": {"local_ip": "192.0.2.97"},
        },
    )
    config = yaml.safe_load(rendered)
    bootstrap_dcs = config["bootstrap"]["dcs"]
    bootstrap_postgresql = bootstrap_dcs["postgresql"]

    assert bootstrap_dcs["slots"] == slots
    assert bootstrap_dcs["primary_start_timeout"] == 60
    assert "primary_start_timeout" not in bootstrap_postgresql
    assert "slots" not in bootstrap_postgresql
    assert bootstrap_postgresql["use_slots"] is True
    assert bootstrap_postgresql["parameters"]["wal_keep_size"] == "1GB"
    assert bootstrap_postgresql["parameters"]["max_slot_wal_keep_size"] == "16GB"
    assert config["postgresql"]["parameters"]["wal_keep_size"] == "1GB"
    assert config["postgresql"]["parameters"]["max_slot_wal_keep_size"] == "16GB"


def test_dynamic_reconciliation_patches_only_drift_and_never_restarts_or_resets():
    tasks = yaml.safe_load(RECONCILE_TASKS_PATH.read_text())
    patch = task_named(tasks, "Patroni replication safety | Patch dynamic configuration when drifted")
    verify = task_named(tasks, "Patroni replication safety | Verify effective dynamic configuration")
    task_text = RECONCILE_TASKS_PATH.read_text()

    assert patch["ansible.builtin.uri"]["method"] == "PATCH"
    assert patch["ansible.builtin.uri"]["body_format"] == "json"
    assert patch["ansible.builtin.uri"]["body"] == "{{ postgres_patroni_replication_safety_patch }}"
    assert patch["when"] == "postgres_patroni_replication_safety_patch | length > 0"
    assert patch["changed_when"] == "postgres_patroni_replication_safety_patch | length > 0"
    assert verify["ansible.builtin.uri"]["method"] == "GET"
    assert "postgres_patroni_replication_safety_patch" in verify["until"]
    assert "ansible.builtin.service" not in task_text
    assert "ansible.builtin.systemd" not in task_text
    assert "postgres_patroni_reset" not in task_text
    assert "postgres_admin_nuke_node" not in task_text


def test_dynamic_reconciliation_discovers_a_consistent_leader_across_sorted_members():
    tasks = yaml.safe_load(RECONCILE_TASKS_PATH.read_text())
    query = task_named(tasks, "Patroni replication safety | Query cluster state from sorted PostgreSQL members")
    retain = task_named(tasks, "Patroni replication safety | Retain usable cluster states")
    consistency = task_named(tasks, "Patroni replication safety | Assert cluster discovery is consistent")
    task_text = RECONCILE_TASKS_PATH.read_text()

    assert query["loop"] == '{{ groups["tags_postgres"] | sort }}'
    assert query["loop_control"]["loop_var"] == "postgres_patroni_replication_safety_candidate"
    assert "postgres_patroni_replication_safety_candidate" in query["ansible.builtin.uri"]["url"]
    assert "| first" not in query["ansible.builtin.uri"]["url"]
    assert query["failed_when"] is False
    assert query["changed_when"] is False
    assert query["run_once"] is True
    assert any("status | default(0) == 200" in condition for condition in retain["when"])
    assert any("reported_leaders | length == 1" in condition for condition in consistency["ansible.builtin.assert"]["that"])
    assert "groups['tags_postgres'] | sort | first" not in task_text


def test_check_mode_and_skynet_action_are_safe_and_wired():
    tasks = yaml.safe_load(MAIN_TASKS_PATH.read_text())
    include = task_named(tasks, "Reconcile Patroni replication-safety dynamic configuration")
    plan = task_named(tasks, "Report Patroni replication-safety check-mode plan")
    tag = "postgres_admin_update_replication_safety"
    skynet = SKYNET_TEMPLATE_PATH.read_text()

    assert "not ansible_check_mode" in include["when"]
    assert "ansible_check_mode" in plan["when"]
    assert plan["changed_when"] is False
    assert tag in include["tags"]
    assert f'postgres:admin-update-replication-safety) echo "{tag}"' in skynet
    assert "admin-update-replication-safety" in SKYNET_DOC_PATH.read_text()
    mapping_line = next(line for line in skynet.splitlines() if "postgres:admin-update-replication-safety)" in line)
    assert "reset" not in mapping_line
    assert "nuke" not in mapping_line


def test_replication_alerts_use_observed_metrics_and_leader_aware_slot_queries():
    rendered = (
        Environment(undefined=StrictUndefined)
        .from_string(RULES_PATH.read_text())
        .render(groups={"tags_postgres": ["pg97", "pg95", "pg96"]})
    )
    rules = yaml.safe_load(rendered)["groups"][0]["rules"]
    expressions = {rule["alert"]: [] for rule in rules}
    for rule in rules:
        expressions.setdefault(rule["alert"], []).append(rule["expr"])

    assert "pg_up" in expressions["PostgresQueryUnavailable"][0]
    assert "pg_scrape_collector_success" in expressions["PostgresReplicationCollectorFailed"][0]
    assert "patroni_postgres_streaming" in "\n".join(expressions["PatroniMemberUnhealthy"])
    assert "pg_stat_replication_pg_wal_lsn_diff" in "\n".join(expressions["PostgresReplicationLagHigh"])
    assert all(
        "patroni_primary" in expr
        and 'up{job="postgres-exporter"}' in expr
        and "pg_scrape_collector_success" in expr
        and "unless on(host)" in expr
        for expr in expressions["PostgresRequiredPhysicalSlotInactive"]
    )
    assert all(
        "pg_replication_slots_safe_wal_size_bytes" in expr and 'slot_type="physical"' in expr and "patroni_primary" in expr
        for expr in expressions["PostgresSlotWalHeadroomLow"]
    )
    assert 'wal_status=~"unreserved|lost"' in expressions["PostgresPhysicalSlotWalUnavailable"][0]
    assert len(expressions["PostgresRequiredPhysicalSlotInactive"]) == 3


def test_wal_headroom_rules_match_postgres_exporter_v0201_metric_labels():
    rendered = (
        Environment(undefined=StrictUndefined)
        .from_string(RULES_PATH.read_text())
        .render(groups={"tags_postgres": ["pg97", "pg95", "pg96"]})
    )
    rules = yaml.safe_load(rendered)["groups"][0]["rules"]
    headroom_rules = [rule for rule in rules if rule["alert"] == "PostgresSlotWalHeadroomLow"]

    assert [(rule["labels"]["severity"], rule["for"]) for rule in headroom_rules] == [
        ("warning", "15m"),
        ("critical", "5m"),
    ]
    expected_thresholds = {"warning": "4294967296", "critical": "1073741824"}
    for rule in headroom_rules:
        expression = rule["expr"]
        assert "pg_replication_slots_safe_wal_size_bytes" in expression
        assert expected_thresholds[rule["labels"]["severity"]] in expression
        assert 'slot_type="physical"' in expression
        assert 'patroni_primary{job="patroni"} == 1' in expression
        assert "pg_replication_slots_pg_wal_lsn_diff" not in expression
        assert "pg_settings_max_slot_wal_keep_size_bytes" not in expression

    all_expressions = "\n".join(rule["expr"] for rule in rules)
    for metric, allowed_labels in POSTGRES_EXPORTER_V0201_SELECTOR_LABELS.items():
        for selected_labels in metric_selector_labels(all_expressions, metric):
            assert selected_labels <= allowed_labels


def test_required_slot_alert_excludes_current_leaders_own_permanent_slot():
    rendered = (
        Environment(undefined=StrictUndefined)
        .from_string(RULES_PATH.read_text())
        .render(groups={"tags_postgres": ["pg97", "pg95", "pg96"]})
    )
    rules = yaml.safe_load(rendered)["groups"][0]["rules"]
    slot_rules = {rule["labels"]["slot_name"]: rule for rule in rules if rule["alert"] == "PostgresRequiredPhysicalSlotInactive"}

    assert set(slot_rules) == {"pg95", "pg96", "pg97"}
    for member, rule in slot_rules.items():
        expression = rule["expr"]
        # Patroni does not create a permanent physical slot on the node whose
        # name matches that slot. Excluding the current primary by name makes
        # its own missing slot incapable of producing the alert vector.
        assert f'patroni_primary{{job="patroni", name!="{member}"}} == 1' in expression
        assert f'slot_name="{member}"' in expression


def test_dashboard_replication_section_uses_health_only_in_current_state_panel():
    rendered = Environment(undefined=StrictUndefined).from_string(DASHBOARD_PATH.read_text()).render()
    dashboard = json.loads(rendered)
    panels = {panel["id"]: panel for panel in dashboard["panels"]}
    current_state_expression = panels[7]["targets"][0]["expr"]

    assert len(panels[7]["targets"]) == 1
    assert "probe_duration_seconds" not in current_state_expression
    assert "probe_http_status_code" not in current_state_expression
    assert "probe_success" in current_state_expression
    assert "pg_up" in current_state_expression
    assert "patroni_postgres_state" in current_state_expression
    assert panels[11]["title"] == "PostgreSQL replication safety"
    firing_expression = panels[5]["targets"][0]["expr"]
    assert 'alertname=~"Blackbox.*|Postgres.*|Patroni.*"' in firing_expression

    headroom_targets = {target["refId"]: target for target in panels[15]["targets"]}
    retained_expression = headroom_targets["A"]["expr"]
    safe_expression = headroom_targets["B"]["expr"]
    assert "pg_replication_slots_pg_wal_lsn_diff" in retained_expression
    assert "and on(host, slot_name)" in retained_expression
    assert "pg_replication_slots_slot_is_active" in retained_expression
    assert 'slot_type="physical"' in retained_expression
    assert "pg_replication_slots_safe_wal_size_bytes" in safe_expression
    assert 'slot_type="physical"' in safe_expression
    assert "patroni_primary" in safe_expression
    assert "clamp_min" not in safe_expression
    assert "pg_settings_max_slot_wal_keep_size_bytes" not in safe_expression
    assert "safe_wal_size" in panels[15]["description"]

    for metric, allowed_labels in POSTGRES_EXPORTER_V0201_SELECTOR_LABELS.items():
        for selected_labels in metric_selector_labels(retained_expression + "\n" + safe_expression, metric):
            assert selected_labels <= allowed_labels

    replication_queries = "\n".join(target["expr"] for panel_id in range(12, 18) for target in panels[panel_id].get("targets", []))
    for metric in (
        "patroni_primary",
        "patroni_postgres_streaming",
        "pg_stat_replication_pg_wal_lsn_diff",
        "pg_replication_slots_slot_is_active",
        "pg_replication_slots_wal_status",
        "pg_replication_slots_safe_wal_size_bytes",
        "patroni_xlog_location",
    ):
        assert metric in replication_queries
