"""Exercise utility metadata collection with every live operation replaced."""

import ast
import contextlib
import importlib.util
import io
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("utility_test", ROOT / "ansible/operator/utility-preparation.py")
UTILITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UTILITY)


def mask_fixture(tmp_path):
    import hashlib

    account = {"name": "fixture", "uid": os.getuid(), "gid": os.getgid(), "home": str(tmp_path)}
    source = tmp_path / ".config/containers/systemd/vaultwarden.container"
    source.parent.mkdir(parents=True)
    source.write_text("[Container]\nImage=fixture.invalid/app\n")
    mask = tmp_path / ".config/systemd/user/vaultwarden.service"
    mask.parent.mkdir(parents=True)
    mask.symlink_to("/dev/null")
    info = mask.lstat()
    record = {
        "account": account,
        "unit": "vaultwarden.service",
        "source": str(source),
        "masked_for_rollback": True,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "mask_identity": {key: getattr(info, key) for key in ["st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_ctime_ns"]},
    }
    state = {"LoadState": "masked", "ActiveState": "inactive", "SubState": "dead", "FragmentPath": str(mask), "SourcePath": ""}
    return account, source, mask, record, state


def test_recorded_mask_release_reloads_only_dedicated_manager(tmp_path, monkeypatch):
    account, source, mask, record, state = mask_fixture(tmp_path)
    unrelated = mask.parent / "unrelated.service"
    unrelated.symlink_to("/dev/null")
    calls = []

    def command(argv, operation):
        calls.append(argv)
        assert argv[:2] == ["fixture-account", "system-context"]
        if "daemon-reload" in argv:
            assert not mask.is_symlink() and unrelated.is_symlink()
            state.update(
                LoadState="loaded", SourcePath=str(source), FragmentPath=f"/run/user/{account['uid']}/systemd/generator/vaultwarden.service"
            )
            return ""
        assert "show" in argv and "vaultwarden.service" in argv
        return "\n".join(f"{key}={value}" for key, value in state.items())

    monkeypatch.setattr(UTILITY, "command", command)
    result = UTILITY.release_recorded_quadlet_mask(account, ["fixture-account", "system-context"], "vaultwarden", record)
    assert result["SourcePath"] == str(source) and unrelated.is_symlink()
    assert sum("daemon-reload" in call for call in calls) == 1
    assert not any("start" in call or "restart" in call for call in calls)


@pytest.mark.parametrize("change", ["unit", "owner", "source", "mask", "active", "fragment", "override"])
def test_recorded_mask_rejects_unexpected_ownership_without_removal(tmp_path, monkeypatch, change):
    account, source, mask, record, state = mask_fixture(tmp_path)
    if change == "unit":
        record["unit"] = "unrelated.service"
    elif change == "owner":
        record["mask_identity"]["st_uid"] += 1
    elif change == "source":
        source.write_text("[Container]\nImage=unexpected.invalid/app\n")
    elif change == "mask":
        mask.unlink()
        mask.symlink_to("/unexpected")
    elif change == "active":
        state["ActiveState"] = "active"
    elif change == "fragment":
        state["FragmentPath"] = "/unexpected/vaultwarden.service"
    else:
        override = tmp_path / ".config/systemd/user.control/vaultwarden.service"
        override.parent.mkdir(parents=True)
        override.symlink_to("/dev/null")
    monkeypatch.setattr(UTILITY, "command", lambda *args: "\n".join(f"{key}={value}" for key, value in state.items()))
    with pytest.raises(ValueError):
        UTILITY.release_recorded_quadlet_mask(account, [], "vaultwarden", record)
    assert mask.is_symlink()


def test_recorded_mask_reload_rejects_wrong_generated_source(tmp_path, monkeypatch):
    account, source, mask, record, state = mask_fixture(tmp_path)

    def command(argv, operation):
        if "daemon-reload" in argv:
            state.update(LoadState="loaded", SourcePath="/unexpected.container")
            return ""
        return "\n".join(f"{key}={value}" for key, value in state.items())

    monkeypatch.setattr(UTILITY, "command", command)
    with pytest.raises(ValueError, match="scoped rollback must remask"):
        UTILITY.release_recorded_quadlet_mask(account, [], "vaultwarden", record)
    assert not mask.is_symlink()  # Caller must enter scoped rollback; never start.


def test_recorded_mask_replacement_during_guard_is_not_removed(tmp_path, monkeypatch):
    account, source, mask, record, state = mask_fixture(tmp_path)
    calls = 0

    def command(argv, operation):
        nonlocal calls
        calls += 1
        if calls == 2:
            mask.unlink()
            mask.symlink_to("/unexpected")
        return "\n".join(f"{key}={value}" for key, value in state.items())

    monkeypatch.setattr(UTILITY, "command", command)
    with pytest.raises(ValueError, match="/dev/null mask"):
        UTILITY.release_recorded_quadlet_mask(account, [], "vaultwarden", record)
    assert os.readlink(mask) == "/unexpected"


def test_stable_configuration_read_allows_read_induced_atime(tmp_path):
    path = tmp_path / "alertmanager.yml"
    body = b"receivers: []\n"
    path.write_bytes(body)
    now = time.time()
    os.utime(path, (now - 3 * 86400, now - 2 * 86400))
    before = path.stat()
    snapshot = UTILITY.read_stable_config(path)
    after = path.stat()
    assert snapshot["body"] == body
    assert before.st_atime_ns != after.st_atime_ns
    assert snapshot == UTILITY.read_stable_config(path)
    assert "st_atime_ns" not in snapshot["identity"]


@pytest.mark.parametrize("change", ["contents", "replace", "mode"])
def test_stable_configuration_read_rejects_writer_or_identity_changes(tmp_path, monkeypatch, change):
    path = tmp_path / "alertmanager.yml"
    path.write_bytes(b"receivers: []\n")
    original = UTILITY.os.fstat
    calls = 0

    def fstat(descriptor):
        nonlocal calls
        calls += 1
        if calls == 2:
            if change == "contents":
                path.write_bytes(b"receivers: {}\n")
            elif change == "replace":
                other = tmp_path / "replacement"
                other.write_bytes(path.read_bytes())
                other.replace(path)
            else:
                path.chmod(path.stat().st_mode ^ 0o100)
        return original(descriptor)

    monkeypatch.setattr(UTILITY.os, "fstat", fstat)
    with pytest.raises(ValueError, match="changed"):
        UTILITY.read_stable_config(path)


def test_stable_configuration_read_rejects_symlink_and_oversize(tmp_path):
    path = tmp_path / "alertmanager.yml"
    path.write_bytes(b"receivers: []\n")
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(ValueError, match="regular file"):
        UTILITY.read_stable_config(link)
    with pytest.raises(ValueError, match="bounded"):
        UTILITY.read_stable_config(path, limit=1)


def test_alertmanager_file_projection_survives_atime_without_revealing_credentials(tmp_path):
    path = tmp_path / "alertmanager.yml"
    path.write_text("receivers:\n- name: fixture\n  webhook_configs:\n  - url: http://gotify:80/message?token=FAKE-SECRET\n")
    now = time.time()
    os.utime(path, (now - 3 * 86400, now - 2 * 86400))
    result = UTILITY.alertmanager_config_destinations(path)
    assert result["source"] == "current file; loaded destination not proved"
    assert result["webhooks"][0]["host"] == "gotify" and result["webhooks"][0]["port"] == 80
    assert result["webhooks"][0]["sensitive_components_present"] is True
    assert "FAKE-SECRET" not in json.dumps(result)


def test_alertmanager_invalid_yaml_error_does_not_include_source(tmp_path):
    path = tmp_path / "alertmanager.yml"
    path.write_text("FAKE-SECRET: [unclosed")
    with pytest.raises(ValueError, match="YAML malformed") as error:
        UTILITY.alertmanager_config_destinations(path)
    assert "FAKE-SECRET" not in str(error.value)


@pytest.mark.parametrize("url", ["<secret>", None, "/message", "https://example.test:bad", "https://example.test:0"])
def test_unusable_receiver_urls_preserve_safe_diagnosis(url):
    metadata = UTILITY.destination_metadata(url)
    assert metadata["reason"]
    assert metadata["port"] is None
    assert url is None or url not in json.dumps(metadata)


def test_receiver_metadata_does_not_expose_url_credentials_or_unknown_paths():
    url = "https://fixture-user:FAKE-SECRET@example.test:8443/FAKE-SECRET?token=FAKE-SECRET"
    metadata = UTILITY.destination_metadata(url)
    assert metadata["host"] == "example.test" and metadata["port"] == 8443
    assert metadata["sensitive_components_present"] is True
    assert metadata["path"] == "(unexpected path withheld)"
    assert "FAKE-SECRET" not in json.dumps(metadata) and "fixture-user" not in json.dumps(metadata)
    assert UTILITY.destination_metadata("http://alertmanager:9093/message")["path"] == "/message"


def test_published_route_producers_preserve_dns_failure_and_redacted_receiver(monkeypatch):
    source = (ROOT / "migrator/examples/route-producers.py").read_text()
    producers = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in ast.parse(source).body
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in {"api", "native"}
    }
    monkeypatch.setattr(UTILITY.os, "getuid", lambda: 1234)
    monkeypatch.setattr(
        UTILITY.socket, "getaddrinfo", lambda *args: (_ for _ in ()).throw(socket.gaierror(socket.EAI_NONAME, "FAKE-SECRET"))
    )
    monkeypatch.setattr(UTILITY.socket, "socket", lambda *args: pytest.fail("DNS failure must not attempt a connection"))
    monkeypatch.setattr(sys, "argv", ["fixture", "1234", "haproxy.example.test", "192.0.2.48", "5432"])
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exec(compile(producers["native"], "actual-native-producer", "exec"), {})
    result = json.loads(output.getvalue())
    assert result["result"] == "DNS lookup failed" and result["sql_proved"] is False
    assert "FAKE-SECRET" not in output.getvalue()

    body = json.dumps({"config": {"original": "receivers:\n- name: fixture\n  webhook_configs:\n  - url: <secret>\n"}}).encode()
    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: SimpleNamespace(open=lambda *args, **kw: io.BytesIO(body)))
    monkeypatch.setattr(sys, "argv", ["fixture", "alertmanager", "9093"])
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exec(compile(producers["api"], "actual-api-producer", "exec"), {})
    result = json.loads(output.getvalue())["delivery"][0]
    assert "redacted" in result["reason"] and result["host"] is None and result["port"] is None


