"""Exercise configured selectors/extraction with JavaScript, without running Renovate.

This checks the exact-string and RE2-compatible regex subset, datasource/update
type selectors and scalar settings used by these rules. It does not resolve
presets, look up releases, calculate release age or simulate Renovate's PR lifecycle.
"""

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
CRITICAL_HUB_IMAGES = (
    "postgres",
    "traefik",
    "haproxy",
    "valkey/valkey",
    "authelia/authelia",
    "infisical/infisical",
    "prom/prometheus",
    "prom/alertmanager",
    "grafana/grafana",
    "grafana/loki",
    "grafana/alloy",
)
CRITICAL_OTHER_IMAGES = ("lscr.io/linuxserver/netbox", "lscr.io/linuxserver/plex")
UPDATE_TYPES = ("minor", "patch", "digest")
TIMESTAMP_OPTIONAL_REGISTRIES = ("ghcr.io", "lscr.io", "codeberg.org")


def hub_aliases(name):
    aliases = [name, f"docker.io/{name}"]
    if "/" not in name:
        aliases += [f"library/{name}", f"docker.io/library/{name}"]
    return aliases


def test_batch_exclusions_mirror_the_critical_image_identities():
    rules = json.loads((ROOT / "renovate.json").read_text())["packageRules"]
    batch = next(rule for rule in rules if rule.get("groupSlug") == "weekly-docker-minor-patch")
    critical = next(rule for rule in rules if "critical" in rule.get("addLabels", []))
    assert batch["matchPackageNames"] == [f"!{pattern}" for pattern in critical["matchPackageNames"]]


