"""Offline controller glue boundaries; vm.py retains lifecycle ownership."""

import importlib.util
import json
import os
import re
import subprocess
import sys
from itertools import product
from pathlib import Path
from types import SimpleNamespace

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
    assert set(inputs) == {"suite", "os", "source_branch", "source_sha", "candidate_approved"}
    assert inputs["suite"]["type"] == inputs["os"]["type"] == "choice"
    assert inputs["source_branch"]["default"] == "main" and inputs["source_sha"]["default"] == ""
    assert inputs["candidate_approved"]["type"] == "boolean" and inputs["candidate_approved"]["default"] is False
    assert inputs["suite"]["default"] == "rocky_node_exporter" and inputs["os"]["default"] == "rocky102"
    assert set(inputs["os"]["options"]) == {"all", *json.loads((ROOT / "molecule/vm/images.json").read_text())}
    assert workflow["concurrency"]["cancel-in-progress"] is False
    job = workflow["jobs"]["acceptance"]
    step = job["steps"][0]
    assert "${{" not in step["run"] and '--suite "$VM_SUITE" --os "$VM_OS"' in step["run"]
    assert "always()" not in (ROOT / ".forgejo/workflows/molecule.yml").read_text()


def test_runner_installs_acl_before_unprivileged_workstation_tooling():
    tasks = yaml.safe_load((ROOT / "ansible/roles/native_services/tasks/forgejo_runner.yml").read_text())
    tooling = next(
        i
        for i, task in enumerate(tasks)
        if task.get("ansible.builtin.include_role", {}).get("name") == "workstation"
        and task["ansible.builtin.include_role"].get("tasks_from") == "tools"
    )
    # SSH connects as rocky; the tooling switches to molecule-ci. Ansible needs
    # setfacl before that switch to keep its transferred modules private.
    assert any(
        "acl" in task.get("ansible.builtin.dnf", {}).get("name", []) and task["ansible.builtin.dnf"].get("state") == "present"
        for task in tasks[:tooling]
    )


@pytest.fixture
def git_source(tmp_path, monkeypatch):
    settings = config(tmp_path)
    source = tmp_path / "origin"
    source.mkdir()
    environment = CONTROLLER.public_environment(settings)
    subprocess.run(["git", "init", "--quiet", "--initial-branch=main", str(source)], env=environment, check=True)
    for name in ["scripts/testing/suite.py", "scripts/testing/vm.py", "ansible/requirements.txt"]:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Synthetic source; never execute infrastructure operations.\n")
    subprocess.run(["git", "-C", str(source), "add", "."], env=environment, check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "-m",
            "Synthetic main",
        ],
        env=environment,
        check=True,
    )
    monkeypatch.setattr(CONTROLLER, "SOURCE", str(source))
    return settings, source, environment


@pytest.mark.integration
def test_exact_main_checkout_is_retained_and_recovery_rejects_modified_source(tmp_path, git_source):
    settings, _, environment = git_source
    checkout = tmp_path / "checkouts" / ("a" * 32)
    checkout.parent.mkdir()
    selected = CONTROLLER.checkout_source(checkout, environment)
    assert selected["requested_source_sha"] is None and selected["source_branch"] == "main"
    record = {"checkout": str(checkout), "sha": selected["resolved_source_sha"]}
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


def workflow_allows(condition, context):
    """Evaluate only this workflow's three equality fields and AND/OR operators."""
    pattern = r"forgejo[.](repository|ref|event_name)\s*==\s*'([^']*)'"
    boolean = re.sub(pattern, lambda match: str(context[match[1]] == match[2]), condition)
    assert re.fullmatch(r"\s*(?:True|False)(?:\s*(?:&&|\|\|)\s*(?:True|False))*\s*", boolean)
    return any(all(term.strip() == "True" for term in group.split("&&")) for group in boolean.split("||"))


def test_workflow_restricts_repository_ref_and_event_and_detects_permissive_guard():
    workflow = yaml.safe_load((ROOT / ".forgejo/workflows/molecule.yml").read_text())
    condition = workflow["jobs"]["acceptance"]["if"]
    rejected_by_weakened_guard = False
    for repo, ref, event in product(
        ["homelab-ci/homelab-ci", "another/repository"],
        ["refs/heads/main", "refs/heads/unreviewed"],
        ["workflow_dispatch", "pull_request"],
    ):
        context = dict(repository=repo, ref=ref, event_name=event)
        expected = repo == "homelab-ci/homelab-ci" and ref == "refs/heads/main" and event == "workflow_dispatch"
        assert workflow_allows(condition, context) is expected
        rejected_by_weakened_guard |= workflow_allows(condition.replace("&&", "||", 1), context) != expected
    assert rejected_by_weakened_guard


def test_retirement_cannot_enter_during_owned_or_interrupted_maintenance(tmp_path, monkeypatch):
    drain = tmp_path / "draining"
    drain.mkdir()
    monkeypatch.setattr(CONTROLLER, "DRAIN", drain)
    with pytest.raises(ValueError, match="draining"):
        CONTROLLER.recover(config(tmp_path), "a" * 32)