@pytest.mark.parametrize("case", ["dns_failure", "wrong_address", "refused", "connected"])
def test_qualified_database_probe_retains_dns_and_socket_evidence(monkeypatch, case):
    monkeypatch.setattr(UTILITY.os, "getuid", lambda: 1234)
    closed, connected = [], []

    class Stream:
        def settimeout(self, value):
            assert value == 5

        def connect(self, destination):
            connected.append(destination)
            if case == "refused":
                raise ConnectionRefusedError("FAKE-SECRET")

        def getpeername(self):
            return "192.0.2.48", 5432

        def getsockname(self):
            return "192.0.2.48", 45000

        def close(self):
            closed.append(True)

    def resolver(*args):
        if case == "dns_failure":
            raise socket.gaierror(socket.EAI_NONAME, "FAKE-SECRET")
        return [(0, 0, 0, 0, ("192.0.2.99" if case == "wrong_address" else "192.0.2.48", 5432))]

    monkeypatch.setattr(UTILITY.socket, "getaddrinfo", resolver)
    monkeypatch.setattr(UTILITY.socket, "socket", Stream)
    monkeypatch.setattr(UTILITY, "load", lambda *args: SimpleNamespace(socket_uid=lambda stream: 1234))
    result = UTILITY.qualified_database_handshake(1234, "haproxy.example.test", "192.0.2.48", 5432)
    assert result["sql_proved"] is False and "FAKE-SECRET" not in json.dumps(result)
    if case == "dns_failure":
        assert result["result"] == "DNS lookup failed" and result["dns_error"]["code"] == socket.EAI_NONAME
    elif case == "wrong_address":
        assert result["resolved"] == ["192.0.2.99"] and result["result"] == "DNS destination differs"
    else:
        assert result["socket_uid"] == 1234 and result["source"] == ["192.0.2.48", 45000]
        assert result["result"] == ("connected" if case == "connected" else "ConnectionRefusedError")
    assert bool(connected) == bool(closed) == (case in {"refused", "connected"})


@pytest.mark.parametrize("failure", [None, "wrong_service", "multiple_projects", "different_cache_project", "missing_writer"])
def test_infisical_collection_requires_exact_compose_pair_and_preserves_policy(tmp_path, monkeypatch, failure):
    policy = {
        "schema": 1,
        "backend": "nf_tables",
        "inventory_host": "mgt",
        "inventory_address": "192.0.2.48",
        "inputs_verified": True,
        "endpoints": [{"ids": ["retained/backend"], "port": 12345, "callers": ["traefik"]}],
        "callers": {
            "traefik": [
                {"kind": "local", "phase": "podman", "account": "podman-fixture", "uid": 1234, "verified": True, "restart_verified": True}
            ]
        },
    }
    projection = {
        "host": "mgt",
        "address": "192.0.2.48",
        "services": {
            name: {
                "name": name,
                "execution": {"host_user": "fixture-" + name},
                "volumes": {},
                "ports": {"cache" if name.endswith("-redis") else "lookup": {"published": 16000 + offset}},
            }
            for offset, name in enumerate(UTILITY.INFISICAL_SERVICES)
        },
    }
    calls = []
    monkeypatch.setattr(UTILITY, "account_command", lambda account: (None, None))

    def command(argv, operation):
        calls.append(argv)
        if argv == ["ip", "-j", "address", "show"]:
            return json.dumps([{"addr_info": [{"local": "192.0.2.48"}]}])
        if "sha256sum" in argv:
            return "fixture-policy-hash"
        if "cat" in argv:
            return json.dumps(policy)
        if "info" in argv:
            return "mgt"
        if "service" in argv and "ls" in argv:
            return ""
        if "ps" in argv:
            selector = argv[argv.index("--filter") + 1]
            assert selector.startswith("label=com.docker.compose.service=")
            name = selector.split("=", 2)[-1]
            if failure == "missing_writer" and name == "infisical":
                return ""
            return name + ("\nextra" if failure == "multiple_projects" and name == "infisical" else "")
        if "ss" in argv:
            return ""
        pytest.fail("unexpected operation: " + operation)

    def container(prefix, cid, *, docker):
        assert docker
        return {
            "id": cid,
            "running": True,
            "swarm": "",
            "project": "other" if cid == "extra" or failure == "different_cache_project" and cid.endswith("-redis") else "observed",
            "service": "wrong" if failure == "wrong_service" and cid == "infisical" else cid,
        }

    monkeypatch.setattr(UTILITY, "command", command)
    monkeypatch.setattr(UTILITY, "container", container)
    if failure:
        with pytest.raises(ValueError, match="(exact Compose|projects differ)"):
            UTILITY.collect(tmp_path, projection)
    else:
        UTILITY.collect(tmp_path, projection)
        for name in UTILITY.INFISICAL_SERVICES:
            saved = json.loads((tmp_path / f"{name}.json").read_text())
            assert saved["docker"][0]["service"] == name
            assert saved["docker"][0]["project"] == "observed"
    inputs = json.loads((tmp_path / "policy-inputs.json").read_text())
    assert inputs["mgt_firewall_active_endpoints"] == ["retained/backend", "infisical-redis/cache", "infisical/lookup"]
    assert inputs["mgt_firewall_callers"] == policy["callers"]
    assert inputs["mgt_firewall_inputs_verified"] is policy["inputs_verified"]
    assert (tmp_path / "installed-policy.json").exists()
    assert not any(set(argv) & {"run", "start", "stop", "pull", "restart", "exec", "chown"} for argv in calls)


def test_projection_real_catalog_never_templates_environment_secrets(monkeypatch):
    from ansible.inventory import manager
    from ansible.plugins import loader
    from ansible.vars.manager import VariableManager

    monkeypatch.setattr(loader, "init_plugin_loader", lambda: None)
    host = SimpleNamespace(name="mgt")
    monkeypatch.setattr(
        manager, "InventoryManager", lambda **kw: SimpleNamespace(groups={"tags_ansible_manager": SimpleNamespace(hosts=[host])})
    )
    monkeypatch.setattr(VariableManager, "__init__", lambda self, **kw: None)
    monkeypatch.setattr(
        VariableManager,
        "get_vars",
        lambda self, **kw: {
            "local_ip": "192.0.2.48",
            "container_host_puid": 2345,
            "container_host_pgid": 3456,
            "container_host_appdata_root": "/fixture",
            "unrelated": "FAKE_SECRET_MUST_NOT_PROJECT",
        },
    )
    monkeypatch.setattr(UTILITY.socket, "gethostname", lambda: "mgt")
    selected = UTILITY.project()
    assert selected["services"]["thelounge"]["execution"]["userns"]["uid"] == 2345
    assert selected["services"]["thelounge"]["application_ids"] == {"PUID": 2345, "PGID": 3456}
    assert {v["source"] for v in selected["services"]["wallos"]["volumes"].values()} == {"/fixture/wallos/db", "/fixture/wallos/logos"}
    assert "FAKE_SECRET" not in json.dumps(selected)


@pytest.mark.parametrize("failure", [None, "address", "policy_changed", "docker_failure"])
def test_collection_preserves_union_and_partial_reports(tmp_path, monkeypatch, failure):
    binding = {
        "kind": "container",
        "phase": "docker",
        "runtime": "docker",
        "selector": "traefik_traefik",
        "verified": True,
        "restart_verified": True,
        "physdev_verified": True,
    }
    policy = {
        "schema": 1,
        "backend": "nf_tables",
        "inventory_host": "mgt",
        "inventory_address": "192.0.2.48",
        "inputs_verified": False,
        "endpoints": [{"ids": ["unrelated/backend"], "port": 12345, "callers": ["traefik"]}],
        "callers": {"traefik": [binding]},
    }
    projection = {
        "host": "mgt",
        "address": "192.0.2.48",
        "services": {
            name: {"name": name, "execution": {"host_user": "fixture-" + name}, "volumes": {}, "ports": [{"published": 1234}]}
            for name in UTILITY.SERVICES
        },
    }
    real_read = Path.read_text
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda self, *a, **kw: "FIXTURE_BOOT" if str(self) == "/proc/sys/kernel/random/boot_id" else real_read(self, *a, **kw),
    )
    monkeypatch.setattr(UTILITY.socket, "gethostname", lambda: "mgt")
    monkeypatch.setattr(UTILITY, "account_command", lambda account: (None, None))
    calls, reads = [], 0

    def command(argv, operation):
        nonlocal reads
        calls.append(argv)
        if argv == ["ip", "-j", "address", "show"]:
            return json.dumps([{"addr_info": [{"local": "192.0.2.99" if failure == "address" else "192.0.2.48"}]}])
        if argv[-2:] == ["sha256sum", "/etc/skynet-mgt-firewall/policy.json"]:
            return "fixture-hash  /etc/skynet-mgt-firewall/policy.json"
        if argv[-2:] == ["cat", "/etc/skynet-mgt-firewall/policy.json"]:
            reads += 1
            return json.dumps({**policy, "inputs_verified": True} if failure == "policy_changed" and reads > 1 else policy)
        if "info" in argv:
            return "mgt"
        if "service" in argv and "ls" in argv:
            return ""
        if "ps" in argv:
            if failure == "docker_failure" and "name=(^|[/_-])thelounge([._-]|$)" in argv:
                raise RuntimeError("fixture Docker failure")
            return ""
        if "ss" in argv:
            return ""
        pytest.fail(f"unexpected operation: {operation}")

    monkeypatch.setattr(UTILITY, "command", command)
    if failure:
        with pytest.raises((ValueError, RuntimeError)):
            UTILITY.collect(tmp_path, projection)
    else:
        UTILITY.collect(tmp_path, projection)
    if failure != "address":
        inputs = json.loads((tmp_path / "policy-inputs.json").read_text())
        assert inputs["mgt_firewall_callers"] == policy["callers"]
        assert inputs["mgt_firewall_inputs_verified"] is False
        assert inputs["mgt_firewall_active_endpoints"] == ["unrelated/backend", "adminer/backend", "thelounge/backend", "wallos/backend"]
    if failure in {"docker_failure", "policy_changed"}:
        assert (tmp_path / "adminer.json").exists()
    if failure == "docker_failure":
        assert (tmp_path / "wallos.json").exists()
        assert (tmp_path / "thelounge-error.json").exists()
    assert not any(set(argv) & {"run", "start", "stop", "pull", "restart", "exec", "chown"} for argv in calls)


@pytest.mark.parametrize("replacement", [False, True])
@pytest.mark.parametrize("docker", [False, True])
def test_container_projection_and_continuity(monkeypatch, replacement, docker):
    cid = "c" * 64
    reads = 0

    def command(argv, operation):
        nonlocal reads
        if "inspect" in argv and "container" in argv:
            if docker:
                assert ".Id" in argv[-2] and ".ID" not in argv[-2]
            else:
                assert ".ID" in argv[-2] and ".Id" not in argv[-2]
            reads += 1
            return json.dumps({"id": cid, "pid": 44 if reads == 1 or not replacement else 45, "running": True, "image_id": "fixture-image"})
        if "image" in argv:
            return "[]"
        if "top" in argv:
            return "PID UID GID COMMAND\n44 2034 2035 fixture" if docker else "HPID\n44"
        if argv[-1].endswith("status"):
            return "Name:\tfixture\nUid:\t2034\t2034\t2034\t2034\nGid:\t2035\t2035\t2035\t2035"
        if argv[-1].endswith("_map"):
            return "0 2034 65536"
        pytest.fail(operation)

    monkeypatch.setattr(UTILITY, "command", command)
    monkeypatch.setattr(UTILITY, "context", lambda pid: {"pid": pid, "birth": "5", "netns": "ns-fixture"})
    if replacement:
        with pytest.raises(ValueError, match="changed"):
            UTILITY.container(["FAKE_RUNTIME"], cid, docker=docker)
    else:
        report = UTILITY.container(["FAKE_RUNTIME"], cid, docker=docker)
        assert report["processes"][0]["uid"] == (2034 if docker else [2034] * 4)


