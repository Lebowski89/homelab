"""Run actual container-role routing with the existing isolated host-operation fixture."""

import pytest

pytest_plugins = ["test_system"]
pytestmark = pytest.mark.integration


def facts(distro, version, backend=None):
    debian = distro in {"Debian", "Ubuntu", "LMDE", "Linux Mint"}
    return {
        "system": "Linux",
        "distribution": distro,
        "distribution_version": version,
        "distribution_major_version": version.split(".")[0],
        "distribution_release": {"Debian": "trixie", "Ubuntu": "resolute", "LMDE": "gigi"}.get(distro, ""),
        "os_family": "Debian" if debian else "RedHat",
        "pkg_mgr": backend or ("apt" if debian else "dnf"),
        "service_mgr": "systemd",
        "architecture": "x86_64",
        "kernel": "6.12.0-124.8.1.el10_1.x86_64",
    }


def run_role(system_run, role, distro="Rocky", version="10.1", backend=None, **kwargs):
    overrides = {
        "ansible_facts": facts(distro, version, backend),
        "fixture_files": {
            "/sys/fs/cgroup/cgroup.controllers": "",
            "/usr/lib/systemd/system-generators/podman-system-generator": "",
        },
        **kwargs.pop("overrides", {}),
    }
    return system_run(role=role, tags=f"{role}_install", overrides=overrides, **kwargs)


def successful(result):
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("role", ["docker", "podman"])
@pytest.mark.parametrize(
    "distro,version,backend",
    [
        ("Ubuntu", "26.04", "apt"),
        ("Debian", "13", "apt"),
        ("LMDE", "7", "apt"),
        ("Fedora", "43", "dnf5"),
        ("Rocky", "10.1", "dnf"),
        ("Rocky", "9.7", "dnf"),
    ],
)
def test_platform_packages_repository_selection_and_installation_boundary(system_run, role, distro, version, backend):
    result, calls, _ = run_role(system_run, role, distro, version, backend, main=True)
    successful(result)
    installs = [call for call in calls if call["module"] in {"apt", "dnf"} and "name" in call["options"]]
    assert installs
    assert all(call["options"]["state"] == "present" for call in installs)
    assert {call["module"] for call in installs} == {"apt" if backend == "apt" else "dnf"}
    assert not any(call["module"] in {"user", "group", "template", "copy", "include_tasks"} for call in calls)
    services = [call["options"] for call in calls if call["module"] in {"systemd", "systemd_service"}]
    module_probes = [call for call in calls if call["module"] == "command" and call["options"]["argv"][0] == "modinfo"]
    assert bool(module_probes) == (role == "docker" and distro == "Rocky" and version.startswith("10."))
    if role == "docker":
        assert services == [{"name": "docker.service", "enabled": True, "state": "started"}]
        repositories = [call for call in calls if call["module"] in {"deb822_repository", "yum_repository"}]
        assert len(repositories) == 1
        repository = repositories[0]["options"]
        if backend == "apt":
            assert repository["uris"].endswith("/ubuntu" if distro == "Ubuntu" else "/debian")
            assert repository["suites"] == ("resolute" if distro == "Ubuntu" else "trixie")
            assert repository["architectures"] == ["amd64"]
        else:
            assert repository["baseurl"].endswith(f"/{'fedora' if distro == 'Fedora' else 'rhel'}/$releasever/$basearch/stable")
            assert repository["gpgcheck"] is True
            assert any(call["module"] == "rpm_key" and call["options"]["fingerprint"] for call in calls)
    else:
        assert not services
        assert not any(call["module"] in {"get_url", "rpm_key", "yum_repository", "deb822_repository"} for call in calls)
        packages = installs[-1]["options"]["name"]
        assert {"podman", "crun", "netavark", "aardvark-dns", "passt"} <= set(packages)
        assert ("uidmap" in packages) == (backend == "apt")
        assert ("shadow-utils" in packages) == (backend != "apt")
        assert ("dbus-user-session" in packages) == (backend == "apt")
        assert ("dbus-broker" in packages) == (backend != "apt")
    if backend != "apt":
        for call in installs:
            assert call["options"]["use_backend"] == ("dnf5" if backend == "dnf5" else "dnf4")
            assert call["options"]["disable_gpg_check"] is False
            assert call["options"]["allowerasing"] is False
            assert "cache_valid_time" not in call["options"]
        assert not any(call["module"] in {"get_url", "deb822_repository", "lineinfile"} for call in calls)


