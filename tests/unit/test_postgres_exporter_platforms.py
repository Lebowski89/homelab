"""Exercise the native exporter with the existing isolated host-operation fixture."""

import pytest
from test_postgres_platforms import facts, successful

pytest_plugins = ["test_system"]
pytestmark = pytest.mark.integration


def run(system_run, *, host_facts=None, overrides=None, check=False, main=False, tags="all"):
    return system_run(
        role="postgres_exporter",
        check=check,
        main=main,
        tags=tags,
        overrides={
            "ansible_facts": host_facts or facts(),
            "local_ip": "192.0.2.9",
            "postgres_exporter_database_user": "fixture_monitor",
            "postgres_exporter_database_name": "postgres",
            # A deterministic non-sensitive stand-in, never a database credential.
            "postgres_exporter_database_password": "check-mode-not-a-secret",
            **(overrides or {}),
        },
    )


@pytest.mark.parametrize(
    ("distro", "version", "backend"),
    [
        ("Debian", "13", "apt"),
        ("Ubuntu", "24.04", "apt"),
        ("Rocky", "9.7", "dnf"),
        ("Rocky", "10.2", "dnf"),
        ("Fedora", "43", "dnf"),
        ("Fedora", "44", "dnf5"),
    ],
)
def test_platform_packages_labels_and_unprivileged_unit(system_run, distro, version, backend):
    result, calls, _ = run(system_run, host_facts=facts(distro, version, backend))
    successful(result)
    packages = [call for call in calls if call["module"] in {"apt", "dnf"}]
    assert len(packages) == 1
    assert packages[0]["module"] == ("apt" if backend == "apt" else "dnf")
    assert packages[0]["options"]["state"] == "present"
    if backend != "apt":
        assert packages[0]["options"]["use_backend"] == ("dnf4" if backend == "dnf" else "dnf5")
        assert packages[0]["options"]["disable_gpg_check"] is False
        assert packages[0]["options"]["allowerasing"] is False
        assert "cache_valid_time" not in packages[0]["options"]
        labels = [call["options"] for call in calls if call["module"] == "community.general.serestorecon"]
        assert labels == [{"path": "/usr/local/bin/postgres_exporter", "recurse": False, "context": "full"}]
        assert next(i for i, call in enumerate(calls) if call["module"] == "community.general.serestorecon") < next(
            i for i, call in enumerate(calls) if call["module"] == "systemd_service"
        )
    else:
        assert not any(call["module"].startswith("community.general.se") for call in calls)
    archive = next(call["options"] for call in calls if call["module"] == "get_url")
    assert archive["checksum"].startswith("sha256:")
    assert ".linux-amd64.tar.gz" in archive["url"]
    unit = next(call["content"] for call in calls if call["module"] == "template" and "content" in call)
    assert "User=postgres_exporter" in unit
    assert "--web.listen-address=192.0.2.9:9187" in unit
    assert "NoNewPrivileges=true" in unit
    protected = [call for call in calls if call["module"] == "template" and call["no_log"]]
    assert len(protected) == 2 and all(call["diff"] is False for call in protected)
    assert all("content" not in call and "content_digest" in call for call in protected)
    assert not any(call["module"] in {"uri", "wait_for", "yum_repository", "deb822_repository"} for call in calls)


@pytest.mark.parametrize("failure", ["ostree", "derivative", "backend", "systemd", "old-release", "architecture", "checksum", "unit-path"])
def test_rejects_invalid_platform_or_pin_before_mutation(system_run, failure):
    host, overrides = facts(), {}
    if failure == "ostree":
        overrides["fixture_ostree"] = True
    elif failure == "derivative":
        host["distribution"] = "AlmaLinux"
    elif failure == "backend":
        host["pkg_mgr"] = "apt"
    elif failure == "systemd":
        host["service_mgr"] = "openrc"
    elif failure == "old-release":
        host = facts("Rocky", "10.0")
    elif failure == "architecture":
        host["architecture"] = "aarch64"  # The default archive remains AMD64.
    elif failure == "checksum":
        overrides["postgres_exporter_checksum"] = ""
    else:
        overrides["postgres_exporter_install_dir"] = "/opt/quoted'path"
    result, calls, _ = run(system_run, host_facts=host, overrides=overrides)
    assert result.returncode != 0
    assert {call["module"] for call in calls} <= {"setup", "stat"}


