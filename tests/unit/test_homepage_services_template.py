from pathlib import Path

import yaml
from jinja2 import Environment, StrictUndefined

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = REPO_ROOT / "ansible/roles/service_common/templates/configs/homepage/services.yaml.j2"


def render_services():
    values = {
        "autobrr_api": "fake-autobrr-api",
        "bazarr_api": "fake-bazarr-api",
        "cloudflare_zone": "example.test",
        "grafana_pass": "fake-grafana-pass",
        "grafana_user": "fake-grafana-user",
        "lidarr_api": "fake-lidarr-api",
        "ombi_api": "fake-ombi-api",
        "plex_token": "fake-plex-token",
        "portainer_token": "fake-portainer-token",
        "prowlarr_api": "fake-prowlarr-api",
        "qui_downloads_token": "https://downloads-proxy.example.test",
        "qui_seeds_token": "https://seeds-proxy.example.test",
        "radarr_4k_api": "fake-radarr-4k-api",
        "radarr_api": "fake-radarr-api",
        "sabnzbd_api": "fake-sabnzbd-api",
        "seerr_api": "fake-seerr-api",
        "sonarr_4k_api": "fake-sonarr-4k-api",
        "sonarr_api": "fake-sonarr-api",
        "stash_api": "fake-stash-api",
        "tautulli_api": "fake-tautulli-api",
        "technitium_token": "fake-technitium-token",
    }
    rendered = Environment(undefined=StrictUndefined).from_string(TEMPLATE_PATH.read_text()).render(service_common_infisical_values=values)
    return yaml.safe_load(rendered)


def services_by_name():
    result = {}
    for group in render_services():
        for services in group.values():
            for service in services:
                result.update(service)
    return result


def test_widget_api_urls_use_stable_internal_application_routes():
    services = services_by_name()
    expected_urls = {
        name: f"https://{hostname}.int.example.test:8443"
        for name, hostname in {
            "Bazarr": "bazarr",
            "Lidarr": "lidarr",
            "Prowlarr": "prowlarr",
            "Radarr": "radarr",
            "Radarr-4K": "radarr-4k",
            "Sonarr": "sonarr",
            "Sonarr-4K": "sonarr-4k",
            "RomM": "romm",
            "Autobrr": "autobrr",
            "Ombi": "ombi",
            "Seerr": "seerr",
            "Stash": "stash",
            "Grafana": "grafana",
            "Portainer": "portainer",
            "Prometheus": "prometheus",
            "Tautulli": "tautulli",
            "SABnzbd": "sabnzbd",
        }.items()
    }

    for name, expected_url in expected_urls.items():
        assert services[name]["href"] == expected_url
        assert services[name]["widget"]["url"] == expected_url

    assert services["Plex"]["widget"]["url"] == services["Plex"]["href"] == "http://192.168.80.59:32400"


def test_widget_api_url_exceptions_remain_on_their_existing_endpoint_contracts():
    services = services_by_name()

    assert services["Traefik"]["widget"]["url"] == "http://traefik:8080"
    assert services["Technitium"]["widget"]["url"] == "http://192.168.80.48:5380"
    assert services["qBittorrent"]["widget"]["url"] == "https://downloads-proxy.example.test"
    assert services["qBittorrent-XS"]["widget"]["url"] == "https://seeds-proxy.example.test"
