import importlib.util
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMON_PREPARE_PATH = REPO_ROOT / "ansible/roles/service_common/tasks/prepare.yml"
COMMON_POSTGRES_PATH = REPO_ROOT / "ansible/roles/service_common/tasks/postgres.yml"
DOCKER_PREP_PATH = REPO_ROOT / "ansible/roles/docker_services/tasks/sub_tasks/prepare.yml"
DOCKER_INIT_PATH = REPO_ROOT / "ansible/roles/docker_services/tasks/sub_tasks/init.yml"
DOCKER_SECRET_TASKS_PATH = REPO_ROOT / "ansible/roles/docker_services/tasks/sub_tasks/secrets/manage.yml"
DOCKER_POSTGRES_PATH = REPO_ROOT / "ansible/roles/docker_services/tasks/sub_tasks/prep/postgres.yml"
COMMON_PREFLIGHT_PATH = REPO_ROOT / "ansible/tasks/service_catalog_common_preflight.yml"
PODMAN_MAIN_PATH = REPO_ROOT / "ansible/roles/podman_services/tasks/main.yml"
PODMAN_INIT_PATH = REPO_ROOT / "ansible/roles/podman_services/tasks/sub_tasks/init.yml"
PODMAN_PREP_PATH = REPO_ROOT / "ansible/roles/podman_services/tasks/sub_tasks/quadlets.yml"
PODMAN_SECRET_TASKS_PATH = REPO_ROOT / "ansible/roles/podman_services/tasks/sub_tasks/secrets/manage.yml"
SERVICES_DIR = REPO_ROOT / "ansible/group_vars/all/services"
SERVICE_CATALOG_PATH = REPO_ROOT / "ansible/filter_plugins/service_catalog.py"

COMMON_PREPARE = COMMON_PREPARE_PATH.read_text()
COMMON_POSTGRES = COMMON_POSTGRES_PATH.read_text()
DOCKER_PREP = DOCKER_PREP_PATH.read_text()
DOCKER_INIT = DOCKER_INIT_PATH.read_text()
DOCKER_SECRET_TASKS = DOCKER_SECRET_TASKS_PATH.read_text()
COMMON_PREFLIGHT = COMMON_PREFLIGHT_PATH.read_text()
PODMAN_MAIN = PODMAN_MAIN_PATH.read_text()
PODMAN_INIT = PODMAN_INIT_PATH.read_text()
PODMAN_PREP = PODMAN_PREP_PATH.read_text()
PODMAN_SECRET_TASKS = PODMAN_SECRET_TASKS_PATH.read_text()

EXPECTED_TAGS = {"deploy", "update", "recreate", "bootstrap"}


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SERVICE_CATALOG = load_module(SERVICE_CATALOG_PATH, "service_catalog_postgres_audit")


def task_named(tasks, name):
    return next(task for task in tasks if task["name"] == name)


