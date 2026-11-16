"""Controller ownership/environment failures; these are not guest acceptance."""

import errno
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("molecule_vm", ROOT / "scripts/testing/vm.py")
VM = importlib.util.module_from_spec(spec)
spec.loader.exec_module(VM)


@pytest.mark.parametrize("existing", [False, True])
def test_host_pins_label_new_and_retained_files_without_changing_trust(tmp_path, monkeypatch, existing):
    directory = tmp_path / "run"
    directory.mkdir(mode=0o700)
    pin = directory / "known_hosts"
    expected = "192.0.2.44 ssh-ed25519 c3ludGhldGlj\n"
    if existing:
        pin.write_text(expected)
        pin.chmod(0o600)
    context = [b"user_u:object_r:user_home_t:s0:c7\0"]
    changes = []

    def get_context(fd, name):
        assert isinstance(fd, int) and name == "security.selinux"
        return context[0]

    def set_context(fd, name, value):
        assert isinstance(fd, int) and name == "security.selinux"
        changes.append(os.fstat(fd).st_ino)
        context[0] = value

    monkeypatch.setattr(VM.os, "getxattr", get_context)
    monkeypatch.setattr(VM.os, "setxattr", set_context)
    original = pin.stat() if existing else None
    VM.write_host_pins(directory, expected)
    after = pin.stat()
    assert pin.read_text() == expected and after.st_mode & 0o777 == 0o600 and after.st_uid == os.getuid()
    assert context[0] == b"user_u:object_r:ssh_home_t:s0:c7\0"
    if original:
        assert (after.st_ino, after.st_uid, after.st_gid, after.st_mode) == (
            original.st_ino,
            original.st_uid,
            original.st_gid,
            original.st_mode,
        )
    VM.write_host_pins(directory, expected)
    assert changes == [after.st_ino]


@pytest.mark.parametrize("foreign", ["pin_link", "parent_link", "hard_link", "mode", "contents"])
def test_host_pins_reject_unsafe_paths_or_changed_trust_before_labeling(tmp_path, monkeypatch, foreign):
    directory = tmp_path / "run"
    directory.mkdir(mode=0o700)
    expected = "192.0.2.44 ssh-ed25519 c3ludGhldGlj\n"
    other = tmp_path / "other"
    other.write_text(expected)
    other.chmod(0o600)
    pin = directory / "known_hosts"
    if foreign == "parent_link":
        alias = tmp_path / "alias"
        alias.symlink_to(directory, target_is_directory=True)
        directory = alias
    elif foreign == "pin_link":
        pin.symlink_to(other)
    elif foreign == "hard_link":
        os.link(other, pin)
    else:
        pin.write_text("different synthetic pin\n" if foreign == "contents" else expected)
        pin.chmod(0o644 if foreign == "mode" else 0o600)
    monkeypatch.setattr(VM.os, "setxattr", lambda *args: pytest.fail("Unsafe pins must not be relabeled"))
    with pytest.raises((OSError, ValueError)):
        VM.write_host_pins(directory, expected)
    assert other.read_text() == expected and other.stat().st_mode & 0o777 == 0o600
    if foreign == "contents":
        assert pin.read_text() == "different synthetic pin\n"


@pytest.mark.parametrize("failure", [errno.ENODATA, errno.ENOTSUP, errno.EACCES])
def test_host_pins_skip_only_absent_filesystem_labels(tmp_path, monkeypatch, failure):
    expected = "192.0.2.44 ssh-ed25519 c3ludGhldGlj\n"

    def absent(*args):
        raise OSError(failure, "synthetic xattr result")

    monkeypatch.setattr(VM.os, "getxattr", absent)
    monkeypatch.setattr(VM.os, "setxattr", lambda *args: pytest.fail("No label was available"))
    if failure == errno.EACCES:
        with pytest.raises(OSError):
            VM.write_host_pins(tmp_path, expected)
    else:
        VM.write_host_pins(tmp_path, expected)
    pin = tmp_path / "known_hosts"
    assert pin.read_text() == expected and pin.stat().st_mode & 0o777 == 0o600


def test_host_pin_label_failure_preserves_private_file_and_is_not_ignored(tmp_path, monkeypatch):
    expected = "192.0.2.44 ssh-ed25519 c3ludGhldGlj\n"
    monkeypatch.setattr(VM.os, "getxattr", lambda *args: b"user_u:object_r:user_home_t:s0")

    def denied(*args):
        raise PermissionError("synthetic relabel denial")

    monkeypatch.setattr(VM.os, "setxattr", denied)
    with pytest.raises(PermissionError):
        VM.write_host_pins(tmp_path, expected)
    assert (tmp_path / "known_hosts").read_text() == expected
    assert (tmp_path / "known_hosts").stat().st_mode & 0o777 == 0o600


def test_host_pin_replacement_cannot_relabel_the_replacement(tmp_path, monkeypatch):
    expected = "192.0.2.44 ssh-ed25519 c3ludGhldGlj\n"
    pin = tmp_path / "known_hosts"
    replacement = tmp_path / "replacement"
    replacement.write_text("foreign data\n")
    replacement.chmod(0o600)
    context = [b"user_u:object_r:user_home_t:s0"]
    monkeypatch.setattr(VM.os, "getxattr", lambda *args: context[0])

    def replace(fd, name, value):
        original_inode = os.fstat(fd).st_ino
        replacement.replace(pin)
        assert pin.stat().st_ino != original_inode
        context[0] = value

    monkeypatch.setattr(VM.os, "setxattr", replace)
    with pytest.raises(ValueError, match="metadata changed during preparation"):
        VM.write_host_pins(tmp_path, expected)
    assert pin.read_text() == "foreign data\n"


@pytest.mark.integration
def test_fifo_host_pin_is_rejected_without_waiting_for_a_writer(tmp_path):
    os.mkfifo(tmp_path / "known_hosts", mode=0o600)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import runpy,sys; from pathlib import Path; "
            "vm=runpy.run_path(sys.argv[1]); "
            "vm['write_host_pins'](Path(sys.argv[2]), 'synthetic pin\\n')",
            str(ROOT / "scripts/testing/vm.py"),
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode != 0
    assert "Host pins must be an owned regular mode-0600 file" in result.stderr
    assert (tmp_path / "known_hosts").is_fifo()


@pytest.mark.integration
@pytest.mark.parametrize(
    "family,option,value,key",
    [
        ("application_lifecycle", "--runtime", "swarm", "runtime"),
        ("runtime_install", "--order", "podman-first", "order"),
    ],
)
def test_individual_variant_selection_needs_no_allocation_or_providers(family, option, value, key):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/testing/suite.py"), "--suite", family, "--os", "rocky102", option, value],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    cases = json.loads(result.stdout)
    assert len(cases) == 1
    assert cases[0]["suite"] == family and cases[0][key] == value


