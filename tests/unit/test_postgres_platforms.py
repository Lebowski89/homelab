"""Exercise PostgreSQL platform choices with the existing isolated host fixture."""

import json
import os
import subprocess
import sys

import pytest
import yaml
from jinja2 import Environment, StrictUndefined
from test_system import REPO

pytest_plugins = ["test_system"]
pytestmark = pytest.mark.integration


def facts(distro="Rocky", version="10.2", backend="dnf", arch="x86_64"):
    return {
        "distribution": distro,
        "distribution_version": version,
        "distribution_major_version": version.split(".")[0],
        "distribution_release": {"Ubuntu": "resolute", "Debian": "trixie"}.get(distro, ""),
        "architecture": arch,
        "pkg_mgr": backend,
        "system": "Linux",
        "service_mgr": "systemd",
    }


def run(system_run, *, tags="postgres_install", host_facts=None, overrides=None, check=False):
    return system_run(
        role="postgres",
        tags=tags,
        check=check,
        overrides={
            "ansible_facts": host_facts or facts(),
            "local_ip": "192.0.2.9",
            "postgres_etcd_node_name": "localhost",
            "postgres_etcd_initial_cluster": "localhost=http://192.0.2.9:2380",
            **(overrides or {}),
        },
    )


def successful(result):
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    ("distro", "version", "backend", "arch"),
    [
        ("Ubuntu", "26.04", "apt", "x86_64"),
        ("Debian", "13", "apt", "aarch64"),
        ("Rocky", "9.7", "dnf", "x86_64"),
        ("Rocky", "10.2", "dnf", "aarch64"),
        ("Fedora", "43", "dnf", "x86_64"),
        ("Fedora", "44", "dnf5", "x86_64"),
    ],
)
def test_package_selection_and_install_only_boundary(system_run, distro, version, backend, arch):
    result, calls, _ = run(system_run, host_facts=facts(distro, version, backend, arch))
    successful(result)
    installs = [call for call in calls if call["module"] in {"apt", "dnf"} and "name" in call["options"]]
    assert installs and {call["module"] for call in installs} == {"apt" if backend == "apt" else "dnf"}
    assert all(call["options"]["state"] == "present" for call in installs)
    assert not any(call["module"] in {"systemd", "systemd_service", "wait_for", "template", "user", "uri"} for call in calls)
    assert all("initdb" not in str(call["options"].get("argv", [])) for call in calls)
    if backend == "apt":
        assert any(call["module"] == "deb822_repository" for call in calls)
        assert not any(call["module"] == "yum_repository" for call in calls)
        assert installs[-1]["options"]["policy_rc_d"] == 101
    else:
        packages = installs[-1]["options"]["name"]
        assert {"postgresql18-server", "postgresql18", "patroni", "patroni-etcd", "etcd"} <= set(packages)
        assert not {"etcd-server", "etcd-client", "postgresql-common", "python3-debian"} & set(packages)
        repos = [call["options"] for call in calls if call["module"] == "yum_repository"]
        assert {repo["name"] for repo in repos} == {
            "pgdg18",
            "pgdg-common",
            "pgdg-fedora-extras" if distro == "Fedora" else "pgdg-rhel" + version.split(".")[0] + "-extras",
        }
        assert all(repo["gpgcheck"] and repo["repo_gpgcheck"] and repo["sslverify"] for repo in repos)
        assert all(("/fedora/" if distro == "Fedora" else "/redhat/") in repo["baseurl"] for repo in repos)
        assert any(call["module"] == "rpm_key" and len(call["options"]["fingerprint"]) == 40 for call in calls)
        key = next(call["options"] for call in calls if call["module"] == "rpm_key")
        assert key["key"].endswith("AARCH64-RHEL") is (distro == "Rocky" and arch == "aarch64")
        assert all(call["options"]["use_backend"] == ("dnf5" if backend == "dnf5" else "dnf4") for call in installs)
        assert all(not call["options"]["allowerasing"] and not call["options"]["disable_gpg_check"] for call in installs)