@pytest.mark.parametrize(
    "case,stage,success",
    [
        ("present", False, True),
        ("initialized_loki", False, True),
        ("initialized_loki_running", False, False),
        ("initialized_loki_replacement", False, False),
        ("non_root_alertmanager", False, True),
        ("alertmanager_mount_order", False, True),
        ("alertmanager_mount_source", True, False),
        ("alertmanager_mount_rw", True, False),
        ("alertmanager_mount_propagation", True, False),
        ("alertmanager_mount_missing_rw", True, False),
        ("alertmanager_mount_mistyped_rw", True, False),
        ("alertmanager_mount_duplicate", True, False),
        ("missing", True, True),
        ("missing", False, False),
        ("image_error", True, False),
        ("wrong_map", True, False),
        ("probe_replacement", True, False),
        ("probe_mount", True, False),
        ("probe_network", True, False),
        ("docker_replacement", True, False),
        ("account_changed", True, False),
        ("boot_changed", True, False),
        ("ranges_changed", True, False),
        ("wrong_digest", True, False),
        ("cleanup_failure", True, False),
        ("probe_interrupt", True, False),
        ("create_timeout", True, False),
        ("start_timeout", True, False),
        ("unowned_collision", True, False),
        ("ambiguous_cleanup", True, False),
        ("expired_cleanup", True, True),
        ("image_update_authorized", True, True),
        ("image_update_ambiguous", True, False),
        ("image_update_no_optin", True, False),
    ],
)
def test_wallos_selected_map_is_explicit_scoped_and_retains_evidence(tmp_path, monkeypatch, case, stage, success):
    mapping = UTILITY.load("ansible/operator/znc-mapping-proof.py", "utility_test_numeric_maps")
    monkeypatch.setattr(UTILITY, "load", lambda *args: mapping)
    service = "alertmanager" if case == "non_root_alertmanager" or case.startswith("alertmanager_mount_") else "wallos"
    initialized = case.startswith("initialized_loki")
    if initialized:
        service = "loki"
    if case.startswith("image_update_"):
        service = "autobrr"
    inside = 1000 if service in {"alertmanager", "autobrr", "loki"} else 82
    cfg = {
        "name": service,
        "image": "docker.io/fixture/wallos:4.9.6@sha256:" + "a" * 64,
        "user": "1000:1000" if service in {"alertmanager", "loki"} else "0:0",
        "execution": {"host_user": "podman-fixture", "userns": {"mode": "keep-id", "uid": str(inside), "gid": str(inside)}},
    }
    account = {"name": "podman-fixture", "uid": 2468, "gid": 3456, "home": "/fixture/home"}
    old = {
        "id": "d" * 64,
        "running": True,
        "repo_digests": ["fixture/wallos@sha256:" + "a" * 64],
        "identity": {"pid": 91, "birth": "original", "netns": "old-ns"},
        "maps": {"uid": "0 0 65536", "gid": "0 0 65536"},
        "swarm": "wallos_wallos",
        "mounts": [],
        "image_id": "fixture-image",
    }
    if case.startswith("image_update_"):
        cfg["image"] = "registry.example/autobrr:1.87"
        cfg["user"] = "1000:1000"
        old["image"] = "registry.example/autobrr:1.86@sha256:" + "a" * 64
    if case.startswith("alertmanager_mount_"):
        # Captured Docker records: the order of these two mounts is incidental.
        old["mounts"] = [
            {
                "Type": "bind",
                "Source": "/opt/alertmanager",
                "Destination": "/etc/alertmanager",
                "RW": False,
                "Mode": "",
                "Propagation": "rprivate",
            },
            {
                "Type": "bind",
                "Source": "/opt/alertmanager/data",
                "Destination": "/alertmanager",
                "RW": True,
                "Mode": "",
                "Propagation": "rprivate",
            },
        ]
    if case == "wrong_digest":
        old["repo_digests"] = ["fixture/wallos@sha256:" + "b" * 64]
    saved = {"account": account, "ranges": {"uid": "fixture-uid", "gid": "fixture-gid"}, "docker": [old]}
    for name, data in {
        "selected.json": {"host": "fixture", "address": "192.0.2.48", "services": {service: cfg}},
        f"{service}.json": saved,
        "host.json": {"hostname": "fixture", "boot_id": "BOOT"},
    }.items():
        (tmp_path / name).write_text(json.dumps(data))
    retained = {p: p.read_bytes() for p in tmp_path.iterdir()}
    real_read = Path.read_text
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda self, *a, **kw: (
            ("CHANGED" if case == "boot_changed" else "BOOT")
            if str(self) == "/proc/sys/kernel/random/boot_id"
            else real_read(self, *a, **kw)
        ),
    )
    monkeypatch.setattr(UTILITY.socket, "gethostname", lambda: "fixture")
    monkeypatch.setattr(
        UTILITY, "account_command", lambda name: ({**account, "uid": 999} if case == "account_changed" else account, ["FAKE_ACCOUNT"])
    )

    def current_container(*args, **kwargs):
        current = deepcopy(old)
        if case == "docker_replacement":
            current["identity"] = {}
        if case == "alertmanager_mount_order":
            current["mounts"].reverse()
        elif case == "alertmanager_mount_source":
            current["mounts"][1]["Source"] = "/opt/unrelated-data"
        elif case == "alertmanager_mount_rw":
            current["mounts"][0]["RW"] = True
        elif case == "alertmanager_mount_propagation":
            current["mounts"][1]["Propagation"] = "rshared"
        elif case == "alertmanager_mount_missing_rw":
            del current["mounts"][1]["RW"]
        elif case == "alertmanager_mount_mistyped_rw":
            current["mounts"][0]["RW"] = 0
        elif case == "alertmanager_mount_duplicate":
            current["mounts"].append(deepcopy(current["mounts"][1]))
        return current

    monkeypatch.setattr(UTILITY, "container", current_container)
    monkeypatch.setattr(UTILITY, "context", lambda pid: {"pid": pid, "birth": "probe", "netns": "probe-ns"})
    calls, inspections = [], 0
    cid = "c" * 64
    output = tmp_path / "new-map"
    output.mkdir()

    def command(argv, operation):
        calls.append(argv)
        if "awk" in argv:
            return "changed" if case == "ranges_changed" else saved["ranges"]["uid" if argv[-1].endswith("uid") else "gid"]
        if argv[-1].endswith("_map"):
            outside = (999 if case == "wrong_map" else account["uid"]) if argv[-1].endswith("uid_map") else account["gid"]
            return f"0 700000 {inside}\n{inside} {outside} 1\n{inside + 1} 701000 {65535 - inside}"
        pytest.fail(operation)

    def runtime(argv, *, operation, timeout=30):
        nonlocal inspections
        calls.append(argv)
        if "image" in argv and "inspect" in argv:
            assert case.startswith("image_update_")
            refs = ["registry.example/autobrr@sha256:" + "b" * 64]
            if case == "image_update_ambiguous":
                refs.append("registry.example/autobrr@sha256:" + "c" * 64)
            return json.dumps(
                {"refs": refs, "tags": [cfg["image"]], "digest": "" if case == "image_update_ambiguous" else "sha256:" + "b" * 64}
            )
        if "exists" in argv:
            if case in {"missing", "image_error"} and not any("pull" in call for call in calls):
                raise mapping.CommandFailure(
                    operation, 125 if case == "image_error" else 1, "fixture failure" if case == "image_error" else ""
                )
            return ""
        if "pull" in argv:
            assert stage and timeout == 600
            assert argv[-1] == cfg["image"]
            return "fixture staged"
        if "create" in argv:
            assert "--network=none" in argv and "--image-volume=ignore" in argv and "--pull=never" in argv and "--rm" in argv
            assert f"--userns=keep-id:uid={inside},gid={inside}" in argv
            assert "--volume" not in argv and "--publish" not in argv
            if initialized:
                assert "--entrypoint=/bin/sleep" not in argv and argv[-1] == cfg["image"]
            else:
                assert "--entrypoint=/bin/sleep" in argv and argv[-1] == "120"
            if case in {"create_timeout", "unowned_collision", "ambiguous_cleanup"}:
                raise subprocess.TimeoutExpired(argv, 30)
            return cid
        if "start" in argv or "init" in argv:
            assert ("init" in argv) is initialized
            assert argv[-1] == cid
            assert json.loads((output / "probe-created.json").read_text())["id"] == cid
            if case == "start_timeout":
                raise subprocess.TimeoutExpired(argv, 30)
            return cid
        if "ps" in argv:
            assert ("id=" + cid in argv) == (case not in {"create_timeout", "unowned_collision", "ambiguous_cleanup"})
            if case == "expired_cleanup":
                return ""
            return cid + "\n" + "e" * 64 if case == "ambiguous_cleanup" else cid
        if "inspect" in argv:
            assert "container" in argv and ".ID" in argv[-2] and argv[-1] == cid
            if "owner" in argv[-2]:
                return json.dumps(
                    {"id": cid, "name": f"skynet-{service}-map-new-map", "owner": "OTHER" if case == "unowned_collision" else "new-map"}
                )
            if case == "probe_interrupt":
                raise KeyboardInterrupt
            inspections += 1
            if initialized:
                return json.dumps(
                    {
                        "id": cid,
                        "pid": 501 if case == "initialized_loki_replacement" and inspections > 1 else 500,
                        "running": case == "initialized_loki_running",
                        "status": "initialized",
                        "mounts": [],
                        "network": "none",
                    }
                )
            return json.dumps(
                {
                    "id": cid,
                    "pid": 501 if case == "probe_replacement" and inspections > 1 else 500,
                    "running": True,
                    "mounts": [{"Source": "/unapproved"}] if case == "probe_mount" else [],
                    "network": "bridge" if case == "probe_network" else "none",
                }
            )
        if "rm" in argv:
            assert argv[-1] == cid and "--ignore" in argv
            if case == "cleanup_failure":
                raise RuntimeError("fixture cleanup failure")
            return ""
        pytest.fail(operation)

    monkeypatch.setattr(UTILITY, "command", command)
    monkeypatch.setattr(mapping, "command", runtime)
    monkeypatch.setattr(UTILITY, "probe_command", lambda argv, output, phase: runtime(argv, operation=phase))
    if success:
        UTILITY.prove_map(
            tmp_path,
            output,
            {"host": "fixture", "address": "192.0.2.48", "services": {service: cfg}},
            service,
            stage_image=stage,
            allow_image_update=case in {"image_update_authorized", "image_update_ambiguous"},
            initialize_only=initialized,
        )
        assert json.loads((output / "result.json").read_text())["probe_removed"] is True
        if case == "image_update_authorized":
            assert json.loads((output / "selected.json").read_text())["image"] == "registry.example/autobrr:1.87@sha256:" + "b" * 64
        assert mapping.mapped(inside, (output / "selected.uid_map").read_text()) == account["uid"]
    else:
        with pytest.raises(KeyboardInterrupt if case == "probe_interrupt" else (ValueError, RuntimeError, subprocess.TimeoutExpired)):
            UTILITY.prove_map(
                tmp_path,
                output,
                {"host": "fixture", "address": "192.0.2.48", "services": {service: cfg}},
                service,
                stage_image=stage,
                allow_image_update=case in {"image_update_authorized", "image_update_ambiguous"},
                initialize_only=initialized,
            )
        assert not (output / "result.json").exists()
    if case.startswith("alertmanager_mount_"):
        report = json.loads((output / "writer-continuity.json").read_text())
        assert report["saved"]["mounts"] == old["mounts"]
        assert report["current"]["mounts"] == current_container()["mounts"]
        if not success:
            assert not any(set(argv) & {"exists", "pull", "create", "start", "rm"} for argv in calls)
    assert all(path.read_bytes() == content for path, content in retained.items())
    assert not any(set(argv) & {"chown", "run", "stop", "restart", "deploy", "exec"} for argv in calls)
    if any("create" in argv for argv in calls):
        assert any("rm" in argv for argv in calls) == (case not in {"unowned_collision", "ambiguous_cleanup", "expired_cleanup"})


