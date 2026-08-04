from __future__ import annotations

import json
import os
import pwd
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
OPT_ROOT = Path("/opt")
ROOTLESS_BIND_PREFIX = "codex-rootless-check-"


@pytest.fixture
def absent_rootless_bind_source(tmp_path):
    bind_source = OPT_ROOT / f"{ROOTLESS_BIND_PREFIX}{os.getpid()}-{tmp_path.name}"
    assert bind_source != OPT_ROOT
    assert bind_source.parent == OPT_ROOT
    assert bind_source.name.startswith(ROOTLESS_BIND_PREFIX)
    assert not os.path.lexists(bind_source)

    try:
        yield bind_source
    finally:
        assert bind_source != OPT_ROOT
        assert bind_source.parent == OPT_ROOT
        assert bind_source.name.startswith(ROOTLESS_BIND_PREFIX)
        if bind_source.is_symlink():
            bind_source.unlink()
        elif bind_source.exists():
            if bind_source.is_dir():
                shutil.rmtree(bind_source)
            else:
                bind_source.unlink()


def account_snapshot(name: str) -> tuple[object, ...] | None:
    try:
        entry = pwd.getpwnam(name)
    except KeyError:
        return None
    return (entry.pw_uid, entry.pw_gid, entry.pw_dir, entry.pw_shell)


def path_snapshot(path: Path) -> tuple[bool, int | None, int | None, int | None]:
    if not path.exists():
        return (False, None, None, None)
    stat = path.stat()
    return (True, stat.st_uid, stat.st_gid, stat.st_mode)


