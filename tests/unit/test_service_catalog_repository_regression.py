import importlib.util
import re
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, StrictUndefined, meta
from jinja2.nativetypes import NativeEnvironment

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_DIR = REPO_ROOT / "ansible/group_vars/all/services"
PLAYBOOK_PATH = REPO_ROOT / "ansible/playbook.yml"
DOCKER_INIT_PATH = REPO_ROOT / "ansible/roles/docker_services/tasks/sub_tasks/init.yml"
PODMAN_INIT_PATH = REPO_ROOT / "ansible/roles/podman_services/tasks/sub_tasks/init.yml"
DOCKER_TASKS_DIR = REPO_ROOT / "ansible/roles/docker_services/tasks"
PODMAN_TASKS_DIR = REPO_ROOT / "ansible/roles/podman_services/tasks"
GLOBAL_DISPATCH_PATH = REPO_ROOT / "ansible/tasks/service_catalog_dispatch.yml"
DOCKER_DISPATCH_PATH = REPO_ROOT / "ansible/tasks/service_catalog_dispatch_docker.yml"
PODMAN_DISPATCH_PATH = REPO_ROOT / "ansible/tasks/service_catalog_dispatch_podman.yml"
COMMON_TEMPLATE_DIR = REPO_ROOT / "ansible/roles/service_common/templates"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_services():
    services = {}
    for path in sorted(SERVICES_DIR.glob("*.yml")):
        data = yaml.safe_load(path.read_text()) or {}
        services.update(data)
    return services


def render_structure(value, variables):
    if isinstance(value, dict):
        return {key: render_structure(item, variables) for key, item in value.items()}
    if isinstance(value, list):
        return [render_structure(item, variables) for item in value]
    if isinstance(value, str) and ("{{" in value or "{%" in value):
        return NativeEnvironment(undefined=StrictUndefined).from_string(value).render(**variables)
    return value