def test_probe_startup_does_not_wait_for_child_inherited_output(tmp_path):
    """Execute real subprocesses, without sudo, inventory or runtime access."""
    import os
    import signal
    import sys

    # Simulate a CLI exiting after a monitor inherits its stdout/stderr. Pipe
    # capture waits for the monitor; regular files wait only for the actual CLI.
    script = """
import os, sys, time
pid = os.fork()
if pid == 0:
    time.sleep(10)
    os._exit(0)
print(pid, flush=True)
"""
    argv = [sys.executable, "-c", script]
    with pytest.raises(subprocess.TimeoutExpired) as failed:
        subprocess.run(argv, capture_output=True, text=True, timeout=0.2, check=False)
    os.kill(int(failed.value.stdout.strip()), signal.SIGKILL)
    child = UTILITY.probe_command(argv, tmp_path, "fixture", timeout=1)
    os.kill(int(child), signal.SIGKILL)
    assert (tmp_path / "probe-fixture.stdout").read_text().strip() == child


def test_probe_timeout_preserves_partial_output_and_reports_phase(tmp_path):
    import sys

    argv = [sys.executable, "-c", "import time; print('partial fixture identity', flush=True); time.sleep(10)"]
    with pytest.raises(RuntimeError, match="Namespace probe create timed out after") as failed:
        UTILITY.probe_command(argv, tmp_path, "create", timeout=0.2)
    assert str(tmp_path / "probe-create.stderr") in str(failed.value)
    assert "partial fixture identity" in (tmp_path / "probe-create.stdout").read_text()
    assert "time.sleep" not in str(failed.value)


def test_image_staging_requires_the_explicit_map_operation(monkeypatch):
    monkeypatch.setattr(UTILITY.os, "umask", lambda value: 0o077)
    monkeypatch.setattr(UTILITY.sys, "argv", ["utility-preparation.py", "--stage-image", "/unused"])
    monkeypatch.setattr(UTILITY, "project", lambda: pytest.fail("must reject before inventory resolution"))
    with pytest.raises(ValueError, match="requires --wallos-map"):
        UTILITY.main()


@pytest.mark.parametrize("change", ["empty_lines", "owner", "permission", "path", "named_acl", "empty"])
def test_acl_comparison_preserves_identity_and_permissions_without_live_queries(tmp_path, monkeypatch, change):
    before = "# file: /fixture/db\n# owner: 82\n# group: 82\nuser::rwx\ngroup::r-x\nother::r-x\n"
    variants = {
        "empty_lines": "\n" + before.replace("\n", "\n\n") + "\n",
        "owner": before.replace("owner: 82", "owner: 1019"),
        "permission": before.replace("other::r-x", "other::rwx"),
        "path": before.replace("/fixture/db", "/fixture/other"),
        "named_acl": before + "user:1234:rwx\n",
        "empty": "\n\n",
    }
    first, second = [tmp_path / name for name in ["before.acl", "after.acl"]]
    first.write_text(before)
    second.write_text(variants[change])
    monkeypatch.setattr(UTILITY.os, "umask", lambda value: 0o077)
    monkeypatch.setattr(UTILITY.sys, "argv", ["utility-preparation.py", "--compare-acls", str(first), str(second)])
    monkeypatch.setattr(UTILITY, "project", lambda: pytest.fail("comparison must not resolve inventory"))
    monkeypatch.setattr(UTILITY, "command", lambda *a: pytest.fail("comparison must not run host commands"))
    if change == "empty_lines":
        UTILITY.main()
    else:
        with pytest.raises(ValueError):
            UTILITY.main()


@pytest.mark.parametrize("change", [None, "tagless", "digest", "repository", "unpinned", "user", "pid", "running", "port", "extra_port"])
def test_runtime_cli_accepts_tagless_pinned_image_without_weakening_checks(tmp_path, monkeypatch, change):
    image = "registry.example:5000/fixture/wallos:4.9.6@sha256:" + "a" * 64
    selected = {
        "image": image,
        "user": "0:0",
        "ports": {"backend": {"host_ip": "192.0.2.48", "published": 18083, "target": 80, "protocol": "tcp"}},
    }
    runtime = {
        "id": "b" * 64,
        "pid": 1234,
        "running": True,
        "image": image,
        "user": "0:0",
        "ports": {"80/tcp": [{"HostIp": "192.0.2.48", "HostPort": "18083"}], "9000/tcp": None},
    }
    if change == "tagless":
        runtime["image"] = image.replace("wallos:4.9.6@", "wallos@")
    elif change == "digest":
        runtime["image"] = image.replace("a" * 64, "c" * 64)
    elif change == "repository":
        runtime["image"] = image.replace("/fixture/", "/other/")
    elif change == "unpinned":
        runtime["image"] = image.split("@")[0]
    elif change == "user":
        runtime["user"] = "82:82"
    elif change == "pid":
        runtime["pid"] = True
    elif change == "running":
        runtime["running"] = False
    elif change == "port":
        runtime["ports"]["80/tcp"][0]["HostIp"] = "0.0.0.0"
    elif change == "extra_port":
        runtime["ports"]["9000/tcp"] = [{"HostIp": "192.0.2.48", "HostPort": "9000"}]
    paths = [tmp_path / name for name in ["runtime.json", "selected.json"]]
    for path, data in zip(paths, [runtime, selected], strict=True):
        path.write_text(json.dumps(data))
    monkeypatch.setattr(UTILITY.os, "umask", lambda value: 0o077)
    monkeypatch.setattr(UTILITY.sys, "argv", ["utility-preparation.py", "--validate-runtime", *map(str, paths)])
    monkeypatch.setattr(UTILITY, "project", lambda: pytest.fail("must not resolve inventory"))
    monkeypatch.setattr(UTILITY, "command", lambda *a: pytest.fail("must not query runtime"))
    if change in {None, "tagless"}:
        UTILITY.main()
    else:
        with pytest.raises(ValueError):
            UTILITY.main()


def test_mapping_cli_keeps_retained_collection_and_uses_a_fresh_output(tmp_path, monkeypatch):
    monkeypatch.setattr(UTILITY.os, "umask", lambda value: 0o077)
    tmp_path.chmod(0o700)
    retained = tmp_path / "selected.json"
    retained.write_text("FAKE_RETAINED_EVIDENCE")
    monkeypatch.setattr(UTILITY.sys, "argv", ["utility-preparation.py", "--wallos-map", "--stage-image", str(tmp_path)])
    projection = {"fixture": True}
    monkeypatch.setattr(UTILITY, "project", lambda: projection)
    monkeypatch.setattr(UTILITY, "collect", lambda *args: pytest.fail("must not rerun collection"))
    calls = []
    monkeypatch.setattr(
        UTILITY, "prove_wallos", lambda directory, output, current, **flags: calls.append((directory, output, current, flags))
    )
    UTILITY.main()
    directory, output, current, flags = calls[0]
    assert directory == tmp_path and output.parent == directory and output.name.startswith("wallos-map-")
    assert output.stat().st_mode & 0o777 == 0o700
    assert current is projection and flags == {"stage_image": True}
    assert retained.read_text() == "FAKE_RETAINED_EVIDENCE"


def test_alerting_projection_uses_inventory_and_keeps_credentials_value_free(monkeypatch):
    from ansible.inventory import manager
    from ansible.plugins import loader
    from ansible.vars.manager import VariableManager

    monkeypatch.setattr(loader, "init_plugin_loader", lambda: None)
    host = SimpleNamespace(name="mgt")
    monkeypatch.setattr(
        manager, "InventoryManager", lambda **kw: SimpleNamespace(groups={"tags_ansible_manager": SimpleNamespace(hosts=[host])})
    )
    monkeypatch.setattr(VariableManager, "__init__", lambda self, **kw: None)
    monkeypatch.setattr(
        VariableManager,
        "get_vars",
        lambda self, **kw: {
            "local_ip": "192.0.2.48",
            "container_host_puid": 2345,
            "container_host_pgid": 3456,
            "container_host_appdata_root": "/fixture",
            "services_internal_zone": "int.example.test",
            "services_private_https_port": 9443,
            "postgres_pass": "FAKE_NOT_A_CREDENTIAL_MUST_NOT_PROJECT",
        },
    )
    monkeypatch.setattr(UTILITY.socket, "gethostname", lambda: "mgt")
    projection = UTILITY.project(UTILITY.ALERTING_SERVICES)
    assert projection["services"]["alertmanager"]["execution"]["userns"]["uid"] == 2345
    assert projection["integrations"] == {"zone": "int.example.test", "private_https_port": 9443}
    assert projection["services"]["gotify"]["postgres"] == {"enable": True, "databases": ["gotify"]}
    assert "FAKE_NOT_A_CREDENTIAL" not in json.dumps(projection)
    assert all("environment" not in cfg and "infisical" not in cfg for cfg in projection["services"].values())


