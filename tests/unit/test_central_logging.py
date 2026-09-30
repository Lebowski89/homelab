import importlib.util
import json
import re
from pathlib import Path, PurePosixPath

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from jinja2.nativetypes import NativeEnvironment

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_DIR = REPO_ROOT / "ansible/group_vars/all/services"
DOCKER_ALLOY_PATH = REPO_ROOT / "ansible/roles/docker_services/templates/alloy_config.alloy.j2"

SERVICE_CATALOG_PATH = REPO_ROOT / "ansible/filter_plugins/service_catalog.py"
SERVICE_COMMON_ROLE_DIR = REPO_ROOT / "ansible/roles/service_common"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


CATALOG_FILTERS = load_module(SERVICE_CATALOG_PATH, "service_catalog_central_logging")
SERVICE_COMMON_FILTERS = load_module(
    SERVICE_COMMON_ROLE_DIR / "filter_plugins/service_common.py",
    "service_common_central_logging",
)
TEST_HOST_CONTEXT = {
    "services_controller_host": "mgt",
    "services_storage_host": "unraid",
    "services_plex_host": "plex",
    "services_log_root": "/var/log/skynet",
    "hostvars": {
        "mgt": {"container_host_appdata_root": "/srv/apps"},
        "unraid": {"container_host_appdata_root": "/mnt/user/appdata"},
        "plex": {"container_host_appdata_root": "/mnt/plex-apps"},
    },
}


def load_service(name: str):
    document = yaml.safe_load((SERVICES_DIR / f"{name}.yml").read_text())
    if name in document:
        return document[name]
    assert len(document) == 1
    return next(iter(document.values()))


def persisted_container_path(catalog_name: str, target_name: str | None, volume_name: str, container_path: str) -> str:
    service = CATALOG_FILTERS.service_catalog_merge_target(load_service(catalog_name), target_name)
    volume = service["volumes"][volume_name]
    mount_target = PurePosixPath(volume["target"])
    relative_path = PurePosixPath(container_path).relative_to(mount_target)
    host_root = NativeEnvironment(undefined=StrictUndefined).from_string(volume["source"]).render(**TEST_HOST_CONTEXT)
    return f"/host/rootfs{str(host_root).rstrip('/')}/{relative_path}"


def render_docker_alloy(*, shared_appdata_root: bool = False) -> str:
    controller_root = "/srv/apps" if not shared_appdata_root else "/opt"
    plex_root = "/mnt/plex-apps" if not shared_appdata_root else "/opt"
    return (
        Environment(undefined=StrictUndefined)
        .from_string(DOCKER_ALLOY_PATH.read_text())
        .render(
            services_controller_host="mgt",
            services_storage_host="unraid",
            services_plex_host="plex",
            services_log_root="/var/log/skynet",
            hostvars={
                "mgt": {"container_host_appdata_root": controller_root},
                "unraid": {"container_host_appdata_root": "/mnt/user/appdata"},
                "plex": {"container_host_appdata_root": plex_root},
            },
        )
    )


def test_docker_alloy_is_global_with_stable_node_identity_and_local_state():
    service = load_service("alloy")

    assert service["deploy"]["mode"] == "global"
    assert "replicas" not in service["deploy"]
    assert service["deploy"]["constraints"] == ["node.platform.os == linux"]
    assert not any("primary_manager" in constraint for constraint in service["deploy"]["constraints"])
    assert Environment(undefined=StrictUndefined).from_string(service["environment"]["ALLOY_HOST"]).render() == "{{.Node.Hostname}}"
    assert service["swarm_configs"] == [{"name": "alloy_config", "src": "alloy_config.alloy.j2", "data_is_template": True}]
    assert service["named_volumes"]["state"] == {
        "external": False,
        "name": "alloy-state",
        "driver": "local",
    }
    assert service["volumes"]["data"] == {
        "type": "volume",
        "source": "state",
        "target": "/etc/alloy/data",
        "read_only": False,
    }
    assert service["volumes"]["docker_sock"]["read_only"] is True
    assert service["volumes"]["host_rootfs"]["read_only"] is True
    assert "paths" not in service


