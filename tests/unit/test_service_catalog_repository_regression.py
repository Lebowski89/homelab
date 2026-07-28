import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, meta

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_DIR = REPO_ROOT / "ansible/group_vars/all/services"
PLAYBOOK_PATH = REPO_ROOT / "ansible/playbook.yml"
DOCKER_INIT_PATH = REPO_ROOT / "ansible/roles/docker_services/tasks/_init.yml"
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


def test_service_catalog_preserves_existing_docker_expansion_ordering():
    docker_filters = load_module(REPO_ROOT / "ansible/filter_plugins/docker_services.py", "docker_services")
    catalog_filters = load_module(REPO_ROOT / "ansible/filter_plugins/service_catalog.py", "service_catalog")
    services = load_services()

    legacy = docker_filters.docker_services_effective(services)
    effective = catalog_filters.service_catalog_effective(services, "manager")
    catalog_docker = [
        {key: value for key, value in item.items() if key not in {"runtime", "dispatch_host"}}
        for item in catalog_filters.service_catalog_by_runtime(effective, "docker")
    ]

    assert catalog_docker == legacy


def selected_without_runtime(items):
    return [{key: value for key, value in item.items() if key not in {"runtime", "dispatch_host"}} for item in items]


def assert_selector_parity(services, run_tags=None, run_all=False, allow_disabled=False):
    docker_filters = load_module(REPO_ROOT / "ansible/filter_plugins/docker_services.py", "docker_services")
    catalog_filters = load_module(REPO_ROOT / "ansible/filter_plugins/service_catalog.py", "service_catalog")

    legacy_effective = docker_filters.docker_services_effective(services)
    legacy_selected = docker_filters.docker_services_select(legacy_effective, run_tags, run_all, allow_disabled)

    catalog_effective = catalog_filters.service_catalog_effective(services, "manager")
    catalog_selected = catalog_filters.service_catalog_select(catalog_effective, run_tags, run_all, allow_disabled)
    catalog_docker_selected = catalog_filters.service_catalog_by_runtime(catalog_selected["selected"], "docker")

    assert selected_without_runtime(catalog_docker_selected) == legacy_selected["selected"]


def test_service_catalog_preserves_docker_selector_parity_for_real_services():
    services = load_services()
    assert_selector_parity(services, run_tags=["authelia"])
    assert_selector_parity(services, run_tags=["media"])
    assert_selector_parity(services, run_tags=["qbittorrent-xs"])
    assert_selector_parity(services, run_all=True)

    disabled_name = next(name for name, cfg in services.items() if cfg["runtime"] == "docker" and cfg.get("enabled") is False)
    assert_selector_parity(services, run_tags=[disabled_name], allow_disabled=False)
    assert_selector_parity(services, run_tags=[disabled_name], allow_disabled=True)


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
        effective["infisical"]["fail_on_empty"],
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


def test_real_traefik_services_retain_lookup_only_cloudflare_zone_declaration():
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
        assert declared.count("cloudflare_zone") == 1, identity
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
        ("homepage", "<base>"),
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
    assert "service_catalog_merge_target" not in str(docker_include["vars"])
    assert "service_catalog_merge_target" not in str(podman_include["vars"])

    docker_init = yaml.safe_load(DOCKER_INIT_PATH.read_text())
    docker_config = task_named(docker_init, "Init | Use catalog-resolved service config")
    docker_assert = task_named(docker_init, "Init | Ensure docker_services_service_cfg is provided")
    podman_init = yaml.safe_load(PODMAN_INIT_PATH.read_text())
    podman_assert = task_named(podman_init, "Init | Assert catalog-resolved service config")

    assert docker_config["ansible.builtin.set_fact"]["docker_services_svc"] == "{{ docker_services_service_cfg }}"
    adapter_tasks = "\n".join(path.read_text() for tasks_dir in (DOCKER_TASKS_DIR, PODMAN_TASKS_DIR) for path in tasks_dir.rglob("*.yml"))
    assert "merge_target" not in adapter_tasks
    assert "docker_services_service_cfg.targets is not defined" in docker_assert["ansible.builtin.assert"]["that"]
    assert "podman_services_service_cfg.targets is not defined" in podman_assert["ansible.builtin.assert"]["that"]