@pytest.mark.parametrize("failure", [None, "replacement", "rw_missing"])
def test_alerting_collection_retains_exact_callers_and_never_promotes(tmp_path, monkeypatch, failure):
    names = ["traefik", "prometheus", "loki", "gotify", "alertmanager"]
    projection = {
        "integrations": {"zone": "int.example.test", "private_https_port": 9443},
        "services": {name: {"volumes": {"data": {"source": f"/fixture/{name}"}}} for name in UTILITY.ALERTING_SERVICES},
    }
    accepted = {"kind": "container", "phase": "docker", "selector": "traefik_traefik", "verified": True}
    inputs = {
        "mgt_firewall_callers": {
            "traefik": [accepted],
            "gotify": [{"kind": "container", "phase": "docker", "selector": "gotify_gotify", "verified": True}],
        },
        "mgt_firewall_active_endpoints": ["unrelated/backend", "gotify/backend", "alertmanager/backend"],
        "mgt_firewall_inputs_verified": True,
    }
    policy = {"callers": inputs["mgt_firewall_callers"]}
    account = {"name": "podman-gotify", "uid": 2468, "gid": 3456, "home": "/fixture/home"}
    (tmp_path / "policy-inputs.json").write_text(json.dumps(inputs))
    (tmp_path / "gotify.json").write_text(json.dumps({"account": account}))
    (tmp_path / "installed-policy.sha256").write_text("fixture-hash\n")
    (tmp_path / "host.json").write_text(json.dumps({"hostname": "fixture", "boot_id": "FIXTURE_BOOT"}))
    real_read = Path.read_text
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda self, *a, **kw: "FIXTURE_BOOT" if str(self) == "/proc/sys/kernel/random/boot_id" else real_read(self, *a, **kw),
    )
    monkeypatch.setattr(UTILITY.socket, "gethostname", lambda: "fixture")
    identity = {"pid": 123, "birth": "same", "netns": "net:[456]"}
    preflight = UTILITY.load("ansible/roles/service_firewall/files/haproxy-preflight.py", "alerting_real_socket_parser")
    fw = SimpleNamespace(container_identities=lambda binding, run: [{"address": "172.20.0.5", "veth": "fixture-veth"}])
    monkeypatch.setattr(UTILITY, "load", lambda path, name: preflight if "preflight.py" in path else fw)
    monkeypatch.setattr(UTILITY, "context", lambda pid: {**identity, "birth": "changed"} if failure == "replacement" else identity)
    monkeypatch.setattr(
        UTILITY,
        "container",
        lambda prefix, cid, docker=False: {
            "swarm": names[int(cid[0], 16)] + "_" + names[int(cid[0], 16)],
            "pid": 123,
            "identity": identity,
            "processes": [{"pid": 123, "uid": 0, "gid": 0}],
        },
    )
    calls = []

    def command(argv, operation):
        calls.append(argv)
        if "ps" in argv:
            if "--filter" not in argv:
                return "a" * 64
            selector = argv[argv.index("--filter") + 1].split("=")[-1]
            return format(names.index(selector.split("_")[0]), "x") * 64
        if "inspect" in argv:
            mount = {"Type": "bind", "Source": "/", "Destination": "/host/rootfs", "RW": False}
            if failure == "rw_missing":
                mount.pop("RW")
            return json.dumps({"id": "a" * 64, "name": "/alloy-task", "service": "alloy_alloy", "mounts": [mount]})
        if "ss" in argv:
            port = int(argv[-1].split(":")[1].split()[0])
            return f'0 0 172.20.0.5:40000 192.0.2.48:{port} users:(("fixture",pid=123,fd=4))\n0 0 172.20.0.5:40001 192.0.2.48:{port} users:(("unrelated",pid=999,fd=5))'
        if argv[-2:] == ["cat", "/etc/skynet-mgt-firewall/policy.json"]:
            return json.dumps(policy)
        if argv[-2:] == ["sha256sum", "/etc/skynet-mgt-firewall/policy.json"]:
            return "fixture-hash"
        pytest.fail(f"unexpected operation {operation}: {argv}")

    monkeypatch.setattr(UTILITY, "command", command)
    if failure:
        with pytest.raises(ValueError):
            UTILITY.collect_alerting_callers(tmp_path, projection, policy, [name + "_" + name for name in names])
    else:
        UTILITY.collect_alerting_callers(tmp_path, projection, policy, [name + "_" + name for name in names])
        candidate = json.loads((tmp_path / "future-caller-inputs.json").read_text())
        assert candidate["mgt_firewall_active_endpoints"] == inputs["mgt_firewall_active_endpoints"]
        assert candidate["mgt_firewall_callers"]["traefik"] == [accepted]
        assert candidate["mgt_firewall_callers"]["gotify"][0] == inputs["mgt_firewall_callers"]["gotify"][0]
        assert candidate["mgt_firewall_callers"]["gotify"][1]["verified"] is False
        assert candidate["mgt_firewall_callers"]["gotify"][1]["restart_verified"] is False
        assert candidate["mgt_firewall_inputs_verified"] is False
        assert json.loads((tmp_path / "gotify-caller-observation.json").read_text())["connections"]["5432"][0]["owner_pids"] == [123]
        assert len(json.loads((tmp_path / "gotify-caller-observation.json").read_text())["connections"]["5432"]) == 1
    assert not any(set(argv) & {"pull", "run", "exec", "restart", "chown"} for argv in calls)


@pytest.mark.parametrize("failure", [None, "unknown_owner", "named_acl", "wrong_identity"])
def test_alerting_ownership_plan_numeric_maps_and_overlapping_trees(tmp_path, failure):
    proof = tmp_path / "proof"
    proof.mkdir()
    cfg = {
        "name": "alertmanager",
        "image": "fixture@sha256:" + "a" * 64,
        "user": "1000:1000",
        "volumes": {"config": {"source": "/fixture/alertmanager"}, "data": {"source": "/fixture/alertmanager/data"}},
    }
    identity = {"pid": 99, "birth": "same", "netns": "ns"}
    account = {"name": "podman-fixture", "uid": 2468, "gid": 2468}
    saved = {
        "selected": cfg,
        "account": account,
        "podman": [],
        "docker": [{"running": True, "identity": identity, "maps": {"uid": "0 0 65536", "gid": "  0   0   65536\n"}}],
    }
    for path, data in [
        (tmp_path / "alertmanager.json", saved),
        (proof / "selected.json", cfg),
        (proof / "result.json", {"selected_mapping_proved": True, "probe_removed": True, "account": account}),
        (proof / "source.json", {"account": account, "docker_identity": {} if failure == "wrong_identity" else identity}),
    ]:
        path.write_text(json.dumps(data))
    for key in ["uid", "gid"]:
        (proof / f"selected.{key}_map").write_text("0 100000 1000\n1000 2468 1\n1001 101000 64535\n")
    owner = 333 if failure == "unknown_owner" else 1000

    def acl(path, uid):
        return (
            f"# file: {path}\n# owner: {uid}\n# group: {uid}\nuser::rwx\ngroup::r-x\nother::r-x\n"
            + ("user:777:rwx\n" if failure == "named_acl" else "")
            + "\n"
        )

    (tmp_path / "alertmanager-tree-0.acl").write_text(acl("/fixture/alertmanager", 0) + acl("/fixture/alertmanager/data", owner))
    (tmp_path / "alertmanager-tree-1.acl").write_text(acl("/fixture/alertmanager/data", owner))
    if failure:
        with pytest.raises(ValueError):
            UTILITY.ownership_plan(tmp_path, proof, "alertmanager")
    else:
        assert UTILITY.ownership_plan(tmp_path, proof, "alertmanager") == [
            {"path": "/fixture/alertmanager", "old": [0, 0], "new": [100000, 100000]},
            {"path": "/fixture/alertmanager/data", "old": [1000, 1000], "new": [2468, 2468]},
        ]


@pytest.mark.parametrize("case", ["managed_inventory_owner", "unmanaged_inventory_owner", "unexplained_owner"])
def test_ownership_plan_uses_declared_file_owner_without_reowning_unknown_data(tmp_path, case):
    proof = tmp_path / "proof"
    proof.mkdir()
    path = "/fixture/gotify" if case == "managed_inventory_owner" else "/fixture/gotify/image"
    cfg = {
        "name": "gotify",
        "user": "0:0",
        "image": "fixture@sha256:" + "a" * 64,
        "volumes": {"data": {"source": "/fixture/gotify"}},
        "host_ids": {"uid": 333, "gid": 444},
        "managed_paths": [{"path": "/fixture/gotify", "state": "directory"}],
        "templates": [],
    }
    identity = {"pid": 5, "birth": "same", "netns": "fixture"}
    account = {"name": "podman-fixture", "uid": 2468, "gid": 3456}
    saved = {
        "selected": cfg,
        "account": account,
        "podman": [],
        "docker": [{"running": True, "identity": identity, "maps": {"uid": "0 0 65536", "gid": "0 0 65536"}}],
    }
    for file, value in [
        (tmp_path / "gotify.json", saved),
        (proof / "selected.json", cfg),
        (proof / "result.json", {"account": account, "selected_mapping_proved": True, "probe_removed": True}),
        (proof / "source.json", {"account": account, "docker_identity": identity}),
    ]:
        file.write_text(json.dumps(value))
    (proof / "selected.uid_map").write_text("0 2468 1\n1 50000 65535\n")
    (proof / "selected.gid_map").write_text("0 3456 1\n1 90000 65535\n")
    owner = 999 if case == "unexplained_owner" else 333
    (tmp_path / "gotify-tree-0.acl").write_text(f"# file: {path}\n# owner: {owner}\n# group: 444\nuser::rwx\ngroup::r-x\nother::r-x\n\n")
    if case == "unexplained_owner":
        with pytest.raises(ValueError, match="unreviewed"):
            UTILITY.ownership_plan(tmp_path, proof, "gotify")
    else:
        rows = UTILITY.ownership_plan(tmp_path, proof, "gotify")
        assert rows == [{"path": path, "old": [333, 444], "new": [2468, 3456] if case == "managed_inventory_owner" else [50332, 90443]}]


