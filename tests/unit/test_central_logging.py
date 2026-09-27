import json
import re
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_DIR = REPO_ROOT / "ansible/group_vars/all/services"
DOCKER_ALLOY_PATH = REPO_ROOT / "ansible/roles/docker_services/templates/alloy_config.alloy.j2"


def load_service(name: str):
    return yaml.safe_load((SERVICES_DIR / f"{name}.yml").read_text())[name]


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
    paths = set(re.findall(r"__path__ = \"([^\"]+)\"", config))

    expected_paths = {
        "/host/rootfs/var/log/skynet/traefik/access.log",
        "/host/rootfs/mnt/user/appdata/qbittorrent-alpha/log/qbittorrent.log",
        "/host/rootfs/mnt/user/appdata/qbittorrent-bravo/log/qbittorrent.log",
        "/host/rootfs/mnt/user/appdata/sabnzbd/logs/sabnzbd.log",
        "/host/rootfs/mnt/user/appdata/radarr/logs/radarr.txt",
        "/host/rootfs/mnt/user/appdata/radarr-4k/logs/radarr.txt",
        "/host/rootfs/mnt/user/appdata/sonarr/logs/sonarr.txt",
        "/host/rootfs/mnt/user/appdata/sonarr-4k/logs/sonarr.txt",
        "/host/rootfs/mnt/user/appdata/lidarr/logs/lidarr.txt",
        "/host/rootfs/mnt/user/appdata/prowlarr/logs/prowlarr.txt",
        "/host/rootfs/mnt/user/appdata/whisparr/logs/whisparr.txt",
        "/host/rootfs/mnt/user/appdata/bazarr/log/bazarr.log",
        "/host/rootfs/mnt/user/appdata/recyclarr/logs/debug.log",
        "/host/rootfs/mnt/user/appdata/nzbhydra2/app/logs/nzbhydra2.log",
        "/host/rootfs/mnt/user/appdata/nzbhydra2/app/logs/wrapper.log",
        "/host/rootfs/mnt/plex-apps/plex/Library/Logs/Plex Media Server/Plex Media Server.log",
        "/host/rootfs/mnt/plex-apps/tautulli/logs/tautulli.log",
        "/host/rootfs/mnt/plex-apps/kometa/logs/meta.log",
        "/host/rootfs/mnt/plex-apps/imagemaid/logs/imagemaid.log",
        "/host/rootfs/srv/apps/seerr/logs/seerr.log",
        "/host/rootfs/srv/apps/unifi-os/var-log/unifi/server.log",
        "/host/rootfs/srv/apps/technitium/logs/*.log",
        "/host/rootfs/mnt/plex-apps/technitium/logs/*.log",
    }
    assert paths == expected_paths
    assert all("**" not in path for path in paths)
    assert all("*" not in path or path.endswith("/technitium/logs/*.log") for path in paths)
    assert all(not path.endswith((".gz", ".zip", ".bak")) for path in paths)
    assert 'ignore_older_than = "24h"' in config
    assert config.count("tail_from_end") == 2
    assert config.count('on_positions_file_error = "restart_from_end"') == 2


def test_technitium_source_is_not_duplicated_when_nodes_share_appdata_root():
    config = render_docker_alloy(shared_appdata_root=True)
    assert config.count("/host/rootfs/opt/technitium/logs/*.log") == 1


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


def test_loki_remains_private_single_node_filesystem_with_seven_day_retention():
    service = load_service("loki")
    config = (REPO_ROOT / "ansible/roles/service_common/templates/configs/loki-config.yaml.j2").read_text()
    dns = (REPO_ROOT / "terraform/technitium/internal-dns/main.tf").read_text()

    assert service["traefik"] == {"enable": True, "exposure": "private", "port": 3100}
    assert "sso" not in service["traefik"]
    assert "retention_period: 168h" in config
    assert "replication_factor: 1" in config
    assert "object_store: filesystem" in config
    assert "schema: v13" in config
    assert re.search(r"^\s+\"loki\",$", dns, flags=re.MULTILINE)


def test_runtime_only_apps_do_not_gain_duplicate_file_logging():
    authelia_service = load_service("authelia")
    authelia_config = (REPO_ROOT / "ansible/roles/service_common/templates/configs/proxy/authelia/config.yml.j2").read_text()
    homepage = load_service("homepage")
    uptime_kuma = yaml.safe_load((SERVICES_DIR / "uptime-kuma.yml").read_text())["uptime_kuma"]
    unpackerr = load_service("unpackerr")
    alloy_config = render_docker_alloy()

    assert "file_path" not in authelia_config
    assert "keep_stdout" not in authelia_config
    assert all(volume.get("target") != "/config/logs" for volume in authelia_service.get("volumes", {}).values())
    assert "authelia.log" not in alloy_config
    assert homepage["environment"]["LOG_TARGETS"] == "stdout"
    assert uptime_kuma["environment"]["UPTIME_KUMA_LOG_FORMAT"] == "json"
    assert "UN_LOG_FILE" not in unpackerr["environment"]
    assert "unpackerr" not in alloy_config


def test_native_rotation_is_bounded_and_dozzle_remains_available():
    qbittorrent = (REPO_ROOT / "ansible/roles/service_common/templates/configs/qbittorrent/qBittorrent.conf.j2").read_text()
    sabnzbd = (REPO_ROOT / "ansible/roles/service_common/templates/configs/sabnzbd.ini.j2").read_text()

    assert r"FileLogger\MaxSizeBytes=5242880" in qbittorrent
    assert r"FileLogger\Backup=true" in qbittorrent
    assert "max_log_size = 5242880" in sabnzbd
    assert "log_backups = 5" in sabnzbd
    assert (SERVICES_DIR / "dozzle.yml").exists()