@pytest.mark.parametrize("role", ["docker", "podman"])
@pytest.mark.parametrize(
    "failure", ["ostree", "derivative", "old-release", "backend", "systemd", "conflict", "override-conflict", "cgroup"]
)
def test_rejection_precedes_any_mutation(system_run, role, failure):
    host_facts = facts("Rocky", "10.1")
    overrides = {"ansible_facts": host_facts}
    if failure == "ostree":
        overrides["fixture_ostree"] = True
    elif failure == "derivative":
        host_facts["distribution"] = "AlmaLinux"
    elif failure == "old-release":
        host_facts.update(distribution="Fedora", distribution_major_version="40", distribution_version="40")
    elif failure == "backend":
        host_facts["pkg_mgr"] = "apt"
    elif failure == "systemd":
        host_facts["service_mgr"] = "openrc"
    elif failure == "conflict":
        overrides["fixture_packages"] = {"podman-docker": [{"version": "5.4.2"}]}
    elif failure == "override-conflict":
        overrides[f"{role}_packages"] = ["podman-docker"]
    elif failure == "cgroup":
        if role == "docker":
            overrides["fixture_packages"] = {"runc": [{"version": "1.2"}]}
        else:
            overrides["fixture_files"] = {}
    result, calls, _ = run_role(system_run, role, overrides=overrides)
    assert result.returncode != 0
    assert {call["module"] for call in calls} <= {"stat", "setup", "package_facts"}


@pytest.mark.parametrize("role", ["docker", "podman"])
@pytest.mark.parametrize("distro,version,backend", [("Debian", "13", "apt"), ("Fedora", "44", "dnf5"), ("Rocky", "10.1", "dnf")])
def test_fresh_check_mode_plans_install_without_runtime_or_package_side_effects(system_run, role, distro, version, backend):
    result, calls, _ = run_role(system_run, role, distro, version, backend, check=True, main=True, overrides={"fixture_podman_version": ""})
    successful(result)
    assert {call["module"] for call in calls} <= {"setup", "stat", "package_facts", "command"}
    assert all(
        call["options"]["argv"] in (["podman", "--version"], ["modinfo", "-F", "filename", "xt_addrtype"])
        for call in calls
        if call["module"] == "command"
    )
    assert "deferred" in result.stdout.lower()
    assert "packages" in result.stdout


@pytest.mark.parametrize("backend", ["apt", "dnf", "dnf5"])
def test_overrides_optional_compose_and_podman_install_disable(system_run, backend):
    distro, version = ("Debian", "13") if backend == "apt" else ("Rocky", "10.1")
    result, calls, _ = run_role(system_run, "docker", distro, version, backend, overrides={"docker_install_compose_plugin": False})
    successful(result)
    runtime = [call["options"] for call in calls if call["module"] in {"apt", "dnf"} and "docker-ce" in call["options"].get("name", [])]
    assert len(runtime) == 1 and "docker-compose-plugin" not in runtime[0]["name"]
    result, calls, _ = run_role(
        system_run,
        "docker",
        distro,
        version,
        backend,
        overrides={
            "docker_packages": ["docker-ce-cli"],
            "docker_prereq_packages": ["operator-prerequisite"],
            "docker_repo_url": "https://packages.example.test/docker",
            "docker_repo_channel": "test",
            "docker_manage_user": True,
            "docker_user": "operator",
        },
    )
    successful(result)
    installs = [call["options"]["name"] for call in calls if call["module"] in {"apt", "dnf"} and "name" in call["options"]]
    assert installs == [["operator-prerequisite"], ["docker-ce-cli"]]
    assert any(call["module"] == "user" and call["options"]["append"] is True for call in calls)
    repo = next(call["options"] for call in calls if call["module"] in {"deb822_repository", "yum_repository"})
    assert "https://packages.example.test/docker" in str(repo)
    result, calls, _ = run_role(
        system_run,
        "podman",
        distro,
        version,
        backend,
        overrides={
            "podman_packages": ["podman", "crun"],
            "podman_install_extra_packages": ["operator-package"],
            "podman_state": "latest",
            "podman_update_cache": False,
        },
    )
    successful(result)
    install = next(call["options"] for call in calls if call["module"] in {"apt", "dnf"})
    assert install["name"] == ["podman", "crun", "operator-package"]
    assert install["state"] == "latest" and install["update_cache"] is False
    result, calls, _ = run_role(system_run, "podman", distro, version, backend, overrides={"podman_install_enable": False})
    successful(result)
    assert not any(call["module"] in {"apt", "dnf"} for call in calls)
    assert any(call["module"] == "command" for call in calls)


