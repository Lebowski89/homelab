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
NATIVE_GROUPS = {
    "tags_podman": ["mgt"],
    "tags_node_exporter": ["mgt", "plex"],
    "tags_keepalived": ["mgt", "plex"],
    "tags_technitium_native": ["mgt", "plex"],
}
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


def catalog_items(filters, services, manager, groups=None):
    source = deepcopy(services)
    variables = {"services_controller_host": manager, "services_storage_host": "unraid", "services_plex_host": "plex"}
    for service in source.values():
        for cfg in [service, *service.get("targets", {}).values()]:
            if "hosts" in cfg.get("deploy", {}):
                cfg["deploy"]["hosts"] = render_structure(cfg["deploy"]["hosts"], variables)
    inventory = {"all": [manager, "mgt", "unraid", "plex", "blacktop", "docker-a", "docker-b"], **NATIVE_GROUPS, **(groups or {})}
    return filters.service_catalog_effective(source, manager, inventory)


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

    effective = catalog_items(catalog_filters, load_services(), "manager", NATIVE_GROUPS)

    assert effective
    assert all("config" not in item for item in effective)
    assert all(
        set(item)
        <= {"name", "target", "runtime", "tags", "enabled", "dispatch_host", "resolved_hosts", "podman_lifecycle", "placement_error"}
        for item in effective
    )
    assert all("podman_lifecycle" not in item for item in effective if item["runtime"] == "docker")
    assert all("podman_lifecycle" in item for item in effective if item["runtime"] == "podman")


def test_real_repository_resolved_hosts_are_lightweight_and_runtime_specific():
    catalog_filters = load_module(
        REPO_ROOT / "ansible/filter_plugins/service_catalog.py",
        "service_catalog_repository_dispatch",
    )
    services = load_services()
    effective = catalog_items(catalog_filters, services, "manager", NATIVE_GROUPS)
    seen_runtimes = set()

    for item in effective:
        service = catalog_filters.service_catalog_merge_target(services[item["name"]], item.get("target"))
        deploy = service.get("deploy", {})
        if item["runtime"] == "docker":
            deploy_type = str(deploy.get("type", "swarm") or "swarm").strip()
            expected_host = "manager" if deploy_type == "swarm" else item["resolved_hosts"][0]
        else:
            expected_host = item["resolved_hosts"][0]

        identity = f"{item['name']}:{item.get('target', '<base>')}"
        assert item["dispatch_host"] == expected_host, identity
        assert "config" not in item, identity
        seen_runtimes.add(item["runtime"])

    assert seen_runtimes == catalog_filters.VALID_RUNTIMES