@pytest.fixture(scope="module")
def image_checks():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is unavailable; JavaScript selector/extraction checks cannot run")
    config = json.loads((ROOT / "renovate.json").read_text())
    rules = config["packageRules"]
    selectors = {
        "batch": next(rule for rule in rules if rule.get("groupSlug") == "weekly-docker-minor-patch"),
        "critical": next(rule for rule in rules if "critical" in rule.get("addLabels", [])),
        "traefik": next(rule for rule in rules if "branchTopic" in rule and "traefik" in rule.get("addLabels", [])),
    }
    names = [alias for name in CRITICAL_HUB_IMAGES for alias in hub_aliases(name)]
    names += list(CRITICAL_OTHER_IMAGES)
    names += [
        "ghcr.io/autobrr/qui",
        "adminer",
        "library/adminer",
        "docker.io/adminer",
        "docker.io/library/adminer",
        "docker.io/grafana/grafana-extra",
        "ghcr.io/grafana/grafana",
        "example.com/library/postgres",
        "dockerXio/grafana/alloy",
        "quay.io/example/app",
    ]
    for registry in TIMESTAMP_OPTIONAL_REGISTRIES:
        names += [
            f"{registry}/example/app",
            f"{registry}.example.com/example/app",
            f"other-{registry}/example/app",
            f"example.com/{registry}/app",
            f"{registry.replace('.', 'X')}/example/app",
        ]
    sources = {
        f"alias/{name}/{digest}": f"image: '{name}:1.2.3{('@sha256:' + 'a' * 64) if digest else ''}'"
        for name in names
        for digest in (False, True)
    }
    spec = importlib.util.spec_from_file_location("renovate_service_catalog", ROOT / "ansible/filter_plugins/service_catalog.py")
    catalog = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(catalog)
    effective_images = {}
    for path in sorted((ROOT / "ansible/group_vars/all/services").glob("*.yml")):
        text = path.read_text()
        for name, base in yaml.safe_load(text).items():
            sources[f"file/{name}"] = text
            if name in ("autobrr", "seerr"):
                tag, _ = base["image"].split("@", 1)
                sources[f"digest-update/{name}"] = f"image: '{tag}@sha256:{'b' * 64}'"
            for target in base.get("targets", {}) or [None]:
                effective = catalog.service_catalog_merge_target(base, target)
                key = f"effective/{name}/{target}"
                effective_images[key] = effective["image"]
                sources[key] = f"image: '{effective['image']}'"
    bootstrap_images = {}
    for role in ("netbox", "infisical", "hugo"):
        text = (ROOT / f"ansible/roles/{role}/defaults/main.yml").read_text()
        sources[f"bootstrap/{role}"] = text
        bootstrap_images[role] = [value for key, value in yaml.safe_load(text).items() if key.endswith("_image")]
    result = subprocess.run(
        [
            node,
            "-e",
            r"""
const { config, selectors, sources } = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
// Only the literal and regex selectors used here: not a replacement Renovate engine.
function matches(name, patterns) {
    const positive = patterns.filter(p => !p.startsWith('!'));
    const negative = patterns.filter(p => p.startsWith('!')).map(p => p.slice(1));
    const match = p => {
        if (p.startsWith('/') && p.endsWith('/')) return new RegExp(p.slice(1, -1)).test(name);
        if (/[*?{}[\]]/.test(p)) throw new Error('Unsupported glob in focused selector check: ' + p);
        return p.toLowerCase() === name.toLowerCase();
    };
    return (!positive.length || positive.some(match)) && !negative.some(match);
}
// Check only selectors and scalar fields used by datasource rules in this config.
// Defaults follow Renovate's documented timestamp-required behaviour; no presets
// or datasource defaults are loaded by this focused check.
function settings(depName, datasource, updateType) {
    const result = {
        minimumReleaseAge: config.minimumReleaseAge,
        minimumReleaseAgeBehaviour: config.minimumReleaseAgeBehaviour ?? 'timestamp-required'
    };
    for (const rule of config.packageRules) {
        if (!rule.matchDatasources?.includes(datasource)) continue;
        if (rule.matchPackageNames && !matches(depName, rule.matchPackageNames)) continue;
        if (rule.matchUpdateTypes && !rule.matchUpdateTypes.includes(updateType)) continue;
        for (const key of ['groupName', 'groupSlug', 'minimumReleaseAge', 'minimumReleaseAgeBehaviour',
                           'dependencyDashboardApproval', 'automerge']) {
            if (Object.hasOwn(rule, key)) result[key] = rule[key];
        }
    }
    return result;
}
const manager = config.customManagers.find(m => m.datasourceTemplate === 'docker');
const result = Object.fromEntries(Object.entries(sources).map(([key, text]) => [key,
    manager.matchStrings.flatMap(pattern => Array.from(text.matchAll(new RegExp(pattern, 'g')), match => ({
        ...match.groups,
        updates: Object.fromEntries(['minor', 'patch', 'digest', 'major'].map(type =>
            [type, settings(match.groups.depName, 'docker', type)])),
        ...Object.fromEntries(Object.entries(selectors).map(([rule, value]) =>
            [rule, matches(match.groups.depName, value.matchPackageNames)]))
    })))
]));
result.nonContainer = ['pypi', 'github-tags', 'terraform-provider'].flatMap(datasource =>
    ['ghcr.io/example/app', 'lscr.io/example/app', 'codeberg.org/example/app'].map(name =>
        settings(name, datasource, 'minor')));
process.stdout.write(JSON.stringify(result));
""",
        ],
        input=json.dumps({"config": config, "selectors": selectors, "sources": sources}),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout), effective_images, bootstrap_images


@pytest.mark.parametrize("name", CRITICAL_HUB_IMAGES + CRITICAL_OTHER_IMAGES)
def test_critical_aliases_are_excluded_from_batch_and_selected_separately(image_checks, name):
    results, _, _ = image_checks
    for alias in hub_aliases(name) if name in CRITICAL_HUB_IMAGES else [name]:
        for digest in (False, True):
            [dep] = results[f"alias/{alias}/{digest}"]
            assert dep["depName"] == alias
            assert dep["currentValue"] == "1.2.3"
            assert dep.get("currentDigest") == (f"sha256:{'a' * 64}" if digest else None)
            assert not dep["batch"], alias
            assert dep["critical"], alias
            assert dep["traefik"] == (name == "traefik"), alias
            for update_type in UPDATE_TYPES:
                assert dep["updates"][update_type].get("groupName") is None, (alias, update_type)
                assert "groupSlug" not in dep["updates"][update_type], (alias, update_type)


