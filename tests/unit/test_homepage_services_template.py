from pathlib import Path

import yaml
from jinja2 import Environment, StrictUndefined

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = REPO_ROOT / "ansible/roles/service_common/templates/configs/homepage/services.yaml.j2"
SETTINGS_PATH = REPO_ROOT / "ansible/roles/service_common/templates/configs/homepage/settings.yaml.j2"
SERVICES_DIR = REPO_ROOT / "ansible/group_vars/all/services"


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
        "unifi_pass": "fake-unifi-pass",
        "unifi_user": "fake-unifi-user",
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


def services_by_group():
    return {name: services for group in render_services() for name, services in group.items()}


def render_settings():
    rendered = (
        Environment(undefined=StrictUndefined)
        .from_string(SETTINGS_PATH.read_text())
        .render(service_common_infisical_values={"cloudflare_zone": "example.test"})
    )
    return yaml.safe_load(rendered)


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
    assert services["UniFi"]["widget"] == {
        "type": "unifi",
        "url": "https://192.168.80.48:11443",
        "username": "fake-unifi-user",
        "password": "fake-unifi-pass",
        "fields": ["uptime", "lan_users", "wlan_users", "wlan_devices"],
    }


def test_enabled_web_app_definitions_have_dashboard_cards():
    expected_cards = {
        "adminer.yml": "Adminer",
        "alertmanager.yml": "Alertmanager",
        "alloy.yml": "Alloy",
        "czkawka.yml": "Czkawka",
        "gitea.yml": "Gitea",
        "gotify.yml": "Gotify",
        "n8n.yml": "n8n",
        "nzbhydra2.yml": "NZBHydra2",
        "obsidian.yml": "Obsidian",
        "qui.yml": "Qui",
        "unifi-os.yml": "UniFi",
        "uptime-kuma.yml": "Uptime Kuma",
        "wallos.yml": "Wallos",
    }
    dashboard_services = services_by_name()

    for filename, card_name in expected_cards.items():
        service_definition = next(iter((yaml.safe_load((SERVICES_DIR / filename).read_text()) or {}).values()))
        assert service_definition["enabled"] is True
        assert card_name in dashboard_services


def test_service_group_layouts_fill_complete_rows():
    groups = services_by_group()
    layout = render_settings()["layout"]
    expected_columns = {
        "arrs": 3,
        "gaming": 1,
        "media": 3,
        "monitoring": 4,
        "network": 3,
        "plex": 2,
        "torrents": 3,
        "usenet": 2,
        "utilities": 3,
    }

    assert set(groups) == set(expected_columns)
    for group_name, columns in expected_columns.items():
        assert layout[group_name]["style"] == "row"
        assert layout[group_name]["columns"] == columns
        assert len(groups[group_name]) % columns == 0