@pytest.mark.parametrize(
    "failure",
    [
        "ostree",
        "derivative",
        "fedora45",
        "old-rocky",
        "backend",
        "systemd",
        "architecture",
        "server-conflict",
        "data-major",
        "binary-major",
        "path-change",
        "malformed-config",
        "etcd-relocation",
    ],
)
def test_unsupported_platform_or_migration_rejected_before_mutation(system_run, failure):
    host = facts()
    overrides = {}
    if failure == "ostree":
        overrides["fixture_ostree"] = True
    elif failure == "derivative":
        host["distribution"] = "AlmaLinux"
    elif failure == "fedora45":
        host = facts("Fedora", "45", "dnf5")
    elif failure == "old-rocky":
        host = facts("Rocky", "10.0")
    elif failure == "backend":
        host["pkg_mgr"] = "apt"
    elif failure == "systemd":
        host["service_mgr"] = "openrc"
    elif failure == "architecture":
        host["architecture"] = "s390x"
    elif failure == "server-conflict":
        overrides["fixture_packages"] = {"postgresql-server": [{"version": "16.9"}]}
    elif failure == "data-major":
        overrides["fixture_files"] = {"/var/lib/pgsql/18/data/PG_VERSION": "17\n"}
    elif failure == "binary-major":
        overrides.update(fixture_files={"/usr/pgsql-18/bin/postgres": "fixture"}, fixture_postgres_version="17.7")
    elif failure == "path-change":
        overrides["fixture_files"] = {
            "/etc/patroni/config.yml": yaml.safe_dump(
                {
                    "postgresql": {
                        "data_dir": "/var/lib/pgsql/17/data",
                        "bin_dir": "/usr/pgsql-17/bin",
                        "authentication": {"password": "NONPRODUCTION_SENTINEL"},
                    }
                }
            )
        }
    elif failure == "malformed-config":
        overrides["fixture_files"] = {"/etc/patroni/config.yml": "postgresql: [broken"}
    else:
        overrides.update(
            fixture_files={"/etc/etcd/etcd.conf": 'ETCD_DATA_DIR="/srv/existing-etcd"\n'}, fixture_directories=["/srv/existing-etcd/member"]
        )
    result, calls, _ = run(system_run, host_facts=host, overrides=overrides)
    assert result.returncode != 0
    assert {call["module"] for call in calls} <= {"setup", "stat", "slurp", "package_facts", "command"}
    assert all(call["options"]["argv"][-1] == "--version" for call in calls if call["module"] == "command")
    assert "NONPRODUCTION_SENTINEL" not in result.stdout + result.stderr


@pytest.mark.parametrize("backend", ["apt", "dnf", "dnf5"])
@pytest.mark.parametrize("tag", ["postgres_install", "postgres_apt", "postgres"])
def test_fresh_check_mode_defers_runtime_and_account_work(system_run, backend, tag):
    host = facts("Ubuntu", "26.04", "apt") if backend == "apt" else facts(backend=backend)
    result, calls, _ = run(system_run, host_facts=host, tags=tag, check=True)
    successful(result)
    assert {call["module"] for call in calls} <= {"setup", "stat", "package_facts", "include_tasks", "include_role"}
    assert "deferred" in result.stdout.lower()
    assert not any(call["module"] == "include_tasks" and call["options"].get("file") == "sub_tasks/backup_setup.yml" for call in calls)


def test_path_overrides_survive_rpm_rendering_and_default_service_is_versioned(system_run):
    overrides = {
        "postgres_patroni_data_dir": "/srv/pg-data",
        "postgres_patroni_bin_dir": "/opt/pg18/bin",
        "postgres_patroni_config_path": "/etc/patroni/selected.yml",
        "postgres_etcd_data_dir": "/srv/etcd-data",
        "fixture_files": {"/opt/pg18/bin/postgres": "fixture", "/srv/pg-data/PG_VERSION": "18\n"},
        "fixture_patroni_unit_config": "/etc/patroni/selected.yml",
    }
    result, calls, _ = run(system_run, tags="postgres_patroni", overrides=overrides)
    successful(result)
    rendered = {call["options"]["src"]: call["content"] for call in calls if call["module"] == "template"}
    config = yaml.safe_load(rendered["patroni.yml.j2"])
    assert config["postgresql"]["data_dir"] == "/srv/pg-data" and config["postgresql"]["bin_dir"] == "/opt/pg18/bin"
    assert "ExecStart=/usr/bin/patroni /etc/patroni/selected.yml" in rendered["patroni-rpm.conf.j2"]
    stopped = [
        call["options"]["name"] for call in calls if call["module"] == "systemd_service" and call["options"].get("state") == "stopped"
    ]
    assert stopped == ["postgresql-18"]
    assert not any(call["module"] in {"apt", "dnf", "uri"} for call in calls)
    assert any(call["module"].endswith("sefcontext") and call["options"]["target"].startswith("/srv/pg") for call in calls)
    # Re-render the same declared paths against the fixture's persisted files.
    # A changed template would notify the real restart handler on this rerun.
    result, calls, _ = run(system_run, tags="postgres_patroni", overrides=overrides)
    successful(result)
    assert not any(call["module"] == "systemd_service" and call["options"].get("state") == "restarted" for call in calls)


def test_running_standalone_server_is_not_stopped_or_adopted(system_run):
    result, calls, _ = run(
        system_run,
        tags="postgres_patroni",
        overrides={
            "fixture_files": {"/usr/pgsql-18/bin/postgres": "fixture"},
            "fixture_services": {"postgresql-18.service": {"state": "running"}},
        },
    )
    assert result.returncode != 0
    assert {call["module"] for call in calls} <= {"setup", "stat", "package_facts", "command", "service_facts"}


