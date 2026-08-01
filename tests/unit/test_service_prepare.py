from __future__ import annotations

import importlib.util
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
DOCKER_PREP_PATH = REPO_ROOT / "ansible/roles/docker_services/tasks/_prep.yml"
PODMAN_MAIN_PATH = REPO_ROOT / "ansible/roles/podman_services/tasks/main.yml"
COMMON_PREFLIGHT_PATH = REPO_ROOT / "ansible/tasks/service_catalog_common_preflight.yml"
PLAYBOOK_PATH = REPO_ROOT / "ansible/playbook.yml"
SERVICES_DIR = REPO_ROOT / "ansible/group_vars/all/services"
PREPARE_FILTER_PATH = ROLE / "filter_plugins/service_prepare.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_service(name: str):
    return yaml.safe_load((SERVICES_DIR / f"{name}.yml").read_text())[name]


def task_named(tasks, name: str):
    return next(task for task in tasks if task.get("name") == name)


def iter_tasks(tasks):
    for task in tasks or []:
        if not isinstance(task, dict):
            continue
        yield task
        for section in ("block", "rescue", "always"):
            yield from iter_tasks(task.get(section))


def render_repository_value(value):
    environment = NativeEnvironment(undefined=StrictUndefined)
    variables = {
        "timezone": "UTC",
        "services_controller_host": "podman01",
        "services_plex_host": "podman01",
        "services_storage_host": "podman01",
        "services_log_root": "/opt/logs",
        "hostvars": {
            "podman01": {
                "container_host_appdata_root": "/opt/appdata",
                "container_host_data_root": "/opt/data",
                "container_host_puid": "1000",
                "container_host_pgid": "1000",
                "local_ip": "192.0.2.10",
            }
        },
    }
    if isinstance(value, dict):
        return {key: render_repository_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [render_repository_value(item) for item in value]
    if isinstance(value, str) and ("{{" in value or "{%" in value):
        return environment.from_string(value).render(variables)
    return value


def test_docker_preparation_declares_the_required_lifecycle_order():
    tasks = yaml.safe_load(DOCKER_PREP_PATH.read_text())
    names = [task["name"] for task in tasks]
    expected = [
        "Prep - Application validation | Validate current service",
        "Prep - Cleanup | Remove existing stack",
        "Prep - Application secrets | Run runtime-neutral generation",
        "Prep - Secrets | Materialize Docker-native secrets",
        "Prep - Application templates | Derive runtime-neutral values",
        "Prep - Service common | Prepare files and Traefik integration",
        "Prep - Application configuration | Apply runtime-neutral configuration",
    ]

    assert [names.index(name) for name in expected] == sorted(names.index(name) for name in expected)

    cleanup = task_named(tasks, "Prep - Cleanup | Remove existing stack")
    assert "not ansible_check_mode" in cleanup["when"]
    native = task_named(tasks, "Prep - Secrets | Materialize Docker-native secrets")
    assert "not ansible_check_mode" in native["when"]

    podman_tasks = yaml.safe_load(PODMAN_MAIN_PATH.read_text())
    podman_names = [task["name"] for task in podman_tasks]
    podman_expected = [
        "Podman services | Validate application preparation",
        "Podman services | Stop deployed service before recreate preparation",
        "Podman services | Generate runtime-neutral application secrets",
        "Podman services | Materialize Podman-native secrets",
        "Podman services | Derive runtime-neutral application template values",
        "Podman services | Prepare runtime-neutral host state",
        "Podman services | Apply runtime-neutral application configuration",
        "Podman services | Include preparation tasks",
        "Podman services | Include service lifecycle tasks",
    ]
    assert [podman_names.index(name) for name in podman_expected] == sorted(podman_names.index(name) for name in podman_expected)


def test_application_role_has_separated_outputs_and_runtime_modules_only_in_executors():
    application_files = [*ROLE.joinpath("tasks/applications").rglob("*.yml"), *ROLE.joinpath("library").glob("*.py")]
    application_text = "\n".join(path.read_text() for path in application_files)
    runtime_text = "\n".join(path.read_text() for path in ROLE.joinpath("tasks/runtimes").rglob("*.yml"))
    validation = yaml.safe_load((ROLE / "tasks/validate.yml").read_text())
    reset = task_named(validation, "Application prepare validation | Reset current-service outputs")

    assert reset["ansible.builtin.set_fact"] == {
        "service_prepare_template_vars": {},
        "service_prepare_generated_secret_values": {},
        "service_prepare_generated_secret_declarations": [],
        "service_prepare_bootstrap_requests": {},
    }
    assert "community.docker" not in application_text
    assert "containers.podman" not in application_text
    assert "infisical.vault.read_secrets" not in application_text
    assert "docker_services_" not in application_text
    assert "podman_services_" not in application_text
    assert "community.docker.docker_container" in runtime_text
    assert "containers.podman.podman_container" in runtime_text


def test_common_and_runtime_adapters_keep_the_revised_ownership_boundaries():
    common_files = [
        *REPO_ROOT.joinpath("ansible/roles/service_common/tasks").rglob("*.yml"),
        *REPO_ROOT.joinpath("ansible/roles/service_common/filter_plugins").rglob("*.py"),
    ]
    common_text = "\n".join(path.read_text().lower() for path in common_files)
    common_task_text = "\n".join(
        path.read_text().lower() for path in REPO_ROOT.joinpath("ansible/roles/service_common/tasks").rglob("*.yml")
    )
    docker_text = "\n".join(
        path.read_text().lower()
        for path in REPO_ROOT.joinpath("ansible/roles/docker_services").rglob("*")
        if path.is_file() and path.suffix in {".yml", ".py"}
    )

    assert "community.docker" not in common_text
    assert "containers.podman" not in common_text
    assert all(application not in common_task_text for application in ("authelia", "bazarr", "nzbhydra2"))
    assert all(application not in docker_text for application in ("authelia", "bazarr", "nzbhydra2"))


def test_controller_host_is_resolved_only_at_orchestration_boundary():
    playbook = yaml.safe_load(PLAYBOOK_PATH.read_text())
    deploy = next(play for play in playbook if play.get("name") == "Deploy homelab services")
    controller = task_named(deploy["tasks"], "Resolve runtime-neutral service controller host")
    preflight_text = COMMON_PREFLIGHT_PATH.read_text()
    docker_prep = DOCKER_PREP_PATH.read_text()
    podman_main = PODMAN_MAIN_PATH.read_text()

    expression = controller["ansible.builtin.set_fact"]["service_catalog_controller_host"]
    assert expression == "{{ services_controller_host }}"
    assert "docker_services_primary_manager" not in preflight_text
    assert 'service_common_controller_host: "{{ service_catalog_controller_host }}"' in preflight_text
    assert 'controller_host: "{{ docker_services_common_context.controller_host }}"' not in docker_prep
    assert 'controller_host: "{{ docker_services_controller_host }}"' in docker_prep
    assert 'controller_host: "{{ podman_services_controller_host }}"' in podman_main


def test_standalone_swarm_and_podman_use_the_same_generic_controller_contract():
    docker_init = (REPO_ROOT / "ansible/roles/docker_services/tasks/_init.yml").read_text()
    podman_init = (REPO_ROOT / "ansible/roles/podman_services/tasks/sub_tasks/init.yml").read_text()

    assert 'docker_services_controller_host: "{{ docker_services_common_context.controller_host }}"' in docker_init
    assert 'podman_services_controller_host: "{{ podman_services_common_context.controller_host }}"' in podman_init
    assert "docker_services_stack_deploy_type" not in COMMON_PREFLIGHT_PATH.read_text()
    assert "podman_services_" not in COMMON_PREFLIGHT_PATH.read_text()


def test_real_migrated_services_declare_only_the_six_application_handlers():
    expected = {
        "authelia": "authelia",
        "qbittorrent": "qbittorrent",
        "plex": "plex",
        "bazarr": "bazarr",
        "nzbhydra2": "nzbhydra2",
        "vaultwarden": "vaultwarden",
    }
    actual = {}

    for path in sorted(SERVICES_DIR.glob("*.yml")):
        for service_name, service in (yaml.safe_load(path.read_text()) or {}).items():
            declarations = []
            if service.get("application_prepare"):
                declarations.append(service["application_prepare"])
            declarations.extend(
                target["application_prepare"] for target in (service.get("targets") or {}).values() if target.get("application_prepare")
            )
            if declarations:
                actual[service_name] = {declaration["handler"] for declaration in declarations}

    assert actual == {name: {handler} for name, handler in expected.items()}


def test_real_migrated_docker_workflows_materialize_through_the_canonical_catalog():
    catalog = load_module(REPO_ROOT / "ansible/filter_plugins/service_catalog.py", "service_catalog_prepare_real")
    services = {name: load_service(name) for name in ("authelia", "qbittorrent", "plex", "bazarr", "nzbhydra2", "vaultwarden")}
    expected = {
        ("authelia", "main", "authelia"),
        ("qbittorrent", "downloads", "qbittorrent"),
        ("qbittorrent", "seeds", "qbittorrent"),
        ("plex", None, "plex"),
        ("bazarr", None, "bazarr"),
        ("nzbhydra2", None, "nzbhydra2"),
        ("vaultwarden", None, "vaultwarden"),
    }
    actual = set()

    for entry in catalog.service_catalog_effective(services, "manager"):
        effective = catalog.service_catalog_merge_target(services[entry["name"]], entry.get("target"))
        handler = (effective.get("application_prepare") or {}).get("handler")
        if handler:
            assert entry["runtime"] == "docker"
            assert effective["image"]
            assert "targets" not in effective
            actual.add((entry["name"], entry.get("target"), handler))

    assert actual == expected


def test_real_temporary_container_services_normalize_for_docker_and_podman():
    catalog = load_module(REPO_ROOT / "ansible/filter_plugins/service_catalog.py", "service_catalog_prepare_runtime_real")
    podman = load_module(
        REPO_ROOT / "ansible/roles/podman_services/filter_plugins/podman_services.py",
        "podman_prepare_runtime_real",
    )
    cases = (("authelia", "main"), ("bazarr", None), ("nzbhydra2", None))

    for service_name, target in cases:
        effective = catalog.service_catalog_merge_target(load_service(service_name), target)
        docker_effective = render_repository_value({**effective, "runtime": "docker"})
        podman_effective = render_repository_value({**effective, "runtime": "podman"})
        normalized = podman.podman_service_normalize(podman_effective, service_name)

        assert docker_effective["application_prepare"]["handler"] == service_name
        assert normalized["image"] == docker_effective["image"]
        assert normalized["container"]["host"] == "podman01"
        assert "targets" not in docker_effective


def test_qbittorrent_targets_retain_handler_inputs_and_instance_behavior():
    catalog = load_module(REPO_ROOT / "ansible/filter_plugins/service_catalog.py", "service_catalog_prepare_qbit")
    base = load_service("qbittorrent")

    downloads = catalog.service_catalog_merge_target(base, "downloads")
    seeds = catalog.service_catalog_merge_target(base, "seeds")

    assert downloads["application_prepare"]["handler"] == "qbittorrent"
    assert seeds["application_prepare"]["handler"] == "qbittorrent"
    assert downloads["name"] == "qbittorrent"
    assert seeds["name"] == "qbittorrent-xs"
    assert [entry["var"] for entry in downloads["infisical"]["secrets_map"]].count("qbittorrent_pass") == 1
    assert [entry["var"] for entry in seeds["infisical"]["secrets_map"]].count("qbittorrent_xs_pass") == 1
    assert downloads["volumes"]["media"]["target"] == "/data/torrents"
    assert seeds["volumes"]["media"]["target"] == "/data/seeds"


def test_runtime_executor_selection_names_and_output_parsing_are_behavioral():
    prepare = load_module(PREPARE_FILTER_PATH, "service_prepare_runtime_filters")

    assert prepare.service_prepare_runtime_executor("docker", "start") == "runtimes/docker/temporary_container_start.yml"
    assert prepare.service_prepare_runtime_executor("podman", "remove") == "runtimes/podman/temporary_container_remove.yml"
    with pytest.raises(prepare.AnsibleFilterError, match="runtime must be one of"):
        prepare.service_prepare_runtime_executor("containerd", "start")

    first = prepare.service_prepare_temporary_name("authelia", "main", "session-key")
    second = prepare.service_prepare_temporary_name("authelia", "main", "jwt-reset-key")
    assert first == prepare.service_prepare_temporary_name("authelia", "main", "session-key")
    assert first != second
    assert first.startswith("prepare-authelia-main-session-key-")
    assert len(first) <= 63

    output = "informational line\nRandom Value: synthetic-generated-value\n"
    assert prepare.service_prepare_extract_output(output, "Random Value: ") == "synthetic-generated-value"
    assert prepare.service_prepare_extract_output(output, "Digest: ") == ""


def test_temporary_executor_guarantees_cleanup_after_execution_block():
    tasks = yaml.safe_load((ROLE / "tasks/runtimes/temporary_container.yml").read_text())
    execute = task_named(tasks, "Temporary preparation container | Execute with guaranteed cleanup")
    start = task_named(execute["block"], "Temporary preparation container | Start selected runtime executor")
    failure = task_named(execute["rescue"], "Temporary preparation container | Report executor failure before cleanup")
    cleanup = task_named(execute["always"], "Temporary preparation container | Remove selected runtime executor")

    assert execute["when"] == "not ansible_check_mode"
    assert "service_prepare_runtime_executor('start')" in start["ansible.builtin.include_tasks"]["file"]
    assert "service_prepare_runtime_executor('remove')" in cleanup["ansible.builtin.include_tasks"]["file"]
    assert "ansible_failed_task.name" in failure["ansible.builtin.fail"]["msg"]
    assert "ansible_failed_result" not in failure["ansible.builtin.fail"]["msg"]

    for runtime in ("docker", "podman"):
        start_tasks = yaml.safe_load((ROLE / f"tasks/runtimes/{runtime}/temporary_container_start.yml").read_text())
        remove_tasks = yaml.safe_load((ROLE / f"tasks/runtimes/{runtime}/temporary_container_remove.yml").read_text())
        stale_remove = task_named(start_tasks, f"{runtime.title()} temporary preparation | Remove stale container")
        stale_verify = task_named(start_tasks, f"{runtime.title()} temporary preparation | Verify stale container is absent")
        runtime_start = task_named(start_tasks, f"{runtime.title()} temporary preparation | Start container")
        removal = task_named(remove_tasks, f"{runtime.title()} temporary preparation | Remove container")
        verification = task_named(remove_tasks, f"{runtime.title()} temporary preparation | Verify container is absent")

        assert "not ansible_check_mode" in runtime_start["when"]
        assert start_tasks.index(stale_remove) < start_tasks.index(stale_verify) < start_tasks.index(runtime_start)
        assert stale_remove["until"] == "service_prepare_temporary_stale_remove is succeeded"
        assert removal["until"] == "service_prepare_temporary_remove is succeeded"
        assert "failed_when" not in stale_remove
        assert "failed_when" not in removal
        assert removal["retries"] == 5
        assert verification["retries"] == 5
        assert verification["changed_when"] is False
        assert verification["failed_when"]
        assert remove_tasks.index(removal) < remove_tasks.index(verification)

        runtime_text = "\n".join(path.read_text() for path in (ROLE / f"tasks/runtimes/{runtime}").glob("*.yml"))
        assert "msg is not defined" not in runtime_text
        assert "failed_when: false" not in runtime_text


def test_temporary_cleanup_uses_runtime_information_modules_and_exact_names():
    expected = {
        "docker": ("community.docker.docker_container_info", "exists"),
        "podman": ("containers.podman.podman_container_info", "containers"),
    }

    for runtime, (module_name, absence_field) in expected.items():
        start_tasks = yaml.safe_load((ROLE / f"tasks/runtimes/{runtime}/temporary_container_start.yml").read_text())
        remove_tasks = yaml.safe_load((ROLE / f"tasks/runtimes/{runtime}/temporary_container_remove.yml").read_text())
        for tasks, name in (
            (start_tasks, f"{runtime.title()} temporary preparation | Verify stale container is absent"),
            (remove_tasks, f"{runtime.title()} temporary preparation | Verify container is absent"),
        ):
            verification = task_named(tasks, name)
            module_args = verification[module_name]
            assert "service_prepare_temporary_container.name" in str(module_args["name"])
            assert absence_field in str(verification["until"])
            assert absence_field in verification["failed_when"]
            assert verification["retries"] == 5
            assert verification["delay"] == 5


def test_podman_capture_uses_logs_command_and_never_module_stdout():
    podman_tasks = yaml.safe_load((ROLE / "tasks/runtimes/podman/temporary_container_start.yml").read_text())
    capture = task_named(podman_tasks, "Podman temporary preparation | Capture foreground output")
    publish = task_named(podman_tasks, "Podman temporary preparation | Publish foreground output")
    start = task_named(podman_tasks, "Podman temporary preparation | Start container")

    assert capture["ansible.builtin.command"]["argv"] == [
        "podman",
        "logs",
        "{{ service_prepare_temporary_container.name }}",
    ]
    assert capture["changed_when"] is False
    assert "service_prepare_temporary_container_capture is failed" in capture["failed_when"]
    assert "service_prepare_temporary_container_capture.rc | default(1) != 0" in capture["failed_when"]
    assert capture["no_log"] is True
    assert capture["diff"] is False
    assert publish["ansible.builtin.set_fact"]["service_prepare_temporary_container_output"] == (
        "{{ service_prepare_temporary_container_capture.stdout }}"
    )
    assert podman_tasks.index(start) < podman_tasks.index(capture) < podman_tasks.index(publish)
    assert (
        "service_prepare_temporary_container_result.stdout"
        not in (ROLE / "tasks/runtimes/podman/temporary_container_start.yml").read_text()
    )

    docker_tasks = yaml.safe_load((ROLE / "tasks/runtimes/docker/temporary_container_start.yml").read_text())
    docker_publish = task_named(docker_tasks, "Docker temporary preparation | Publish foreground output")
    assert (
        "service_prepare_temporary_container_result.container.Output"
        in docker_publish["ansible.builtin.set_fact"]["service_prepare_temporary_container_output"]
    )


def test_qbittorrent_derivation_precedes_common_templates_for_both_adapters():
    docker = DOCKER_PREP_PATH.read_text()
    podman = PODMAN_MAIN_PATH.read_text()

    assert docker.index("Derive runtime-neutral values") < docker.index("Prepare files and Traefik integration")
    assert podman.index("Derive runtime-neutral application template values") < podman.index("Prepare runtime-neutral host state")
    assert 'service_common_template_vars: "{{ docker_services_application_template_vars }}"' in docker
    assert 'service_common_template_vars: "{{ podman_services_application_template_vars }}"' in podman


def test_authelia_users_database_consumes_runtime_neutral_template_values():
    template = (REPO_ROOT / "ansible/roles/service_common/templates/configs/proxy/authelia/users_database.yml.j2").read_text()
    rendered = (
        NativeEnvironment(undefined=StrictUndefined)
        .from_string(template)
        .render(
            service_common_infisical_values={
                "authelia_display_name": "Synthetic User",
                "authelia_user": "synthetic-user",
                "smtp_email": "synthetic@example.invalid",
            },
            service_common_template_vars={"authelia_argon2_password": "SYNTHETIC_RUNTIME_HASH"},
        )
    )

    users = yaml.safe_load(rendered)["users"]
    assert users["synthetic-user"]["password"] == "SYNTHETIC_RUNTIME_HASH"


def test_vaultwarden_generation_returns_value_free_declaration_to_adapters():
    generation = (ROLE / "tasks/applications/vaultwarden/generate_secrets.yml").read_text()
    docker_secrets = (REPO_ROOT / "ansible/roles/docker_services/tasks/sub_tasks/prep/secrets.yml").read_text()
    podman_secrets = (REPO_ROOT / "ansible/roles/podman_services/tasks/sub_tasks/secrets/materialize.yml").read_text()

    publish = generation.index("Publish generated value and value-free declaration")
    declarations = generation.index("service_prepare_generated_secret_declarations", publish)
    assert "service_prepare_vaultwarden_token" not in generation[declarations:]
    assert "service_prepare_secret_declaration" in generation[declarations:]
    assert "runtime_options" not in generation[declarations:]
    assert "community.docker.docker_secret" in docker_secrets
    assert "containers.podman.podman_secret" in podman_secrets
    assert "community.docker" not in generation
    assert "containers.podman" not in generation


def test_authelia_publishes_values_and_value_free_declarations_for_normal_materializers():
    authelia = load_service("authelia")
    main = authelia["targets"]["main"]
    declarations = main["infisical"]["secrets_map"]
    generation = (ROLE / "tasks/applications/authelia/generate_secret.yml").read_text()
    docker_secrets = (REPO_ROOT / "ansible/roles/docker_services/tasks/sub_tasks/prep/secrets.yml").read_text()
    podman_secrets = (REPO_ROOT / "ansible/roles/podman_services/tasks/sub_tasks/secrets/materialize.yml").read_text()

    storage = next(entry for entry in declarations if entry["var"] == "authelia_storage_key")
    assert storage["secret"]["name"] == "authelia_storage_key_secret"
    declaration_section = generation.split("service_prepare_generated_secret_declarations:", 1)[1]
    assert "service_prepare_authelia_generated_value" not in declaration_section
    assert "service_prepare_secret_declaration" in declaration_section
    assert "runtime_options" not in declaration_section
    assert "immutable" not in declaration_section
    assert "replace" not in declaration_section
    assert "community.docker.docker_secret" in docker_secrets
    assert "docker_services_existing_secret_names" in docker_secrets
    assert "docker secret inspect" not in generation
    assert "containers.podman.podman_secret" in podman_secrets


def test_plex_volume_is_declarative_and_external_calls_are_bootstrap_only():
    plex = load_service("plex")
    volume = plex["named_volumes"]["media_nfs"]
    app_tasker = (ROLE / "tasks/applications/plex/tasker.yml").read_text()
    bootstrap = yaml.safe_load((ROLE / "tasks/bootstrap.yml").read_text())
    include = task_named(bootstrap, "Application bootstrap | Include explicit Plex bootstrap")

    assert volume["external"] is False
    assert volume["name"] == "media_nfs"
    assert volume["driver"] == "local"
    assert "192.168." not in (SERVICES_DIR / "plex.yml").read_text()
    assert "community.docker.docker_volume" not in app_tasker
    assert set(include["tags"]) == {"never", "bootstrap"}
    assert set(include["ansible.builtin.include_tasks"]["apply"]["tags"]) == {"bootstrap"}
    assert "not ansible_check_mode" in include["when"]


def test_bazarr_and_nzbhydra_runtime_bootstraps_follow_common_paths_and_precede_mutation():
    docker = DOCKER_PREP_PATH.read_text()
    common = docker.index("Prep - Service common | Prepare files and Traefik integration")
    configure = docker.index("Apply runtime-neutral configuration")
    bazarr_tasks = yaml.safe_load((ROLE / "tasks/applications/bazarr/configure.yml").read_text())
    nzbhydra_tasks = yaml.safe_load((ROLE / "tasks/applications/nzbhydra2/configure.yml").read_text())

    assert common < configure
    for tasks, application in ((bazarr_tasks, "Bazarr"), (nzbhydra_tasks, "NZBHydra2")):
        names = [task["name"] for task in tasks]
        initial_stat = names.index(f"Prep - {application} | Check whether initial config exists")
        generate = names.index(f"Prep - {application} | Generate absent initial config with selected runtime")
        verify = names.index(f"Prep - {application} | Verify runtime bootstrap produced config")
        mutation = next(index for index, name in enumerate(names) if index > verify and ("Configure" in name or "Set auth user" in name))
        assert initial_stat < generate < verify < mutation
        task = tasks[generate]
        assert task["when"] == f"not service_prepare_{application.lower()}_initial_config_stat.stat.exists"


def test_only_remaining_plex_podman_bootstrap_fails_explicitly():
    validation = yaml.safe_load((ROLE / "tasks/validate.yml").read_text())
    reject = task_named(validation, "Application prepare validation | Reject remaining Docker-only Plex bootstrap on Podman")

    assert "service_prepare_context.runtime == 'podman'" in reject["when"]
    assert "service_prepare_handler == 'plex'" in reject["when"]
    assert "runtime: podman" in reject["ansible.builtin.fail"]["msg"]


def test_new_dynamic_includes_propagate_operation_tags():
    files = [
        DOCKER_PREP_PATH,
        PODMAN_MAIN_PATH,
        ROLE / "tasks/validate.yml",
        ROLE / "tasks/generate_secrets.yml",
        ROLE / "tasks/derive_templates.yml",
        ROLE / "tasks/configure.yml",
        ROLE / "tasks/bootstrap.yml",
        ROLE / "tasks/runtimes/temporary_container.yml",
        ROLE / "tasks/applications/authelia/generate_secrets.yml",
        ROLE / "tasks/applications/authelia/generate_secret.yml",
        ROLE / "tasks/applications/authelia/derive_templates.yml",
        ROLE / "tasks/applications/bazarr/configure.yml",
        ROLE / "tasks/applications/bazarr/bootstrap.yml",
        ROLE / "tasks/applications/nzbhydra2/configure.yml",
        ROLE / "tasks/applications/nzbhydra2/bootstrap.yml",
        ROLE / "tasks/applications/plex/tasker.yml",
    ]

    for path in files:
        for task in yaml.safe_load(path.read_text()) or []:
            include = task.get("ansible.builtin.include_tasks") or task.get("ansible.builtin.include_role")
            if not isinstance(include, dict) or "apply" not in include:
                continue
            outer_tags = set(task.get("tags", []))
            applied_tags = set(include["apply"].get("tags", []))
            assert outer_tags, f"{path}: {task['name']} lacks outer tags"
            assert applied_tags, f"{path}: {task['name']} lacks apply.tags"
            assert applied_tags <= outer_tags, f"{path}: {task['name']} does not expose all applied tags"


def test_service_prepare_dynamic_includes_do_not_use_invalid_task_diff_attribute():
    for path in ROLE.joinpath("tasks").rglob("*.yml"):
        for task in iter_tasks(yaml.safe_load(path.read_text())):
            if "ansible.builtin.include_tasks" not in task:
                continue
            assert "diff" not in task, f"{path}: {task['name']} sets diff directly on TaskInclude"

    runtime_tasks = yaml.safe_load((ROLE / "tasks/runtimes/temporary_container.yml").read_text())
    execute = task_named(runtime_tasks, "Temporary preparation container | Execute with guaranteed cleanup")
    assert "diff" not in execute


def test_check_mode_guards_external_and_mutating_application_phases():
    docker_tasks = yaml.safe_load(DOCKER_PREP_PATH.read_text())
    podman_tasks = yaml.safe_load(PODMAN_MAIN_PATH.read_text())
    playbook = yaml.safe_load(PLAYBOOK_PATH.read_text())
    deploy = next(play for play in playbook if play.get("name") == "Deploy homelab services")

    guarded_docker = {"Prep - Cleanup | Remove existing stack", "Prep - Secrets | Materialize Docker-native secrets"}
    for name in guarded_docker:
        assert "not ansible_check_mode" in task_named(docker_tasks, name)["when"]

    podman_native = task_named(podman_tasks, "Podman services | Materialize Podman-native secrets")
    assert "not ansible_check_mode" in podman_native["when"]
    podman_cleanup = task_named(podman_tasks, "Podman services | Stop deployed service before recreate preparation")
    assert "not ansible_check_mode" in podman_cleanup["when"]

    runtime_execute = task_named(
        yaml.safe_load((ROLE / "tasks/runtimes/temporary_container.yml").read_text()),
        "Temporary preparation container | Execute with guaranteed cleanup",
    )
    assert runtime_execute["when"] == "not ansible_check_mode"
    deploy_all = task_named(deploy["tasks"], "Deploy all Docker stacks")
    assert "not ansible_check_mode" in deploy_all["when"]


def test_check_mode_selects_no_temporary_runtime_executor(tmp_path: Path):
    playbook = tmp_path / "temporary-container-check.yml"
    playbook.write_text(
        """---
- name: Exercise temporary executor check-mode contract
  hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: Validate Docker temporary request without execution
      ansible.builtin.include_role:
        name: service_prepare
        tasks_from: runtimes/temporary_container
      vars:
        service_prepare_context:
          runtime: docker
        service_prepare_temporary_container:
          name: prepare-synthetic-docker
          image: example.invalid/application:1.0.0
          command: generate
          host: localhost
          environment: {}
          mounts: []
          detach: false
          capture_output: true

    - name: Validate Podman temporary request without execution
      ansible.builtin.include_role:
        name: service_prepare
        tasks_from: runtimes/temporary_container
      vars:
        service_prepare_context:
          runtime: podman
        service_prepare_temporary_container:
          name: prepare-synthetic-podman
          image: example.invalid/application:1.0.0
          command: generate
          host: localhost
          environment: {}
          mounts: []
          detach: false
          capture_output: true

    - name: Validate Authelia declarations without generation
      ansible.builtin.include_role:
        name: service_prepare
        tasks_from: generate_secrets
      vars:
        service_prepare_handler: authelia
        service_prepare_template_vars: {}
        service_prepare_generated_secret_values: {}
        service_prepare_generated_secret_declarations: []
        service_prepare_bootstrap_requests: {}
        service_prepare_context:
          service_name: synthetic-authelia
          target: main
          runtime: docker
          service:
            image: example.invalid/authelia:1.0.0
          filesystem_hosts: [localhost]

"""
    )
    environment = os.environ.copy()
    environment.update(
        {
            "ANSIBLE_CONFIG": str(REPO_ROOT / "ansible/ansible.cfg"),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible-local"),
            "ANSIBLE_ROLES_PATH": str(REPO_ROOT / "ansible/roles"),
        }
    )

    result = subprocess.run(
        [str(Path(sys.executable).with_name("ansible-playbook")), "-i", "localhost,", str(playbook), "--check"],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "Authelia prepare | Generate runtime secret values" in output
    assert "Authelia prepare | Publish value-free declaration" in output
    assert "Docker temporary preparation | Start container" not in output
    assert "Podman temporary preparation | Start container" not in output
    assert "Docker temporary preparation | Remove stale container" not in output
    assert "Podman temporary preparation | Remove stale container" not in output
    assert "Docker temporary preparation | Verify container is absent" not in output
    assert "Podman temporary preparation | Verify container is absent" not in output
    assert "Podman temporary preparation | Capture foreground output" not in output
    assert "example.invalid" not in output


def test_validation_resets_seeded_outputs_without_mutation_or_external_calls(tmp_path: Path):
    playbook = tmp_path / "service-prepare-reset.yml"
    playbook.write_text(
        """---
- name: Exercise application output reset
  hosts: localhost
  connection: local
  gather_facts: false
  vars:
    service_prepare_context:
      service_name: plain
      runtime: docker
      operation: deploy
      service: {}
      resolved_environment: {}
      lookup_values: {}
      secret_declarations: []
      controller_host: localhost
      filesystem_hosts: [localhost]
      host_defaults:
        localhost: {}
  tasks:
    - name: Seed previous-service outputs
      no_log: true
      ansible.builtin.set_fact:
        service_prepare_template_vars:
          stale_template: synthetic-old-value
        service_prepare_generated_secret_values:
          stale_secret: synthetic-old-value
        service_prepare_generated_secret_declarations:
          - var: stale_secret
            name: stale_secret
        service_prepare_bootstrap_requests:
          stale: true

    - name: Validate following service
      ansible.builtin.include_role:
        name: service_prepare
        tasks_from: validate

    - name: Verify following service owns empty outputs
      ansible.builtin.assert:
        that:
          - service_prepare_template_vars == {}
          - service_prepare_generated_secret_values == {}
          - service_prepare_generated_secret_declarations == []
          - service_prepare_bootstrap_requests == {}
"""
    )
    environment = os.environ.copy()
    environment.update(
        {
            "ANSIBLE_CONFIG": str(REPO_ROOT / "ansible/ansible.cfg"),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible-local"),
            "ANSIBLE_ROLES_PATH": str(REPO_ROOT / "ansible/roles"),
        }
    )

    result = subprocess.run(
        [str(Path(sys.executable).with_name("ansible-playbook")), "-i", "localhost,", str(playbook), "--check"],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "synthetic-old-value" not in output
    assert "community.docker" not in output
    assert "containers.podman" not in output
    assert "infisical" not in output.lower()


def test_generated_application_secret_declarations_normalize_through_both_adapters():
    prepare = load_module(PREPARE_FILTER_PATH, "service_prepare_generated_declarations")
    common = load_module(
        REPO_ROOT / "ansible/roles/service_common/filter_plugins/service_common.py",
        "service_common_generated_declarations",
    )
    docker = load_module(
        REPO_ROOT / "ansible/roles/docker_services/filter_plugins/docker_services_secrets.py",
        "docker_generated_declarations",
    )
    podman = load_module(
        REPO_ROOT / "ansible/roles/podman_services/filter_plugins/podman_services.py",
        "podman_generated_declarations",
    )
    identities = [
        ("vaultwarden_admin_token", "vaultwarden_admin_token_secret"),
        ("authelia_session_key", "authelia_session_key_secret"),
        ("authelia_jwt_reset_key", "authelia_jwt_key_secret"),
    ]
    generated = [prepare.service_prepare_secret_declaration(variable, name) for variable, name in identities]
    expected = [
        {
            "var": variable,
            "name": name,
            "target": f"/run/secrets/{name}",
            "origins": ["canonical"],
            "update_policy": "preserve",
        }
        for variable, name in identities
    ]

    assert generated == expected
    assert all(set(declaration) == {"var", "name", "target", "origins", "update_policy"} for declaration in generated)

    for declaration in generated:
        common_declaration = common.service_common_infisical_normalize(
            [
                {
                    "var": declaration["var"],
                    "path": "/Synthetic",
                    "name": "SYNTHETIC_VALUE",
                    "secret": {"name": declaration["name"]},
                }
            ]
        )["secret_declarations"][0]
        assert common_declaration == declaration

    podman_declarations = podman.podman_secret_declarations(generated)
    assert podman_declarations == [
        {
            "name": declaration["name"],
            "var": declaration["var"],
            "target": declaration["target"],
            "update_policy": "preserve",
        }
        for declaration in generated
    ]
    assert docker.docker_services_secret_attachments([], generated, "swarm") == [name for _, name in identities]
    standalone = docker.docker_services_secret_attachments([], generated, "container")
    assert standalone == [{"source": name, "target": f"/run/secrets/{name}"} for _, name in identities]

    marker = "SYNTHETIC_SECRET_VALUE_MUST_NOT_APPEAR"
    assert marker not in repr(generated)
    assert marker not in repr(podman_declarations)
    assert marker not in repr(standalone)
    assert all("docker" not in repr(item).lower() for item in generated)
    assert all("podman" not in repr(item).lower() for item in generated)