def test_overrides_render_through_to_installation_and_converge(system_run):
    overrides = {
        "postgres_exporter_version": "0.20.0",
        "postgres_exporter_release_base_url": "https://example.invalid/releases",
        "postgres_exporter_install_dir": "/opt/monitor/bin",
        "postgres_exporter_config_dir": "/etc/monitor",
        "postgres_exporter_user": "monitoring",
        "postgres_exporter_group": "monitoring",
        "postgres_exporter_listen_address": "192.0.2.99:19187",
        "postgres_exporter_arch": "arm64",
        "postgres_exporter_checksum": "sha256:" + "a" * 64,
    }
    host = facts(arch="aarch64")
    result, calls, _ = run(system_run, host_facts=host, overrides=overrides)
    successful(result)
    archive = next(call["options"] for call in calls if call["module"] == "get_url")
    assert archive["url"].startswith("https://example.invalid/releases/")
    assert archive["url"].endswith("0.20.0.linux-arm64.tar.gz")
    assert archive["checksum"] == overrides["postgres_exporter_checksum"]
    unit = next(call["content"] for call in calls if call["module"] == "template" and "content" in call)
    assert "User=monitoring" in unit
    assert "EnvironmentFile=/etc/monitor/environment" in unit
    assert "ExecStart=/opt/monitor/bin/postgres_exporter --web.listen-address=192.0.2.99:19187" in unit
    label = next(call["options"] for call in calls if call["module"] == "community.general.sefcontext")
    assert label["target"] == "/opt/monitor/bin/postgres_exporter"
    result, calls, _ = run(system_run, host_facts=host, overrides=overrides)
    successful(result)
    assert not any(call["module"] == "systemd" for call in calls)  # No restart handler on rerun.
    start = next(call["options"] for call in calls if call["module"] == "systemd_service")
    assert start["state"] == "started" and start["daemon_reload"] is False
    result, calls, _ = run(system_run, host_facts=host, overrides={**overrides, "postgres_exporter_listen_address": "192.0.2.99:29187"})
    successful(result)
    assert any(call["module"] == "systemd" and call["options"].get("state") == "restarted" for call in calls)


def test_check_mode_defers_credentials_download_and_all_host_mutations(system_run):
    result, calls, _ = run(
        system_run,
        check=True,
        overrides={"postgres_exporter_database_password": "{{ undefined_credential_must_not_be_resolved }}"},
    )
    successful(result)
    assert {call["module"] for call in calls} <= {"setup", "stat"}
    assert "Credential validation/rendering" in result.stdout
    assert "have not been verified" in result.stdout
    result, calls, _ = run(system_run, overrides={"postgres_exporter_database_password": ""})
    assert result.returncode != 0
    assert {call["module"] for call in calls} <= {"setup", "stat"}


@pytest.mark.parametrize("selinux", [{"status": "disabled"}, {"status": "unknown"}])
def test_selinux_status_is_respected_before_configuration(system_run, selinux):
    result, calls, _ = run(system_run, overrides={"fixture_selinux": selinux})
    if selinux["status"] == "disabled":
        successful(result)
        assert any(call["module"] == "systemd_service" for call in calls)
    else:
        assert result.returncode != 0
        assert not any(call["module"] in {"group", "user", "template", "systemd_service", "get_url"} for call in calls)
    assert not any(call["module"].startswith("community.general.se") for call in calls)


def test_existing_tagged_playbook_entry_point_check_mode_stays_outside_other_operations(system_run):
    result, calls, _ = run(system_run, main=True, tags="postgres_admin_monitor,postgres_exporter", check=True)
    successful(result)
    assert {call["module"] for call in calls} <= {"setup", "stat"}
    assert "checksum-pinned amd64 exporter" in result.stdout
