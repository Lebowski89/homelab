"""Operator-only metadata collection and unverified HAProxy candidate generation.

Invoked by the dedicated playbook with the bundled existing firewall helper.
No environment inspection, database connections, packet changes or secrets.
"""

from __future__ import annotations

import ipaddress
import json
import os
import pwd
import re
import socket
import sys
import time
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace


def firewall():
    namespace = {"__name__": "preflight_firewall", "__file__": "operator-bundled-policy.py"}
    exec(globals()["FIREWALL_SOURCE"], namespace)
    return SimpleNamespace(**namespace)


DOCKER = ["docker", "--host", "unix:///var/run/docker.sock"]
FORMAT = (
    '{"name":{{json .Name}},"pid":{{.State.Pid}},'
    '"swarm":{{json (index .Config.Labels "com.docker.swarm.service.name")}},'
    '"project":{{json (index .Config.Labels "com.docker.compose.project")}},'
    '"service":{{json (index .Config.Labels "com.docker.compose.service")}}}'
)
PROVIDER_FORMAT = (
    '{"id":{{json .ID}},"vips":{{json .Endpoint.VirtualIPs}},"name":{{json .Spec.Name}},"image":{{json .Spec.TaskTemplate.ContainerSpec.Image}},'
    '"constraints":{{json .Spec.TaskTemplate.Placement.Constraints}},'
    '"configs":{{json .Spec.TaskTemplate.ContainerSpec.Configs}},"ports":{{json .Endpoint.Spec.Ports}}}'
)


