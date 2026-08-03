from __future__ import annotations

import os
import pwd
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


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


def test_rootless_check_mode_validates_without_account_quadlet_systemd_or_podman_mutation(tmp_path):
    host_user = "podman-check-mode"
    home = Path("/var/lib") / host_user
    quadlet_dir = home / ".config/containers/systemd"
    before = (account_snapshot(host_user), path_snapshot(home), path_snapshot(quadlet_dir))
    playbook = tmp_path / "rootless-check.yml"
    playbook.write_text(
        """---
- name: Rootless Podman check-mode regression
  hosts: localhost
  connection: local
  gather_facts: false
  become: false
  vars:
    podman_services_service_cfg:
      runtime: podman
      image: registry.example.invalid/adminer:5.4.2
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
          host_user: podman-check-mode
    podman_services_role_prefix: rootless-check
    podman_services_common_context:
      runtime: podman
      dispatch_host: localhost
      controller_host: localhost
      lookup_values: {}
      resolved_environment: {}
      secret_declarations: []
  tasks:
    - name: Include Podman initialization only
      ansible.builtin.include_role:
        name: podman_services
        tasks_from: sub_tasks/init

    - name: Include rootless execution preparation only
      ansible.builtin.include_role:
        name: podman_services
        tasks_from: sub_tasks/execution_prepare

    - name: Include rootless Quadlet preparation only
      ansible.builtin.include_role:
        name: podman_services
        tasks_from: sub_tasks/prepare
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
    assert "failed=0" in result.stdout
    assert (account_snapshot(host_user), path_snapshot(home), path_snapshot(quadlet_dir)) == before
    assert "Provision dedicated rootless account" in result.stdout
    assert "Enable rootless account linger" in result.stdout
    assert "Start rootless user manager" in result.stdout
    assert "Render container Quadlet" in result.stdout
    assert "changed=0" in result.stdout


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