def test_swarm_node_template_survives_the_actual_compose_renderer():
    service = load_service("alloy")
    node_hostname = Environment(undefined=StrictUndefined).from_string(service["environment"]["ALLOY_HOST"]).render()
    environment = Environment(
        loader=FileSystemLoader(REPO_ROOT / "ansible/roles/docker_services/templates"),
        undefined=StrictUndefined,
    )
    environment.filters["bool"] = bool
    environment.filters["to_json"] = json.dumps
    environment.globals["lookup"] = lambda *args, **kwargs: ""
    rendered = environment.get_template("compose.yml.j2").render(
        deploy_stack_type="swarm",
        stack_networks={},
        stack_volumes={},
        docker_services_compose_services={
            "alloy": {
                "image": service["image"],
                "logging": {"driver": "json-file", "options": {"max-size": "10m", "max-file": "3"}},
                "environment": {"ALLOY_HOST": node_hostname},
                "deploy": {"mode": "global"},
            }
        },
    )

    compose = yaml.safe_load(rendered)
    assert compose["services"]["alloy"]["environment"]["ALLOY_HOST"] == "{{.Node.Hostname}}"
    assert compose["services"]["alloy"]["deploy"]["mode"] == "global"


def test_docker_alloy_labels_are_stable_and_metrics_keep_node_identity():
    config = render_docker_alloy()

    for label in ("host", "runtime", "source"):
        assert re.search(rf"\b{label}\s+=", config)
    assert 'target_label  = "container"' in config
    assert 'sys.env("ALLOY_HOST")' in config
    assert "__meta_docker_container_label_com_docker_swarm_service_name" in config
    assert config.count('regex         = "^[^_]+_(.+)"') == 2
    assert config.count('replacement   = "$1"') == 2
    assert "container_id" not in config
    assert "task_id" not in config
    assert "image_digest" not in config
    assert "prometheus.exporter.unix" in config
    assert "prometheus.exporter.cadvisor" in config
    assert config.count('target_label = "instance"') == 2
    assert "alloy-unix" in config
    assert "alloy-cadvisor" in config


def test_docker_file_collection_is_an_explicit_active_file_allowlist():
    config = render_docker_alloy()
    paths = set(re.findall(r'__path__\s*=\s*"([^"]+)"', config))

    # Each application path is derived from its real persisted container bind,
    # then combined with an independently stated in-container log contract.
    contracts = [
        ("traefik", None, "logs", "/etc/traefik/logs/access.log"),
        ("qbittorrent", "alpha", "config", "/config/log/qbittorrent.log"),
        ("qbittorrent", "bravo", "config", "/config/log/qbittorrent.log"),
        ("sabnzbd", None, "config", "/config/logs/sabnzbd.log"),
        ("radarr", "radarr", "config", "/config/logs/radarr.txt"),
        ("radarr", "radarr_4k", "config", "/config/logs/radarr.txt"),
        ("sonarr", "sonarr", "config", "/config/logs/sonarr.txt"),
        ("sonarr", "sonarr_4k", "config", "/config/logs/sonarr.txt"),
        ("lidarr", None, "config", "/config/logs/lidarr.txt"),
        ("prowlarr", None, "config", "/config/logs/prowlarr.txt"),
        ("whisparr", None, "config", "/config/logs/whisparr.txt"),
        ("bazarr", None, "config", "/config/log/bazarr.log"),
        ("recyclarr", None, "config", "/config/logs/debug.log"),
        ("nzbhydra2", None, "config", "/config/app/logs/nzbhydra2.log"),
        ("nzbhydra2", None, "config", "/config/app/logs/wrapper.log"),
        (
            "plex",
            None,
            "config",
            "/config/Library/Application Support/Plex Media Server/Logs/Plex Media Server.log",
        ),
        ("tautulli", None, "config", "/config/logs/tautulli.log"),
        ("kometa", None, "config", "/config/logs/meta.log"),
        ("imagemaid", None, "config", "/config/logs/imagemaid.log"),
        ("seerr", None, "config", "/app/config/logs/seerr.log"),
        ("unifi-os", None, "var_log", "/var/log/unifi/server.log"),
        ("technitium", "technitium_primary", "config", "/etc/dns/logs/*.log"),
        ("technitium", "technitium_secondary", "config", "/etc/dns/logs/*.log"),
    ]
    expected_paths = {
        persisted_container_path(catalog, target, volume, container_path) for catalog, target, volume, container_path in contracts
    }

    assert paths == expected_paths
    assert all("**" not in path for path in paths)
    assert all("*" not in path or path.endswith("/technitium/logs/*.log") for path in paths)
    assert all(not path.endswith((".gz", ".zip", ".bak")) for path in paths)
    assert 'ignore_older_than = "24h"' in config
    assert config.count("tail_from_end") == 2
    assert config.count('on_positions_file_error = "restart_from_end"') == 2


