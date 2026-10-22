"""Exercise private offline migration scaffolding and integrity boundaries."""

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("migration_workspace", ROOT / "migrator/migrate.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


@pytest.fixture
def repository(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    services = root / "ansible/group_vars/all/services"
    services.mkdir(parents=True)
    (services / "README.md").write_text("Non-YAML reference alongside service definitions\n")
    definition = {
        "example": {
            "runtime": "docker",
            "image": "registry.example.invalid/nonproduction:1@sha256:" + "a" * 64,
            "environment": {"PASSWORD": "NONPRODUCTION-MUST-NOT-BE-COPIED"},
            "operational_requirements": {"acl": ["worker_backends"]},
            "targets": {
                "worker": {"name": "example-worker", "deploy": {"host": "{{ services_storage_host }}"}},
                "mgt": {
                    "runtime": "podman",
                    "name": "example-mgt",
                    "operational_requirements": {"ownership_transition": True},
                    "deploy": {
                        "execution": {
                            "mode": "rootless",
                            "host_user": "podman-example",
                            "unsupported_environment": {"PASSWORD": "NONPRODUCTION-MUST-NOT-BE-COPIED"},
                        }
                    },
                },
            },
        }
    }
    (services / "example.yml").write_text(yaml.safe_dump(definition))
    for source in ["migrator/migrate.py", "ansible/operator/utility-preparation.py"]:
        p = root / source
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# NONPRODUCTION source fixture\n")
    monkeypatch.setattr(M, "REPO", root)
    monkeypatch.setattr(M.TOOLS, "command", lambda *a, **k: pytest.fail("offline tool attempted a runtime operation"))
    evidence = tmp_path / "private"
    evidence.mkdir(mode=0o700)
    return root, evidence


def completed_batch(repository):
    _, evidence = repository
    directory = M.initialize(evidence, "fixture", ["example:mgt"])
    (directory / "PLAN.md").write_text("Reviewed NONPRODUCTION plan fixture\n")
    (directory / "recipes/cutover.sh").write_text("#!/bin/bash\nexit 0\n")
    return directory


def test_exact_target_merge_privacy_and_no_overwrite(repository):
    _, evidence = repository
    first = M.initialize(evidence, "fixture", ["example:mgt"])
    second = M.initialize(evidence, "fixture", ["example:worker"], "rootful")
    assert first != second
    snapshot = json.loads((first / "catalogue.json").read_text())
    service = snapshot["services"][0]
    assert service["canonical_runtime"] == "podman"
    assert service["name"] == "example-mgt"
    assert service["operational_requirements"] == {"acl": ["worker_backends"], "ownership_transition": True}
    assert "not collected" in service["observed_runtime"]
    assert json.loads((second / "catalogue.json").read_text())["proposed_execution_mode"] == "rootful"
    for path in [first, *first.rglob("*")]:
        assert stat.S_IMODE(path.stat().st_mode) == (0o700 if path.is_dir() else 0o600)
        if path.is_file():
            assert "NONPRODUCTION-MUST-NOT-BE-COPIED" not in path.read_text()


@pytest.mark.parametrize("selector", ["example", "example:missing", "../example", "example:mgt:extra", "missing"])
def test_ambiguous_or_invalid_selection_fails_before_creating_workspace(repository, selector):
    _, evidence = repository
    with pytest.raises(ValueError):
        M.initialize(evidence, "fixture", [selector])
    assert list(evidence.iterdir()) == []


@pytest.mark.integration
def test_drafts_fail_closed_and_cannot_be_sealed(repository):
    _, evidence = repository
    directory = M.initialize(evidence, "fixture", ["example:mgt"])
    result = subprocess.run(["/bin/bash", str(directory / "recipes/cutover.sh")], capture_output=True, text=True)
    assert result.returncode == 64
    with pytest.raises(ValueError, match="TODO"):
        M.seal(directory, ["recipes/cutover.sh"])


@pytest.mark.parametrize("changed", ["plan", "recipe", "source", "hash"])
def test_seal_verify_and_tamper_rejection(repository, changed):
    root, _ = repository
    directory = completed_batch(repository)
    manifest, checksum = M.seal(directory, ["recipes/cutover.sh"])
    M.verify(directory, manifest.name, checksum)
    assert M.seal(directory, ["recipes/cutover.sh"])[0] != manifest
    if changed == "hash":
        checksum = "0" * 64
    else:
        target = {"plan": directory / "PLAN.md", "recipe": directory / "recipes/cutover.sh", "source": root / "migrator/migrate.py"}[
            changed
        ]
        target.write_text(target.read_text() + "changed\n")
    with pytest.raises(ValueError, match="changed|differs"):
        M.verify(directory, manifest.name, checksum)


def test_changed_catalogue_symlink_and_escape_rejected(repository):
    root, _ = repository
    directory = completed_batch(repository)
    (directory / "recipes/link.sh").symlink_to(directory / "recipes/cutover.sh")
    with pytest.raises(ValueError, match="symlink"):
        M.seal(directory, ["recipes/link.sh"])
    with pytest.raises(ValueError):
        M.seal(directory, ["recipes/../../outside.sh"])
    declaration = root / "ansible/group_vars/all/services/example.yml"
    declaration.write_text(declaration.read_text() + "# changed\n")
    with pytest.raises(ValueError, match="canonical source changed"):
        M.seal(directory, ["recipes/cutover.sh"])


def test_nonprivate_evidence_root_rejected(repository):
    _, evidence = repository
    evidence.chmod(0o755)
    with pytest.raises(ValueError, match="0700"):
        M.initialize(evidence, "fixture", ["example:mgt"])
    assert list(evidence.iterdir()) == []


@pytest.mark.integration
def test_real_catalogue_cli_init_is_offline_and_target_scoped(tmp_path):
    tmp_path.chmod(0o700)
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "migrator/migrate.py"),
            "init",
            "--name",
            "offline",
            "--service",
            "haproxy:workers",
            "--evidence-root",
            str(tmp_path),
        ],
        text=True,
        capture_output=True,
        env={**os.environ, "PATH": "/nonexistent"},
    )
    assert result.returncode == 0, result.stderr
    directory = next(tmp_path.glob("offline.*"))
    snapshot = json.loads((directory / "catalogue.json").read_text())
    assert [item["selector"] for item in snapshot["services"]] == ["haproxy:workers"]
    assert snapshot["services"][0]["canonical_runtime"] == "docker"
    assert "inventory_host_expression" in snapshot["services"][0]
    (directory / "PLAN.md").write_text("NONPRODUCTION integrity-only smoke; no execution approval\n")
    (directory / "recipes/cutover.sh").write_text("#!/bin/bash\nexit 64\n")
    prefix = [sys.executable, str(ROOT / "migrator/migrate.py")]
    sealed = subprocess.run(
        [*prefix, "seal", str(directory), "--recipe", "recipes/cutover.sh"],
        text=True,
        capture_output=True,
        env={**os.environ, "PATH": "/nonexistent"},
    )
    assert sealed.returncode == 0, sealed.stderr
    manifest = next(directory.glob("manifest-*.json"))
    checked = subprocess.run(
        [*prefix, "verify", str(directory), "--manifest", manifest.name, "--sha256", hashlib.sha256(manifest.read_bytes()).hexdigest()],
        text=True,
        capture_output=True,
        env={**os.environ, "PATH": "/nonexistent"},
    )
    assert checked.returncode == 0, checked.stderr


def test_malformed_yaml_is_rejected_without_source_values(repository):
    root, evidence = repository
    file = root / "ansible/group_vars/all/services/example.yml"
    file.write_text("example: [NONPRODUCTION-WITHHELD,\n")
    with pytest.raises(ValueError, match="example.yml") as error:
        M.initialize(evidence, "fixture", ["example:mgt"])
    assert "NONPRODUCTION-WITHHELD" not in str(error.value)
    assert list(evidence.iterdir()) == []


def test_snapshot_edits_do_not_drop_canonical_integrity_checks(repository):
    directory = completed_batch(repository)
    path = directory / "catalogue.json"
    snapshot = json.loads(path.read_text())
    snapshot["services"][0]["image"] = "registry.example.invalid/other:1"
    path.write_text(json.dumps(snapshot))
    with pytest.raises(ValueError, match="snapshot differs"):
        M.seal(directory, ["recipes/cutover.sh"])