@pytest.mark.integration
@pytest.mark.parametrize("retain_controller_group", [True, False])
def test_pasta_prerequisite_targets_the_disposable_controller_through_real_operations(prepared, retain_controller_group):
    """List real operation hosts; services.yml otherwise overrides inventory defaults."""
    import yaml

    directory, manifest = prepared
    VM.write_json(directory / "inventory.yml", VM.inventory(manifest, directory))
    prerequisite = yaml.safe_load((ROOT / "molecule/runtime_install/ubuntu-pasta-prerequisite.tasks.yml").read_text())
    overrides = prerequisite[0]["vars"]["molecule_vm_overrides"].copy()
    if not retain_controller_group:
        overrides.pop("services_controller_inventory_group")
    result = subprocess.run(
        [
            str(Path(sys.executable).with_name("ansible-playbook")),
            "-i",
            str(directory / "inventory.yml"),
            str(ROOT / "ansible/operations.yml"),
            "--tags",
            prerequisite[0]["vars"]["molecule_vm_tags"],
            "--list-hosts",
            "-e",
            json.dumps(overrides),
        ],
        cwd=ROOT,
        env=VM.guest_environment(directory),
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    selected = result.stdout.split("Permit the observed Podman SIGTERM to its pasta network helper", 1)[1]
    assert ("hosts (1):" in selected and "subject" in selected) is retain_controller_group


@pytest.mark.integration
@pytest.mark.parametrize("distribution", ["Ubuntu", "Debian", "Fedora", "Rocky"])
def test_bootstrap_avoids_ubuntus_unnecessary_early_network_dependency(tmp_path, distribution):
    """Evaluate the actual HCL expression offline; live reboot proves the boot graph.

    Ubuntu cloud-init 26.1 waits before sysinit for any nonempty bootcmd, even
    an RPM-only no-op. Its native firewalld needs sysinit before network-pre.
    """
    import re
    import shutil

    tofu = shutil.which("tofu")
    if not tofu:
        pytest.skip("OpenTofu expression evaluator unavailable")
    source = (ROOT / "molecule/vm/proxmox/main.tf").read_text()
    expression = re.search(r"^\s*bootcmd\s*=\s*(.+)$", source, re.MULTILINE).group(1)
    (tmp_path / "main.tf").write_text(
        'variable "run" { type = object({ image = object({ distribution = string }) }) }\nlocals { bootcmd = ' + expression + " }\n"
    )
    result = subprocess.run(
        [tofu, "console", "-no-color", "-var", 'run={image={distribution="' + distribution + '"}}'],
        input="jsonencode(local.bootcmd)\n",
        cwd=tmp_path,
        env={key: value for key, value in os.environ.items() if not key.startswith(("TF_", "TOFU_"))},
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    commands = json.loads(json.loads(result.stdout))
    assert bool(commands) is (distribution != "Ubuntu")
    if commands:
        assert "update-ca-trust extract" in commands[0][-1]


def test_prepared_image_requires_matching_recipe_source_and_owned_bytes(tmp_path):
    run_id = "a" * 32
    directory = tmp_path / run_id
    directory.mkdir(mode=0o700)
    image = directory / "fedora44.qcow2"
    size = json.loads((ROOT / "molecule/vm/fedora-source.json").read_text())["disk_gb"] * 1024**3
    header = b"QFI\xfb" + (3).to_bytes(4, "big") + bytes(16) + size.to_bytes(8, "big")
    image.write_bytes(header + b"synthetic image body, not a guest acceptance test")
    provenance = {
        "builder_id": run_id,
        "source": json.loads((ROOT / "molecule/vm/fedora-source.json").read_text()),
        "recipe": VM.image_recipe(),
        "path": str(image),
        "checksum": hashlib.sha256(image.read_bytes()).hexdigest(),
        "virtual_size_bytes": size,
    }
    VM.write_json(tmp_path / "fedora-image.json", provenance)
    assert VM.prepared_fedora(tmp_path) == provenance
    provenance["virtual_size_bytes"] += 1024**3
    with pytest.raises(ValueError, match="virtual size"):
        VM.validate_prepared_image(provenance, tmp_path)
    provenance["virtual_size_bytes"] -= 1024**3
    original = image.read_bytes()
    image.write_bytes(header[:24] + (size * 2).to_bytes(8, "big") + original[32:])
    provenance["checksum"] = hashlib.sha256(image.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="header differs"):
        VM.validate_prepared_image(provenance, tmp_path)
    image.write_bytes(original)
    provenance["checksum"] = hashlib.sha256(original).hexdigest()
    image.write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum differs"):
        VM.prepared_fedora(tmp_path)
    image.unlink()
    image.symlink_to(tmp_path / "foreign-image")
    with pytest.raises(ValueError, match="owned artifact"):
        VM.prepared_fedora(tmp_path)
    provenance["recipe"] = "0" * 64
    with pytest.raises(ValueError, match="source or recipe changed"):
        VM.validate_prepared_image(provenance, tmp_path)


@pytest.mark.integration
def test_uploaded_image_retirement_cannot_select_a_foreign_artifact(prepared):
    _, manifest = prepared
    manifest["prepared_image"] = {"builder_id": "a" * 32}
    manifest["run"]["image_local_path"] = "/private/owned/fedora44.qcow2"
    value = {
        "content_type": "iso",
        "node_name": manifest["run"]["node"],
        "datastore_id": manifest["run"]["image_storage"],
        "id": manifest["run"]["image_storage"] + f":iso/molecule-{manifest['id']}.img",
        "source_file": [{"path": manifest["run"]["image_local_path"], "file_name": f"molecule-{manifest['id']}.img"}],
    }
    state = {"values": {"root_module": {"resources": [{"type": "proxmox_virtual_environment_file", "values": value}]}}}
    VM.check_state(state, manifest)
    value["source_file"][0]["path"] = "/private/production.qcow2"
    with pytest.raises(ValueError, match="Foreign uploaded image"):
        VM.check_state(state, manifest)


@pytest.mark.integration
def test_file_plan_refuses_adoption_and_world_readable_bootstrap(prepared):
    _, manifest = prepared
    name = f"molecule-{manifest['id']}-bootstrap.yaml"
    value = {
        "node_name": manifest["run"]["node"],
        "datastore_id": manifest["run"]["snippet_storage"],
        "source_raw": [{"file_name": name, "data": "private disposable host key"}],
        "overwrite": True,
        "file_mode": "0600",
    }
    state = {"values": {"root_module": {"resources": [{"type": "proxmox_virtual_environment_file", "values": value}]}}}
    with pytest.raises(ValueError, match="refuse adoption"):
        VM.check_state(state, manifest, planned=True)
    value["overwrite"] = False
    value["file_mode"] = "0644"
    with pytest.raises(ValueError, match="root-only"):
        VM.check_state(state, manifest, planned=True)
    value["file_mode"] = "0600"
    VM.check_state(state, manifest, planned=True)


@pytest.mark.integration
def test_image_retry_cannot_adopt_an_acceptance_guest(prepared):
    directory, manifest = prepared
    manifest["allocation"]["allow_image_preparation"] = True
    VM.write_json(directory / "builder-allocation.json", manifest["allocation"])
    (directory / "manifest.json").write_text(json.dumps(manifest))
    args = SimpleNamespace(
        allocation=directory / "builder-allocation.json", state_root=directory.parent, rebuild=False, resume_builder=directory
    )
    with pytest.raises(ValueError, match="Resume only the exact owned image builder"):
        VM.prepare_fedora_image(args)


def test_guest_module_requirements_use_repository_pins_without_secret_clients(tmp_path, monkeypatch):
    requirements = tmp_path / "ansible/requirements.txt"
    requirements.parent.mkdir()
    requirements.write_text("docker==7.0.0\njsondiff==2.0.0\npyyaml==6.0\nrequests==2.0\ninfisicalsdk==1.0\n")
    monkeypatch.setattr(VM, "ROOT", tmp_path)
    selected = VM.guest_requirements()
    assert "infisical" not in selected
    assert all(line in requirements.read_text().splitlines() for line in selected.splitlines())
    requirements.write_text(requirements.read_text().replace("docker==7.0.0", "docker"))
    with pytest.raises(ValueError, match="Missing pinned"):
        VM.guest_requirements()


@pytest.fixture
def prepared(tmp_path, request):
    config = json.loads((ROOT / "molecule/vm/allocation.json.sample").read_text())
    key = tmp_path / "test.pub"
    key.write_text("ssh-ed25519 AAAATEST fixture-public-key")
    config.update(approved_disposable=True, public_key_path=str(key), pool_id=getattr(request, "param", None))
    path = tmp_path / "allocation.json"
    path.write_text(json.dumps(config))
    args = SimpleNamespace(
        allocation=path, state_root=tmp_path / "runs", os="rocky102", suite="node_exporter", order="docker-first", runtime="rootless"
    )
    VM.prepare(args)
    directory = next(args.state_root.iterdir())
    return directory, VM.load_run(directory)


@pytest.mark.integration
def test_preparation_is_offline_and_unique_with_no_production_inventory(prepared, monkeypatch):
    directory, manifest = prepared
    # No provider cache/state is initialized by preparing a run.
    assert not (directory / "tofu/.terraform").exists()
    assert directory.stat().st_mode & 0o077 == 0
    inventory = VM.inventory(manifest, directory)
    hosts = inventory["all"]["children"]["molecule_guests"]["hosts"]
    assert set(hosts) == {"subject"}
    assert hosts["subject"]["ansible_python_interpreter"] == VM.GUEST_PYTHON
    assert hosts["subject"]["ansible_user"] == "molecule"
    assert hosts["subject"]["docker_swarm_node_labels"]["ansible_host"] == "subject"
    assert "StrictHostKeyChecking=yes" in hosts["subject"]["ansible_ssh_common_args"]
    assert "GlobalKnownHostsFile=/dev/null" in hosts["subject"]["ansible_ssh_common_args"]
    assert "peer" not in json.dumps(inventory)
    monkeypatch.setenv("PROXMOX_VE_API_TOKEN", "SENTINEL")
    monkeypatch.setenv("TF_VAR_password", "SENTINEL")
    monkeypatch.setenv("SSH_AUTH_SOCK", "SENTINEL")
    monkeypatch.setenv("ANSIBLE_INVENTORY", "production.yml")
    monkeypatch.setenv("TF_CLI_CONFIG_FILE", str(directory / "trusted-mirror.tfrc"))
    monkeypatch.setenv("TF_DATA_DIR", "/production/state")
    monkeypatch.setenv("TF_WORKSPACE", "production")
    env = VM.guest_environment(directory)
    assert not any("SENTINEL" in v or "production.yml" in v for v in env.values())
    assert env["HOME"] != os.environ.get("HOME")
    provider_env = VM.provisioning_environment(manifest)
    assert provider_env["TF_CLI_CONFIG_FILE"] == str(directory / "trusted-mirror.tfrc")
    assert not {"TF_VAR_password", "TF_DATA_DIR", "TF_WORKSPACE"} & provider_env.keys()


@pytest.mark.parametrize(
    "field,value",
    [
        ("vm_ids", [9100, 9100]),
        ("approved_disposable", "true"),
        ("addresses", ["127.0.0.1/24"]),
        ("addresses", ["192.0.2.0/24"]),
        ("endpoint", "http://example.invalid"),
        ("pool_id", "production"),
        ("pool_id", ""),
        ("pool_id", 1),
    ],
)
def test_allocation_refuses_invalid_or_ambiguous_inputs(tmp_path, field, value):
    config = json.loads((ROOT / "molecule/vm/allocation.json.sample").read_text())
    config[field] = value
    path = tmp_path / "allocation.json"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        VM.allocation(path)


@pytest.mark.integration
def test_retirement_checks_exact_vm_identity_and_refuses_foreign_state(prepared):
    _, manifest = prepared
    own = {
        "type": "proxmox_virtual_environment_vm",
        "values": {
            "vm_id": manifest["run"]["template_id"],
            "node_name": manifest["run"]["node"],
            "name": f"molecule-{manifest['id']}-template",
            "description": f"homelab-molecule:{manifest['id']}:template",
        },
    }
    # Partial creation is explicitly supported; no absent VM is adopted.
    VM.check_state({"values": {"root_module": {"resources": [own]}}}, manifest)
    own["values"]["vm_id"] = 9100
    with pytest.raises(ValueError, match="foreign VM"):
        VM.check_state({"values": {"root_module": {"resources": [own]}}}, manifest)


@pytest.mark.integration
def test_failed_retirement_reports_observed_survivors_without_a_success_marker(prepared, monkeypatch):
    directory, manifest = prepared
    guest_id = manifest["run"]["guests"]["subject"]["vm_id"]
    volume = f"{manifest['run']['storage']}:vm-{guest_id}-disk-0"
    calls = []

    def api(path):
        calls.append(path)
        if path == "cluster/resources?type=vm":
            return [{"vmid": guest_id}]
        return [{"vmid": guest_id, "volid": volume}] if f"/storage/{manifest['run']['storage']}/" in path else []

    monkeypatch.setattr(VM, "Proxmox", lambda _: SimpleNamespace(ownership=lambda _: calls.append("ownership"), api=api))
    monkeypatch.setattr(VM, "locked", lambda _: nullcontext())
    monkeypatch.setattr(VM.subprocess, "check_output", lambda *args, **kwargs: b"{}")
    monkeypatch.setattr(VM, "verify_files", lambda *args: calls.append("verified-files"))
    monkeypatch.setattr(VM, "command", lambda *args: (1, 0.1))
    with pytest.raises(ValueError, match="exact --confirm-run"):
        VM.retire(directory, manifest, "another-run")
    assert calls == []
    with pytest.raises(ValueError) as failure:
        VM.retire(directory, manifest, manifest["id"])
    assert str(guest_id) in str(failure.value) and volume in str(failure.value)
    assert calls[:2] == ["ownership", "verified-files"]
    assert "cluster/resources?type=vm" in calls
    assert not (directory / "retired.json").exists()


@pytest.mark.integration
@pytest.mark.parametrize("stuck", [False, True])
def test_retirement_stops_only_state_owned_guests_and_bounds_an_unresponsive_stop(prepared, monkeypatch, stuck):
    _, manifest = prepared
    guest_id = manifest["run"]["guests"]["subject"]["vm_id"]
    path = f"nodes/{manifest['run']['node']}/qemu/{guest_id}/status"
    calls = []
    stopping = False

    def api(endpoint, data=None):
        nonlocal stopping
        calls.append((endpoint, data))
        if endpoint == "cluster/resources?type=vm":
            return [{"vmid": guest_id}, {"vmid": manifest["run"]["template_id"]}, {"vmid": 9100}]
        if endpoint == path + "/stop":
            stopping = True
            return "owned-stop-task"
        assert endpoint == path + "/current"
        return {"status": "running" if stuck or not stopping else "stopped"}

    client = SimpleNamespace(api=api, ownership=lambda _: calls.append(("ownership", None)))
    clock = iter([0, 61])
    monkeypatch.setattr(VM.time, "monotonic", lambda: next(clock))
    if stuck:
        with pytest.raises(ValueError, match="power-off is unconfirmed"):
            VM.stop_retiring_guests(client, manifest, {"subject"})
    else:
        VM.stop_retiring_guests(client, manifest, {"subject"})
    assert calls[0] == ("ownership", None)
    assert [(endpoint, data) for endpoint, data in calls if data is not None] == [(path + "/stop", {"overrule-shutdown": 1})]


@pytest.mark.integration
def test_retirement_refuses_power_control_when_current_ownership_differs(prepared):
    _, manifest = prepared

    def foreign(_):
        raise ValueError("Current ownership differs")

    def forbidden(*args, **kwargs):
        pytest.fail("Power control preceded ownership validation")

    with pytest.raises(ValueError, match="ownership differs"):
        VM.stop_retiring_guests(SimpleNamespace(ownership=foreign, api=forbidden), manifest, {"subject"})


@pytest.mark.integration
@pytest.mark.parametrize("prepared", [None, "molecule-acceptance"], indirect=True)
def test_saved_plan_enforces_budget_and_explicitly_stopped_template(prepared):
    _, manifest = prepared
    address = "proxmox_virtual_environment_vm.template"
    value = {
        "vm_id": manifest["run"]["template_id"],
        "node_name": manifest["run"]["node"],
        "name": f"molecule-{manifest['id']}-template",
        "description": f"homelab-molecule:{manifest['id']}:template",
        "pool_id": manifest["run"].get("pool_id"),
        "template": True,
        "started": None,
        "on_boot": False,
        "cpu": [{"cores": 2}],
        "memory": [{"dedicated": 2048}],
        "network_device": [{"bridge": manifest["run"]["bridge"]}],
        "disk": [{"datastore_id": manifest["run"]["storage"], "size": manifest["run"]["image"]["disk_gb"]}],
    }
    expression = {"constant_value": False}
    plan = {
        "configuration": {"root_module": {"resources": [{"address": address, "expressions": {"started": expression}}]}},
        "resource_changes": [{"address": address, "mode": "managed", "type": "proxmox_virtual_environment_vm", "change": {"after": value}}],
    }
    # The actual provider's template plan has null started, despite literal false.
    VM.check_plan(plan, manifest)
    value["pool_id"] = "production"
    with pytest.raises(ValueError, match="approved pool"):
        VM.check_plan(plan, manifest)
    value["pool_id"] = manifest["run"].get("pool_id")
    expression["constant_value"] = True
    with pytest.raises(ValueError, match="stopped template"):
        VM.check_plan(plan, manifest)
    expression["constant_value"] = False
    value["memory"][0]["dedicated"] = 4096
    with pytest.raises(ValueError, match="CPU/RAM budget"):
        VM.check_plan(plan, manifest)
    value["memory"][0]["dedicated"] = 2048
    value["disk"].append(dict(value["disk"][0]))
    with pytest.raises(ValueError, match="disk storage or size"):
        VM.check_plan(plan, manifest)
    value["disk"].pop()
    value["disk"][0]["size"] += 1
    with pytest.raises(ValueError, match="disk storage or size"):
        VM.check_plan(plan, manifest)
    value["disk"][0]["size"] -= 1
    value["node_name"] = "unapproved-node"
    with pytest.raises(ValueError, match="foreign VM"):
        VM.check_plan(plan, manifest)


@pytest.mark.integration
@pytest.mark.parametrize("prepared", [None, "molecule-acceptance"], indirect=True)
def test_guest_plan_cannot_clone_a_migration_vm_or_change_the_reserved_address(prepared):
    _, manifest = prepared
    run = manifest["run"]
    guest = run["guests"]["subject"]
    value = {
        "vm_id": guest["vm_id"],
        "node_name": run["node"],
        "name": f"molecule-{manifest['id']}-subject",
        "description": f"homelab-molecule:{manifest['id']}:subject",
        "pool_id": run.get("pool_id"),
        "template": False,
        "started": True,
        "on_boot": False,
        "cpu": [{"cores": 2}],
        "memory": [{"dedicated": 2048}],
        "network_device": [{"bridge": run["bridge"]}],
        "disk": [{"datastore_id": run["storage"], "size": run["disk_gb"]}],
        "clone": [{"vm_id": run["template_id"], "full": True, "node_name": None}],
        "initialization": [
            {
                "datastore_id": run["storage"],
                "dns": [{"domain": "", "servers": run["dns"]}],
                "ip_config": [{"ipv4": [{"address": guest["address"], "gateway": run["gateway"]}], "ipv6": []}],
            }
        ],
    }
    plan = {"resource_changes": [{"mode": "managed", "type": "proxmox_virtual_environment_vm", "change": {"after": value}}]}
    VM.check_plan(plan, manifest)
    value["pool_id"] = "production"
    with pytest.raises(ValueError, match="approved pool"):
        VM.check_plan(plan, manifest)
    value["pool_id"] = run.get("pool_id")
    value["disk"][0]["size"] += 1
    with pytest.raises(ValueError, match="disk storage or size"):
        VM.check_plan(plan, manifest)
    value["disk"][0]["size"] -= 1
    # The real provider's no-op resume plan normalizes the implicit node to "".
    value["clone"][0]["node_name"] = ""
    VM.check_plan(plan, manifest)
    value["clone"][0]["node_name"] = "another-node"
    with pytest.raises(ValueError, match="stopped image template"):
        VM.check_plan(plan, manifest)
    value["clone"][0]["node_name"] = ""
    value["clone"][0]["vm_id"] = 9100
    with pytest.raises(ValueError, match="this run's stopped image template"):
        VM.check_plan(plan, manifest)
    value["clone"][0]["vm_id"] = run["template_id"]
    value["initialization"][0]["ip_config"][0]["ipv4"][0]["address"] = "192.0.2.99/24"
    with pytest.raises(ValueError, match="approved guest address"):
        VM.check_plan(plan, manifest)


@pytest.mark.integration
def test_modified_allocation_is_rejected_before_guest_or_provider_execution(prepared):
    directory, manifest = prepared
    manifest["run"]["guests"]["subject"]["address"] = "192.0.2.99/24"
    (directory / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="addresses differ"):
        VM.load_run(directory)


@pytest.mark.integration
def test_custom_network_data_cannot_change_allocation_or_rename_the_link(prepared):
    _, manifest = prepared
    manifest["os"] = "ubuntu2604"
    manifest["run"]["image"] = VM.IMAGES["ubuntu2604"] | {"user": "molecule"}
    name = f"molecule-{manifest['id']}-network.yaml"
    data = VM.network_data(manifest)
    value = {
        "node_name": manifest["run"]["node"],
        "datastore_id": manifest["run"]["snippet_storage"],
        "id": manifest["run"]["snippet_storage"] + ":snippets/" + name,
        "source_raw": [{"file_name": name, "data": json.dumps(data)}],
    }
    state = {"values": {"root_module": {"resources": [{"type": "proxmox_virtual_environment_file", "values": value}]}}}
    VM.check_state(state, manifest)
    for field, unwanted in (("addresses", ["192.0.2.99/24"]), ("set-name", "eth0")):
        changed = VM.network_data(manifest)
        changed["ethernets"]["ens18"][field] = unwanted
        value["source_raw"][0]["data"] = json.dumps(changed)
        with pytest.raises(ValueError, match="network data differs"):
            VM.check_state(state, manifest)


@pytest.mark.integration
def test_changed_node_or_network_allocation_cannot_reach_provisioning(prepared):
    directory, manifest = prepared
    for field, unexpected in (("node", "another-node"), ("gateway", "192.0.2.99")):
        previous = manifest["run"][field]
        manifest["run"][field] = unexpected
        (directory / "manifest.json").write_text(json.dumps(manifest))
        with pytest.raises(ValueError, match="resources differ"):
            VM.load_run(directory)
        manifest["run"][field] = previous


@pytest.mark.integration
def test_untrusted_node_is_rejected_before_provider_access(prepared, monkeypatch):
    directory, manifest = prepared
    calls = []

    def ssh_failure(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=255)

    def provider_forbidden(config):
        pytest.fail("An unverified node reached the infrastructure provider")

    monkeypatch.setattr(VM.subprocess, "run", ssh_failure)
    monkeypatch.setattr(VM, "Proxmox", provider_forbidden)
    with pytest.raises(ValueError, match="verification failed"):
        VM.provision(directory, manifest)
    assert "StrictHostKeyChecking=yes" in calls[0]
    assert "GlobalKnownHostsFile=/dev/null" in calls[0]
    assert "UserKnownHostsFile=" + str(Path.home() / ".ssh/known_hosts") in calls[0]


@pytest.mark.integration
def test_ownership_checks_every_current_disk_and_never_adopts_a_foreign_vm(prepared, monkeypatch):
    _, manifest = prepared
    client = object.__new__(VM.Proxmox)
    client.config = manifest["allocation"]
    values = {
        "name": f"molecule-{manifest['id']}-subject",
        "description": f"homelab-molecule:{manifest['id']}:subject",
        "tags": f"molecule;run-{manifest['id']}",
        "scsi0": "test-disks:vm-980001-disk-0,size=32G",
    }
    monkeypatch.setattr(client, "api", lambda path: [{"vmid": 980001}])
    monkeypatch.setattr(client, "config_for", lambda vm_id: values)
    VM.Proxmox.ownership(client, manifest)
    values["scsi0"] = "test-disks:vm-9100-disk-0,size=32G"
    with pytest.raises(ValueError, match="disk outside"):
        VM.Proxmox.ownership(client, manifest)
    values["description"] = "production"
    with pytest.raises(ValueError, match="ownership differs"):
        VM.Proxmox.ownership(client, manifest)


@pytest.fixture
def pending_pool_template(prepared):
    _, manifest = prepared
    run = manifest["run"]
    client = object.__new__(VM.Proxmox)
    client.config = manifest["allocation"]
    values = {
        "name": f"molecule-{manifest['id']}-template",
        "description": f"homelab-molecule:{manifest['id']}:template",
        "template": 1,
        "digest": "synthetic-config-digest",
        "scsi0": f"{run['storage']}:base-{run['template_id']}-disk-0,size=10G",
    }
    status = {"status": "stopped"}
    pool = {
        "poolid": "molecule-acceptance",
        "comment": "homelab-molecule:acceptance-pool",
        "members": [{"type": "qemu", "vmid": run["template_id"], "node": run["node"], "name": values["name"]}],
    }
    state = {
        "values": {
            "root_module": {
                "resources": [
                    {
                        "address": "proxmox_virtual_environment_vm.template",
                        "type": "proxmox_virtual_environment_vm",
                        "values": {
                            "id": str(run["template_id"]),
                            "vm_id": run["template_id"],
                            "node_name": run["node"],
                            "pool_id": run["pool_id"],
                            "name": values["name"],
                            "description": values["description"],
                            "template": True,
                        },
                    }
                ]
            }
        }
    }
    writes = []

    def api(path, data=None, *, method=None):
        if path == "cluster/resources?type=vm":
            return [{"vmid": run["template_id"]}]
        if path == "pools?poolid=molecule-acceptance":
            return [pool]
        if path == f"nodes/{run['node']}/qemu/{run['template_id']}/status/current":
            return status
        if path == f"nodes/{run['node']}/qemu/{run['template_id']}/config":
            if data is not None:
                assert method in {"PUT", "POST"} and data["digest"] == values["digest"]
                writes.append(dict(data))
                if method == "POST":
                    return "UPID:synthetic:qmconfig"  # Worker has not committed yet.
                values["tags"] = data["tags"]
                return None
            return dict(values)
        pytest.fail("Unexpected API access")

    client.api = api
    return client, manifest, state, values, pool, status, writes


@pytest.mark.integration
@pytest.mark.parametrize("prepared", ["molecule-acceptance"], indirect=True)
def test_pool_template_tag_initialization_is_guarded_and_retryable_after_an_uncertain_write(pending_pool_template, monkeypatch):
    client, manifest, state, values, _, _, writes = pending_pool_template
    # POST can return successfully while strict ownership still sees no tags.
    task = client.api(
        f"nodes/{manifest['run']['node']}/qemu/{manifest['run']['template_id']}/config",
        {"tags": f"molecule;run-{manifest['id']}", "digest": values["digest"]},
        method="POST",
    )
    assert task == "UPID:synthetic:qmconfig" and not values.get("tags")
    with pytest.raises(ValueError, match="ownership differs"):
        client.ownership(manifest)  # Ordinary operations still reject missing tags.
    writes.clear()
    original_api = client.api

    def interrupted(path, data=None, *, method=None):
        result = original_api(path, data, method=method)
        if data is not None:
            raise ValueError("Synthetic connection loss after committed tag update")
        return result

    monkeypatch.setattr(client, "api", interrupted)
    with pytest.raises(ValueError, match="connection loss"):
        client.initialize_template_tags(manifest, state)
    monkeypatch.setattr(client, "api", original_api)
    client.initialize_template_tags(manifest, state)
    client.ownership(manifest)
    assert writes == [{"tags": f"molecule;run-{manifest['id']}", "digest": "synthetic-config-digest"}]
    assert values["tags"] == f"molecule;run-{manifest['id']}"


@pytest.mark.integration
@pytest.mark.parametrize("prepared", ["molecule-acceptance"], indirect=True)
@pytest.mark.parametrize(
    ("foreign", "error"),
    [
        ("untracked", "saved state"),
        ("wrong_state_id", "exact saved resource"),
        ("identity", "ownership differs"),
        ("tags", "ownership differs"),
        ("pool", "outside its approved pool"),
        ("running", "remain stopped"),
        ("digest", "current config digest"),
    ],
)
def test_pool_template_tag_initialization_never_adopts_or_overwrites_unverified_resources(pending_pool_template, foreign, error):
    client, manifest, state, values, pool, status, writes = pending_pool_template
    if foreign == "untracked":
        state["values"]["root_module"]["resources"].clear()
    elif foreign == "wrong_state_id":
        state["values"]["root_module"]["resources"][0]["values"]["id"] = "104"
    elif foreign == "identity":
        values["description"] = "unrelated"
    elif foreign == "tags":
        values["tags"] = "production"
    elif foreign == "pool":
        pool["members"].clear()
    elif foreign == "running":
        status["status"] = "running"
    else:
        values.pop("digest")
    with pytest.raises(ValueError, match=error):
        client.initialize_template_tags(manifest, state)
    assert writes == [] and values.get("tags") != f"molecule;run-{manifest['id']}"


@pytest.mark.integration
@pytest.mark.parametrize("prepared", ["molecule-acceptance"], indirect=True)
def test_template_tag_update_rejects_a_config_race_without_retrying_the_write(pending_pool_template, monkeypatch):
    client, manifest, state, values, _, _, writes = pending_pool_template
    original_api = client.api

    def raced(path, data=None, *, method=None):
        if data is not None:
            values["digest"] = "changed-by-another-writer"
            assert data["digest"] != values["digest"]
            raise ValueError("Synthetic PVE config digest conflict")
        return original_api(path, data, method=method)

    monkeypatch.setattr(client, "api", raced)
    with pytest.raises(ValueError, match="digest conflict"):
        client.initialize_template_tags(manifest, state)
    assert writes == [] and not values.get("tags")


@pytest.mark.integration
@pytest.mark.parametrize("prepared", ["molecule-acceptance"], indirect=True)
def test_retirement_completes_owned_template_identity_before_power_or_destroy(prepared, pending_pool_template, monkeypatch):
    directory, manifest = prepared
    client, _, state, values, _, _, writes = pending_pool_template
    original_api = client.api
    destroyed = False

    def api(path, data=None, *, method=None):
        if destroyed and (path == "cluster/resources?type=vm" or "/storage/" in path):
            return []
        return original_api(path, data, method=method)

    def destroy(argv, *args):
        nonlocal destroyed
        assert argv[:2] == ["tofu", "destroy"]
        assert len(writes) == 1 and values["tags"] == f"molecule;run-{manifest['id']}"
        destroyed = True
        return 0, 0.1

    monkeypatch.setattr(client, "api", api)
    monkeypatch.setattr(VM, "Proxmox", lambda _: client)
    monkeypatch.setattr(VM, "locked", lambda _: nullcontext())
    monkeypatch.setattr(VM.subprocess, "check_output", lambda *args, **kwargs: json.dumps(state))
    monkeypatch.setattr(VM, "verify_remote_files", lambda *args, **kwargs: None)
    monkeypatch.setattr(VM, "command", destroy)
    VM.retire(directory, manifest, manifest["id"])
    assert json.loads((directory / "retired.json").read_text())["id"] == manifest["id"] and destroyed


@pytest.mark.integration
@pytest.mark.parametrize("prepared", ["molecule-acceptance"], indirect=True)
@pytest.mark.parametrize("foreign", ["storage", "production", "controller", "other_run", "outside_pool", "malformed_member"])
def test_pool_ownership_rejects_foreign_members_and_reserved_vms_outside_the_pool(prepared, foreign):
    _, manifest = prepared
    pool = {"poolid": "molecule-acceptance", "comment": "homelab-molecule:acceptance-pool", "members": []}
    rows = []
    client = object.__new__(VM.Proxmox)
    client.api = lambda path: [pool] if path == "pools?poolid=molecule-acceptance" else rows
    client.pool_ownership(manifest)  # An empty owned pool is ready for the next run.
    member = {"type": "qemu", "vmid": 980001, "node": manifest["run"]["node"], "name": f"molecule-{manifest['id']}-subject"}
    pool["members"].append(member)
    rows.append({"vmid": 980001})
    client.pool_ownership(manifest)
    if foreign == "storage":
        pool["members"].append({"type": "storage", "storage": "test-disks"})
    elif foreign == "production":
        member["vmid"] = 104
    elif foreign == "controller":
        member["vmid"] = 9300
    elif foreign == "other_run":
        member["name"] = "molecule-" + "f" * 32 + "-subject"
    elif foreign == "malformed_member":
        pool["members"].append(None)
    else:
        pool["members"].clear()
    with pytest.raises(ValueError, match="foreign member|malformed member|outside its approved pool"):
        client.pool_ownership(manifest)


@pytest.mark.integration
@pytest.mark.parametrize("prepared", ["molecule-acceptance"], indirect=True)
@pytest.mark.parametrize("invalid", ["object", "empty", "duplicate", "malformed_entry", "mismatched", "missing_poolid"])
def test_pool_ownership_requires_exactly_one_matching_object_in_a_list(prepared, invalid):
    _, manifest = prepared
    pool = {"poolid": "molecule-acceptance", "comment": "homelab-molecule:acceptance-pool", "members": []}
    response = {
        "object": pool,
        "empty": [],
        "duplicate": [pool, pool],
        "malformed_entry": [None],
        "mismatched": [pool | {"poolid": "production"}],
        "missing_poolid": [{key: value for key, value in pool.items() if key != "poolid"}],
    }[invalid]
    client = object.__new__(VM.Proxmox)
    client.api = lambda path: response
    with pytest.raises(ValueError, match="exactly one object with the approved poolid"):
        client.pool_ownership(manifest)


@pytest.mark.integration
@pytest.mark.parametrize("prepared", ["molecule-acceptance"], indirect=True)
def test_pool_manifest_cannot_change_or_omit_its_approved_pool(prepared):
    directory, manifest = prepared
    assert manifest["run"]["pool_id"] == manifest["allocation"]["pool_id"] == "molecule-acceptance"
    manifest["run"].pop("pool_id")
    (directory / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="pool differs"):
        VM.load_run(directory, retirement=True)


@pytest.mark.integration
def test_synthetic_provider_refuses_production_or_other_run_declarations(prepared, monkeypatch):
    directory, manifest = prepared
    plugin_spec = importlib.util.spec_from_file_location(
        "vm_credentials", ROOT / "molecule/shared/collections/ansible_collections/infisical/vault/plugins/lookup/read_secrets.py"
    )
    plugin = importlib.util.module_from_spec(plugin_spec)
    plugin_spec.loader.exec_module(plugin)
    monkeypatch.setenv("HOMELAB_MOLECULE_SECRET_FILE", str(directory / "synthetic-credential.json"))
    lookup = plugin.LookupModule()
    variables = {"molecule_vm_run_id": manifest["id"]}
    result = lookup.run([], variables, path="/molecule/" + manifest["id"], secret_name="credential")
    assert len(result) == 1 and result[0]["value"].startswith("molecule-")
    with pytest.raises(Exception, match="refuses non-fixture"):
        lookup.run([], variables, path="/production", secret_name="credential")
    with pytest.raises(Exception, match="different run"):
        lookup.run([], {"molecule_vm_run_id": "a" * 32}, path="/molecule/" + "a" * 32, secret_name="credential")


def test_path_selection_is_focused_and_broad_lane_includes_both_runtime_orders(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "vm", VM)
    suite_spec = importlib.util.spec_from_file_location("vm_suite", ROOT / "scripts/testing/suite.py")
    suite = importlib.util.module_from_spec(suite_spec)
    suite_spec.loader.exec_module(suite)
    assert not suite.select(["docs/unrelated.md"])
    assert not suite.select(["molecule/README.md", "docs/testing.md"])
    assert suite.select(["molecule/protected_network/verify.yml"]) == {"protected_network"}
    assert suite.select(["ansible/roles/service_firewall/files/lifecycle_remote.py"]) == {"application_lifecycle", "protected_network"}
    assert suite.select(["ansible/roles/native_services/templates/node_exporter.service.j2"]) == {"node_exporter"}
    assert suite.select(["molecule/node_exporter/verify.yml"]) == {"node_exporter"}
    node_cases = suite.plan({"node_exporter"}, list(VM.IMAGES))
    assert {case["os"] for case in node_cases} == set(VM.IMAGES)
    assert all(case["suite"] == "node_exporter" for case in node_cases)
    cases = suite.plan(suite.select(broad=True), ["debian13", "rocky102"])
    assert cases[0]["suite"] == "node_exporter" and cases[0]["os"] == "rocky102"
    installs = [case for case in cases if case["suite"] == "runtime_install"]
    assert {(case["os"], case["order"]) for case in installs} == {
        (platform, order) for platform in ["debian13", "rocky102"] for order in ["docker-first", "podman-first"]
    }
    assert len({json.dumps(case, sort_keys=True) for case in cases}) == len(cases)


def test_source_provenance_detects_code_changes_without_invalidating_documentation_updates(tmp_path, monkeypatch):
    (tmp_path / "play.yml").write_text("initial code")
    (tmp_path / "notes.md").write_text("initial documentation")
    monkeypatch.setattr(VM, "ROOT", tmp_path)
    monkeypatch.setattr(
        VM.subprocess,
        "check_output",
        lambda argv, **kwargs: b"play.yml\0notes.md\0" if argv[1] == "ls-files" else "a" * 40,
    )
    before = VM.source_state()
    (tmp_path / "notes.md").write_text("updated documentation")
    assert VM.source_state() == before
    (tmp_path / "play.yml").write_text("changed code")
    assert VM.source_state() != before
    (tmp_path / "play.yml").unlink()
    assert VM.source_state() != before


@pytest.mark.integration
def test_insufficient_controller_space_fails_before_provider_or_ssh_access(prepared, monkeypatch):
    directory, manifest = prepared
    monkeypatch.setattr(VM.shutil, "disk_usage", lambda path: SimpleNamespace(free=0))
    monkeypatch.setattr(VM, "Proxmox", lambda config: pytest.fail("Provider reached before the space gate"))
    monkeypatch.setattr(VM, "verify_remote_files", lambda *args, **kwargs: pytest.fail("SSH reached before the space gate"))
    with pytest.raises(ValueError, match="Insufficient controller"):
        VM.provision(directory, manifest)


@pytest.mark.integration
@pytest.mark.parametrize("condition", ["owned", "foreign-name", "unverified-bytes"])
def test_orphan_snippet_recovery_requires_saved_plan_scope_and_verified_bytes(prepared, monkeypatch, condition):
    directory, manifest = prepared
    (directory / "tofu/run.tfplan").write_text("private synthetic saved plan")
    filename = f"molecule-{manifest['id']}-bootstrap.yaml"
    volume = manifest["run"]["snippet_storage"] + ":snippets/" + filename
    plan = {
        "resource_changes": [
            {
                "mode": "managed",
                "type": "proxmox_virtual_environment_file",
                "change": {
                    "actions": ["create"],
                    "after": {
                        "content_type": "snippets",
                        "node_name": manifest["run"]["node"],
                        "datastore_id": manifest["run"]["snippet_storage"],
                        "overwrite": False,
                        "file_mode": "0600",
                        "source_raw": [
                            {"file_name": "operator-owned.yaml" if condition == "foreign-name" else filename, "data": "owned bootstrap"}
                        ],
                    },
                },
            }
        ]
    }
    monkeypatch.setattr(VM.subprocess, "check_output", lambda *args, **kwargs: json.dumps(plan))
    events = []

    def verify(files, received, allow_missing):
        assert files == [[volume, "sha256", hashlib.sha256(b"owned bootstrap").hexdigest()]]
        assert received is manifest and allow_missing is False
        events.append("verify")
        if condition == "unverified-bytes":
            raise ValueError("Requested file verification failed")

    class Client:
        present = True

        def api(self, path, *, method=None):
            if method == "DELETE":
                assert path.endswith("/" + VM.urllib.parse.quote(volume, safe=""))
                events.append("delete")
                self.present = False
                return
            return [{"volid": volume}] if self.present else []

    monkeypatch.setattr(VM, "verify_remote_files", verify)
    client = Client()
    if condition == "owned":
        VM.retire_orphan_snippets(directory, manifest, client, {})
        assert events == ["verify", "delete"] and client.present is False
    else:
        with pytest.raises(ValueError):
            VM.retire_orphan_snippets(directory, manifest, client, {})
        assert "delete" not in events and client.present is True


@pytest.mark.integration
@pytest.mark.parametrize(
    "platform,builder", [("debian13", False), ("rocky102", False), ("ubuntu2604", False), ("fedora44", False), ("ubuntu2604", True)]
)
def test_new_run_carries_selected_os_and_capacity_through_manifest_provider_and_guest_inputs(tmp_path, platform, builder):
    config = json.loads((ROOT / "molecule/vm/allocation.json.sample").read_text())
    public_key = tmp_path / "test.pub"
    public_key.write_text("ssh-ed25519 AAAATEST fixture-public-key")
    config.update(approved_disposable=True, allow_image_preparation=True, public_key_path=str(public_key))
    allocation = tmp_path / "allocation.json"
    allocation.write_text(json.dumps(config))
    args = SimpleNamespace(
        allocation=allocation,
        state_root=tmp_path / "runs",
        os=platform,
        suite="node_exporter",
        order="docker-first",
        runtime="rootless",
        image_builder=builder,
    )
    VM.prepare(args)
    directory = next(args.state_root.iterdir())
    manifest = VM.load_run(directory)
    selected = 32 if builder else 16
    assert manifest["run"]["disk_gb"] == selected
    assert manifest["run"]["image"]["disk_gb"] <= selected
    assert json.loads((directory / "tofu/run.auto.tfvars.json").read_text())["run"]["disk_gb"] == selected
    guest = json.loads((directory / "guest-vars.json").read_text())
    assert guest["molecule_vm_disk_gb"] == selected
    assert manifest["suite"] == guest["molecule_vm_suite"] == "node_exporter"
    assert manifest["os"] == guest["molecule_vm_platform"] == platform
    image = guest["molecule_vm_images"][guest["molecule_vm_platform"]]
    assert manifest["run"]["image"] == image | {"user": "molecule"}
    assert guest["docker_selinux_enable"] is image["selinux"]
    assert guest["podman_docker_iptables_compatibility"] is False
    assert VM.inventory(manifest, directory)["all"]["children"]["molecule_node_exporter"]["hosts"] == {"subject": {}}
    # A retained run cannot adopt a changed capacity. It remains retireable.
    manifest["run"]["disk_gb"] = selected - 1
    (directory / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="capacity changed"):
        VM.load_run(directory)
    assert VM.load_run(directory, retirement=True)["id"] == manifest["id"]


@pytest.mark.integration
@pytest.mark.parametrize("size", [9, 33, True])
def test_invalid_or_shrinking_disk_selection_fails_before_creating_a_run(prepared, monkeypatch, size):
    directory, manifest = prepared
    config = dict(VM.IMAGES["rocky102"], guest_disk_gb=size)
    monkeypatch.setitem(VM.IMAGES, "rocky102", config)
    allocation = directory.parent.parent / "allocation.json"
    args = SimpleNamespace(
        allocation=allocation,
        state_root=directory.parent.parent / "new-runs",
        os="rocky102",
        suite="node_exporter",
        order="docker-first",
        runtime="rootless",
    )
    with pytest.raises(ValueError, match="shrinking is forbidden"):
        VM.prepare(args)
    assert not args.state_root.exists()


@pytest.mark.integration
def test_legacy_disk_manifest_can_be_retired_without_resizing(prepared):
    directory, manifest = prepared
    manifest["run"].pop("disk_gb")
    manifest["run"]["image"].pop("guest_disk_gb")
    (directory / "manifest.json").write_text(json.dumps(manifest))
    assert VM.load_run(directory, retirement=True)["id"] == manifest["id"]
    with pytest.raises(ValueError, match="Image pin changed"):
        VM.load_run(directory)


@pytest.mark.integration
@pytest.mark.parametrize("separate", [False, True])
def test_node_file_verification_uses_management_identity_without_changing_guest_identity(prepared, monkeypatch, separate):
    _, manifest = prepared
    if not separate:
        manifest["allocation"].pop("node_private_key_path")
    calls = []
    monkeypatch.setattr(VM.subprocess, "run", lambda argv, **kwargs: calls.append(argv) or SimpleNamespace(returncode=0))
    VM.verify_remote_files([], manifest, allow_missing=False)
    expected = manifest["allocation"]["node_private_key_path" if separate else "private_key_path"]
    assert calls[0][calls[0].index("-i") + 1] == expected
    inventory = VM.inventory(manifest, Path("/private/run"))
    assert (
        inventory["all"]["children"]["molecule_guests"]["hosts"]["subject"]["ansible_ssh_private_key_file"]
        == manifest["allocation"]["private_key_path"]
    )