@pytest.mark.parametrize("conflict", ["config", "environment", "pass-environment", "envfile", "fragment"])
def test_effective_patroni_unit_cannot_bypass_declared_data_ownership(system_run, conflict):
    overrides = {"fixture_files": {"/usr/pgsql-18/bin/postgres": "fixture"}}
    if conflict == "config":
        overrides["fixture_patroni_unit_config"] = "/srv/other-patroni.yml"
    elif conflict == "environment":
        overrides["fixture_patroni_unit_environment"] = "PATRONI_POSTGRESQL_DATA_DIR=/srv/other-data"
    elif conflict == "pass-environment":
        overrides["fixture_patroni_unit_pass_environment"] = "PATRONI_POSTGRESQL_DATA_DIR"
    elif conflict == "envfile":
        overrides["fixture_files"]["/etc/patroni_env.conf"] = "NONPRODUCTION_SENTINEL"
    else:
        overrides["fixture_patroni_unit_fragment"] = "/etc/systemd/system/patroni.service"
    result, calls, _ = run(system_run, tags="postgres_patroni", overrides=overrides)
    assert result.returncode != 0
    assert {call["module"] for call in calls} <= {"setup", "stat", "package_facts", "command", "service_facts"}
    assert "NONPRODUCTION_SENTINEL" not in result.stdout + result.stderr


@pytest.mark.parametrize("tag", ["postgres_patroni_reset", "postgres_etcd_reset", "postgres_admin_nuke_node"])
def test_rpm_destructive_recovery_does_not_reuse_debian_commands(system_run, tag):
    result, calls, _ = run(system_run, tags=tag)
    assert result.returncode != 0
    assert {call["module"] for call in calls} <= {"setup", "stat"}


@pytest.mark.parametrize("backend", ["apt", "dnf", "dnf5"])
def test_backup_prerequisites_remain_scoped_to_the_selected_package_manager(system_run, backend):
    host = facts("Ubuntu", "26.04", "apt") if backend == "apt" else facts(backend=backend)
    result, calls, _ = run(system_run, tags="postgres_backup_setup", host_facts=host)
    successful(result)
    packages = [call for call in calls if call["module"] in {"apt", "dnf"}]
    assert len(packages) == 1 and packages[0]["options"]["name"] == "acl"
    assert packages[0]["module"] == ("apt" if backend == "apt" else "dnf")
    assert all(call["options"]["state"] == "present" for call in packages)


@pytest.mark.parametrize(
    ("backend", "version", "accepted"),
    [
        ("apt", "0.19.1", True),
        ("dnf5", "0.19.1+ds", True),
        ("dnf", "0.17.0", False),
    ],
)
def test_remote_backup_package_setup_does_not_require_a_repository_or_credentials(system_run, backend, version, accepted):
    host = facts("Ubuntu", "26.04", "apt") if backend == "apt" else facts("Fedora", "44", backend)
    result, calls, _ = run(
        system_run,
        tags="postgres_backup_remote_setup",
        host_facts=host,
        overrides={
            "postgres_backup_remote_manage": True,
            "postgres_backup_remote_repository": "",
            "fixture_restic_version": "restic " + version + " compiled with fixture",
        },
    )
    assert (result.returncode == 0) is accepted, result.stdout + result.stderr
    packages = [call for call in calls if call["module"] in {"apt", "dnf"}]
    assert len(packages) == 1 and packages[0]["options"]["name"] == "restic"
    assert packages[0]["module"] == ("apt" if backend == "apt" else "dnf")
    assert all(call["options"]["argv"][-1] == "version" for call in calls if call["module"] == "command")


def test_skynet_package_install_and_legacy_alias_keep_inventory_limit(tmp_path):
    defaults = yaml.safe_load((REPO / "ansible/roles/workstation/defaults/main.yml").read_text())
    values = {key: str(tmp_path / key) for key in defaults if key.startswith("workstation_")}
    values.update(workstation_repository_path=str(REPO), workstation_user_home=str(tmp_path / "home"))
    wrapper = tmp_path / "skynet"
    wrapper.write_text(
        Environment(undefined=StrictUndefined)
        .from_string((REPO / "ansible/roles/workstation/templates/skynet.j2").read_text())
        .render(**values)
    )
    record = tmp_path / "args.json"
    fake = tmp_path / "fake-ansible"
    fake.write_text(
        f"#!{sys.executable}\nimport json,sys\nfrom pathlib import Path\nPath({str(record)!r}).write_text(json.dumps(sys.argv[1:]))\n"
    )
    fake.chmod(0o755)
    for alias, tag in [("install", "postgres_install"), ("apt", "postgres_apt")]:
        result = subprocess.run(
            ["bash", str(wrapper), "limit", "rocky", "run", "postgres", alias],
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "ANSIBLE_PLAYBOOK_BIN": str(fake),
                "INVENTORY": "localhost,",
                "BECOME_PASS_FILE": str(tmp_path / "absent"),
                "VAULT_PASS_FILE": str(tmp_path / "absent"),
                "ANSIBLE_LOG_PATH": str(tmp_path / "ansible.log"),
            },
        )
        successful(result)
        arguments = json.loads(record.read_text())
        assert arguments[arguments.index("--tags") + 1] == tag
        assert arguments[arguments.index("--limit") + 1] == "rocky"
