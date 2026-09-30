import importlib.util
import json
import re
from pathlib import Path

import yaml
from jinja2 import Environment, StrictUndefined
from jinja2.nativetypes import NativeEnvironment

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_DIR = REPO_ROOT / "ansible/group_vars/all/services"
PROMETHEUS_VARS_PATH = REPO_ROOT / "ansible/group_vars/all/prometheus.yml"
ALERTING_WORKFLOW_PATH = REPO_ROOT / ".github/workflows/alerting-config-validation.yml"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_services():
    services = {}
    for path in sorted(SERVICES_DIR.glob("*.yml")):
        services.update(yaml.safe_load(path.read_text()) or {})
    return services


def render_structure(value, variables):
    if isinstance(value, dict):
        return {key: render_structure(item, variables) for key, item in value.items()}
    if isinstance(value, list):
        return [render_structure(item, variables) for item in value]
    if isinstance(value, str) and ("{{" in value or "{%" in value):
        return NativeEnvironment(undefined=StrictUndefined).from_string(value).render(**variables)
    return value


def availability_model():
    availability = load_module(REPO_ROOT / "ansible/filter_plugins/availability.py", "availability_filters")
    catalog = load_module(REPO_ROOT / "ansible/filter_plugins/service_catalog.py", "availability_catalog")
    services = load_services()
    selected = catalog.service_catalog_effective(services, "mgt")
    host_names = ["dns01", "dns02", "dns03", "mgt", "unraid", "plex", "pve1", "pg95", "pg96", "pg97"]
    hostvars = {host: {"local_ip": f"192.0.2.{index}"} for index, host in enumerate(host_names, start=1)}
    variables = {
        "hostvars": hostvars,
        "services_controller_host": "mgt",
        "services_plex_host": "plex",
        "services_private_https_port": 8443,
        "services_internal_zone": "internal.example",
        "keepalived_instances": {
            "dns_vip_a": {"virtual_ip": "192.0.2.250"},
            "dns_vip_b": {"virtual_ip": "192.0.2.251"},
        },
    }
    prometheus_vars = render_structure(yaml.safe_load(PROMETHEUS_VARS_PATH.read_text()), variables)
    http = availability.availability_http_file_sd(
        services,
        selected,
        variables["services_internal_zone"],
        variables["services_private_https_port"],
        prometheus_vars["prometheus_availability_category_tags"],
        prometheus_vars["prometheus_availability_private_exclusions"],
        prometheus_vars["prometheus_availability_external_private_services"],
        prometheus_vars["prometheus_availability_http_overrides"],
    )
    http += availability.availability_direct_http_file_sd(prometheus_vars["prometheus_availability_direct_http_targets"])
    icmp = availability.availability_icmp_file_sd(hostvars, prometheus_vars["prometheus_availability_icmp_hosts"])
    tcp = availability.availability_tcp_file_sd(hostvars, prometheus_vars["prometheus_availability_tcp_targets"])
    postgres = availability.availability_postgres_file_sd(hostvars, ["pg95", "pg96", "pg97"])
    patroni = availability.availability_patroni_file_sd(hostvars, ["pg95", "pg96", "pg97"])
    return {"http": http, "icmp": icmp, "tcp": tcp, "postgres": postgres, "patroni": patroni, "vars": prometheus_vars}


def by_monitor_id(targets):
    return {target["labels"]["monitor_id"]: target for target in targets}


def test_generated_http_targets_cover_catalogue_and_direct_sources():
    model = availability_model()
    targets = by_monitor_id(model["http"])

    assert len(targets) == len(model["http"])
    assert {"http.homepage-private", "http.plex-direct", "http.proxmox"} <= set(targets)
    for excluded in model["vars"]["prometheus_availability_private_exclusions"]:
        assert f"http.{excluded}-private" not in targets


def test_catalogue_variants_special_urls_and_categories_are_preserved():
    targets = by_monitor_id(availability_model()["http"])
    for variant in (
        "radarr-4k",
        "sonarr-4k",
        "qbittorrent-alpha",
        "qbittorrent-bravo",
        "qui-alpha",
        "qui-bravo",
    ):
        assert f"http.{variant}-private" in targets

    assert targets["http.tautulli-private"]["targets"] == ["https://tautulli.internal.example:8443/status"]
    assert targets["http.tautulli-private"]["labels"]["module"] == "http_2xx_no_redirects"
    assert targets["http.plex-direct"]["targets"][0].endswith(":32400/identity")
    assert targets["http.plex-direct"]["labels"]["module"] == "http_2xx"
    assert targets["http.proxmox"]["targets"][0].endswith(":8006")
    assert targets["http.proxmox"]["labels"]["module"] == "http_private"
    assert targets["http.gitea-private"]["labels"]["category"] == "Media"
    assert targets["http.wallos-private"]["labels"]["category"] == "Finance"