def test_existing_docker_and_podman_coexist_and_missing_generator_is_rejected(system_run):
    for role, other in [("docker", "podman"), ("podman", "docker-ce")]:
        result, _, _ = run_role(system_run, role, overrides={"fixture_packages": {other: [{"version": "5"}], "crun": [{"version": "1"}]}})
        successful(result)
    result, _, _ = run_role(system_run, "podman", overrides={"fixture_files": {"/sys/fs/cgroup/cgroup.controllers": ""}})
    assert result.returncode != 0
    assert "generator not found" in result.stdout
    result, calls, _ = run_role(system_run, "podman", check=True, overrides={"fixture_podman_version": "podman version 5.4.1"})
    assert result.returncode != 0
    assert {call["module"] for call in calls} <= {"setup", "stat", "package_facts", "command"}
    result, calls, _ = run_role(
        system_run,
        "podman",
        overrides={
            "fixture_packages": {"containerd.io": [{"version": "2"}]},
            "podman_install_extra_packages": ["runc-1.3.0"],
        },
    )
    assert result.returncode != 0
    assert {call["module"] for call in calls} <= {"setup", "stat", "package_facts"}


def test_unraid_engine_remains_externally_managed(system_run):
    result, calls, _ = run_role(
        system_run,
        "docker",
        overrides={
            "ansible_facts": facts("Unraid", "7.2"),
            "fixture_files": {"/etc/unraid-version": "7.2"},
        },
        main=True,
    )
    successful(result)
    assert {call["module"] for call in calls} <= {"stat", "setup"}


@pytest.mark.parametrize("distro,version", [("Debian", "12"), ("Ubuntu", "24.04"), ("Rocky", "10.0")])
def test_podman_rejects_stock_releases_below_its_runtime_floor(system_run, distro, version):
    result, calls, _ = run_role(system_run, "podman", distro, version)
    assert result.returncode != 0
    assert {call["module"] for call in calls} <= {"stat", "setup"}


@pytest.mark.parametrize("tag", ["docker_swarm_init", "docker_swarm_join", "docker_swarm_network", "docker_swarm_labels"])
def test_swarm_suboperations_retain_preflight_without_selecting_installation(system_run, tag):
    result, calls, _ = system_run(role="docker", tags=tag, overrides={"ansible_facts": facts("Rocky", "10.1")})
    assert result.returncode != 0
    assert {call["module"] for call in calls} <= {"setup"}


def test_fedora_install_supplies_swarm_sdk_without_initialising_cluster(system_run):
    overrides = {
        "ansible_facts": facts("Fedora", "44", "dnf5"),
        "docker_swarm_primary_manager": "localhost",
        "local_ip": "192.0.2.44",
        "fixture_inventory_groups": ["tags_swarm_manager"],
        "fixture_require_docker_sdk": True,
    }
    result, _, _ = system_run(role="docker", tags="docker_swarm_init", overrides=overrides)
    assert result.returncode != 0
    result, calls, state = run_role(system_run, "docker", "Fedora", "44", "dnf5")
    successful(result)
    assert state.get("docker_sdk") and not state.get("swarm_active")
    assert not any(call["module"] == "community.docker.docker_swarm" for call in calls)
    result, calls, state = system_run(
        role="docker",
        tags="docker_swarm_init,docker_swarm_network,docker_swarm_labels",
        check=True,
        overrides={**overrides, "docker_swarm_node_labels": {"acceptance": "fedora"}},
    )
    successful(result)
    assert not state.get("swarm_active")
    assert not any(call["module"] in {"community.docker.docker_network_info", "community.docker.docker_node"} for call in calls)
    assert "deferred" in result.stdout
    result, calls, state = system_run(role="docker", tags="docker_swarm_init", overrides=overrides)
    successful(result)
    assert state["swarm_active"]
    assert not any(call["module"] in {"apt", "dnf"} for call in calls)


@pytest.mark.parametrize("backend,newer_installed", [("dnf", True), ("dnf5", False)], ids=["dnf4-newer-installed", "dnf5"])
def test_rocky_missing_module_installs_only_the_booted_kernel_supplement_before_startup(system_run, backend, newer_installed):
    overrides = {"fixture_addrtype_missing": True, "fixture_newer_kernel_supplement": newer_installed}
    result, calls, _ = run_role(system_run, "docker", backend=backend, overrides=overrides)
    successful(result)
    kernel_packages = [
        (index, call["options"])
        for index, call in enumerate(calls)
        if call["module"] == "dnf" and isinstance(call["options"].get("name"), str)
    ]
    assert len(kernel_packages) == 1
    kernel_index, options = kernel_packages[0]
    requirement = "kernel-modules-extra-uname-r = " + facts("Rocky", "10.1")["kernel"]
    assert options["name"] == requirement
    assert options["state"] == "present" and options["allowerasing"] is False
    assert options["disable_gpg_check"] is False and options["install_weak_deps"] is False
    start_index = next(index for index, call in enumerate(calls) if call["module"] == "systemd_service")
    assert kernel_index < start_index

    # The fixture persists installation state, so a subsequent run must not
    # request another supplement or any extra service operation.
    result, calls, _ = run_role(system_run, "docker", backend=backend, overrides=overrides)
    successful(result)
    assert not any(call["module"] == "dnf" and isinstance(call["options"].get("name"), str) for call in calls)
    assert all(call["options"]["state"] == "started" for call in calls if call["module"] == "systemd_service")


