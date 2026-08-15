from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlparse

import pytest
import yaml
from jinja2 import Environment, StrictUndefined, UndefinedError

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE_PATH = REPO_ROOT / "ansible/group_vars/all/services/homepage.yml"
TEMPLATE_PATH = REPO_ROOT / "ansible/roles/service_common/templates/configs/homepage/services.yaml.j2"
SETTINGS_PATH = REPO_ROOT / "ansible/roles/service_common/templates/configs/homepage/settings.yaml.j2"

# The rendered Homepage configuration is the source of truth for card and
# layout content. These tests validate rendering, structure, and runtime
# portability rather than duplicating the dashboard inventory. Homepage
# membership is intentionally curated; enabled services do not automatically
# require dashboard cards. UniFi is intentionally absent because this deployment
# uses unifi-os rather than Homepage's unifi-controller integration.


def load_homepage_definition():
    return yaml.safe_load(SERVICE_PATH.read_text())["homepage"]


def homepage_infisical_vars():
    return [declaration["var"] for declaration in load_homepage_definition()["infisical"]["secrets_map"]]


def fake_homepage_infisical_values():
    return {var: "example.test" if var == "cloudflare_zone" else f"https://fixture.example.test/{var}" for var in homepage_infisical_vars()}


def render_yaml_template(path, *, source=None, values=None):
    template_source = path.read_text() if source is None else source
    rendered = (
        Environment(undefined=StrictUndefined)
        .from_string(template_source)
        .render(service_common_infisical_values=fake_homepage_infisical_values() if values is None else values)
    )
    return yaml.safe_load(rendered)


def render_services(*, source=None, values=None):
    return render_yaml_template(TEMPLATE_PATH, source=source, values=values)


def render_settings():
    return render_yaml_template(SETTINGS_PATH)


def services_by_group():
    return {name: services for group in render_services() for name, services in group.items()}


def iter_service_cards(rendered_services):
    for group in rendered_services:
        for cards in group.values():
            for card in cards:
                yield from card.items()


def assert_service_group_layouts_are_valid(groups, settings):
    layout = settings.get("layout")
    assert isinstance(layout, dict)
    assert set(groups) <= set(layout), f"Service groups missing layout entries: {set(groups) - set(layout)}"

    for group_name in groups:
        entry = layout[group_name]
        assert isinstance(entry, dict), f"Layout for {group_name} must be a mapping"
        if "columns" in entry:
            columns = entry["columns"]
            assert isinstance(columns, int) and not isinstance(columns, bool) and columns > 0
        if "style" in entry:
            assert isinstance(entry["style"], str) and entry["style"].strip()


def assert_runtime_neutral_http_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return

    hostname = parsed.hostname
    assert hostname, f"Widget URL has no hostname: {url}"
    try:
        ip_address(hostname)
    except ValueError:
        assert "." in hostname, f"Widget URL uses a runtime-local hostname: {url}"


def test_fake_infisical_values_are_derived_from_homepage_declaration():
    declared_vars = homepage_infisical_vars()
    fake_values = fake_homepage_infisical_values()

    assert set(fake_values) == set(declared_vars)
    assert fake_values["cloudflare_zone"] == "example.test"
    assert all(fake_values[var] == f"https://fixture.example.test/{var}" for var in declared_vars if var != "cloudflare_zone")


def test_services_template_renders_as_valid_yaml_with_declared_infisical_values():
    assert isinstance(render_services(), list)


def test_services_template_rejects_undeclared_infisical_references():
    source = f"{TEMPLATE_PATH.read_text()}\n# {{{{ secrets.undeclared_fixture_secret }}}}\n"

    with pytest.raises(UndefinedError, match="undeclared_fixture_secret"):
        render_services(source=source)


def test_rendered_service_cards_have_valid_structure():
    rendered_services = render_services()
    seen_groups = set()

    assert isinstance(rendered_services, list)
    for group in rendered_services:
        assert isinstance(group, dict) and len(group) == 1
        group_name, cards = next(iter(group.items()))
        assert isinstance(group_name, str) and group_name.strip()
        assert group_name not in seen_groups
        seen_groups.add(group_name)
        assert isinstance(cards, list)

        for card in cards:
            assert isinstance(card, dict) and len(card) == 1
            card_name, body = next(iter(card.items()))
            assert isinstance(card_name, str) and card_name.strip()
            assert isinstance(body, dict)
            if "href" in body:
                assert isinstance(body["href"], str)
            if "widget" in body:
                widget = body["widget"]
                assert isinstance(widget, dict)
                if "type" in widget:
                    assert isinstance(widget["type"], str) and widget["type"].strip()
                if "url" in widget:
                    assert isinstance(widget["url"], str)


def test_service_groups_have_structurally_valid_layout_entries():
    assert_service_group_layouts_are_valid(services_by_group(), render_settings())


def test_layout_contract_allows_curated_groups_columns_and_incomplete_rows():
    groups = {"new-curated-group": [{"Only card": {}}]}
    settings = {"layout": {"new-curated-group": {"style": "row", "columns": 4}}}

    assert_service_group_layouts_are_valid(groups, settings)


def test_layout_contract_rejects_service_groups_without_layout_entries():
    with pytest.raises(AssertionError, match="missing-layout"):
        assert_service_group_layouts_are_valid({"missing-layout": []}, {"layout": {}})


def test_widget_http_urls_do_not_use_runtime_local_hostnames():
    for card_name, body in iter_service_cards(render_services()):
        widget_url = body.get("widget", {}).get("url")
        if isinstance(widget_url, str):
            try:
                assert_runtime_neutral_http_url(widget_url)
            except AssertionError as error:
                raise AssertionError(f"{card_name}: {error}") from error


@pytest.mark.parametrize(
    "url",
    [
        "https://sonarr.int.example.test:8443",
        "https://proxy.example.test/widget-endpoint",
        "http://192.0.2.10:1234",
        "http://[2001:db8::10]:1234",
    ],
)
def test_runtime_neutral_widget_url_accepts_fqdns_and_ip_addresses(url):
    assert_runtime_neutral_http_url(url)


@pytest.mark.parametrize("url", ["http://sonarr:8989", "http://runtime-service:8080"])
def test_runtime_neutral_widget_url_rejects_bare_runtime_hostnames(url):
    with pytest.raises(AssertionError, match="runtime-local hostname"):
        assert_runtime_neutral_http_url(url)
