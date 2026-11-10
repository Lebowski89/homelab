from __future__ import annotations

import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ROLE = REPO_ROOT / "ansible/roles/docker_services"


@pytest.mark.integration
@pytest.mark.parametrize(
    ("operation", "force", "expected_cleanup"),
    [
        ("deploy", False, False),
        ("deploy", True, False),
        ("update", False, False),
        ("bootstrap", False, False),
        ("remove", False, True),
        ("recreate", False, True),
    ],
)
def test_inherited_operation_tags_do_not_authorize_docker_cleanup(tmp_path, operation, force, expected_cleanup):
    """Execute the real cleanup guards; replace only the destructive include with a private marker."""
    prepare = yaml.safe_load((ROLE / "tasks/sub_tasks/prepare.yml").read_text())
    tasks = deepcopy([task for task in prepare if task["name"].startswith("Cleanup |")])
    marker = tmp_path / "cleanup-reached"
    tracker = tmp_path / "cleanup-tracker.json"
    cleanup = next(task for task in tasks if task["name"] == "Cleanup | Remove existing deployment")
    del cleanup["ansible.builtin.include_tasks"]
    cleanup["ansible.builtin.copy"] = {"dest": str(marker), "content": "SYNTHETIC_CLEANUP", "mode": "0600"}
    (tmp_path / "cleanup.yml").write_text(yaml.safe_dump(tasks))
    main = yaml.safe_load((ROLE / "tasks/main.yml").read_text())
    include = next(
        task
        for group in main
        for task in [group, *group.get("block", [])]
        if task.get("ansible.builtin.include_tasks", {}).get("file") == "sub_tasks/prepare.yml"
    )
    playbook = tmp_path / "play.yml"
    playbook.write_text(
        yaml.safe_dump(
            [
                {
                    "hosts": "localhost",
                    "connection": "local",
                    "gather_facts": False,
                    "vars": {
                        "ansible_python_interpreter": sys.executable,
                        "docker_services_common_action": operation,
                        "docker_services_svc": {"cleanup": {"enable": True, "force": force}},
                        "docker_services_is_deploy_host": True,
                        "docker_services_stack_name_effective": "synthetic-stack",
                    },
                    "tasks": [
                        {
                            "ansible.builtin.include_tasks": {
                                "file": "cleanup.yml",
                                "apply": deepcopy(include["ansible.builtin.include_tasks"]["apply"]),
                            },
                            "tags": deepcopy(include["tags"]),
                        },
                        {
                            "ansible.builtin.copy": {
                                "dest": str(tracker),
                                "content": "{{ docker_services_stacks_cleaned | default([]) | to_json }}",
                                "mode": "0600",
                            },
                            "tags": ["always"],
                        },
                    ],
                }
            ]
        )
    )
    config = tmp_path / "ansible.cfg"
    config.write_text("[defaults]\nstdout_callback=default\nretry_files_enabled=false\ninject_facts_as_vars=false\n")
    environment = {
        **{key: value for key, value in os.environ.items() if not key.startswith("ANSIBLE_")},
        "ANSIBLE_CONFIG": str(config),
        "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
        "ANSIBLE_REMOTE_TEMP": str(tmp_path / "remote"),
    }
    result = subprocess.run(
        [str(Path(sys.executable).with_name("ansible-playbook")), "-i", "localhost,", str(playbook), "--tags", operation],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert marker.exists() is expected_cleanup, result.stdout + result.stderr
    assert json.loads(tracker.read_text()) == (["synthetic-stack"] if expected_cleanup else [])


@pytest.mark.integration
@pytest.mark.parametrize("network_state", ["retires", "stuck", "unavailable"])
def test_swarm_cleanup_waits_for_owned_networks_and_retains_manifest_on_failure(tmp_path, network_state):
    """Mock Docker I/O only; run the real cleanup ordering, retries and rescue."""
    from test_podman_rootless_check_mode import run_local_playbook

    actions = tmp_path / "collections/ansible_collections/community/docker/plugins/action"
    actions.mkdir(parents=True)
    plugin = """from pathlib import Path
from ansible.plugins.action import ActionBase
class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        manifest=Path(task_vars['test_stack_manifest'])
        assert manifest.exists(), 'Manifest removed before network retirement'
        if self._task.action.endswith('docker_stack'):
            assert self._task.args['state']=='absent'
            return {'changed': True}
        expected='com.docker.stack.namespace='+task_vars['docker_services_cleanup_stack_name']
        assert self._task.args['networks_filters']=={'label': expected}, 'Unscoped network query'
        counter=Path(task_vars['test_network_counter'])
        count=int(counter.read_text())+1 if counter.exists() else 1
        counter.write_text(str(count))
        if task_vars['test_network_state']=='unavailable':
            return {'failed': True, 'msg': 'Synthetic unavailable daemon'}
        retired=task_vars['test_network_state']=='retires' and count>=2
        return {'changed': False, 'networks': [] if retired else [{'Id': 'retiring-network'}]}
"""
    for name in ["docker_stack", "docker_host_info", "docker_compose_v2"]:
        (actions / (name + ".py")).write_text(plugin)
    manifest = tmp_path / "stack.yml"
    manifest.write_text("retained stack declaration")
    counter = tmp_path / "network-queries"
    tasks = deepcopy(yaml.safe_load((ROLE / "tasks/sub_tasks/cleanup.yml").read_text()))
    for task in tasks:
        for nested in task.get("block", []):
            if "ansible.builtin.file" in nested and nested["ansible.builtin.file"]["path"].endswith("-stack.yml"):
                nested["ansible.builtin.file"]["path"] = str(manifest)
            if "until" in nested:
                nested.update(retries=2, delay=0)
    result = run_local_playbook(
        tmp_path,
        [
            {
                "hosts": "localhost",
                "connection": "local",
                "gather_facts": False,
                "vars": {
                    "ansible_python_interpreter": sys.executable,
                    "docker_services_stack_name_effective": "synthetic-stack",
                    "docker_services_stack_deploy_type": "swarm",
                    "test_stack_manifest": str(manifest),
                    "test_network_counter": str(counter),
                    "test_network_state": network_state,
                },
                "tasks": tasks,
            }
        ],
        check_mode=False,
        extra_env={"ANSIBLE_COLLECTIONS_PATH": str(tmp_path / "collections")},
    )
    assert (result.returncode == 0) is (network_state == "retires"), result.stdout + result.stderr
    assert int(counter.read_text()) >= 2
    assert manifest.exists() is (network_state != "retires")
