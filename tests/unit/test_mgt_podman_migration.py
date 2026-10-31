"""Exercise migration contracts with real catalog merges and isolated rendering."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
from copy import deepcopy
from functools import cache
from pathlib import Path

import pytest
import yaml
from ansible.errors import AnsibleFilterError
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from jinja2.nativetypes import NativeEnvironment

ROOT = Path(__file__).resolve().parents[2]


def plugin(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PODMAN = plugin("ansible/roles/podman_services/filter_plugins/podman_services.py", "migration_podman")
CATALOG = plugin("ansible/filter_plugins/service_catalog.py", "migration_catalog")
COMMON = plugin("ansible/roles/service_common/filter_plugins/service_common.py", "migration_common")


def context():
    hosts = {
        name: {
            "local_ip": f"192.0.2.{number}",
            "container_host_appdata_root": "/opt",
            "container_host_data_root": "/opt/data",
            "container_host_puid": "1000",
            "container_host_pgid": "1000",
        }
        for name, number in [("mgt", 10), ("unraid", 11), ("plex", 12)]
    }
    return {
        **catalog(),
        "hostvars": hosts,
        "groups": {"all": ["mgt", "unraid", "plex", "blacktop", "worker", "manager"]},
        "local_ip": hosts["mgt"]["local_ip"],
        "inventory_hostname": "mgt",
        "services_controller_host": "mgt",
        "services_storage_host": "unraid",
        "prometheus_worker_metrics_address": NativeEnvironment(undefined=StrictUndefined)
        .from_string(yaml.safe_load((ROOT / "ansible/group_vars/all/prometheus.yml").read_text())["prometheus_worker_metrics_address"])
        .render(hostvars=hosts, services_storage_host="unraid", haproxy=catalog()["haproxy"]),
        "services_plex_host": "plex",
        "services_log_root": "/var/log/skynet",
        "services_internal_zone": "int.example.test",
        "services_private_https_port": 8443,
        "timezone": "Australia/Melbourne",
        "podman_shared_network_name": "mgt-services",
    }


@cache
def native_template(source):
    return NativeEnvironment(undefined=StrictUndefined).from_string(source)


def resolve(value, variables):
    if isinstance(value, dict):
        return {key: resolve(item, variables) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve(item, variables) for item in value]
    if isinstance(value, str) and ("{{" in value or "{%" in value):
        return native_template(value).render(**variables)
    return value


def catalog():
    # Tests may edit their catalog; only the parsed immutable baseline is shared.
    return deepcopy(_catalog())


@cache
def _catalog():
    result = {}
    for file in sorted((ROOT / "ansible/group_vars/all/services").glob("*.yml")):
        result.update(yaml.safe_load(file.read_text()))
    return result


def catalog_items(services, manager="mgt", **options):
    source = deepcopy(services)
    variables = context() | {"services_controller_host": manager}
    for service in source.values():
        for cfg in [service, *service.get("targets", {}).values()]:
            if "hosts" in cfg.get("deploy", {}):
                cfg["deploy"]["hosts"] = resolve(cfg["deploy"]["hosts"], variables)
    return CATALOG.service_catalog_effective(source, manager, variables["groups"], **options)


def mgt_entries(services):
    variables = context()
    return [
        entry
        for entry in catalog_items(services, "mgt")
        if entry["enabled"] and entry["runtime"] == "podman" and resolve(entry["dispatch_host"], variables) == "mgt"
    ]


def worker_backend_entries(services):
    entries = []
    for entry in catalog_items(services, "mgt"):
        cfg = CATALOG.service_catalog_merge_target(services[entry["name"]], entry.get("target"))
        if (
            entry["enabled"]
            and entry["runtime"] == "docker"
            and ("web_backend" in cfg.get("ports", {}) or "worker_backends" in cfg.get("operational_requirements", {}).get("acl", []))
        ):
            entries.append(entry)
    return entries


@cache
def renderer():
    env = Environment(
        loader=FileSystemLoader(ROOT / "ansible/roles/podman_services/templates"),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters.update(PODMAN.FilterModule().filters())
    return env


def render_container(service):
    return (
        renderer()
        .get_template("container.container.j2")
        .render(
            podman_service=service,
            podman_services_quadlet_dir="/etc/containers/systemd",
        )
    )


def test_real_mgt_selection_normalizes_without_swarm_leakage_and_keeps_rootless_stores():
    services = catalog()
    before = deepcopy(services)
    selected = mgt_entries(services)
    counts = {"rootful": 0, "rootless": 0}
    for item in selected:
        cfg = resolve(CATALOG.service_catalog_merge_target(services[item["name"]], item.get("target")), context())
        normalized = PODMAN.podman_service_normalize(cfg, item["name"])
        assert normalized["container"]["host"] == "mgt"
        counts[normalized["execution"]["mode"]] += 1
        unit = render_container(normalized)
        assert "LogDriver=journald" in unit
        assert "WantedBy=" in unit
        assert not any(field in cfg for field in ["stack", "swarm_configs", "configs", "container_name", "named_volumes"])
        if normalized["execution"]["mode"] == "rootful" and cfg.get("network_mode") != "host":
            network = normalized["network"]
            assert f"Requires={network['name']}-network.service" in unit
            if network["external"]:
                assert network == {"name": "mgt-services", "external": True}
            else:
                # Rootful applications may own a bridge, as accepted for UniFi.
                assert network["driver"] == "bridge"
    # Exercise both supported execution modes without freezing the service census.
    assert counts["rootful"] > 0 and counts["rootless"] > 0
    assert services == before
    assert all(item["runtime"] == "podman" for item in selected)
    planned = CATALOG.service_catalog_podman_lifecycle_plan(catalog_items(services, "mgt"), selected, "deploy")["selected"]
    # Cross-account network dependencies never become user-manager edges.
    assert len(planned) == len(selected)
    for item in planned:
        cfg = resolve(CATALOG.service_catalog_merge_target(services[item["name"]], item.get("target")), context())
        normalized = PODMAN.podman_service_normalize(cfg, item["name"])
        if normalized["execution"]["mode"] == "rootless":
            if normalized["container"].get("network_mode") == "pasta":
                assert normalized["network"] is None
            else:
                assert not normalized["network"]["external"]
            assert not cfg.get("systemd", {}).get("requires")
            assert not cfg.get("systemd", {}).get("wants")
            assert "mgt-services" not in render_container(normalized)


def test_worker_routes_match_unique_published_ports_without_changing_container_listeners():
    services = catalog()
    selected = worker_backend_entries(services)
    allocated = set()
    for item in selected:
        cfg = resolve(CATALOG.service_catalog_merge_target(services[item["name"]], item.get("target")), context())
        assert cfg["runtime"] == "docker"
        route = cfg.get("traefik", {})
        if not route.get("enable"):
            continue
        assert route["backend_mode"] == "host"
        target_host = route["backend_host_inventory"]
        port = cfg["ports"]["web_backend"]
        assert port["published"] == route["port"]
        assert port["mode"] == "host"
        assert "host_ip" not in port
        key = (target_host, port["published"])
        assert key not in allocated
        allocated.add(key)
        result = COMMON.service_common_traefik_context(
            name=cfg["name"],
            service=cfg,
            internal_zone="int.example.test",
            target_hosts=[target_host],
            inventory_hosts=context()["hostvars"],
        )
        assert result["backend_url"] == f"http://{context()['hostvars'][target_host]['local_ip']}:{port['published']}"
        if item["name"] == "qbittorrent":
            env = Environment(loader=FileSystemLoader(ROOT / "ansible/roles/service_common/templates"), undefined=StrictUndefined)
            rendered = env.get_template("configs/qbittorrent/qBittorrent.env.j2").render(
                service_common_service=cfg, services_lan_cidr="192.0.2.0/24"
            )
            assert f"WEBUI_PORTS={port['target']}/tcp,{port['target']}/udp" in rendered
            conf = env.get_template("configs/qbittorrent/qBittorrent.conf.j2").render(
                service_common_service=cfg,
                service_common_infisical_values={"qbittorrent_user": "NONPRODUCTION", "qbittorrent_api": "NONPRODUCTION_API"},
                service_common_template_vars={"qbittorrent_pass_pbkdf2": "NONPRODUCTION"},
                **context(),
            )
            assert f"WebUI\\Port={port['target']}" in conf
            assert "WebUI\\APIKey=NONPRODUCTION_API" in conf
            assert f"Session\\DefaultSavePath={cfg['volumes']['media']['target']}/completed" in conf
            assert f"Session\\TempPath={cfg['volumes']['media']['target']}/incoming" in conf
            assert "172.98.0.0/24;192.0.2.10" in conf
    assert allocated
    for name in ["haproxy", "alloy"]:
        worker = CATALOG.service_catalog_merge_target(services[name], "workers")
        assert worker["runtime"] == "docker"
        assert worker["stack"] == name
        assert worker["deploy"]["mode"] == "global"
        assert "node.labels.ansible_host != {{ services_controller_host }}" in worker["deploy"]["constraints"]


def test_dotenv_is_literal_quoted_and_ordered_with_explicit_overrides():
    first = PODMAN.podman_dotenv('A=\'NONPRODUCTION $key %n\'\nB=one\nC="a \\"quote\\""\nD=unquoted # comment\nE=$(printf fake)\n')
    second = PODMAN.podman_dotenv("B=two\n")
    merged = first | second | {"B": "explicit"}
    assert merged == {"A": "NONPRODUCTION $key %n", "B": "explicit", "C": 'a "quote"', "D": "unquoted", "E": "$(printf fake)"}
    for invalid in ["export A=NONPRODUCTION", "UNSET", "A='NONPRODUCTION\ncontinued'", 'A="bad\\q"', "A=abc\\"]:
        with pytest.raises(AnsibleFilterError) as failure:
            PODMAN.podman_dotenv(invalid)
        assert "NONPRODUCTION" not in str(failure.value)


def test_config_changes_restart_only_declared_application_files():
    assert COMMON.service_common_files_changed({"results": [{"changed": True, "file": {"dest": "/opt/config"}}]}, "file")
    assert not COMMON.service_common_files_changed({"results": [{"changed": True, "file": {"restart": False}}]}, "file")
    assert not COMMON.service_common_files_changed({"results": [{"changed": False, "file": {}}]}, "file")
    metadata = {"results": [{"changed": True, "stat_result": {"declaration": {"restart": False}}}]}
    assert not COMMON.service_common_files_changed(metadata, "stat_result", "declaration")
    metadata["results"][0]["stat_result"]["declaration"]["restart"] = True
    assert COMMON.service_common_files_changed(metadata, "stat_result", "declaration")
    with pytest.raises(AnsibleFilterError):
        COMMON.service_common_file_policy({"templates": [{"restart": "false"}]})


@pytest.mark.integration
def test_generator_preserves_argv_and_shell_substitution_using_only_fake_files(tmp_path):
    generator = Path("/usr/lib/systemd/system-generators/podman-system-generator")
    if not generator.is_file():
        pytest.skip("Local isolated Quadlet generator unavailable")
    fake_file = tmp_path / "fake-secret"
    fake_file.write_text("NONPRODUCTION-quoted-value")
    argv = ["sh", "-c", f'printf "%s" "$(cat {fake_file})"', 'literal $VARIABLE ${VARIABLE} %n "quote" \\']
    cfg = {"runtime": "podman", "image": "registry.example.invalid/fake:1.0", "command": argv}
    service = PODMAN.podman_service_normalize(cfg, "fake")
    (tmp_path / "fake.container").write_text(render_container(service))
    result = subprocess.run(
        [str(generator), "--dryrun"], env=dict(os.environ, QUADLET_UNIT_DIRS=str(tmp_path)), capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    line = next(line for line in result.stdout.splitlines() if line.startswith("ExecStart="))
    # The generator uses systemd C escapes, including \x20 for spaces.
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|[^\s]+', line.partition("=")[2])
    generated = [ast.literal_eval(token) if token.startswith('"') else token for token in tokens]
    actual = generated[generated.index(cfg["image"]) + 1 :]
    actual = [arg.replace("$$", "$").replace("%%", "%") for arg in actual]
    assert actual == argv
    executed = subprocess.run(actual, capture_output=True, text=True)
    assert executed.returncode == 0
    assert executed.stdout == "NONPRODUCTION-quoted-value"
    for invalid in ["sh -c echo", [], ["echo", ""], ["echo", "line\nbreak"]]:
        with pytest.raises(AnsibleFilterError):
            PODMAN.podman_quadlet_argv(invalid)


def test_host_network_and_typed_systemd_options_reject_conflicting_or_unsafe_inputs():
    cfg = {"runtime": "podman", "image": "registry.example.invalid/fake:1.0", "network_mode": "host"}
    assert "Network=host" in render_container(PODMAN.podman_service_normalize(cfg, "fake"))
    for field, value in [
        ("ports", [{"published": 53, "target": 53}]),
        ("named_networks", {"bridge": {}}),
        ("deploy", {"execution": {"mode": "rootless", "host_user": "podman-fake"}}),
    ]:
        with pytest.raises(AnsibleFilterError):
            PODMAN.podman_service_normalize(cfg | {field: value}, "fake")
    for field, value in [
        ("cgroup", "private"),
        ("tmpfs", ["/tmp:untrusted=flag"]),
        ("runtime_options", {"podman": {"args": "--privileged"}}),
        ("systemd", {"requires": ["foo.service\nExecStart=bad"]}),
    ]:
        with pytest.raises(AnsibleFilterError):
            PODMAN.podman_service_normalize({"runtime": "podman", "image": cfg["image"], field: value}, "fake")
    for invalid in [{"notify_healthy": "true"}, {"notify_healthy": True}, {"notify_healthy": True, "healthcheck": {"test": ["NONE"]}}]:
        with pytest.raises(AnsibleFilterError, match="notify_healthy"):
            PODMAN.podman_service_normalize({"runtime": "podman", "image": cfg["image"]} | invalid, "fake")


@pytest.mark.integration
@pytest.mark.parametrize("role,count", [("netbox", 3), ("infisical", 2)])
def test_bootstrap_definitions_render_with_private_fake_inputs_without_inventory_or_secret_store(role, count, tmp_path):
    defaults = yaml.safe_load((ROOT / f"ansible/roles/{role}/defaults/main.yml").read_text())
    variables = context() | {
        "netbox_domain": "example.test",
        "container_host_appdata_root": "/opt",
        "container_host_puid": "1000",
        "container_host_pgid": "1000",
    }
    # Resolve role defaults in dependency order; fixtures never contain real values.
    variables.update(
        {key: "NONPRODUCTION-fake" for key in defaults if key.endswith(("_key", "_pass", "_password", "_user", "_email", "_sender"))}
    )
    pending = {key: value for key, value in defaults.items() if key not in variables and key != f"{role}_podman_services"}
    for _ in range(10):
        for key, value in list(pending.items()):
            try:
                variables[key] = resolve(value, variables)
            except Exception:
                continue
            del pending[key]
    definitions = resolve(defaults[f"{role}_podman_services"], variables)
    assert len(definitions) == count
    for cfg in definitions:
        without_tags = deepcopy(cfg)
        without_tags.pop("tags", None)
        with pytest.raises(AnsibleFilterError, match="services_bootstrap_acl_ready"):
            COMMON.service_common_requirements_validate(without_tags, cfg["name"], "recreate", {})
        inputs = {"services_bootstrap_acl_ready": True}
        if cfg.get("volumes"):
            with pytest.raises(AnsibleFilterError, match="services_rootless_data_ready"):
                COMMON.service_common_requirements_validate(without_tags, cfg["name"], "recreate", inputs)
            inputs["services_rootless_data_ready"] = {cfg["name"]: True}
        assert COMMON.service_common_requirements_validate(without_tags, cfg["name"], "recreate", inputs)
        normalized = PODMAN.podman_service_normalize(cfg, cfg["name"])
        targets = variables[f"{role}_podman_secret_targets"]
        normalized["secrets"] = PODMAN.podman_secret_declarations(
            [
                {"name": name, "var": name, "target": targets.get(name, "/run/secrets/" + name), "update_policy": "preserve"}
                for name in cfg["secrets"]
            ]
        )
        unit = render_container(normalized)
        assert "Notify=healthy" in unit
        assert "Network=" + normalized["network"]["name"] + ".network" in unit
        assert normalized["execution"]["mode"] == "rootless"
        assert f"User={cfg['user'].split(':')[0]}" in unit
        assert "NONPRODUCTION" not in unit
        for declaration in normalized["secrets"]:
            assert f"Secret={declaration['name']},target={declaration['target']},uid=0,gid=0,mode=0400" in unit
        directory = tmp_path / normalized["execution"]["host_user"]
        directory.mkdir()
        (directory / f"{normalized['unit_name']}.container").write_text(unit)
        (directory / f"{normalized['network']['name']}.network").write_text(
            renderer().get_template("network.network.j2").render(podman_service=normalized)
        )
    generator = Path("/usr/lib/systemd/system-generators/podman-system-generator")
    if generator.is_file():
        for directory in tmp_path.iterdir():
            result = subprocess.run(
                [str(generator), "--dryrun", "--user"],
                env=dict(os.environ, QUADLET_UNIT_DIRS=str(directory)),
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, result.stderr
            assert re.search(
                r"^---(?:.*/)?" + re.escape(directory.name.removeprefix("podman-") + ".service") + r"---$", result.stdout, re.MULTILINE
            )
    if role == "netbox":
        assert definitions[0]["volumes"]["data"]["target"] == "/var/lib/postgresql"
        assert definitions[-1]["environment"]["DB_HOST"] == variables["local_ip"]
        assert int(definitions[-1]["environment"]["DB_PORT"]) == definitions[0]["ports"]["database"]["published"]
        assert int(definitions[-1]["environment"]["REDIS_PORT"]) == definitions[1]["ports"]["cache"]["published"]
    else:
        assert definitions[-1]["environment"]["DB_CONNECTION_URI"].endswith("@192.0.2.10:5432/infisical?sslmode=disable")
        assert definitions[-1]["environment"]["REDIS_URL"].endswith("@192.0.2.10:16381")
    source = (ROOT / f"ansible/roles/{role}/tasks/service.yml").read_text()
    assert "name: podman_services" in source
    assert "service_common\n" not in source
    assert "NONPRODUCTION-check-only" in source


@pytest.mark.integration
def test_all_real_mgt_quadlets_generate_offline_in_their_own_execution_stores(tmp_path):
    generator = Path("/usr/lib/systemd/system-generators/podman-system-generator")
    if not generator.is_file():
        pytest.skip("Local isolated Quadlet generator unavailable")
    services = catalog()
    selected = mgt_entries(services)
    stores = {}
    for item in selected:
        cfg = resolve(CATALOG.service_catalog_merge_target(services[item["name"]], item.get("target")), context())
        normalized = PODMAN.podman_service_normalize(cfg, item["name"])
        owner = normalized["execution"].get("host_user", "root")
        stores.setdefault(owner, []).append(normalized)
    for owner, definitions in stores.items():
        directory = tmp_path / owner
        directory.mkdir()
        if owner == "root":
            central = ROOT / "ansible/roles/podman/templates/shared.network.j2"
            (directory / "mgt-services.network").write_text(
                Environment().from_string(central.read_text()).render(podman_shared_network_name="mgt-services")
            )
        for normalized in definitions:
            (directory / f"{normalized['unit_name']}.container").write_text(render_container(normalized))
            if normalized["network"] and not normalized["network"]["external"]:
                network = renderer().get_template("network.network.j2").render(podman_service=normalized)
                (directory / f"{normalized['network']['name']}.network").write_text(network)
            for volume in normalized["volumes"]:
                generated = renderer().get_template("volume.volume.j2").render(volume=volume, podman_service=normalized)
                (directory / f"{volume['name']}.volume").write_text(generated)
        result = subprocess.run(
            [str(generator), "--dryrun", *(["--user"] if owner != "root" else [])],
            env=dict(os.environ, QUADLET_UNIT_DIRS=str(directory)),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert "unsupported key" not in result.stderr.lower()
        for normalized in definitions:
            assert re.search(r"^---(?:.*/)?" + re.escape(normalized["unit_name"] + ".service") + r"---$", result.stdout, re.MULTILINE)
        if owner == "root":
            assert "--cgroupns=host --systemd=always" in result.stdout
            assert "Delegate=yes" in result.stdout


def test_alloy_readonly_config_provides_its_nested_writable_mountpoint(tmp_path):
    # Captured runc failure: the read-only /etc/alloy bind hid the directory
    # needed for its writable data mount. Derive the prerequisite from the real
    # normalized mounts, rather than permitting writes to the config directory.
    cfg = resolve(CATALOG.service_catalog_merge_target(catalog()["alloy"], "mgt"), context())
    normalized = PODMAN.podman_service_normalize(cfg, "alloy")
    mounts = normalized["container"]["mounts"]
    nested = [
        (parent, child)
        for parent in mounts
        for child in mounts
        if parent.get("read_only") is True and child.get("read_only") is False and Path(parent["target"]) in Path(child["target"]).parents
    ]
    assert nested, "regression must exercise a writable child under a read-only bind"
    required = [str(Path(parent["source"]) / Path(child["target"]).relative_to(parent["target"])) for parent, child in nested]

    def prepare_fixture(paths, directory):
        for declaration in paths:
            if declaration.get("state") == "directory":
                (directory / declaration["path"].lstrip("/")).mkdir(parents=True, exist_ok=True)
        return all((directory / name.lstrip("/")).is_dir() for name in required)

    original = [declaration for declaration in cfg["paths"] if declaration["path"] not in required]
    assert not prepare_fixture(original, tmp_path / "missing"), "old layout must lack the mountpoint"
    assert prepare_fixture(cfg["paths"], tmp_path / "prepared")
    rendered = render_container(normalized)
    for parent, child in nested:
        assert f"Volume={parent['source']}:{parent['target']}:ro" in rendered
        assert f"Volume={child['source']}:{child['target']}\n" in rendered
    assert normalized["execution"]["mode"] == "rootful"


@pytest.mark.integration
def test_bootstrap_registers_adapter_filters_without_catalog_preconditions(tmp_path):
    import sys

    definitions = [
        {"runtime": "podman", "name": "fake-db", "image": "registry.example.invalid/db:1.0", "command": ["echo", "NONPRODUCTION"]},
        {"runtime": "podman", "name": "fake-app", "image": "registry.example.invalid/app:1.0", "systemd": {"wants": ["fake-db.service"]}},
    ]
    play = [
        {
            "hosts": "localhost",
            "connection": "local",
            "gather_facts": False,
            "tasks": [
                {
                    "ansible.builtin.include_role": {"name": "podman_services", "tasks_from": "validate_definitions"},
                    "vars": {"podman_services_bootstrap_definitions": definitions},
                },
                {"ansible.builtin.assert": {"that": ["podman_services_bootstrap_validated.unit_name == 'fake-app'"]}},
            ],
        }
    ]
    path = tmp_path / "bootstrap-validation.yml"
    path.write_text(yaml.safe_dump(play))
    config = tmp_path / "ansible.cfg"
    config.write_text(
        f"[defaults]\nroles_path={ROOT}/ansible/roles\naction_plugins={ROOT}/ansible/action_plugins\nlibrary={ROOT}/ansible/library\ninventory=localhost,\nstdout_callback=default\n"
    )
    result = subprocess.run(
        [str(Path(sys.executable).with_name("ansible-playbook")), "-i", "localhost,", str(path), "--check"],
        env=dict(
            os.environ, ANSIBLE_CONFIG=str(config), ANSIBLE_LOCAL_TEMP=str(tmp_path / "local"), ANSIBLE_REMOTE_TEMP=str(tmp_path / "remote")
        ),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "failed=0" in result.stdout


def test_bootstrap_and_shared_network_lifecycle_guards_and_tag_propagation():
    for role in ["netbox", "infisical"]:
        tasks = yaml.safe_load((ROOT / f"ansible/roles/{role}/tasks/main.yml").read_text())
        names = [task["name"] for task in tasks]
        validate = next(i for i, name in enumerate(names) if "Validate all Quadlet" in name)
        first_mutation = next(i for i, name in enumerate(names) if "Stop consumers" in name)
        requirements = next(i for i, name in enumerate(names) if "Enforce every bootstrap requirement" in name)
        assert validate < requirements < first_mutation
        gate = tasks[requirements]
        assert set(gate["tags"]) <= set(gate["ansible.builtin.include_tasks"]["apply"]["tags"])
        prerequisite = yaml.safe_load((ROOT / f"ansible/roles/{role}/tasks/requirements.yml").read_text())[0]
        assert set(gate["tags"]) <= set(prerequisite["ansible.builtin.include_role"]["apply"]["tags"])
        assert f"{role}_podman_services" in gate["loop"]
        assert "service_common_requirements_metadata" in prerequisite["vars"]["service_common_service"]
        stop = next(task for task in tasks if "Stop consumers before providers" in task["name"])
        assert "not ansible_check_mode" in stop["when"]
        assert stop["ansible.builtin.include_role"]["tasks_from"] == "stop_bootstrap"
        loop = next(task for task in tasks if "Process bootstrap providers" in task["name"])
        assert f"{role}_remove" in loop["ansible.builtin.include_tasks"]["apply"]["tags"]
        assert "reverse" in loop["loop"]
        adapter = yaml.safe_load((ROOT / f"ansible/roles/{role}/tasks/service.yml").read_text())[-1]
        for action in ["bootstrap", "deploy", "recreate", "remove"]:
            assert f"{role}_{action}" in adapter["ansible.builtin.include_role"]["apply"]["tags"]
        text = (ROOT / f"ansible/roles/{role}/tasks/service.yml").read_text()
        assert f"{role}_podman_values: {{}}" in text
        assert "no_log: true" in text and "diff: false" in text
    shared = yaml.safe_load((ROOT / "ansible/roles/podman/tasks/shared_network.yml").read_text())
    assert not any(task.get("ansible.builtin.file", {}).get("state") == "absent" for task in shared)
    for task in shared:
        if "ansible.builtin.systemd_service" in task:
            assert "not ansible_check_mode" in task["when"]


@pytest.mark.integration
def test_real_cache_commands_keep_fake_credentials_out_of_argv_and_escape_config(tmp_path):
    service = CATALOG.service_catalog_merge_target(catalog()["authelia"], "redis")
    argv = resolve(service["command"], context())
    fake_secret = tmp_path / "fake-secret"
    fake_secret.write_text('NONPRODUCTION $token %n "quoted" \\slash')
    config = tmp_path / "runtime.conf"
    fake_server = tmp_path / "valkey-server"
    fake_server.write_text('#!/bin/sh\ncat "$1"\n')
    fake_server.chmod(0o700)
    argv[-1] = argv[-1].replace("/run/secrets/authelia_redis_secret", str(fake_secret)).replace("/tmp/skynet-valkey.conf", str(config))
    assert "--requirepass" not in argv[-1]
    assert "NONPRODUCTION" not in argv[-1]
    result = subprocess.run(argv, env=dict(os.environ, PATH=f"{tmp_path}:{os.environ['PATH']}"), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'requirepass "NONPRODUCTION $token %n \\"quoted\\" \\\\slash"\n'
    assert config.stat().st_mode & 0o777 == 0o600


@pytest.mark.integration
@pytest.mark.parametrize("proxy", [False, True])
def test_haproxy_uses_one_config_source_for_both_runtimes_and_keeps_overrides(tmp_path, proxy):
    source = ROOT / "ansible/roles/service_common/templates/configs/haproxy.cfg.j2"
    settings = {"haproxy_maxconn": 7654, "haproxy_timeout_server": "7h", "haproxy_overlay_metrics_proxy": proxy}
    variables = {
        "service_common_service": {"settings": settings},
        "groups": {"tags_postgres": ["pg-test"]},
        "hostvars": {"pg-test": {"local_ip": "192.0.2.20"}},
    }
    common = (
        Environment(undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True).from_string(source.read_text()).render(**variables)
    )
    role_path = ROOT / "ansible/roles/docker_services"
    tasks = yaml.safe_load((role_path / "tasks/sub_tasks/swarm_configs/create.yml").read_text())[:2]
    output = tmp_path / "rendered.cfg"
    tasks.append({"ansible.builtin.copy": {"content": "{{ docker_services_swarm_cfg_rendered }}", "dest": str(output), "mode": "0600"}})
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(
        yaml.safe_dump(
            {
                "all": {
                    "hosts": {"localhost": {"ansible_connection": "local"}},
                    "children": {"tags_postgres": {"hosts": {"pg-test": {"local_ip": "192.0.2.20"}}}},
                }
            }
        )
    )
    play = tmp_path / "play.yml"
    play.write_text(
        yaml.safe_dump(
            [
                {
                    "hosts": "localhost",
                    "gather_facts": False,
                    "vars": {
                        "role_path": str(role_path),
                        "docker_services_svc": {"settings": settings},
                        "cfg": {
                            "name": "haproxy_cfg",
                            "src": str(role_path / "templates/configs/haproxy.cfg.j2"),
                            "data_is_template": True,
                        },
                    },
                    "tasks": tasks,
                }
            ]
        )
    )
    config = tmp_path / "ansible.cfg"
    config.write_text("[defaults]\nretry_files_enabled=False\n")
    result = subprocess.run(
        [str(Path(sys.executable).parent / "ansible-playbook"), "-i", str(inventory), str(play)],
        env={**os.environ, "ANSIBLE_CONFIG": str(config)},
        capture_output=True,
        text=True,
        timeout=40,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    docker = output.read_text()
    assert docker.strip() == common.strip()
    assert "maxconn 7654" in common and "timeout server 7h" in common
    assert "GET /primary" in common and "init-state fully-down" in common
    assert "192.0.2.20:5432 check port 8008" in common


def test_systemd_dependency_graph_orders_removal_and_rejects_invalid_inputs():
    base = {"runtime": "podman", "image": "registry.example.invalid/fake:1.0", "deploy": {"type": "container", "hosts": "mgt"}}
    services = {"consumer": base | {"systemd": {"wants": ["provider.service"]}}, "provider": base}
    items = catalog_items(services, "mgt")
    deploy = CATALOG.service_catalog_podman_lifecycle_plan(items, items, "deploy")["selected"]
    remove = CATALOG.service_catalog_podman_lifecycle_plan(items, items, "remove")["selected"]
    assert [item["name"] for item in deploy] == ["provider", "consumer"]
    assert [item["name"] for item in remove] == ["consumer", "provider"]
    # Ordinary unit dependencies do not become destructive namespace transactions.
    assert all(not item["podman_lifecycle"]["namespace_dependents"] for item in deploy)
    for invalid in [None, "provider.service", [False], [""]]:
        with pytest.raises(AnsibleFilterError, match="systemd.wants"):
            catalog_items({"bad": base | {"systemd": {"wants": invalid}}}, "mgt")
    cycle = services | {"provider": base | {"systemd": {"requires": ["consumer.service"]}}}
    items = catalog_items(cycle, "mgt")
    with pytest.raises(AnsibleFilterError, match="dependency cycle"):
        CATALOG.service_catalog_podman_lifecycle_plan(items, items, "deploy")

    across_stores = services | {"provider": base | {"deploy": {"type": "container", "hosts": "mgt", "execution": {"mode": "rootless"}}}}
    items = catalog_items(across_stores, "mgt")
    with pytest.raises(AnsibleFilterError, match="execution stores"):
        CATALOG.service_catalog_podman_lifecycle_plan(items, items, "deploy")


@pytest.mark.parametrize("field", ["requires", "wants", "after"])
def test_managed_unit_dependencies_require_one_host_and_user_manager(field):
    base = {
        "runtime": "podman",
        "deploy": {"type": "container", "hosts": "mgt", "execution": {"mode": "rootless", "host_user": "podman-test"}},
    }
    services = {"consumer": base | {"systemd": {field: ["provider.service"]}}, "provider": deepcopy(base)}
    items = catalog_items(services, "mgt")
    plan = CATALOG.service_catalog_podman_lifecycle_plan(items, items, "deploy")["selected"]
    assert [item["name"] for item in plan] == ["provider", "consumer"]
    assert all(not item["podman_lifecycle"]["namespace_dependents"] for item in plan)
    for change in [{"host_user": "podman-other"}, {"mode": "rootful"}]:
        other = deepcopy(services)
        other["provider"]["deploy"]["execution"] = change | {"mode": change.get("mode", "rootless")}
        items = catalog_items(other, "mgt")
        with pytest.raises(AnsibleFilterError, match="execution stores or accounts"):
            CATALOG.service_catalog_podman_lifecycle_plan(items, items, "deploy")
    remote = deepcopy(services)
    remote["provider"]["deploy"]["hosts"] = "worker"
    items = catalog_items(remote, "mgt")
    with pytest.raises(AnsibleFilterError, match="same host and manager"):
        CATALOG.service_catalog_podman_lifecycle_plan(items, items, "deploy")


def test_real_machine_urls_and_direct_backends_do_not_form_proxy_loops():
    variables = context() | {"groups": {}, "prometheus_blackbox_exporter_address": "192.0.2.11:22622"}
    env = Environment(loader=FileSystemLoader(ROOT / "ansible/roles/service_common/templates"), undefined=StrictUndefined)
    datasources = yaml.safe_load(env.get_template("configs/grafana/provisioning/datasources/prometheus.yml.j2").render(**variables))
    services = catalog()
    for datasource in datasources["datasources"]:
        name = datasource["name"].lower()
        url = f"https://{name}.int.example.test:8443"
        assert datasource["url"] == url
        cfg = resolve(services[name], variables)
        route = COMMON.service_common_traefik_context(
            name=name,
            service=cfg,
            internal_zone=variables["services_internal_zone"],
            target_hosts=["mgt"],
            inventory_hosts=variables["hostvars"],
        )
        assert route["backend_url"].startswith("http://192.0.2.10:")
        assert route["backend_url"] != url
        assert not route["authelia_enabled"]
    prometheus = yaml.safe_load(
        env.get_template("configs/prometheus/prometheus.yml.j2").render(**variables, service_common_service=services["prometheus"])
    )
    assert prometheus["alerting"]["alertmanagers"][0]["scheme"] == "https"
    assert prometheus["alerting"]["alertmanagers"][0]["static_configs"][0]["targets"] == ["alertmanager.int.example.test:8443"]
    scrape = {job["job_name"]: job for job in prometheus["scrape_configs"]}
    for name, target, listener in [
        ("authelia", "main", "metrics"),
        ("haproxy", "mgt", "metrics"),
        ("traefik", None, "metrics"),
        ("scraparr", None, "backend"),
    ]:
        cfg = resolve(CATALOG.service_catalog_merge_target(services[name], target), variables)
        port = cfg["ports"][listener]["published"]
        if name in {"authelia", "traefik"}:
            assert scrape[name]["static_configs"][0]["targets"] == [variables["prometheus_worker_metrics_address"]]
            assert scrape[name]["static_configs"][0]["labels"]["instance"] == f"{name}:{cfg['ports'][listener]['target']}"
            assert scrape[name]["metrics_path"] == f"/{name}/metrics"
        else:
            assert scrape[name]["static_configs"][0]["targets"] == [f"192.0.2.10:{port}"]
    for path in ["configs/alloy-mgt.alloy.j2", "../docker_services/templates/alloy_config.alloy.j2"]:
        source = ROOT / "ansible/roles/service_common/templates" / path
        if path.startswith("../"):
            source = ROOT / "ansible/roles/docker_services/templates/alloy_config.alloy.j2"
        rendered = env.from_string(source.read_text()).render(**variables)
        assert 'url = "https://loki.int.example.test:8443/loki/api/v1/push"' in rendered
        assert 'url = "https://prometheus.int.example.test:8443/api/v1/write"' in rendered
        assert "insecure_skip_verify" not in rendered


def test_ingress_dashboard_uses_the_resolver_defined_by_the_static_configuration():
    env = Environment(loader=FileSystemLoader(ROOT / "ansible/roles/service_common/templates"), undefined=StrictUndefined)
    variables = context()
    static = yaml.safe_load(env.get_template("configs/proxy/traefik/config.yml.j2").render(**variables))
    dynamic = yaml.safe_load(env.get_template("configs/proxy/traefik/dashboard.yml.j2").render(**variables))
    tls = dynamic["http"]["routers"]["traefik-dashboard"]["tls"]
    assert tls["certResolver"] in static["certificatesResolvers"]
    assert static["certificatesResolvers"][tls["certResolver"]]["acme"]["dnsChallenge"]["provider"] == "cloudflare"
    assert tls["options"] == "securetls@file"


def test_explicit_rootless_ingress_network_preserves_wildcard_https_and_private_metrics():
    cfg = resolve(catalog()["traefik"], context())
    normalized = PODMAN.podman_service_normalize(cfg, "traefik")
    rendered = render_container(normalized)
    assert "Network=pasta\n" in rendered
    assert normalized["network"] is None
    assert "PublishPort=8443:8443/tcp\n" in rendered
    assert "PublishPort=192.0.2.10:18084:8082/tcp\n" in rendered
    for invalid in ["host", "pasta:--netns,/unowned", "container:unrelated"]:
        changed = deepcopy(cfg)
        changed["network_mode"] = invalid
        with pytest.raises(AnsibleFilterError, match="network_mode|host networking"):
            PODMAN.podman_service_normalize(changed, "traefik")
    changed = deepcopy(cfg)
    changed["named_networks"] = {"unexpected": {"driver": "bridge", "external": False}}
    with pytest.raises(AnsibleFilterError, match="cannot be combined"):
        PODMAN.podman_service_normalize(changed, "traefik")
    changed = deepcopy(cfg)
    changed["deploy"]["execution"] = {"mode": "rootful"}
    with pytest.raises(AnsibleFilterError, match="pasta requires rootless"):
        PODMAN.podman_service_normalize(changed, "traefik")


@pytest.mark.integration
def test_rootless_signal_and_preparation_commands_use_the_declared_account(tmp_path):
    env = Environment(loader=FileSystemLoader(ROOT / "ansible/roles/service_common/templates"), undefined=StrictUndefined)
    env.filters["quote"] = shlex.quote
    cfg = resolve(catalog()["traefik"], context())
    rendered = env.get_template("configs/proxy/traefik/reopen-logs.sh.j2").render(
        service_common_service=cfg,
        service_common_runtime="podman",
        service_common_template_vars={"runtime_execution": cfg["deploy"]["execution"], "runtime_home": "/var/lib/podman-traefik"},
    )
    script = tmp_path / "reopen.sh"
    script.write_text(rendered)
    subprocess.run(["sh", "-n", str(script)], check=True)
    assert "/usr/sbin/runuser -u podman-traefik -- /usr/bin/env" in rendered
    assert "--login" not in rendered and "su -" not in rendered
    assert "HOME=/var/lib/podman-traefik" in rendered
    assert "XDG_RUNTIME_DIR=" in rendered
    assert "/usr/bin/podman kill --signal USR1 traefik" in rendered
    policy = env.get_template("configs/proxy/traefik/logrotate.j2").render(service_common_service=cfg)
    assert "create 0640 podman-traefik podman-traefik" in policy
    # Render every actual executor operation against two stores. Start, inspect,
    # logs, stale cleanup, and final cleanup must all select the same owner.
    for account in ["podman-first", "podman-second"]:
        variables = {
            "service_prepare_context": {
                "execution": {"mode": "rootless", "host_user": account},
                "runtime_environment": {"HOME": "/var/lib/" + account, "XDG_RUNTIME_DIR": "/synthetic/runtime"},
            }
        }
        for action in ["start", "remove"]:
            tasks = yaml.safe_load(
                (ROOT / f"ansible/roles/service_prepare/tasks/runtimes/podman/temporary_container_{action}.yml").read_text()
            )
            for task in tasks:
                if any(key.startswith("containers.podman.") or key == "ansible.builtin.command" for key in task):
                    assert resolve(task["become_user"], variables) == account
                    assert resolve(task["environment"], variables)["HOME"].endswith(account)
                    conditions = task["when"] if isinstance(task["when"], list) else [task["when"]]
                    assert "not ansible_check_mode" in conditions


def test_authelia_secret_ownership_follows_its_final_application_identity():
    cfg = resolve(CATALOG.service_catalog_merge_target(catalog()["authelia"], "main"), context())
    normalized = PODMAN.podman_service_normalize(cfg, "authelia")
    expected_uid = cfg["environment"]["PUID"]
    expected_gid = cfg["environment"]["PGID"]
    assert normalized["container"]["uid"] == "0"  # The entrypoint must perform initialization.
    assert normalized["execution"]["userns"]["uid"] == str(expected_uid)
    common = COMMON.service_common_infisical_normalize(cfg["infisical"]["secrets_map"])
    declarations = PODMAN.podman_secret_declarations(common["secret_declarations"])
    assert all(declaration["uid"] == str(expected_uid) and declaration["gid"] == str(expected_gid) for declaration in declarations)
    prepare = plugin("ansible/roles/service_prepare/filter_plugins/service_prepare.py", "migration_prepare")
    env = NativeEnvironment(undefined=StrictUndefined)
    env.filters.update(prepare.FilterModule().filters())
    env.filters["combine"] = lambda value, addition: value | addition
    task = yaml.safe_load((ROOT / "ansible/roles/service_prepare/tasks/applications/authelia/generate_secret.yml").read_text())[-1]
    expression = task["ansible.builtin.set_fact"]["service_prepare_generated_secret_declarations"]
    generated = env.from_string(expression).render(
        service_prepare_generated_secret_declarations=[],
        service_prepare_authelia_secret_job={"name": "NONPRODUCTION-generated", "var": "fake_generated"},
        service_prepare_context={"resolved_environment": cfg["environment"]},
    )
    assert str(generated[0]["uid"]) == str(expected_uid)
    assert str(generated[0]["gid"]) == str(expected_gid)


@pytest.mark.parametrize("name", ["alertmanager", "autobrr", "loki", "prometheus", "vaultwarden", "seerr", "znc"])
def test_rootless_mapping_preserves_inventory_application_identity_overrides(name):
    variables = context()
    variables["hostvars"]["mgt"].update(container_host_puid=2301, container_host_pgid=2402)
    cfg = resolve(catalog()[name], variables)
    normalized = PODMAN.podman_service_normalize(cfg, name)
    mapping = normalized["execution"]["userns"]
    assert (mapping["uid"], mapping["gid"]) == ("2301", "2402")
    if cfg["user"] == "0:0":
        assert (cfg["environment"]["PUID"], cfg["environment"]["PGID"]) == (2301, 2402)
    else:
        assert (normalized["container"]["uid"], normalized["container"]["gid"]) == (mapping["uid"], mapping["gid"])


@pytest.mark.parametrize("scope,input_name", list(COMMON._OPERATIONAL_ACL_INPUTS.items()))
@pytest.mark.parametrize("action", ["deploy", "update", "recreate", "bootstrap"])
def test_explicit_acl_requirements_reject_missing_false_and_nonboolean_acknowledgements(scope, input_name, action):
    service = {"operational_requirements": {"acl": [scope]}}
    for inputs in [{}, *[{input_name: value} for value in [False, "true", 1, None, [], {}]]]:
        with pytest.raises(AnsibleFilterError, match=input_name):
            COMMON.service_common_requirements_validate(service, "fake-service", action, inputs)
    assert COMMON.service_common_requirements_validate(service, "fake-service", action, {input_name: True})


def test_data_acknowledgement_uses_actual_service_name_and_strict_boolean():
    cfg = resolve(catalog()["loki"], context())
    catalog_alias = "log-service"
    assert cfg["name"] != catalog_alias
    inputs = {"services_mgt_backend_acl_ready": True, "services_mgt_receiver_acl_ready": True}
    for readiness in [{}, {catalog_alias: True}, *[{cfg["name"]: value} for value in [False, "true", 1, None]], "true", []]:
        with pytest.raises(AnsibleFilterError, match="services_rootless_data_ready"):
            COMMON.service_common_requirements_validate(cfg, cfg["name"], "deploy", inputs | {"services_rootless_data_ready": readiness})
    assert COMMON.service_common_requirements_validate(
        cfg, cfg["name"], "deploy", inputs | {"services_rootless_data_ready": {cfg["name"]: True}}
    )


@pytest.mark.parametrize(
    "requirements",
    [
        None,
        [],
        {"unknown": True},
        {"acl": "mgt_backends"},
        {"acl": ["unknown"]},
        {"acl": [True]},
        {"ownership_transition": "true"},
        {"ownership_transition": 1},
    ],
)
def test_invalid_requirement_declarations_fail_even_for_planning_and_recovery(requirements):
    for action, check in [("deploy", True), ("remove", False), ("drift", False)]:
        with pytest.raises(AnsibleFilterError):
            COMMON.service_common_requirements_validate({"operational_requirements": requirements}, "fake", action, {}, check)


def test_planning_removal_drift_and_account_only_preparation_need_no_deployment_acknowledgements():
    service = {"operational_requirements": {"acl": list(COMMON._OPERATIONAL_ACL_INPUTS), "ownership_transition": True}}
    for action, check, account in [
        ("remove", False, False),
        ("drift", False, False),
        ("recreate", True, False),
        ("deploy", False, True),
        ("update", False, True),
        ("bootstrap", False, True),
    ]:
        assert COMMON.service_common_requirements_validate(service, "fake", action, {}, check, account)
    for action in ["remove", "drift", "recreate"]:
        with pytest.raises(AnsibleFilterError, match="account-only"):
            COMMON.service_common_requirements_validate(service, "fake", action, {}, False, True)
    for check, account in [("true", False), (False, "true"), (1, False)]:
        with pytest.raises(AnsibleFilterError, match="booleans"):
            COMMON.service_common_requirements_validate(service, "fake", "deploy", {}, check, account)


def test_real_service_and_batch_selection_keep_requirements_after_all_configuration_tags_are_removed():
    services = catalog()
    # This migration exercises container protection, independently of optional
    # native inventory groups (which no longer implicitly disable entries).
    effective = catalog_items(services, "mgt", runtimes=["docker", "podman"])
    for selector in ["monitoring", "arrs", "alloy-workers", "mgt-collector"]:
        selected = CATALOG.service_catalog_select(effective, ["deploy", selector])["selected"]
        assert selected
        for entry in selected:
            raw = CATALOG.service_catalog_merge_target(services[entry["name"]], entry.get("target"))
            cfg = resolve(raw, context())
            requirements = COMMON.service_common_requirements_normalize(cfg.get("operational_requirements", {}))
            if not requirements["acl"] and not requirements["ownership_transition"]:
                continue
            without_tags = deepcopy(services[entry["name"]])
            without_tags.pop("tags", None)
            for target in without_tags.get("targets", {}).values():
                target.pop("tags", None)
            individual = CATALOG.service_catalog_select(
                catalog_items({entry["name"]: without_tags}, "mgt"), ["deploy", entry.get("target", entry["name"])]
            )["selected"]
            individual_entry = next(item for item in individual if item.get("target") == entry.get("target"))
            individual_cfg = resolve(CATALOG.service_catalog_merge_target(without_tags, individual_entry.get("target")), context())
            assert individual_cfg["operational_requirements"] == cfg["operational_requirements"]
            for definition in [cfg, individual_cfg]:
                with pytest.raises(AnsibleFilterError, match="requires"):
                    COMMON.service_common_requirements_validate(definition, definition.get("name", entry["name"]), "deploy", {})
                acknowledgements = {key: True for key in COMMON._OPERATIONAL_ACL_INPUTS.values()}
                acknowledgements["services_rootless_data_ready"] = {definition.get("name", entry["name"]): True}
                assert COMMON.service_common_requirements_validate(
                    definition, definition.get("name", entry["name"]), "deploy", acknowledgements
                )


def test_effective_target_requirements_use_normal_merge_and_remain_distinct_between_workers_and_mgt():
    for name in ["alloy", "haproxy"]:
        services = catalog()[name]
        mgt = CATALOG.service_catalog_merge_target(services, "mgt")
        workers = CATALOG.service_catalog_merge_target(services, "workers")
        assert mgt["operational_requirements"]["acl"] == ["mgt_backends"]
        assert "mgt_backends" not in workers.get("operational_requirements", {}).get("acl", [])
    base = deepcopy(catalog()["loki"])
    base["targets"] = {"temporary": {"tags": [], "operational_requirements": {"acl": ["bootstrap"]}}}
    merged = CATALOG.service_catalog_merge_target(base, "temporary")
    assert set(merged["operational_requirements"]["acl"]) == {"mgt_backends", "mgt_receivers", "bootstrap"}
    assert merged["operational_requirements"]["ownership_transition"] is True
    base["targets"]["temporary"]["operational_requirements"]["acl"] = []
    assert CATALOG.service_catalog_merge_target(base, "temporary")["operational_requirements"] == base["operational_requirements"]


def test_changed_publications_have_explicit_acl_coverage_including_traefik_metrics():
    services = catalog()
    selected = mgt_entries(services) + worker_backend_entries(services)
    for item in selected:
        cfg = resolve(CATALOG.service_catalog_merge_target(services[item["name"]], item.get("target")), context())
        # These five retain their already published listener contracts.
        if not cfg.get("ports") or item["name"] in {"adminer", "forgejo", "homepage", "thelounge", "unifi"}:
            continue
        expected = "worker_backends" if cfg["runtime"] == "docker" else "mgt_backends"
        assert expected in cfg.get("operational_requirements", {}).get("acl", []), item
    traefik = resolve(services["traefik"], context())
    normalized = PODMAN.podman_service_normalize(traefik, "traefik")
    assert "PublishPort=192.0.2.10:18084:8082/tcp" in render_container(normalized)
    with pytest.raises(AnsibleFilterError, match="services_mgt_backend_acl_ready"):
        COMMON.service_common_requirements_validate(traefik, "traefik", "deploy", {"services_rootless_data_ready": {"traefik": True}})


@pytest.mark.integration
@pytest.mark.parametrize("entry_point", ["catalog", "netbox", "infisical"])
def test_real_preflight_blocks_before_secret_resolution_files_or_bootstrap_recreate(tmp_path, entry_point):
    import sys

    cfg = {
        "runtime": "podman",
        "name": "fake-unit",
        "image": "registry.example.invalid/unit:1.0",
        "operational_requirements": {"ownership_transition": True},
    }
    variables = {"local_ip": "192.0.2.10", "services_internal_zone": "int.example.test", "netbox_domain": "example.test"}
    if entry_point == "catalog":
        variables |= {
            "service_catalog_action": "deploy",
            "service_catalog_controller_host": "localhost",
            "service_catalog_materialized_service": {"runtime": "podman", "name": "fake-unit", "config": cfg},
            "service_catalog_dispatch_entry": {"runtime": "podman", "name": "fake-unit"},
            "infisical_lookup_default_params": "must-never-be-resolved",
        }
        include = {"ansible.builtin.include_tasks": str(ROOT / "ansible/tasks/service_catalog_common_preflight.yml")}
    else:
        variables[f"{entry_point}_podman_services"] = [cfg]
        variables["netbox_required_docker_secrets"] = {}
        for key in [
            "infisical_enc_key",
            "infisical_jwt_key",
            "infisical_postgres_user",
            "infisical_postgres_pass",
            "infisical_redis_password",
        ]:
            variables[key] = "NONPRODUCTION"
        include = {"ansible.builtin.include_role": {"name": entry_point}, "tags": [f"{entry_point}_recreate"]}
    marker = tmp_path / "mutation-must-not-run"
    play = [
        {
            "hosts": "localhost",
            "connection": "local",
            "gather_facts": False,
            "vars": variables,
            "tasks": [
                include,
                {
                    "ansible.builtin.copy": {"content": "NONPRODUCTION", "dest": str(marker), "mode": "0600"},
                    "tags": [f"{entry_point}_recreate"],
                },
            ],
        }
    ]
    path = tmp_path / "requirements.yml"
    path.write_text(yaml.safe_dump(play))
    actions = tmp_path / "actions"
    actions.mkdir()
    (actions / "service_operational_check.py").write_text(
        "from ansible.plugins.action import ActionBase\n"
        "class ActionModule(ActionBase):\n"
        "    def run(self, tmp=None, task_vars=None):\n"
        "        assert self._task.args['phase'] == 'runtime'\n"
        "        return {'changed': False, 'managed': False}\n"
    )
    config = tmp_path / "ansible.cfg"
    config.write_text(
        f"[defaults]\nroles_path={ROOT}/ansible/roles\naction_plugins={actions}:{ROOT}/ansible/action_plugins\nlibrary={ROOT}/ansible/library\ninventory=localhost,\nstdout_callback=default\n"
    )
    args = [str(Path(sys.executable).with_name("ansible-playbook")), "-i", "localhost,", str(path)]
    if entry_point != "catalog":
        args += ["--tags", f"{entry_point}_recreate"]
    result = subprocess.run(
        args,
        env=dict(
            os.environ, ANSIBLE_CONFIG=str(config), ANSIBLE_LOCAL_TEMP=str(tmp_path / "local"), ANSIBLE_REMOTE_TEMP=str(tmp_path / "remote")
        ),
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "services_rootless_data_ready" in result.stdout + result.stderr, result.stdout + result.stderr
    assert "Stop consumers" not in result.stdout
    assert "Resolve common Infisical" not in result.stdout
    assert not marker.exists()


def test_requirement_handoffs_pass_only_value_free_metadata():
    cfg = {
        "name": "fake",
        "operational_requirements": {"acl": ["mgt_backends"]},
        "environment": {"PASSWORD": "NONPRODUCTION-do-not-forward"},
    }
    for path, variables in [
        ("ansible/tasks/service_catalog_common_preflight.yml", {"service_catalog_materialized_service": {"config": cfg}}),
        ("ansible/roles/podman_services/tasks/sub_tasks/init.yml", {"podman_services_service_cfg": cfg}),
        ("ansible/roles/docker_services/tasks/sub_tasks/init.yml", {"docker_services_svc": cfg}),
    ]:
        tasks = yaml.safe_load((ROOT / path).read_text())
        gate = next(task for task in tasks if task.get("ansible.builtin.include_role", {}).get("tasks_from") == "operational_requirements")
        environment = NativeEnvironment(undefined=StrictUndefined)
        environment.filters.update(COMMON.FilterModule().filters())
        passed = environment.from_string(gate["vars"]["service_common_service"]).render(**variables, service_common_name="fake")
        assert passed == COMMON.service_common_requirements_metadata(cfg, "fake")
        assert "NONPRODUCTION" not in repr(passed)


def test_catalog_ownership_acknowledgement_uses_adapter_default_name_for_unnamed_target():
    base = {
        "runtime": "podman",
        "image": "registry.example.invalid/unit:1",
        "operational_requirements": {"ownership_transition": True},
        "targets": {"blue": {"tags": ["temporary"]}},
    }
    entry = catalog_items({"fake": base}, "mgt")[0]
    cfg = CATALOG.service_catalog_merge_target(base, "blue")
    gate = next(
        task
        for task in yaml.safe_load((ROOT / "ansible/tasks/service_catalog_common_preflight.yml").read_text())
        if task.get("ansible.builtin.include_role", {}).get("tasks_from") == "operational_requirements"
    )
    name = resolve(gate["vars"]["service_common_name"], {"service_catalog_materialized_service": entry | {"config": cfg}})
    normalized = PODMAN.podman_service_normalize(cfg, "fake-blue")
    assert name == normalized["name"]
    assert COMMON.service_common_requirements_validate(cfg, name, "deploy", {"services_rootless_data_ready": {name: True}})
    with pytest.raises(AnsibleFilterError, match="services_rootless_data_ready"):
        COMMON.service_common_requirements_validate(cfg, name, "deploy", {"services_rootless_data_ready": {"fake": True}})


@pytest.mark.integration
def test_rootless_log_reopen_changes_to_account_home_before_podman(tmp_path):
    """Run the real account shell wrapper from an operator-private directory."""
    env = Environment(loader=FileSystemLoader(ROOT / "ansible/roles/service_common/templates"), undefined=StrictUndefined)
    env.filters["quote"] = shlex.quote
    cfg = resolve(catalog()["traefik"], context())
    home = tmp_path / "dedicated home"
    home.mkdir(mode=0o700)
    private = tmp_path / "private operator cwd"
    private.mkdir(mode=0o700)
    child = tmp_path / "podman"
    child.write_text('#!/bin/sh\nprintf "%s\\n" "$PWD" "$HOME" "$XDG_RUNTIME_DIR" "$DBUS_SESSION_BUS_ADDRESS" "$@"\n')
    child.chmod(0o700)
    runuser = tmp_path / "runuser"
    runuser.write_text('#!/bin/sh\n[ "$1" = -u ] && [ "$2" = podman-traefik ] && [ "$3" = -- ] || exit 2\nshift 3\nexec "$@"\n')
    runuser.chmod(0o700)
    rendered = env.get_template("configs/proxy/traefik/reopen-logs.sh.j2").render(
        service_common_service=cfg,
        service_common_runtime="podman",
        service_common_template_vars={"runtime_execution": cfg["deploy"]["execution"], "runtime_home": str(home)},
    )
    rendered = (
        rendered.replace("/usr/bin/id -u podman-traefik", "printf 12345")
        .replace("/usr/sbin/runuser", shlex.quote(str(runuser)))
        .replace("/usr/bin/podman", shlex.quote(str(child)))
        .replace(" >/dev/null", "")
    )
    result = subprocess.run(["/bin/sh", "-c", rendered], cwd=private, capture_output=True, text=True, check=True)
    assert result.stdout.splitlines() == [
        str(home),
        str(home),
        "/run/user/12345",
        "unix:path=/run/user/12345/bus",
        "kill",
        "--signal",
        "USR1",
        "traefik",
    ]


@pytest.mark.integration
def test_netbox_bootstrap_health_sends_the_allowed_host(tmp_path):
    """Run the rendered health command against a Host-restricting HTTP server."""
    import http.server
    import threading

    defaults = yaml.safe_load((ROOT / "ansible/roles/netbox/defaults/main.yml").read_text())
    variables = context() | {
        "inventory_hostname": "mgt",
        "container_host_appdata_root": "/opt/fixture",
        "container_host_puid": "1000",
        "container_host_pgid": "1000",
    }
    pending = {key: value for key, value in defaults.items() if key not in variables and key != "netbox_podman_services"}
    for _ in range(10):
        for key, value in list(pending.items()):
            try:
                variables[key] = resolve(value, variables)
            except Exception:
                continue
            del pending[key]
    definitions = resolve(defaults["netbox_podman_services"], variables)
    app = next(cfg for cfg in definitions if cfg["name"] == "netbox")
    command = PODMAN.podman_service_normalize(app, "netbox")["container"]["healthcheck"]["command"]
    seen = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.headers.get("Host"))
            self.send_response(200 if self.headers.get("Host") == variables["netbox_frontend_fqdn"] else 400)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run(
            ["/bin/sh", "-c", command.replace("127.0.0.1:8000", f"127.0.0.1:{server.server_port}")],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0
        assert seen == [variables["netbox_frontend_fqdn"]]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.integration
def test_generated_health_shell_preserves_quotes_substitution_and_environment(tmp_path):
    """Run the generated health argument, without a container or real credentials."""
    generator = Path("/usr/lib/systemd/system-generators/podman-system-generator")
    if not generator.is_file():
        pytest.skip("Local isolated Quadlet generator unavailable")
    fake_secret = tmp_path / "fake-secret"
    fake_secret.write_text("NONPRODUCTION credential with spaces")
    executable = tmp_path / "fixture-ready"
    executable.write_text(
        '#!/bin/sh\n[ "$#" = 2 ] && [ "$1" = -d ] && [ "$2" = "$POSTGRES_DB" ] && [ "$PGUSER" = "NONPRODUCTION credential with spaces" ]\n'
    )
    executable.chmod(0o700)
    payload = f'PGUSER="$(cat {fake_secret})" {executable} -d "$POSTGRES_DB" && test "%n" = "%n"'
    cfg = {"runtime": "podman", "image": "registry.example.invalid/fake:1.0", "healthcheck": {"test": ["CMD-SHELL", payload]}}
    service = PODMAN.podman_service_normalize(cfg, "fake-health")
    (tmp_path / "fake-health.container").write_text(render_container(service))
    result = subprocess.run(
        [str(generator), "--dryrun"], env=dict(os.environ, QUADLET_UNIT_DIRS=str(tmp_path)), capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    line = next(line for line in result.stdout.splitlines() if line.startswith("ExecStart="))
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|[^\s]+', line.partition("=")[2])
    generated = [ast.literal_eval(token) if token.startswith('"') else token for token in tokens]
    health = generated[generated.index("--health-cmd") + 1].replace("$$", "$").replace("%%", "%")
    argv = json.loads(health)
    assert argv == ["/bin/sh", "-c", payload]
    executed = subprocess.run(
        argv, env=dict(os.environ, POSTGRES_DB="NONPRODUCTION database with spaces"), capture_output=True, text=True, check=False
    )
    assert executed.returncode == 0, executed.stderr


def test_cached_inputs_remain_independent_between_test_cases():
    current = catalog()
    name = next(iter(current))
    baseline = deepcopy(current[name])
    current[name]["image"] = "registry.invalid/nonproduction:changed"
    assert catalog()[name] == baseline
    assert resolve("{{ value }}", {"value": "first"}) == "first"
    assert resolve("{{ value }}", {"value": "second"}) == "second"