def test_noncritical_images_and_unrelated_registries_remain_in_batch(image_checks):
    results, _, _ = image_checks
    for key, dependencies in results.items():
        if not key.startswith("alias/"):
            continue
        [dep] = dependencies
        if dep["depName"] in {alias for name in CRITICAL_HUB_IMAGES for alias in hub_aliases(name)} | set(CRITICAL_OTHER_IMAGES):
            continue
        assert dep["batch"], key
        assert not dep["critical"], key
        assert not dep["traefik"], key
        for update_type in UPDATE_TYPES:
            assert dep["updates"][update_type]["groupSlug"] == "weekly-docker-minor-patch", (key, update_type)


def test_real_effective_targets_and_bootstrap_images_are_extracted_and_classified(image_checks):
    results, effective_images, bootstrap_images = image_checks
    critical = set(CRITICAL_HUB_IMAGES + CRITICAL_OTHER_IMAGES)
    for key, reference in effective_images.items():
        [dep] = results[key]
        name, tag = reference.split("@", 1)[0].rsplit(":", 1)
        assert (dep["depName"], dep["currentValue"]) == (name, tag), key
        assert dep.get("currentDigest") == (reference.split("@", 1)[1] if "@" in reference else None), key
        canonical = name.removeprefix("docker.io/").removeprefix("library/")
        assert dep["critical"] == (canonical in critical), key
        assert dep["batch"] == (canonical not in critical), key
        # The effective image must also be found in the original YAML, including target overrides.
        assert any(item["depName"] == name and item["currentValue"] == tag for item in results[f"file/{key.split('/')[1]}"])
    for role, references in bootstrap_images.items():
        dependencies = results[f"bootstrap/{role}"]
        assert {dep["depName"] for dep in dependencies} == {ref.rsplit(":", 1)[0] for ref in references}
        for dep in dependencies:
            canonical = dep["depName"].removeprefix("docker.io/").removeprefix("library/")
            assert dep["critical"] == (canonical in critical), role
            assert dep["batch"] == (canonical not in critical), role


@pytest.mark.parametrize("service", ("autobrr", "seerr"))
def test_real_same_tag_digest_changes_join_nightly_batch(image_checks, service):
    results, _, _ = image_checks
    [current] = results[f"file/{service}"]
    [updated] = results[f"digest-update/{service}"]
    assert current["depName"] == updated["depName"]
    assert current["currentValue"] == updated["currentValue"]
    assert current["currentDigest"] != updated["currentDigest"]
    assert updated["updates"]["digest"]["groupSlug"] == "weekly-docker-minor-patch"


def test_container_major_approval_and_disabled_automerge_remain_intact(image_checks):
    results, _, _ = image_checks
    for key, dependencies in results.items():
        if key == "nonContainer":
            continue
        for dep in dependencies:
            major = dep["updates"]["major"]
            assert major["dependencyDashboardApproval"] is True, key
            assert major.get("groupName") is None, key
            assert "groupSlug" not in major, key
            assert all(settings["automerge"] is False for settings in dep["updates"].values()), key


def test_timestamp_exceptions_cover_only_the_intended_image_registries(image_checks):
    results, _, _ = image_checks
    for key, dependencies in results.items():
        if key == "nonContainer":
            continue
        for dep in dependencies:
            registry = dep["depName"].split("/", 1)[0]
            expected = "timestamp-optional" if registry in TIMESTAMP_OPTIONAL_REGISTRIES else "timestamp-required"
            for settings in dep["updates"].values():
                assert settings["minimumReleaseAgeBehaviour"] == expected, key
                assert settings["minimumReleaseAge"] == "3 days", key
    for settings in results["nonContainer"]:
        assert settings["minimumReleaseAgeBehaviour"] == "timestamp-required"
        assert settings["minimumReleaseAge"] == "3 days"