@pytest.mark.parametrize(
    "change", ["lifecycle", "whitespace", "image", "name", "uid_map", "gid_map", "mount", "extra_mount", "missing_map"]
)
def test_replacement_preserves_artifacts_maps_and_mounts(change):
    image = "registry.example/utility:1@sha256:" + "a" * 64
    selected = {
        "name": "utility",
        "image": image,
        "user": "0:0",
        "ports": {"backend": {"target": 80, "published": 18081, "protocol": "tcp", "host_ip": "192.0.2.48"}},
    }
    reference = {
        "id": "b" * 64,
        "pid": 123,
        "running": True,
        "name": "utility",
        "image": image,
        "user": "0:0",
        "image_id": "sha256:" + "d" * 64,
        "ports": {"80/tcp": [{"HostIp": "192.0.2.48", "HostPort": "18081"}]},
        "maps": {"uid": "0 1009 1\n1 500000 65536\n", "gid": "0 1009 1\n1 500000 65536\n"},
        "mounts": [{"Type": "bind", "Source": "/FAKE/data", "Destination": "/app/data", "RW": True}],
    }
    current = deepcopy(reference)
    current["id"], current["pid"] = "c" * 64, 456
    if change == "whitespace":
        current["maps"]["uid"] = "    0    1009    1\n  1  500000 65536\n"
    elif change == "image":
        current["image_id"] = "sha256:" + "e" * 64
    elif change == "name":
        current["name"] = "other"
    elif change in {"uid_map", "gid_map"}:
        current["maps"][change.split("_")[0]] = "0 0 65536\n"
    elif change == "mount":
        current["mounts"][0]["RW"] = False
    elif change == "extra_mount":
        current["mounts"].append({"Type": "bind", "Source": "/FAKE/other", "Destination": "/other", "RW": True})
    elif change == "missing_map":
        del current["maps"]["uid"]
    if change in {"lifecycle", "whitespace"}:
        UTILITY.validate_runtime_replacement(current, selected, reference)
    else:
        with pytest.raises((ValueError, KeyError)):
            UTILITY.validate_runtime_replacement(current, selected, reference)


@pytest.mark.parametrize(
    "batch",
    [
        UTILITY.ALERTING_SERVICES,
        UTILITY.MEDIA_SERVICES,
        UTILITY.MONITORING_SERVICES,
        UTILITY.RECEIVER_SERVICES,
        UTILITY.VAULT_SERVICES,
        UTILITY.AUTH_SERVICES,
        UTILITY.INGRESS_SERVICES,
        UTILITY.NETBOX_SERVICES,
        UTILITY.INFISICAL_SERVICES,
    ],
)
def test_bounded_batch_projection_and_cli_use_real_catalog_without_secret_resolution(monkeypatch, tmp_path, batch):
    from ansible.inventory import manager
    from ansible.plugins import loader
    from ansible.vars.manager import VariableManager

    monkeypatch.setattr(loader, "init_plugin_loader", lambda: None)
    host = SimpleNamespace(name="mgt")
    monkeypatch.setattr(
        manager, "InventoryManager", lambda **kw: SimpleNamespace(groups={"tags_ansible_manager": SimpleNamespace(hosts=[host])})
    )
    monkeypatch.setattr(VariableManager, "__init__", lambda self, **kw: None)
    monkeypatch.setattr(
        VariableManager,
        "get_vars",
        lambda self, **kw: {
            "local_ip": "192.0.2.48",
            "container_host_puid": 2345,
            "container_host_pgid": 3456,
            "container_host_appdata_root": "/fixture",
            "services_log_root": "/fixture-logs",
            "services_internal_zone": "int.example.test",
            "services_private_https_port": 9443,
            "postgres_pass": "FAKE_SECRET_NOT_TO_RESOLVE",
            "netbox_postgres_pass": "{{ credential_source_must_not_be_resolved }}",
            "infisical_enc_key": "{{ credential_source_must_not_be_resolved }}",
            "infisical_postgres_pass": "{{ credential_source_must_not_be_resolved }}",
            "infisical_redis_password": "{{ credential_source_must_not_be_resolved }}",
        },
    )
    monkeypatch.setattr(UTILITY.socket, "gethostname", lambda: "mgt")
    projected = UTILITY.project(batch)
    assert set(projected["services"]) == set(batch)
    assert "FAKE_SECRET" not in json.dumps(projected)
    if batch == UTILITY.RECEIVER_SERVICES:
        for name in batch:
            cfg = projected["services"][name]
            assert cfg["host_ids"] == {"uid": 2345, "gid": 3456}
            assert cfg["managed_paths"] and cfg["templates"]
            assert all(entry["dest"].startswith("/fixture/") for entry in cfg["templates"])
        assert projected["integrations"] == {"zone": "int.example.test", "private_https_port": 9443}
    if batch == UTILITY.NETBOX_SERVICES:
        assert "{{" not in json.dumps(projected)
        assert {cfg["volumes"]["config" if name == "netbox" else "data"]["source"] for name, cfg in projected["services"].items()} == {
            "/fixture/netbox/config",
            "/fixture/netbox/postgres",
            "/fixture/netbox/redis",
        }
        assert all(cfg["host"] == "mgt" for cfg in projected["services"].values())
    if batch == UTILITY.INFISICAL_SERVICES:
        assert projected["services"]["infisical"]["volumes"] == {}
        assert projected["services"]["infisical-redis"]["volumes"]["data"]["source"] == "/fixture/infisical/redis"
        assert all(cfg["host"] == "mgt" for cfg in projected["services"].values())
        assert "credential_source" not in json.dumps(projected)
    if batch == UTILITY.AUTH_SERVICES:
        main, cache = [projected["services"][name] for name in batch]
        assert main["execution"]["host_user"] != cache["execution"]["host_user"]
        assert main["execution"]["userns"]["uid"] == 2345
        assert str(cache["execution"]["userns"]["uid"]) == "0"
        assert main["postgres"]["databases"] == ["authelia"] and cache["postgres"] == {}
        assert cache["volumes"]["config"]["source"] == "/fixture/authelia/redis"
        assert main["volumes"]["config"]["source"] == "/fixture/authelia"
        assert "environment" not in main and "infisical" not in main
    if batch == UTILITY.VAULT_SERVICES:
        assert projected["integrations"]["postgres"]["vaultwarden"] == {
            "driver": "postgres",
            "host": "haproxy.int.example.test",
            "port": 5432,
            "database": "vaultwarden",
        }
        assert projected["services"]["vaultwarden"]["user"] == "2345:3456"
    if batch == UTILITY.MEDIA_SERVICES:
        assert projected["services"]["seerr"]["user"] == "0:0"
        assert projected["services"]["seerr"]["execution"]["userns"]["uid"] == 2345
        assert projected["integrations"]["znc"] == {"host": "znc.int.example.test", "port": 16502, "caller": "autobrr"}
        assert projected["integrations"]["postgres"]["seerr"]["database"] == "seerr"
    tmp_path.chmod(0o700)
    collected = []
    monkeypatch.setattr(UTILITY, "collect", lambda directory, projection: collected.append((directory, projection)))
    monkeypatch.setattr(sys, "argv", ["utility", str(tmp_path), "--services", *batch])
    UTILITY.main()
    assert collected == [(tmp_path, projected)]


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "replacement",
        "wrong_selector",
        "wrong_znc",
        "policy_change",
        "boot_change",
        "policy_bytes",
        "inventory_address",
        "missing_account",
    ],
)
def test_media_callers_preserve_union_project_owned_routes_and_reject_changed_identity(tmp_path, monkeypatch, failure):
    names = ["traefik", "autobrr", "seerr"]
    bindings = {
        name: [
            {
                "kind": "container",
                "phase": "docker",
                "runtime": "docker",
                "path": "bridge",
                "selector": name + "_" + name,
                "verified": True,
                "restart_verified": True,
                "physdev_verified": True,
            }
        ]
        for name in names
    }
    policy = {"callers": bindings}
    inputs = {
        "mgt_firewall_callers": bindings,
        "mgt_firewall_inputs_verified": True,
        "mgt_firewall_active_endpoints": [
            "homepage/backend",
            "forgejo/backend",
            "gotify/backend",
            "haproxy/postgres",
            "znc/irc",
            "autobrr/backend",
            "seerr/backend",
        ],
    }
    (tmp_path / "policy-inputs.json").write_text(json.dumps(inputs))
    (tmp_path / "installed-policy.sha256").write_text("fixture-hash\n")
    (tmp_path / "host.json").write_text(json.dumps({"hostname": "mgt", "boot_id": "FIXTURE_BOOT"}))
    identity = {"pid": 123, "birth": "same", "netns": "net:[456]"}
    accounts = {name: {"name": "podman-" + name, "uid": 2468, "gid": 3456, "home": "/fixture/home"} for name in [*names, "znc"]}
    for i, name in enumerate(names[1:], 1):
        (tmp_path / f"{name}.json").write_text(
            json.dumps(
                {
                    "account": None if failure == "missing_account" and name == "autobrr" else accounts[name],
                    "docker": [{"running": True, "id": str(i) * 64, "identity": identity}],
                }
            )
        )
    projection = {"address": "192.0.2.48", "integrations": {"zone": "int.example.test", "znc": {"port": 16502}}}
    numeric = UTILITY.load("ansible/operator/znc-mapping-proof.py", "media_real_maps")
    preflight = UTILITY.load("ansible/roles/service_firewall/files/haproxy-preflight.py", "media_real_ss")
    fw = SimpleNamespace(container_identities=lambda binding, run: [{"veth": "fixture-veth", "address": "172.20.0.5"}])
    monkeypatch.setattr(
        UTILITY, "load", lambda path, name: preflight if "preflight.py" in path else numeric if "mapping-proof" in path else fw
    )
    image = "fixture/znc:1@sha256:" + "a" * 64
    monkeypatch.setattr(UTILITY, "project_znc_metadata", lambda: {"account": "podman-znc", "image": image, "uid": 1000, "gid": 1000})
    monkeypatch.setattr(UTILITY, "account_command", lambda name: (accounts[name.removeprefix("podman-")], ["fixture-account", name]))
    monkeypatch.setattr(UTILITY, "context", lambda pid: {**identity, "birth": "changed"} if failure == "replacement" else identity)
    monkeypatch.setattr(UTILITY.socket, "gethostname", lambda: "mgt")
    real_read = Path.read_text
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda self, *a, **kw: (
            ("OTHER_BOOT" if failure == "boot_change" else "FIXTURE_BOOT")
            if str(self) == "/proc/sys/kernel/random/boot_id"
            else real_read(self, *a, **kw)
        ),
    )

    def container(prefix, cid, docker=False):
        if docker:
            name = names[int(cid[0])]
            return {
                "id": cid,
                "swarm": "wrong" if failure == "wrong_selector" else name + "_" + name,
                "pid": 123,
                "identity": identity,
                "processes": [{"pid": 123, "uid": 1000}],
            }
        return {
            "name": "znc",
            "image": image,
            "pid": 123,
            "identity": identity,
            "maps": {"uid": "0 50000 1000\n1000 2468 1\n1001 51000 64535", "gid": "0 90000 1000\n1000 3456 1\n1001 91000 64535"},
            "ports": {"6502/tcp": [{"HostIp": "192.0.2.99" if failure == "wrong_znc" else "192.0.2.48", "HostPort": "16502"}]},
        }

    monkeypatch.setattr(UTILITY, "container", container)
    calls = []

    def command(argv, operation):
        calls.append(argv)
        if "ps" in argv:
            if argv[0] == "fixture-account":
                return "a" * 64
            selector = argv[argv.index("--filter") + 1].split("=")[-1]
            return str(names.index(selector.split("_")[0])) * 64
        if "ss" in argv:
            port = int(argv[-1].split(":")[1].split()[0])
            return f'0 0 172.20.0.5:40000 192.0.2.48:{port} users:(("fixture",pid=123,fd=4))\n0 0 172.20.0.5:40001 192.0.2.48:{port} users:(("unrelated",pid=999,fd=4))'
        if argv[-2:] == ["cat", "/etc/skynet-mgt-firewall/policy.json"]:
            return json.dumps({"callers": {}} if failure == "policy_change" else policy)
        if argv[-2:] == ["sha256sum", "/etc/skynet-mgt-firewall/policy.json"]:
            return "changed-hash" if failure == "policy_bytes" else "fixture-hash"
        if argv == ["ip", "-j", "address", "show"]:
            return json.dumps([{"addr_info": [{"local": "192.0.2.99" if failure == "inventory_address" else "192.0.2.48"}]}])
        pytest.fail(f"unexpected operation {operation}: {argv}")

    monkeypatch.setattr(UTILITY, "command", command)
    if failure and failure != "missing_account":
        with pytest.raises(ValueError):
            UTILITY.collect_media_callers(tmp_path, projection, policy, [name + "_" + name for name in names])
    else:
        UTILITY.collect_media_callers(tmp_path, projection, policy, [name + "_" + name for name in names])
        candidate = json.loads((tmp_path / "future-caller-inputs.json").read_text())
        assert candidate["mgt_firewall_active_endpoints"] == inputs["mgt_firewall_active_endpoints"]
        assert candidate["mgt_firewall_callers"]["traefik"] == bindings["traefik"]
        assert candidate["mgt_firewall_inputs_verified"] is False
        for name in UTILITY.MEDIA_SERVICES:
            assert candidate["mgt_firewall_callers"][name][0] == bindings[name][0]
            if failure == "missing_account" and name == "autobrr":
                assert candidate["mgt_firewall_callers"][name] == bindings[name]
                continue
            assert candidate["mgt_firewall_callers"][name][1]["verified"] is False
            assert candidate["mgt_firewall_callers"][name][1]["restart_verified"] is False
            sockets = json.loads((tmp_path / f"{name}-caller-observation.json").read_text())["connections"]["5432"]
            assert len(sockets) == 1 and sockets[0]["owner_pids"] == [123]
    assert not any(set(argv) & {"pull", "run", "exec", "restart", "chown"} for argv in calls)


