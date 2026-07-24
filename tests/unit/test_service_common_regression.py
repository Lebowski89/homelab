from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_DIR = REPO_ROOT / "ansible/group_vars/all/services"
SENSITIVE_COMMON_TEMPLATES = {
    "configs/gitea.env.j2",
    "configs/gotify.env.j2",
    "configs/homepage/services.yaml.j2",
    "configs/imagemaid.j2",
    "configs/kometa.yml.j2",
    "configs/ombi.json.j2",
    "configs/opencloud/opencloud.env.j2",
    "configs/qui.env.j2",
    "configs/recyclarr/secrets.yml.j2",
    "configs/seerr.env.j2",
    "configs/stash.yml.j2",
    "configs/vaultwarden.env.j2",
}


def load_services():
    services = {}
    for path in sorted(SERVICES_DIR.glob("*.yml")):
        data = yaml.safe_load(path.read_text()) or {}
        assert isinstance(data, dict), f"{path} must contain a mapping"
        services.update(data)
    return services


def iter_common_sources(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"copies", "templates", "swarm_env_templates"} and isinstance(child, list):
                for item in child:
                    if isinstance(item, dict) and item.get("src"):
                        yield "templates" if key == "swarm_env_templates" else key, item["src"]
            yield from iter_common_sources(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_common_sources(child)


def source_path(kind, source):
    role = REPO_ROOT / "ansible/roles/service_common"
    return role / ("templates" if kind == "templates" else "") / source


def test_every_service_yaml_loads_as_a_mapping():
    paths = sorted(SERVICES_DIR.glob("*.yml"))
    assert paths
    for path in paths:
        assert isinstance(yaml.safe_load(path.read_text()) or {}, dict), path


def test_every_common_copy_and_template_source_exists():
    missing = []
    for service_name, service in load_services().items():
        for kind, source in iter_common_sources(service):
            path = source_path(kind, source)
            if not path.is_file():
                missing.append(f"{service_name}: {source} ({path})")
    assert not missing, "Missing common assets:\n" + "\n".join(missing)


def test_secret_bearing_common_templates_disable_logging_and_diffs():
    configured = {}

    def collect(value):
        if isinstance(value, dict):
            if value.get("src") in SENSITIVE_COMMON_TEMPLATES:
                configured[value["src"]] = value
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(load_services())

    assert set(configured) == SENSITIVE_COMMON_TEMPLATES
    assert all(item.get("no_log") is True for item in configured.values())
