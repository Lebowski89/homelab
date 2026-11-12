"""Offline controller glue boundaries; vm.py retains lifecycle ownership."""

import importlib.util
import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("forgejo_controller", ROOT / "scripts/testing/forgejo.py")
CONTROLLER = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CONTROLLER)


def config(tmp_path):
    return {
        "data_dir": str(tmp_path),
        "python": "/synthetic/venv/bin/python",
        "collections": "/synthetic/collections",
        "allocation": str(tmp_path / "allocation.json"),
        "provisioning": str(tmp_path / "provisioning.json"),
        "tofurc": "/synthetic/tofurc",
        "ssh_agent": "/synthetic/node-agent.sock",
    }


def test_provisioning_credentials_are_loaded_only_for_harness_execution(tmp_path, monkeypatch):
    settings = config(tmp_path)
    secret = Path(settings["provisioning"])
    secret.write_text(json.dumps({"PROXMOX_VE_API_TOKEN": "synthetic-provisioner-only"}))
    secret.chmod(0o600)
    monkeypatch.setenv("PROXMOX_VE_API_TOKEN", "inherited-must-not-escape")
    monkeypatch.setenv("SSH_AUTH_SOCK", "/workstation/agent")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "inherited-must-not-escape")
    public = CONTROLLER.public_environment(settings)
    assert not any(key.startswith(("PROXMOX", "SSH_", "ANSIBLE_", "TF_")) for key in public)
    assert "GIT_CONFIG_COUNT" not in public
    provisioner = CONTROLLER.provisioning_environment(settings)
    assert provisioner["PROXMOX_VE_API_TOKEN"] == "synthetic-provisioner-only"
    assert provisioner["SSH_AUTH_SOCK"] == settings["ssh_agent"]
    # A misplaced API token of a different purpose cannot be silently loaded.
    secret.write_text(json.dumps({"CI_API_TOKEN": "synthetic-wrong-purpose"}))
    with pytest.raises(ValueError, match="only a non-empty dedicated API token"):
        CONTROLLER.provisioning_environment(settings)
    secret.chmod(0o644)
    with pytest.raises(ValueError, match="mode 0600"):
        CONTROLLER.read_private(secret)
    secret.unlink()
    secret.symlink_to(tmp_path / "foreign")
    with pytest.raises(ValueError, match="owned regular file"):
        # A dangling symlink is rejected too, without following it.
        CONTROLLER.read_private(secret)


def test_workflow_is_manual_and_passes_fixed_choices_as_arguments():
    workflow = yaml.safe_load((ROOT / ".forgejo/workflows/molecule.yml").read_text())
    # PyYAML's YAML 1.1 parser treats the unquoted workflow key 'on' as True.
    trigger = workflow.get("on", workflow.get(True))
    assert set(trigger) == {"workflow_dispatch"}
    inputs = trigger["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"suite", "os"} and all(item["type"] == "choice" for item in inputs.values())
    assert inputs["suite"]["default"] == "rocky_node_exporter" and inputs["os"]["default"] == "rocky102"
    assert set(inputs["os"]["options"]) == {"all", *json.loads((ROOT / "molecule/vm/images.json").read_text())}
    assert workflow["concurrency"]["cancel-in-progress"] is False
    job = workflow["jobs"]["acceptance"]
    assert all(part in job["if"] for part in ("homelab-ci/homelab-ci", "refs/heads/main", "workflow_dispatch"))
    step = job["steps"][0]
    assert "${{" not in step["run"] and '--suite "$VM_SUITE" --os "$VM_OS"' in step["run"]
    assert "always()" not in (ROOT / ".forgejo/workflows/molecule.yml").read_text()


@pytest.mark.integration
def test_exact_main_checkout_is_retained_and_recovery_rejects_modified_source(tmp_path, monkeypatch):
    settings = config(tmp_path)
    monkeypatch.setattr(CONTROLLER, "SOURCE", str(ROOT))
    checkout = tmp_path / "checkouts" / ("a" * 32)
    checkout.parent.mkdir()
    sha = CONTROLLER.checkout_main(checkout, CONTROLLER.public_environment(settings))
    record = {"checkout": str(checkout), "sha": sha}
    assert CONTROLLER.source_checkout(record, settings) == checkout
    (checkout / "scripts/testing/suite.py").write_text("raise RuntimeError('modified fixture')\n")
    with pytest.raises(ValueError, match="source checkout changed"):
        CONTROLLER.source_checkout(record, settings)
    record["checkout"] = str(tmp_path / "outside")
    with pytest.raises(ValueError, match="original persistent controller directory"):
        CONTROLLER.source_checkout(record, settings)


def test_maintenance_marker_prevents_a_job_before_any_subprocess_or_secret_read(tmp_path, monkeypatch):
    drain = tmp_path / "draining"
    drain.touch()
    monkeypatch.setattr(CONTROLLER, "DRAIN", drain)
    with pytest.raises(ValueError, match="draining"):
        CONTROLLER.run(config(tmp_path), "rocky_node_exporter", "rocky102")