def test_managed_seerr_files_map_to_account_while_unmanaged_root_files_retain_root_namespace_identity(tmp_path):
    proof = tmp_path / "proof"
    proof.mkdir()
    cfg = {
        "name": "seerr",
        "user": "0:0",
        "image": "fixture@sha256:" + "a" * 64,
        "execution": {"userns": {"mode": "keep-id", "uid": 1000, "gid": 1000}},
        "host_ids": {"uid": 1000, "gid": 1000},
        "volumes": {"config": {"source": "/fixture/seerr"}},
        "managed_paths": [{"path": "/fixture/seerr"}],
        "templates": [{"dest": "/fixture/seerr/.env"}],
    }
    identity = {"pid": 5, "birth": "same", "netns": "ns"}
    account = {"name": "podman-seerr", "uid": 2468, "gid": 2468}
    saved = {
        "selected": cfg,
        "account": account,
        "podman": [],
        "docker": [{"running": True, "identity": identity, "maps": {"uid": "0 0 65536", "gid": "0 0 65536"}}],
    }
    for file, value in [
        (tmp_path / "seerr.json", saved),
        (proof / "selected.json", cfg),
        (proof / "result.json", {"account": account, "selected_mapping_proved": True, "probe_removed": True}),
        (proof / "source.json", {"account": account, "docker_identity": identity}),
    ]:
        file.write_text(json.dumps(value))
    for key in ["uid", "gid"]:
        (proof / f"selected.{key}_map").write_text("0 50000 1000\n1000 2468 1\n1001 51000 64535")
    (tmp_path / "seerr-tree-0.acl").write_text(
        "\n".join(
            f"# file: /fixture/seerr{suffix}\n# owner: {owner}\n# group: {owner}\nuser::rwx\ngroup::r-x\nother::r-x\n"
            for suffix, owner in [("", 1000), ("/.env", 0), ("/settings.json", 1000), ("/root-file", 0)]
        )
    )
    rows = UTILITY.ownership_plan(tmp_path, proof, "seerr")
    assert [row["new"] for row in rows] == [[2468, 2468], [2468, 2468], [2468, 2468], [50000, 50000]]


@pytest.mark.parametrize("failure", [None, "missing_primary", "foreign_primary", "wrong_tag"])
def test_updated_image_uses_verified_primary_even_with_multiple_repo_digests(failure):
    tag = "registry.example/autobrr:1.87"
    record = {
        "digest": "sha256:" + "b" * 64,
        "tags": [tag],
        "refs": ["registry.example/autobrr@sha256:" + "a" * 64, "registry.example/autobrr@sha256:" + "b" * 64],
    }
    if failure == "missing_primary":
        record["digest"] = ""
    elif failure == "foreign_primary":
        record["digest"] = "sha256:" + "c" * 64
    elif failure == "wrong_tag":
        record["tags"] = ["registry.example/autobrr:old"]
    if failure:
        with pytest.raises(ValueError):
            UTILITY.image_update_pin(tag, record)
    else:
        assert UTILITY.image_update_pin(tag, record) == tag + "@sha256:" + "b" * 64


def hardlink_fixture(tmp_path):
    roots = [tmp_path / "data", tmp_path / "other"]
    for root in roots:
        root.mkdir()
    file = roots[0] / "first"
    file.write_bytes(b"fixture persistent contents\n")
    os.link(file, roots[0] / "second")
    os.link(file, roots[1] / "third")
    (roots[0] / "passive-link").symlink_to("first")
    tree = UTILITY.ownership_tree(roots)
    rows = [
        {"path": name, "old": [info["uid"], info["gid"]], "new": [info["uid"], info["gid"]]}
        for name, info in tree["entries"].items()
        if info["kind"] != "symlink"
    ]
    return roots, rows


def test_ownership_applies_once_per_inode_preserving_every_name(tmp_path, monkeypatch):
    roots, rows = hardlink_fixture(tmp_path)
    # Overlapping approved roots must not lose or double-count any pathname.
    snapshot = UTILITY.ownership_inventory(rows, [*roots, roots[0]])
    calls = []
    original = os.fchown

    def fchown(descriptor, uid, gid):
        info = os.fstat(descriptor)
        calls.append((info.st_dev, info.st_ino))
        original(descriptor, uid, gid)

    monkeypatch.setattr(UTILITY.os, "fchown", fchown)
    UTILITY.ownership_apply(snapshot)
    assert len(calls) == len(set(calls)) == 3  # One file inode, two directories.
    assert len(snapshot["groups"]) == 1 and len(snapshot["groups"][0]) == 3
    assert UTILITY.ownership_verify(snapshot)["groups"] == snapshot["groups"]
    assert (roots[0] / "passive-link").readlink() == Path("first")


@pytest.mark.parametrize("failure", ["external", "conflict", "missing", "duplicate", "symlink", "set-id"])
def test_ownership_hardlink_preflight_rejects_before_any_mutation(tmp_path, monkeypatch, failure):
    roots, rows = hardlink_fixture(tmp_path)
    if failure == "external":
        os.link(roots[0] / "first", tmp_path / "outside")
    elif failure == "conflict":
        next(row for row in rows if row["path"].endswith("/second"))["new"][0] += 1
    elif failure == "missing":
        rows = [row for row in rows if not row["path"].endswith("/third")]
    elif failure == "duplicate":
        rows.append(rows[-1])
    elif failure == "symlink":
        info = (roots[0] / "passive-link").lstat()
        rows.append({"path": str(roots[0] / "passive-link"), "old": [info.st_uid, info.st_gid], "new": [info.st_uid, info.st_gid]})
    else:
        (roots[0] / "first").chmod(0o4755)
    monkeypatch.setattr(UTILITY.os, "fchown", lambda *args: pytest.fail("mutation before rejection"))
    with pytest.raises(ValueError):
        UTILITY.ownership_inventory(rows, roots)


@pytest.mark.parametrize("change", ["replace", "external", "unlink", "contents", "mode", "new-name"])
def test_ownership_hardlink_apply_rejects_changed_identity_before_chown(tmp_path, monkeypatch, change):
    roots, rows = hardlink_fixture(tmp_path)
    snapshot = UTILITY.ownership_inventory(rows, roots)
    file = roots[0] / "second"
    if change == "replace":
        file.unlink()
        file.write_bytes(b"fixture persistent contents\n")
    elif change == "external":
        os.link(file, tmp_path / "outside")
    elif change == "unlink":
        file.unlink()
    elif change == "contents":
        file.write_bytes(b"changed fixture contents\n")
    elif change == "mode":
        file.chmod(0o600)
    else:
        (roots[0] / "new").write_bytes(b"new pathname")
    monkeypatch.setattr(UTILITY.os, "fchown", lambda *args: pytest.fail("changed identity was mutated"))
    with pytest.raises(ValueError):
        UTILITY.ownership_apply(snapshot)


def test_gnu_tar_backup_restore_retains_hardlinks_and_symlinks(tmp_path):
    import tarfile

    roots, rows = hardlink_fixture(tmp_path)
    before = UTILITY.ownership_tree(roots)
    archive = tmp_path / "data.tar"
    subprocess.run(
        [
            "tar",
            "--acls",
            "--xattrs",
            "--numeric-owner",
            "--one-file-system",
            "-cpf",
            str(archive),
            "-C",
            "/",
            "--",
            *[str(root).lstrip("/") for root in roots],
        ],
        check=True,
    )
    projection = UTILITY.ownership_archive_verify(archive, before)
    with tarfile.open(archive) as stream:
        assert sum(member.islnk() for member in stream) == 2
    restored = tmp_path / "restored"
    restored.mkdir()
    subprocess.run(
        ["tar", "--acls", "--xattrs", "--numeric-owner", "--same-permissions", "-xpf", str(archive), "-C", str(restored)], check=True
    )
    restored_roots = [restored / str(root).lstrip("/") for root in roots]
    after = UTILITY.ownership_tree(restored_roots)

    def names(groups):
        return sorted(sorted("/" + str(Path(name).relative_to(restored)) for name in group) for group in groups)

    assert names(after["groups"]) == projection["groups"]
    assert [len(group) for group in after["groups"]] == [3]
    assert (restored_roots[0] / "first").read_bytes() == b"fixture persistent contents\n"
    assert (restored_roots[0] / "passive-link").readlink() == Path("first")
    assert (restored_roots[0] / "first").stat().st_mode == (roots[0] / "first").stat().st_mode

    def remap(name):
        return str(restored / str(Path(name)).lstrip("/"))

    expected = {
        "roots": [remap(root) for root in roots],
        "entries": {remap(name): info for name, info in before["entries"].items()},
        "groups": sorted(sorted(remap(name) for name in group) for group in before["groups"]),
    }
    UTILITY.ownership_restored_verify(expected)
    alias = restored_roots[0] / "second"
    body = alias.read_bytes()
    alias.unlink()
    alias.write_bytes(body)
    with pytest.raises(ValueError, match="hardlink"):
        UTILITY.ownership_restored_verify(expected)


