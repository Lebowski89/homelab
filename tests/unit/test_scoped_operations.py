"""Exercise explicit operation selection without inventory, secrets or runtimes."""

import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.integration
@pytest.mark.parametrize(
    "tag,check",
    [
        (None, False),
        ("all", False),
        ("mgt_firewall_check", False),
        ("worker_backend_firewall_check", True),
        ("haproxy_preflight", True),
        ("prometheus_haproxy_scrape", False),
        ("loki_alertmanager_route", False),
        ("prometheus_alertmanager_routes", True),
        ("prometheus_scraparr_scrape", True),
        ("podman_pasta_signal", True),
    ],
)
def test_only_explicit_operation_runs_and_inherits_tags(tmp_path, tag, check):
    plays = yaml.safe_load((ROOT / "ansible/operations.yml").read_text())
    expected = []
    for index, play in enumerate(plays):
        play.update(hosts="localhost", connection="local", become=False)
        play.pop("vars_files")
        include = play["tasks"][0]
        if tag in include["tags"]:
            expected.append(index)
        source = ROOT / "ansible" / include["ansible.builtin.include_tasks"]["file"]
        tasks = yaml.safe_load(source.read_text())
        role = next((deepcopy(task) for task in tasks if "ansible.builtin.include_role" in task), None)
        marker = {"name": "Record selected operation", "ansible.builtin.debug": {"msg": f"SCOPED_OPERATION_{index}"}}
        if role:
            # Keep the real role-include/apply contract, but replace runtime code with a fixture role.
            role.pop("when", None)
            role.pop("vars", None)
            role["ansible.builtin.include_role"].update(name=f"fixture_{index}", tasks_from="main")
            role_dir = tmp_path / "roles" / f"fixture_{index}" / "tasks"
            role_dir.mkdir(parents=True)
            (role_dir / "main.yml").write_text(yaml.safe_dump([marker]))
            body = [role]
        else:
            body = [marker]
        task_file = tmp_path / f"operation-{index}.yml"
        task_file.write_text(yaml.safe_dump(body))
        include["ansible.builtin.include_tasks"]["file"] = str(task_file)
    playbook = tmp_path / "operations.yml"
    playbook.write_text(yaml.safe_dump(plays))
    config = tmp_path / "ansible.cfg"
    config.write_text(f"[defaults]\nroles_path={tmp_path / 'roles'}\nstdout_callback=default\nretry_files_enabled=False\n")
    command = [str(Path(sys.executable).parent / "ansible-playbook"), "-i", "localhost,", str(playbook)]
    if tag:
        command += ["--tags", tag]
    if check:
        command += ["--check"]
    result = subprocess.run(
        command,
        env={
            **os.environ,
            "ANSIBLE_CONFIG": str(config),
            "ANSIBLE_LOG_PATH": str(tmp_path / "ansible.log"),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
            "ANSIBLE_REMOTE_TEMP": str(tmp_path / "remote"),
        },
        capture_output=True,
        text=True,
        timeout=45,
    )
    retired = {"prometheus_haproxy_scrape", "loki_alertmanager_route", "prometheus_alertmanager_routes", "prometheus_scraparr_scrape"}
    if tag in retired:
        assert result.returncode != 0
        assert "Completed Swarm-only workflows are archived" in result.stdout + result.stderr
        assert "SCOPED_OPERATION_" not in result.stdout
        return
    assert result.returncode == 0, result.stdout + result.stderr
    actual = [index for index in range(len(plays)) if f"SCOPED_OPERATION_{index}" in result.stdout]
    assert actual == expected, result.stdout


