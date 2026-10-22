"""Exercise configured selectors/extraction with JavaScript, without running Renovate.

This checks the exact-string and RE2-compatible regex subset used by these rules;
it does not resolve presets, look up releases, or simulate Renovate's PR lifecycle.
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
        "docker.io/library/adminer",
        "docker.io/grafana/grafana-extra",
        "ghcr.io/grafana/grafana",
        "example.com/library/postgres",
        "dockerXio/grafana/alloy",
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
            for target in base.get("targets", {}) or [None]:
                effective = catalog.service_catalog_merge_target(base, target)
                key = f"effective/{name}/{target}"
                effective_images[key] = effective["image"]
                sources[key] = f"image: '{effective['image']}'"
    bootstrap_images = {}
    for role in ("netbox", "infisical"):
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
const manager = config.customManagers.find(m => m.datasourceTemplate === 'docker');
const result = Object.fromEntries(Object.entries(sources).map(([key, text]) => [key,
    manager.matchStrings.flatMap(pattern => Array.from(text.matchAll(new RegExp(pattern, 'g')), match => ({
        ...match.groups,
        ...Object.fromEntries(Object.entries(selectors).map(([rule, value]) =>
            [rule, matches(match.groups.depName, value.matchPackageNames)]))
    })))
]));
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
        assert all(dep["critical"] and not dep["batch"] for dep in dependencies)