def test_agent_and_runner_units_require_confined_domains_without_weakening_hardening():
    import configparser

    from jinja2 import Environment, StrictUndefined

    settings = {"user": "fixture-ci", "group": "fixture-ci", "data_dir": "/var/lib/fixture-ci"}
    units = {}
    for name in ["forgejo-runner", "forgejo-runner-agent"]:
        source = ROOT / f"ansible/roles/native_services/templates/forgejo_runner/{name}.service.j2"
        rendered = Environment(undefined=StrictUndefined).from_string(source.read_text()).render(native_services_config=settings)
        unit = configparser.ConfigParser(interpolation=None, strict=False)
        unit.read_string(rendered)
        service = unit["Service"]
        assert service["User"] == settings["user"] and service["Group"] == settings["group"]
        assert all(service[key] == "true" for key in ["NoNewPrivileges", "ProtectHome", "PrivateTmp"])
        assert service["ProtectSystem"] == "strict" and service["UMask"] == "0077"
        assert not service["SELinuxContext"].startswith("-") and "unconfined" not in service["SELinuxContext"]
        units[name] = service
    assert units["forgejo-runner"]["SELinuxContext"] == "user_u:user_r:user_t:s0"
    agent = units["forgejo-runner-agent"]
    assert agent["SELinuxContext"] == "system_u:system_r:homelab_forgejo_agent_t:s0"
    assert agent["Type"] == "forking" and " -D " not in agent["ExecStart"]
    assert agent["RuntimeDirectoryMode"] == "0700"
    assert agent["ExecStartPost"].endswith("/usr/bin/ssh-add /etc/forgejo-runner/private/node-key")
    policy = (ROOT / "ansible/roles/native_services/files/forgejo_runner/selinux/homelab_forgejo_runner.te").read_text()
    statements = re.sub(r"#.*", "", policy)
    assert not re.search(r"\b(permissive|dontaudit|unconfined_domain_type)\b", statements)
    assert "execute_no_trans" not in re.search(r"allow init_t ssh_agent_exec_t:file ([^;]+);", statements)[1]
    assert not re.search(r"allow [^;]+:(?:tcp_socket|udp_socket|capability)\b", statements)


@pytest.mark.parametrize(
    ("branch", "sha", "approved"),
    [
        ("reviewed", "a" * 40, False),
        ("reviewed", "", True),
        ("reviewed", "short", True),
        ("reviewed", "A" * 40, True),
        ("https://github.com/foreign/repo", "a" * 40, True),
        ("reviewed; touch /tmp/untrusted", "a" * 40, True),
        ("--upload-pack=untrusted", "a" * 40, True),
        ("main", "", True),
    ],
)
def test_candidate_requires_explicit_approval_and_safe_exact_source_before_fetch(tmp_path, branch, sha, approved):
    with pytest.raises(ValueError):
        CONTROLLER.checkout_source(tmp_path / "checkout", {}, branch, sha, approved)
    assert not (tmp_path / "checkout").exists()


@pytest.mark.integration
def test_reviewed_candidate_uses_exact_sha_even_when_branch_advances(tmp_path, git_source):
    settings, source, environment = git_source
    subprocess.run(["git", "-C", str(source), "branch", "reviewed/candidate"], env=environment, check=True)
    requested = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], env=environment, text=True).strip()
    subprocess.run(["git", "-C", str(source), "checkout", "--quiet", "reviewed/candidate"], env=environment, check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "--allow-empty",
            "-m",
            "Unreviewed newer tip",
        ],
        env=environment,
        check=True,
    )
    checkout = tmp_path / "checkouts" / ("b" * 32)
    checkout.parent.mkdir()
    selected = CONTROLLER.checkout_source(checkout, environment, "reviewed/candidate", requested, True)
    assert selected["requested_source_sha"] == selected["resolved_source_sha"] == requested
    assert selected["branch_tip_sha"] != requested and selected["source_branch"] == "reviewed/candidate"
    assert CONTROLLER.source_checkout(selected | {"checkout": str(checkout), "sha": requested}, settings) == checkout


@pytest.mark.integration
@pytest.mark.parametrize("branch", ["main", "missing", "invalid..branch"])
def test_candidate_from_other_branch_or_invalid_branch_is_never_checked_out(tmp_path, git_source, branch):
    _, source, environment = git_source
    subprocess.run(["git", "-C", str(source), "checkout", "--quiet", "-b", "other"], env=environment, check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "--allow-empty",
            "-m",
            "Other branch only",
        ],
        env=environment,
        check=True,
    )
    foreign = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], env=environment, text=True).strip()
    checkout = tmp_path / "checkout"
    if branch == "main":
        with pytest.raises(ValueError, match="does not belong to the fetched GitHub branch"):
            CONTROLLER.checkout_source(checkout, environment, branch, foreign, True)
    else:
        with pytest.raises(subprocess.CalledProcessError) as error:
            CONTROLLER.checkout_source(checkout, environment, branch, foreign, True)
        assert error.value.cmd[1 if branch == "invalid..branch" else 3] == ("check-ref-format" if branch == "invalid..branch" else "fetch")
    assert not (checkout / "scripts/testing/suite.py").exists()


