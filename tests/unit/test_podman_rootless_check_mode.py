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


@pytest.mark.integration
@pytest.mark.parametrize("direct_pasta", [False, True])
def test_rootless_check_mode_renders_and_reports_a_non_mutating_artifact_plan(tmp_path, absent_rootless_bind_source, direct_pasta):
    host_user = f"podman-check-{os.getpid()}"
    runtime_root = tmp_path / "runtime"
    home = runtime_root / host_user
    quadlet_dir = home / ".config/containers/systemd"
    network_dropin = home / ".config/containers/containers.conf.d/20-podman-services-network.conf"
    bind_source = absent_rootless_bind_source
    before = (account_snapshot(host_user), path_snapshot(home), path_snapshot(quadlet_dir), path_snapshot(network_dropin))
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
      image: registry.example.invalid/adminer:1.2.3
      user: "0:0"
      environment:
        HOME: /application/home
        CHECK_SECRET: declaration-placeholder
      infisical:
        secrets_map:
          - var: file_value
            path: /Synthetic
            name: FILE_VALUE
            secret:
              name: check_file_secret
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
        hosts: localhost
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
        - path: {bind_source}/docker.yaml
          state: absent
        - path: {bind_source}/.env
          state: absent
      copies:
        - src: files/earth-rise-2.jpg
          dest: {bind_source}/background.jpg
          mode: "0644"
      templates:
        - src: configs/homepage/custom.css.j2
          dest: {bind_source}/custom.css
          mode: "0664"
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
      lookup_values:
        file_value: {secret_sentinel}
      resolved_environment:
        HOME: /application/home
        CHECK_SECRET: {secret_sentinel}
      secret_declarations:
        - name: check_file_secret
          var: file_value
          target: /run/secrets/check_file_secret
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

    if direct_pasta:
        plays = yaml.safe_load(playbook.read_text())
        service = plays[0]["vars"]["podman_services_service_cfg"]
        del service["named_networks"]
        service["network_mode"] = "pasta"
        playbook.write_text(yaml.safe_dump(plays, sort_keys=False))
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
    task_results = [task["hosts"].get("localhost", {}) for play in callback["plays"] for task in play["tasks"]]
    assert (account_snapshot(host_user), path_snapshot(home), path_snapshot(quadlet_dir), path_snapshot(network_dropin)) == before
    assert not bind_source.exists()
    assert not os.path.lexists(bind_source)
    assert not runtime_root.exists()
    assert not (tmp_path / "state").exists()
    assert not (tmp_path / "system").exists()
    assert not runtime_marker.exists()
    # Observe plans and unchanged state, not which individual tasks emitted
    # them. Runtime-command sentinels above still fail on an attempted mutation.
    assert not any(task.get("failed", False) for task in task_results)
    assert any(task.get("changed") and str(network_dropin) in str(task.get("msg", "")) for task in task_results)
    sanitized_plan = next(
        task["msg"]
        for task in task_results
        if isinstance(task.get("msg"), list)
        and task["msg"]
        and all(isinstance(artifact, dict) and "kind" in artifact for artifact in task["msg"])
    )
    expected_kinds = {"container", "environment"} | (set() if direct_pasta else {"network"})
    assert {artifact["kind"] for artifact in sanitized_plan} == expected_kinds
    assert all(set(artifact) == {"kind", "path", "changed", "comparison_available"} for artifact in sanitized_plan)
    assert {
        "kind": "environment",
        "path": str(quadlet_dir / "rootless-check.env"),
        "changed": True,
        "comparison_available": False,
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


@pytest.mark.integration
def test_execution_only_preparation_returns_before_service_work(tmp_path):
    account = f"podman-check-{os.getpid()}"
    before = account_snapshot(account)
    runtime_marker = tmp_path / "runtime-command-called"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for command in ("podman", "systemctl", "loginctl"):
        executable = fake_bin / command
        executable.write_text(f"#!/bin/sh\ntouch {runtime_marker}\nexit 99\n")
        executable.chmod(0o755)
    play = {
        "hosts": "localhost",
        "connection": "local",
        "gather_facts": False,
        "vars": {
            "podman_services_prepare_execution_only": True,
            "podman_services_rootless_home_root": str(tmp_path / "homes"),
            "podman_services_execution_state_dir": str(tmp_path / "state"),
            "podman_services_system_quadlet_dir": str(tmp_path / "system"),
            "podman_services_common_context": {
                "runtime": "podman",
                "dispatch_host": "localhost",
                "controller_host": "localhost",
                "lookup_values": {},
                "resolved_environment": {},
                "secret_declarations": [],
            },
            "podman_services_service_cfg": {
                "runtime": "podman",
                "operational_requirements": {"acl": ["mgt_backends"], "ownership_transition": True},
                "image": "registry.example.invalid/test:1",
                "deploy": {"type": "container", "hosts": "localhost", "execution": {"mode": "rootless", "host_user": account}},
                "named_networks": {"account-check": {"external": False}},
            },
            "podman_services_role_prefix": "account-check",
        },
        "tasks": [
            {"ansible.builtin.include_role": {"name": "podman_services"}},
            {"name": "Continue after execution-only role", "ansible.builtin.debug": {"msg": "account-plan-finished"}},
        ],
    }
    result = run_local_playbook(tmp_path, [play], structured=True, extra_env={"PATH": f"{fake_bin}:{os.environ.get('PATH', '')}"})
    assert result.returncode == 0, result.stdout + result.stderr
    callback = json.loads(result.stdout)
    results = [task["hosts"].get("localhost", {}) for entry in callback["plays"] for task in entry["tasks"]]
    assert any(task.get("msg") == "account-plan-finished" for task in results)
    # The prerequisites still run; application files and runtime commands do not.
    assert any(
        "/service_common/tasks/operational_requirements.yml:" in task["task"].get("path", "")
        for entry in callback["plays"]
        for task in entry["tasks"]
    )
    assert account_snapshot(account) == before
    assert not runtime_marker.exists()
    assert not (tmp_path / "homes").exists()
    assert not (tmp_path / "state").exists()


@pytest.mark.integration
def test_reconciled_secret_restart_depends_on_material_change(tmp_path):
    case_tasks = tmp_path / "restart-case.yml"
    case_tasks.write_text(
        yaml.safe_dump(
            [
                {"ansible.builtin.include_role": {"name": "podman_services", "tasks_from": "sub_tasks/image"}},
                {"ansible.builtin.assert": {"that": ["podman_services_requires_restart == restart_case.expected"]}},
            ]
        )
    )
    result = run_local_playbook(
        tmp_path,
        [
            {
                "hosts": "localhost",
                "connection": "local",
                "gather_facts": False,
                "vars": {
                    "podman_services_state": "{{ restart_case.operation }}",
                    "podman_services_service": {"secrets": [{"update_policy": "reconcile"}]},
                    "podman_services_container_quadlet": {"changed": False},
                    "podman_services_env_file": {"changed": False},
                    "podman_services_network_quadlet": {"changed": False},
                    "podman_services_volume_quadlets": {"changed": False},
                    "podman_services_secret_results": {"results": [{"changed": "{{ restart_case.changed }}"}]},
                    "podman_services_config_changed": "{{ restart_case.config_changed | default(false) }}",
                },
                "tasks": [
                    {
                        "ansible.builtin.include_tasks": str(case_tasks),
                        "loop": [
                            {"operation": "update", "changed": False, "expected": False},
                            {"operation": "update", "changed": True, "expected": True},
                            {"operation": "recreate", "changed": False, "expected": True},
                            {"operation": "update", "changed": False, "config_changed": True, "expected": True},
                        ],
                        "loop_control": {"loop_var": "restart_case"},
                    }
                ],
            }
        ],
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.integration
@pytest.mark.parametrize(
    ("field", "destination"),
    [
        ("templates", "/etc/rootless-check/settings.yml"),
        ("copies", "/opt/rootless-check-evil/background.jpg"),
    ],
)
def test_rootless_check_mode_rejects_managed_files_outside_the_bind_tree(tmp_path, field, destination):
    bind_source = "/opt/rootless-check-owned"
    service = {
        "runtime": "podman",
        "image": "registry.example.invalid/synthetic:1.0",
        "named_networks": {"synthetic": {"driver": "bridge", "external": False}},
        "ports": [{"published": 18081, "target": 8080, "protocol": "tcp"}],
        "deploy": {
            "type": "container",
            "hosts": "localhost",
            "execution": {
                "mode": "rootless",
                "host_user": "podman-check-invalid",
                "userns": {"mode": "keep-id", "uid": "1000", "gid": "1000"},
            },
        },
        "paths": [{"path": bind_source, "state": "directory", "mode": "0750"}],
        "volumes": {
            "config": {
                "type": "bind",
                "source": bind_source,
                "target": "/config",
                "read_only": False,
            }
        },
        field: [{"src": "synthetic", "dest": destination}],
    }
    result = run_local_playbook(
        tmp_path,
        [
            {
                "name": "Reject unsafe rootless managed file in check mode",
                "hosts": "localhost",
                "connection": "local",
                "gather_facts": False,
                "become": False,
                "vars": {
                    "podman_services_service_cfg": service,
                    "podman_services_role_prefix": "synthetic",
                    "podman_services_common_context": {
                        "runtime": "podman",
                        "dispatch_host": "localhost",
                        "controller_host": "localhost",
                        "lookup_values": {},
                        "resolved_environment": {},
                        "secret_declarations": [],
                    },
                },
                "tasks": [{"name": "Include complete Podman role", "ansible.builtin.include_role": {"name": "podman_services"}}],
            }
        ],
    )

    assert result.returncode != 0
    assert f"{field}[0].dest" in result.stdout
    assert "declared rootless bind source" in result.stdout


@pytest.mark.integration
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


@pytest.mark.integration
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
                        "deploy": {"type": "container", "hosts": "localhost"},
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
                        "ansible.builtin.include_role": {"name": "podman_services", "tasks_from": "sub_tasks/execution"},
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
    # File ownership identifies the adapter boundary regardless of task names.
    removal_reached = any(
        "/podman_services/tasks/sub_tasks/remove.yml:" in task["task"].get("path", "")
        for play in callback["plays"]
        for task in play["tasks"]
    )
    if supported:
        assert result.returncode == 0, result.stdout + result.stderr
        assert callback["stats"]["localhost"]["failures"] == 0
        assert removal_reached
    else:
        assert result.returncode != 0
        assert "versionless legacy state or explicit integer version 2" in result.stdout
        assert not removal_reached
    assert not runtime_marker.exists()
    assert state_path.read_text() == state_before
    assert list(quadlet_dir.iterdir()) == quadlet_before


@pytest.mark.integration
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
                        "deploy": {"type": "container", "hosts": "localhost"},
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
                        "ansible.builtin.include_role": {"name": "podman_services", "tasks_from": "sub_tasks/execution"},
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


@pytest.mark.integration
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
                            "deploy": {"type": "container", "hosts": "localhost"},
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
                            "ansible.builtin.include_role": {"name": "podman_services", "tasks_from": "sub_tasks/execution"},
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


@pytest.mark.integration
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
        "deploy": {"type": "container", "hosts": "localhost", "execution": execution},
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
                                "tasks_from": "sub_tasks/execution",
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
                                "tasks_from": "sub_tasks/image_drift",
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


@pytest.mark.integration
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
                                "tasks_from": "sub_tasks/image_drift",
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


@pytest.mark.integration
@pytest.mark.parametrize("check_mode", [True, False])
def test_netbox_account_only_preparation_never_resolves_bootstrap_credentials(tmp_path, check_mode):
    """Exercise the real bootstrap tasks with deliberately unavailable values."""
    play = {
        "hosts": "localhost",
        "connection": "local",
        "gather_facts": False,
        "vars": {
            "netbox_domain": "example.test",
            "local_ip": "192.0.2.48",
            "podman_services_prepare_execution_only": True,
            "podman_services_rootless_home_root": str(tmp_path / "homes"),
            "podman_services_execution_state_dir": str(tmp_path / "state"),
            "netbox_required_docker_secrets": "{{ credential_source_must_not_be_resolved }}",
            "netbox_podman_services": [
                {
                    "runtime": "podman",
                    "name": "netbox-fixture",
                    "image": "fixture.invalid/netbox:1",
                    "user": "0:0",
                    "environment": {},
                    "secrets": ["unavailable_secret"],
                    "named_networks": {"netbox-fixture": {"external": False}},
                    "operational_requirements": {"acl": ["bootstrap"], "ownership_transition": True},
                    "deploy": {
                        "type": "container",
                        "hosts": "localhost",
                        "execution": {"mode": "rootless", "host_user": "podman-check-netbox"},
                    },
                }
            ],
        },
        "tasks": [
            {"ansible.builtin.include_role": {"name": "netbox"}, "tags": ["netbox_deploy"]},
            {"ansible.builtin.debug": {"msg": "credential-free-account-plan-finished"}},
        ],
    }
    extra_env = {}
    if not check_mode:
        # Execute real bootstrap orchestration in live mode, but replace only
        # the mutating runtime adapter with a local assertion-only role.
        roles = tmp_path / "roles"
        tasks = roles / "podman_services/tasks"
        tasks.mkdir(parents=True)
        (tasks / "validate_definitions.yml").write_text("[]\n")
        (tasks / "main.yml").write_text(
            yaml.safe_dump(
                [
                    {
                        "ansible.builtin.assert": {
                            "that": [
                                "podman_services_prepare_execution_only is sameas true",
                                "podman_services_common_context.lookup_values == {}",
                                "podman_services_common_context.secret_declarations == []",
                                "podman_services_common_context.resolved_environment == {}",
                            ]
                        }
                    },
                    {"ansible.builtin.debug": {"msg": "credential-free-account-adapter-reached"}},
                ]
            )
        )
        extra_env["ANSIBLE_ROLES_PATH"] = str(roles) + ":" + str(REPO_ROOT / "ansible/roles")
    result = run_local_playbook(tmp_path, [play], structured=True, check_mode=check_mode, extra_env=extra_env)
    assert result.returncode == 0, result.stdout + result.stderr
    # The credential-free adapter sentinel and filesystem checks establish the
    # account-only result; task names/prefixes do not define that boundary.
    if not check_mode:
        callback = json.loads(result.stdout)
        assert any(
            str(roles / "podman_services/tasks/main.yml") in task["task"].get("path", "")
            for entry in callback["plays"]
            for task in entry["tasks"]
        )
    assert not (tmp_path / "homes").exists() and not (tmp_path / "state").exists()


@pytest.mark.integration
@pytest.mark.parametrize(
    "mode,scenario",
    [
        ("rootful", "success"),
        ("rootless", "success"),
        ("rootless", "delete-failure"),
        ("rootful", "marker"),
        ("rootless", "unowned"),
        ("rootless", "symlink"),
        ("rootless", "check"),
    ],
)
def test_empty_environment_retires_owned_secret_before_state_update_and_remove(tmp_path, mode, scenario):
    import copy
    import grp

    tasks_root = REPO_ROOT / "ansible/roles/podman_services/tasks/sub_tasks"
    quadlets = yaml.safe_load((tasks_root / "quadlets.yml").read_text())
    retire = next(task for task in quadlets if "Retire the managed environment file" in task.get("name", ""))
    lifecycle = yaml.safe_load((tasks_root / "service_state.yml").read_text())
    record = next(task for task in lifecycle if task.get("name") == "Service | Record managed resources after successful start")
    save = copy.deepcopy(next(task for task in lifecycle if task.get("name") == "Service | Save successful execution state"))
    # Only OS ownership is adapted to the unprivileged fixture account.
    owner, group = pwd.getpwuid(os.getuid()).pw_name, grp.getgrgid(os.getgid()).gr_name
    save["ansible.builtin.copy"].update(owner=owner, group=group)
    directory = tmp_path / "quadlets"
    directory.mkdir()
    env_file, container = directory / "synthetic.env", directory / "synthetic.container"
    marker = "# Generated by Ansible. Do not edit manually.\n"
    env_file.write_text((marker if scenario != "marker" else "# Unmanaged\n") + "PASSWORD=NONPRODUCTION_VALUE\n")
    env_file.chmod(0o600)
    if scenario == "symlink":
        outside = tmp_path / "outside.env"
        env_file.rename(outside)
        env_file.symlink_to(outside)
    container.write_text(marker + "[Container]\n")
    state_path = tmp_path / "synthetic.yml"
    state = {
        "version": 2,
        "managed_by": "podman_services",
        "service": "synthetic",
        "mode": mode,
        "unit_name": "synthetic.service",
        "quadlet_dir": str(directory),
        "resources": {"network": {}, "volumes": [], "generated_files": [str(container), str(env_file)]},
    }
    if mode == "rootless":
        state.update(host_user="podman-synthetic", home=str(tmp_path), uid=str(os.getuid()), gid=str(os.getgid()))
    if scenario == "unowned":
        state["resources"]["generated_files"].remove(str(env_file))
    state_path.write_text(yaml.safe_dump(state))
    before = state_path.read_bytes()
    variables = {
        "podman_services_state": "update",
        "podman_services_service": {"name": "synthetic", "unit_name": "synthetic", "env": {}, "network": None, "volumes": []},
        "podman_services_unit_name": "synthetic.service",
        "podman_services_quadlet_dir": str(directory),
        "podman_services_execution": {"mode": mode, "host_user": "podman-synthetic"},
        "podman_services_active_execution": state,
        "podman_services_execution_owner": owner,
        "podman_services_execution_group": group,
        "podman_services_execution_state_path": str(state_path),
        "podman_services_execution_home": str(tmp_path),
        "podman_services_execution_uid": str(os.getuid()),
        "podman_services_execution_gid": str(os.getgid()),
    }
    cfg = tmp_path / "ansible.cfg"
    cfg.write_text("[defaults]\nvars_plugins_enabled=\nstdout_callback=default\n")
    plays = [
        {
            "hosts": "localhost",
            "connection": "local",
            "gather_facts": False,
            "become": False,
            "vars": variables,
            "tasks": [copy.deepcopy(retire), record, save],
            "handlers": [{"name": "Podman services | daemon reload", "ansible.builtin.debug": {"msg": "NONPRODUCTION reload boundary"}}],
        }
    ]
    if scenario == "delete-failure":
        deletion = plays[0]["tasks"][0]["block"][-1]
        deletion.pop("ansible.builtin.file")
        deletion["ansible.builtin.fail"] = {"msg": "NONPRODUCTION unlink failure"}

    def execute():
        return run_local_playbook(tmp_path, plays, check_mode=scenario == "check", extra_env={"ANSIBLE_CONFIG": str(cfg)})

    result = execute()
    assert "NONPRODUCTION_VALUE" not in result.stdout + result.stderr
    if scenario in {"marker", "unowned", "symlink", "delete-failure"}:
        assert result.returncode != 0, result.stdout + result.stderr
        assert env_file.exists() and state_path.read_bytes() == before
        if scenario != "delete-failure":
            return
        plays[0]["tasks"][0] = copy.deepcopy(retire)
        result = execute()
    assert result.returncode == 0, result.stdout + result.stderr
    if scenario == "check":
        assert env_file.exists() and state_path.read_bytes() == before
        return
    assert not env_file.exists()
    saved = yaml.safe_load(state_path.read_text())
    assert saved["resources"]["generated_files"] == [str(container)]
    plays[0]["vars"]["podman_services_active_execution"] = saved
    repeated = execute()
    assert repeated.returncode == 0 and "changed=0" in repeated.stdout, repeated.stdout + repeated.stderr
    # Subsequent remove consumes the actual saved resource list; no orphaned
    # protected file or forgotten ownership remains.
    removes = yaml.safe_load((tasks_root / "remove.yml").read_text())
    keep = {
        "Remove | Load saved resources for removal",
        "Remove | Validate saved resources before removal",
        "Remove | Check saved generated files",
        "Remove | Read existing managed generated files",
        "Remove | Verify files are Ansible-managed before deletion",
        "Remove | Remove saved generated files",
        "Remove | Remove saved execution state",
    }
    plays[0]["tasks"] = [task for task in removes if task["name"] in keep]
    plays[0]["vars"].update(podman_services_state="remove", podman_services_execution_state_stat={"stat": {"exists": True}})
    removed = execute()
    assert removed.returncode == 0, removed.stdout + removed.stderr
    assert not env_file.exists() and not container.exists() and not state_path.exists()
