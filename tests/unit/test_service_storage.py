"""Storage label contracts, actual adapter rendering and isolated host-policy behavior."""

import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from ansible.errors import AnsibleFilterError
from ansible.plugins.filter.core import FilterModule as CoreFilters
from jinja2 import Environment, FileSystemLoader
from test_podman_quadlet_templates import canonical_service, render
from test_service_catalog_repository_regression import render_structure

pytest_plugins = ["test_system"]
ROOT = Path(__file__).resolve().parents[2]


def load(path):
    spec = importlib.util.spec_from_file_location(Path(path).stem + "_storage_tests", ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STORAGE = load("ansible/filter_plugins/service_storage.py")
COMMON = load("ansible/roles/service_common/filter_plugins/service_common.py")
DOCKER = load("ansible/roles/docker_services/filter_plugins/docker_services_volumes.py")
PODMAN = load("ansible/roles/podman_services/filter_plugins/podman_services.py")
PREPARE = load("ansible/roles/service_prepare/filter_plugins/service_prepare.py")
CATALOG = load("ansible/filter_plugins/service_catalog.py")


def service(mode="shared"):
    return {
        "volumes": {"data": {"type": "bind", "source": "/opt/appdata/demo", "target": "/data", "read_only": True, "selinux": mode}},
        "paths": [{"path": "/opt/appdata/demo", "state": "directory", "owner": "1001", "mode": "0750"}],
    }


def compose(volumes, deployment="container"):
    env = Environment(loader=FileSystemLoader(ROOT / "ansible/roles/docker_services/templates"), trim_blocks=True, lstrip_blocks=True)
    env.filters.update(CoreFilters().filters())
    output = env.get_template("compose.yml.j2").render(
        deploy_stack_type=deployment,
        docker_services_compose_services={
            "demo": {"image": "example.invalid/demo:1", "logging": {"driver": "json-file", "options": {}}, "volumes": volumes}
        },
    )
    return yaml.safe_load(output)["services"]["demo"]["volumes"]


@pytest.mark.parametrize("mode,flag", [("shared", "z"), ("private", "Z"), ("preserve", None)])
def test_bind_label_choice_survives_both_adapter_renderers_without_changing_access(mode, flag):
    cfg = canonical_service()
    cfg["volumes"]["config"]["selinux"] = mode
    normalized = PODMAN.podman_service_normalize(cfg, "portable")
    assert normalized["container"]["mounts"][0]["read_only"] is True
    assert f"Volume=/opt/portable/config:/config:ro{',' + flag if flag else ''}" in render("container.container.j2", normalized)
    volumes = DOCKER.docker_services_canonical_volumes(cfg["volumes"])
    assert compose(volumes)[0] == f"/opt/portable/config:/config:ro{',' + flag if flag else ''}"


def test_swarm_shared_labels_use_host_policy_and_private_requests_fail_before_rendering():
    cfg = service()
    plan = STORAGE.service_storage_plan(cfg, "docker", "swarm")
    assert plan["persistent"] is True and plan["paths"][0]["selevel"] == "s0"
    assert compose(DOCKER.docker_services_canonical_volumes(cfg["volumes"]), "swarm")[0] == {
        "type": "bind",
        "source": "/opt/appdata/demo",
        "target": "/data",
        "read_only": True,
    }
    with pytest.raises(AnsibleFilterError, match="Swarm cannot"):
        STORAGE.service_storage_plan(service("private"), "docker", "swarm")


@pytest.mark.parametrize("value", [True, None, "Z"])
def test_new_policy_inputs_are_strict_in_both_volume_normalizers(value):
    volumes = [{"type": "bind", "source": "/opt/appdata/demo", "target": "/data", "selinux": value}]
    for normalize in (DOCKER.docker_services_canonical_volumes, lambda value: PODMAN._canonical_volumes(value, name="volumes")):
        with pytest.raises(AnsibleFilterError, match="selinux"):
            normalize(volumes)
    for kind in ("volume", "tmpfs"):
        with pytest.raises(AnsibleFilterError, match="selinux"):
            DOCKER.docker_services_canonical_volumes([{**volumes[0], "type": kind, "selinux": "preserve"}])


def test_preserve_is_the_legacy_default_and_automatic_labels_require_owned_storage():
    cfg = service()
    cfg["volumes"]["data"].pop("selinux")
    original = deepcopy(cfg)
    assert STORAGE.service_storage_plan(cfg, "podman")["paths"] == []
    assert cfg == original
    cfg["volumes"]["data"]["selinux"] = "shared"
    cfg["paths"] = []
    with pytest.raises(AnsibleFilterError, match="owned"):
        STORAGE.service_storage_plan(cfg, "podman")
    cfg = service("private")
    cfg["volumes"]["other"] = {**cfg["volumes"]["data"], "target": "/other", "selinux": "shared"}
    with pytest.raises(AnsibleFilterError, match="overlap"):
        STORAGE.service_storage_plan(cfg, "podman")
    with pytest.raises(AnsibleFilterError, match="silently"):
        DOCKER.docker_services_merge_volumes(
            DOCKER.docker_services_canonical_volumes(service("preserve")["volumes"]), service()["volumes"], action="append_unique"
        )


def test_preparation_inherits_shared_labels_and_rejects_private_relabeling_or_unrelated_paths():
    cfg = service()
    assert PREPARE.service_prepare_storage_mounts(cfg, ["/opt/appdata/demo:/data:ro"]) == ["/opt/appdata/demo:/data:ro,z"]
    with pytest.raises(AnsibleFilterError, match="privately relabel"):
        PREPARE.service_prepare_storage_mounts(service("private"), ["/opt/appdata/demo:/data"])
    with pytest.raises(AnsibleFilterError, match="current service"):
        PREPARE.service_prepare_storage_mounts(cfg, ["/opt/another:/data"])


@pytest.mark.parametrize("source,actual", [("/etc", None), ("/opt/appdata", None), ("/opt/appdata/demo", "/etc/demo")])
def test_context_scope_rejects_system_paths_broad_roots_and_symlink_escapes(source, actual):
    contexts = [{"path": source, "recurse": True, "setype": "container_file_t", "selevel": "s0"}]
    resolved = {source: actual, "/opt/appdata": "/opt/appdata"} if actual else None
    with pytest.raises(AnsibleFilterError):
        COMMON.service_common_file_contexts(contexts, ["/opt/appdata"], resolved)


def test_real_haproxy_target_storage_preserves_policy_across_the_effective_merge():
    real = yaml.safe_load((ROOT / "ansible/group_vars/all/services/haproxy.yml").read_text())["haproxy"]
    cfg = CATALOG.service_catalog_merge_target(real, "mgt")
    variables = {"services_controller_host": "mgt", "hostvars": {"mgt": {"container_host_appdata_root": "/opt/appdata"}}}
    cfg["volumes"] = render_structure(cfg["volumes"], variables)
    cfg["paths"] = render_structure(cfg["paths"], variables)
    cfg["templates"] = [{"dest": render_structure(item["dest"], variables)} for item in cfg.get("templates", [])]
    owned = {p["path"] for p in cfg["paths"]} | {p["dest"] for p in cfg["templates"]}
    bind = next(v for v in cfg["volumes"].values() if v.get("type", "bind") == "bind" and v["source"] in owned)
    bind["selinux"] = "shared"
    for runtime, deployment in [("podman", "container"), ("docker", "swarm")]:
        plan = STORAGE.service_storage_plan(cfg, runtime, deployment)
        assert plan["paths"] and plan["persistent"] == (runtime == "docker")
        assert any(path["path"] == bind["source"] for path in plan["paths"])


def run_contexts(system_run, **kwargs):
    contexts = STORAGE.service_storage_plan(service(), "docker", "swarm")["paths"]
    return system_run(
        role="service_common",
        tasks_from="file_contexts",
        tags="all",
        overrides={
            "service_common_file_contexts": contexts,
            "service_common_file_context_roots": ["/opt/appdata"],
            "service_common_file_context_host": "localhost",
            "service_common_file_context_apply": True,
            "fixture_directories": ["/opt/appdata/demo"],
            **kwargs.pop("overrides", {}),
        },
        **kwargs,
    )


@pytest.mark.integration
def test_context_policy_and_restore_are_scoped_and_converge_without_posix_ownership_changes(system_run):
    result, calls, _ = run_contexts(system_run)
    assert result.returncode == 0, result.stdout + result.stderr
    mappings = [call["options"] for call in calls if call["module"] == "community.general.sefcontext"]
    assert mappings == [{"target": "/opt/appdata/demo(/.*)?", "setype": "container_file_t", "selevel": "s0", "state": "present"}]
    restores = [call["options"] for call in calls if call["module"] == "community.general.serestorecon"]
    assert restores == [{"path": "/opt/appdata/demo", "recurse": True, "cross_filesystems": False, "context": "full"}]
    assert not any(call["module"] in {"file", "user", "group", "systemd_service"} for call in calls)
    result, _, _ = run_contexts(system_run)
    assert result.returncode == 0 and "changed=0" in result.stdout, result.stdout + result.stderr


@pytest.mark.integration
@pytest.mark.parametrize("case", ["check", "unknown-check", "disabled", "validate-only", "missing-path"])
def test_context_plans_defer_missing_resources_and_preserve_disabled_or_runtime_managed_labels(system_run, case):
    overrides = {"fixture_selinux": {"status": "disabled"}} if case == "disabled" else {}
    if case == "unknown-check":
        overrides["fixture_selinux"] = False
    if case == "validate-only":
        overrides["service_common_file_context_apply"] = False
    if case == "missing-path":
        overrides["fixture_directories"] = []
    result, calls, _ = run_contexts(system_run, check=case in {"check", "unknown-check"}, overrides=overrides)
    assert result.returncode == 0, result.stdout + result.stderr
    if case != "missing-path":
        assert {call["module"] for call in calls} <= {"setup", "command", "stat"}
    else:
        assert not any(call["module"] == "community.general.serestorecon" for call in calls)


@pytest.mark.integration
def test_context_realpath_escape_fails_before_any_policy_or_package_mutation(system_run):
    result, calls, _ = run_contexts(system_run, overrides={"fixture_realpaths": {"/opt/appdata/demo": "/etc"}})
    assert result.returncode != 0
    assert {call["module"] for call in calls} <= {"setup", "command"}


@pytest.mark.integration
def test_unknown_selinux_state_cannot_authorize_policy_changes(system_run):
    result, calls, _ = run_contexts(system_run, overrides={"fixture_selinux": False})
    assert result.returncode != 0
    assert {call["module"] for call in calls} <= {"setup"}
    assert "unknown state" in result.stdout


def test_storage_preflight_tag_propagation_and_removal_guards():
    required = {"deploy", "update", "recreate", "bootstrap"}
    for path in [
        ROOT / "ansible/roles/docker_services/tasks/main.yml",
        ROOT / "ansible/roles/docker_services/tasks/sub_tasks/prepare.yml",
        ROOT / "ansible/roles/podman_services/tasks/main.yml",
    ]:

        def walk(tasks):
            for task in tasks:
                yield task
                for branch in ("block", "rescue", "always"):
                    yield from walk(task.get(branch, []))

        tasks = list(walk(yaml.safe_load(path.read_text())))
        for task in tasks:
            include = task.get("ansible.builtin.include_tasks", {})
            role = task.get("ansible.builtin.include_role", {})
            if isinstance(include, dict) and include.get("file") == "sub_tasks/storage.yml" or role.get("tasks_from") == "file_contexts":
                selected = include if include else role
                assert required <= set(task["tags"]) and required <= set(selected["apply"]["tags"])
                assert "deploy" in str(task.get("when", [])) and "remove" not in str(task.get("when", []))


@pytest.mark.integration
def test_managed_file_context_is_exact_and_nonrecursive(system_run):
    path = "/opt/appdata/demo/config.yml"
    result, calls, _ = run_contexts(
        system_run,
        overrides={
            "service_common_file_contexts": [{"path": path, "setype": "container_file_t", "selevel": "s0", "recurse": False}],
            "fixture_directories": [],
            "fixture_files": {path: ""},
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    mapping = next(call["options"] for call in calls if call["module"] == "community.general.sefcontext")
    assert mapping["target"] == r"/opt/appdata/demo/config\.yml"
    restore = next(call["options"] for call in calls if call["module"] == "community.general.serestorecon")
    assert restore["path"] == path and restore["recurse"] is False