def test_technitium_sources_keep_distinct_owners_when_nodes_share_appdata_root():
    config = render_docker_alloy(shared_appdata_root=True)
    technitium_targets = [(path, owner) for path, owner, service in owned_file_targets(config) if service == "technitium"]

    assert technitium_targets == [
        ("/host/rootfs/opt/technitium/logs/*.log", "mgt"),
        ("/host/rootfs/opt/technitium/logs/*.log", "plex"),
    ]


def test_traefik_access_stream_remains_json_and_uses_only_bounded_labels():
    traefik_config = (REPO_ROOT / "ansible/roles/service_common/templates/configs/proxy/traefik/config.yml.j2").read_text()
    alloy_config = render_docker_alloy()

    assert "filePath: /etc/traefik/logs/access.log" in traefik_config
    assert "format: json" in traefik_config
    assert 'loki.process "traefik_access"' in alloy_config
    assert "entryPointName" in alloy_config
    assert "RouterName" in alloy_config
    assert "ServiceName" in alloy_config
    for forbidden in ("ClientHost", "RequestPath", "RequestAddr", "User-Agent", "request_id"):
        assert forbidden not in alloy_config


def test_traefik_access_log_has_bounded_reopen_safe_rotation():
    service = load_service("traefik")
    log_root = NativeEnvironment(undefined=StrictUndefined).from_string(service["volumes"]["logs"]["source"]).render(**TEST_HOST_CONTEXT)
    template_context = {
        "name": service["name"],
        "stack": service["stack"],
        "volumes": {"logs": {"source": log_root}},
    }
    environment = Environment(
        loader=FileSystemLoader(REPO_ROOT / "ansible/roles/service_common/templates"),
        undefined=StrictUndefined,
    )
    policy = environment.get_template("configs/proxy/traefik/logrotate.j2").render(service_common_service=template_context)
    reopen = environment.get_template("configs/proxy/traefik/reopen-logs.sh.j2").render(service_common_service=template_context)
    declarations = {item["src"]: item for item in service["templates"]}
    alloy_config = render_docker_alloy()

    assert "/var/log/skynet/traefik/access.log {" in policy
    for directive in ("daily", "maxsize 25M", "rotate 7", "maxage 7", "compress", "delaycompress"):
        assert directive in policy
    assert "create 0640 root root" in policy
    assert "/usr/local/sbin/skynet-traefik-reopen-logs" in policy
    assert "copytruncate" not in policy

    assert 'service_name="traefik_traefik"' in reopen
    assert "label=com.docker.swarm.service.name=${service_name}" in reopen
    assert '--filter "status=running"' in reopen
    assert "set -- ${container_ids}" in reopen
    assert 'if [ "$#" -ne 1 ]' in reopen
    assert '/usr/bin/docker kill --signal USR1 "$1"' in reopen
    assert '--filter "name=' not in reopen

    assert declarations["configs/proxy/traefik/logrotate.j2"] == {
        "src": "configs/proxy/traefik/logrotate.j2",
        "dest": "/etc/logrotate.d/skynet-traefik",
        "owner": "0",
        "group": "0",
        "mode": "0644",
        "force": True,
    }
    assert declarations["configs/proxy/traefik/reopen-logs.sh.j2"] == {
        "src": "configs/proxy/traefik/reopen-logs.sh.j2",
        "dest": "/usr/local/sbin/skynet-traefik-reopen-logs",
        "owner": "0",
        "group": "0",
        "mode": "0755",
        "force": True,
    }
    assert service["deploy"]["mode"] == "replicated"
    assert service["deploy"]["replicas"] == 1
    assert service["deploy"]["constraints"] == ["node.labels.docker_services_host == docker_services_primary_manager"]
    assert alloy_config.count("/host/rootfs/var/log/skynet/traefik/access.log") == 1
    assert "access.log*" not in alloy_config