def test_real_repository_resolved_hosts_match_repository_host_definitions():
    catalog_filters = load_module(
        REPO_ROOT / "ansible/filter_plugins/service_catalog.py",
        "service_catalog_repository_hosts",
    )
    services = deepcopy(load_services())
    host_context = {
        "services_controller_host": "mgt",
        "services_storage_host": "unraid",
        "services_plex_host": "plex",
    }
    for service in services.values():
        configurations = [service, *(service.get("targets", {}) or {}).values()]
        for configuration in configurations:
            deploy = configuration.get("deploy", {})
            host = deploy.get("hosts")
            if isinstance(host, str) and "{{" in host:
                deploy["hosts"] = NativeEnvironment(undefined=StrictUndefined).from_string(host).render(**host_context)

    effective = catalog_items(catalog_filters, services, "mgt", NATIVE_GROUPS)
    repository_hosts = {path.stem for path in (REPO_ROOT / "ansible/host_vars").glob("*.yml")}
    repository_hosts.update(path.name for path in (REPO_ROOT / "terraform/proxmox/vms").iterdir() if path.is_dir())
    netbox_locals = (REPO_ROOT / "terraform/netbox/locals.tf").read_text().split("base_hosts = {", 1)[1]
    netbox_base_hosts = netbox_locals.split("\n  }\n", 1)[0]
    repository_hosts.update(re.findall(r"^    ([a-z0-9_-]+) = \{$", netbox_base_hosts, re.MULTILINE))

    assert effective
    assert all(entry["dispatch_host"] in repository_hosts for entry in effective)


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
    original = deepcopy(services)

    for item in catalog_items(catalog_filters, services, "manager", NATIVE_GROUPS):
        if item["runtime"] != "podman":
            continue
        effective = catalog_filters.service_catalog_merge_target(services[item["name"]], item.get("target"))
        rendered_effective = render_structure(
            deepcopy(effective),
            {
                "hostvars": {
                    "manager": {
                        "container_host_appdata_root": "/opt",
                        "container_host_puid": 1000,
                        "container_host_pgid": 1000,
                        "local_ip": "192.0.2.10",
                    },
                    "blacktop": {
                        "container_host_appdata_root": "/opt/appdata",
                        "container_host_data_root": "/opt/data",
                        "container_host_puid": 1000,
                        "container_host_pgid": 1000,
                        "local_ip": "192.0.2.40",
                    },
                },
                "local_ip": "192.0.2.10",
                "inventory_hostname": "manager",
                "services_log_root": "/var/log/skynet",
                "podman_shared_network_name": "mgt-services",
                "services_controller_host": "manager",
                "services_public_zone": "public.example",
                "services_internal_zone": "private.example.internal",
                "services_lan_cidr": "192.0.2.0/24",
                "services_private_https_port": 9443,
                "timezone": "Australia/Melbourne",
            },
        )
        normalized = podman_filters.podman_service_normalize(rendered_effective, item.get("target", item["name"]))
        assert normalized["image"] == rendered_effective["image"]
        checked.append((item["name"], item.get("target")))

    assert checked
    assert services == original


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

    for item in catalog_items(catalog_filters, services, "manager", NATIVE_GROUPS):
        effective = catalog_filters.service_catalog_merge_target(services[item["name"]], item.get("target"))
        infisical = effective.get("infisical", {})
        normalized = common_filters.service_common_infisical_normalize(
            render_structure(
                infisical.get("secrets_map", []),
                {
                    "services_controller_host": "synthetic-controller",
                    "hostvars": {"synthetic-controller": {"container_host_puid": 2301, "container_host_pgid": 2402}},
                },
            ),
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

    assert checked


def test_real_docker_swarm_constraints_match_configured_node_label_values():
    catalog_filters = load_module(
        REPO_ROOT / "ansible/filter_plugins/service_catalog.py",
        "service_catalog_repository_swarm_constraints",
    )
    services = load_services()
    expected_by_host = {
        "{{ services_plex_host }}": "node.labels.docker_services_host == docker_services_plex_host",
        "{{ services_storage_host }}": "node.labels.docker_services_host == docker_services_unraid_host",
    }
    observed = set()

    for item in catalog_items(catalog_filters, services, "manager", NATIVE_GROUPS):
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
        expected = expected_by_host.get(deploy.get("hosts"))
        assert expected is not None, f"{item['name']}/{target} has an unknown constrained deploy host"
        assert host_constraints == [expected], f"{item['name']}/{target} has a mismatched Swarm host constraint"
        observed.add(expected)

    assert observed == set(expected_by_host.values())


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

    for item in catalog_items(catalog_filters, services, "manager", NATIVE_GROUPS):
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

    for item in catalog_items(catalog_filters, services, "manager", NATIVE_GROUPS):
        effective = catalog_filters.service_catalog_merge_target(services[item["name"]], item.get("target"))
        if effective.get("env_file"):
            actual.add((item["name"], item.get("target", "<base>")))

    assert actual == {
        ("authelia", "main"),
        ("gotify", "<base>"),
        ("grafana", "<base>"),
        ("opencloud", "<base>"),
        ("qbittorrent", "alpha"),
        ("qbittorrent", "bravo"),
        ("qui", "alpha"),
        ("qui", "bravo"),
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
    for filter_name in (
        "availability_http_file_sd",
        "availability_direct_http_file_sd",
        "availability_icmp_file_sd",
        "availability_tcp_file_sd",
        "availability_postgres_file_sd",
        "availability_patroni_file_sd",
        "availability_etcd_file_sd",
        "to_nice_json",
    ):
        environment.filters[filter_name] = lambda value, *args, **kwargs: value
    checked = []

    for item in catalog_items(catalog_filters, services, "manager", NATIVE_GROUPS):
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
            "deploy": {"type": "container", "hosts": "docker-a"},
        },
        "second": {
            "runtime": "docker",
            "deploy": {"type": "container", "hosts": "docker-b"},
        },
    }

    selected = catalog_filters.service_catalog_select(
        catalog_items(catalog_filters, services, "manager", NATIVE_GROUPS),
        run_all=True,
    )["selected"]

    assert [(entry["name"], entry["dispatch_host"]) for entry in selected] == [
        ("first", "docker-a"),
        ("second", "docker-b"),
    ]