@pytest.mark.integration
@pytest.mark.parametrize(
    "profile,operation,entry,tags,success",
    [
        ("mgt", "check", "service_firewall", "mgt_firewall_check", True),
        ("mgt", "observe", "service_firewall", "mgt_firewall_observe", True),
        ("workers", "remove", "service_firewall", "worker_backend_firewall_remove", True),
        ("workers", "observe", "service_firewall", "all", False),
        ("unknown", "check", "service_firewall", "all", False),
        ("mgt", "destroy", "service_firewall", "all", False),
        ("mgt", "install", "service_firewall", "mgt_firewall_check", False),
        ("mgt", "check", "service_firewall", "mgt_firewall_check,worker_backend_firewall_check", False),
        ("mgt", "check", "mgt_firewall", "mgt_firewall_check", True),
        ("workers", "check", "worker_backend_firewall", "worker_backend_firewall_check", True),
        ("mgt", "check", "operation_mgt", "mgt_firewall_check", True),
        ("workers", "remove", "operation_workers", "worker_backend_firewall_remove", True),
    ],
)
def test_canonical_dispatch_and_legacy_role_forwarding_reject_invalid_combinations(tmp_path, profile, operation, entry, tags, success):
    # Exercise the real dispatcher and old wrappers, replacing only profile work
    # with read-only sentinels: invalid inputs cannot reach an inspection/write.
    roles = tmp_path / "roles"
    canonical = roles / "service_firewall"
    (canonical / "tasks").mkdir(parents=True)
    (canonical / "tasks/main.yml").write_text((ROOT / "ansible/roles/service_firewall/tasks/main.yml").read_text())
    # An external rollback playbook must not depend on playbook-local filter paths.
    (canonical / "filter_plugins").mkdir()
    (canonical / "files").mkdir()
    for kind, name in [
        ("filter_plugins", "service_firewall.py"),
        ("files", "bundle.py"),
        ("files", "transactions.py"),
        ("files", "mgt-firewall.py"),
        ("files", "worker-backend-firewall.py"),
    ]:
        (canonical / kind / name).write_text((ROOT / "ansible/roles/service_firewall" / kind / name).read_text())
    for selected, prefix in [("mgt", "mgt_firewall"), ("workers", "worker_backend_firewall")]:
        target = canonical / "tasks" / selected
        target.mkdir()
        (target / "main.yml").write_text(
            yaml.safe_dump(
                [
                    {
                        "ansible.builtin.set_fact": {"fixture_bundle": "{{ '" + selected + "' | service_firewall_helper_source }}"},
                        "no_log": True,
                    },
                    {"ansible.builtin.assert": {"that": ["fixture_bundle is string", "fixture_bundle | length > 0"]}},
                    {"ansible.builtin.debug": {"msg": "SELECTED_" + selected + "_{{ " + prefix + "_operation }}"}},
                ]
            )
        )
        legacy = roles / prefix / "tasks"
        legacy.mkdir(parents=True)
        (legacy / "main.yml").write_text((ROOT / f"ansible/roles/{prefix}/tasks/main.yml").read_text())
    (canonical / "tasks/operations").mkdir()
    for selected in ["mgt", "workers"]:
        (canonical / f"tasks/operations/{selected}.yml").write_text(
            (ROOT / f"ansible/roles/service_firewall/tasks/operations/{selected}.yml").read_text()
        )
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(
        yaml.safe_dump(
            {
                "all": {
                    "children": {
                        "controllers": {"hosts": {"localhost": {"ansible_connection": "local"}}},
                        "storage": {"hosts": {"unraid": {"ansible_connection": "local"}}},
                        "plexes": {"hosts": {"plex": {"ansible_connection": "local"}}},
                    }
                }
            }
        )
    )
    role_include = {"name": "service_firewall" if entry.startswith("operation_") else entry, "apply": {"tags": ["always"]}}
    if entry.startswith("operation_"):
        role_include["tasks_from"] = "operations/" + profile
    prefix = "mgt_firewall" if profile == "mgt" else "worker_backend_firewall"
    play = tmp_path / "dispatch.yml"
    play.write_text(
        yaml.safe_dump(
            [
                {
                    "hosts": "unraid" if entry == "operation_workers" else "localhost",
                    "connection": "local",
                    "gather_facts": False,
                    "vars": {
                        "services_controller_inventory_group": "controllers",
                        "services_storage_inventory_group": "storage",
                        "services_plex_host": "plex",
                        "service_firewall_profile": profile,
                        "service_firewall_operation": operation,
                        prefix + "_operation": operation,
                    },
                    "tasks": [{"ansible.builtin.include_role": role_include, "tags": ["always"]}],
                }
            ]
        )
    )
    config = tmp_path / "ansible.cfg"
    config.write_text(f"[defaults]\nroles_path={roles}\nvars_plugins_enabled=\nstdout_callback=default\n")
    result = subprocess.run(
        [str(Path(sys.executable).parent / "ansible-playbook"), "-i", str(inventory), str(play), "--check", "--tags", tags],
        env={
            **os.environ,
            "ANSIBLE_CONFIG": str(config),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
            "ANSIBLE_LOG_PATH": str(tmp_path / "ansible.log"),
        },
        capture_output=True,
        text=True,
        timeout=45,
    )
    output = result.stdout + result.stderr
    assert (result.returncode == 0) == success, output
    if success:
        assert "SELECTED_" + profile + "_" + operation in output, output
        assert "SELECTED_" + ("workers" if profile == "mgt" else "mgt") not in output
    else:
        assert "SELECTED_" not in output
        assert "Select one firewall profile" in output


@pytest.mark.integration
@pytest.mark.parametrize("name,prefix", [("mgt-firewall", "mgt_firewall"), ("worker-backend-firewall", "worker_backend_firewall")])
@pytest.mark.parametrize("selection", [None, "all", "check"])
def test_installed_skynet_playbook_aliases_also_require_explicit_selection(tmp_path, name, prefix, selection):
    plays = yaml.safe_load((ROOT / f"ansible/{name}.yml").read_text())
    play = plays[0]
    play.update(hosts="localhost", connection="local", become=False)
    play.pop("vars_files")
    marker = tmp_path / "operation.yml"
    marker.write_text(yaml.safe_dump([{"ansible.builtin.debug": {"msg": "COMPAT_OPERATION_SELECTED"}}]))
    play["tasks"][0]["ansible.builtin.import_tasks"] = str(marker)
    source = tmp_path / "compat.yml"
    source.write_text(yaml.safe_dump(plays))
    config = tmp_path / "ansible.cfg"
    config.write_text("[defaults]\nvars_plugins_enabled=\nstdout_callback=default\n")
    command = [str(Path(sys.executable).parent / "ansible-playbook"), "-i", "localhost,", str(source)]
    if selection:
        command += ["--tags", prefix + "_check" if selection == "check" else selection]
    result = subprocess.run(
        command,
        env={
            **os.environ,
            "ANSIBLE_CONFIG": str(config),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
            "ANSIBLE_LOG_PATH": str(tmp_path / "ansible.log"),
        },
        capture_output=True,
        text=True,
        timeout=45,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert ("COMPAT_OPERATION_SELECTED" in output) == (selection == "check"), output
