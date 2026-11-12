"""Validate the real VM fixture contract; this is not runtime acceptance."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar

ROOT = Path(__file__).resolve().parents[2]


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


PODMAN = module("ansible/roles/podman_services/filter_plugins/podman_services.py", "vm_fixture_podman")
DOCKER = module("ansible/roles/docker_services/filter_plugins/docker_services_volumes.py", "vm_fixture_docker")
DOCKER_FIELDS = module("ansible/roles/docker_services/filter_plugins/docker_services_list_fields.py", "vm_fixture_docker_fields")
DOCKER_PORTS = module("ansible/roles/docker_services/filter_plugins/docker_services_ports.py", "vm_fixture_docker_ports")
STORAGE = module("ansible/filter_plugins/service_storage.py", "vm_fixture_storage")
CATALOG = module("ansible/filter_plugins/service_catalog.py", "vm_fixture_catalog")
FIREWALL = module("ansible/roles/service_firewall/files/declarations.py", "vm_fixture_firewall")
STATS = module("molecule/shared/callback_plugins/vm_stats.py", "vm_fixture_stats")


def test_preparation_failure_evidence_handles_loop_results_without_accepting_unrelated_failures():
    marker = "molecule/shared/fixtures/missing.j2"
    callback = STATS.CallbackModule()
    callback.v2_runner_on_failed(SimpleNamespace(result={"msg": "loop failed", "results": [{"msg": "unrelated", "item": {"src": marker}}]}))
    assert not getattr(callback, "_expected_prepare_failure", False)
    callback.v2_runner_item_on_failed(SimpleNamespace(result={"msg": f"Template lookup failed: {marker}"}))
    assert callback._expected_prepare_failure
    censored = STATS.CallbackModule()
    event = SimpleNamespace(msg=f"Template lookup failed: {marker}", events=None, chain=None)
    censored.v2_runner_item_on_failed(SimpleNamespace(result={"censored": True}, exception=SimpleNamespace(event=event)))
    assert censored._expected_prepare_failure


@pytest.mark.parametrize("mode", ["compose", "swarm", "rootful", "rootless"])
def test_application_fixture_uses_supported_storage_and_adapter_fields_after_target_merge(mode):
    loader = DataLoader()
    raw = loader.load_from_file(str(ROOT / "molecule/shared/fixtures/application.yml"), trusted_as_template=True)["svcfiles"]["writer"]
    run_id = "a" * 32
    templar = Templar(loader=loader, variables={"molecule_vm_runtime": mode, "molecule_vm_run_id": run_id})
    catalog = {"writer:" + target: templar.template(CATALOG.service_catalog_merge_target(raw, target)) for target in raw["targets"]}
    # Unselected fixture variants must not reserve the selected publication.
    assert sum(cfg["enabled"] for cfg in catalog.values()) == 1
    FIREWALL.plan("writer:" + mode, catalog, "subject", [], {"subject": {"local_ip": "192.0.2.10"}})
    # Production merges raw base/target declarations before host templating.
    merged = CATALOG.service_catalog_merge_target(raw, mode)
    cfg = templar.template(merged)
    # In particular, Swarm must use the supported host-label contract rather
    # than a private-label declaration rejected by the real storage planner.
    STORAGE.service_storage_plan(cfg, cfg["runtime"], cfg["deploy"]["type"])
    if cfg["runtime"] == "podman":
        normalized = PODMAN.podman_service_normalize(cfg, "writer")
        assert normalized["execution"]["mode"] == mode
        assert normalized["secret_attachments"]  # Materialized by the real adapters, not replaced in the VM test.
        assert run_id in normalized["container"]["exec"]
    else:
        assert DOCKER.docker_services_canonical_volumes(cfg["volumes"])
        DOCKER_FIELDS.docker_services_no_new_privileges_security_opts(cfg["no_new_privileges"], cfg["deploy"]["type"])
        assert DOCKER_PORTS.docker_services_canonical_ports(ports=cfg["ports"], stack_deploy_type=cfg["deploy"]["type"])
    # Shell/environment interpolation must not be delegated to Compose or
    # systemd: the same literal command reaches both runtime adapters.
    assert "$" not in " ".join(cfg["command"])


def test_diagnostic_storage_removes_sensitive_daemon_lines_but_keeps_failure_evidence():
    loader = DataLoader()
    tasks = loader.load_from_file(str(ROOT / "molecule/shared/diagnostics.tasks.yml"), trusted_as_template=True)
    capture = next(task for task in tasks if task.get("register") == "molecule_vm_diagnostic")
    assert capture["no_log"] is True and capture["diff"] is False
    storage = next(task for task in tasks if "molecule_vm_diagnostic_redaction" in task.get("vars", {}))
    templar = Templar(
        loader=loader,
        variables={
            **storage["vars"],
            "molecule_vm_diagnostic": {
                "results": [
                    {
                        "rc": 0,
                        "stdout": "Docker memberlist Keys:[[SYNTHETIC_GOSSIP_VALUE]]\nnetwork fixture not found",
                        "stderr": "Authorization: SYNTHETIC_AUTH_VALUE\nordinary diagnostic",
                    }
                ]
            },
        },
    )
    result = templar.template(storage["ansible.builtin.copy"]["content"])
    assert "SYNTHETIC_GOSSIP_VALUE" not in result and "SYNTHETIC_AUTH_VALUE" not in result
    assert "network fixture not found" in result and "ordinary diagnostic" in result


@pytest.mark.integration
@pytest.mark.parametrize("skipped", [False, True])
def test_quadlet_diagnostic_is_stored_for_completed_commands_and_skipped_for_absent_accounts(tmp_path, skipped):
    import json

    import yaml
    from test_podman_rootless_check_mode import run_local_playbook

    tasks = yaml.safe_load((ROOT / "molecule/shared/diagnostics.tasks.yml").read_text())
    storage = next(task for parent in tasks for task in parent.get("block", []) if "ansible.builtin.copy" in task)
    observation = {"skipped": True} if skipped else {"rc": 1, "stdout": "ActiveState=failed", "stderr": "synthetic failure"}
    result = run_local_playbook(
        tmp_path,
        [
            {
                "hosts": "localhost",
                "connection": "local",
                "gather_facts": False,
                "vars": {"molecule_vm_evidence_directory": str(tmp_path), "molecule_vm_quadlet_diagnostic": observation},
                "tasks": [storage],
            }
        ],
        check_mode=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    evidence = list(tmp_path.glob("*.json"))
    assert len(evidence) == (0 if skipped else 1)
    if evidence:
        assert json.loads(evidence[0].read_text())["stdout"] == observation["stdout"]


@pytest.mark.integration
@pytest.mark.parametrize("layout", ["expected", "foreign-root", "wrong-filesystem", "additional-volume", "wrong-capacity"])
def test_fedora_growth_refuses_foreign_layout_before_mutation(tmp_path, layout):
    import yaml
    from ansible_task_cases import task_section
    from test_podman_rootless_check_mode import run_local_playbook

    tasks = yaml.safe_load((ROOT / "molecule/vm/fedora-root.tasks.yml").read_text())
    selected = task_section(
        tasks,
        lambda task: "ansible.builtin.set_fact" in task,
        lambda task: "community.general.lvol" in task,
        purpose="Fedora allocation growth guard",
    )
    root = {"mount": "/", "device": "/dev/mapper/systemVG-LVRoot", "fstype": "xfs"}
    group = {"num_lvs": 1, "num_pvs": 1, "size_g": "13.55", "lvs": {"LVRoot": {"size_g": "3.12"}}}
    if layout == "wrong-capacity":
        group["size_g"] = "29.55"
    if layout == "foreign-root":
        root["device"] = "/dev/mapper/production-root"
    if layout == "wrong-filesystem":
        root["fstype"] = "ext4"
    if layout == "additional-volume":
        group.update(num_lvs=2, lvs={"LVRoot": {}, "other": {}})
    actions = tmp_path / "collections/ansible_collections/community/general/plugins/action"
    actions.mkdir(parents=True)
    marker = tmp_path / "growth-boundary"
    (actions / "lvol.py").write_text(
        "from pathlib import Path\nfrom ansible.plugins.action import ActionBase\n"
        "class ActionModule(ActionBase):\n"
        " def run(self,tmp=None,task_vars=None):\n"
        "  assert self._task.args['shrink'] is False and self._task.args['force'] is False\n"
        "  Path(task_vars['test_growth_marker']).touch()\n"
        "  return {'changed':False}\n"
    )
    result = run_local_playbook(
        tmp_path,
        [
            {
                "hosts": "localhost",
                "connection": "local",
                "gather_facts": False,
                "vars": {
                    "ansible_facts": {"mounts": [root], "lvm": {"vgs": {"systemVG": group}}},
                    "molecule_vm_disk_gb": 16,
                    "test_growth_marker": str(marker),
                },
                "tasks": selected,
            }
        ],
        check_mode=False,
        extra_env={"ANSIBLE_COLLECTIONS_PATH": str(tmp_path / "collections")},
    )
    assert (result.returncode == 0) is (layout == "expected"), result.stdout + result.stderr
    assert marker.exists() is (layout == "expected")
    if layout != "expected":
        assert "no growth was attempted" in result.stdout