def test_service_play_gathers_facts_only_for_selected_operations_and_hosts():
    play = next(play for play in yaml.safe_load(PLAYBOOK_PATH.read_text()) if play.get("hosts") == "tags_skynet")
    assert play["gather_facts"] is False
    assert play["any_errors_fatal"] is True
    setups = [task for task in play["tasks"] if "ansible.builtin.setup" in task]
    selected = next(task for task in setups if "service_catalog_selected" in str(task.get("when")))
    assert "resolved_hosts" in str(selected["when"])
    assert {"deploy", "update", "remove", "recreate"} <= set(selected["tags"])
    assert all(task.get("when") for task in setups)
    # Native applications have one catalogue path, with no standalone includes.
    assert not any(task.get("ansible.builtin.include_role", {}).get("name") == "native_services" for task in play["tasks"])


def test_playbook_processes_one_globally_ordered_lightweight_catalog_loop():
    play = next(play for play in yaml.safe_load(PLAYBOOK_PATH.read_text()) if play.get("hosts") == "tags_skynet")
    assert play["strategy"] == "linear"
    dispatch = next(
        task for task in play["tasks"] if task.get("ansible.builtin.include_tasks", {}).get("file") == "tasks/service_catalog_dispatch.yml"
    )
    assert dispatch["loop"] == "{{ service_catalog_selected }}"
    assert dispatch["loop_control"]["loop_var"] == "service_catalog_dispatch_entry"
    assert set(dispatch["tags"]) <= set(dispatch["ansible.builtin.include_tasks"]["apply"]["tags"])
    routes = list(walk_mappings(yaml.safe_load(GLOBAL_DISPATCH_PATH.read_text())))
    materialize = next(task for task in routes if "service_catalog_materialize" in task)
    assert "resolved_hosts" in materialize["when"]
    assert materialize["service_catalog_materialize"]["source_var"] == "svcfiles"
    native = next(task for task in routes if task.get("ansible.builtin.include_role", {}).get("name") == "native_services")
    assert 'service_catalog_dispatch_entry.runtime == "native"' in native["when"]
    assert "inventory_hostname in service_catalog_dispatch_entry.resolved_hosts" in native["when"]
    for route in routes:
        include = route.get("ansible.builtin.include_tasks", {})
        if include.get("file") in {"service_catalog_dispatch_docker.yml", "service_catalog_dispatch_podman.yml"}:
            assert "inventory_hostname == service_catalog_dispatch_entry.dispatch_host" in route["when"]
            assert set(route["tags"]) <= set(include["apply"]["tags"])
    assert "delegate_to" not in GLOBAL_DISPATCH_PATH.read_text()
    # Adapters receive the selected host-local materialization; they must not
    # independently merge the whole catalogue or leak the previous service.
    for path, prefix in ((DOCKER_DISPATCH_PATH, "docker_services"), (PODMAN_DISPATCH_PATH, "podman_services")):
        tasks = yaml.safe_load(path.read_text())
        facts = [task["ansible.builtin.set_fact"] for task in tasks if "ansible.builtin.set_fact" in task]
        assert facts[0][prefix + "_dispatch_config"] == {}
        assert any(prefix + "_dispatch_config" in fact and "config" in str(fact[prefix + "_dispatch_config"]) for fact in facts[1:])
        assert "svcfiles" not in path.read_text()
        assert "service_catalog_merge_target" not in path.read_text()


def test_real_vpn_namespace_stack_has_managed_provider_edges_and_safe_recreate_order():
    catalog_filters = load_module(
        REPO_ROOT / "ansible/filter_plugins/service_catalog.py",
        "service_catalog_namespace_lifecycle_repository",
    )
    services = load_services()
    effective = catalog_items(catalog_filters, services, "manager", NATIVE_GROUPS)
    selected = catalog_filters.service_catalog_select(effective, ["gluetun_stack"])["selected"]

    plan = catalog_filters.service_catalog_podman_lifecycle_plan(effective, selected, "recreate")

    assert plan["dependencies"] == [
        {"consumer": "jdownloader2", "provider": "gluetun", "host": "blacktop"},
        {"consumer": "mullvad_browser", "provider": "gluetun", "host": "blacktop"},
    ]
    assert [entry["name"] for entry in plan["selected"]] == ["gluetun", "jdownloader2", "mullvad_browser"]
    dependents = plan["selected"][0]["podman_lifecycle"]["namespace_dependents"]
    assert [dependent["unit_name"] for dependent in dependents] == [
        "jdownloader2.service",
        "mullvad-browser.service",
    ]


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
            "deploy": {"hosts": "manager"},
            "command": ["serve"],
        },
        "podman-app": {
            "runtime": "podman",
            "image": "example.invalid/podman-app:1.0.0",
            "deploy": {"type": "container", "hosts": "manager"},
        },
    }
    selected = catalog_filters.service_catalog_select(
        catalog_items(catalog_filters, services, "manager", NATIVE_GROUPS),
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