def test_file_sources_deliberately_drop_the_automatic_filename_label():
    docker_config = render_docker_alloy()
    assert "forward_to              = [loki.process.application_files.receiver]" in docker_config
    assert "forward_to              = [loki.process.traefik_access.receiver]" in docker_config
    assert docker_config.count('values = ["filename"]') == 2


def test_verified_application_log_layouts_remain_narrow_and_version_pinned():
    alloy_config = render_docker_alloy()
    technitium = load_service("technitium")

    assert load_service("nzbhydra2")["image"] == "ghcr.io/hotio/nzbhydra2:release-v8.9.0"
    assert load_service("imagemaid")["image"] == "kometateam/imagemaid:v1.2.0"
    assert load_service("seerr")["image"] == "ghcr.io/hotio/seerr:release-v3.4.1"
    assert load_service("unifi-os")["image"] == "ghcr.io/lemker/unifi-os-server:v1.7.0"
    assert technitium["image"] == "technitium/dns-server:15.5.0"
    assert "/nzbhydra2/app/logs/nzbhydra2.log" in alloy_config
    assert "/nzbhydra2/app/logs/wrapper.log" in alloy_config
    assert "/imagemaid/logs/imagemaid.log" in alloy_config
    assert "/seerr/logs/seerr.log" in alloy_config
    assert "/unifi-os/var-log/unifi/server.log" in alloy_config
    assert alloy_config.count("/technitium/logs/*.log") == 2
    assert not any("QUERY" in key.upper() and "LOG" in key.upper() for key in technitium["environment"])
    assert all("*.gz" not in path for path in re.findall(r'__path__ = "([^"]+)"', alloy_config))