@pytest.mark.integration
@pytest.mark.parametrize("reachable", [False, True])
def test_candidate_failure_retains_requested_resolved_and_workflow_identity(tmp_path, git_source, monkeypatch, reachable):
    settings, source, environment = git_source
    settings["python"] = sys.executable
    # An actual local entry-point failure, before dependencies or credentials.
    (source / "scripts/testing/suite.py").write_text("raise SystemExit(23)\n")
    subprocess.run(["git", "-C", str(source), "add", "."], env=environment, check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "-m",
            "Failing synthetic entry point",
        ],
        env=environment,
        check=True,
    )
    requested = (
        subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], env=environment, text=True).strip()
        if reachable
        else "a" * 40
    )
    for name in ["runs", "jobs", "checkouts", "tmp"]:
        (tmp_path / name).mkdir(mode=0o700)
    monkeypatch.setattr(CONTROLLER, "DRAIN", tmp_path / "draining")
    monkeypatch.setattr(CONTROLLER.shutil, "disk_usage", lambda path: SimpleNamespace(free=7 * 1024**3))
    output = subprocess.check_output
    monkeypatch.setattr(
        CONTROLLER.subprocess, "check_output", lambda argv, **kwargs: "ext4\n" if argv[0] == "findmnt" else output(argv, **kwargs)
    )
    monkeypatch.setattr(
        CONTROLLER, "provisioning_environment", lambda config: pytest.fail("No credential access before validation/setup succeeds")
    )
    monkeypatch.setenv("FORGEJO_LAUNCHER_SHA", "c" * 40)
    if reachable:
        with pytest.raises(subprocess.CalledProcessError) as error:
            CONTROLLER.run(settings, "rocky_node_exporter", "rocky102", "main", requested, True)
        assert error.value.returncode == 23 and error.value.cmd[1].endswith("scripts/testing/suite.py")
    else:
        with pytest.raises(ValueError, match="does not belong to the fetched GitHub branch"):
            CONTROLLER.run(settings, "rocky_node_exporter", "rocky102", "main", requested, True)
    (job,) = (tmp_path / "jobs").iterdir()
    request = json.loads((job / "request.json").read_text())
    result = json.loads((job / "result.json").read_text())
    assert request["requested_source_sha"] == result["requested_source_sha"] == requested
    assert request["forgejo_workflow_sha"] == result["forgejo_workflow_sha"] == "c" * 40
    assert result["exit_code"] == 1 and not list((tmp_path / "runs").iterdir())
    if reachable:
        record = json.loads((job / "source.json").read_text())
        assert record["sha"] == record["resolved_source_sha"] == result["resolved_source_sha"] == requested
        assert CONTROLLER.source_checkout(record, settings) == Path(record["checkout"])
    else:
        assert result["resolved_source_sha"] is None and not (job / "source.json").exists()


@pytest.mark.integration
def test_workflow_passes_candidate_inputs_as_literal_arguments(tmp_path):
    workflow = yaml.safe_load((ROOT / ".forgejo/workflows/molecule.yml").read_text())
    step = workflow["jobs"]["acceptance"]["steps"][0]
    binary = tmp_path / "homelab-molecule"
    binary.write_text(
        f"#!{sys.executable}\nimport json,sys\nfrom pathlib import Path\nPath(sys.argv[0]+'.json').write_text(json.dumps(sys.argv[1:]))\n"
    )
    binary.chmod(0o700)
    # Metacharacters remain a single argument for the launcher's strict validation.
    branch = f"reviewed/$(touch {tmp_path}/executed)"
    values = {
        "suite": "rocky_node_exporter",
        "os": "rocky102",
        "source_branch": branch,
        "source_sha": "d" * 40,
        "candidate_approved": "true",
    }
    environment = {"PATH": str(tmp_path) + ":" + os.defpath}
    for key, expression in step["env"].items():
        environment[key] = (
            "c" * 40 if expression == "${{ forgejo.sha }}" else values[expression.removeprefix("${{ inputs.").removesuffix(" }}")]
        )
    subprocess.run(["bash", "-c", step["run"]], env=environment, check=True, timeout=5)
    assert json.loads(Path(str(binary) + ".json").read_text()) == [
        "run",
        "--suite",
        "rocky_node_exporter",
        "--os",
        "rocky102",
        "--source-branch",
        branch,
        "--source-sha",
        "d" * 40,
        "--candidate-approved",
        "true",
    ]
    assert not (tmp_path / "executed").exists()
