import importlib.util
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from jinja2.nativetypes import NativeEnvironment

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE_PATH = REPO_ROOT / "ansible/group_vars/all/services/homepage.yml"
PODMAN_ROLE = REPO_ROOT / "ansible/roles/podman_services"
COMMON_ROLE = REPO_ROOT / "ansible/roles/service_common"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


podman_filters = load_module(PODMAN_ROLE / "filter_plugins/podman_services.py", "podman_services_homepage")
common_filters = load_module(COMMON_ROLE / "filter_plugins/service_common.py", "service_common_homepage")


def render_structure(value, variables):
    if isinstance(value, dict):
        return {key: render_structure(item, variables) for key, item in value.items()}
    if isinstance(value, list):
        return [render_structure(item, variables) for item in value]
    if isinstance(value, str) and ("{{" in value or "{%" in value):
        return NativeEnvironment(undefined=StrictUndefined).from_string(value).render(**variables)
    return value


def homepage_service():
    service = yaml.safe_load(SERVICE_PATH.read_text())["homepage"]
    return render_structure(
        service,
        {
            "services_controller_host": "manager",
            "services_public_zone": "public.example",
            "services_internal_zone": "private.example.internal",
            "services_private_https_port": 9443,
            "local_ip": "192.0.2.10",
            "timezone": "Australia/Melbourne",
            "hostvars": {
                "manager": {
                    "local_ip": "192.0.2.10",
                    "container_host_puid": 1000,
                    "container_host_pgid": 1000,
                    "container_host_appdata_root": "/opt",
                }
            },
        },
    )


def render_quadlet(name, service):
    environment = Environment(loader=FileSystemLoader(PODMAN_ROLE / "templates"), trim_blocks=True, lstrip_blocks=True)
    environment.filters["podman_env_file_key"] = podman_filters.podman_env_file_key
    environment.filters["podman_env_file_value"] = podman_filters.podman_env_file_value
    return environment.get_template(name).render(
        podman_service=service,
        podman_services_quadlet_dir="/var/lib/podman-homepage/.config/containers/systemd",
    )


def test_homepage_allowed_host_and_traefik_backend_use_canonical_runtime_neutral_interfaces():
    service = homepage_service()
    lookup_config = common_filters.service_common_infisical_normalize(service["infisical"]["secrets_map"])
    resolved_environment = common_filters.service_common_environment_resolve(
        service["environment"],
        {},
        lookup_config,
    )
    traefik = common_filters.service_common_traefik_context(
        service,
        "homepage",
        ["manager"],
        "private.example.internal",
        {"manager": {"local_ip": "192.0.2.10"}},
    )

    assert resolved_environment["HOMEPAGE_ALLOWED_HOSTS"] == "homepage.private.example.internal:9443"
    assert traefik["address"] == "homepage.private.example.internal"
    assert traefik["backend_url"] == "http://192.0.2.10:13000"

    normalized = podman_filters.podman_service_normalize(service, "homepage")
    normalized["env"] = resolved_environment
    container = render_quadlet("container.container.j2", normalized)
    env_file = render_quadlet("env.env.j2", normalized)
    assert "UserNS=keep-id:uid=1000,gid=1000" in container
    assert "PublishPort=192.0.2.10:13000:3000/tcp" in container
    assert "Volume=/opt/homepage:/app/config" in container
    assert "Volume=/opt/homepage/images:/app/public/images:ro" in container
    assert "HOMEPAGE_ALLOWED_HOSTS=homepage.private.example.internal:9443" in env_file