def test_rocky_missing_module_check_mode_defers_without_host_mutation(system_run):
    result, calls, state = run_role(system_run, "docker", check=True, overrides={"fixture_addrtype_missing": True})
    successful(result)
    assert {call["module"] for call in calls} <= {"setup", "stat", "package_facts", "command"}
    assert "kernel-modules-extra-uname-r = " + facts("Rocky", "10.1")["kernel"] in result.stdout
    assert "deferred" in result.stdout
    assert state == {}


@pytest.mark.parametrize(
    "failure", ["fixture_kernel_package_unavailable", "fixture_kernel_install_noop"], ids=["unavailable", "unverified"]
)
def test_unverified_running_kernel_stops_before_docker_repository_or_service_changes(system_run, failure):
    result, calls, _ = run_role(
        system_run,
        "docker",
        overrides={"fixture_addrtype_missing": True, failure: True},
    )
    assert result.returncode != 0
    assert {call["module"] for call in calls} <= {"setup", "stat", "package_facts", "command", "dnf"}
    installs = [call["options"]["name"] for call in calls if call["module"] == "dnf"]
    assert installs == ["kernel-modules-extra-uname-r = " + facts("Rocky", "10.1")["kernel"]]
    assert "maintenance" in result.stdout


def swarm_join(system_run, **kwargs):
    overrides = {
        "fixture_inventory_groups": ["tags_swarm_manager"],
        "docker_swarm_primary_manager": "localhost",
        "local_ip": "192.0.2.10",
        "docker_swarm_join_availability": "drain",
        **kwargs.pop("overrides", {}),
    }
    return system_run(role="docker", tags="docker_swarm_join", overrides=overrides, **kwargs)


def test_swarm_join_check_mode_does_not_retrieve_tokens_or_join(system_run):
    result, calls, state = swarm_join(system_run, check=True)
    successful(result)
    assert not any(call["module"] == "command" for call in calls)
    assert all(call["options"].get("method", "GET") == "GET" for call in calls if call["module"] == "uri")
    assert not state.get("swarm_active", False)
    assert "deferred" in result.stdout


def test_swarm_manager_join_is_drained_and_converges_without_tokens(system_run):
    result, calls, state = swarm_join(system_run)
    successful(result)
    joins = [call["options"] for call in calls if call["module"] == "uri" and call["options"].get("method") == "POST"]
    assert len(joins) == 1
    assert joins[0]["body"]["Availability"] == "drain"
    assert joins[0]["body"]["RemoteAddrs"] == ["192.0.2.10:2377"]
    assert state["swarm_role"] == "manager"
    assert not any(call["module"] in {"dnf", "apt", "community.docker.docker_network", "community.docker.docker_node"} for call in calls)
    assert "synthetic-test-token" not in result.stdout
    protected = [call for call in calls if call["module"] == "command" or call["options"].get("method") == "POST"]
    assert all(call["no_log"] is True and call["diff"] is False for call in protected)

    result, calls, _ = swarm_join(system_run)
    successful(result)
    assert not any(call["module"] == "command" for call in calls)
    assert not any(call["module"] == "uri" and call["options"].get("method") == "POST" for call in calls)


@pytest.mark.parametrize("overrides", [{"fixture_other_swarm": True}, {"fixture_swarm_existing_role": "worker"}])
def test_swarm_join_refuses_existing_membership_mismatch(system_run, overrides):
    result, calls, _ = swarm_join(system_run, overrides=overrides, state={"swarm_active": True})
    assert result.returncode != 0
    assert not any(call["module"] == "command" for call in calls)
    assert not any(call["module"] == "uri" and call["options"].get("method") == "POST" for call in calls)


def test_swarm_worker_join_preserves_active_default(system_run):
    result, calls, state = system_run(
        role="docker",
        tags="docker_swarm_join",
        overrides={
            "fixture_inventory_groups": ["tags_swarm_worker"],
            "docker_swarm_primary_manager": "primary",
            "local_ip": "192.0.2.10",
        },
        inventory_groups={"tags_swarm_manager": {"hosts": {"primary": {"local_ip": "192.0.2.1"}}}},
    )
    successful(result)
    assert state["swarm_role"] == "worker"
    assert state["swarm_availability"] == "active"
    tokens = [call["options"]["argv"] for call in calls if call["module"] == "command"]
    assert len(tokens) == 1 and tokens[0][-1] == "worker"
