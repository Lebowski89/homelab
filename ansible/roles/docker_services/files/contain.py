"""Selected-service Swarm containment; the adapter owns node-local evidence."""

import hashlib
import json
import subprocess
import time


def require(condition, message):
    if not condition:
        raise ValueError(message)


def command(argv):
    result = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=20)
    if result.returncode:
        message = result.stderr.strip().lower()
        # Only these exact object lookups may return missing metadata. A failed
        # daemon/transport query is unavailable evidence, never an empty result.
        task = argv[3:6] == ["inspect", "--type", "task"]
        service = argv[3:5] == ["service", "inspect"]
        identity = argv[-1].lower()
        if identity in message and (
            (task and ("no such object" in message or "no such task" in message or f"task {identity} not found" in message))
            or (service and "no such service" in message)
        ):
            return None
        raise RuntimeError("Docker containment: " + " ".join(argv[3:5]) + " failed; required evidence unavailable")
    return result.stdout


BASE = ["docker", "--host", "unix:///var/run/docker.sock"]
TERMINAL = {"shutdown", "complete", "failed", "rejected", "remove", "orphaned"}
SERVICE = '{"id":{{json .ID}},"name":{{json .Spec.Name}},"version":{{json .Version.Index}},"mode":{{json .Spec.Mode}},"labels":{"com.docker.stack.namespace":{{json (index .Spec.Labels "com.docker.stack.namespace")}}},"constraints":{{json .Spec.TaskTemplate.Placement.Constraints}}}'
TASK = '{"id":{{json .ID}},"service_id":{{json .ServiceID}},"node_id":{{json .NodeID}},"state":{{json .Status.State}}}'


def service(selector, run):
    body = run(BASE + ["service", "inspect", "--format", SERVICE, selector])
    return None if body is None else json.loads(body)


def tasks(service_id, run):
    ids = run(BASE + ["service", "ps", "--no-trunc", "-q", service_id]).split()
    result = {}
    for task in ids:
        body = run(BASE + ["inspect", "--type", "task", "--format", TASK, task])
        value = None if body is None else json.loads(body)
        require(value is None or value["id"] == task and value["service_id"] == service_id, "task identity replaced")
        result[task] = value
    return result


def node_targets(node_ids, inventory, run):
    targets = []
    template = '{"id":{{json .ID}},"host":{{json (index .Spec.Labels "ansible_host")}},"label":{{json (index .Spec.Labels "docker_services_host")}}}'
    for node in sorted(node_ids):
        value = json.loads(run(BASE + ["node", "inspect", "--format", template, node]))
        host = value["host"]
        require(value["id"] == node and host in inventory, "required task node has no supported inventory identity")
        require(
            inventory[host].get("ansible_host") == host and inventory[host].get("docker_services_host") == value["label"],
            "task node labels differ from inventory identity",
        )
        targets.append({"id": node, "host": host})
    require(len({n["host"] for n in targets}) == len(targets), "ambiguous task node inventory identity")
    return targets


