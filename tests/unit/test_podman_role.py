from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PODMAN_ROLE = REPO_ROOT / "ansible" / "roles" / "podman"
PODMAN_DEFAULTS = yaml.safe_load((PODMAN_ROLE / "defaults" / "main.yml").read_text())
PODMAN_TASKS = yaml.safe_load((PODMAN_ROLE / "tasks" / "main.yml").read_text())


def podman_task(name: str) -> dict:
    return next(task for task in PODMAN_TASKS if task["name"] == name)


def run_assertion_task(tmp_path: Path, task_name: str, variables: dict) -> subprocess.CompletedProcess[str]:
    playbook = tmp_path / "podman-assertion.yml"
    playbook.write_text(
        yaml.safe_dump(
            [
                {
                    "name": "Exercise Podman role assertion",
                    "hosts": "localhost",
                    "connection": "local",
                    "gather_facts": False,
                    "vars": variables,
                    "tasks": [podman_task(task_name)],
                }
            ],
            sort_keys=False,
        )
    )
    environment = os.environ.copy()
    environment.update(
        {
            "ANSIBLE_CONFIG": str(REPO_ROOT / "ansible" / "ansible.cfg"),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible-local"),
            "ANSIBLE_REMOTE_TEMP": str(tmp_path / "ansible-remote"),
            "ANSIBLE_NOCOLOR": "1",
        }
    )
    return subprocess.run(
        [str(Path(sys.executable).with_name("ansible-playbook")), "-i", "localhost,", str(playbook)],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    "facts",
    [
        {
            "os_family": "Debian",
            "distribution": "Ubuntu",
            "distribution_version": "26.04",
            "distribution_major_version": "26",
        },
        {
            "os_family": "Debian",
            "distribution": "Ubuntu",
            "distribution_version": "26.10",
            "distribution_major_version": "26",
        },
        {
            "os_family": "Debian",
            "distribution": "LMDE",
            "distribution_version": "7",
            "distribution_major_version": "7",
        },
    ],
    ids=["ubuntu-26.04", "newer-ubuntu", "lmde-7"],
)
def test_supported_podman_platforms_pass_the_role_contract(tmp_path: Path, facts: dict):
    result = run_assertion_task(
        tmp_path,
        "Podman | Assert supported host",
        {"ansible_facts": facts, "podman_min_version": PODMAN_DEFAULTS["podman_min_version"]},
    )

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "facts",
    [
        {
            "os_family": "Debian",
            "distribution": "Ubuntu",
            "distribution_version": "24.04",
            "distribution_major_version": "24",
        },
        {
            "os_family": "Debian",
            "distribution": "LMDE",
            "distribution_version": "6",
            "distribution_major_version": "6",
        },
        {
            "os_family": "Debian",
            "distribution": "Linux Mint",
            "distribution_version": "22",
            "distribution_major_version": "22",
        },
        {
            "os_family": "Debian",
            "distribution": "Debian",
            "distribution_version": "13",
            "distribution_major_version": "13",
        },
        {
            "os_family": "RedHat",
            "distribution": "Fedora",
            "distribution_version": "43",
            "distribution_major_version": "43",
        },
    ],
    ids=["ubuntu-24.04", "lmde-6", "ordinary-linux-mint", "debian-13", "non-debian-family"],
)
def test_unsupported_podman_platforms_fail_the_role_contract(tmp_path: Path, facts: dict):
    result = run_assertion_task(
        tmp_path,
        "Podman | Assert supported host",
        {"ansible_facts": facts, "podman_min_version": PODMAN_DEFAULTS["podman_min_version"]},
    )

    assert result.returncode != 0
    assert "LMDE 7" in result.stdout + result.stderr


@pytest.mark.parametrize("version", ["5.4.2", "5.7.0", "6.0.0"])
def test_supported_podman_versions_pass_the_role_contract(tmp_path: Path, version: str):
    result = run_assertion_task(
        tmp_path,
        "Podman | Assert Quadlet-capable version",
        {
            "podman_min_version": PODMAN_DEFAULTS["podman_min_version"],
            "podman_version_result": {"rc": 0, "stdout": f"podman version {version}"},
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("version", ["5.4.1", "4.9.3"])
def test_podman_versions_below_the_supported_floor_fail(tmp_path: Path, version: str):
    result = run_assertion_task(
        tmp_path,
        "Podman | Assert Quadlet-capable version",
        {
            "podman_min_version": PODMAN_DEFAULTS["podman_min_version"],
            "podman_version_result": {"rc": 0, "stdout": f"podman version {version}"},
        },
    )

    assert result.returncode != 0
    assert "must be at least 5.4.2" in result.stdout + result.stderr


def test_podman_role_declares_required_runtime_packages():
    assert set(PODMAN_DEFAULTS["podman_packages"]) == {
        "podman",
        "containernetworking-plugins",
        "uidmap",
        "slirp4netns",
        "passt",
        "fuse-overlayfs",
        "dbus-user-session",
    }


def test_podman_role_retains_runtime_capability_guards():
    version = podman_task("Podman | Assert Quadlet-capable version")
    cgroup = podman_task("Podman | Assert cgroup v2")
    generator = podman_task("Podman | Assert system Quadlet generator exists")

    assert "podman_min_version" in str(version["ansible.builtin.assert"]["that"])
    assert cgroup["ansible.builtin.assert"]["that"] == ["podman_cgroup_version_result.stdout | trim == 'v2'"]
    assert generator["ansible.builtin.assert"]["that"] == ["podman_quadlet_generator_path | length > 0"]