def test_host_and_tcp_targets_come_from_inventory_and_prometheus_configuration():
    model = availability_model()
    expected_icmp = {f"ping.{name}" for name in model["vars"]["prometheus_availability_icmp_hosts"]}
    expected_tcp = {f"tcp.{name}" for name in model["vars"]["prometheus_availability_tcp_targets"]}
    expected_postgres_hosts = {"pg95", "pg96", "pg97"}

    assert set(by_monitor_id(model["icmp"])) == expected_icmp
    assert set(by_monitor_id(model["tcp"])) == expected_tcp
    assert {target["labels"]["host"] for target in model["postgres"]} == expected_postgres_hosts
    assert all(target["targets"][0].endswith(":9187") for target in model["postgres"])
    assert {target["labels"]["host"] for target in model["patroni"]} == expected_postgres_hosts
    assert all(target["targets"][0].endswith(":8008") for target in model["patroni"])


def test_labels_are_bounded_and_privacy_services_are_not_activity_targets():
    model = availability_model()
    allowed = {"service", "category", "probe_type", "host", "criticality", "module", "monitor_id"}
    all_targets = model["http"] + model["icmp"] + model["tcp"] + model["postgres"] + model["patroni"]
    assert all(set(target["labels"]) <= allowed for target in all_targets)
    serialized = json.dumps(all_targets).lower()
    assert "jdownloader" not in serialized
    assert "mullvad" not in serialized
    assert "filename" not in serialized
    assert "destination" not in serialized


def test_blackbox_modules_capability_and_prometheus_file_sd_wiring():
    blackbox_service = yaml.safe_load((SERVICES_DIR / "blackbox-exporter.yml").read_text())["blackbox_exporter"]
    assert blackbox_service["cap_add"] == ["NET_RAW"]
    assert blackbox_service.get("privileged") is not True

    env = Environment(undefined=StrictUndefined)
    env.filters["regex_escape"] = re.escape
    rendered = env.from_string(
        (REPO_ROOT / "ansible/roles/docker_services/templates/configs/prometheus/blackbox.yml.j2").read_text()
    ).render(
        prometheus_blackbox_dns_query_name="adminer.internal.example",
        prometheus_blackbox_dns_expected_a="192.0.2.1",
    )
    modules = yaml.safe_load(rendered)["modules"]
    assert set(modules) >= {"http_private", "http_2xx", "http_2xx_no_redirects", "icmp_ipv4", "tcp_connect"}
    assert modules["http_private"]["timeout"] == "30s"
    assert modules["http_private"]["http"]["valid_status_codes"] == [*range(200, 400), 401, 403]
    assert modules["http_2xx_no_redirects"]["http"]["follow_redirects"] is False

    prometheus_template = (REPO_ROOT / "ansible/roles/service_common/templates/configs/prometheus/prometheus.yml.j2").read_text()
    for job in ("blackbox-http", "blackbox-icmp", "blackbox-tcp", "postgres-exporter", "patroni"):
        assert f'job_name: "{job}"' in prometheus_template
    for target_file in ("blackbox-http.json", "blackbox-icmp.json", "blackbox-tcp.json", "postgres.json", "patroni.json"):
        assert f"/etc/prometheus/file_sd/{target_file}" in prometheus_template


def test_dns_coverage_includes_all_configured_endpoints():
    prometheus_vars = yaml.safe_load(PROMETHEUS_VARS_PATH.read_text())
    assert set(prometheus_vars["prometheus_blackbox_dns_targets"]) == {"dns_vip_a", "dns_vip_b", "dns01", "dns02", "dns03"}
    prometheus_template = (REPO_ROOT / "ansible/roles/service_common/templates/configs/prometheus/prometheus.yml.j2").read_text()
    assert 'job_name: "blackbox-dns-udp"' in prometheus_template
    assert 'job_name: "blackbox-dns-tcp"' in prometheus_template


def test_postgres_exporter_role_is_checksum_pinned_unprivileged_and_secret_safe():
    defaults = yaml.safe_load((REPO_ROOT / "ansible/roles/postgres_exporter/defaults/main.yml").read_text())
    tasks = yaml.safe_load((REPO_ROOT / "ansible/roles/postgres_exporter/tasks/main.yml").read_text())
    unit = (REPO_ROOT / "ansible/roles/postgres_exporter/templates/postgres_exporter.service.j2").read_text()
    environment = (REPO_ROOT / "ansible/roles/postgres_exporter/templates/environment.j2").read_text()
    playbook = yaml.safe_load((REPO_ROOT / "ansible/playbook.yml").read_text())

    assert defaults["postgres_exporter_version"] == "0.20.1"
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", defaults["postgres_exporter_checksum"])
    password_task = next(task for task in tasks if task["name"].endswith("Install protected password file"))
    assert password_task["ansible.builtin.template"]["mode"] == "0640"
    assert password_task["no_log"] is True
    assert password_task["diff"] is False
    assert "User={{ postgres_exporter_user }}" in unit
    assert "--web.listen-address={{ postgres_exporter_listen_address }}" in unit
    assert "password" not in unit.lower()
    assert "DATA_SOURCE_PASS_FILE=" in environment
    assert "postgres_exporter_database_password" not in environment
    assert any("postgres_exporter" in str(task) and "tags_postgres" in str(task) for play in playbook for task in play.get("tasks", []))
    monitor_tasks = (REPO_ROOT / "ansible/roles/postgres/tasks/sub_tasks/admin/pg_monitor.yml").read_text()
    postgres_defaults = yaml.safe_load((REPO_ROOT / "ansible/roles/postgres/defaults/main.yml").read_text())
    postgres_group_vars = yaml.safe_load((REPO_ROOT / "ansible/group_vars/tags_postgres.yml").read_text())
    postgres_vault_sample = yaml.safe_load((REPO_ROOT / "ansible/group_vars/all/vault.sample/postgres.yml").read_text())
    assert postgres_defaults["postgres_monitor_role_name"] == "postgres_monitor"
    assert postgres_defaults["postgres_monitor_role_pass"] == ""
    assert postgres_defaults["postgres_monitor_database"] == "postgres"
    assert postgres_group_vars["postgres_monitor_role_name"] == "postgres_monitor"
    assert postgres_group_vars["postgres_monitor_database"] == "postgres"
    assert postgres_vault_sample["postgres_monitor_role_pass"] == "replace-me"
    assert "INHERIT" in monitor_tasks
    assert "NOINHERIT" not in monitor_tasks
    skynet = (REPO_ROOT / "ansible/roles/ubuntu/templates/skynet.j2").read_text()
    assert 'postgres:admin-monitor)         echo "postgres_admin_monitor"' in skynet
    assert 'postgres-exporter:deploy)       echo "postgres_exporter"' in skynet


