from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from jinja2 import StrictUndefined
from jinja2.nativetypes import NativeEnvironment

REPO_ROOT = Path(__file__).resolve().parents[2]
ROLE = REPO_ROOT / "ansible/roles/service_prepare"
SERVICE_PATH = REPO_ROOT / "ansible/group_vars/all/services/romm.yml"
SEED_PATH = REPO_ROOT / "ansible/roles/service_common/files/romm/config.yml"
STRUCTURE = {"default": "roms/{platform}/{game}", "firmware": "bios/{platform}"}


def test_romm_seed_and_mounts_match_the_migrated_structure():
    service = yaml.safe_load(SERVICE_PATH.read_text())["romm"]
    seed = yaml.safe_load(SEED_PATH.read_text())
    copy = next(copy for copy in service["copies"] if copy["src"] == "files/romm/config.yml")

    assert seed["filesystem"]["structure"] == STRUCTURE
    assert not {"roms_folder", "firmware_folder"} & seed["filesystem"].keys()
    assert service["application_prepare"]["handler"] == "romm"
    assert copy["force"] is False
    assert copy["dest"] == service["volumes"]["config"]["source"] + "/config.yml"
    assert service["volumes"]["config"]["target"] + "/config.yml" == "/romm/config/config.yml"
    assert service["volumes"]["library"]["target"] == "/romm/library"
    assert service["volumes"]["library"]["source"] == ("{{ hostvars[services_storage_host].container_host_data_root }}/games/romm/library")


def test_romm_migration_is_tagged_and_runs_after_copies_before_deployment():
    tasks = yaml.safe_load((ROLE / "tasks/configure.yml").read_text())
    include = next(task for task in tasks if task["ansible.builtin.include_tasks"]["file"] == "applications/romm/configure.yml")
    for tags in (include["tags"], include["ansible.builtin.include_tasks"]["apply"]["tags"]):
        assert {"deploy", "update", "recreate", "bootstrap"} <= set(tags)
    assert "not ansible_check_mode" in include["when"]
    assert include["loop"] == "{{ service_prepare_context.filesystem_hosts }}"

    docker = yaml.safe_load((REPO_ROOT / "ansible/roles/docker_services/tasks/sub_tasks/prepare.yml").read_text())
    names = [task["name"] for task in docker]
    assert names.index("Prepare | Prepare shared files and integrations") < names.index("Prepare | Apply application configuration")
    main = yaml.safe_load((REPO_ROOT / "ansible/roles/docker_services/tasks/main.yml").read_text())
    names = [task["name"] for task in main]
    assert names.index("Docker services | Prepare service") < names.index("Docker services | Build Compose configuration")