def test_loki_private_ingest_route_and_clients_render_end_to_end():
    service = load_service("loki")
    loki_config = (REPO_ROOT / "ansible/roles/service_common/templates/configs/loki-config.yaml.j2").read_text()
    dns = (REPO_ROOT / "terraform/technitium/internal-dns/main.tf").read_text()
    static_traefik = (REPO_ROOT / "ansible/roles/service_common/templates/configs/proxy/traefik/config.yml.j2").read_text()
    native_defaults = yaml.safe_load((REPO_ROOT / "ansible/roles/alloy_native/defaults/main.yml").read_text())
    native_url = (
        Environment(undefined=StrictUndefined)
        .from_string(native_defaults["alloy_native_loki_url"])
        .render(
            services_internal_zone="private.example.internal",
            services_private_https_port=9443,
        )
    )
    context = SERVICE_COMMON_FILTERS.service_common_traefik_context(
        service,
        "loki",
        ["mgt"],
        "private.example.internal",
        {"mgt": {"local_ip": "192.0.2.10"}},
    )
    environment = Environment(
        loader=FileSystemLoader(SERVICE_COMMON_ROLE_DIR / "templates"),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    route_text = environment.get_template("traefik/dynamic.yml.j2").render(service_common_traefik=context)
    route = yaml.safe_load(route_text)
    router = route["http"]["routers"]["loki"]
    middleware = route["http"]["middlewares"]["loki-private-ui-chain"]["chain"]["middlewares"]

    assert service["traefik"] == {"enable": True, "exposure": "private", "port": 3100}
    assert router["entryPoints"] == ["https_private"]
    assert router["rule"] == "Host(`loki.private.example.internal`)"
    assert router["middlewares"] == ["loki-private-ui-chain"]
    assert middleware == ["secure-headers@file", "robots-noindex@file", "hsts@file", "gzip@file"]
    assert "authelia@file" not in route_text
    assert 'address: ":{{ services_private_https_port }}"' in static_traefik
    assert "{{ services_internal_zone }}" in static_traefik
    assert native_url == "https://loki.private.example.internal:9443/loki/api/v1/push"
    assert 'url = "http://loki:3100/loki/api/v1/push"' in render_docker_alloy()
    assert re.search(r"^\s+\"loki\",$", dns, flags=re.MULTILINE)
    assert "retention_period: 168h" in loki_config
    assert "replication_factor: 1" in loki_config
    assert "object_store: filesystem" in loki_config
    assert "schema: v13" in loki_config


def test_runtime_only_apps_do_not_gain_duplicate_file_logging():
    authelia_service = load_service("authelia")
    authelia_config = (REPO_ROOT / "ansible/roles/service_common/templates/configs/proxy/authelia/config.yml.j2").read_text()
    homepage = load_service("homepage")
    unpackerr = load_service("unpackerr")
    alloy_config = render_docker_alloy()

    assert "file_path" not in authelia_config
    assert "keep_stdout" not in authelia_config
    assert all(volume.get("target") != "/config/logs" for volume in authelia_service.get("volumes", {}).values())
    assert "authelia.log" not in alloy_config
    old_log_name = "authelia" + ".log"
    old_log_path = "/config/logs/" + old_log_name
    for path in (REPO_ROOT / "ansible").rglob("*"):
        if path.is_file() and path.suffix in {".yml", ".j2", ".py"}:
            text = path.read_text()
            assert old_log_name not in text
            assert old_log_path not in text
    assert homepage["environment"]["LOG_TARGETS"] == "stdout"
    assert "UN_LOG_FILE" not in unpackerr["environment"]
    assert "unpackerr" not in alloy_config


def test_native_application_rotation_is_bounded():
    qbittorrent = (REPO_ROOT / "ansible/roles/service_common/templates/configs/qbittorrent/qBittorrent.conf.j2").read_text()
    sabnzbd = (REPO_ROOT / "ansible/roles/service_common/templates/configs/sabnzbd.ini.j2").read_text()

    assert r"FileLogger\MaxSizeBytes=5242880" in qbittorrent
    assert r"FileLogger\Backup=true" in qbittorrent
    assert r"FileLogger\DeleteOld=true" in qbittorrent
    assert r"FileLogger\Age=1" in qbittorrent
    assert r"FileLogger\AgeType=1" in qbittorrent
    assert "max_log_size = 5242880" in sabnzbd
    assert "log_backups = 5" in sabnzbd


def owned_file_targets(config: str) -> list[tuple[str, str, str]]:
    return re.findall(
        r"""\{\s+__path__\s*=\s*"([^"]+)",\s+
        __tmp_owner_host\s*=\s*"([^"]+)",[^}]*?\bservice\s+=\s+"([^"]+)",[^}]*?\}""",
        config,
        flags=re.VERBOSE,
    )


def test_docker_file_targets_are_filtered_to_their_inventory_owner_before_discovery():
    config = render_docker_alloy()
    targets = owned_file_targets(config)

    storage_services = {
        "qbittorrent-alpha",
        "qbittorrent-bravo",
        "sabnzbd",
        "radarr",
        "radarr-4k",
        "sonarr",
        "sonarr-4k",
        "lidarr",
        "prowlarr",
        "whisparr",
        "bazarr",
        "recyclarr",
        "nzbhydra2",
    }
    plex_services = {"plex", "tautulli", "kometa", "imagemaid", "technitium"}
    controller_services = {"seerr", "unifi", "technitium", "traefik"}

    assert len(targets) == 23
    assert {service for _, owner, service in targets if owner == "unraid"} == storage_services
    assert {service for _, owner, service in targets if owner == "plex"} == plex_services
    assert {service for _, owner, service in targets if owner == "mgt"} == controller_services
    application_gate = config.split('discovery.relabel "application_paths_owned" {', 1)[1].split('local.file_match "applications" {', 1)[0]
    traefik_gate = config.split('discovery.relabel "traefik_access_path_owned" {', 1)[1].split('local.file_match "traefik_access" {', 1)[0]
    for gate in (application_gate, traefik_gate):
        assert gate.count('action        = "keepequal"') == 1
        assert gate.count('source_labels = ["__tmp_owner_host"]') == 1
        assert gate.count('replacement  = sys.env("ALLOY_HOST")') == 1
    assert "constants.hostname" not in config
    assert "path_targets = discovery.relabel.application_paths_owned.output" in config
    assert "path_targets = discovery.relabel.traefik_access_path_owned.output" in config