def walk_mappings(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_mappings(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_mappings(child)


def task_named(value, name):
    return next(mapping for mapping in walk_mappings(value) if mapping.get("name") == name)


def test_real_repository_catalog_contains_only_lightweight_selection_metadata():
    catalog_filters = load_module(
        REPO_ROOT / "ansible/filter_plugins/service_catalog.py",
        "service_catalog_lightweight_repository",
    )

    effective = catalog_filters.service_catalog_effective(load_services(), "manager")

    assert effective
    assert all("config" not in item for item in effective)
    assert all(set(item) <= {"name", "target", "runtime", "tags", "enabled", "dispatch_host"} for item in effective)


def test_real_repository_dispatch_hosts_are_lightweight_and_runtime_specific():
    catalog_filters = load_module(
        REPO_ROOT / "ansible/filter_plugins/service_catalog.py",
        "service_catalog_repository_dispatch",
    )
    effective = catalog_filters.service_catalog_effective(load_services(), "manager")
    arrs = [item for item in effective if "arrs" in item["tags"]]
    n8n = next(item for item in effective if item["name"] == "n8n")

    assert arrs
    assert all(item["runtime"] == "docker" for item in arrs)
    assert all(item["dispatch_host"] == "manager" for item in arrs)
    assert n8n["runtime"] == "podman"
    assert n8n["dispatch_host"] == "n8n"
    assert all("config" not in item for item in [*arrs, n8n])


def test_real_repository_dispatch_hosts_match_repository_host_definitions():
    catalog_filters = load_module(
        REPO_ROOT / "ansible/filter_plugins/service_catalog.py",
        "service_catalog_repository_hosts",
    )
    services = deepcopy(load_services())
    for service in services.values():
        configurations = [service, *(service.get("targets", {}) or {}).values()]
        for configuration in configurations:
            deploy = configuration.get("deploy", {})
            if deploy.get("host") == "{{ services_controller_host }}":
                deploy["host"] = "mgt"

    effective = catalog_filters.service_catalog_effective(services, "mgt")
    repository_hosts = {path.stem for path in (REPO_ROOT / "ansible/host_vars").glob("*.yml")}
    repository_hosts.update(path.name for path in (REPO_ROOT / "terraform/proxmox/vms").iterdir() if path.is_dir())

    assert {entry["dispatch_host"] for entry in effective} == {"mgt", "n8n"}
    assert all(entry["dispatch_host"] in repository_hosts for entry in effective)


def test_every_real_service_declares_a_supported_runtime():
    services = load_services()

    for service_name, service_cfg in services.items():
        assert "runtime" in service_cfg, f"{service_name} must declare its runtime explicitly"
        assert service_cfg["runtime"] in {"docker", "podman"}, f"{service_name} declares an unsupported runtime"


def test_removed_compatibility_identifiers_have_no_production_references():
    removed_plugin = REPO_ROOT / "ansible/roles/docker_services/filter_plugins/docker_services_merge.py"
    assert not removed_plugin.exists()

    production_files = [
        path for path in (REPO_ROOT / "ansible").rglob("*") if path.is_file() and path.suffix in {".j2", ".py", ".yaml", ".yml"}
    ]
    removed_identifiers = (
        r"\bdocker_services_merge_target\b",
        r"\bdocker_services_effective\b",
        r"\bdocker_services_select\b",
        r"\bservice_common_secret_values\b",
        r"__INFISICAL__:",
    )

    for path in production_files:
        contents = path.read_text()
        for identifier in removed_identifiers:
            assert re.search(identifier, contents) is None, f"{identifier} remains in {path.relative_to(REPO_ROOT)}"


def test_real_podman_definitions_use_only_canonical_adapter_inputs():
    catalog_filters = load_module(
        REPO_ROOT / "ansible/filter_plugins/service_catalog.py",
        "service_catalog_repository_podman_canonical",
    )
    podman_filters = load_module(
        REPO_ROOT / "ansible/roles/podman_services/filter_plugins/podman_services.py",
        "podman_services_repository_canonical",
    )
    services = load_services()
    checked = []
    expected = {
        "adminer": {
            "network": "adminer",
            "host": "manager",
            "host_port": 18080,
            "container_port": 8080,
            "execution": {"mode": "rootless", "host_user": "podman-adminer"},
            "systemd": {
                "after": ["network-online.target"],
                "restart": "on-failure",
                "restart_sec": "10s",
            },
        },
        "homepage": {
            "network": "homepage",
            "host": "manager",
            "host_port": 13000,
            "container_port": 3000,
            "execution": {
                "mode": "rootless",
                "host_user": "podman-homepage",
                "userns": {"mode": "keep-id", "uid": "1000", "gid": "1000"},
            },
            "systemd": {
                "after": ["network-online.target"],
                "restart": "on-failure",
                "restart_sec": "10s",
            },
        },
        "thelounge": {
            "network": "thelounge",
            "host": "manager",
            "host_port": 19000,
            "container_port": 9000,
            "execution": {
                "mode": "rootless",
                "host_user": "podman-thelounge",
                "userns": {"mode": "keep-id", "uid": "1000", "gid": "1000"},
            },
            "container_user": {"uid": "0", "gid": "0"},
            "systemd": {
                "after": ["network-online.target"],
                "restart": "on-failure",
                "restart_sec": "10s",
                "timeout_start_sec": "900s",
            },
        },
        "n8n": {
            "network": "n8n",
            "host": "n8n",
            "host_port": 5678,
            "container_port": 5678,
            "execution": {"mode": "rootful"},
            "systemd": {
                "after": ["network-online.target"],
                "restart": "on-failure",
                "restart_sec": "15s",
            },
        },
    }

    for item in catalog_filters.service_catalog_effective(services, "manager"):
        if item["runtime"] != "podman":
            continue
        effective = catalog_filters.service_catalog_merge_target(services[item["name"]], item.get("target"))
        assert not ({"container", "env", "host_paths", "network"} & set(effective))
        podman_runtime_options = effective.get("runtime_options", {}).get("podman", {})
        assert "network" not in podman_runtime_options
        assert "systemd" not in podman_runtime_options
        rendered_effective = render_structure(
            deepcopy(effective),
            {
                "hostvars": {
                    "manager": {
                        "container_host_appdata_root": "/opt",
                        "container_host_puid": 1000,
                        "container_host_pgid": 1000,
                        "local_ip": "192.0.2.10",
                    }
                },
                "local_ip": "192.0.2.10",
                "services_controller_host": "manager",
                "services_public_zone": "public.example",
                "services_internal_zone": "private.example.internal",
                "services_private_https_port": 9443,
                "timezone": "Australia/Melbourne",
            },
        )
        assert set(rendered_effective) <= podman_filters._SUPPORTED_TOP_LEVEL_FIELDS
        normalized = podman_filters.podman_service_normalize(rendered_effective, item.get("target", item["name"]))
        assert normalized["name"] == item["name"]
        assert normalized["unit_name"] == item["name"]
        assert normalized["image"] == effective["image"]
        behavior = expected[item["name"]]
        assert normalized["network"] == {
            "name": behavior["network"],
            "driver": "bridge",
            "external": False,
        }
        assert normalized["container"]["host"] == behavior["host"]
        assert normalized["container"]["ports"][0]["host"] == behavior["host_port"]
        assert normalized["container"]["ports"][0]["container"] == behavior["container_port"]
        assert normalized["container"]["systemd"] == behavior["systemd"]
        assert normalized["execution"] == behavior["execution"]
        if item["name"] == "thelounge":
            assert normalized["container"]["uid"] == behavior["container_user"]["uid"]
            assert normalized["container"]["gid"] == behavior["container_user"]["gid"]
            assert normalized["host_paths"] == [{"path": "/opt/thelounge", "state": "directory", "mode": "0750"}]
            assert normalized["container"]["mounts"] == [
                {
                    "source": "/opt/thelounge",
                    "target": "/config",
                    "read_only": False,
                }
            ]
        checked.append((item["name"], item.get("target")))

    assert checked == [("adminer", None), ("homepage", None), ("n8n", None), ("thelounge", None)]


def test_repository_secret_policy_is_runtime_neutral_and_defaults_safely():
    services = load_services()
    policies = []

    for service_name, service_cfg in services.items():
        service_options = service_cfg.get("runtime_options", {}).get("podman", {})
        assert "network" not in service_options, service_name
        assert "systemd" not in service_options, service_name
        for declaration in service_cfg.get("infisical", {}).get("secrets_map", []):
            secret = declaration.get("secret", {})
            assert "runtime_options" not in secret, service_name
            assert "immutable" not in secret, service_name
            assert "replace" not in secret, service_name
            if secret:
                policies.append((service_name, secret.get("update_policy", "preserve")))

    assert policies
    assert set(policy for _, policy in policies) <= {"preserve", "reconcile"}


def test_every_effective_service_uses_the_canonical_secret_contract_and_default_empty_policy():
    catalog_filters = load_module(
        REPO_ROOT / "ansible/filter_plugins/service_catalog.py",
        "service_catalog_secret_contract_repository",
    )
    common_filters = load_module(
        REPO_ROOT / "ansible/roles/service_common/filter_plugins/service_common.py",
        "service_common_secret_contract_repository",
    )
    podman_filters = load_module(
        REPO_ROOT / "ansible/roles/podman_services/filter_plugins/podman_services.py",
        "podman_secret_contract_repository",
    )
    services = load_services()
    checked = []

    for service_name, service_cfg in services.items():
        for mapping in walk_mappings(service_cfg):
            infisical = mapping.get("infisical")
            if isinstance(infisical, dict):
                assert infisical.get("fail_on_empty") is not True, service_name

    for item in catalog_filters.service_catalog_effective(services, "manager"):
        effective = catalog_filters.service_catalog_merge_target(services[item["name"]], item.get("target"))
        infisical = effective.get("infisical", {})
        normalized = common_filters.service_common_infisical_normalize(
            infisical.get("secrets_map", []),
            infisical.get("fail_on_empty", True),
        )
        check_values = common_filters.service_common_infisical_check_values(normalized)
        resolved_environment = common_filters.service_common_environment_resolve(
            effective.get("environment", {}),
            check_values,
            normalized,
        )
        identity = f"{item['name']}/{item.get('target', '<base>')}"
        assert isinstance(resolved_environment, dict), identity
        assert normalized["fail_on_empty"] is infisical.get("fail_on_empty", True), identity
        for declaration in normalized["secret_declarations"]:
            assert declaration["update_policy"] in {"preserve", "reconcile"}, identity
            assert {"runtime_options", "immutable", "replace"}.isdisjoint(declaration), identity
        if item["runtime"] == "podman":
            podman_declarations = podman_filters.podman_secret_declarations(normalized["secret_declarations"])
            assert all({"immutable", "replace"}.isdisjoint(declaration) for declaration in podman_declarations), identity
        checked.append(identity)

    n8n = catalog_filters.service_catalog_merge_target(services["n8n"])
    n8n_normalized = common_filters.service_common_infisical_normalize(n8n["infisical"]["secrets_map"])
    n8n_policies = {entry["name"]: entry["update_policy"] for entry in n8n_normalized["secret_declarations"]}
    assert n8n_policies["n8n_encryption_key_secret"] == "preserve"
    assert n8n_policies["postgres_pass_secret"] == "reconcile"
    assert checked


def test_real_docker_swarm_constraints_match_configured_node_label_values():
    catalog_filters = load_module(
        REPO_ROOT / "ansible/filter_plugins/service_catalog.py",
        "service_catalog_repository_swarm_constraints",
    )
    services = load_services()
    expected_by_host = {
        "{{ services_controller_host }}": "node.labels.docker_services_host == docker_services_primary_manager",
        "{{ services_plex_host }}": "node.labels.docker_services_host == docker_services_plex_host",
        "{{ services_storage_host }}": "node.labels.docker_services_host == docker_services_unraid_host",
    }
    observed = set()

    for item in catalog_filters.service_catalog_effective(services, "manager"):
        effective = catalog_filters.service_catalog_merge_target(services[item["name"]], item.get("target"))
        if effective["runtime"] != "docker":
            continue

        deploy = effective.get("deploy", {})
        host_constraints = [
            constraint for constraint in deploy.get("constraints", []) if constraint.startswith("node.labels.docker_services_host == ")
        ]
        if not host_constraints:
            continue

        target = item.get("target", "base")
        expected = expected_by_host.get(deploy.get("host"))
        assert expected is not None, f"{item['name']}/{target} has an unknown constrained deploy host"
        assert host_constraints == [expected], f"{item['name']}/{target} has a mismatched Swarm host constraint"
        observed.add(expected)

    assert observed == set(expected_by_host.values())


def test_real_sonarr_catalog_target_keeps_effective_configuration():
    catalog_filters = load_module(
        REPO_ROOT / "ansible/filter_plugins/service_catalog.py",
        "service_catalog_real_sonarr",
    )
    item = next(
        item
        for item in catalog_filters.service_catalog_effective(load_services(), "manager")
        if item["name"] == "sonarr" and item.get("target") == "sonarr"
    )

    services = load_services()
    effective = catalog_filters.service_catalog_merge_target(services[item["name"]], item["target"])
    common_filters = load_module(
        REPO_ROOT / "ansible/roles/service_common/filter_plugins/service_common.py",
        "service_common_real_sonarr",
    )
    normalized = common_filters.service_common_infisical_normalize(
        effective["infisical"]["secrets_map"],
        effective["infisical"].get("fail_on_empty", True),
    )

    assert "targets" not in effective
    assert effective["name"] == "sonarr"
    assert effective["deploy"]["type"] == "swarm"
    assert effective["environment"]["SONARR__APP__INSTANCENAME"] == "Sonarr"
    assert [declaration["name"] for declaration in normalized["secret_declarations"]] == [
        "postgres_user_secret",
        "postgres_pass_secret",
        "sonarr_api_secret",
    ]
    assert effective["traefik"] == {"enable": True, "exposure": "private", "port": 8989}


@pytest.mark.parametrize(
    ("service_name", "target_name", "api_var"),
    [
        ("radarr", "radarr", "radarr_api"),
        ("radarr", "radarr_4k", "radarr_4k_api"),
        ("sonarr", "sonarr", "sonarr_api"),
        ("sonarr", "sonarr_4k", "sonarr_4k_api"),
    ],
)
def test_real_arr_targets_inherit_base_credentials_once_and_keep_target_api(service_name, target_name, api_var):
    catalog_filters = load_module(
        REPO_ROOT / "ansible/filter_plugins/service_catalog.py",
        f"service_catalog_real_{service_name}_{target_name}",
    )
    service = load_services()[service_name]

    effective = catalog_filters.service_catalog_merge_target(service, target_name)
    declarations = [entry["var"] for entry in effective["infisical"]["secrets_map"]]

    assert effective["runtime"] == service["runtime"] == "docker"
    assert declarations.count("postgres_user") == 1
    assert declarations.count("postgres_pass") == 1
    assert declarations.count(api_var) == 1
    assert "targets" not in effective


def test_real_traefik_services_do_not_require_cloudflare_zone_infisical_declarations():
    catalog_filters = load_module(
        REPO_ROOT / "ansible/filter_plugins/service_catalog.py",
        "service_catalog_real_traefik_infisical",
    )
    services = load_services()
    checked = []

    for item in catalog_filters.service_catalog_effective(services, "manager"):
        effective = catalog_filters.service_catalog_merge_target(services[item["name"]], item.get("target"))
        if (effective.get("traefik") or {}).get("enable") is not True:
            continue
        declared = [entry.get("var") for entry in (effective.get("infisical") or {}).get("secrets_map", [])]
        identity = f"{item['name']}:{item.get('target', '<base>')}"
        assert "cloudflare_zone" not in declared, identity
        checked.append(identity)

    assert checked


def test_real_docker_env_file_services_retain_their_effective_declarations():
    catalog_filters = load_module(
        REPO_ROOT / "ansible/filter_plugins/service_catalog.py",
        "service_catalog_real_env_files",
    )
    services = load_services()
    actual = set()

    for item in catalog_filters.service_catalog_effective(services, "manager"):
        effective = catalog_filters.service_catalog_merge_target(services[item["name"]], item.get("target"))
        if effective.get("env_file"):
            actual.add((item["name"], item.get("target", "<base>")))

    assert actual == {
        ("authelia", "main"),
        ("gitea", "<base>"),
        ("gotify", "<base>"),
        ("grafana", "<base>"),
        ("opencloud", "<base>"),
        ("qbittorrent", "downloads"),
        ("qbittorrent", "seeds"),
        ("qui", "<base>"),
        ("seerr", "<base>"),
        ("vaultwarden", "<base>"),
    }


def test_real_common_templates_consume_declared_infisical_values_through_common_mapping():
    catalog_filters = load_module(
        REPO_ROOT / "ansible/filter_plugins/service_catalog.py",
        "service_catalog_real_common_templates",
    )
    services = load_services()
    environment = Environment()
    checked = []

    for item in catalog_filters.service_catalog_effective(services, "manager"):
        effective = catalog_filters.service_catalog_merge_target(services[item["name"]], item.get("target"))
        declared = {entry.get("var") for entry in (effective.get("infisical") or {}).get("secrets_map", []) if isinstance(entry, dict)}
        for field in ("templates", "swarm_env_templates"):
            for declaration in effective.get(field, []) or []:
                source = COMMON_TEMPLATE_DIR / declaration["src"]
                undeclared = meta.find_undeclared_variables(environment.parse(source.read_text()))
                identity = f"{item['name']}:{item.get('target', '<base>')}:{declaration['src']}"
                assert not (declared & undeclared), identity
                if "service_common_infisical_values." in source.read_text():
                    assert "service_common_infisical_values" in undeclared, identity
                    assert declaration.get("no_log") is True, identity
                    checked.append(identity)

    assert checked


def test_cross_host_standalone_services_retain_global_catalog_order():
    catalog_filters = load_module(
        REPO_ROOT / "ansible/filter_plugins/service_catalog.py",
        "service_catalog_cross_host_order",
    )
    services = {
        "first": {
            "runtime": "docker",
            "deploy": {"type": "container", "host": "docker-a"},
        },
        "second": {
            "runtime": "docker",
            "deploy": {"type": "container", "host": "docker-b"},
        },
    }

    selected = catalog_filters.service_catalog_select(
        catalog_filters.service_catalog_effective(services, "manager"),
        run_all=True,
    )["selected"]

    assert [(entry["name"], entry["dispatch_host"]) for entry in selected] == [
        ("first", "docker-a"),
        ("second", "docker-b"),
    ]


def test_playbook_processes_one_globally_ordered_lightweight_catalog_loop():
    playbook = yaml.safe_load(PLAYBOOK_PATH.read_text())
    deploy_play = next(play for play in playbook if play.get("name") == "Deploy homelab services")
    deploy_tasks = deploy_play["tasks"]
    assert deploy_play["strategy"] == "linear"
    catalog_task = task_named(playbook, "Build service catalog processing list from service definitions")
    selection_task = task_named(playbook, "Build selected service catalog processing list")
    selection_extract_task = task_named(playbook, "Extract service catalog selection facts")
    dispatch_host_validation = task_named(playbook, "Validate selected service dispatch hosts")
    share_task = task_named(playbook, "Share lightweight service catalog selection with play hosts")
    global_dispatch_task = task_named(playbook, "Process globally ordered service catalog")
    deploy_all_task = task_named(playbook, "Deploy all Docker stacks")

    assert catalog_task["when"] == "inventory_hostname == services_controller_host"
    assert selection_task["when"] == "inventory_hostname == services_controller_host"
    catalog_expression = catalog_task["ansible.builtin.set_fact"]["service_catalog_effective"]
    assert "svcfiles | service_catalog_effective(services_controller_host)" in catalog_expression
    assert "service_catalog_effective" not in share_task["ansible.builtin.set_fact"]

    expected_tags = {"deploy", "update", "remove", "recreate", "bootstrap", "drift"}
    assert dispatch_host_validation["when"] == "inventory_hostname == services_controller_host"
    assert dispatch_host_validation["loop"] == "{{ service_catalog_selected }}"
    assert dispatch_host_validation["loop_control"]["loop_var"] == "service_catalog_dispatch_item"
    assert dispatch_host_validation["ansible.builtin.assert"]["that"] == [
        "service_catalog_dispatch_item.dispatch_host in ansible_play_hosts_all"
    ]
    dispatch_failure = dispatch_host_validation["ansible.builtin.assert"]["fail_msg"]
    assert "service_catalog_dispatch_item.name" in dispatch_failure
    assert "service_catalog_dispatch_item.target" in dispatch_failure
    assert "service_catalog_dispatch_item.dispatch_host" in dispatch_failure
    assert set(dispatch_host_validation["tags"]) == expected_tags
    assert deploy_tasks.index(selection_extract_task) < deploy_tasks.index(dispatch_host_validation)
    assert deploy_tasks.index(dispatch_host_validation) < deploy_tasks.index(share_task)
    assert deploy_tasks.index(share_task) < deploy_tasks.index(global_dispatch_task)
    assert deploy_tasks.index(global_dispatch_task) < deploy_tasks.index(deploy_all_task)

    shared_facts = share_task["ansible.builtin.set_fact"]
    assert set(shared_facts) == {
        "service_catalog_matched",
        "service_catalog_selected",
        "service_catalog_disabled_only_selection",
    }
    assert "config" not in str(shared_facts)
    assert "materialized" not in str(shared_facts)

    assert global_dispatch_task["loop"] == "{{ service_catalog_selected }}"
    assert global_dispatch_task["loop_control"]["loop_var"] == "service_catalog_dispatch_entry"
    assert "when" not in global_dispatch_task
    assert global_dispatch_task["ansible.builtin.include_tasks"]["file"] == "tasks/service_catalog_dispatch.yml"
    assert set(global_dispatch_task["tags"]) == expected_tags
    assert set(global_dispatch_task["ansible.builtin.include_tasks"]["apply"]["tags"]) == expected_tags
    assert "service_catalog_host_selected" not in PLAYBOOK_PATH.read_text()
    assert "docker_services_selected" not in PLAYBOOK_PATH.read_text()
    assert "podman_services_selected" not in PLAYBOOK_PATH.read_text()
    assert any("service_catalog_selected" in condition for condition in deploy_all_task["when"])
    assert any("service_catalog_by_runtime('docker')" in condition for condition in deploy_all_task["when"])

    global_dispatch = yaml.safe_load(GLOBAL_DISPATCH_PATH.read_text())
    reset = task_named(global_dispatch, "Service catalog dispatch | Reset host-local materialized result")
    materialize = task_named(global_dispatch, "Service catalog dispatch | Materialize selected entry on dispatch host")
    copy_result = task_named(global_dispatch, "Service catalog dispatch | Copy returned materialized entry")
    validate = task_named(global_dispatch, "Service catalog dispatch | Validate single materialized entry")
    docker_route = task_named(global_dispatch, "Service catalog dispatch | Process Docker entry")
    podman_route = task_named(global_dispatch, "Service catalog dispatch | Process Podman entry")

    assert global_dispatch.index(reset) < global_dispatch.index(materialize) < global_dispatch.index(copy_result)
    assert global_dispatch.index(copy_result) < global_dispatch.index(validate)
    assert global_dispatch.index(validate) < global_dispatch.index(docker_route)
    assert global_dispatch.index(validate) < global_dispatch.index(podman_route)
    assert reset["ansible.builtin.set_fact"]["service_catalog_host_materialized"] == []
    expected_host_condition = "inventory_hostname == service_catalog_dispatch_entry.dispatch_host"
    assert materialize["when"] == expected_host_condition
    assert validate["when"] == expected_host_condition
    assert materialize["service_catalog_materialize"] == {
        "source_var": "svcfiles",
        "selected": ["{{ service_catalog_dispatch_entry }}"],
    }
    assert materialize["register"] == "service_catalog_materialize_result"
    assert copy_result["when"] == expected_host_condition
    assert copy_result["ansible.builtin.set_fact"]["service_catalog_host_materialized"] == (
        "{{ service_catalog_materialize_result.ansible_facts.service_catalog_host_materialized }}"
    )
    assert validate["ansible.builtin.assert"]["that"] == [
        "service_catalog_host_materialized is sequence",
        "service_catalog_host_materialized | length == 1",
        "service_catalog_host_materialized[0].config is mapping",
    ]
    for route, runtime, filename, variable in (
        (docker_route, "docker", "service_catalog_dispatch_docker.yml", "service_catalog_docker_service"),
        (podman_route, "podman", "service_catalog_dispatch_podman.yml", "service_catalog_podman_service"),
    ):
        assert route["when"] == [expected_host_condition, f'service_catalog_dispatch_entry.runtime == "{runtime}"']
        assert route["ansible.builtin.include_tasks"]["file"] == filename
        assert set(route["tags"]) == expected_tags
        assert set(route["ansible.builtin.include_tasks"]["apply"]["tags"]) == expected_tags
        assert route["vars"][variable] == "{{ service_catalog_host_materialized[0] }}"

    assert "{{ svcfiles }}" not in GLOBAL_DISPATCH_PATH.read_text()
    assert "hostvars" not in GLOBAL_DISPATCH_PATH.read_text()
    assert "delegate_to" not in GLOBAL_DISPATCH_PATH.read_text()
    assert "delegate_facts" not in GLOBAL_DISPATCH_PATH.read_text()

    docker_dispatch = yaml.safe_load(DOCKER_DISPATCH_PATH.read_text())
    podman_dispatch = yaml.safe_load(PODMAN_DISPATCH_PATH.read_text())
    docker_reset = task_named(
        docker_dispatch,
        "Service catalog dispatch | Reset Docker transient configuration",
    )
    docker_copy = task_named(
        docker_dispatch,
        "Service catalog dispatch | Copy Docker materialized configuration",
    )
    docker_include = task_named(
        docker_dispatch,
        "Service catalog dispatch | Include Docker service role",
    )
    podman_reset = task_named(
        podman_dispatch,
        "Service catalog dispatch | Reset Podman transient configuration",
    )
    podman_copy = task_named(
        podman_dispatch,
        "Service catalog dispatch | Copy Podman materialized configuration",
    )
    podman_include = task_named(
        podman_dispatch,
        "Service catalog dispatch | Include Podman service role",
    )

    assert docker_reset["ansible.builtin.set_fact"]["docker_services_dispatch_config"] == {}
    assert podman_reset["ansible.builtin.set_fact"]["podman_services_dispatch_config"] == {}
    assert docker_dispatch.index(docker_reset) < docker_dispatch.index(docker_copy) < docker_dispatch.index(docker_include)
    assert podman_dispatch.index(podman_reset) < podman_dispatch.index(podman_copy) < podman_dispatch.index(podman_include)

    assert docker_copy["ansible.builtin.set_fact"]["docker_services_dispatch_config"] == ("{{ service_catalog_docker_service.config }}")
    assert podman_copy["ansible.builtin.set_fact"]["podman_services_dispatch_config"] == ("{{ service_catalog_podman_service.config }}")
    assert "svcfiles" not in DOCKER_DISPATCH_PATH.read_text()
    assert "svcfiles" not in PODMAN_DISPATCH_PATH.read_text()
    assert "service_catalog_merge_target" not in DOCKER_DISPATCH_PATH.read_text()
    assert "service_catalog_merge_target" not in PODMAN_DISPATCH_PATH.read_text()
    assert docker_include["vars"]["docker_services_service_cfg_found"] is True
    assert podman_include["vars"]["podman_services_service_cfg_found"] is True
    assert "default(service_cfg_found" not in DOCKER_DISPATCH_PATH.read_text()
    assert "default(service_cfg_found" not in PODMAN_DISPATCH_PATH.read_text()
    assert "when" not in docker_include
    assert "when" not in podman_include

    assert docker_include["vars"]["docker_services_service_cfg"] == "{{ docker_services_dispatch_config }}"
    assert podman_include["vars"]["podman_services_service_cfg"] == "{{ podman_services_dispatch_config }}"
    assert podman_include["vars"]["ansible_pipelining"] is True
    assert "ansible_pipelining" not in docker_include["vars"]
    assert "service_catalog_merge_target" not in str(docker_include["vars"])
    assert "service_catalog_merge_target" not in str(podman_include["vars"])

    docker_init = yaml.safe_load(DOCKER_INIT_PATH.read_text())
    docker_config = task_named(docker_init, "Initialize | Load service configuration")
    docker_assert = task_named(docker_init, "Initialize | Validate service configuration input")
    podman_init = yaml.safe_load(PODMAN_INIT_PATH.read_text())
    podman_assert = task_named(podman_init, "Init | Validate selected service configuration")

    assert docker_config["ansible.builtin.set_fact"]["docker_services_svc"] == "{{ docker_services_service_cfg }}"
    adapter_tasks = "\n".join(path.read_text() for tasks_dir in (DOCKER_TASKS_DIR, PODMAN_TASKS_DIR) for path in tasks_dir.rglob("*.yml"))
    assert "merge_target" not in adapter_tasks
    assert "docker_services_service_cfg.targets is not defined" in docker_assert["ansible.builtin.assert"]["that"]
    assert "podman_services_service_cfg.targets is not defined" in podman_assert["ansible.builtin.assert"]["that"]


def test_runtime_partition_only_sends_podman_entries_to_strict_podman_normalization():
    catalog_filters = load_module(
        REPO_ROOT / "ansible/filter_plugins/service_catalog.py",
        "service_catalog_runtime_guardrail_repository",
    )
    podman_filters = load_module(
        REPO_ROOT / "ansible/roles/podman_services/filter_plugins/podman_services.py",
        "podman_services_runtime_guardrail_repository",
    )
    services = {
        "docker-app": {
            "runtime": "docker",
            "image": "example.invalid/docker-app:1.0.0",
            "command": ["serve"],
        },
        "podman-app": {
            "runtime": "podman",
            "image": "example.invalid/podman-app:1.0.0",
            "deploy": {"type": "container"},
        },
    }
    selected = catalog_filters.service_catalog_select(
        catalog_filters.service_catalog_effective(services, "manager"),
        run_all=True,
    )["selected"]
    docker_entries = catalog_filters.service_catalog_by_runtime(selected, "docker")
    podman_entries = catalog_filters.service_catalog_by_runtime(selected, "podman")

    assert [entry["name"] for entry in docker_entries] == ["docker-app"]
    assert [entry["name"] for entry in podman_entries] == ["podman-app"]
    docker_config = catalog_filters.service_catalog_merge_target(services["docker-app"])
    podman_config = catalog_filters.service_catalog_merge_target(services["podman-app"])
    assert docker_config["command"] == ["serve"]
    assert podman_filters.podman_service_normalize(podman_config, "podman-app")["name"] == "podman-app"


def test_podman_target_role_prefix_and_explicit_name_produce_collision_free_names():
    catalog_filters = load_module(
        REPO_ROOT / "ansible/filter_plugins/service_catalog.py",
        "service_catalog_target_name_guardrail_repository",
    )
    podman_filters = load_module(
        REPO_ROOT / "ansible/roles/podman_services/filter_plugins/podman_services.py",
        "podman_services_target_name_guardrail_repository",
    )
    service = {
        "runtime": "podman",
        "image": "example.invalid/app:1.0.0",
        "targets": {
            "blue": {},
            "green": {"name": "custom-green"},
        },
    }

    blue = catalog_filters.service_catalog_merge_target(service, "blue")
    green = catalog_filters.service_catalog_merge_target(service, "green")
    blue_normalized = podman_filters.podman_service_normalize(blue, "app-blue")
    green_normalized = podman_filters.podman_service_normalize(green, "app-green")

    assert blue_normalized["name"] == blue_normalized["unit_name"] == "app-blue"
    assert green_normalized["name"] == green_normalized["unit_name"] == "custom-green"


def test_real_adminer_podman_migration_preserves_runtime_contracts():
    catalog_filters = load_module(
        REPO_ROOT / "ansible/filter_plugins/service_catalog.py",
        "service_catalog_adminer_podman_repository",
    )
    podman_filters = load_module(
        REPO_ROOT / "ansible/roles/podman_services/filter_plugins/podman_services.py",
        "podman_services_adminer_repository",
    )
    common_filters = load_module(
        REPO_ROOT / "ansible/roles/service_common/filter_plugins/service_common.py",
        "service_common_adminer_repository",
    )
    rendered_service = render_structure(
        deepcopy(load_services()["adminer"]),
        {
            "hostvars": {"manager": {"local_ip": "192.0.2.10"}},
            "local_ip": "192.0.2.10",
            "services_controller_host": "manager",
        },
    )
    entry = catalog_filters.service_catalog_effective({"adminer": rendered_service}, "manager")[0]
    rendered_effective = catalog_filters.service_catalog_merge_target(rendered_service)
    normalized = podman_filters.podman_service_normalize(rendered_effective, "adminer")
    lookup_config = common_filters.service_common_infisical_normalize(rendered_effective.get("infisical", {}).get("secrets_map") or [])
    check_values = common_filters.service_common_infisical_check_values(lookup_config)
    resolved_environment = common_filters.service_common_environment_resolve(
        rendered_effective.get("environment", {}),
        check_values,
        lookup_config,
    )
    traefik = common_filters.service_common_traefik_context(
        rendered_effective,
        "adminer",
        ["manager"],
        "public.example",
        "private.example.internal",
        {"manager": {"local_ip": "192.0.2.10"}},
    )

    assert entry["runtime"] == "podman"
    assert entry["dispatch_host"] == "manager"
    assert "stack" not in rendered_effective
    assert {"profile", "constraints", "mode", "replicas"}.isdisjoint(rendered_effective["deploy"])
    assert rendered_effective["deploy"] == {
        "type": "container",
        "host": "manager",
        "execution": {"mode": "rootless", "host_user": "podman-adminer"},
    }
    assert normalized["name"] == normalized["unit_name"] == "adminer"
    assert normalized["execution"] == {"mode": "rootless", "host_user": "podman-adminer"}
    assert normalized["network"] == {"name": "adminer", "driver": "bridge", "external": False}
    assert normalized["container"]["host"] == "manager"
    assert normalized["container"]["ports"] == [
        {
            "host": 18080,
            "container": 8080,
            "protocol": "tcp",
            "host_ip": "192.0.2.10",
        }
    ]
    assert normalized["container"]["systemd"] == {
        "after": ["network-online.target"],
        "restart": "on-failure",
        "restart_sec": "10s",
    }
    assert lookup_config["secret_declarations"] == []
    assert check_values == {}
    assert resolved_environment == {}
    assert traefik["address"] == "adminer.private.example.internal"
    assert traefik["backend_url"] == "http://192.0.2.10:18080"


def test_real_adminer_renders_a_managed_network_and_host_published_quadlet():
    catalog_filters = load_module(
        REPO_ROOT / "ansible/filter_plugins/service_catalog.py",
        "service_catalog_adminer_quadlet_repository",
    )
    podman_filters = load_module(
        REPO_ROOT / "ansible/roles/podman_services/filter_plugins/podman_services.py",
        "podman_services_adminer_quadlet_repository",
    )
    effective = catalog_filters.service_catalog_merge_target(load_services()["adminer"])
    rendered_effective = render_structure(
        deepcopy(effective),
        {
            "local_ip": "192.0.2.10",
            "services_controller_host": "manager",
        },
    )
    normalized = podman_filters.podman_service_normalize(rendered_effective, "adminer")
    template = Environment(trim_blocks=True, lstrip_blocks=True).from_string(
        (REPO_ROOT / "ansible/roles/podman_services/templates/container.container.j2").read_text()
    )
    rendered = template.render(
        podman_service=normalized,
        podman_services_quadlet_dir="/var/lib/podman-adminer/.config/containers/systemd",
    )

    assert "ContainerName=adminer" in rendered
    assert f"Image={normalized['image']}" in rendered
    assert "Network=adminer.network" in rendered
    assert "PublishPort=192.0.2.10:18080:8080/tcp" in rendered
    assert "After=network-online.target" in rendered
    assert "Restart=on-failure" in rendered
    assert "RestartSec=10s" in rendered
    assert "WantedBy=default.target" in rendered
    assert "NoNewPrivileges=true" in rendered
    assert "overlay" not in rendered


def test_real_thelounge_catalog_contract_normalizes_and_renders_rootless_bind_quadlets_without_mutation():
    catalog_filters = load_module(
        REPO_ROOT / "ansible/filter_plugins/service_catalog.py",
        "service_catalog_thelounge_repository",
    )
    podman_filters = load_module(
        REPO_ROOT / "ansible/roles/podman_services/filter_plugins/podman_services.py",
        "podman_services_thelounge_repository",
    )
    common_filters = load_module(
        REPO_ROOT / "ansible/roles/service_common/filter_plugins/service_common.py",
        "service_common_thelounge_repository",
    )
    source = load_services()["thelounge"]
    original = deepcopy(source)
    entry = catalog_filters.service_catalog_effective({"thelounge": source}, "manager")[0]
    effective = catalog_filters.service_catalog_merge_target(source)
    rendered_effective = render_structure(
        deepcopy(effective),
        {
            "hostvars": {
                "manager": {
                    "container_host_appdata_root": "/opt/appdata",
                    "container_host_puid": 1000,
                    "container_host_pgid": 1000,
                    "local_ip": "192.0.2.10",
                }
            },
            "local_ip": "192.0.2.10",
            "services_controller_host": "manager",
            "services_public_zone": "public.example",
            "services_internal_zone": "private.example.internal",
            "services_private_https_port": 9443,
            "timezone": "Australia/Melbourne",
        },
    )
    normalized = podman_filters.podman_service_normalize(rendered_effective, "thelounge")
    traefik = common_filters.service_common_traefik_context(
        rendered_effective,
        "thelounge",
        ["manager"],
        "public.example",
        "private.example.internal",
        {"manager": {"local_ip": "192.0.2.10"}},
    )
    quadlet_dir = "/var/lib/podman-thelounge/.config/containers/systemd"
    container_template = Environment(trim_blocks=True, lstrip_blocks=True).from_string(
        (REPO_ROOT / "ansible/roles/podman_services/templates/container.container.j2").read_text()
    )
    network_template = Environment(trim_blocks=True, lstrip_blocks=True).from_string(
        (REPO_ROOT / "ansible/roles/podman_services/templates/network.network.j2").read_text()
    )
    container = container_template.render(
        podman_service=normalized,
        podman_services_quadlet_dir=quadlet_dir,
    )
    network = network_template.render(podman_service=normalized)

    assert entry["runtime"] == "podman"
    assert entry["dispatch_host"] == "{{ services_controller_host }}"
    assert "stack" not in effective
    assert {"profile", "constraints", "mode", "replicas"}.isdisjoint(effective["deploy"])
    assert normalized["execution"] == {
        "mode": "rootless",
        "host_user": "podman-thelounge",
        "userns": {"mode": "keep-id", "uid": "1000", "gid": "1000"},
    }
    assert effective["user"] == "0:0"
    assert normalized["container"]["uid"] == "0"
    assert normalized["container"]["gid"] == "0"
    assert normalized["host_paths"] == [
        {
            "path": "/opt/appdata/thelounge",
            "state": "directory",
            "mode": "0750",
        }
    ]
    assert normalized["container"]["mounts"] == [
        {
            "source": "/opt/appdata/thelounge",
            "target": "/config",
            "read_only": False,
        }
    ]
    assert normalized["container"]["ports"] == [
        {
            "host": 19000,
            "container": 9000,
            "protocol": "tcp",
            "host_ip": "192.0.2.10",
        }
    ]
    assert normalized["env"] == {
        "TZ": "Australia/Melbourne",
        "PUID": 1000,
        "PGID": 1000,
        "UMASK": "022",
    }
    assert str(normalized["env"]["PUID"]) == normalized["execution"]["userns"]["uid"]
    assert str(normalized["env"]["PGID"]) == normalized["execution"]["userns"]["gid"]
    assert normalized["container"]["systemd"] == {
        "after": ["network-online.target"],
        "restart": "on-failure",
        "restart_sec": "10s",
        "timeout_start_sec": "900s",
    }
    assert traefik["backend_url"] == "http://192.0.2.10:19000"
    assert "NetworkName=thelounge" in network
    assert "Driver=bridge" in network
    assert "Network=thelounge.network" in container
    assert "PublishPort=192.0.2.10:19000:9000/tcp" in container
    assert "Volume=/opt/appdata/thelounge:/config" in container
    assert "UserNS=keep-id:uid=1000,gid=1000" in container
    assert f"EnvironmentFile={quadlet_dir}/thelounge.env" in container
    assert "User=0" in container
    assert "Group=0" in container
    assert "NoNewPrivileges=true" in container
    assert "Tmpfs=/run" not in container
    assert "After=network-online.target" in container
    assert "Restart=on-failure" in container
    assert "RestartSec=10s" in container
    assert "TimeoutStartSec=900s" in container
    assert "WantedBy=default.target" in container
    assert "overlay" not in container
    assert source == original
