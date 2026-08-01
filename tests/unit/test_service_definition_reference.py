"""Drift protection for the canonical service-definition reference."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

import yaml

ROOT = Path(__file__).resolve().parents[2]
REFERENCE_PATH = ROOT / "ansible/group_vars/all/services/README.md"
REFERENCE = REFERENCE_PATH.read_text()
COMMON_FILTER = ROOT / "ansible/roles/service_common/filter_plugins/service_common.py"

SUPPORTED_TOP_LEVEL_KEYS = {
    "application_prepare",
    "cap_add",
    "cap_drop",
    "cgroup",
    "cleanup",
    "command",
    "configs",
    "container_name",
    "copies",
    "depends_on",
    "deploy",
    "description",
    "devices",
    "enabled",
    "entrypoint",
    "env_file",
    "environment",
    "healthcheck",
    "hostname",
    "image",
    "infisical",
    "labels",
    "name",
    "named_networks",
    "named_volumes",
    "network_mode",
    "networks",
    "no_new_privileges",
    "paths",
    "paths_vault",
    "pid",
    "ports",
    "postgres",
    "prep",
    "read_only",
    "runtime",
    "secrets",
    "security_opt",
    "settings",
    "shm_size",
    "shm_tmpfs_size",
    "stack",
    "swarm_configs",
    "swarm_env_templates",
    "sysctls",
    "systemd",
    "tags",
    "targets",
    "templates",
    "tmpfs",
    "traefik",
    "user",
    "volumes",
}

NESTED_PATHS = {
    "environment.<NAME>.value_from.infisical",
    "environment.<NAME>.value_template",
    "infisical.secrets_map[].check_mode_value",
    "infisical.secrets_map[].secret.update_policy",
    "ports[].published",
    "ports[].target",
    "ports[].protocol",
    "ports[].host_ip",
    "ports[].mode",
    "named_networks.<key>.name",
    "named_networks.<key>.driver",
    "named_networks.<key>.external",
    "volumes[].type",
    "volumes[].source",
    "volumes[].target",
    "volumes[].read_only",
    "volumes[].tmpfs.size",
    "healthcheck.test",
    "healthcheck.interval",
    "healthcheck.timeout",
    "healthcheck.retries",
    "healthcheck.start_period",
    "traefik.backend_mode",
    "traefik.backend_host_inventory",
    "traefik.themepark.app",
    "traefik.themepark.theme",
    "postgres.enable",
    "postgres.databases",
    "postgres.user_var",
    "postgres.password_var",
    "postgres.host",
    "postgres.host_inventory",
    "deploy.type",
    "deploy.host",
    "deploy.mode",
    "deploy.replicas",
    "deploy.profile",
    "deploy.constraints",
    "deploy.restart_policy",
    "deploy.update_config",
    "deploy.rollback_config",
    "deploy.resources",
    "systemd.after",
    "systemd.restart",
    "systemd.restart_sec",
    "application_prepare.handler",
    "application_prepare.bootstrap.enabled",
    "prep.radarr.host",
    "prep.sonarr.host",
    "prep.postgres.host",
    "prep.sabnzbd.url",
    "paths_vault.vault_dir",
    "paths_vault.vault_token_file",
    "paths_vault.vault_pass_file",
    "paths_vault.vault_secret_name",
}

REMOVED_TABLE_OPTIONS = {
    "container",
    "device_cgroup_rules",
    "dns",
    "drift",
    "env",
    "expose",
    "extra_hosts",
    "group",
    "host_paths",
    "immutable",
    "network",
    "privileged",
    "pull_policy",
    "replace",
    "runtime_options",
    "themepark",
    "ulimits",
    "working_dir",
}


def load_module(path: Path, name: str) -> ModuleType:
    """Load a repository filter module without importing it as a package."""

    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def option_rows() -> dict[str, list[str]]:
    """Return canonical option-table rows keyed by documented path."""

    rows: dict[str, list[str]] = {}
    in_option_table = False
    for line in REFERENCE.splitlines():
        if line == "| Option | Type | Required | Default | Runtime | Owner | Description |":
            in_option_table = True
            continue
        if not in_option_table:
            continue
        if line.startswith("| ------"):
            continue
        if not line.startswith("| "):
            in_option_table = False
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        assert len(cells) == 7, line
        match = re.fullmatch(r"`([^`]+)`", cells[0])
        assert match, line
        rows[match.group(1)] = cells
    return rows


def example_services() -> list[dict[str, object]]:
    """Parse every YAML example in the dedicated Examples section."""

    examples = REFERENCE.split("## Examples", maxsplit=1)[1].split("## Removed and unsupported fields", maxsplit=1)[0]
    documents = re.findall(r"```yaml\n(.*?)```", examples, flags=re.DOTALL)
    assert len(documents) == 7
    return [yaml.safe_load(document) for document in documents]


def test_reference_has_all_major_sections_and_consistent_option_tables():
    headings = {
        "Schema fundamentals",
        "Defaults at a glance",
        "Identity and process",
        "Environment",
        "Infisical and native secrets",
        "Connectivity",
        "Filesystem and storage",
        "Devices and security",
        "Health checks",
        "Traefik",
        "PostgreSQL",
        "Deployment and placement",
        "Podman systemd",
        "Application preparation",
        "Actions and lifecycle",
        "Runtime compatibility",
        "Examples",
        "Removed and unsupported fields",
    }

    assert {f"## {heading}" for heading in headings} <= set(REFERENCE.splitlines())
    assert option_rows()


def test_reference_covers_every_supported_top_level_and_nested_option():
    rows = option_rows()

    assert rows.keys() >= SUPPORTED_TOP_LEVEL_KEYS
    assert rows.keys() >= NESTED_PATHS
    documented_top_level = {option for option in rows if not any(marker in option for marker in (".", "[", "<"))}
    assert documented_top_level == SUPPORTED_TOP_LEVEL_KEYS
    assert REMOVED_TABLE_OPTIONS.isdisjoint(rows)


def test_documented_defaults_match_common_filter_defaults():
    common = load_module(COMMON_FILTER, "service_common_reference_defaults")

    lookup = common.service_common_infisical_normalize(
        [
            {
                "var": "example_value",
                "path": "/Synthetic",
                "name": "EXAMPLE_VALUE",
                "secret": {"name": "example_secret"},
            }
        ]
    )
    declaration = lookup["secret_declarations"][0]
    postgres = common.service_common_postgres_normalize(
        {},
        "controller",
        {},
        {},
        False,
    )

    assert lookup["fail_on_empty"] is True
    assert declaration["target"] == "/run/secrets/example_secret"
    assert declaration["update_policy"] == "preserve"
    assert common.service_common_infisical_check_values(lookup) == {"example_value": "__CHECK_MODE_REDACTED_INFISICAL_example_value__"}
    assert postgres == {
        "enable": False,
        "databases": [],
        "port": 5432,
        "user_var": "postgres_user",
        "password_var": "postgres_pass",
        "host_inventory": "controller",
    }

    rows = option_rows()
    assert rows["infisical.fail_on_empty"][3] == "`true`"
    assert rows["infisical.secrets_map[].secret.target"][3] == ("`/run/secrets/<name>`")
    assert rows["infisical.secrets_map[].secret.update_policy"][3] == "`preserve`"
    assert rows["postgres.port"][3] == "`5432`"


def test_runtime_specific_options_are_labelled_correctly():
    rows = option_rows()

    assert rows["image"][4] == "Both"
    assert rows["environment"][4] == "Both"
    assert rows["stack"][4] == "Docker"
    assert rows["container_name"][4] == "Docker"
    assert rows["systemd"][4] == "Podman"
    assert rows["read_only"][4] == "Podman"
    assert rows["paths_vault"][4] == "Both"
    assert {row[2] for row in rows.values()} <= {"Yes", "No", "Conditional"}
    assert {row[4] for row in rows.values()} <= {"Both", "Docker", "Podman", "N/A"}


def test_examples_use_only_supported_keys_and_synthetic_values():
    forbidden_secret_markers = (
        "AKIA",
        "BEGIN PRIVATE KEY",
        "ghp_",
        "glpat-",
        "sk-",
    )

    for document in example_services():
        assert isinstance(document, dict)
        assert len(document) == 1
        service = next(iter(document.values()))
        assert isinstance(service, dict)
        assert set(service) <= SUPPORTED_TOP_LEVEL_KEYS

        image = service["image"]
        assert isinstance(image, str)
        assert ":" in image.rsplit("/", maxsplit=1)[-1]
        assert not image.endswith(":latest")

        targets = service.get("targets", {})
        assert isinstance(targets, dict)
        for target in targets.values():
            assert isinstance(target, dict)
            assert set(target) <= SUPPORTED_TOP_LEVEL_KEYS
            assert "targets" not in target

        rendered = yaml.safe_dump(document)
        assert not any(marker in rendered for marker in forbidden_secret_markers)
        assert not re.search(r"(?im)^\s*(password|token|value):\s+\S", rendered)


def test_related_human_docs_link_to_the_canonical_reference():
    related = (
        ROOT / "docs/service-definition-style.md",
        ROOT / "docs/service-runtime-refactor.md",
        ROOT / "docs/podman-services.md",
    )

    for path in related:
        assert "../ansible/group_vars/all/services/README.md" in path.read_text()