@pytest.fixture
def local_deployment(tmp_path):
    """Execute only real copy and preparation tasks against fake localhost data."""
    appdata = tmp_path / "appdata"
    config = appdata / "romm/config/config.yml"
    config.parent.mkdir(parents=True)
    service = yaml.safe_load(SERVICE_PATH.read_text())["romm"]
    renderer = NativeEnvironment(undefined=StrictUndefined)
    variables = {
        "hostvars": {"localhost": {"container_host_appdata_root": str(appdata)}},
        "services_storage_host": "localhost",
    }
    seed_copy = next(copy for copy in service["copies"] if copy["src"] == "files/romm/config.yml").copy()
    seed_copy["dest"] = renderer.from_string(seed_copy["dest"]).render(variables)
    service["copies"] = [seed_copy]
    context = {
        "service_name": "romm",
        "runtime": "docker",
        "operation": "update",
        "service": service,
        "resolved_environment": {},
        "lookup_values": {},
        "secret_declarations": [],
        "controller_host": "localhost",
        "filesystem_hosts": ["localhost"],
        "host_defaults": {},
    }
    playbook = tmp_path / "migration.yml"
    tasks = [
        {"ansible.builtin.include_role": {"name": "service_prepare", "tasks_from": "validate"}},
        {
            "ansible.builtin.include_role": {
                "name": "service_common",
                "tasks_from": "copies",
                "apply": {"tags": ["deploy", "update", "recreate", "bootstrap"]},
            },
            "vars": {
                "service_common_target_host": "localhost",
                "service_common_copies": [seed_copy],
                "service_common_host_defaults": {},
                "service_common_default_owner": str(os.getuid()),
                "service_common_default_group": str(os.getgid()),
            },
        },
        {"ansible.builtin.include_role": {"name": "service_prepare", "tasks_from": "configure"}},
    ]
    for task in tasks:
        task["tags"] = ["deploy", "update", "recreate", "bootstrap"]
    playbook.write_text(
        yaml.safe_dump(
            [
                {
                    "hosts": "localhost",
                    "connection": "local",
                    "gather_facts": False,
                    "vars": {"service_prepare_context": context, "ansible_python_interpreter": sys.executable},
                    "tasks": tasks,
                }
            ]
        )
    )
    ansible_config = tmp_path / "ansible.cfg"
    ansible_config.write_text(f"[defaults]\nroles_path = {REPO_ROOT / 'ansible/roles'}\nstdout_callback = default\n")
    environment = os.environ.copy()
    environment.update(
        {
            "ANSIBLE_CONFIG": str(ansible_config),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible-local"),
            "ANSIBLE_REMOTE_TEMP": str(tmp_path / "ansible-remote"),
        }
    )

    def run(*args):
        result = subprocess.run(
            [str(Path(sys.executable).with_name("ansible-playbook")), "-i", "localhost,", str(playbook), *args],
            cwd=tmp_path,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode, result.stdout + result.stderr

    return config, run


@pytest.mark.parametrize(
    ("initial", "tags"),
    [
        (None, "deploy"),
        ("---\n# Previous repository seed was empty.\n", "update"),
        (
            "# Keep my settings\nscan:\n  priority:\n    metadata: [igdb, hasheous]\n"
            "filesystem:\n  custom_setting: keep\n  structure:\n    default: wrong\n    firmware: wrong\n"
            '    ps3: "roms/{platform}/{category}/{game}"\n',
            "recreate",
        ),
        (
            "filesystem:\n  roms_folder: roms\n  firmware_folder: bios\n  platform_binding: {custom: snes}\n",
            "bootstrap",
        ),
        ("filesystem:\n  roms_folder: null\n  firmware_folder: null\n", "update"),
    ],
)
def test_actual_deployment_migrates_existing_configs_and_converges(local_deployment, initial, tags):
    config, run = local_deployment
    before = (yaml.safe_load(initial) or {}) if initial is not None else {}
    if initial is not None:
        config.write_text(initial)
    rc, output = run("--tags", tags)
    assert rc == 0, output
    deployed = yaml.safe_load(config.read_text())
    assert deployed["filesystem"]["structure"]["default"] == STRUCTURE["default"]
    assert deployed["filesystem"]["structure"]["firmware"] == STRUCTURE["firmware"]
    assert not {"roms_folder", "firmware_folder"} & deployed["filesystem"].keys()
    for key, value in before.items():
        if key != "filesystem":
            assert deployed[key] == value
    for key, value in before.get("filesystem", {}).items():
        if key not in {"structure", "roms_folder", "firmware_folder"}:
            assert deployed["filesystem"][key] == value
    for key, value in before.get("filesystem", {}).get("structure", {}).items():
        if key not in STRUCTURE:
            assert deployed["filesystem"]["structure"][key] == value
    if initial and "# Keep my settings" in initial:
        assert "# Keep my settings" in config.read_text()
    assert config.stat().st_uid == os.getuid()
    assert config.stat().st_gid == os.getgid()
    assert config.stat().st_mode & 0o777 == 0o644

    converged = config.read_bytes()
    modified = config.stat().st_mtime_ns
    rc, output = run("--tags", tags)
    assert rc == 0, output
    assert "changed=0" in output
    assert config.read_bytes() == converged
    assert config.stat().st_mtime_ns == modified


def test_check_mode_does_not_edit_config(local_deployment):
    config, run = local_deployment
    original = "scan: {custom: keep}\n"
    config.write_text(original)
    rc, output = run("--check", "--tags", "update")
    assert rc == 0, output
    assert config.read_text() == original
    assert "RomM prepare | Set explicit library structure" not in output


def test_invalid_yaml_fails_without_replacing_user_config(local_deployment):
    config, run = local_deployment
    original = "filesystem: [invalid\n"
    config.write_text(original)
    rc, output = run("--tags", "update")
    assert rc != 0, output
    assert config.read_text() == original
