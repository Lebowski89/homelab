#!/usr/bin/python3
"""Finite HAProxy handoff operations; operator execution only, no secret lookup."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import ipaddress
import json
import os
import pwd
import re
import shlex
import signal
import socket
import subprocess
import sys
import time
import uuid
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if not (REPO / "ansible").is_dir():
    REPO = Path(os.environ.get("PLAYBOOK", "/opt/homelab/ansible/playbook.yml")).resolve().parents[1]
NATIVE_LOG = "native-hooks-20261008T145711Z-1717643.log"
CANDIDATE = "haproxy-candidate-04-20261008T150348Z-1717643.json"
SLICES = {"controller": "skynet_pg_prepare.slice", "recovery": "skynet_pg_recovery.slice"}
MGT = ["autobrr", "gotify", "vaultwarden", "infisical", "authelia", "seerr", "prometheus", "forgejo"]
DOCKER = ["docker", "--host", "unix:///var/run/docker.sock"]


def load(relative, name):
    spec = importlib.util.spec_from_file_location(name, REPO / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FW = load("ansible/roles/mgt_firewall/files/mgt-firewall.py", "cutover_firewall")
PREFLIGHT = load("ansible/roles/mgt_firewall/files/haproxy-preflight.py", "cutover_preflight")


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    # Fresh private output only; never overwrite supplied evidence or accepted inputs.
    with open(path, "x", opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True) + "\n")


def native_evidence(text):
    records = [json.loads(line) for line in text.splitlines() if line.startswith('{"binding_cgroup":')]
    for name, parent in SLICES.items():
        own = [record for record in records if record.get("binding_cgroup") == parent]
        if len(own) != 2 or len({record["cgroup"] for record in own}) != 2:
            raise ValueError(f"{name}: require two accepted distinct native child services")
        if any(
            type(record.get("socket_uid")) is not int
            or record["socket_uid"] != 0
            or type(record.get("process_uid")) is not int
            or record["process_uid"] != 0
            or not record["cgroup"].startswith(parent + "/")
            for record in own
        ):
            raise ValueError(f"{name}: native UID/cgroup evidence disagrees")
        for hook in ["mangle", "filter"]:
            if f"{name} ordinary root: {hook} OUTPUT=0 (expected 0)" not in text:
                raise ValueError(f"{name}: missing ordinary-root negative control")
        for attempt in [1, 2]:
            match = re.search(rf"{name} attempt {attempt}: mangle OUTPUT=(\d+); filter OUTPUT=(\d+)", text)
            if not match or min(map(int, match.groups())) <= 0:
                raise ValueError(f"{name}: missing accepted OUTPUT hook evidence")


def retained_inputs(policy):
    """Require a complete installed baseline, including exact generated IDs."""
    FW.validate_policy(policy)
    active = []
    for endpoint in policy["endpoints"]:
        identities = endpoint.get("ids")
        if not isinstance(identities, list) or not identities or any(not isinstance(i, str) or not i or i in active for i in identities):
            raise ValueError("installed endpoint IDs are missing or ambiguous")
        if len(identities) != len(set(identities)):
            raise ValueError("installed endpoint IDs are ambiguous")
        active.extend(identities)
    return {
        "mgt_firewall_active_endpoints": active,
        "mgt_firewall_callers": deepcopy(policy["callers"]),
        "mgt_firewall_inputs_verified": policy["inputs_verified"],
    }


def baseline_inputs(batch):
    root = Path(batch)
    values = retained_inputs(read(root / "policy-before.json"))
    for identity in ["haproxy/postgres", "haproxy/metrics"]:
        if identity not in values["mgt_firewall_active_endpoints"]:
            values["mgt_firewall_active_endpoints"].append(identity)
    write(root / "policy-before-inputs.json", values)


def retained_policy(batch):
    """Reject omissions/changed accepted bindings before policy installation."""
    root = Path(batch)
    before, values, stage = read(root / "policy-before.json"), read(root / "working-policy.json"), read(root / "stage.json")
    baseline = retained_inputs(before)
    projected = stage["policy"]
    FW.validate_policy(projected, False)
    if any(projected.get(key) != before.get(key) for key in ["schema", "backend", "inventory_host", "inventory_address"]):
        raise ValueError("prepared policy baseline host/backend changed")
    for endpoint in before["endpoints"]:
        if endpoint not in projected["endpoints"]:
            raise ValueError("installed endpoint omitted or changed in prepared policy")
    active = values.get("mgt_firewall_active_endpoints")
    if (
        not isinstance(active, list)
        or any(not isinstance(i, str) for i in active)
        or len(active) != len(set(active))
        or set(active) != {i for e in projected["endpoints"] for i in e["ids"]}
    ):
        raise ValueError("prepared endpoint selection changed before installation")
    if not set(baseline["mgt_firewall_active_endpoints"]) <= set(active):
        raise ValueError("installed endpoint silently omitted from working inputs")
    for name, bindings in baseline["mgt_firewall_callers"].items():
        if values["mgt_firewall_callers"].get(name) != bindings:
            raise ValueError(f"installed accepted binding changed: {name}")


def rollback_policy(batch):
    """Do not restore a baseline over an unrelated newer installed policy."""
    root = Path(batch)
    before = read(root / "policy-before.json")
    retained_inputs(before)
    retained_policy(root)
    values, expected = read(root / "working-policy.json"), read(root / "stage.json")["policy"]
    expected["callers"] = values["mgt_firewall_callers"]
    expected["inputs_verified"] = values["mgt_firewall_inputs_verified"]
    current = read("/etc/skynet-mgt-firewall/policy.json")
    FW.validate_policy(current)
    # Persistence metadata is role-owned; endpoint/identity policy must match
    # either the saved baseline (partial failure) or this exact staged install.
    keys = ["schema", "backend", "inventory_host", "inventory_address", "endpoints", "callers", "principals", "inputs_verified"]
    if not any(all(current.get(key) == allowed.get(key) for key in keys) for allowed in [before, expected]):
        raise ValueError("installed policy changed outside this handoff; refusing stale rollback")


def working(handoff, candidate, metadata, output):
    import yaml

    root = Path(handoff)
    accepted = yaml.safe_load((root / "homepage-inputs.yml").read_text())
    saved = read(root / "homepage-policy.json")
    if accepted["mgt_firewall_callers"] != saved["callers"] or accepted["mgt_firewall_active_endpoints"] != ["homepage/backend"]:
        raise ValueError("saved Homepage inputs/policy disagree; keep the accepted rollback pair")
    if accepted["mgt_firewall_inputs_verified"] is not True or saved["inputs_verified"] is not True:
        raise ValueError("Homepage must already be accepted")
    baseline = read(root / "policy-before.json")
    baseline_values = retained_inputs(baseline)
    if any(baseline.get(key) != saved.get(key) for key in ["inventory_host", "inventory_address"]):
        raise ValueError("installed baseline differs from accepted Homepage host")
    for name, bindings in accepted["mgt_firewall_callers"].items():
        if baseline["callers"].get(name) != bindings:
            raise ValueError("installed baseline disagrees with accepted Homepage bindings")
    native_evidence((root / NATIVE_LOG).read_text())
    result = read(candidate)
    reports = read(metadata)
    hosts, boots = [r["host"] for r in reports], [r["identity"]["boot_id"] for r in reports]
    if len(reports) != 3 or len(set(hosts)) != 3 or len(set(boots)) != 3 or saved["inventory_host"] not in hosts:
        raise ValueError("require three distinct validated host reports")
    manager = next(r for r in reports if r["host"] == saved["inventory_host"])
    PREFLIGHT.validate_identity(manager, {"inventory_address": saved["inventory_address"]})
    callers = result["mgt_firewall_callers"]
    for name, bindings in callers.items():
        for binding in bindings:
            for key in list(binding):
                if key.endswith("verified"):
                    binding[key] = False
        if name in accepted["mgt_firewall_callers"]:
            callers[name] = deepcopy(accepted["mgt_firewall_callers"][name])
    for name, parent in SLICES.items():
        callers[name] = [
            {"kind": "local", "phase": "native", "account": "root", "uid": 0, "cgroup": parent, "verified": True, "restart_verified": True}
        ]
    prometheus = [c for c in manager["containers"] if (c.get("swarm") or "").endswith("_prometheus") or c.get("service") == "prometheus"]
    if len(prometheus) != 1 or not prometheus[0].get("binding"):
        raise ValueError("Prometheus needs one observed exact label binding; no guessed selector")
    callers["prometheus"] = [deepcopy(prometheus[0]["binding"])]
    for key in callers["prometheus"][0]:
        if key.endswith("verified"):
            callers["prometheus"][0][key] = False
    forgejo = callers.get("forgejo", [])
    if len(forgejo) != 1 or forgejo[0].get("uid") != 1004 or forgejo[0].get("account") != "podman-forgejo":
        raise ValueError("retain Forgejo's accepted actual host socket UID 1004")
    callers.update(deepcopy(baseline["callers"]))
    result["mgt_firewall_active_endpoints"] = baseline_values["mgt_firewall_active_endpoints"]
    for identity in ["haproxy/postgres", "haproxy/metrics"]:
        if identity not in result["mgt_firewall_active_endpoints"]:
            result["mgt_firewall_active_endpoints"].append(identity)
    result["mgt_firewall_inputs_verified"] = False
    write(Path(output) / "working-policy.json", result)
    write(
        Path(output) / "deployment-inputs.json",
        {
            "services_mgt_backend_acl_ready": False,
            "services_rootless_data_ready": {"haproxy": False},
            "service_common_postgres_operator_context": True,
            "podman_services_pull_images": False,
        },
    )


def run(argv):
    result = subprocess.run(argv, text=True, capture_output=True, check=False, timeout=120)
    if result.returncode:
        raise RuntimeError(f"{argv[0]} {argv[1] if len(argv) > 1 else ''}: {result.stderr.strip()}")
    return result.stdout


def account_command(name):
    account = pwd.getpwnam(name)
    if account.pw_uid <= 0:
        raise ValueError("a dedicated rootless account must not be root")
    return [
        "runuser",
        "-u",
        name,
        "--",
        "env",
        "HOME=" + account.pw_dir,
        f"XDG_RUNTIME_DIR=/run/user/{account.pw_uid}",
        f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{account.pw_uid}/bus",
        "/bin/sh",
        "-c",
        'cd "$HOME" || exit; exec "$@"',
        "skynet-forgejo",
    ]


def mounts(directory, metadata):
    """Reject writers/direct consumers; allow passive read-only ancestor mounts."""
    root = Path(directory)
    if not root.is_absolute() or root.anchor == "//" or ".." in root.parts:
        raise ValueError("configuration directory must be an unambiguous absolute path")
    identities, names = set(), set()
    for line in Path(metadata).read_text().splitlines():
        record = json.loads(line)
        if not isinstance(record, dict) or not {"id", "name", "swarm", "project", "service", "mounts"} <= record.keys():
            raise ValueError("mount projection lacks required container/service metadata")
        identity, name = record["id"], record["name"]
        if (
            not isinstance(identity, str)
            or not re.fullmatch(r"[0-9a-f]{64}", identity)
            or not isinstance(name, str)
            or not re.fullmatch(r"/?[a-zA-Z0-9][a-zA-Z0-9_.-]*", name)
        ):
            raise ValueError("mount projection lacks an exact container identity")
        labels = [record[key] for key in ["swarm", "project", "service"]]
        if any(value is not None and (not isinstance(value, str) or not value.strip()) for value in labels):
            raise ValueError(f"{identity} {name}: invalid service identity metadata")
        if bool(record["project"]) != bool(record["service"]) or (record["swarm"] and record["project"]):
            raise ValueError(f"{identity} {name}: ambiguous Swarm/Compose service identity")
        if identity in identities or name in names or not isinstance(record["mounts"], list):
            raise ValueError(f"{identity} {name}: duplicate identity or missing mount list")
        identities.add(identity)
        names.add(name)
        destinations = set()
        for mount in record["mounts"]:
            if not isinstance(mount, dict) or not {"type", "source", "destination", "rw"} <= mount.keys():
                raise ValueError(f"{identity} {name}: incomplete mount metadata")
            source, destination = mount["source"], mount["destination"]
            if mount["type"] not in ["bind", "volume", "tmpfs"] or type(mount["rw"]) is not bool:
                raise ValueError(f"{identity} {name}: unsupported mount type or non-boolean RW")
            if any(not isinstance(value, str) for value in [source, destination]):
                raise ValueError(f"{identity} {name}: invalid mount paths")
            target = Path(destination)
            if not target.is_absolute() or target.anchor == "//" or ".." in target.parts or target in destinations:
                raise ValueError(f"{identity} {name}: ambiguous mount destination")
            destinations.add(target)
            if mount["type"] == "tmpfs":
                if source:
                    raise ValueError(f"{identity} {name}: unexpected tmpfs source")
                continue
            source_path = Path(source)
            if not source_path.is_absolute() or source_path.anchor == "//" or ".." in source_path.parts:
                raise ValueError(f"{identity} {name}: ambiguous mount source")
            if source_path == root or root in source_path.parents or (source_path in root.parents and mount["rw"]):
                raise ValueError(
                    f"{identity} {name} service={record['swarm'] or record['service']}: existing writer/direct consumer {source}"
                )
            if source_path in root.parents:
                print(json.dumps({"passive_read_only_ancestor": record, "source": source, "destination": destination}), flush=True)


def current(binding):
    if binding.get("compose"):
        labels = [f"com.docker.compose.{key}={value}" for key, value in binding["compose"].items()]
    else:
        labels = ["com.docker.swarm.service.name=" + binding["selector"]]
    command = DOCKER + ["ps"]
    for label in labels:
        command += ["--filter", "label=" + label]
    ids = run(command + ["--format", "{{.ID}}"]).split()
    if len(ids) != 1:
        raise ValueError("require exactly one running local selected caller; wait for replacement convergence")
    record = json.loads(run(DOCKER + ["inspect", "--format", PREFLIGHT.FORMAT, ids[0]]))
    if record["pid"] <= 0:
        raise ValueError("selected caller is not running")
    if binding.get("compose"):
        if {k: record[k] for k in ["project", "service"]} != binding["compose"]:
            raise ValueError("fresh Compose labels disagree")
    elif record["swarm"] != binding["selector"]:
        raise ValueError("fresh Swarm label disagrees")
    return ids[0], record


def observe_rules(rules, probe, execute=run):
    """Own only these complete no-target rules; exact deletion on every path."""
    installed = []
    try:
        for binary, table, chain, match in rules:
            print(json.dumps({"exact_cleanup": shlex.join([binary, "-w", "5", "-t", table, "-D", chain, *match])}), flush=True)
            execute([binary, "-w", "5", "-t", table, "-I", chain, "1", *match])
            installed.append((binary, table, chain, match))
        probe()
        counts = []
        for binary, table, chain, match in installed:
            lines = execute([binary + "-save", "-c", "-t", table]).splitlines()
            token = match[match.index("--comment") + 1]
            exact = []
            for line in lines:
                parsed = shlex.split(line)
                if parsed[1:3] == ["-A", chain] and "--comment" in parsed and parsed[parsed.index("--comment") + 1] == token:
                    if "-j" in parsed or "-g" in parsed:
                        raise ValueError("observation must remain a no-target counter")
                    exact.append(line)
            if len(exact) != 1:
                raise ValueError("exact observation counter disappeared/changed")
            count = int(re.fullmatch(r"\[(\d+):\d+\]", shlex.split(exact[0])[0])[1])
            if count <= 0:
                raise ValueError(f"{table} {chain}: identity probe did not match")
            counts.append({"table": table, "hook": chain, "packets": count})
        return counts
    finally:
        failures = []
        for binary, table, chain, match in reversed(installed):
            try:
                execute([binary, "-w", "5", "-t", table, "-D", chain, *match])
            except RuntimeError as error:
                failures.append(str(error))
        if failures:
            raise RuntimeError("exact observation cleanup failed: " + "; ".join(failures))


def hooks(inputs, projection, replace, active=False):
    if os.geteuid() != 0 or (not active and (set(replace) != set(MGT) or len(replace) != len(MGT))):
        raise ValueError("root operator must explicitly name exactly the eight caller replacements")
    values, stage = read(inputs), read(projection)
    policy = deepcopy(stage["policy"])
    policy["callers"] = values["mgt_firewall_callers"]
    FW.validate_policy(policy, require_verified=False)
    for name in MGT:
        bindings = policy["callers"].get(name, [])
        if len(bindings) != 1:
            raise ValueError(f"{name}: require one prepared caller binding before any replacement")
        binding = bindings[0]
        if name == "forgejo":
            if (
                binding.get("kind") != "local"
                or binding.get("phase") != "podman"
                or binding.get("account") != "podman-forgejo"
                or binding.get("uid") != 1004
            ):
                raise ValueError("Forgejo must retain its exact observed account/UID before replacement")
        elif binding.get("kind") != "container" or binding.get("runtime") != "docker" or binding.get("path", "bridge") != "bridge":
            raise ValueError(f"{name}: expected the prepared current Docker bridge caller")
    address = stage["policy"]["inventory_address"]
    addresses = [entry["local"] for link in json.loads(run(["ip", "-j", "address", "show"])) for entry in link.get("addr_info", [])]
    PREFLIGHT.validate_identity(
        {"host": stage["controller"], "addresses": addresses, "identity": PREFLIGHT.observed_identity()}, {"inventory_address": address}
    )
    port = next(e["port"] for e in stage["policy"]["endpoints"] if "haproxy/metrics" in e["ids"])
    if ipaddress.ip_address(address).version != 4:
        raise ValueError("this accepted preparation uses IPv4; IPv6 enforcement remains separate acceptance")
    if not active and run(["ss", "-Hln", f"( sport = :{port} )"]).strip():
        raise ValueError("identity preparation needs the unused future metrics port; do not disturb a listener")
    metrics_port = port
    pg_port = next(e["port"] for e in stage["policy"]["endpoints"] if "haproxy/postgres" in e["ids"])
    for name in MGT:
        port = metrics_port if not active or name == "prometheus" else pg_port
        binding = values["mgt_firewall_callers"][name][0]
        print(f"Caller {name}: {'active listener acceptance' if active else 'explicit replacement of only this service'}", flush=True)
        before = None
        for attempt in [1] if active else [1, 2]:
            token = "skynet-haproxy-observe-" + uuid.uuid4().hex
            rules = []
            if name == "forgejo":
                prefix = account_command(binding["account"])
                ids = run(prefix + ["/usr/bin/podman", "--remote=false", "ps", "--filter", "name=^forgejo$", "--format", "{{.ID}}"]).split()
                if len(ids) != 1:
                    raise ValueError("require one current Forgejo container in its own account store")
                pid = run(prefix + ["/usr/bin/podman", "--remote=false", "inspect", "--format", "{{.State.Pid}}", ids[0]]).strip()
                identity = {"kind": "local", "uid": binding["uid"]}
                match = FW.caller_match(identity, 4, True)
                for table in ["mangle", "filter"]:
                    rules.append(
                        (
                            "iptables",
                            table,
                            "OUTPUT",
                            [
                                "-p",
                                "tcp",
                                "-m",
                                "conntrack",
                                "--ctdir",
                                "ORIGINAL",
                                "--ctorigdst",
                                address,
                                "--ctorigdstport",
                                str(port),
                                *match,
                                "-m",
                                "comment",
                                "--comment",
                                token,
                            ],
                        )
                    )
                owner = pwd.getpwnam(binding["account"])
                if owner.pw_uid != binding["uid"]:
                    raise ValueError("actual Forgejo account UID changed")
                # Enter only the current workload network namespace, then drop
                # privilege before opening a socket. No caller binary/pull or
                # mount/environment/credential inspection is needed.
                probe_command = [
                    "nsenter",
                    "--target",
                    pid,
                    "--net",
                    "/usr/bin/python3",
                    "-c",
                    "import os,socket,sys\nos.setgroups([]);os.setgid(int(sys.argv[1]));os.setuid(int(sys.argv[2]))\n"
                    "s=socket.socket();s.settimeout(3)\ntry:\n s.connect((sys.argv[3],int(sys.argv[4])))\n"
                    "except OSError as e:\n print(str(e),file=sys.stderr);sys.exit(1)\nfinally:\n s.close()\n",
                    str(owner.pw_gid),
                    str(owner.pw_uid),
                    address,
                    str(port),
                ]
            else:
                identity_id, record = current(binding)
                pid = str(record["pid"])
                identities = FW.container_identities(binding, run)
                route = json.loads(run(["nsenter", "--target", pid, "--net", "ip", "-j", "route", "get", address]))
                source = route[0].get("prefsrc") or route[0].get("src")
                choices = [i for i in identities if i["address"] == source]
                if len(choices) != 1:
                    raise ValueError("actual route source is not one exclusive resolved bridge identity")
                identity = choices[0]
                match = FW.caller_match(identity, 4, False)
                rules = [
                    (
                        "iptables",
                        "mangle",
                        "PREROUTING",
                        ["-p", "tcp", "-d", address, "--dport", str(port), *match, "-m", "comment", "--comment", token],
                    ),
                    (
                        "iptables",
                        "filter",
                        "INPUT",
                        [
                            "-p",
                            "tcp",
                            "-m",
                            "conntrack",
                            "--ctdir",
                            "ORIGINAL",
                            "--ctorigdst",
                            address,
                            "--ctorigdstport",
                            str(port),
                            *match,
                            "-m",
                            "comment",
                            "--comment",
                            token,
                        ],
                    ),
                ]
                probe_command = [
                    "nsenter",
                    "--target",
                    pid,
                    "--net",
                    "/usr/bin/python3",
                    "-c",
                    "import socket,sys\ns=socket.socket();s.settimeout(3)\ntry:\n s.bind((sys.argv[1],0));s.connect((sys.argv[2],int(sys.argv[3])))\n"
                    "except OSError as e:\n print(str(e),file=sys.stderr);sys.exit(1)\nfinally:\n s.close()\n",
                    source,
                    address,
                    str(port),
                ]

            def probe(probe_command=probe_command):
                # No listener/no payload: refusal or timeout is expected here.
                # The positive counters prove matching only, never ACL acceptance.
                result = subprocess.run(probe_command, text=True, capture_output=True, check=False, timeout=8)
                if result.returncode == 127:
                    raise ValueError("caller has no existing probe client; evidence remains pending")
                if active and result.returncode != 0:
                    raise ValueError("active listener denied an intended caller or its client failed")
                if not active and result.returncode == 0:
                    raise ValueError("unexpected listener appeared on the unused probe port")

            counts = observe_rules(rules, probe)
            if name == "forgejo":
                observed_pid = run(prefix + ["/usr/bin/podman", "--remote=false", "inspect", "--format", "{{.State.Pid}}", ids[0]]).strip()
            else:
                observed_id, observed = current(binding)
                if observed_id != identity_id or FW.container_identities(binding, run) != identities:
                    raise ValueError("caller identity changed during probe; repeat")
                observed_pid = str(observed["pid"])
            if observed_pid != pid or (attempt == 2 and pid == before):
                raise ValueError("require a stable probe and an actually replaced process")
            print(json.dumps({"caller": name, "attempt": attempt, "identity": identity, "counters": counts}), flush=True)
            if attempt == 1 and not active:
                before = pid
                if name == "forgejo":
                    run(prefix + ["systemctl", "--user", "restart", "forgejo.service"])
                elif binding.get("compose"):
                    run(DOCKER + ["restart", identity_id])
                else:
                    run(DOCKER + ["service", "update", "--force", binding["selector"]])
                time.sleep(5)
        print(f"{name}: matching/replacement evidence collected; confirmations unchanged", flush=True)


def routes(inputs, candidate, metadata, projection):
    stage, fresh, reports = read(projection), read(candidate), read(metadata)
    # Fresh generator already validates transport/host identity. Recompute exact
    # route mapping; never convert an idle client into an exception.
    PREFLIGHT.map_routes(reports, stage["controller"], "haproxy", stage["workers"])
    workers = set(stage["workers"])
    tasks = [
        t
        for r in reports
        for s in r["topology"]["services"]
        if s["name"].endswith("_haproxy")
        for t in s.get("tasks", [])
        if t["state"] == "running"
    ]
    nodes = {r["topology"]["swarm"]["node_id"]: r["host"] for r in reports}
    if not tasks or {nodes.get(t["node_id"]) for t in tasks} != workers:
        raise ValueError("provider running tasks must be exactly the two validated workers")
    values = read(inputs)
    pending = []
    for name in next(e["callers"] for e in stage["policy"]["endpoints"] if "haproxy/postgres" in e["ids"]):
        principal = stage["plan"]["principals"][name]
        host = principal.get("inventory_hosts")
        if not isinstance(host, str) or host not in workers:
            continue
        bindings = fresh["mgt_firewall_callers"].get(name, [])
        records = [
            c
            for r in reports
            if r["host"] == host
            for c in r["containers"]
            if (c.get("swarm") or "").endswith("_" + name) or c.get("service") == name
        ]
        actual_routes = [route for c in records for connection in c["destinations"] for route in connection["routes"]]
        confined = (
            len(records) == 1
            and bool(records[0]["destinations"])
            and bool(actual_routes)
            and all(
                (route["kind"] == "overlay_service" and route.get("provider") is True and route.get("worker_only") is True)
                or (route["kind"] == "overlay_task" and route.get("provider") is True and route.get("task_host") == host)
                or (route["kind"] == "worker_publication" and route.get("host") == host)
                for route in actual_routes
            )
        )
        if not confined or len(bindings) != 1 or bindings[0].get("kind") != "elsewhere" or bindings[0].get("inventory_host") != host:
            pending.append(name)
        else:
            binding = deepcopy(bindings[0])
            for flag in ["route_verified", "verified", "restart_verified"]:
                binding[flag] = False
            values["mgt_firewall_callers"][name] = [binding]
    if pending:
        raise ValueError("unresolved actual worker application routes: " + ", ".join(pending))
    # Write a separate proposal. Operator acceptance must promote its flags;
    # keep accepted mgt/native/Homepage entries, never replace with raw candidate.
    values["mgt_firewall_inputs_verified"] = False
    write(Path(inputs).with_name("worker-route-proposal.json"), values)


def render(projection, output):
    from jinja2 import Environment, StrictUndefined

    stage = read(projection)
    inputs = deepcopy(stage["render"])
    if not inputs["groups"]["tags_postgres"]:
        raise ValueError("Patroni inventory must not be empty")
    for host in inputs["groups"]["tags_postgres"]:
        ipaddress.ip_address(inputs["hostvars"][host]["local_ip"])
    inputs["service_common_service"] = {"settings": stage["definition"]["settings"]}
    template = (REPO / "ansible/roles/service_common/templates/configs/haproxy.cfg.j2").read_text()
    with open(output, "x", opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
        stream.write(
            Environment(undefined=StrictUndefined, trim_blocks=True, keep_trailing_newline=True).from_string(template).render(inputs)
        )


def ready(inputs, metadata, projection, require_destinations=True):
    """Only placement-dependent worker confirmations may remain before exclusion."""
    values, stage, reports = read(inputs), read(projection), read(metadata)
    policy = deepcopy(stage["policy"])
    active = values.get("mgt_firewall_active_endpoints")
    if (
        not isinstance(active, list)
        or any(not isinstance(i, str) for i in active)
        or len(active) != len(set(active))
        or set(active) != {i for e in policy["endpoints"] for i in e["ids"]}
    ):
        raise ValueError("all prepared endpoints must remain selected")
    policy["callers"] = values["mgt_firewall_callers"]
    FW.validate_policy(policy, require_verified=False)
    pending = []
    required = {name for e in policy["endpoints"] for name in e["callers"]}
    database = next(e["callers"] for e in policy["endpoints"] if "haproxy/postgres" in e["ids"])
    for name in required:
        host = stage["plan"]["principals"][name].get("inventory_hosts")
        if host in stage["workers"]:
            # Shared provider VIP is acceptable dependency evidence at this
            # stage; its worker-only routing cannot yet be accepted.
            pass
        else:
            bindings = policy["callers"].get(name, [])
            if not bindings or any(b.get("kind") in {"disabled", "elsewhere"} for b in bindings):
                pending.append(name + ": required mgt context unresolved")
            for binding in bindings:
                flags = ["verified", "restart_verified"] + (["physdev_verified"] if binding["kind"] == "container" else [])
                if any(binding.get(flag) is not True for flag in flags):
                    pending.append(name + ": operator matching/replacement acceptance pending")
            if name in MGT:
                managers = [r for r in reports if r.get("host") == stage["controller"]]
                if name == "forgejo":
                    if len(managers) != 1 or managers[0]["accounts"].get("podman-forgejo", {}).get("uid") != 1004:
                        pending.append("forgejo: fresh observed account UID changed/missing")
                else:
                    observed = [
                        c
                        for r in managers
                        for c in r["containers"]
                        if (c.get("swarm") or "").endswith("_" + name) or c.get("service") == name
                    ]
                    if (
                        len(observed) != 1
                        or len(bindings) != 1
                        or any(
                            (observed[0].get("binding") or {}).get(key) != bindings[0].get(key)
                            for key in ["runtime", "phase", "selector", "compose"]
                        )
                    ):
                        pending.append(name + ": fresh exact caller labels changed/missing; repeat preparation")
        if require_destinations and name in database and name not in SLICES:
            records = [
                c for r in reports for c in r["containers"] if (c.get("swarm") or "").endswith("_" + name) or c.get("service") == name
            ]
            if name == "forgejo":
                records = [c for r in reports for c in r["accounts"].get("podman-forgejo", {}).get("containers", [])]
            if (
                len(records) != 1
                or not records[0]["destinations"]
                or not all(
                    any(route.get("provider") is True or route["kind"] == "mgt_publication" for route in connection["routes"])
                    for connection in records[0]["destinations"]
                )
            ):
                pending.append(name + ": actual declared PostgreSQL destination still unresolved/idle")
    if pending:
        raise ValueError("before placement: " + "; ".join(pending))


def preconditions(inputs, metadata, projection):
    """Validate accepted confirmations before capture, retaining idle dependencies."""
    ready(inputs, metadata, projection, require_destinations=False)


def resume(batch, metadata, projection, output):
    """Complete only the interrupted read-only gates, never regenerate accepted inputs."""
    root = Path(batch)
    original, current_stage, reports = read(root / "stage.json"), read(projection), read(metadata)
    for key in ["definition", "render", "controller", "workers", "postgres_declarations"]:
        if original.get(key) != current_stage.get(key):
            raise ValueError(f"prepared {key} changed; do not resume this batch")
    previous = read(root / "after.json.metadata.json")
    if len(reports) != len(previous) or {r["host"] for r in reports} != {r["host"] for r in previous}:
        raise ValueError("capture does not cover the prepared hosts")
    for report in reports:
        old = next(r for r in previous if r["host"] == report["host"])
        if report["identity"] != old["identity"] or report["addresses"] != old["addresses"]:
            raise ValueError("prepared observed host identity changed; stop resume")
        if report.get("capture", {}).get("complete") is not True:
            raise ValueError("resume requires a completed bounded capture window")
    homepage(root / "working-policy.json", root / "homepage-inputs.yml")
    native_evidence((root / NATIVE_LOG).read_text())
    deployment(root / "deployment-inputs.json", "pre")
    # Only value-free repository declarations; no live environments/configuration.
    notes = {
        "bazarr": "PostgreSQL enabled; prep.postgres=haproxy:5432; Bazarr preparation writes postgresql.enabled/host/port to config.yaml.",
        "romm": "ROMM_DB_DRIVER=postgresql, DB_HOST=haproxy, DB_PORT=5432; common database preparation does not establish the application's actual driver/route.",
        "seerr": "Generated template declares DB_TYPE=postgres, DB_HOST=haproxy.<internal-zone>, DB_PORT=5432; current Swarm runtime must be evidenced separately.",
        "infisical": "Prepared rootless declaration uses the inventory mgt address:5432; the current Compose caller's route must be observed, not inferred from that future declaration.",
    }
    for name, note in notes.items():
        print(f"{name}: {note}", flush=True)
    ready(root / "working-policy.json", metadata, root / "stage.json")
    write(
        output,
        {
            "capture_metadata": str(Path(metadata).resolve()),
            "capture_stage": str(Path(projection).resolve()),
            "placement_changed": False,
            "confirmations_changed": False,
            "sha256": {
                name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                for name in ["working-policy.json", "deployment-inputs.json", "stage.json", "haproxy.cfg", "image-id"]
            },
        },
    )


def deployment(inputs, phase):
    values = read(inputs)
    expected = {
        "service_common_postgres_operator_context": True,
        "podman_services_pull_images": False,
        "services_mgt_backend_acl_ready": phase == "live",
    }
    if phase not in {"pre", "live"}:
        raise ValueError("deployment phase must be pre or live")
    for name, value in expected.items():
        if values.get(name) is not value:
            raise ValueError(f"{name}: expected boolean {value} for {phase} deployment inputs")
    ownership = values.get("services_rootless_data_ready")
    if not isinstance(ownership, dict) or ownership.get("haproxy") is not True:
        raise ValueError("services_rootless_data_ready.haproxy: ownership acceptance remains pending")


def homepage(inputs, accepted):
    import yaml

    values = read(inputs)
    saved = yaml.safe_load(Path(accepted).read_text())
    if "homepage/backend" not in values["mgt_firewall_active_endpoints"] or any(
        values["mgt_firewall_callers"].get(name) != bindings for name, bindings in saved["mgt_firewall_callers"].items()
    ):
        raise ValueError("accepted Homepage endpoint/bindings changed; stop before placement or policy writes")


def continuity(before, after, controller, excluded):
    original, current_provider = read(before), read(after)
    for key in ["id", "name", "image", "configs", "ports", "vips"]:
        if original[key] != current_provider[key]:
            raise ValueError(f"provider {key} changed; preserve the original workers/VIP/native config")
    constraint = "node.labels.ansible_host != " + controller
    expected = set(original.get("constraints") or []) | ({constraint} if excluded == "yes" else set())
    if set(current_provider.get("constraints") or []) != expected:
        raise ValueError("only the canonical mgt exclusion may change provider constraints")


def continuation_state(batch):
    """Emit only validated assignments, never execute the supplied state file."""
    values = {}
    for line in (Path(batch) / "rollback-state.sh").read_text().splitlines():
        match = re.fullmatch(r'declare -- (exclusion_started|policy_started|deployment_started|probe_unit)="([a-zA-Z0-9_.-]*)"', line)
        if not match or match[1] in values:
            raise ValueError("continuation state is incomplete, duplicated or incompatible")
        values[match[1]] = match[2]
    if set(values) != {"exclusion_started", "policy_started", "deployment_started", "probe_unit"} or any(
        values.get(key) != value
        for key, value in {"exclusion_started": "true", "policy_started": "true", "deployment_started": "false"}.items()
    ):
        raise ValueError("continuation requires excluded placement, started policy and no deployment")
    if values["probe_unit"] and not re.fullmatch(r"skynet-haproxy-acceptance-[a-zA-Z0-9_.-]+\.service", values["probe_unit"]):
        raise ValueError("continuation probe unit is not the recorded acceptance unit")
    print("\n".join(key + "=" + shlex.quote(value) for key, value in values.items()))


def continuation_policy(batch):
    """Reuse strict inputs and installed-policy audit without reinstalling policy."""
    root = Path(batch)
    deployment(root / "deployment-inputs.json", "live")
    homepage(root / "working-policy.json", root / "homepage-inputs.yml")
    values = read(root / "working-policy.json")
    policy = deepcopy(read(root / "stage.json")["policy"])
    active = values.get("mgt_firewall_active_endpoints")
    expected = {identity for endpoint in policy["endpoints"] for identity in endpoint["ids"]}
    if not isinstance(active, list) or any(not isinstance(identity, str) for identity in active) or set(active) != expected:
        raise ValueError("continuation active endpoints differ from the prepared policy")
    policy["callers"] = values["mgt_firewall_callers"]
    policy["inputs_verified"] = values["mgt_firewall_inputs_verified"]
    FW.validate_policy(policy, require_verified=True)
    installed = read("/etc/skynet-mgt-firewall/policy.json")
    for key in ["schema", "backend", "callers", "endpoints", "inventory_address", "inventory_host", "inputs_verified", "principals"]:
        if installed.get(key) != policy.get(key):
            raise ValueError("continuation installed policy differs from prepared " + key)
    audit = json.loads(run(["/usr/bin/python3", "/etc/skynet-mgt-firewall/policy.py", "check"]))
    if audit.get("compliant") is not True or audit.get("families") != [4, 6] or audit.get("pending"):
        raise ValueError("continuation requires a compliant both-family installed policy")


def stop_recorded_probe(batch, unit):
    """Stop only the exact owned transient listener; tolerate automatic expiry."""
    if not re.fullmatch(r"skynet-haproxy-acceptance-[a-zA-Z0-9_.-]+\.service", unit):
        raise ValueError("invalid recorded probe unit")
    command = ["/usr/bin/python3", str(Path(batch).resolve() / "haproxy-cutover.py"), "listen", "5432", "18405"]
    properties = ["LoadState", "Id", "Transient", "User", "Slice", "RuntimeMaxUSec", "ExecStart", "MainPID", "ActiveState", "InvocationID"]

    def inspect_unit():
        return dict(
            line.split("=", 1)
            for line in run(
                ["systemctl", "show", unit, "--no-pager", *[argument for prop in properties for argument in ["-p", prop]]]
            ).splitlines()
            if "=" in line
        )

    def owned(fields):
        arguments = re.findall(r"argv\[\]=(.*?) ;", fields.get("ExecStart", ""))
        if (
            fields.get("LoadState") != "loaded"
            or fields.get("Id") != unit
            or fields.get("Transient") != "yes"
            or fields.get("User") != "root"
            or fields.get("Slice") != "skynet_pg_recovery.slice"
            or fields.get("RuntimeMaxUSec") != "4min"
            or len(arguments) != 1
            or shlex.split(arguments[0]) != command
        ):
            raise ValueError("recorded probe unit ownership or listener command differs; refusing stop")
        pid = fields.get("MainPID", "")
        if not pid.isdecimal() or (pid == "0" and fields.get("ActiveState") not in {"inactive", "failed"}):
            raise ValueError("recorded probe process state is ambiguous; refusing stop")
        invocation = fields.get("InvocationID", "")
        if not re.fullmatch(r"[a-fA-F0-9]{32}", invocation) and not (pid == "0" and invocation == ""):
            raise ValueError("recorded probe invocation is ambiguous; refusing stop")
        return pid

    initial = inspect_unit()
    if initial.get("LoadState") == "not-found":
        return
    pid = owned(initial)
    if pid == "0":
        return
    missing_process = False
    try:
        if Path("/proc", pid, "cmdline").read_bytes().split(b"\0")[:-1] != [os.fsencode(x) for x in command]:
            raise ValueError("recorded probe process command differs; refusing stop")
        if "0::/skynet_pg_recovery.slice/" + unit not in Path("/proc", pid, "cgroup").read_text().splitlines():
            raise ValueError("recorded probe process cgroup differs; refusing stop")
    except FileNotFoundError:
        missing_process = True
    current = inspect_unit()
    if current.get("LoadState") == "not-found":
        return
    current_pid = owned(current)
    if current_pid == "0" and current.get("InvocationID") in {initial["InvocationID"], ""}:
        return
    if current.get("InvocationID") != initial["InvocationID"] or current_pid != pid or missing_process:
        raise ValueError("recorded probe process/invocation changed before stop")
    try:
        run(["systemctl", "stop", unit])
    except RuntimeError:
        if inspect_unit().get("LoadState") != "not-found":
            raise
    final = inspect_unit()
    if final.get("LoadState") == "not-found":
        return
    if owned(final) != "0" or final.get("InvocationID") not in {initial["InvocationID"], ""}:
        raise ValueError("recorded probe has not stopped")


def listener(ports):
    sockets = []
    try:
        for family, bind in [(socket.AF_INET, "0.0.0.0"), (socket.AF_INET6, "::")]:
            for port in ports:
                stream = socket.socket(family)
                if family == socket.AF_INET6:
                    stream.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                stream.bind((bind, int(port)))
                stream.listen(32)
                sockets.append(stream)
        # Bounded handshake-only active listener; never read/send payload.
        time.sleep(240)
    finally:
        for stream in sockets:
            stream.close()


def negative_command(argv, report=True):
    """Label route stderr, including successful commands that emitted warnings."""
    result = subprocess.run(argv, text=True, capture_output=True, check=False, timeout=15)
    if report:
        print(json.dumps({"operation": argv, "status": result.returncode, "stderr": result.stderr.strip()}), flush=True)
    if result.returncode or result.stderr.strip():
        raise RuntimeError("negative acceptance command failed: " + shlex.join(argv) + ": " + result.stderr.strip())
    return result.stdout


def negative_socket(destination, port, interface="", execute=negative_command, local=False):
    address = ipaddress.ip_address(destination)
    argv = ["ip", "-j", "-" + str(address.version), "route", "get", str(address)]
    if interface:
        argv += ["oif", interface]
    routes = json.loads(execute(argv))
    if len(routes) != 1 or routes[0].get("type") in {"unreachable", "blackhole", "prohibit"}:
        raise ValueError("one usable numeric route is required")
    route = routes[0]
    source = route.get("prefsrc") or route.get("src")
    if not source or ipaddress.ip_address(source).version != address.version or not route.get("dev"):
        raise ValueError("route lacks an explicit source/interface")
    if interface and route["dev"] != interface and not (local and route.get("type") == "local"):
        raise ValueError("route uses a different interface")
    scope = socket.if_nametoindex(interface or route["dev"]) if address.is_link_local else 0
    stream = socket.socket(socket.AF_INET6 if address.version == 6 else socket.AF_INET)
    try:
        stream.settimeout(3)
        stream.bind((source, 0, 0, scope) if address.version == 6 else (source, 0))
        return stream, {
            "source": list(stream.getsockname()),
            "destination": [str(address), port],
            "route": route,
            "route_command": argv,
            "scope": scope,
            "family": address.version,
        }
    except BaseException:
        stream.close()
        raise


def negative_connect(stream, plan):
    target = tuple(plan["destination"])
    if plan["family"] == 6:
        target += (0, plan["scope"])
    try:
        stream.connect(target)
        result = "connected"
    except TimeoutError:
        result = "timeout"
    except OSError as error:
        result = "error:" + str(error.errno) + ":" + str(error)
    return {"result": result, "source": list(stream.getsockname()), "destination": plan["destination"]}


def negative_peer(destination, port, interface):
    stream, plan = negative_socket(destination, port, interface, execute=lambda argv: negative_command(argv, report=False))
    try:
        plan["host_identity"] = {"hostname": socket.gethostname(), "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}
        print(json.dumps({"ready": plan}), flush=True)
        if sys.stdin.readline().strip() != "PROBE":
            raise ValueError("probe synchronization missing")
        print(json.dumps(negative_connect(stream, plan)), flush=True)
    finally:
        stream.close()


def negative_drop(tool, chain, port, execute=run):
    """Select the exact existing owned LOCAL/port DROP, retaining its rule index."""
    selected = []
    position = 0
    for line in execute([tool + "-save", "-c", "-t", "mangle"]).splitlines():
        fields = shlex.split(line)
        if fields[1:3] != ["-A", chain]:
            continue
        position += 1
        match = fields[3:]
        desired = ["-p", "tcp", "-m", "addrtype", "--dst-type", "LOCAL", "--dport", str(port), "-j", "DROP"]
        if FW.OWNED.normalized(match) == FW.OWNED.normalized(desired):
            counter = re.fullmatch(r"\[(\d+):\d+\]", fields[0])
            if not counter:
                raise ValueError("DROP packet counter missing")
            selected.append({"position": position, "packets": int(counter[1]), "rule": match})
    if len(selected) != 1:
        raise ValueError("one exact owned DROP is required for " + chain + ":" + str(port))
    return selected[0]


def negative_observe(plan, local, probe, active, execute=run):
    """Counter immediately before the unchanged DROP; no acceptance/return target."""
    # Reuse the installed reconciler lock only for this bounded probe and cleanup.
    with FW.OWNED.writer_lock():
        tool = "ip6tables" if plan["family"] == 6 else "iptables"
        chain = "SKY-MGT-OUT" if local else "SKY-MGT-PRE"
        port = plan["destination"][1]
        active()
        before = negative_drop(tool, chain, port, execute)
        token = "skynet-haproxy-negative-" + uuid.uuid4().hex
        match = [
            "-p",
            "tcp",
            "-s",
            plan["source"][0],
            "-d",
            plan["destination"][0],
            "--sport",
            str(plan["source"][1]),
            "--dport",
            str(port),
            "-m",
            "comment",
            "--comment",
            token,
        ]
        deletion = [tool, "-w", "5", "-t", "mangle", "-D", chain, *match]
        print(json.dumps({"exact_cleanup": shlex.join(deletion)}), flush=True)
        execute([tool, "-w", "5", "-t", "mangle", "-I", chain, str(before["position"]), *match])
        try:
            result = probe()
            active()
            observations = []
            for line in execute([tool + "-save", "-c", "-t", "mangle"]).splitlines():
                fields = shlex.split(line)
                if fields[1:3] == ["-A", chain] and "--comment" in fields and fields[fields.index("--comment") + 1] == token:
                    if "-j" in fields or "-g" in fields:
                        raise ValueError("temporary observation changed into an action")
                    actual_match = fields[3:]
                    for rule in [actual_match, match]:
                        index = rule.index("-d") + 1
                        rule[index] = str(ipaddress.ip_interface(rule[index]).ip)
                    if FW.OWNED.normalized(actual_match) != FW.OWNED.normalized(match):
                        raise ValueError("temporary observation identity changed")
                    observations.append(int(re.fullmatch(r"\[(\d+):\d+\]", fields[0])[1]))
            # Read the observer before the final DROP counter so its interval
            # stays inside the DROP interval even if a retransmission arrives
            # between reads. Retain the strict delta >= observation check.
            after = negative_drop(tool, chain, port, execute)
            delta = after["packets"] - before["packets"]
            evidence = {
                "probe": result,
                "route": plan["route"],
                "family": plan["family"],
                "local_root": local,
                "owned_chain": chain,
                "owned_drop_rule": before["rule"],
                "drop_increase": delta,
                "observation_packets": observations,
            }
            print(json.dumps(evidence), flush=True)
            if (
                result["result"] != "timeout"
                or result["source"] != plan["source"]
                or result["destination"] != plan["destination"]
                or len(observations) != 1
                or observations[0] <= 0
                or delta < observations[0]
                or after["position"] != before["position"] + 1
                or after["rule"] != before["rule"]
            ):
                raise ValueError("denial requires stable source, timeout, exact observation and matching owned DROP increase")
            return evidence
        finally:
            execute(deletion)


def negative_listener(batch, unit, execute=negative_command):
    fields = dict(
        line.split("=", 1)
        for line in execute(
            [
                "systemctl",
                "show",
                unit,
                "--no-pager",
                "-p",
                "ActiveState",
                "-p",
                "MainPID",
                "-p",
                "RuntimeMaxUSec",
                "-p",
                "Slice",
                "-p",
                "User",
            ]
        ).splitlines()
        if "=" in line
    )
    if (
        fields.get("ActiveState") != "active"
        or fields.get("RuntimeMaxUSec") != "4min"
        or fields.get("Slice") != "skynet_pg_recovery.slice"
        or fields.get("User") != "root"
    ):
        raise ValueError("recorded 240-second root probe unit is not active with its original limit/slice")
    pid = fields.get("MainPID", "")
    if not pid.isdecimal() or int(pid) <= 0:
        raise ValueError("probe listener PID missing")
    if Path("/proc", pid, "cmdline").read_bytes().split(b"\0")[:-1] != [
        os.fsencode(x) for x in ["/usr/bin/python3", str(batch / "haproxy-cutover.py"), "listen", "5432", "18405"]
    ]:
        raise ValueError("probe unit command differs from the paused runner")
    if ("0::/skynet_pg_recovery.slice/" + unit) not in Path("/proc", pid, "cgroup").read_text().splitlines():
        raise ValueError("listener cgroup differs from recorded probe unit")
    for family, wildcard in [(4, "0.0.0.0"), (6, "[::]")]:
        rows = execute(["ss", "-H", "-lntp", "-" + str(family), "( sport = :5432 or sport = :18405 )"]).splitlines()
        allowed = {wildcard, "*"}
        if (
            len(rows) != 2
            or {row.split()[3].rsplit(":", 1)[1] for row in rows} != {"5432", "18405"}
            or any(row.split()[3].rsplit(":", 1)[0] not in allowed for row in rows)
        ):
            raise ValueError("both wildcard IPv" + str(family) + " listeners must be active")
        if any({int(p) for p in re.findall(r"pid=(\d+)", row)} != {int(pid)} for row in rows):
            raise ValueError("listener socket is not exclusively owned by the recorded unit")
    print(json.dumps({"probe_unit_state": fields, "listener_families": [4, 6], "ports": [5432, 18405]}), flush=True)
    return fields


def negative_peer_ssh(peer):
    """Keep SSH trust/config/key-agent context with the original sudo operator."""
    identity = peer.get("operator")
    sudo_uid = os.environ.get("SUDO_UID", "")
    if not sudo_uid.isdecimal() or int(sudo_uid) <= 0 or not isinstance(identity, dict):
        raise ValueError("peer SSH requires the recorded non-root sudo operator")
    operator = pwd.getpwuid(int(sudo_uid))
    if (
        type(identity.get("uid")) is not int
        or identity["uid"] != operator.pw_uid
        or identity.get("account") != operator.pw_name
        or identity.get("home") != operator.pw_dir
    ):
        raise ValueError("peer SSH operator identity differs from the original sudo caller")
    prefix = ["runuser", "-u", operator.pw_name, "--", "env", "-u", "SSH_AUTH_SOCK", "HOME=" + operator.pw_dir]
    agent = identity.get("ssh_auth_sock")
    if agent is not None:
        if not isinstance(agent, str) or not Path(agent).is_absolute() or any(c in agent for c in "\r\n\0"):
            raise ValueError("invalid operator SSH agent socket path")
        prefix.append("SSH_AUTH_SOCK=" + agent)
    prefix += ["/bin/sh", "-c", 'cd "$HOME" || exit; exec "$@"', "skynet-haproxy-peer"]
    return prefix + [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=8",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "UpdateHostKeys=no",
        "-p",
        str(peer["ansible_port"]),
        peer["ansible_user"] + "@" + peer["ansible_host"],
    ]


def negative_tailscale_addresses(links, version):
    """Usable unicast candidates; the live route must still select this source."""
    interfaces = [link for link in links if link["ifname"] == "tailscale0"]
    if len(interfaces) != 1:
        return []
    selected = []
    for record in interfaces[0].get("addr_info", []):
        address = ipaddress.ip_address(record["local"])
        if address.version != version:
            continue
        if (
            record.get("scope") != "global"
            or record.get("family") != ("inet6" if version == 6 else "inet")
            or address.is_link_local
            or address.is_loopback
            or address.is_multicast
            or address.is_unspecified
            or any(record.get(flag) or flag in record.get("flags", []) for flag in ["tentative", "dadfailed", "deprecated"])
            or record.get("valid_life_time") == 0
            or record.get("preferred_life_time") == 0
        ):
            continue
        selected.append({"address": str(address), "interface": "tailscale0"})
    return selected


def start_negative_probe(batch, unit):
    for family in [4, 6]:
        if negative_command(["ss", "-H", "-lnt", "-" + str(family), "( sport = :5432 or sport = :18405 )"]).strip():
            raise ValueError("both TCP ports must be free in IPv" + str(family) + " before starting the recorded probe")
    if run(["systemctl", "show", unit, "--value", "-p", "LoadState"]).strip() != "not-found":
        raise ValueError("recorded probe unit still exists; do not replace an active/failed unit")
    print(
        json.dumps(
            {
                "probe_unit": unit,
                "runtime_seconds": 240,
                "historical_rtnetlink": "runner all-protocol ss free-port check; failing request/family unrecorded",
            }
        ),
        flush=True,
    )
    negative_command(
        [
            "systemd-run",
            "--quiet",
            "--collect",
            "--unit=" + unit,
            "--slice=skynet_pg_recovery.slice",
            "--property=User=root",
            "--property=UMask=0077",
            "--property=RuntimeMaxSec=240",
            "/usr/bin/python3",
            str(batch / "haproxy-cutover.py"),
            "listen",
            "5432",
            "18405",
        ]
    )
    time.sleep(2)


def actual_state(batch):
    state = (batch / "rollback-state.sh").read_text()
    fields = {}
    for line in state.splitlines():
        match = re.fullmatch(r'declare -- (exclusion_started|policy_started|deployment_started|probe_unit)="([a-zA-Z0-9_.-]*)"', line)
        if not match or match[1] in fields:
            raise ValueError("actual-service acceptance requires unambiguous recorded state")
        fields[match[1]] = match[2]
    if fields != {"exclusion_started": "true", "policy_started": "true", "deployment_started": "true", "probe_unit": ""}:
        raise ValueError("actual-service acceptance requires completed deployment and no temporary probe")
    deployment(batch / "deployment-inputs.json", "live")


def service_listener(batch, execute=negative_command):
    """Validate the actual account/unit/container and all declared publications."""
    owner = pwd.getpwnam("podman-haproxy")
    if owner.pw_uid != 1011:
        raise ValueError("prepared HAProxy account UID changed")
    prefix = account_command(owner.pw_name)
    fields = dict(
        line.split("=", 1)
        for line in execute(
            prefix
            + [
                "systemctl",
                "--user",
                "show",
                "haproxy.service",
                "--no-pager",
                "-p",
                "ActiveState",
                "-p",
                "ControlGroup",
                "-p",
                "InvocationID",
            ]
        ).splitlines()
        if "=" in line
    )
    cgroup = f"/user.slice/user-{owner.pw_uid}.slice/user@{owner.pw_uid}.service/app.slice/haproxy.service"
    if (
        fields.get("ActiveState") != "active"
        or fields.get("ControlGroup") != cgroup
        or not re.fullmatch(r"[0-9a-f]{32}", fields.get("InvocationID", ""))
    ):
        raise ValueError("actual HAProxy user unit is not active in its prepared cgroup")
    records = json.loads(
        execute(
            prefix
            + [
                "/usr/bin/podman",
                "--remote=false",
                "container",
                "inspect",
                "--format",
                '{"id":{{json .ID}},"pid":{{.State.Pid}},"running":{{json .State.Running}},"image":{{json .Image}},"ports":{{json .NetworkSettings.Ports}}}',
                "haproxy",
            ]
        )
    )
    if not isinstance(records, dict):
        raise ValueError("actual HAProxy inspection must return one projected object")
    if (
        records.get("running") is not True
        or type(records.get("pid")) is not int
        or records["pid"] <= 0
        or not isinstance(records.get("id"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", records.get("id", ""))
    ):
        raise ValueError("one running actual HAProxy container is required")
    if not isinstance(records.get("image"), str) or records["image"].removeprefix("sha256:") != (
        batch / "image-id"
    ).read_text().strip().removeprefix("sha256:"):
        raise ValueError("actual HAProxy image differs from the prepared image")
    expected = {}
    for port in read(batch / "stage.json")["definition"]["ports"].values():
        expected[str(port["target"]) + "/" + port.get("protocol", "tcp")] = [
            {"HostIp": port["host_ip"], "HostPort": str(port["published"])}
        ]
    if (
        not isinstance(records.get("ports"), dict)
        or {key: value for key, value in records["ports"].items() if value not in [None, []]} != expected
    ):
        raise ValueError("actual HAProxy publications differ from the prepared definition")
    listeners = set()
    listener_owners = []
    for family in [4, 6]:
        rows = execute(["ss", "-H", "-lntp", "-" + str(family), "( sport = :5432 or sport = :18405 )"]).splitlines()
        for row in rows:
            address, port = row.split()[3].rsplit(":", 1)
            listeners.add((str(ipaddress.ip_address(address.strip("[]"))), port))
            pids = set(re.findall(r"pid=(\d+)", row))
            if not pids:
                raise ValueError("actual published listener has no socket owner")
            listener_owners.append([str(ipaddress.ip_address(address.strip("[]"))), port, sorted(pids)])
            for pid in pids:
                status = Path("/proc", pid, "status").read_text()
                uid = re.search(r"^Uid:\s+(\d+)\s+(\d+)", status, re.M)
                groups = Path("/proc", pid, "cgroup").read_text().splitlines()
                if (
                    not uid
                    or {int(uid[1]), int(uid[2])} != {owner.pw_uid}
                    or not any(line == "0::" + cgroup or line.startswith("0::" + cgroup + "/") for line in groups)
                ):
                    raise ValueError("actual published listener is not owned by the HAProxy account/unit")
    required = {(binding["HostIp"], binding["HostPort"]) for bindings in expected.values() for binding in bindings}
    if listeners != required:
        raise ValueError("all declared actual HAProxy listeners must be active, with no competing publications")
    result = {
        "unit": fields,
        "container": records["id"],
        "pid": records["pid"],
        "process": PREFLIGHT.process_identity(records["pid"], execute),
        "image": records["image"],
        "listeners": sorted(listeners),
        "listener_owners": sorted(listener_owners),
        "listener_families": sorted({ipaddress.ip_address(address).version for address, _ in listeners}),
    }
    print(json.dumps({"actual_service": result, "ipv6_listener_claimed": 6 in result["listener_families"]}), flush=True)
    return result


def accept_native(batch_path):
    """Actual-service handshakes from the two existing native contexts."""
    batch = Path(batch_path).resolve()
    actual_state(batch)
    continuation_policy(batch)
    before = service_listener(batch)
    values, stage = read(batch / "working-policy.json"), read(batch / "stage.json")
    address = stage["policy"]["inventory_address"]
    for name, path in SLICES.items():
        bindings = values["mgt_firewall_callers"].get(name, [])
        if len(bindings) != 1 or any(
            bindings[0].get(key) != value
            for key, value in {
                "kind": "local",
                "phase": "native",
                "account": "root",
                "uid": 0,
                "cgroup": path,
                "verified": True,
                "restart_verified": True,
            }.items()
        ):
            raise ValueError(name + ": accepted exact native binding is required")
        match = FW.caller_match(bindings[0], 4, True)
        token = "skynet-haproxy-observe-" + uuid.uuid4().hex
        rules = [
            (
                "iptables",
                table,
                "OUTPUT",
                [
                    "-p",
                    "tcp",
                    "-m",
                    "conntrack",
                    "--ctdir",
                    "ORIGINAL",
                    "--ctorigdst",
                    address,
                    "--ctorigdstport",
                    "5432",
                    *match,
                    "-m",
                    "comment",
                    "--comment",
                    token,
                ],
            )
            for table in ["mangle", "filter"]
        ]
        result = {}

        def probe(name=name, path=path, result=result):
            observed = json.loads(
                run(["/usr/bin/python3", "/usr/local/libexec/skynet-mgt-operator/mgt-operator.py", "probe", name, address, "5432", "0"])
            )
            if not isinstance(observed, dict):
                raise ValueError("native probe must return one projected object")
            if (
                type(observed.get("socket_uid")) is not int
                or observed["socket_uid"] != 0
                or type(observed.get("process_uid")) is not int
                or observed["process_uid"] != 0
                or not isinstance(observed.get("cgroup"), str)
                or not observed.get("cgroup", "").startswith(path + "/")
                or observed.get("destination") != [address, 5432]
            ):
                raise ValueError("native actual-service probe identity/destination changed")
            result.update(observed)

        with FW.OWNED.writer_lock():
            counts = observe_rules(rules, probe)
        if service_listener(batch) != before:
            raise ValueError("actual HAProxy identity changed during native acceptance")
        print(
            json.dumps({"native_caller": name, "actual_service_probe": result, "counters": counts, "confirmations_changed": False}),
            flush=True,
        )


def negative(batch_path, peer_path, actual=False):
    """One finite negative batch; no placement, deployment or confirmation writes."""
    import inspect
    import select

    batch = Path(batch_path).resolve()
    if os.getuid() != 0 or os.geteuid() != 0:
        raise ValueError("negative acceptance must run as ordinary mgt root after sudo")
    own_cgroup = Path("/proc/self/cgroup").read_text()
    if any(parent in own_cgroup for parent in SLICES.values()):
        raise ValueError("ordinary-root control must be outside both authorized operator slices")
    protected = ["working-policy.json", "deployment-inputs.json", "rollback-state.sh"]
    original = {name: (batch / name).read_bytes() for name in protected}
    state = original["rollback-state.sh"].decode()
    if actual:
        actual_state(batch)
        unit = "haproxy.service"
    else:
        matches = re.findall(r'^declare -- probe_unit="([a-zA-Z0-9_.-]+\.service)"$', state, re.M)
        if len(matches) != 1 or not matches[0].startswith("skynet-haproxy-acceptance-"):
            raise ValueError("one recorded paused-runner probe unit is required")
        if 'declare -- policy_started="true"' not in state or 'declare -- deployment_started="false"' not in state:
            raise ValueError("negative batch applies only to the paused predeployment policy phase")
        unit = matches[0]
    stage, values, peer = read(batch / "stage.json"), read(batch / "working-policy.json"), read(peer_path)
    policy = deepcopy(stage["policy"])
    policy["callers"] = values["mgt_firewall_callers"]
    policy["inputs_verified"] = values["mgt_firewall_inputs_verified"]
    FW.validate_policy(policy, require_verified=True)
    installed = read("/etc/skynet-mgt-firewall/policy.json")
    for key in ["callers", "endpoints", "inventory_address", "inventory_host", "inputs_verified", "principals"]:
        if installed[key] != policy[key]:
            raise ValueError("installed policy differs from prepared " + key)
    audit = json.loads(run(["/usr/bin/python3", "/etc/skynet-mgt-firewall/policy.py", "check"]))
    if audit.get("compliant") is not True or audit.get("families") != [4, 6] or audit.get("pending"):
        raise ValueError("installed both-family policy audit failed")
    reports = read(batch / "worker-offline-20261009T200449Z-2609904/worker-only.json.metadata.json")
    expected = {r["host"]: r for r in reports}
    if peer["inventory_host"] not in stage["workers"] or peer["inventory_address"] != expected[peer["inventory_host"]]["inventory_address"]:
        raise ValueError("peer transport differs from validated inventory host")
    ipaddress.ip_address(peer["ansible_host"])
    if (
        not re.fullmatch(r"[a-zA-Z0-9_-]+", peer["ansible_user"])
        or type(peer["ansible_port"]) is not int
        or not 1 <= peer["ansible_port"] <= 65535
    ):
        raise ValueError("invalid inventory SSH transport")
    ssh = negative_peer_ssh(peer)
    identity_program = (
        "import json,socket,subprocess;from pathlib import Path;"
        'print(json.dumps({"identity":{"hostname":socket.gethostname(),"boot_id":Path("/proc/sys/kernel/random/boot_id").read_text().strip()},'
        '"links":json.loads(subprocess.check_output(["ip","-j","address","show"],text=True))}))'
    )

    def peer_command(program, arguments, operation):
        result = subprocess.run(
            ssh + [shlex.join(["/usr/bin/python3", "-c", program, *arguments])], text=True, capture_output=True, check=False, timeout=15
        )
        print(
            json.dumps(
                {"peer": peer["inventory_host"], "operation": operation, "status": result.returncode, "stderr": result.stderr.strip()}
            ),
            flush=True,
        )
        if result.returncode or result.stderr.strip():
            raise ValueError("peer operation failed: " + str(operation) + ": " + result.stderr.strip()[:2000])
        return result.stdout

    observed_peer = json.loads(peer_command(identity_program, [], "observed host identity/address projection"))
    links = json.loads(negative_command(["ip", "-j", "address", "show"]))
    if (
        PREFLIGHT.observed_identity() != expected[stage["controller"]]["identity"]
        or observed_peer["identity"] != expected[peer["inventory_host"]]["identity"]
    ):
        raise ValueError("observed mgt/peer hostname or boot identity changed")

    def lan_interface(links, address):
        selected = [link["ifname"] for link in links if any(a["local"] == address for a in link.get("addr_info", []))]
        if len(selected) != 1:
            raise ValueError("inventory address must identify one interface")
        return selected[0]

    lan = lan_interface(links, policy["inventory_address"])
    peer_lan = lan_interface(observed_peer["links"], peer["inventory_address"])
    addresses = [(link["ifname"], a["local"]) for link in links for a in link.get("addr_info", [])]
    lan4 = [a for dev, a in addresses if dev == lan and ipaddress.ip_address(a).version == 4]
    lan6 = [a for dev, a in addresses if dev == lan and ipaddress.ip_address(a).version == 6]
    ts4, ts6, peer_sources = [], [], {}
    if len(lan4) < 2:
        raise ValueError("alternate mgt LAN IPv4 unavailable on inventory interface " + lan)
    for version, selected in [(4, ts4), (6, ts6)]:
        candidates = negative_tailscale_addresses(links, version)
        sources = negative_tailscale_addresses(observed_peer["links"], version)
        if len(candidates) != 1 or len(sources) != 1:
            raise ValueError(
                f"Tailscale IPv{version}: require one usable global-scope unicast address on tailscale0; "
                f"mgt candidates={len(candidates)}, peer candidates={len(sources)}"
            )
        selected.append(candidates[0]["address"])
        peer_sources[selected[0]] = sources[0]["address"]
        print(
            json.dumps(
                {
                    "coverage": f"Tailscale IPv{version}",
                    "destination": selected[0],
                    "peer_source": sources[0]["address"],
                    "interface": "tailscale0",
                }
            ),
            flush=True,
        )
    if not lan6:
        print(
            json.dumps({"coverage": "LAN IPv6", "status": "unconfigured", "required": False, "interface": lan, "denial_tested": False}),
            flush=True,
        )
    cases = [(a, peer_lan, "LAN IPv4") for a in lan4]
    cases += [(a, peer_lan, "LAN IPv6") for a in lan6]
    cases += [(a, "tailscale0", "Tailscale IPv4/IPv6") for a in ts4 + ts6]
    local_cases = [
        (a, lan if ipaddress.ip_address(a).is_link_local else "", "ordinary local root")
        for a in dict.fromkeys(lan4 + lan6 + ts4 + ts6 + ["127.0.0.1", "::1"])
    ]
    # Route preflight precedes listener creation; each actual probe also resolves
    # and binds a fresh source. Nothing inferred from the historical RTNETLINK line.
    for address, interface, label in cases:
        argv = ["ip", "-j", "-" + str(ipaddress.ip_address(address).version), "route", "get", address, "oif", interface]
        route_program = "import subprocess,sys;raise SystemExit(subprocess.call(sys.argv[1:]))"
        print(json.dumps({"peer": peer["inventory_host"], "coverage": label, "route_command": argv}), flush=True)
        route = json.loads(peer_command(route_program, argv, argv))
        if (
            len(route) != 1
            or route[0].get("type") in {"unreachable", "blackhole", "prohibit"}
            or route[0].get("dev") != interface
            or not (route[0].get("prefsrc") or route[0].get("src"))
        ):
            raise ValueError("peer route/source unavailable for " + address)
        if address in peer_sources and str(ipaddress.ip_address(route[0].get("prefsrc") or route[0].get("src"))) != peer_sources[address]:
            raise ValueError("Tailscale route does not select the observed usable peer source for " + address)
    if actual:
        original_service = service_listener(batch)

        def active():
            if service_listener(batch) != original_service:
                raise ValueError("actual HAProxy unit/container/process/listener changed during acceptance")
    else:
        start_negative_probe(batch, unit)

        def active():
            return negative_listener(batch, unit)

    active()
    native = load("ansible/operator/mgt-operator.py", "negative_native_socket")
    peer_program = (
        "import ipaddress,json,re,shlex,socket,subprocess,sys\nfrom pathlib import Path\n"
        + "\n".join(inspect.getsource(f) for f in [negative_command, negative_socket, negative_connect, negative_peer])
        + "\ntry:\n negative_peer(sys.argv[1],int(sys.argv[2]),sys.argv[3])\n"
        "except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as error:\n"
        " print('negative-peer: '+str(error),file=sys.stderr);sys.exit(1)\n"
    )
    count = 0
    for local, probes in [(False, cases), (True, local_cases)]:
        for address, interface, label in probes:
            for port in [5432, 18405]:
                active()
                print(
                    json.dumps({"coverage": label, "destination": [address, port], "local_root_cgroup": own_cgroup if local else None}),
                    flush=True,
                )
                if local:
                    stream, plan = negative_socket(address, port, interface, local=True)
                    try:

                        def root_probe(stream=stream, plan=plan):
                            result = negative_connect(stream, plan)
                            result["socket_uid"] = native.socket_uid(stream)
                            result["process_uid"] = os.getuid()
                            if result["socket_uid"] != 0:
                                raise ValueError("ordinary-root probe socket is not owned by UID 0")
                            return result

                        negative_observe(plan, True, root_probe, active)
                    finally:
                        stream.close()
                else:
                    child = subprocess.Popen(
                        ssh + [shlex.join(["/usr/bin/python3", "-u", "-c", peer_program, address, str(port), interface])],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    try:
                        while True:
                            if not select.select([child.stdout], [], [], 15)[0]:
                                raise ValueError("peer probe readiness timed out")
                            line = child.stdout.readline()
                            if not line:
                                raise ValueError("peer probe failed: " + child.stderr.read().strip()[:2000])
                            record = json.loads(line)
                            print(json.dumps({"peer": peer["inventory_host"], **record}), flush=True)
                            if "ready" in record:
                                plan = record["ready"]
                                if plan.get("host_identity") != expected[peer["inventory_host"]]["identity"]:
                                    raise ValueError("peer identity changed during the listener window")
                                if address in peer_sources and str(ipaddress.ip_address(plan["source"][0])) != peer_sources[address]:
                                    raise ValueError("Tailscale peer source changed during the listener window")
                                break

                        def probe(child=child):
                            stdout, stderr = child.communicate("PROBE\n", timeout=10)
                            if child.returncode or stderr.strip():
                                raise ValueError("peer probe failed: " + stderr.strip()[:2000])
                            return json.loads(stdout)

                        negative_observe(plan, False, probe, active)
                    finally:
                        if child.poll() is None:
                            child.kill()
                        child.wait(timeout=10)
                count += 1
                if any((batch / name).read_bytes() != content for name, content in original.items()):
                    raise ValueError("protected batch inputs/state changed during negative acceptance")
    active()
    print(
        json.dumps(
            {
                "negative_acceptance": "passed",
                "probes": count,
                "probe_unit": unit,
                "confirmations_changed": False,
                "actual_service": actual,
                "cleanup_owner": "exact observation rules only; actual HAProxy unchanged"
                if actual
                else "recorded maintenance rollback or automatic 240-second unit expiry; no runner liveness assumed",
            }
        ),
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation",
        choices=[
            "baseline-inputs",
            "retained-policy",
            "rollback-policy",
            "working",
            "hooks",
            "accept",
            "routes",
            "render",
            "ready",
            "deployment",
            "homepage",
            "listen",
            "negative",
            "negative-service",
            "accept-native",
            "continuation-state",
            "continuation-policy",
            "stop-probe",
            "provider",
            "continuity",
            "mounts",
            "preconditions",
            "resume",
        ],
    )
    parser.add_argument("args", nargs="+")
    args = parser.parse_args()
    counts = {
        "baseline-inputs": 1,
        "retained-policy": 1,
        "rollback-policy": 1,
        "working": 4,
        "hooks": 10,
        "accept": 2,
        "routes": 4,
        "render": 2,
        "ready": 3,
        "deployment": 2,
        "homepage": 2,
        "provider": 1,
        "continuity": 4,
        "mounts": 2,
        "preconditions": 3,
        "resume": 4,
        "negative": 2,
        "negative-service": 2,
        "accept-native": 1,
        "continuation-state": 1,
        "continuation-policy": 1,
        "stop-probe": 2,
    }
    if args.operation in counts and len(args.args) != counts[args.operation]:
        parser.error(f"{args.operation} requires {counts[args.operation]} arguments")
    if args.operation == "hooks":
        hooks(args.args[0], args.args[1], args.args[2:])
    elif args.operation == "accept":
        hooks(args.args[0], args.args[1], [], active=True)
    elif args.operation == "listen":
        listener(args.args)
    elif args.operation == "provider":
        print(run(DOCKER + ["service", "inspect", "--format", PREFLIGHT.PROVIDER_FORMAT, args.args[0]]))
    else:
        {
            "baseline-inputs": baseline_inputs,
            "retained-policy": retained_policy,
            "rollback-policy": rollback_policy,
            "working": working,
            "routes": routes,
            "render": render,
            "ready": ready,
            "deployment": deployment,
            "homepage": homepage,
            "continuity": continuity,
            "mounts": mounts,
            "preconditions": preconditions,
            "resume": resume,
            "negative": negative,
            "negative-service": lambda batch, peer: negative(batch, peer, actual=True),
            "accept-native": accept_native,
            "continuation-state": continuation_state,
            "continuation-policy": continuation_policy,
            "stop-probe": stop_recorded_probe,
        }[args.operation](*args.args)


if __name__ == "__main__":

    def interrupted(signum, frame):
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.TimeoutExpired) as error:
        print(f"HAProxy handoff: {error}", file=sys.stderr)
        sys.exit(1)