def quiesce_swarm(record, inventory, run=command, sleep=time.sleep):
    """Quiesce one immutable service; collect required nodes before task GC."""
    binding, mode = record["binding"], record.get("swarm_mode", "replicated")
    selector = binding["selector"]
    require(binding["runtime"] == "docker" and mode in {"replicated", "global"}, "expected one Swarm service")
    observed = service(selector, run)
    require(observed and observed["name"] == selector and observed["id"], "selected Swarm identity is absent or differs")
    suffix = "_" + record["service"]
    require(
        selector.endswith(suffix) and observed["labels"].get("com.docker.stack.namespace") == selector[: -len(suffix)],
        "Swarm stack ownership differs",
    )
    require(set(observed["mode"]) == {"Global" if mode == "global" else "Replicated"}, "Swarm service mode differs")
    initial = tasks(observed["id"], run)
    # Empty/vanished history at entry cannot locate an orphaned writer. Do not
    # confuse preparation hosts or Docker node hostnames with execution nodes.
    require(
        initial and all(value and value["node_id"] for value in initial.values()),
        "task-to-node evidence unavailable; containment inconclusive",
    )
    locations = {task: value["node_id"] for task, value in initial.items()}
    node_targets(set(locations.values()), inventory, run)  # validate before mutation
    constraint = None
    if mode == "global":
        constraint = "node.id==" + hashlib.sha256(observed["id"].encode()).hexdigest()[:25]
        nodes = run(BASE + ["node", "ls", "-q"]).split()
        require(nodes and constraint.split("==")[1] not in nodes, "cannot establish a nonmatching containment placement")
        run(BASE + ["service", "update", "--detach=true", "--constraint-add", constraint, observed["id"]])
    else:
        run(BASE + ["service", "scale", "--detach=true", observed["id"] + "=0"])
    deadline = time.monotonic() + 60
    missing = False
    for _ in range(30):
        current = tasks(observed["id"], run)
        missing = missing or bool(set(locations) - set(current))
        for task, value in current.items():
            require(value is not None or task in locations, "new task lost node metadata; containment inconclusive")
            if value:
                require(bool(value["node_id"]), "scheduled task node is unavailable")
                locations[task] = value["node_id"]
            else:
                missing = True
        if all(value is None or value["state"] in TERMINAL for value in current.values()):
            after = service(selector, run)
            require(after and after["id"] == observed["id"], "Swarm identity replaced during containment")
            snapshot = {
                "service_id": observed["id"],
                "selector": selector,
                "mode": mode,
                "version": after["version"],
                "constraint": constraint,
                "tasks": locations,
                "nodes": node_targets(set(locations.values()), inventory, run),
                "task_history_missing": missing,
            }
            require_quiesced(snapshot, run)
            return {"changed": True, "contained": False, "snapshot": snapshot}
        if time.monotonic() >= deadline:
            break
        sleep(2)
    raise ValueError("selected scheduler tasks did not quiesce; reservation/protection retained")


def observe_node(snapshot, node, run=command):
    require(node in snapshot["nodes"], "node observation does not belong to this containment")
    actual = json.loads(run(BASE + ["info", "--format", "{{json .Swarm.NodeID}}"]))
    require(actual == node["id"], "node-local Docker identity differs from manager evidence")
    running = run(BASE + ["ps", "--no-trunc", "--filter", "label=com.docker.swarm.service.id=" + snapshot["service_id"], "-q"]).split()
    return {"changed": False, "observation": {"service_id": snapshot["service_id"], "node": node, "running": running}}


def require_quiesced(snapshot, run):
    observed = service(snapshot["selector"], run)
    require(
        observed and observed["id"] == snapshot["service_id"] and observed["version"] == snapshot["version"],
        "Swarm identity/spec replaced during containment",
    )
    if snapshot["mode"] == "replicated":
        require(observed["mode"].get("Replicated", {}).get("Replicas") == 0, "selected service is no longer scaled to zero")
    else:
        require(
            "Global" in observed["mode"] and snapshot["constraint"] in (observed["constraints"] or []),
            "global containment placement changed",
        )
        nodes = run(BASE + ["node", "ls", "-q"]).split()
        require(nodes and snapshot["constraint"].split("==")[1] not in nodes, "global containment placement cannot be verified")
    for task, value in tasks(snapshot["service_id"], run).items():
        require(
            task in snapshot["tasks"] and (value is None or value["node_id"] == snapshot["tasks"][task] and value["state"] in TERMINAL),
            "scheduler evidence changed; containment inconclusive",
        )


def verify_swarm(snapshot, observations, inventory, run=command):
    require(observations and len(observations) == len(snapshot["nodes"]), "required node-local evidence unavailable")
    require(len({v["node"]["id"] for v in observations}) == len(observations), "duplicate node-local evidence")
    for value in observations:
        require(
            value["service_id"] == snapshot["service_id"] and value["node"] in snapshot["nodes"] and value["running"] == [],
            "selected writer remains or node-local identity differs",
        )
    require(node_targets({v["id"] for v in snapshot["nodes"]}, inventory, run) == snapshot["nodes"], "node inventory identity changed")
    require_quiesced(snapshot, run)
    if snapshot["mode"] == "global":
        run(BASE + ["service", "rm", snapshot["service_id"]])
        require(service(snapshot["selector"], run) is None, "service identity remains or was replaced after removal")
    return {"changed": True, "contained": True, "service_id": snapshot["service_id"], "mode": snapshot["mode"]}
