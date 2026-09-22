from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import pytest
import yaml
from jinja2 import Environment, StrictUndefined
from jinja2.nativetypes import NativeEnvironment

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_DIR = REPO_ROOT / "ansible/group_vars/all/services"
TEMPLATE_DIR = REPO_ROOT / "ansible/roles/service_common/templates/configs"
PREPARE_DIR = REPO_ROOT / "ansible/roles/service_prepare/tasks/applications"
CLOUDFLARE_HOMELAB_DIR = REPO_ROOT / "terraform/cloudflare/homelab"
TOPOLOGY = {
    "services_public_zone": "public.example",
    "services_internal_zone": "private.example.internal",
    "services_private_https_port": 9443,
}


def load_service(name: str):
    return yaml.safe_load((SERVICES_DIR / f"{name}.yml").read_text())[name]


def iter_secret_declarations(value):
    if isinstance(value, dict):
        infisical = value.get("infisical")
        if isinstance(infisical, dict):
            yield from infisical.get("secrets_map") or []
        for child in value.values():
            yield from iter_secret_declarations(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_secret_declarations(child)


def fake_lookup_values(service):
    return {declaration["var"]: f"fixture-{declaration['var']}" for declaration in iter_secret_declarations(service)}


def render_template(service_name: str, relative_path: str):
    service = load_service(service_name)
    return (
        Environment(undefined=StrictUndefined)
        .from_string((TEMPLATE_DIR / relative_path).read_text())
        .render(
            service_common_infisical_values=fake_lookup_values(service),
            services_plex_host="plex-host",
            services_storage_host="storage-host",
            hostvars={
                "plex-host": {"local_ip": "192.0.2.59"},
                "storage-host": {"local_ip": "192.0.2.60"},
            },
            **TOPOLOGY,
        )
    )


def task_named(path: Path, name: str):
    return next(task for task in yaml.safe_load(path.read_text()) if task.get("name") == name)


def render_expression(expression: str, lookup_values: dict[str, str] | None = None):
    return (
        NativeEnvironment(undefined=StrictUndefined)
        .from_string(expression)
        .render(service_prepare_context={"lookup_values": lookup_values or {}}, **TOPOLOGY)
    )


@pytest.mark.parametrize("service_name", ["unpackerr", "scraparr"])
def test_application_url_environment_uses_inventory_topology(service_name):
    service = load_service(service_name)
    url_values = {
        name: value
        for name, value in service["environment"].items()
        if name.endswith("_URL") and isinstance(value, str) and value.startswith("https://")
    }

    assert url_values
    for value in url_values.values():
        url = NativeEnvironment(undefined=StrictUndefined).from_string(value).render(**TOPOLOGY)
        parsed = urlparse(url)
        assert parsed.scheme == "https"
        assert parsed.hostname.endswith(".private.example.internal")
        assert parsed.port == 9443


def test_service_infisical_declarations_do_not_contain_dns_topology():
    for path in sorted(SERVICES_DIR.glob("*.yml")):
        for service in (yaml.safe_load(path.read_text()) or {}).values():
            declarations = (service.get("infisical") or {}).get("secrets_map") or []
            assert "cloudflare_zone" not in {item.get("var") for item in declarations}, path.name


@pytest.mark.parametrize(
    ("service_name", "relative_path"),
    [
        ("recyclarr", "recyclarr/secrets.yml.j2"),
        ("kometa", "kometa.yml.j2"),
        ("grafana", "grafana/provisioning/datasources/prometheus.yml.j2"),
        ("loki", "loki-config.yaml.j2"),
        ("authelia", "proxy/authelia/config.yml.j2"),
        ("traefik", "proxy/authelia/router.yml.j2"),
        ("traefik", "proxy/traefik/config.yml.j2"),
        ("traefik", "proxy/traefik/dashboard.yml.j2"),
    ],
)
def test_touched_yaml_templates_render_strictly_and_parse(service_name, relative_path):
    assert isinstance(yaml.safe_load(render_template(service_name, relative_path)), dict)


def test_touched_environment_templates_render_strictly():
    for service_name, relative_path in (
        ("authelia", "proxy/authelia/authelia.env.j2"),
        ("grafana", "grafana/grafana.env.j2"),
        ("opencloud", "opencloud/opencloud.env.j2"),
    ):
        rendered = render_template(service_name, relative_path)
        assert rendered.strip()
        assert "{{" not in rendered


def test_former_public_application_urls_use_private_inventory_topology():
    rendered = render_template("vaultwarden", "vaultwarden.env.j2")
    environment = dict(line.split("=", 1) for line in rendered.splitlines() if line and not line.startswith("#") and "=" in line)
    assert environment["DOMAIN"] == "https://vaultwarden.private.example.internal:9443"

    opencloud = dict(
        line.split("=", 1)
        for line in render_template("opencloud", "opencloud/opencloud.env.j2").splitlines()
        if line and not line.startswith("#") and "=" in line
    )
    assert opencloud["OC_URL"] == "https://opencloud.private.example.internal:9443"

    grafana = dict(
        line.split("=", 1)
        for line in render_template("grafana", "grafana/grafana.env.j2").splitlines()
        if line and not line.startswith("#") and "=" in line
    )
    assert grafana["GF_AUTH_GENERIC_OAUTH_AUTH_URL"] == ("https://authelia.private.example.internal:9443/api/oidc/authorization")
    assert grafana["GF_AUTH_GENERIC_OAUTH_TOKEN_URL"] == "https://authelia.private.example.internal:9443/api/oidc/token"
    assert grafana["GF_AUTH_GENERIC_OAUTH_API_URL"] == "https://authelia.private.example.internal:9443/api/oidc/userinfo"
    assert grafana["GF_AUTH_SIGNOUT_REDIRECT_URL"] == "https://authelia.private.example.internal:9443/logout"

    authelia = yaml.safe_load(render_template("authelia", "proxy/authelia/config.yml.j2"))
    assert authelia["access_control"]["rules"][0]["domain"] == [
        "*.private.example.internal",
        "private.example.internal",
    ]
    cookie = authelia["session"]["cookies"][0]
    assert cookie == {
        "domain": "private.example.internal",
        "authelia_url": "https://authelia.private.example.internal:9443",
        "default_redirection_url": "https://homepage.private.example.internal:9443",
    }

    authelia_env = dict(
        line.split("=", 1)
        for line in render_template("authelia", "proxy/authelia/authelia.env.j2").splitlines()
        if line and not line.startswith("#") and "=" in line
    )
    assert authelia_env["AUTHELIA_SESSION_NAME"] == "authelia_session_internal"
    assert authelia_env["AUTHELIA_TOTP_ISSUER"] == "private.example.internal"
    assert "https://*.private.example.internal:9443" in authelia_env["AUTHELIA_SERVER_HEADERS_CSP_TEMPLATE"]
    assert "public.example" not in authelia_env["AUTHELIA_SERVER_HEADERS_CSP_TEMPLATE"]

    router = yaml.safe_load(render_template("traefik", "proxy/authelia/router.yml.j2"))["http"]["routers"]["authelia"]
    assert router["entryPoints"] == ["https_private"]
    assert router["rule"] == "Host(`authelia.private.example.internal`)"


def test_every_catalog_traefik_route_is_private_and_published_by_technitium():
    route_names = {"authelia"}
    for path in sorted(SERVICES_DIR.glob("*.yml")):
        for base_key, base in (yaml.safe_load(path.read_text()) or {}).items():
            targets = base.get("targets") or {}
            candidates = [] if targets else [(base_key, base)]
            for target_key, target in targets.items():
                effective = {**base, **target}
                effective["traefik"] = {**(base.get("traefik") or {}), **(target.get("traefik") or {})}
                candidates.append((target_key, effective))

            for candidate_key, service in candidates:
                traefik = service.get("traefik") or {}
                if traefik.get("enable") is not True:
                    continue
                assert traefik.get("exposure", "private") == "private", path.name
                route_names.add(traefik.get("subdomain") or service.get("name") or candidate_key.replace("_", "-"))

    technitium_source = (REPO_ROOT / "terraform/technitium/internal-dns/main.tf").read_text()
    record_block = technitium_source.split("ipv4_records = [", 1)[1].split("]", 1)[0]
    internal_aliases = set(re.findall(r'^\s+"([^"]+)",$', record_block, flags=re.MULTILINE))

    assert route_names <= internal_aliases


def test_cloudflare_homelab_root_owns_mail_dns_without_application_a_records():
    main_source = (CLOUDFLARE_HOMELAB_DIR / "main.tf").read_text()
    root_source = "\n".join(path.read_text() for path in sorted(CLOUDFLARE_HOMELAB_DIR.glob("*.tf")))
    sample_variables = (CLOUDFLARE_HOMELAB_DIR / "secrets.auto.tfvars.sample").read_text()
    record_resources = set(
        re.findall(
            r'resource\s+"cloudflare_dns_record"\s+"([^"]+)"',
            main_source,
        )
    )

    assert record_resources == {
        "mx_fwd1",
        "mx_fwd2",
        "txt_dkim_default",
        "txt_dmarc",
        "txt_spf",
    }
    assert re.search(r'\btype\s*=\s*"A"', main_source) is None
    assert "service_a" not in root_source
    assert "public_ipv4" not in root_source
    assert "public_ipv4" not in sample_variables

    workflow = (REPO_ROOT / ".github/workflows/tofu-check.yml").read_text()
    assert "terraform/cloudflare/homelab" in workflow
    assert "terraform/cloudflare/domain" not in workflow


def test_traefik_exposes_only_private_https_and_operational_entrypoints():
    config = yaml.safe_load(render_template("traefik", "proxy/traefik/config.yml.j2"))
    assert set(config["entryPoints"]) == {"https_private", "ping", "metrics"}
    assert config["entryPoints"]["https_private"]["address"] == ":9443"
    assert config["entryPoints"]["https_private"]["http"]["tls"]["domains"] == [
        {"main": "private.example.internal", "sans": ["*.private.example.internal"]}
    ]
    assert "dns-cloudflare" in config["certificatesResolvers"]

    ports = load_service("traefik")["ports"]
    assert set(ports) == {"web_secure_private"}
    assert ports["web_secure_private"]["published"] == "{{ services_private_https_port }}"


def test_sabnzbd_whitelist_accepts_stable_internal_endpoint_and_inventory_host():
    rendered = render_template("sabnzbd", "sabnzbd.ini.j2")
    whitelist_line = next(line for line in rendered.splitlines() if line.startswith("host_whitelist = "))
    whitelist = {host.strip() for host in whitelist_line.split("=", 1)[1].split(",")}

    assert "192.0.2.60" in whitelist
    assert "sabnzbd.private.example.internal" in whitelist
    assert "192.168.80.20" not in whitelist
    assert not any("nosugarmaxtaste.com" in host for host in whitelist)


def test_recyclarr_uses_matching_private_application_endpoints_with_trailing_slashes():
    config = yaml.safe_load(render_template("recyclarr", "recyclarr/secrets.yml.j2"))
    base_urls = {name: value for name, value in config.items() if name.endswith("_base_url")}

    assert base_urls
    for name, url in base_urls.items():
        service_name = name.removesuffix("_base_url").replace("_", "-")
        parsed = urlparse(url)
        assert parsed.scheme == "https"
        assert parsed.hostname == f"{service_name}.private.example.internal"
        assert parsed.port == 9443
        assert parsed.path == "/"


def test_kometa_and_imagemaid_use_stable_application_interfaces_without_overwrite_changes():
    kometa = yaml.safe_load(render_template("kometa", "kometa.yml.j2"))
    for integration in ("radarr", "sonarr", "tautulli"):
        parsed = urlparse(kometa[integration]["url"])
        assert parsed.scheme == "https"
        assert parsed.hostname == f"{integration}.private.example.internal"
        assert parsed.port == 9443
    assert kometa["plex"]["url"] == "http://192.0.2.59:32400"

    imagemaid = dict(
        line.split("=", 1) for line in render_template("imagemaid", "imagemaid.j2").splitlines() if line and not line.startswith("#")
    )
    assert imagemaid["PLEX_URL"] == "http://192.0.2.59:32400/"

    for service_name, source in (("kometa", "configs/kometa.yml.j2"), ("imagemaid", "configs/imagemaid.j2")):
        template = next(item for item in load_service(service_name)["templates"] if item["src"] == source)
        assert template["force"] is False


def test_grafana_query_datasources_use_private_application_endpoints():
    config = yaml.safe_load(render_template("grafana", "grafana/provisioning/datasources/prometheus.yml.j2"))
    for datasource in config["datasources"]:
        parsed = urlparse(datasource["url"])
        assert parsed.scheme == "https"
        assert parsed.hostname == f"{datasource['name'].lower()}.private.example.internal"
        assert parsed.port == 9443


def test_bazarr_preparation_persists_private_tls_endpoints():
    service = load_service("bazarr")
    configure_path = PREPARE_DIR / "bazarr/configure.yml"
    lookup_task = task_named(configure_path, "Prep - Bazarr | Set secret vars")
    facts = lookup_task["ansible.builtin.set_fact"]
    assert set(service["prep"]) == {"postgres"}
    assert render_expression(facts["service_prepare_bazarr_radarr_ip"]) == "radarr.private.example.internal"
    assert str(render_expression(facts["service_prepare_bazarr_radarr_port"])) == "9443"
    assert render_expression(facts["service_prepare_bazarr_sonarr_ip"]) == "sonarr.private.example.internal"
    assert str(render_expression(facts["service_prepare_bazarr_sonarr_port"])) == "9443"

    radarr = task_named(configure_path, "Prep - Bazarr | Configure radarr settings")["vars"]["_bazarr_radarr_config"]
    sonarr = task_named(configure_path, "Prep - Bazarr | Configure sonarr settings")["vars"]["_bazarr_sonarr_config"]
    assert radarr["radarr.ssl"] == "true"
    assert sonarr["sonarr.ssl"] == "true"


def test_nzbhydra2_preparation_persists_private_sabnzbd_endpoint():
    service = load_service("nzbhydra2")
    configure_path = PREPARE_DIR / "nzbhydra2/configure.yml"
    facts = task_named(configure_path, "Prep - NZBHydra2 | Set derived vars")["ansible.builtin.set_fact"]

    assert "prep" not in service
    assert render_expression(facts["service_prepare_nzbhydra2_sabnzbd_url"]) == "https://sabnzbd.private.example.internal:9443"


def test_observability_control_plane_links_remain_direct():
    prometheus = (TEMPLATE_DIR / "prometheus/prometheus.yml.j2").read_text()
    alloy = (REPO_ROOT / "ansible/roles/docker_services/files/alloy_config.alloy").read_text()
    loki = yaml.safe_load(render_template("loki", "loki-config.yaml.j2"))

    assert 'targets: ["alertmanager:9093"]' in prometheus
    assert 'targets: ["prometheus:9090"]' in prometheus
    assert 'url = "http://loki:3100/loki/api/v1/push"' in alloy
    assert 'url = "http://prometheus:9090/api/v1/write"' in alloy
    assert loki["ruler"]["alertmanager_url"] == "http://alertmanager:9093"


def test_uptime_kuma_uses_only_internal_homelab_routes_and_dns():
    locals_source = (REPO_ROOT / "terraform/uptime-kuma/locals.tf").read_text()
    tags_source = (REPO_ROOT / "terraform/uptime-kuma/tags.tf").read_text()
    private_services = locals_source.split("private_http_services = {", 1)[1].split("private_http_monitors = {", 1)[0]
    status_pages = (REPO_ROOT / "terraform/uptime-kuma/status-pages.tf").read_text()

    declared_tag_keys = set(re.findall(r"^    ([a-z0-9_-]+)\s+=\s+\{ name =", tags_source, flags=re.MULTILINE))
    used_tag_keys = {
        tag_key for tag_list in re.findall(r"tag_keys\s+=\s+\[([^]]+)]", locals_source) for tag_key in re.findall(r'"([^"]+)"', tag_list)
    }

    assert re.search(r"^\s*traefik\s*=", private_services, flags=re.MULTILINE)
    assert all(f"{service} " in private_services for service in ("authelia", "opencloud", "vaultwarden"))
    assert "public_http_services" not in locals_source
    assert "cloudflare_zone" not in locals_source
    assert "http.traefik-private" in status_pages
    assert "http.traefik-public" not in status_pages
    assert "traefik_private_tcp = {" in locals_source
    assert "traefik_public_tcp = {" not in locals_source
    assert 'hostname           = "opencloud.${local.internal_zone}"' in locals_source
    assert 'dns_resolve_server = local.dns_ips["dns_vip_a"]' in locals_source
    assert "dns.technitium_internal" in status_pages
    assert used_tag_keys <= declared_tag_keys


def test_orphaned_endpoint_templates_are_removed():
    assert not (TEMPLATE_DIR / "scraparr-config.yaml.j2").exists()
    assert not (TEMPLATE_DIR / "autopulse.env.j2").exists()