def observed_identity():
    """Portable Linux identity; neither hostname nor inventory labels are proof alone."""
    return {"hostname": socket.gethostname(), "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}


def validate_identity(report, expected):
    identity = report.get("identity", {})
    address = str(ipaddress.ip_address(expected["inventory_address"]))
    addresses = {str(ipaddress.ip_address(value)) for value in report["addresses"]}
    if address not in addresses or not identity.get("hostname") or not identity.get("boot_id"):
        raise ValueError(f"{report['host']}: observed host identity does not match inventory address {address}; reject metadata")


def validated_reports(config):
    """Bind loop results to inventory hosts before accepting any application metadata."""
    expected = config["expected_hosts"]
    reports = []
    seen_hosts, seen_boots = set(), set()
    for result in config["collection"]:
        host = result["haproxy_preflight_host"]
        report = json.loads(result["stdout"])
        if host not in expected or host in seen_hosts or report.get("host") != host:
            raise ValueError("unexpected, duplicate or relabelled collection result")
        validate_identity(report, expected[host])
        report["inventory_address"] = expected[host]["inventory_address"]
        boot = report["identity"]["boot_id"]
        if boot in seen_boots:
            raise ValueError("distinct inventory hosts returned the same observed host identity; reject metadata")
        seen_hosts.add(host)
        seen_boots.add(boot)
        reports.append(report)
    if seen_hosts != set(expected):
        raise ValueError("incomplete host collection; reject metadata")
    return reports


def destinations(pid, port, run, owners=None):
    """Numeric sockets only; shared host namespaces additionally require process ownership."""
    flags = "-Hntp" if owners is not None else "-Hnt"
    text = run(["nsenter", "--target", str(pid), "--net", "ss", flags, "state", "established", f"( dport = :{port} )"])
    result = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 4:
            raise ValueError("unrecognized ss endpoint output; review locally")
        socket_owners = {int(value) for value in re.findall(r"pid=(\d+)", line)}
        if owners is not None and (not socket_owners or not socket_owners <= owners):
            continue  # A shared namespace or another process's socket is not this application's evidence.
        local, peer = fields[2:4]
        address, peer_port = peer.rsplit(":", 1)
        address = str(ipaddress.ip_address(address.strip("[]")))
        if int(peer_port) != port:
            raise ValueError("unexpected connection port")
        entry = {"local": local, "destination": address, "port": port}
        if owners is not None:
            entry["owner_pids"] = sorted(socket_owners)
        result.append(entry)
    return result


def process_identity(pid, run):
    """PID reuse and namespace changes must not join separate socket observations."""
    fields = run(["cat", f"/proc/{pid}/stat"]).rsplit(")", 1)[1].split()
    if len(fields) < 20:
        raise ValueError("incomplete process identity metadata")
    start = fields[19]  # field 22, following the parenthesized process name
    if not start.isdecimal():
        raise ValueError("invalid process start time")
    return {"netns": run(["readlink", f"/proc/{pid}/ns/net"]).strip(), "start_time": start}


def podman_command(account, name):
    return [
        "runuser",
        "-u",
        name,
        "--",
        "env",
        f"HOME={account.pw_dir}",
        f"XDG_RUNTIME_DIR=/run/user/{account.pw_uid}",
        f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{account.pw_uid}/bus",
        "/bin/sh",
        "-c",
        'cd "$HOME" || exit; exec "$@"',
        "skynet-preflight",
        "/usr/bin/podman",
        "--remote=false",
    ]


def capture_window(config, report, fw, run, account_lookup, identity_lookup, clock=time.monotonic, sleep=time.sleep):
    """Sample while activity occurs; accept only one continuous identity per caller."""
    seconds = config.get("window_seconds", 0)
    interval = config.get("sample_interval", 1)
    if type(seconds) is not int or not 0 <= seconds <= 600:
        raise ValueError("window_seconds must be an integer between 0 and 600")
    if type(interval) not in {int, float} or not 0.1 <= interval <= 5:
        raise ValueError("sample_interval must be between 0.1 and 5 seconds")
    if not seconds:
        return report
    names = config["capture_callers"]
    if not isinstance(names, list) or not names or any(not isinstance(name, str) or not name for name in names):
        raise ValueError("a capture window requires explicit caller names")
    identity_names = config.get("identity_callers", names)
    docker = [
        c
        for c in report["containers"]
        if c.get("service") in identity_names
        or c.get("swarm") in identity_names
        or any((c.get("swarm") or "").endswith("_" + name) for name in identity_names)
    ]
    rootless = [c for a in report["accounts"].values() for c in a.get("containers", [])]
    records = [
        c
        for c in docker
        if c.get("service") in names or c.get("swarm") in names or any((c.get("swarm") or "").endswith("_" + name) for name in names)
    ] + [c for c in rootless if c["account"] in config.get("capture_accounts", report["accounts"])]
    # The initial snapshot predates the bounded window and cannot supply its evidence.
    for record in report["containers"] + rootless:
        record["destinations"] = []
    started, samples = clock(), 0
    started_at = time.time()

    def check(record):
        pid = record["pid"]
        if "account" in record:
            account = account_lookup(record["account"])
            if account.pw_uid != report["accounts"][record["account"]]["uid"]:
                raise ValueError("rootless account changed during capture")
            prefix = podman_command(account, record["account"])
            ids = run(prefix + ["ps", "--no-trunc", "--format", "{{.ID}}"]).split()
            if ids != [record["id"]] or run(prefix + ["inspect", "--format", "{{.State.Pid}}", record["id"]]).strip() != str(pid):
                raise ValueError("rootless caller replaced during capture; reject entire window")
        else:
            prefix = DOCKER
            labels = (
                ["com.docker.swarm.service.name=" + record["swarm"]]
                if record["swarm"]
                else [
                    "com.docker.compose.project=" + record["project"],
                    "com.docker.compose.service=" + record["service"],
                ]
            )
            argv = prefix + ["ps", "--no-trunc"]
            for label in labels:
                argv += ["--filter", "label=" + label]
            if run(argv + ["--format", "{{.ID}}"]).split() != [record["id"]]:
                raise ValueError("Docker caller replaced/ambiguous during capture; reject entire window")
            current = json.loads(run(prefix + ["inspect", "--format", FORMAT, record["id"]]))
            current["name"] = current["name"].removeprefix("/")
            if any(current[key] != record[key] for key in ["name", "pid", "swarm", "project", "service"]):
                raise ValueError("Docker caller labels/PID changed during capture; reject entire window")
            if record.get("identities") and fw.container_identities(record["binding"], run) != record["identities"]:
                raise ValueError("Docker bridge/IP/MAC/veth changed during capture; reject entire window")
        if process_identity(pid, run) != {key: record[key] for key in ["netns", "start_time"]}:
            raise ValueError("caller PID/network namespace changed during capture; reject entire window")
        owners = None
        if record["host_network"]:
            owners = {
                int(v)
                for v in run(
                    prefix + ["top", record["id"], "hpid"] if "account" in record else prefix + ["top", record["id"], "-eo", "pid"]
                ).split()
                if v.isdecimal()
            }
            if pid not in owners:
                raise ValueError("socket process ownership changed during capture")
        return owners

    while True:
        if identity_lookup() != report["identity"] or sorted(fw.OWNED.local_addresses(run)) != report["addresses"]:
            raise ValueError("observed host identity changed during capture; reject entire window")
        validate_identity(report, config["expected"])
        for record in records:
            owners = check(record)
            observed = destinations(record["pid"], config["port"], run, owners)
            check(record)
            for connection in observed:
                if connection not in record["destinations"]:
                    record["destinations"].append(connection)
        if identity_lookup() != report["identity"] or sorted(fw.OWNED.local_addresses(run)) != report["addresses"]:
            raise ValueError("observed host identity changed during capture; reject entire window")
        samples += 1
        remaining = seconds - (clock() - started)
        if remaining <= 0:
            break
        sleep(min(interval, remaining))
    # Retained destinations must match identities checked at the END of this window,
    # including callers whose sockets were sampled in an earlier window.
    for record in docker + rootless:
        check(record)
    if identity_lookup() != report["identity"] or sorted(fw.OWNED.local_addresses(run)) != report["addresses"]:
        raise ValueError("observed host identity changed during capture; reject entire window")
    if "topology" in report:
        report["topology"] = topology(config, run)
    report["capture"] = {
        "seconds": seconds,
        "samples": samples,
        "callers": names,
        "complete": True,
        "started_at": started_at,
        "completed_at": time.time(),
    }
    for record in records:
        for connection in record["destinations"]:
            connection["observations"] = [{"capture": deepcopy(report["capture"])}]
    return report


def capture_host_differences(report, old):
    """Describe only safe identity fields; retain strict host/address equality."""
    differences = {}
    identity, previous = report.get("identity", {}), old.get("identity", {})
    if identity != previous:
        differences["identity"] = sorted(key for key in identity.keys() | previous.keys() if identity.get(key) != previous.get(key))
    if report.get("addresses") != old.get("addresses"):
        current = {str(ipaddress.ip_address(value)) for value in report.get("addresses", [])}
        retained = {str(ipaddress.ip_address(value)) for value in old.get("addresses", [])}
        differences["addresses"] = {"added": sorted(current - retained), "removed": sorted(retained - current)}
        if current == retained:
            differences["addresses"]["ordering_or_representation_changed"] = True
    if old.get("capture", {}).get("complete") is not True:
        differences["capture.complete"] = "missing or not strict true"
    return differences


def same_caller(record, matches):
    """The existing identity contract, also used for idle declared callers."""
    fields = ["id", "pid", "netns", "start_time", "host_network"]
    fields += ["account"] if "account" in record else ["name", "swarm", "project", "service", "binding", "identities"]
    return len(matches) == 1 and all(key in record for key in fields[:5]) and all(matches[0].get(key) == record.get(key) for key in fields)


def provider_removal_transition(reports, captured, context):
    """Only a proven controller-provider removal may lose incidental link-local addresses."""
    controller, workers = context["controller"], set(context["workers"])
    current = {r["host"]: r for r in reports}
    previous = {r["host"]: r for r in captured}
    expected = context["expected_hosts"]
    if len(workers) != 2 or controller in workers or set(current) != {controller, *workers} or set(expected) != set(current):
        raise ValueError("provider-removal transition requires exactly the inventory controller and two workers")
    old, report = previous[controller], current[controller]
    differences = capture_host_differences(report, old)
    delta = differences.get("addresses", {})
    removed = delta.get("removed", [])
    if (
        set(differences) != {"addresses"}
        or not removed
        or delta.get("added")
        or not all(ipaddress.ip_address(a).is_link_local for a in removed)
    ):
        return None
    boots, nodes = set(), {}
    for host, fresh in current.items():
        before = previous[host]
        validate_identity(fresh, expected[host])
        validate_identity(before, expected[host])
        if fresh["identity"] != before["identity"] or before.get("capture", {}).get("complete") is not True:
            raise ValueError("provider-removal transition host reboot/identity or incomplete retained capture")
        if host != controller and fresh["addresses"] != before["addresses"]:
            raise ValueError("provider-removal transition changed worker addresses")
        boot = fresh["identity"]["boot_id"]
        node = fresh["topology"]["swarm"]["node_id"]
        if boot in boots or not node or node in nodes or node != before["topology"]["swarm"]["node_id"]:
            raise ValueError("provider-removal transition has duplicate or changed host/node identity")
        if fresh["topology"]["swarm"].get("manager") is not (host == controller) or before["topology"]["swarm"].get("manager") is not (
            host == controller
        ):
            raise ValueError("provider-removal transition manager identity changed")
        boots.add(boot)
        nodes[node] = host
    # Check every declared application, even if it was idle in the retained window.
    endpoint = next(e for e in context["plan"]["endpoints"] if "haproxy/postgres" in e["ids"])
    for name in endpoint["callers"]:
        if name in {"controller", "recovery"}:
            continue  # Persistent native contexts retain their separately accepted evidence.
        principal = context["plan"]["principals"][name]
        account = principal.get("future_account")
        alias = context.get("names", {}).get(name)

        def matches(record, account=account, alias=alias, name=name):
            if "account" in record:
                return record["account"] == account
            if alias:
                return record.get("name") == alias
            return record.get("service") == name or record.get("swarm") == name or (record.get("swarm") or "").endswith("_" + name)

        found = []
        for host, before in previous.items():
            records = before["containers"] + [c for a in before["accounts"].values() for c in a.get("containers", [])]
            for record in filter(matches, records):
                fresh = current[host]
                running = fresh["containers"] + [c for a in fresh["accounts"].values() for c in a.get("containers", [])]
                all_matches = [
                    (h, c)
                    for h, r in current.items()
                    for c in r["containers"] + [c for a in r["accounts"].values() for c in a.get("containers", [])]
                    if matches(c)
                ]
                if len(all_matches) != 1 or all_matches[0][0] != host or not same_caller(record, [c for c in running if matches(c)]):
                    raise ValueError(f"provider-removal transition caller identity changed: {name}")
                if "account" in record and fresh["accounts"].get(account, {}).get("uid") != before["accounts"][account]["uid"]:
                    raise ValueError(f"provider-removal transition account UID changed: {name}")
                found.append(record)
        if len(found) != 1:
            raise ValueError(f"provider-removal transition caller missing/ambiguous: {name}")
    providers = old.get("providers", [])
    if len(providers) != 1 or not providers[0].get("id") or not providers[0].get("name"):
        raise ValueError("provider-removal transition retained provider identity missing/ambiguous")
    provider = providers[0]
    if provider["name"] != "haproxy" and not provider["name"].endswith("_haproxy"):
        raise ValueError("provider-removal transition requires the HAProxy service")

    def selected(r):
        return [c for c in r["containers"] if c.get("swarm") == provider["name"]]

    original = selected(old)
    if len(original) != 1 or selected(report) or any(c.get("id") == original[0].get("id") for r in reports for c in r["containers"]):
        raise ValueError("provider-removal transition original provider remains or is ambiguous")
    veths = [i["veth"] for i in original[0].get("identities", []) if i.get("veth")]
    interfaces = report.get("interface_names")
    if not veths or not isinstance(interfaces, list) or not interfaces or any(not isinstance(i, str) or not i for i in interfaces):
        raise ValueError("provider-removal transition requires observed provider veth and current host interfaces")
    if any(veth in interfaces for veth in veths):
        raise ValueError("provider-removal transition original provider veth remains")

    def service(r):
        found = [s for s in r["topology"]["services"] if s.get("id") == provider["id"] and s.get("name") == provider["name"]]
        if len(found) != 1:
            raise ValueError("provider-removal transition manager service missing/ambiguous")
        return found[0]

    before, fresh = service(old), service(report)
    if any(before.get(key) != fresh.get(key) or fresh.get(key) != provider.get(key) for key in ["id", "name", "ports", "vips"]):
        raise ValueError("provider-removal transition provider VIP/publication identity changed")

    def running_tasks(value, hosts):
        tasks = [t for t in value.get("tasks", []) if t.get("state") == "running"]
        if len(tasks) != len(hosts) or {nodes.get(t.get("node_id")) for t in tasks} != hosts:
            raise ValueError("provider-removal transition provider task placement not proven")
        return {nodes[t["node_id"]]: t for t in tasks}

    old_tasks = running_tasks(before, {controller, *workers})
    new_tasks = running_tasks(fresh, workers)
    if not original[0]["name"].endswith("." + old_tasks[controller]["id"]):
        raise ValueError("provider-removal transition original controller task mismatch")
    for host in workers:
        retained, now = selected(previous[host]), selected(current[host])
        if (
            new_tasks[host] != old_tasks[host]
            or len(retained) != 1
            or not same_caller(retained[0], now)
            or not now[0]["name"].endswith("." + new_tasks[host]["id"])
        ):
            raise ValueError("provider-removal transition worker provider replaced or task mismatched")
    return {"provider": provider["id"], "removed_container": original[0]["id"], "removed_veths": veths, "removed_link_local": removed}


def merge_capture(reports, captured, source=None, transition_context=None):
    """Carry observed destinations into a fresh topology only for unchanged callers."""
    if {r["host"] for r in reports} != {r["host"] for r in captured} or len(reports) != len(captured):
        raise ValueError("capture hosts differ from fresh collection")
    transition = None
    if transition_context is not None and any(
        r["addresses"] != old["addresses"] for r in reports for old in captured if r["host"] == old["host"]
    ):
        transition = provider_removal_transition(reports, captured, transition_context)
    for report in reports:
        old = next(r for r in captured if r["host"] == report["host"])
        differences = capture_host_differences(report, old)
        permitted = transition is not None and report["host"] == transition_context["controller"] and set(differences) == {"addresses"}
        if differences and not permitted:
            raise ValueError(
                "capture host identity differs/incomplete: "
                + json.dumps({"host": report["host"], "differences": differences}, sort_keys=True)
            )
        for account, value in old["accounts"].items():
            if value.get("containers") and report["accounts"].get(account, {}).get("uid") != value["uid"]:
                raise ValueError("capture rootless account UID changed; repeat capture")
        fresh = report["containers"] + [c for a in report["accounts"].values() for c in a.get("containers", [])]
        previous = old["containers"] + [c for a in old["accounts"].values() for c in a.get("containers", [])]
        for record in previous:
            if not record["destinations"]:
                continue
            matches = [c for c in fresh if c.get("id") == record.get("id")]
            if not same_caller(record, matches):
                raise ValueError("captured caller replaced or identity changed; repeat capture")
            for connection in record["destinations"]:
                connection = deepcopy({key: value for key, value in connection.items() if key != "routes"})
                observations = connection.setdefault("observations", [{"capture": deepcopy(old["capture"])}])
                if source:
                    for observation in observations:
                        # Keep the original file/hash/window when reusing an aggregate.
                        observation.setdefault("source", deepcopy(source))
                if connection not in matches[0]["destinations"]:
                    matches[0]["destinations"].append(connection)
        history = report.setdefault("capture_history", [])
        observation = {"capture": old["capture"], "source": source}
        if permitted:
            observation["provider_removal"] = deepcopy(transition)
        for entry in old.get("capture_history", []) + [observation]:
            if entry not in history:
                history.append(deepcopy(entry))
        if "capture" not in report:
            report["capture"] = deepcopy(old["capture"])
    return reports


SERVICE_FORMAT = '{"id":{{json .ID}},"name":{{json .Spec.Name}},"vips":{{json .Endpoint.VirtualIPs}},"ports":{{json .Endpoint.Spec.Ports}}}'
TASK_FORMAT = (
    '{"id":{{json .ID}},"node_id":{{json .NodeID}},"state":{{json .Status.State}},'
    '"networks":[{{range $i,$n := .NetworksAttachments}}{{if $i}},{{end}}'
    '{"id":{{json $n.Network.ID}},"addresses":{{json $n.Addresses}}}{{end}}]}'
)
NETWORK_FORMAT = (
    '{"id":{{json .Id}},"name":{{json .Name}},"driver":{{json .Driver}},"scope":{{json .Scope}},"services":{{json (index . "Services")}}}'
)
INFO_FORMAT = '{"node_id":{{json .Swarm.NodeID}},"manager":{{json .Swarm.ControlAvailable}}}'


def topology(config, run):
    """Project exact overlay VIP/task addresses without reading service specs or secrets."""
    result = {"swarm": json.loads(run(DOCKER + ["info", "--format", INFO_FORMAT])), "services": [], "networks": []}
    if result["swarm"]["manager"]:
        for identity in run(DOCKER + ["service", "ls", "--format", "{{.ID}}"]).split():
            service = json.loads(run(DOCKER + ["service", "inspect", "--format", SERVICE_FORMAT, identity]))
            name = service["name"]
            if name == config.get("provider") or name.endswith("_" + config.get("provider", "haproxy")):
                service["tasks"] = []
                for task in run(
                    DOCKER + ["service", "ps", "--no-trunc", "--filter", "desired-state=running", "--format", "{{.ID}}", identity]
                ).split():
                    service["tasks"].append(json.loads(run(DOCKER + ["inspect", "--type", "task", "--format", TASK_FORMAT, task])))
            result["services"].append(service)
    for identity in run(DOCKER + ["network", "ls", "--filter", "driver=overlay", "--format", "{{.ID}}"]).split():
        result["networks"].append(json.loads(run(DOCKER + ["network", "inspect", "--verbose", "--format", NETWORK_FORMAT, identity])))
    return result


def map_routes(reports, controller, provider, workers):
    """Exact address correlation; an overlay VIP is not a host-published destination."""
    nodes = {report.get("topology", {}).get("swarm", {}).get("node_id"): report["host"] for report in reports}
    nodes.pop(None, None)
    nodes.pop("", None)
    services = [service for report in reports for service in report.get("topology", {}).get("services", [])]
    networks = [network for report in reports for network in report.get("topology", {}).get("networks", [])]
    for report in reports:
        records = report["containers"] + [record for account in report["accounts"].values() for record in account.get("containers", [])]
        for record in records:
            for connection in record["destinations"]:
                address = connection["destination"]
                matches = []
                for service in services:
                    tasks = [task for task in service.get("tasks", []) if task["state"] == "running"]
                    task_hosts = [nodes.get(task["node_id"]) for task in tasks]
                    is_provider = service["name"] == provider or service["name"].endswith("_" + provider)
                    for vip in service.get("vips") or []:
                        vip_address = vip.get("Addr")
                        if not vip_address:
                            continue
                        if str(ipaddress.ip_interface(vip_address).ip) == address:
                            matches.append(
                                {
                                    "kind": "overlay_service",
                                    "service": service["name"],
                                    "network": vip["NetworkID"],
                                    "task_hosts": task_hosts,
                                    "worker_only": bool(tasks) and all(host in workers for host in task_hosts),
                                    "provider": is_provider,
                                }
                            )
                    for task in tasks:
                        for network in task["networks"] or []:
                            if address in {str(ipaddress.ip_interface(value).ip) for value in network["addresses"] or []}:
                                matches.append(
                                    {
                                        "kind": "overlay_task",
                                        "service": service["name"],
                                        "network": network["id"],
                                        "task_host": nodes.get(task["node_id"]),
                                        "provider": is_provider,
                                    }
                                )
                if not matches:
                    for network in networks:
                        for name, service in (network.get("services") or {}).items():
                            vip = service.get("VIP", "")
                            if vip and str(ipaddress.ip_interface(vip).ip) == address:
                                matches.append({"kind": "overlay_service", "service": name, "network": network["id"], "worker_only": False})
                if not matches:
                    hosts = [host["host"] for host in reports if address in host["addresses"]]
                    matches = [{"kind": "mgt_publication" if host == controller else "worker_publication", "host": host} for host in hosts]
                # No guess from an overlay subnet, DNS name or a supplied connection string.
                connection["routes"] = matches or [{"kind": "unresolved"}]


def collect(config, fw, run, account_lookup=pwd.getpwnam, systemd=True, identity_lookup=observed_identity):
    report = {"host": config["host"], "addresses": sorted(fw.OWNED.local_addresses(run)), "containers": [], "accounts": {}, "pending": []}
    report["identity"] = identity_lookup()
    validate_identity(report, config["expected"])
    report["interface_names"] = [link["ifname"] for link in json.loads(run(["ip", "-j", "address", "show"]))]
    report["inventory_address"] = config["expected"]["inventory_address"]
    report["connection"] = config.get("connection", {})
    report["context"] = {"uid": os.geteuid(), "cgroup": Path("/proc/self/cgroup").read_text().strip()}
    report["providers"] = []
    try:
        ready = (
            run(["systemctl", "is-active", "docker.service"]).strip() == "active" if systemd else Path("/var/run/docker.sock").is_socket()
        )
    except RuntimeError:
        ready = False
    if ready:
        report["topology"] = topology(config, run)
        for identity in run(DOCKER + ["ps", "--no-trunc", "--format", "{{.ID}}"]).split():
            if not fw.NAME.fullmatch(identity):
                raise ValueError("invalid Docker identity")
            record = json.loads(run(DOCKER + ["inspect", "--format", FORMAT, identity]))
            record["name"] = record["name"].removeprefix("/")
            pid = record["pid"]
            if not fw.integer(pid) or pid <= 0:
                report["pending"].append(f"{record['name']}: stopped during collection")
                continue
            record["id"] = identity
            record.update(process_identity(pid, run))
            record["host_network"] = run(["readlink", f"/proc/{pid}/ns/net"]).strip() == run(["readlink", "/proc/1/ns/net"]).strip()
            owners = None
            if record["host_network"]:
                owners = {int(value) for value in run(DOCKER + ["top", identity, "-eo", "pid"]).split() if value.isdecimal()}
                if pid not in owners:
                    raise ValueError("container process ownership changed during collection; repeat")
            record["destinations"] = destinations(pid, config["port"], run, owners)
            binding = {"kind": "container", "runtime": "docker", "phase": "docker", "verified": False, "restart_verified": False}
            if record["swarm"]:
                binding["selector"] = record["swarm"]
            elif record["project"] and record["service"]:
                binding["compose"] = {"project": record["project"], "service": record["service"]}
            else:
                binding = None
            if binding and not record["host_network"]:
                binding["physdev_verified"] = False
                record["binding"] = binding
                if config["host"] == config["controller"]:
                    try:
                        record["identities"] = fw.container_identities(binding, run)
                    except (ValueError, RuntimeError, OSError) as error:
                        record["pending"] = str(error)
            else:
                record["pending"] = "missing stable labels or observed host-socket UID/cgroup"
            if run(DOCKER + ["inspect", "--format", "{{.State.Pid}}", identity]).strip() != str(pid) or process_identity(pid, run) != {
                key: record[key] for key in ["netns", "start_time"]
            }:
                raise ValueError("container restarted/changed namespace during collection; repeat")
            report["containers"].append(record)
            provider = config.get("provider")
            if (
                config["host"] == config["controller"]
                and provider
                and record["swarm"]
                and (record["swarm"] == provider or record["swarm"].endswith("_" + provider))
            ):
                report["providers"].append(json.loads(run(DOCKER + ["service", "inspect", "--format", PROVIDER_FORMAT, record["swarm"]])))
    else:
        report["pending"].append("Docker is not active; no socket activation attempted")
    for name in config["accounts"]:
        try:
            account = account_lookup(name)
        except KeyError:
            report["pending"].append(f"{name}: account not prepared")
            continue
        report["accounts"][name] = {"uid": account.pw_uid}
        if account.pw_uid <= 0:
            report["pending"].append(f"{name}: dedicated rootless account must have a non-root UID")
            continue
        if name not in config["running_rootless_accounts"]:
            continue
        command = podman_command(account, name)
        for identity in run(command + ["ps", "--no-trunc", "--format", "{{.ID}}"]).split():
            if not fw.NAME.fullmatch(identity):
                raise ValueError("invalid rootless container identity")
            pid = run(command + ["inspect", "--format", "{{.State.Pid}}", identity]).strip()
            if not pid.isdecimal() or int(pid) <= 0:
                raise ValueError("rootless caller stopped during collection")
            host_network = run(["readlink", f"/proc/{pid}/ns/net"]).strip() == run(["readlink", "/proc/1/ns/net"]).strip()
            owners = None
            if host_network:
                owners = {int(value) for value in run(command + ["top", identity, "hpid"]).split() if value.isdecimal()}
                if int(pid) not in owners:
                    raise ValueError("rootless process ownership changed during collection; repeat")
            fingerprint = process_identity(pid, run)
            entry = {
                "account": name,
                "id": identity,
                "pid": int(pid),
                "host_network": host_network,
                "destinations": destinations(int(pid), config["port"], run, owners),
            }
            entry.update(fingerprint)
            if run(command + ["inspect", "--format", "{{.State.Pid}}", identity]).strip() != pid or process_identity(pid, run) != {
                key: entry[key] for key in ["netns", "start_time"]
            }:
                raise ValueError("rootless caller restarted during collection; repeat")
            report["accounts"][name].setdefault("containers", []).append(entry)
    return capture_window(config, report, fw, run, account_lookup, identity_lookup)


def candidates(config):
    """Propose label/account bindings; confirmations never come from collection."""
    plan, reports = config["plan"], validated_reports(config)
    if config.get("capture_reports") is not None:
        source = config.get("capture_source")
        if source is not None and (
            not isinstance(source, dict)
            or not isinstance(source.get("path"), str)
            or not source["path"].startswith("/")
            or not isinstance(source.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"])
        ):
            raise ValueError("invalid capture source provenance")
        merge_capture(reports, config["capture_reports"], source, transition_context=config)
    map_routes(reports, config["controller"], "haproxy", config["workers"])
    endpoint = next(entry for entry in plan["endpoints"] if "haproxy/postgres" in entry["ids"])
    existing = deepcopy(config["existing"])
    existing["mgt_firewall_inputs_verified"] = False
    existing["mgt_firewall_active_endpoints"] = sorted(set(existing.get("mgt_firewall_active_endpoints", [])) | {"haproxy/postgres"})
    callers = existing.setdefault("mgt_firewall_callers", {})
    pending = []
    controller = config["controller"]
    controller_addresses = next(report["addresses"] for report in reports if report["host"] == controller)
    for name in endpoint["callers"]:
        callers[name] = []
        principal = plan["principals"].get(name, {})
        for report in reports:
            host = report["host"]
            if name in {"controller", "recovery"}:
                continue  # snapshot of a become session cannot prove exclusive operator sockets
            hosts = principal.get("inventory_hosts", [])
            hosts = hosts if isinstance(hosts, list) else [hosts]
            alias = config.get("names", {}).get(name)
            matches = [
                record
                for record in report["containers"]
                if (
                    record["name"] == alias
                    if alias
                    else record["service"] == name or record["swarm"] == name or (record["swarm"] or "").endswith("_" + name)
                )
            ]
            if host not in hosts:
                if matches:
                    pending.append(
                        f"{name}@{host}: observed Docker caller outside effective future placement; review mapped routes; no guessed mgt allowance"
                    )
                continue
            if len(matches) == 1:
                record = matches[0]
                destinations_ = {connection["destination"] for connection in record["destinations"]}
                routes = [route for connection in record["destinations"] for route in connection["routes"]]
                worker_routes = bool(routes) and all(
                    (route["kind"] == "worker_publication" and route["host"] == host)
                    or (route["kind"] == "overlay_service" and route.get("provider") and route.get("worker_only"))
                    or (route["kind"] == "overlay_task" and route.get("provider") and route.get("task_host") == host)
                    for route in routes
                )
                if host == controller and record.get("binding") and record.get("identities") and not record.get("pending"):
                    callers[name].append(record["binding"])
                elif (
                    host != controller
                    and destinations_
                    and worker_routes
                    and not destinations_ & set(controller_addresses)
                    and not any(ipaddress.ip_address(address).is_loopback for address in destinations_)
                ):
                    callers[name].append(
                        {
                            "kind": "elsewhere",
                            "phase": "docker",
                            "inventory_host": host,
                            "route_verified": False,
                            "verified": False,
                            "restart_verified": False,
                        }
                    )
                else:
                    pending.append(f"{name}@{host}: unresolved/shared route or socket identity; no mgt source-IP exception")
            account = principal.get("future_account")
            observed = report["accounts"].get(account, {})
            if host == controller and observed.get("containers") and observed.get("uid", 0) > 0:
                callers[name].append(
                    {
                        "kind": "local",
                        "phase": "podman",
                        "account": account,
                        "uid": observed["uid"],
                        "verified": False,
                        "restart_verified": False,
                    }
                )
        if not callers[name]:
            pending.append(f"{name}: no unique verified-context candidate; review labels, destinations and context metadata")
    return {"candidate": existing, "pending": pending, "reports": reports}


def run_command(fw, argv, data=None):
    """Add a useful operation name without printing formats, environments or source."""
    try:
        return fw.execute(argv, data)
    except RuntimeError as error:
        command = argv[:1]
        if argv[:3] == DOCKER:
            command += argv[3:5] if argv[3] in {"service", "network"} else argv[3:4]
        raise RuntimeError(f"{' '.join(command)}: {error}") from None


def main():
    config = {}
    operation = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    try:
        config = json.loads(sys.stdin.read())
        if not isinstance(config, dict):
            raise ValueError("preflight input must be a mapping")
        if operation == "collect":
            fw = firewall()
            result = collect(config, fw, lambda argv, data=None: run_command(fw, argv, data), systemd=Path("/run/systemd/system").is_dir())
        elif operation == "candidates":
            result = candidates(config)
        else:
            raise ValueError("unsupported preflight operation")
        print(json.dumps(result, sort_keys=True))
    except Exception as error:
        # Explicit exit avoids Python/Ubuntu crash hooks on routine CLI failures.
        host = config.get("host", config.get("controller", "unknown")) if isinstance(config, dict) else "unknown"
        print(f"haproxy-preflight: host={host} operation={operation}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