def test_alerting_validator_workflow_uses_repository_ansible_core_constraint():
    workflow_text = ALERTING_WORKFLOW_PATH.read_text()
    requirements = (REPO_ROOT / "ansible/requirements.txt").read_text().splitlines()
    ansible_core_pin = next(line for line in requirements if line.startswith("ansible-core=="))

    assert ansible_core_pin == "ansible-core==2.21.4"
    assert yaml.safe_load(workflow_text)
    assert "--constraint ansible/requirements.txt" in workflow_text
    assert "ansible-core jinja2 pyyaml" in workflow_text
    assert "ansible-core==2.21.4" not in workflow_text
    assert workflow_text.count("      - ansible/requirements.txt") == 2
    assert workflow_text.count("      - ansible/filter_plugins/availability.py") == 2
    assert workflow_text.count("      - ansible/filter_plugins/service_catalog.py") == 2


def test_alertmanager_keeps_email_adds_secret_file_gotify_and_valid_payload_shape():
    service = yaml.safe_load((SERVICES_DIR / "alertmanager.yml").read_text())["alertmanager"]
    declaration = next(item for item in service["infisical"]["secrets_map"] if item["var"] == "gotify_alertmanager_token")
    assert declaration["secret"]["name"] == "alertmanager_gotify_token_secret"

    rendered = (
        Environment(undefined=StrictUndefined)
        .from_string((REPO_ROOT / "ansible/roles/service_common/templates/configs/alertmanager.yml.j2").read_text())
        .render(
            service_common_infisical_values={
                "smtp_email": "alerts@example.com",
                "smtp_host": "smtp.example.com",
                "smtp_port": "587",
                "smtp_username": "alertmanager@example.com",
            }
        )
    )
    config = yaml.safe_load(rendered)
    assert config["inhibit_rules"][0]["equal"] == ["alertname", "instance", "application_name", "slot_name"]
    receiver = config["receivers"][0]
    webhook = receiver["webhook_configs"][0]
    assert receiver["email_configs"][0]["send_resolved"] is True
    assert webhook["send_resolved"] is True
    assert webhook["url"] == "http://gotify/message"
    assert webhook["http_config"]["authorization"] == {
        "type": "Bearer",
        "credentials_file": "/run/secrets/alertmanager_gotify_token_secret",
    }
    assert webhook["payload"]["priority"] == 8
    assert set(webhook["payload"]) == {"title", "message", "priority"}
    assert "gotify_alertmanager_token" not in rendered
    assert "ALERTMANAGER_APP_TOKEN" not in rendered


def test_availability_dashboard_renders_valid_json_and_queries_generated_labels():
    path = REPO_ROOT / "ansible/roles/service_common/templates/configs/grafana/dashboards/homelab-availability.json.j2"
    rendered = Environment(undefined=StrictUndefined).from_string(path.read_text()).render()
    dashboard = json.loads(rendered)
    assert dashboard["uid"] == "homelab-availability"
    assert dashboard["title"] == "Homelab Availability"
    assert dashboard["templating"]["list"][1]["query"].split(",") == [
        "Infrastructure",
        "Networking",
        "Monitoring",
        "ARRs",
        "Torrents",
        "Usenet",
        "Plex",
        "Media",
        "Gaming",
        "Finance",
        "Network",
        "Utilities",
    ]
    expressions = "\n".join(target["expr"] for panel in dashboard["panels"] for target in panel.get("targets", []))
    assert "probe_success" in expressions
    assert "probe_http_status_code" in expressions
    assert "probe_duration_seconds" in expressions
    assert "probe_ssl_earliest_cert_expiry" in expressions
    assert "pg_up" in expressions
    assert 'category=~"$category"' in expressions
