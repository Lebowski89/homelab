"""Finite operator batches tested with fake hosts/managers and no real secrets."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("cutover_test", ROOT / "ansible/operator/haproxy-cutover.py")
BATCH = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BATCH)


def dump(path, value):
    path.write_text(json.dumps(value))
    return path


def mount_record(source="/", rw=False):
    return {
        "id": "a" * 64,
        "name": "/alloy_alloy.1.captured-task",
        "swarm": "alloy_alloy",
        "project": None,
        "service": None,
        "mounts": [{"type": "bind", "source": source, "destination": "/host/rootfs", "rw": rw}],
    }


@pytest.fixture(scope="module")
def mount_projection(tmp_path_factory):
    go = shutil.which("go")
    if not go:
        pytest.skip("Go unavailable for actual Docker mount projection regression")
    root = tmp_path_factory.mktemp("mount-projection")
    source = root / "projection.go"
    source.write_text("""package main
import ("encoding/json"; "fmt"; "os"; "text/template")
func main() {
    var input struct { Format string; Container map[string]any }
    if err := json.NewDecoder(os.Stdin).Decode(&input); err != nil { panic(err) }
    funcs := template.FuncMap{"json": func(value any) (string,error) { data,err := json.Marshal(value); return string(data),err }}
    projection,err := template.New("").Option("missingkey=error").Funcs(funcs).Parse(input.Format)
    if err == nil { err = projection.Execute(os.Stdout,input.Container) }
    if err != nil { fmt.Fprintln(os.Stderr,err); os.Exit(1) }
}
""")
    binary = root / "projection"
    environment = {
        **os.environ,
        "GOTOOLCHAIN": "local",
        "GOPROXY": "off",
        "GOSUMDB": "off",
        "GO111MODULE": "off",
        "GOCACHE": str(root / "cache"),
    }
    result = subprocess.run([go, "build", "-o", str(binary), str(source)], capture_output=True, text=True, env=environment, timeout=120)
    assert result.returncode == 0, result.stderr
    script = (ROOT / "ansible/operator/haproxy-cutover-batch.sh").read_text()
    format_string = next(value for value in re.findall(r"inspect --format '([^']+)'", script) if ".Mounts" in value)

    def project(container):
        result = subprocess.run(
            [str(binary)], input=json.dumps({"format": format_string, "container": container}), capture_output=True, text=True, check=False
        )
        if result.returncode:
            raise RuntimeError(result.stderr)
        return result.stdout

    return project


@pytest.mark.parametrize("rw", [False, True, "absent"])
def test_actual_alloy_mount_projection_and_guard(tmp_path, mount_projection, rw):
    captured = {
        "Id": "a" * 64,
        "Name": "/alloy_alloy.1.captured-task",
        "Config": {"Labels": {"com.docker.swarm.service.name": "alloy_alloy"}},
        "Mounts": [{"Type": "bind", "Source": "/", "Destination": "/host/rootfs", "RW": rw}],
    }
    if rw == "absent":
        del captured["Mounts"][0]["RW"]
        with pytest.raises(RuntimeError, match="RW"):
            mount_projection(captured)
        return
    record = json.loads(mount_projection(captured))
    assert record == mount_record(rw=rw)
    metadata = tmp_path / "mounts.jsonl"
    metadata.write_text(json.dumps(record) + "\n")
    if rw:
        with pytest.raises(ValueError, match="alloy_alloy.*writer/direct consumer"):
            BATCH.mounts("/opt/haproxy", metadata)
    else:
        BATCH.mounts("/opt/haproxy", metadata)


@pytest.mark.parametrize(
    "source,rw,blocked",
    [
        ("/opt", False, False),
        ("/opt", True, True),
        ("/opt/haproxy", True, True),
        ("/opt/haproxy", False, True),
        ("/opt/haproxy/haproxy.cfg", True, True),
        ("/opt/haproxy/haproxy.cfg", False, True),
        ("/opt/haproxy/subdirectory", False, True),
        ("/srv/unrelated", True, False),
    ],
)
def test_configuration_mount_overlap_contract(tmp_path, source, rw, blocked):
    metadata = tmp_path / "mounts.jsonl"
    metadata.write_text(json.dumps(mount_record(source, rw)) + "\n")
    if blocked:
        with pytest.raises(ValueError, match="writer/direct consumer"):
            BATCH.mounts("/opt/haproxy", metadata)
    else:
        BATCH.mounts("/opt/haproxy", metadata)


@pytest.mark.parametrize(
    "invalid",
    [
        "rw-absent",
        "rw-string",
        "identity-absent",
        "service-absent",
        "compose-incomplete",
        "mounts-null",
        "source-relative",
        "source-ambiguous",
        "destination-absent",
        "duplicate",
    ],
)
def test_mount_metadata_missing_or_ambiguous_never_passes(tmp_path, invalid):
    record = mount_record()
    if invalid == "rw-absent":
        del record["mounts"][0]["rw"]
    elif invalid == "rw-string":
        record["mounts"][0]["rw"] = "false"
    elif invalid == "identity-absent":
        del record["id"]
    elif invalid == "service-absent":
        del record["service"]
    elif invalid == "compose-incomplete":
        record["project"] = "incomplete-project"
    elif invalid == "mounts-null":
        record["mounts"] = None
    elif invalid == "source-relative":
        record["mounts"][0]["source"] = "opt/haproxy"
    elif invalid == "source-ambiguous":
        record["mounts"][0]["source"] = "//"
    elif invalid == "destination-absent":
        del record["mounts"][0]["destination"]
    metadata = tmp_path / "mounts.jsonl"
    metadata.write_text((json.dumps(record) + "\n") * (2 if invalid == "duplicate" else 1))
    with pytest.raises(ValueError):
        BATCH.mounts("/opt/haproxy", metadata)


def evidence():
    lines = []
    for name, parent in BATCH.SLICES.items():
        for hook in ["mangle", "filter"]:
            lines.append(f"{name} ordinary root: {hook} OUTPUT=0 (expected 0)")
        for attempt in [1, 2]:
            lines.append(
                json.dumps({"binding_cgroup": parent, "cgroup": f"{parent}/fake-{attempt}.service", "process_uid": 0, "socket_uid": 0})
            )
            lines.append(f"{name} attempt {attempt}: mangle OUTPUT=3; filter OUTPUT=3")
    return "\n".join(lines)


@pytest.mark.parametrize("bad", [None, "wrong-uid", "duplicate-child", "no-counter", "no-negative", "homepage-mismatch"])
def test_working_policy_preserves_homepage_and_only_merges_accepted_native(tmp_path, bad):
    home = {
        "kind": "container",
        "runtime": "docker",
        "phase": "docker",
        "selector": "edge_proxy",
        "verified": True,
        "restart_verified": True,
        "physdev_verified": True,
        "path": "bridge",
    }
    accepted = {
        "mgt_firewall_active_endpoints": ["homepage/backend"],
        "mgt_firewall_callers": {"traefik": [home]},
        "mgt_firewall_inputs_verified": True,
    }
    (tmp_path / "homepage-inputs.yml").write_text(yaml.safe_dump(accepted))
    saved = {
        "callers": accepted["mgt_firewall_callers"],
        "inputs_verified": True,
        "inventory_host": "manager",
        "inventory_address": "192.0.2.48",
    }
    if bad == "homepage-mismatch":
        saved["callers"] = {}
    dump(tmp_path / "homepage-policy.json", saved)
    baseline = {
        **saved,
        "schema": 1,
        "backend": "nf_tables",
        "endpoints": [
            {"ids": ["homepage/backend"], "port": 13000, "purpose": "backend", "callers": ["traefik"]},
            {"ids": ["forgejo/backend"], "port": 13001, "purpose": "backend", "callers": ["traefik"]},
            {"ids": ["unrelated/backend"], "port": 18001, "purpose": "backend", "callers": ["other"]},
        ],
        "callers": {"traefik": [home], "other": [{**home, "selector": "accepted_other"}]},
    }
    dump(tmp_path / "policy-before.json", baseline)
    native = evidence()
    if bad == "wrong-uid":
        native = native.replace('"socket_uid": 0', '"socket_uid": false')
    if bad == "duplicate-child":
        native = native.replace("fake-2.service", "fake-1.service")
    if bad == "no-counter":
        native = native.replace("mangle OUTPUT=3", "mangle OUTPUT=0")
    if bad == "no-negative":
        native = native.replace("filter OUTPUT=0 (expected 0)", "filter OUTPUT=1 (expected 0)")
    (tmp_path / BATCH.NATIVE_LOG).write_text(native)
    candidate = deepcopy(accepted)
    candidate["mgt_firewall_callers"].update(
        {"forgejo": [{"kind": "local", "account": "podman-forgejo", "uid": 1004, "phase": "podman", "verified": True}], "unresolved": []}
    )
    projected = {"kind": "container", "runtime": "docker", "phase": "docker", "selector": "observed_prometheus", "verified": True}
    reports = [
        {
            "host": host,
            "identity": {"boot_id": host, "hostname": host},
            "addresses": [address],
            "containers": [{"swarm": "observed_prometheus", "binding": projected}] if host == "manager" else [],
        }
        for host, address in [("manager", "192.0.2.48"), ("worker", "192.0.2.20"), ("media", "192.0.2.59")]
    ]
    output = tmp_path / "output"
    output.mkdir()
    args = [tmp_path, dump(tmp_path / "candidate.json", candidate), dump(tmp_path / "metadata.json", reports), output]
    if bad:
        with pytest.raises(ValueError):
            BATCH.working(*args)
        assert list(output.iterdir()) == []
    else:
        BATCH.working(*args)
        result = BATCH.read(output / "working-policy.json")
        assert result["mgt_firewall_active_endpoints"] == [
            "homepage/backend",
            "forgejo/backend",
            "unrelated/backend",
            "haproxy/postgres",
            "haproxy/metrics",
        ]
        assert result["mgt_firewall_callers"]["other"] == baseline["callers"]["other"]
        assert result["mgt_firewall_callers"]["traefik"] == [home]
        assert result["mgt_firewall_callers"]["unresolved"] == []
        assert result["mgt_firewall_callers"]["forgejo"][0]["verified"] is False
        assert result["mgt_firewall_callers"]["prometheus"][0]["verified"] is False
        assert result["mgt_firewall_inputs_verified"] is False
        assert all(result["mgt_firewall_callers"][n][0]["restart_verified"] is True for n in BATCH.SLICES)
        assert BATCH.read(output / "deployment-inputs.json")["service_common_postgres_operator_context"] is True
        assert (output / "working-policy.json").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("failure", [None, "probe", "second-insert", "empty-counter"])
def test_observation_cleanup_is_exact_even_after_partial_failure(failure):
    calls = []
    rules = [
        ("iptables", table, chain, ["-p", "tcp", "-s", "192.0.2.10", "-m", "comment", "--comment", "unique-fixture"])
        for table, chain in [("mangle", "PREROUTING"), ("filter", "INPUT")]
    ]

    def execute(argv):
        calls.append(argv)
        if failure == "second-insert" and "-I" in argv and "INPUT" in argv:
            raise RuntimeError("fake insert failed")
        if argv[0] == "iptables-save":
            chain = "PREROUTING" if argv[-1] == "mangle" else "INPUT"
            return (
                f"[{0 if failure == 'empty-counter' else 3}:100] -A {chain} -p tcp -s 192.0.2.10/32 -m comment --comment unique-fixture\n"
            )
        return ""

    def probe():
        if failure == "probe":
            raise RuntimeError("fake probe failed")

    if failure:
        with pytest.raises((ValueError, RuntimeError)):
            BATCH.observe_rules(rules, probe, execute)
    else:
        assert len(BATCH.observe_rules(rules, probe, execute)) == 2
    insertions = [a for a in calls if "-I" in a]
    successful = insertions[:-1] if failure == "second-insert" else insertions
    deletions = [a for a in calls if "-D" in a]
    assert deletions == [[*a[:5], "-D", a[6], *a[8:]] for a in reversed(successful)]
    assert all("-F" not in a and "-j" not in a for a in calls)


def route_fixture(tmp_path, mgt_task=False, idle=False):
    reports = [
        {
            "host": name,
            "addresses": [ip],
            "accounts": {},
            "containers": [],
            "topology": {"swarm": {"node_id": name}, "services": [], "networks": []},
        }
        for name, ip in [("manager", "192.0.2.48"), ("worker", "192.0.2.20"), ("media", "192.0.2.59")]
    ]
    reports[0]["topology"]["services"] = [
        {
            "name": "pg_haproxy",
            "vips": [{"Addr": "198.51.100.144/24", "NetworkID": "fake-network"}],
            "tasks": [
                {"state": "running", "node_id": node, "networks": []}
                for node in (["manager", "worker", "media"] if mgt_task else ["worker", "media"])
            ],
        }
    ]
    reports[1]["containers"] = [
        {"swarm": "observed_worker-db", "destinations": [] if idle else [{"destination": "198.51.100.144", "port": 5432}]}
    ]
    values = {"mgt_firewall_callers": {"native": [{"verified": True}], "worker-db": []}, "mgt_firewall_inputs_verified": False}
    fresh = {
        "mgt_firewall_callers": {
            "worker-db": [
                {"kind": "elsewhere", "inventory_host": "worker", "verified": True, "restart_verified": True, "route_verified": True}
            ]
        }
    }
    stage = {
        "controller": "manager",
        "workers": ["worker", "media"],
        "plan": {"principals": {"worker-db": {"inventory_hosts": "worker"}, "native": {}}},
        "policy": {"endpoints": [{"ids": ["haproxy/postgres"], "callers": ["worker-db", "native"]}]},
    }
    return [
        dump(tmp_path / "working-policy.json", values),
        dump(tmp_path / "fresh.json", fresh),
        dump(tmp_path / "reports.json", reports),
        dump(tmp_path / "stage.json", stage),
    ]


@pytest.mark.parametrize("mgt_task,idle", [(True, False), (False, True), (False, False)])
def test_worker_proposal_requires_postplacement_actual_routes_and_keeps_false(tmp_path, mgt_task, idle):
    args = route_fixture(tmp_path, mgt_task, idle)
    if mgt_task or idle:
        with pytest.raises(ValueError):
            BATCH.routes(*args)
        assert not (tmp_path / "worker-route-proposal.json").exists()
    else:
        BATCH.routes(*args)
        result = BATCH.read(tmp_path / "worker-route-proposal.json")
        assert result["mgt_firewall_callers"]["native"] == [{"verified": True}]
        assert result["mgt_firewall_callers"]["worker-db"][0]["route_verified"] is False
        assert result["mgt_firewall_inputs_verified"] is False


@pytest.mark.parametrize("change", [None, "id", "image", "configs", "vips", "constraints"])
def test_provider_continuity_allows_only_one_mgt_constraint(tmp_path, change):
    before = {
        "id": "fake-id",
        "name": "pg_haproxy",
        "image": "fixture@sha256:fake",
        "configs": ["fake-native"],
        "ports": [5432],
        "vips": ["198.51.100.144"],
        "constraints": ["node.labels.haproxy == true"],
    }
    after = deepcopy(before)
    after["constraints"].append("node.labels.ansible_host != manager")
    if change:
        after[change] = ["unexpected"] if isinstance(after[change], list) else "unexpected"
    args = [dump(tmp_path / "before", before), dump(tmp_path / "after", after), "manager", "yes"]
    if change:
        with pytest.raises(ValueError):
            BATCH.continuity(*args)
    else:
        BATCH.continuity(*args)


@pytest.mark.parametrize("idle,flag", [(False, True), (True, True), (False, False), (False, "true")])
def test_before_placement_readiness_requires_dependency_and_mgt_acceptance(tmp_path, idle, flag):
    values = {
        "mgt_firewall_active_endpoints": ["haproxy/postgres"],
        "mgt_firewall_callers": {
            "controller": [
                {
                    "kind": "local",
                    "phase": "native",
                    "account": "root",
                    "uid": 0,
                    "cgroup": BATCH.SLICES["controller"],
                    "verified": flag,
                    "restart_verified": True,
                }
            ],
            "worker-db": [],
        },
    }
    policy = {
        "schema": 1,
        "backend": "nf_tables",
        "inventory_host": "manager",
        "inventory_address": "192.0.2.48",
        "inputs_verified": False,
        "callers": {},
        "endpoints": [
            {
                "ids": ["haproxy/postgres"],
                "port": 5432,
                "purpose": "declared PostgreSQL applications and recovery",
                "callers": ["controller", "worker-db"],
            }
        ],
    }
    stage = {
        "policy": policy,
        "workers": ["worker", "media"],
        "plan": {
            "principals": {
                "controller": {"inventory_hosts": "manager"},
                "worker-db": {"inventory_hosts": "worker", "future_runtime": "docker"},
            }
        },
    }
    reports = [
        {
            "containers": [
                {
                    "swarm": "app_worker-db",
                    "destinations": [] if idle else [{"routes": [{"kind": "overlay_service", "provider": True, "worker_only": False}]}],
                }
            ]
        }
    ]
    args = [dump(tmp_path / "working", values), dump(tmp_path / "metadata", reports), dump(tmp_path / "stage", stage)]
    if idle or flag is not True:
        with pytest.raises(ValueError):
            BATCH.ready(*args)
    else:
        BATCH.ready(*args)


@pytest.mark.parametrize("compose", [False, True])
def test_current_selector_resolves_again_and_requires_all_exact_labels(monkeypatch, compose):
    binding = {"compose": {"project": "observed-project", "service": "observed-service"}} if compose else {"selector": "observed-service"}
    queries = []
    generation = 0

    def execute(argv):
        nonlocal generation
        queries.append(argv)
        if "ps" in argv:
            generation += 1
            return f"fake{generation}\n"
        return json.dumps({"pid": generation, "project": "observed-project", "service": "observed-service", "swarm": "observed-service"})

    monkeypatch.setattr(BATCH, "run", execute)
    assert BATCH.current(binding)[0] == "fake1"
    assert BATCH.current(binding)[0] == "fake2"
    if compose:
        assert all(
            "label=com.docker.compose.project=observed-project" in a and "label=com.docker.compose.service=observed-service" in a
            for a in queries
            if "ps" in a
        )


@pytest.mark.parametrize("check", [False, True])
def test_actual_optional_projection_and_renderer_without_secret_values(tmp_path, check):
    catalog = {}
    for path in (ROOT / "ansible/group_vars/all/services").glob("*.yml"):
        catalog.update(yaml.safe_load(path.read_text()))
    play = {"tasks": yaml.safe_load((ROOT / "ansible/tasks/haproxy-firewall-preflight.yml").read_text())}
    task = deepcopy(play["tasks"][-1])
    for entry in task["block"]:
        if "ansible.builtin.include_vars" in entry:
            entry["ansible.builtin.include_vars"]["file"] = str(ROOT / "ansible" / entry["ansible.builtin.include_vars"]["file"])
        if "ansible.builtin.include_tasks" in entry:
            entry["ansible.builtin.include_tasks"] = str(ROOT / "ansible" / entry["ansible.builtin.include_tasks"])
    inventory = {
        "all": {
            "children": {"tags_postgres": {"hosts": {"pg1": {"local_ip": "192.0.2.101"}}}},
            "hosts": {
                "manager": {
                    "ansible_connection": "local",
                    "ansible_python_interpreter": sys.executable,
                    "local_ip": "192.0.2.48",
                    "container_host_appdata_root": "/tmp/NONPRODUCTION-apps",
                    "container_host_puid": 99,
                    "container_host_pgid": 99,
                }
            },
        }
    }
    projection = tmp_path / "stage.json"
    variables = {
        "haproxy_preflight_catalog": catalog,
        "mgt_firewall_active_endpoints": ["homepage/backend", "forgejo/backend"],
        "haproxy_preflight_stage_output": str(projection),
        "services_controller_host": "manager",
        "services_storage_host": "storage",
        "services_plex_host": "media",
        "services_private_https_port": 10443,
        "infisical_postgres_port": 6543,
    }
    tasks = [
        task,
        {
            "name": "Render the actual adapter template",
            "ansible.builtin.template": {
                "src": str(ROOT / "ansible/roles/service_common/templates/configs/haproxy.cfg.j2"),
                "dest": str(tmp_path / "adapter.cfg"),
                "mode": "0600",
            },
            "vars": {"service_common_service": {"settings": catalog["haproxy"]["settings"]}},
        },
    ]
    (tmp_path / "inventory.yml").write_text(yaml.safe_dump(inventory))
    (tmp_path / "play.yml").write_text(
        yaml.safe_dump(
            [{"name": "Offline projection fixture", "hosts": "manager", "gather_facts": False, "vars": variables, "tasks": tasks}]
        )
    )
    config = tmp_path / "ansible.cfg"
    config.write_text(
        f"[defaults]\naction_plugins={ROOT}/ansible/action_plugins\nlibrary={ROOT}/ansible/library\n"
        f"filter_plugins={ROOT}/ansible/filter_plugins\ncollections_path={ROOT}/ansible/collections\nvars_plugins_enabled=\n"
        "[inventory]\nenable_plugins=yaml\n"
    )
    result = subprocess.run(
        [str(Path(sys.executable).parent / "ansible-playbook"), "-i", str(tmp_path / "inventory.yml"), str(tmp_path / "play.yml")]
        + (["--check"] if check else []),
        capture_output=True,
        text=True,
        env={**os.environ, "ANSIBLE_CONFIG": str(config)},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    if check:
        assert not projection.exists() and not (tmp_path / "adapter.cfg").exists()
    else:
        stage = BATCH.read(projection)
        assert {i for e in stage["policy"]["endpoints"] for i in e["ids"]} == {
            "homepage/backend",
            "forgejo/backend",
            "haproxy/postgres",
            "haproxy/metrics",
        }
        assert stage["postgres_declarations"]["infisical"]["port"] == 6543
        assert "ENCRYPTION_KEY" not in projection.read_text() and "DB_CONNECTION_URI" not in projection.read_text()
        BATCH.render(projection, tmp_path / "staged.cfg")
        assert (tmp_path / "staged.cfg").read_bytes() == (tmp_path / "adapter.cfg").read_bytes()


@pytest.mark.parametrize("change", [None, "binding", "endpoint"])
def test_reviewed_policy_cannot_change_accepted_homepage(tmp_path, change):
    accepted = {"mgt_firewall_callers": {"traefik": [{"selector": "exact", "verified": True}]}}
    values = dict(accepted, mgt_firewall_active_endpoints=["homepage/backend", "haproxy/postgres", "haproxy/metrics"])
    values = deepcopy(values)
    if change == "binding":
        values["mgt_firewall_callers"]["traefik"][0]["selector"] = "other"
    if change == "endpoint":
        values["mgt_firewall_active_endpoints"].remove("homepage/backend")
    source = tmp_path / "homepage.yml"
    source.write_text(yaml.safe_dump(accepted))
    current = dump(tmp_path / "working.json", values)
    if change:
        with pytest.raises(ValueError, match="Homepage"):
            BATCH.homepage(current, source)
    else:
        BATCH.homepage(current, source)


@pytest.mark.parametrize("state", ["before-write", "after-write", "outside-change", "new-paths"])
def test_scoped_configuration_rollback_handles_partial_deployment(tmp_path, state):
    import re

    root = tmp_path / "config"
    saved = tmp_path / "saved"
    root.mkdir()
    saved.mkdir()
    cfg = root / "haproxy.cfg"
    (saved / "haproxy.cfg").write_text("prepared configuration\n")
    (saved / "haproxy-before.cfg").write_text("original configuration\n")
    original = [{"path": str(path), "uid": os.getuid(), "gid": os.getgid(), "mode": "0o700"} for path in [root, cfg]]
    if state == "new-paths":
        original = [{"path": str(path), "absent": True} for path in [root, cfg]]
    cfg.write_text(
        {
            "before-write": "original configuration\n",
            "after-write": "prepared configuration\n",
            "outside-change": "unrelated operator change\n",
            "new-paths": "prepared configuration\n",
        }[state]
    )
    dump(saved / "config-ownership.json", original)
    other = tmp_path / "unrelated"
    other.write_text("preserve\n")
    source = (ROOT / "ansible/operator/haproxy-cutover-batch.sh").read_text()
    code = re.search(r"sudo /usr/bin/python3 - \"\$HAPROXY_CONFIG_DIR\" \"\$batch_dir\" <<'PY'\n(.*?)\nPY", source, re.S).group(1)
    result = subprocess.run([sys.executable, "-", str(root), str(saved)], input=code, capture_output=True, text=True, check=False)
    assert other.read_text() == "preserve\n"
    if state == "outside-change":
        assert result.returncode != 0 and "changed outside" in result.stderr
        assert cfg.read_text() == "unrelated operator change\n"
    else:
        assert result.returncode == 0, result.stderr
        if state == "new-paths":
            assert not root.exists()
        else:
            assert cfg.read_text() == "original configuration\n"
            assert cfg.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize(
    "case",
    ["active", "expired", "inactive", "expires-during-read", "wrong-user", "wrong-command", "wrong-cgroup", "changed-invocation"],
)
def test_recorded_probe_cleanup_checks_ownership_and_tolerates_expiry(tmp_path, monkeypatch, case):
    unit = "skynet-haproxy-acceptance-recorded.service"
    command = ["/usr/bin/python3", str(tmp_path / "haproxy-cutover.py"), "listen", "5432", "18405"]
    initial = {
        "LoadState": "loaded",
        "Id": unit,
        "Transient": "yes",
        "User": "root",
        "Slice": "skynet_pg_recovery.slice",
        "RuntimeMaxUSec": "4min",
        "MainPID": "4242",
        "ActiveState": "active",
        "InvocationID": "a" * 32,
        "ExecStart": "{ path=/usr/bin/python3 ; argv[]=" + " ".join(command) + " ; start_time=old ; }",
    }
    if case == "expired":
        initial = {"LoadState": "not-found"}
    elif case == "inactive":
        initial.update(MainPID="0", ActiveState="failed", InvocationID="")
    elif case == "wrong-user":
        initial["User"] = "unrelated"
    elif case == "wrong-command":
        initial["ExecStart"] = initial["ExecStart"].replace("listen 5432", "listen 9999")
    expired = dict(initial, MainPID="0", ActiveState="failed", ExecStart=initial.get("ExecStart", "").replace("old", "expired"))
    current = expired if case == "expires-during-read" else dict(initial)
    if case == "changed-invocation":
        current["InvocationID"] = "b" * 32
    snapshots = iter([initial, current, expired])
    calls = []

    def run(argv):
        calls.append(argv)
        if argv[1] == "show":
            return "\n".join(key + "=" + value for key, value in next(snapshots).items())
        assert argv == ["systemctl", "stop", unit]
        return ""

    original_text, original_bytes = Path.read_text, Path.read_bytes

    def contents(path, *args, **kwargs):
        if str(path) == "/proc/4242/cmdline":
            if case == "expires-during-read":
                raise FileNotFoundError(str(path))
            return b"\0".join(os.fsencode(value) for value in command) + b"\0"
        return original_bytes(path, *args, **kwargs)

    def text(path, *args, **kwargs):
        if str(path) == "/proc/4242/cgroup":
            return "0::/" + ("unrelated.slice/" if case == "wrong-cgroup" else "skynet_pg_recovery.slice/") + unit + "\n"
        return original_text(path, *args, **kwargs)

    monkeypatch.setattr(BATCH, "run", run)
    monkeypatch.setattr(Path, "read_bytes", contents)
    monkeypatch.setattr(Path, "read_text", text)
    if case.startswith("wrong-") or case == "changed-invocation":
        with pytest.raises(ValueError):
            BATCH.stop_recorded_probe(tmp_path, unit)
    else:
        BATCH.stop_recorded_probe(tmp_path, unit)
    assert [argv for argv in calls if argv[1] == "stop"] == ([["systemctl", "stop", unit]] if case == "active" else [])


@pytest.mark.parametrize("change", [None, "omitted", "port", "binding", "new-installed-endpoint", "new-installed-binding"])
def test_retained_policy_and_scoped_rollback_reject_stale_overwrites(tmp_path, monkeypatch, change):
    binding = {
        "kind": "container",
        "phase": "docker",
        "runtime": "docker",
        "selector": "existing_traefik",
        "path": "bridge",
        "verified": True,
        "restart_verified": True,
        "physdev_verified": True,
    }
    baseline = {
        "schema": 1,
        "backend": "nf_tables",
        "inventory_host": "mgt",
        "inventory_address": "192.0.2.48",
        "inputs_verified": True,
        "callers": {"traefik": [binding]},
        "endpoints": [{"ids": ["forgejo/backend"], "port": 13001, "callers": ["traefik"]}],
    }
    dump(tmp_path / "policy-before.json", baseline)
    stage = {"policy": deepcopy(baseline)}
    stage["policy"]["endpoints"].append({"ids": ["haproxy/metrics"], "port": 18405, "callers": ["traefik"]})
    values = BATCH.retained_inputs(baseline)
    values["mgt_firewall_active_endpoints"].append("haproxy/metrics")
    if change == "omitted":
        values["mgt_firewall_active_endpoints"].remove("forgejo/backend")
    if change == "port":
        stage["policy"]["endpoints"][0]["port"] = 13002
    if change == "binding":
        values["mgt_firewall_callers"]["traefik"][0]["selector"] = "different_traefik"
    dump(tmp_path / "stage.json", stage)
    dump(tmp_path / "working-policy.json", values)
    current = deepcopy(stage["policy"])
    if change == "new-installed-endpoint":
        current["endpoints"].append({"ids": ["new/backend"], "port": 18000, "callers": ["traefik"]})
    if change == "new-installed-binding":
        current["callers"]["traefik"][0]["selector"] = "new_traefik"
    original = BATCH.read
    monkeypatch.setattr(BATCH, "read", lambda path: current if str(path) == "/etc/skynet-mgt-firewall/policy.json" else original(path))
    if change:
        with pytest.raises(ValueError):
            BATCH.rollback_policy(tmp_path)
    else:
        BATCH.retained_policy(tmp_path)
        BATCH.rollback_policy(tmp_path)
        current.clear()
        current.update(deepcopy(baseline))
        BATCH.rollback_policy(tmp_path)  # Failed installation before writes is idempotent.