def walk_mappings(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_mappings(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_mappings(child)


def materialized_secret_names(service):
    names = set()
    for mapping in walk_mappings(service):
        infisical = mapping.get("infisical")
        if not isinstance(infisical, dict):
            continue
        for entry in infisical.get("secrets_map", []):
            if not isinstance(entry, dict):
                continue
            if isinstance(entry.get("docker_secret"), str):
                names.add(entry["docker_secret"])
            secret = entry.get("secret")
            if isinstance(secret, dict) and isinstance(secret.get("name"), str):
                names.add(secret["name"])
    return names


def effective_service_configs(services):
    effective = SERVICE_CATALOG.service_catalog_effective(services, "manager")
    for item in effective:
        yield (
            item["name"],
            item.get("target", "<base>"),
            SERVICE_CATALOG.service_catalog_merge_target(services[item["name"]], item.get("target")),
        )


def assert_postgres_credentials_declared(services):
    failures = []
    for service_name, target_name, service in effective_service_configs(services):
        postgres = service.get("postgres")
        if not isinstance(postgres, dict) or postgres.get("enable") is not True:
            continue

        user_var = postgres.get("user_var", "postgres_user")
        password_var = postgres.get("password_var", "postgres_pass")
        infisical = service.get("infisical", {})
        secrets_map = infisical.get("secrets_map", []) if isinstance(infisical, dict) else []
        declared_vars = {entry.get("var") for entry in secrets_map if isinstance(entry, dict)}
        missing = [variable for variable in (user_var, password_var) if variable not in declared_vars]
        if missing:
            failures.append(
                f"service={service_name}, target={target_name}: "
                f"missing infisical.secrets_map declarations for {', '.join(map(str, missing))}"
            )

    assert not failures, "PostgreSQL credential declaration errors:\n" + "\n".join(failures)


def test_common_dispatch_context_is_snapshotted_into_both_runtime_adapters():
    common_tasks = yaml.safe_load(COMMON_PREFLIGHT)
    common_reset = task_named(common_tasks, "Service catalog preflight | Reset current-service common context")
    common_lookup = task_named(common_tasks, "Service catalog preflight | Resolve common Infisical and environment context")
    common_snapshot = task_named(common_tasks, "Service catalog preflight | Snapshot current-service common outputs")
    docker_init = yaml.safe_load(DOCKER_INIT)
    docker_reset = task_named(docker_init, "Initialize | Reset per-service state")
    docker_snapshot = task_named(docker_init, "Initialize | Load shared service context")
    docker_prepare = task_named(
        yaml.safe_load(DOCKER_PREP),
        "Prepare | Prepare shared files and integrations",
    )

    assert common_reset["ansible.builtin.set_fact"]["service_catalog_common_context"]["lookup_values"] == {}
    assert common_reset["no_log"] is True
    assert common_reset["diff"] is False
    assert common_tasks.index(common_reset) < common_tasks.index(common_lookup) < common_tasks.index(common_snapshot)
    assert common_snapshot["ansible.builtin.set_fact"]["service_catalog_common_context"]["lookup_values"] == (
        "{{ service_common_infisical_values }}"
    )
    assert docker_reset["ansible.builtin.set_fact"]["docker_services_common_values"] == {}
    assert docker_reset["no_log"] is True
    assert docker_reset["diff"] is False
    assert docker_snapshot["ansible.builtin.set_fact"]["docker_services_common_values"] == (
        "{{ docker_services_common_context.lookup_values }}"
    )
    assert docker_snapshot["no_log"] is True
    assert docker_snapshot["diff"] is False
    assert docker_init.index(docker_reset) < docker_init.index(docker_snapshot)
    assert docker_prepare["vars"]["service_common_infisical_values"] == "{{ docker_services_common_values }}"
    assert "docker_services_common_values" in docker_prepare["vars"]["service_common_traefik_base_zone"]
    assert "service_common_infisical_values" not in docker_prepare["vars"]["service_common_traefik_base_zone"]
    assert "docker_services_effective_secret_values" in DOCKER_SECRET_TASKS
    assert "service_common_infisical_values" not in DOCKER_SECRET_TASKS

    podman_reset = task_named(
        yaml.safe_load(PODMAN_INIT),
        "Init | Reset temporary service state",
    )
    podman_snapshot = task_named(
        yaml.safe_load(PODMAN_INIT),
        "Init | Store shared service context",
    )
    podman_prepare = task_named(
        yaml.safe_load(PODMAN_MAIN),
        "Podman services | Prepare service files and directories",
    )
    podman_traefik = task_named(yaml.safe_load(PODMAN_MAIN), "Podman services | Configure Traefik integration")
    podman_secret = task_named(yaml.safe_load(PODMAN_SECRET_TASKS), "Secrets | Create or update Podman secrets")

    assert podman_reset["ansible.builtin.set_fact"]["podman_services_common_values"] == {}
    assert podman_reset["no_log"] is True
    assert podman_reset["diff"] is False
    assert podman_snapshot["ansible.builtin.set_fact"]["podman_services_common_values"] == (
        "{{ podman_services_common_context.lookup_values }}"
    )
    assert podman_snapshot["no_log"] is True
    assert podman_snapshot["diff"] is False
    assert podman_prepare["vars"]["service_common_infisical_values"] == "{{ podman_services_common_values }}"
    assert podman_secret["containers.podman.podman_secret"]["data"] == (
        "{{ podman_services_effective_secret_values[podman_services_secret.var] }}"
    )
    assert podman_traefik["vars"]["service_common_traefik_base_zone"] == ("{{ podman_services_common_values.cloudflare_zone }}")


def test_both_runtime_paths_reach_common_postgres_after_infisical_resolution():
    common_tasks = yaml.safe_load(COMMON_PREPARE)
    postgres_include = task_named(
        common_tasks,
        "Service common prepare | Include PostgreSQL database preparation",
    )
    include = postgres_include["ansible.builtin.include_tasks"]

    assert include["file"] == "postgres.yml"
    assert set(include["apply"]["tags"]) == EXPECTED_TAGS
    assert set(postgres_include["tags"]) == EXPECTED_TAGS
    assert "service_common_service.postgres is defined" in postgres_include["when"]

    assert "tasks_from: infisical" not in DOCKER_PREP
    assert "name: service_common" in DOCKER_PREP

    assert "tasks_from: infisical" not in PODMAN_MAIN
    assert "tasks_from: prepare" in PODMAN_MAIN


def test_common_postgres_check_mode_reports_without_connecting():
    tasks = yaml.safe_load(COMMON_POSTGRES)
    normalize = task_named(tasks, "Service common PostgreSQL | Validate and normalize declaration")
    report = task_named(tasks, "Service common PostgreSQL | Report check-mode database plan")
    ensure = task_named(tasks, "Service common PostgreSQL | Ensure declared databases exist")

    assert "when" not in normalize
    assert normalize["no_log"] is True
    assert normalize["diff"] is False
    assert "ansible_check_mode" in report["when"]
    assert report["changed_when"] is False
    assert "not ansible_check_mode" in ensure["when"]
    assert "community.postgresql.postgresql_db" not in report
    assert set(report["tags"]) == EXPECTED_TAGS

    plan = report["ansible.builtin.debug"]["msg"]
    assert "databases=" in plan
    assert "host=" in plan
    assert "inventory=" in plan
    assert "port=" in plan
    assert "user" not in plan
    assert "password" not in plan


def test_live_postgres_uses_common_values_and_idempotent_database_module_once():
    tasks = yaml.safe_load(COMMON_POSTGRES)
    ensure = task_named(tasks, "Service common PostgreSQL | Ensure declared databases exist")
    module = ensure["community.postgresql.postgresql_db"]

    assert module["state"] == "present"
    assert "service_common_infisical_values" in module["login_user"]
    assert "service_common_infisical_values" in module["login_password"]
    assert module["login_host"] == "{{ service_common_postgres_config.host }}"
    assert module["login_port"] == "{{ service_common_postgres_config.port }}"
    assert ensure["delegate_to"] == "{{ service_common_controller_host }}"
    assert ensure["run_once"] is True
    assert ensure["no_log"] is True
    assert ensure["diff"] is False
    assert ensure["loop_control"]["loop_var"] == "service_common_postgres_database"
    assert "community.postgresql.postgresql_ping" not in COMMON_POSTGRES


def test_common_postgres_has_no_runtime_modules_or_runtime_secret_creation():
    assert "community.docker." not in COMMON_POSTGRES
    assert "containers.podman." not in COMMON_POSTGRES
    assert "postgres_pass_secret" not in COMMON_POSTGRES

    assert not DOCKER_POSTGRES_PATH.exists()
    assert "sub_tasks/prep/postgres.yml" not in DOCKER_PREP
    assert "Report check-mode PostgreSQL database plan" not in PODMAN_PREP


def test_every_postgres_password_secret_consumer_declares_materialization():
    consumers = []
    missing = []

    for path in sorted(SERVICES_DIR.glob("*.yml")):
        services = yaml.safe_load(path.read_text()) or {}
        for name, service in services.items():
            if "postgres_pass_secret" not in repr(service):
                continue
            consumers.append(name)
            if "postgres_pass_secret" not in materialized_secret_names(service):
                missing.append(name)

    assert consumers
    assert missing == []


def test_postgres_credential_guard_includes_disabled_malformed_declarations():
    services = {
        "disabled": {
            "enabled": False,
            "runtime": "docker",
            "infisical": {
                "secrets_map": [
                    {"var": "postgres_user", "path": "/Postgres", "name": "USER"},
                ]
            },
            "postgres": {
                "enable": True,
                "databases": ["disabled"],
            },
        }
    }

    with pytest.raises(AssertionError) as exc_info:
        assert_postgres_credentials_declared(services)

    message = str(exc_info.value)
    assert "service=disabled, target=<base>" in message
    assert "postgres_pass" in message


def test_every_postgres_effective_service_declares_credentials():
    services = {}
    for path in sorted(SERVICES_DIR.glob("*.yml")):
        services.update(yaml.safe_load(path.read_text()) or {})

    assert_postgres_credentials_declared(services)


@pytest.mark.parametrize(
    ("service_name", "target_name", "api_var"),
    [
        ("radarr", "radarr", "radarr_api"),
        ("radarr", "radarr_4k", "radarr_4k_api"),
        ("sonarr", "sonarr", "sonarr_api"),
        ("sonarr", "sonarr_4k", "sonarr_4k_api"),
    ],
)
def test_real_arr_targets_inherit_postgres_credentials_once_and_keep_api_secret(service_name, target_name, api_var):
    services = yaml.safe_load((SERVICES_DIR / f"{service_name}.yml").read_text())
    effective = {(name, target): service for name, target, service in effective_service_configs(services)}[(service_name, target_name)]
    declared_vars = [entry["var"] for entry in effective["infisical"]["secrets_map"]]

    assert declared_vars.count("postgres_user") == 1
    assert declared_vars.count("postgres_pass") == 1
    assert declared_vars.count(api_var) == 1


@pytest.mark.parametrize("runtime", ["docker", "podman"])
def test_postgres_credential_guard_reports_genuinely_missing_declaration(runtime):
    services = {
        "broken": {
            "runtime": runtime,
            "infisical": {
                "secrets_map": [
                    {"var": "postgres_user", "path": "/Postgres", "name": "USER"},
                ]
            },
            "targets": {
                "primary": {
                    "postgres": {
                        "enable": True,
                        "databases": ["broken"],
                    }
                }
            },
        }
    }

    with pytest.raises(AssertionError) as exc_info:
        assert_postgres_credentials_declared(services)

    message = str(exc_info.value)
    assert "service=broken, target=primary" in message
    assert "postgres_pass" in message