def test_rootless_check_mode_renders_and_reports_a_non_mutating_artifact_plan(tmp_path, absent_rootless_bind_source):
    host_user = f"podman-check-{os.getpid()}"
    runtime_root = tmp_path / "runtime"
    home = runtime_root / host_user
    quadlet_dir = home / ".config/containers/systemd"
    bind_source = absent_rootless_bind_source
    before = (account_snapshot(host_user), path_snapshot(home), path_snapshot(quadlet_dir))
    secret_sentinel = "PODMAN_CHECK_SECRET_SENTINEL_7f40b03e"
    runtime_marker = tmp_path / "runtime-command-called"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for command in ("podman", "systemctl", "systemd-analyze", "loginctl"):
        executable = fake_bin / command
        executable.write_text(f"#!/bin/sh\ntouch {runtime_marker}\nexit 99\n")
        executable.chmod(0o755)

    playbook = tmp_path / "rootless-check.yml"
    playbook.write_text(
        f"""---
- name: Rootless Podman check-mode regression
  hosts: localhost
  connection: local
  gather_facts: false
  become: false
  vars:
    podman_services_service_cfg:
      runtime: podman
      image: registry.example.invalid/adminer:5.4.2
      user: "0:0"
      environment:
        HOME: /application/home
        CHECK_SECRET: declaration-placeholder
      named_networks:
        check-mode:
          driver: bridge
          external: false
      ports:
        - published: 18081
          target: 8080
          protocol: tcp
      deploy:
        type: container
        host: localhost
        execution:
          mode: rootless
          host_user: {host_user}
          userns:
            mode: keep-id
            uid: "1000"
            gid: "1000"
      paths:
        - path: {bind_source}
          state: directory
          mode: "0750"
      volumes:
        config:
          type: bind
          source: {bind_source}
          target: /config
          read_only: false
    podman_services_role_prefix: rootless-check
    podman_services_rootless_home_root: {runtime_root}
    podman_services_execution_state_dir: {tmp_path / "state"}
    podman_services_system_quadlet_dir: {tmp_path / "system"}
    podman_services_common_context:
      runtime: podman
      dispatch_host: localhost
      controller_host: localhost
      lookup_values: {{}}
      resolved_environment:
        HOME: /application/home
        CHECK_SECRET: {secret_sentinel}
      secret_declarations: []
  tasks:
    - name: Include complete Podman role
      ansible.builtin.include_role:
        name: podman_services

    - name: Publish sanitized check artifact plan
      ansible.builtin.debug:
        msg: "{{{{ podman_services_check_artifact_plan }}}}"

    - name: Require secret-bearing check state is cleared
      ansible.builtin.assert:
        that:
          - podman_services_check_rendered_artifacts == []
          - podman_services_check_existing_artifacts == {{}}
"""
    )
    env = os.environ.copy()
    env.update(
        {
            "ANSIBLE_CONFIG": str(REPO_ROOT / "ansible/ansible.cfg"),
            "ANSIBLE_FILTER_PLUGINS": str(REPO_ROOT / "ansible/filter_plugins"),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
            "ANSIBLE_REMOTE_TEMP": str(tmp_path / "remote"),
            "ANSIBLE_NOCOLOR": "1",
            "ANSIBLE_STDOUT_CALLBACK": "ansible.posix.json",
            "PATH": f"{fake_bin}:{env.get('PATH', '')}",
        }
    )

    result = subprocess.run(
        [
            str(Path(sys.executable).with_name("ansible-playbook")),
            "-i",
            "localhost,",
            str(playbook),
            "--check",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    callback = json.loads(result.stdout)
    callback_text = json.dumps(callback, sort_keys=True)
    assert secret_sentinel not in result.stdout
    assert secret_sentinel not in result.stderr
    assert secret_sentinel not in callback_text
    task_results = {
        task["task"]["name"].split(" : ")[-1]: task["hosts"].get("localhost", {}) for play in callback["plays"] for task in play["tasks"]
    }
    assert (account_snapshot(host_user), path_snapshot(home), path_snapshot(quadlet_dir)) == before
    assert not bind_source.exists()
    assert not os.path.lexists(bind_source)
    assert not runtime_root.exists()
    assert not (tmp_path / "state").exists()
    assert not (tmp_path / "system").exists()
    assert not runtime_marker.exists()
    for task_name in (
        "Execution | Provision dedicated rootless account",
        "Execution | Enable rootless account linger",
        "Execution | Start rootless user manager",
        "Podman services | Reconcile rootless bind source ownership",
        "Prep | Render network Quadlet",
        "Prep | Render protected environment file",
        "Prep | Render container Quadlet",
        "Lifecycle | Validate user Quadlets with Podman generator dry run",
        "Lifecycle | Start user service for deploy/bootstrap",
        "Lifecycle | Persist successful execution owner",
    ):
        assert task_results[task_name]["skipped"] is True
    for task_name in (
        "Check render | Render managed network in memory",
        "Check render | Render protected environment in memory",
        "Check render | Render container in memory",
        "Check render | Validate in-memory artifact syntax",
    ):
        assert task_results[task_name].get("skipped", False) is False
        assert task_results[task_name].get("failed", False) is False
    assert task_results["Check render | Report planned artifact change"]["changed"] is True
    sanitized_plan = task_results["Publish sanitized check artifact plan"]["msg"]
    assert all(set(artifact) == {"kind", "path", "changed"} for artifact in sanitized_plan)
    assert {
        "kind": "environment",
        "path": str(quadlet_dir / "rootless-check.env"),
        "changed": True,
    } in sanitized_plan


def run_local_playbook(tmp_path, plays, *, check_mode=True, structured=False, extra_env=None):
    playbook = tmp_path / "behavior.yml"
    playbook.write_text(yaml.safe_dump(plays, sort_keys=False))
    env = os.environ.copy()
    env.update(
        {
            "ANSIBLE_CONFIG": str(REPO_ROOT / "ansible/ansible.cfg"),
            "ANSIBLE_FILTER_PLUGINS": str(REPO_ROOT / "ansible/filter_plugins"),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
            "ANSIBLE_REMOTE_TEMP": str(tmp_path / "remote"),
            "ANSIBLE_NOCOLOR": "1",
        }
    )
    if structured:
        env["ANSIBLE_STDOUT_CALLBACK"] = "ansible.posix.json"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [str(Path(sys.executable).with_name("ansible-playbook")), "-i", "localhost,", str(playbook), *(["--check"] if check_mode else [])],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_common_path_preparation_restricts_existing_bind_root_without_replacing_contents(tmp_path):
    bind_source = tmp_path / "thelounge"
    nested = bind_source / "users"
    nested.mkdir(parents=True)
    bind_source.chmod(0o755)
    credential_file = nested / "synthetic-user.json"
    credential_file.write_text("synthetic-non-secret\n")
    credential_file.chmod(0o640)
    source_inode = bind_source.stat().st_ino
    credential_inode = credential_file.stat().st_ino

    plays = [
        {
            "name": "Exercise rootless bind path preparation locally",
            "hosts": "localhost",
            "connection": "local",
            "gather_facts": False,
            "become": False,
            "vars": {
                "service_common_name": "thelounge",
                "service_common_paths": [
                    {
                        "path": str(bind_source),
                        "state": "directory",
                        "mode": "0750",
                    }
                ],
                "service_common_target_host": "localhost",
                "service_common_host_defaults": {"localhost": {}},
                "service_common_default_owner": str(os.getuid()),
                "service_common_default_group": str(os.getgid()),
                "service_common_default_mode": "0750",
            },
            "tasks": [
                {
                    "name": "Apply the service-common path contract",
                    "ansible.builtin.include_role": {
                        "name": "service_common",
                        "tasks_from": "paths",
                    },
                }
            ],
        }
    ]

    result = run_local_playbook(tmp_path, plays, check_mode=False)

    assert result.returncode == 0, result.stdout + result.stderr
    assert bind_source.stat().st_ino == source_inode
    assert stat.S_IMODE(bind_source.stat().st_mode) == 0o750
    assert credential_file.stat().st_ino == credential_inode
    assert credential_file.read_text() == "synthetic-non-secret\n"
    assert stat.S_IMODE(credential_file.stat().st_mode) == 0o640
    probe = bind_source / "write-probe"
    probe.write_text("writable\n")
    assert probe.read_text() == "writable\n"


@pytest.mark.parametrize(
    ("version", "supported"), [(None, True), (2, True), ("2", False), (True, False), (1, False), (3, False), ({}, False)]
)
def test_execution_state_version_contract_is_enforced_before_runtime_work(tmp_path, version, supported):
    state_dir = tmp_path / "state"
    quadlet_dir = tmp_path / "quadlets"
    runtime_marker = tmp_path / "runtime-command-called"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for command in ("podman", "systemctl"):
        executable = fake_bin / command
        executable.write_text(f"#!/bin/sh\ntouch {runtime_marker}\nexit 99\n")
        executable.chmod(0o755)
    state_dir.mkdir()
    quadlet_dir.mkdir()
    state = {
        "managed_by": "podman_services",
        "service": "synthetic",
        "mode": "rootful",
        "quadlet_dir": str(quadlet_dir),
        "unit_name": "synthetic.service",
    }
    if version is not None:
        state["version"] = version
    if version == 2 and not isinstance(version, bool):
        state["resources"] = {"network": {}, "volumes": [], "generated_files": []}
    state_path = state_dir / "synthetic.yml"
    state_path.write_text(yaml.safe_dump(state, sort_keys=False))
    state_before = state_path.read_text()
    quadlet_before = list(quadlet_dir.iterdir())
    result = run_local_playbook(
        tmp_path,
        [
            {
                "name": "Execution state version regression",
                "hosts": "localhost",
                "connection": "local",
                "gather_facts": False,
                "become": False,
                "vars": {
                    "podman_services_service_cfg": {
                        "runtime": "podman",
                        "image": "registry.example.invalid/synthetic:1.0",
                        "deploy": {"type": "container", "host": "localhost"},
                    },
                    "podman_services_role_prefix": "synthetic",
                    "podman_services_common_action": "remove",
                    "podman_services_state": "remove",
                    "podman_services_execution_state_dir": str(state_dir),
                    "podman_services_system_quadlet_dir": str(tmp_path / "system"),
                    "podman_services_common_context": {
                        "runtime": "podman",
                        "dispatch_host": "localhost",
                        "controller_host": "localhost",
                        "lookup_values": {},
                        "resolved_environment": {},
                        "secret_declarations": [],
                    },
                },
                "tasks": [
                    {
                        "name": "Include Podman initialization",
                        "ansible.builtin.include_role": {"name": "podman_services", "tasks_from": "sub_tasks/init"},
                    },
                    {
                        "name": "Include execution state validation",
                        "ansible.builtin.include_role": {"name": "podman_services", "tasks_from": "sub_tasks/execution_prepare"},
                    },
                    {
                        "name": "Include removal after validation",
                        "ansible.builtin.include_role": {"name": "podman_services", "tasks_from": "sub_tasks/remove"},
                    },
                ],
            }
        ],
        structured=True,
        extra_env={"PATH": f"{fake_bin}:{os.environ.get('PATH', '')}"},
    )
    callback = json.loads(result.stdout)
    task_names = [task["task"]["name"].split(" : ")[-1] for play in callback["plays"] for task in play["tasks"]]
    if supported:
        assert result.returncode == 0, result.stdout + result.stderr
        assert callback["stats"]["localhost"]["failures"] == 0
        assert "Include removal after validation" in task_names
        assert any(name.startswith("Remove |") for name in task_names)
    else:
        assert result.returncode != 0
        assert "versionless legacy state or explicit integer version 2" in result.stdout
        assert "Include removal after validation" not in task_names
        assert not any(name.startswith("Remove |") for name in task_names)
    assert not runtime_marker.exists()
    assert state_path.read_text() == state_before
    assert list(quadlet_dir.iterdir()) == quadlet_before


@pytest.mark.parametrize("mode", ["rootful", "rootless"])
@pytest.mark.parametrize("marked", [True, False])
def test_removal_requires_managed_marker_for_existing_rootful_and_rootless_files(tmp_path, mode, marked):
    state_dir = tmp_path / "state"
    quadlet_dir = tmp_path / mode
    state_dir.mkdir()
    quadlet_dir.mkdir()
    generated = quadlet_dir / "synthetic.container"
    generated.write_text("# Generated by Ansible. Do not edit manually.\n[Container]\n" if marked else "[Container]\nImage=synthetic\n")
    state = {
        "version": 2,
        "managed_by": "podman_services",
        "service": "synthetic",
        "mode": mode,
        "quadlet_dir": str(quadlet_dir),
        "unit_name": "synthetic.service",
        "resources": {"network": {}, "volumes": [], "generated_files": [str(generated)]},
    }
    if mode == "rootless":
        state.update({"host_user": "podman-synthetic", "home": str(tmp_path / "home"), "uid": "2001", "gid": "2001"})
    state_path = state_dir / "synthetic.yml"
    state_path.write_text(yaml.safe_dump(state, sort_keys=False))
    result = run_local_playbook(
        tmp_path,
        [
            {
                "name": "Managed marker removal regression",
                "hosts": "localhost",
                "connection": "local",
                "gather_facts": False,
                "become": False,
                "vars": {
                    "podman_services_service_cfg": {
                        "runtime": "podman",
                        "image": "registry.example.invalid/synthetic:1.0",
                        "deploy": {"type": "container", "host": "localhost"},
                    },
                    "podman_services_role_prefix": "synthetic",
                    "podman_services_common_action": "remove",
                    "podman_services_state": "remove",
                    "podman_services_execution_state_dir": str(state_dir),
                    "podman_services_system_quadlet_dir": str(tmp_path / "system"),
                    "podman_services_common_context": {
                        "runtime": "podman",
                        "dispatch_host": "localhost",
                        "controller_host": "localhost",
                        "lookup_values": {},
                        "resolved_environment": {},
                        "secret_declarations": [],
                    },
                },
                "tasks": [
                    {
                        "name": "Include Podman initialization",
                        "ansible.builtin.include_role": {"name": "podman_services", "tasks_from": "sub_tasks/init"},
                    },
                    {
                        "name": "Include execution ownership selection",
                        "ansible.builtin.include_role": {"name": "podman_services", "tasks_from": "sub_tasks/execution_prepare"},
                    },
                    {
                        "name": "Include safe removal",
                        "ansible.builtin.include_role": {"name": "podman_services", "tasks_from": "sub_tasks/remove"},
                    },
                ],
            }
        ],
    )
    assert (result.returncode == 0) is marked, result.stdout + result.stderr
    assert generated.exists()
    assert state_path.exists()


def test_versionless_cleanup_ignores_unproven_resource_metadata_but_version_two_uses_it(tmp_path):
    for version in (None, 2):
        case_dir = tmp_path / ("legacy" if version is None else "v2")
        state_dir = case_dir / "state"
        quadlet_dir = case_dir / "quadlets"
        state_dir.mkdir(parents=True)
        quadlet_dir.mkdir()
        fallback = [quadlet_dir / "synthetic.container", quadlet_dir / "synthetic.env"]
        resource_files = [quadlet_dir / "synthetic.network", quadlet_dir / "synthetic.volume"]
        for path in fallback + resource_files:
            path.write_text("# Generated by Ansible. Do not edit manually.\n")
        state = {
            "managed_by": "podman_services",
            "service": "synthetic",
            "mode": "rootful",
            "quadlet_dir": str(quadlet_dir),
            "unit_name": "synthetic.service",
            "resources": {
                "network": {"name": "synthetic", "managed": True},
                "volumes": [{"name": "synthetic"}],
                "generated_files": [str(path) for path in fallback + resource_files],
            },
        }
        if version is not None:
            state["version"] = version
        state_path = state_dir / "synthetic.yml"
        state_path.write_text(yaml.safe_dump(state, sort_keys=False))
        expected_paths = [str(path) for path in (fallback + resource_files if version == 2 else fallback)]
        expected_network = state["resources"]["network"] if version == 2 else {}
        result = run_local_playbook(
            case_dir,
            [
                {
                    "name": "Version-aware cleanup regression",
                    "hosts": "localhost",
                    "connection": "local",
                    "gather_facts": False,
                    "become": False,
                    "vars": {
                        "podman_services_service_cfg": {
                            "runtime": "podman",
                            "image": "registry.example.invalid/synthetic:1.0",
                            "deploy": {"type": "container", "host": "localhost"},
                        },
                        "podman_services_role_prefix": "synthetic",
                        "podman_services_common_action": "remove",
                        "podman_services_state": "remove",
                        "podman_services_execution_state_dir": str(state_dir),
                        "podman_services_system_quadlet_dir": str(case_dir / "system"),
                        "podman_services_common_context": {
                            "runtime": "podman",
                            "dispatch_host": "localhost",
                            "controller_host": "localhost",
                            "lookup_values": {},
                            "resolved_environment": {},
                            "secret_declarations": [],
                        },
                        "expected_paths": expected_paths,
                        "expected_network": expected_network,
                    },
                    "tasks": [
                        {
                            "name": "Include Podman initialization",
                            "ansible.builtin.include_role": {"name": "podman_services", "tasks_from": "sub_tasks/init"},
                        },
                        {
                            "name": "Include execution ownership selection",
                            "ansible.builtin.include_role": {"name": "podman_services", "tasks_from": "sub_tasks/execution_prepare"},
                        },
                        {
                            "name": "Include version-aware removal",
                            "ansible.builtin.include_role": {"name": "podman_services", "tasks_from": "sub_tasks/remove"},
                        },
                        {
                            "name": "Assert conservative cleanup ownership",
                            "ansible.builtin.assert": {
                                "that": [
                                    "podman_services_remove_generated_paths == expected_paths",
                                    "podman_services_remove_network == expected_network",
                                ]
                            },
                        },
                    ],
                }
            ],
        )
        assert result.returncode == 0, result.stdout + result.stderr
        if version is None:
            assert "Versionless execution state proves ownership" in result.stdout
        else:
            assert "Versionless execution state proves ownership" not in result.stdout
        assert state_path.exists()
        assert all(path.exists() for path in fallback + resource_files)


@pytest.mark.parametrize(
    ("action", "desired_mode", "persisted_mode", "legacy_rootful", "expected_mode", "expected_user", "check_mode"),
    [
        ("remove", "rootful", "rootless", False, "rootless", "podman-synthetic", True),
        ("remove", "rootless", "rootful", False, "rootful", "", True),
        ("drift", "rootless", "rootful", False, "rootful", "", True),
        ("drift", "rootful", "rootless", False, "rootless", "podman-synthetic", True),
        ("drift", "rootless", None, True, "rootful", "", True),
        ("drift", "rootful", None, False, "none", "", False),
        ("remove", "rootless", None, True, "rootful", "", True),
    ],
)
def test_remove_and_drift_materialize_the_persisted_active_owner(
    tmp_path,
    action,
    desired_mode,
    persisted_mode,
    legacy_rootful,
    expected_mode,
    expected_user,
    check_mode,
):
    state_dir = tmp_path / "state"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    podman_marker = tmp_path / "podman-called"
    fake_podman = fake_bin / "podman"
    fake_podman.write_text(f"#!/bin/sh\ntouch {podman_marker}\nexit 125\n")
    fake_podman.chmod(0o755)
    system_quadlet_dir = tmp_path / "system-quadlets"
    state_dir.mkdir()
    system_quadlet_dir.mkdir()
    if persisted_mode:
        state = {
            "managed_by": "podman_services",
            "service": "synthetic",
            "mode": persisted_mode,
        }
        if persisted_mode == "rootless":
            state.update(
                {
                    "host_user": "podman-synthetic",
                    "home": "/var/lib/podman-synthetic",
                    "uid": "2001",
                    "gid": "2001",
                }
            )
        (state_dir / "synthetic.yml").write_text(yaml.safe_dump(state, sort_keys=False))
    if legacy_rootful:
        (system_quadlet_dir / "synthetic.container").write_text("# Generated by Ansible. Do not edit manually.\n")

    execution = {"mode": desired_mode}
    service = {
        "runtime": "podman",
        "name": "synthetic",
        "image": "registry.example.invalid/synthetic:1.0",
        "deploy": {"type": "container", "host": "localhost", "execution": execution},
    }
    if desired_mode == "rootless":
        execution["host_user"] = "podman-synthetic"
        service["named_networks"] = {"synthetic": {"driver": "bridge", "external": False}}
        service["ports"] = [{"published": 18082, "target": 8080, "protocol": "tcp"}]

    expected_quadlet_dir = (
        Path("/var/lib/podman-synthetic/.config/containers/systemd") if expected_mode == "rootless" else system_quadlet_dir
    )
    playbook = tmp_path / f"active-owner-{action}-{desired_mode}-{persisted_mode or ('legacy' if legacy_rootful else 'none')}.yml"
    playbook.write_text(
        yaml.safe_dump(
            [
                {
                    "name": "Active Podman owner regression",
                    "hosts": "localhost",
                    "connection": "local",
                    "gather_facts": False,
                    "become": False,
                    "vars": {
                        "podman_services_service_cfg": service,
                        "podman_services_role_prefix": "synthetic",
                        "podman_services_common_action": action,
                        "podman_services_state": action,
                        "podman_services_execution_state_dir": str(state_dir),
                        "podman_services_system_quadlet_dir": str(system_quadlet_dir),
                        "podman_services_common_context": {
                            "runtime": "podman",
                            "dispatch_host": "localhost",
                            "controller_host": "localhost",
                            "lookup_values": {},
                            "resolved_environment": {},
                            "secret_declarations": [],
                        },
                    },
                    "tasks": [
                        {
                            "name": "Include Podman initialization",
                            "ansible.builtin.include_role": {
                                "name": "podman_services",
                                "tasks_from": "sub_tasks/init",
                            },
                        },
                        {
                            "name": "Include execution ownership selection",
                            "ansible.builtin.include_role": {
                                "name": "podman_services",
                                "tasks_from": "sub_tasks/execution_prepare",
                            },
                        },
                        {
                            "name": "Assert active owner selection",
                            "ansible.builtin.assert": {
                                "that": [
                                    f"podman_services_active_execution.mode == '{expected_mode}'",
                                    f"podman_services_execution.mode == '{expected_mode}'",
                                    f"podman_services_quadlet_dir == '{expected_quadlet_dir}'",
                                    (
                                        f"podman_services_execution.host_user == '{expected_user}'"
                                        if expected_user
                                        else "podman_services_execution.host_user is not defined"
                                    ),
                                ]
                            },
                        },
                        {
                            "name": "Include drift classification",
                            "when": "podman_services_common_action == 'drift'",
                            "ansible.builtin.include_role": {
                                "name": "podman_services",
                                "tasks_from": "sub_tasks/drift",
                            },
                        },
                        {
                            "name": "Assert deterministic missing drift",
                            "when": "podman_services_common_action == 'drift'",
                            "ansible.builtin.assert": {
                                "that": [
                                    "podman_services_image_reference_drift.drift | bool",
                                    "podman_services_image_reference_drift.missing | bool",
                                ]
                            },
                        },
                    ],
                }
            ],
            sort_keys=False,
        )
    )
    env = os.environ.copy()
    env.update(
        {
            "ANSIBLE_CONFIG": str(REPO_ROOT / "ansible/ansible.cfg"),
            "ANSIBLE_FILTER_PLUGINS": str(REPO_ROOT / "ansible/filter_plugins"),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
            "ANSIBLE_REMOTE_TEMP": str(tmp_path / "remote"),
            "ANSIBLE_NOCOLOR": "1",
            "PATH": f"{fake_bin}:{env['PATH']}",
        }
    )

    result = subprocess.run(
        [
            str(Path(sys.executable).with_name("ansible-playbook")),
            "-i",
            "localhost,",
            str(playbook),
            *(["--check"] if check_mode else []),
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "failed=0" in result.stdout
    assert not podman_marker.exists()


def test_drift_uses_the_persisted_rootless_owner_runtime_environment(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    observed = tmp_path / "observed-environment"
    fake_podman = fake_bin / "podman"
    fake_podman.write_text(
        "#!/bin/sh\n"
        f'printf "%s\n%s\n%s\n" "$HOME" "$XDG_RUNTIME_DIR" "$DBUS_SESSION_BUS_ADDRESS" > {observed}\n'
        'printf "registry.example.invalid/synthetic:1.0\n"\n'
    )
    fake_podman.chmod(0o755)
    current_user = pwd.getpwuid(os.getuid()).pw_name
    expected = ["/synthetic/persisted-home", "/synthetic/runtime", "unix:path=/synthetic/runtime/bus"]
    runtime_environment = {
        "HOME": expected[0],
        "XDG_RUNTIME_DIR": expected[1],
        "DBUS_SESSION_BUS_ADDRESS": expected[2],
        "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
    }
    playbook = tmp_path / "drift-active-owner.yml"
    playbook.write_text(
        yaml.safe_dump(
            [
                {
                    "name": "Persisted rootless drift owner regression",
                    "hosts": "localhost",
                    "connection": "local",
                    "gather_facts": False,
                    "become": False,
                    "vars": {
                        "podman_services_state": "drift",
                        "podman_services_service": {
                            "name": "synthetic",
                            "unit_name": "synthetic",
                            "image": "registry.example.invalid/synthetic:1.0",
                        },
                        "podman_services_active_execution": {
                            "mode": "rootless",
                            "host_user": current_user,
                        },
                        "podman_services_runtime_environment": runtime_environment,
                    },
                    "tasks": [
                        {
                            "name": "Include drift classification",
                            "ansible.builtin.include_role": {
                                "name": "podman_services",
                                "tasks_from": "sub_tasks/drift",
                            },
                        },
                        {
                            "name": "Require no image drift",
                            "ansible.builtin.assert": {"that": ["not podman_services_image_reference_drift.drift | bool"]},
                        },
                    ],
                }
            ],
            sort_keys=False,
        )
    )
    env = os.environ.copy()
    env.update(
        {
            "ANSIBLE_CONFIG": str(REPO_ROOT / "ansible/ansible.cfg"),
            "ANSIBLE_FILTER_PLUGINS": str(REPO_ROOT / "ansible/filter_plugins"),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
            "ANSIBLE_REMOTE_TEMP": str(tmp_path / "remote"),
            "ANSIBLE_NOCOLOR": "1",
        }
    )
    result = subprocess.run(
        [str(Path(sys.executable).with_name("ansible-playbook")), "-i", "localhost,", str(playbook)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert observed.read_text().splitlines() == expected