@pytest.mark.parametrize("failure", ["independent-copy", "external-target", "missing-member"])
def test_archive_topology_rejects_broken_or_outside_links(tmp_path, failure):
    import tarfile

    roots, rows = hardlink_fixture(tmp_path)
    before = UTILITY.ownership_tree(roots)
    archive = tmp_path / "data.tar"
    with tarfile.open(archive, "w", dereference=failure == "independent-copy") as stream:
        for root in roots:
            stream.add(root, arcname=str(root).lstrip("/"))
        if failure == "external-target":
            member = tarfile.TarInfo(str(roots[0] / "evil").lstrip("/"))
            member.type, member.linkname = tarfile.LNKTYPE, "unapproved/outside"
            stream.addfile(member)
    if failure == "missing-member":
        before["entries"][str(roots[0] / "missing")] = dict(next(iter(before["entries"].values())))
    with pytest.raises(ValueError):
        UTILITY.ownership_archive_verify(archive, before)


def test_tar_and_inode_translation_preserve_numeric_acl_entries(tmp_path):
    import shutil

    if not shutil.which("setfacl") or not shutil.which("getfacl"):
        pytest.skip("local ACL tools unavailable")
    roots, rows = hardlink_fixture(tmp_path)
    file = roots[0] / "first"
    subprocess.run(["setfacl", "-m", "u:12345:r--", str(file)], check=True)
    before_acl = subprocess.check_output(["getfacl", "-cpn", str(file)], text=True)
    snapshot = UTILITY.ownership_inventory(rows, roots)
    UTILITY.ownership_apply(snapshot)
    assert subprocess.check_output(["getfacl", "-cpn", str(file)], text=True) == before_acl
    archive = tmp_path / "acl.tar"
    subprocess.run(
        ["tar", "--acls", "--xattrs", "--numeric-owner", "-cpf", str(archive), "-C", "/", "--", *[str(root).lstrip("/") for root in roots]],
        check=True,
    )
    UTILITY.ownership_archive_verify(archive, snapshot)
    destination = tmp_path / "restored"
    destination.mkdir()
    subprocess.run(["tar", "--acls", "--xattrs", "--numeric-owner", "-xpf", str(archive), "-C", str(destination)], check=True)
    restored_file = destination / str(file).lstrip("/")
    assert subprocess.check_output(["getfacl", "-cpn", str(restored_file)], text=True) == before_acl
    assert restored_file.stat().st_nlink == 3


def test_restored_acl_manifest_compares_names_without_traversal_order():
    first = "# file: /fixture/a\n# owner: 1000\n# group: 1000\nuser::rw-\ngroup::r--\nother::---\n"
    second = first.replace("/fixture/a", "/fixture/b").replace("user::rw-", "user::r--")
    assert UTILITY.ownership_acl_lines(first + "\n" + second) == UTILITY.ownership_acl_lines(second + "\n" + first)
    assert UTILITY.ownership_acl_lines(first + second) != UTILITY.ownership_acl_lines(first + second.replace("other::---", "other::r--"))
    assert UTILITY.ownership_acl_lines(first + second) != UTILITY.ownership_acl_lines(
        first + second.replace("# owner: 1000", "# owner: 1001")
    )
    with pytest.raises(ValueError, match="duplicate"):
        UTILITY.ownership_acl_lines(first + first)


@pytest.mark.parametrize("service", [*UTILITY.MEDIA_SERVICES, *UTILITY.MONITORING_SERVICES])
def test_explicit_image_proof_cli_remains_scoped_to_selected_service(tmp_path, monkeypatch, service):
    tmp_path.chmod(0o700)
    calls = []
    projection = {"services": {service: {"name": service}}}
    monkeypatch.setattr(UTILITY, "project", lambda services: projection)
    monkeypatch.setattr(UTILITY, "prove_map", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(sys, "argv", ["utility", str(tmp_path), "--service-map", service, "--allow-image-update", "--stage-image"])
    UTILITY.main()
    assert len(calls) == 1 and calls[0][0][0] == tmp_path and calls[0][0][3] == service
    assert calls[0][1] == {"stage_image": True, "allow_image_update": True}


@pytest.mark.parametrize(
    "arguments",
    [["--service-map", "grafana", "--allow-image-update"], ["--service-map", "gotify", "--allow-image-update", "--stage-image"]],
)
def test_image_update_cli_rejects_missing_staging_or_wrong_batch(tmp_path, monkeypatch, arguments):
    monkeypatch.setattr(UTILITY, "project", lambda *args: pytest.fail("rejected invocation reached inventory"))
    monkeypatch.setattr(sys, "argv", ["utility", str(tmp_path), *arguments])
    with pytest.raises(ValueError, match="allow-image-update"):
        UTILITY.main()


@pytest.mark.parametrize("ambiguous", [False, True])
def test_auth_collection_attributes_exact_targets_and_preserves_policy_union(tmp_path, monkeypatch, ambiguous):
    policy = {
        "schema": 1,
        "backend": "nf_tables",
        "inventory_host": "mgt",
        "inventory_address": "192.0.2.48",
        "inputs_verified": True,
        "endpoints": [{"ids": ["retained/backend"], "port": 12345, "callers": ["traefik"]}],
        "callers": {
            "traefik": [
                {
                    "kind": "container",
                    "phase": "docker",
                    "runtime": "docker",
                    "selector": "traefik_traefik",
                    "verified": True,
                    "restart_verified": True,
                    "physdev_verified": True,
                }
            ]
        },
    }
    projection = {
        "host": "mgt",
        "address": "192.0.2.48",
        "services": {
            name: {
                "name": name,
                "execution": {"host_user": "fixture-" + name},
                "volumes": {},
                "ports": {key: {"published": port} for key, port in (("cache", 16379),) if name.endswith("-redis")}
                if name.endswith("-redis")
                else {"backend": {"published": 19091}, "metrics": {"published": 19959}},
            }
            for name in UTILITY.AUTH_SERVICES
        },
    }
    monkeypatch.setattr(UTILITY, "account_command", lambda name: (None, None))
    monkeypatch.setattr(UTILITY.socket, "gethostname", lambda: "mgt")
    monkeypatch.setattr(
        UTILITY,
        "container",
        lambda cmd, cid, **kw: {"id": cid, "running": True, "swarm": "authelia_authelia" + ("-redis" if cid == "cache" else "")},
    )

    def run(argv, operation):
        if argv == ["ip", "-j", "address", "show"]:
            return json.dumps([{"addr_info": [{"local": "192.0.2.48"}]}])
        if "sha256sum" in argv:
            return "fixture-digest"
        if "cat" in argv:
            return json.dumps(policy)
        if "info" in argv:
            return "mgt"
        if "service" in argv and "ls" in argv:
            return "authelia_authelia\nauthelia_authelia-redis" + ("\nother_authelia" if ambiguous else "")
        if "service" in argv and "inspect" in argv:
            return "{}"
        if "service" in argv and "ps" in argv:
            return "fixture placement"
        if "ps" in argv:
            return "main\ncache"  # Main name also matches cache, as on Docker.
        if "ss" in argv:
            return ""
        pytest.fail("unexpected operation: " + operation)

    monkeypatch.setattr(UTILITY, "command", run)
    if ambiguous:
        with pytest.raises(ValueError, match="one exact current Swarm service"):
            UTILITY.collect(tmp_path, projection)
    else:
        UTILITY.collect(tmp_path, projection)
        for name, cid in zip(UTILITY.AUTH_SERVICES, ("main", "cache"), strict=True):
            assert [r["id"] for r in json.loads((tmp_path / (name + ".json")).read_text())["docker"]] == [cid]
    inputs = json.loads((tmp_path / "policy-inputs.json").read_text())
    assert inputs["mgt_firewall_active_endpoints"] == ["retained/backend", "authelia/backend", "authelia/metrics", "authelia-redis/cache"]
    assert inputs["mgt_firewall_callers"] == policy["callers"]


@pytest.mark.parametrize("cache_root", ["/fixture/authelia/redis", "/fixture/authelia", "/outside"])
def test_authelia_ownership_does_not_translate_independent_cache_paths(tmp_path, cache_root):
    proof = tmp_path / "proof"
    proof.mkdir()
    cfg = {
        "name": "authelia",
        "user": "0:0",
        "image": "fixture",
        "volumes": {"config": {"source": "/fixture/authelia"}},
        "execution": {"userns": {"uid": 1000, "gid": 1000}},
        "host_ids": {"uid": 1000, "gid": 1000},
    }
    account = {"name": "fixture", "uid": 2468, "gid": 2468}
    identity = {"pid": 1, "birth": "fixture", "netns": "fixture"}
    saved = {
        "selected": cfg,
        "account": account,
        "podman": [],
        "docker": [{"running": True, "identity": identity, "maps": {"uid": "0 0 65536", "gid": "0 0 65536"}}],
    }
    records = {
        tmp_path / "authelia.json": saved,
        proof / "selected.json": cfg,
        proof / "source.json": {"account": account, "docker_identity": identity},
        proof / "result.json": {"selected_mapping_proved": True, "probe_removed": True, "account": account},
        tmp_path / "selected.json": {"services": {"authelia-redis": {"volumes": {"config": {"source": cache_root}}}}},
    }
    for path, value in records.items():
        path.write_text(json.dumps(value))
    for key in ("uid", "gid"):
        (proof / ("selected." + key + "_map")).write_text("0 100000 1000\n1000 2468 1\n1001 101000 64535\n")
    acl = "".join(
        f"# file: {path}\n# owner: 1000\n# group: 1000\nuser::rwx\ngroup::r-x\nother::r-x\n\n"
        for path in (
            "/fixture/authelia",
            "/fixture/authelia/users_database.yml",
            "/fixture/authelia/redis",
            "/fixture/authelia/redis/dump.rdb",
        )
    )
    (tmp_path / "authelia-tree-0.acl").write_text(acl)
    if cache_root == "/fixture/authelia/redis":
        assert {r["path"] for r in UTILITY.ownership_plan(tmp_path, proof, "authelia")} == {
            "/fixture/authelia",
            "/fixture/authelia/users_database.yml",
        }
    else:
        with pytest.raises(ValueError, match="strict child"):
            UTILITY.ownership_plan(tmp_path, proof, "authelia")
