import importlib.util
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, FileSystemLoader

REPO_ROOT = Path(__file__).resolve().parents[2]
ROLE_DIR = REPO_ROOT / "ansible/roles/service_common"
FILTER_PATH = ROLE_DIR / "filter_plugins/service_common.py"
spec = importlib.util.spec_from_file_location("service_common", FILTER_PATH)
service_common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service_common)


def render(
    service,
    name="example",
    target_hosts=None,
    hostvars=None,
    public_zone="public.example",
    internal_zone="private.example.internal",
):
    context = service_common.service_common_traefik_context(
        service,
        name,
        target_hosts or ["manager"],
        public_zone,
        internal_zone,
        hostvars or {"manager": {"local_ip": "192.0.2.10"}},
    )
    env = Environment(loader=FileSystemLoader(ROLE_DIR / "templates"), trim_blocks=True, lstrip_blocks=True)
    text = env.get_template("traefik/dynamic.yml.j2").render(service_common_traefik=context)
    return text, yaml.safe_load(text)


def test_public_docker_baseline_renders_all_existing_middleware_and_tls_behaviour():
    service = {
        "traefik": {
            "enable": True,
            "exposure": "public",
            "port": 8080,
            "sso": "authelia",
            "internal_api": True,
            "internal_api_rules": ["PathPrefix(`/api`)", "PathPrefix(`/metrics`)"],
            "themepark": {"app": "sonarr", "theme": "hotline"},
        }
    }

    text, document = render(service, name="sonarr")

    router = document["http"]["routers"]["sonarr"]
    assert router["entryPoints"] == ["https"]
    assert router["rule"] == "Host(`sonarr.public.example`)"
    assert router["tls"] == {"options": "securetls@file", "certResolver": "dns-cloudflare"}
    assert document["http"]["services"]["sonarr-svc"]["loadBalancer"]["servers"] == [{"url": "http://sonarr:8080"}]
    assert "crowdsec@file" in text
    assert "authelia@file" in text
    assert "secure-headers@file" in text
    assert "robots-noindex@file" in text
    assert "hsts@file" in text
    assert "gzip@file" in text
    assert "themepark-sonarr@file" in text
    assert "PathPrefix(`/api`) || PathPrefix(`/metrics`)" in text


def test_private_route_uses_private_entrypoint_and_excludes_crowdsec():
    text, document = render({"traefik": {"enable": True, "exposure": "private", "port": 3000}}, name="grafana")

    router = document["http"]["routers"]["grafana"]
    assert router["entryPoints"] == ["https_private"]
    assert router["rule"] == "Host(`grafana.private.example.internal`)"
    assert router["middlewares"] == ["grafana-private-ui-chain"]
    assert "crowdsec@file" not in text


def test_explicit_backend_host_does_not_evaluate_missing_inventory_host():
    service = {
        "traefik": {
            "enable": True,
            "exposure": "private",
            "port": 5678,
            "backend_mode": "host",
            "backend_host": "192.0.2.55",
            "backend_host_inventory": "missing-host",
        }
    }

    _, document = render(service, name="n8n", hostvars={})

    assert document["http"]["services"]["n8n-svc"]["loadBalancer"]["servers"][0]["url"] == "http://192.0.2.55:5678"


def test_inventory_host_backend_resolves_n8n_vm_address_and_port():
    service = {
        "traefik": {
            "enable": True,
            "exposure": "private",
            "port": 5678,
            "backend_mode": "host",
            "backend_host_inventory": "n8n",
        }
    }

    _, document = render(service, name="n8n", target_hosts=["n8n"], hostvars={"n8n": {"local_ip": "192.0.2.98"}})

    assert document["http"]["services"]["n8n-svc"]["loadBalancer"]["servers"][0]["url"] == "http://192.0.2.98:5678"


def test_backend_url_scheme_and_middleware_overrides_are_preserved():
    service = {
        "traefik": {
            "enable": True,
            "exposure": "public",
            "port": 443,
            "backend_scheme": "https",
            "backend_url": "https://upstream.example.test:9443/base",
            "middleware_chain": "custom-chain@file",
            "headers_middleware": "custom-headers@file",
        }
    }

    text, document = render(service)

    router = document["http"]["routers"]["example"]
    assert router["middlewares"] == ["custom-chain@file"]
    assert "custom-headers@file" in text
    assert document["http"]["services"]["example-svc"]["loadBalancer"]["servers"][0]["url"] == ("https://upstream.example.test:9443/base")


def test_explicit_zone_override_wins_for_either_exposure():
    _, document = render(
        {"traefik": {"enable": True, "exposure": "private", "zone": "override.example", "port": 8080}},
        name="app",
        public_zone="",
        internal_zone="",
    )

    assert document["http"]["routers"]["app"]["rule"] == "Host(`app.override.example`)"


@pytest.mark.parametrize(
    ("exposure", "public_zone", "internal_zone", "missing_name"),
    [
        ("public", "", "private.example.internal", "service_common_traefik_public_zone"),
        ("private", "public.example", "", "service_common_traefik_internal_zone"),
    ],
)
def test_selected_exposure_requires_its_independent_zone(exposure, public_zone, internal_zone, missing_name):
    with pytest.raises(service_common.AnsibleFilterError, match=missing_name):
        render(
            {"traefik": {"enable": True, "exposure": exposure, "port": 8080}},
            public_zone=public_zone,
            internal_zone=internal_zone,
        )


def test_equivalent_docker_and_podman_inputs_render_identically():
    traefik = {
        "enable": True,
        "exposure": "private",
        "port": 5678,
        "backend_mode": "host",
        "backend_host_inventory": "n8n",
    }
    docker_input = {"image": "example/n8n:1", "environment": {}, "traefik": traefik}
    podman_input = {"container": {"image": "example/n8n:1"}, "env": {}, "traefik": traefik}
    kwargs = {"name": "n8n", "target_hosts": ["n8n"], "hostvars": {"n8n": {"local_ip": "192.0.2.98"}}}

    assert render(docker_input, **kwargs)[0] == render(podman_input, **kwargs)[0]
