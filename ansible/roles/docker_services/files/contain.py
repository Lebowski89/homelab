"""Docker-adapter failure containment; no firewall policy ownership."""

import hashlib
import json
import subprocess


def require(condition, message):
    if not condition:
        raise ValueError(message)


def command(argv):
    result = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=20)
    if result.returncode:
        raise RuntimeError("Docker containment: " + " ".join(argv[3:5]) + ": " + result.stderr.strip()[:400])
    return result.stdout


def contain_swarm(record, run=command, sleep=None):
    """Stop exactly the failed selected service and prove all saved tasks exited.

    Global services cannot be scaled. Removing only their exact service leaves
    configs/networks intact; the next normal stack deploy recreates that service.
    Replicated services retain the existing scale-to-zero recovery contract.
    """
    import time

    sleep = sleep or time.sleep
    binding = record["binding"]
    require(binding["runtime"] == "docker" and "selector" in binding, "containment requires an exact Swarm selector")
    base = ["docker", "--host", "unix:///var/run/docker.sock"]
    selector = binding["selector"]
    template = '{"id":{{json .ID}},"name":{{json .Spec.Name}},"mode":{{json .Spec.Mode}}}'
    observed = json.loads(run(base + ["service", "inspect", "--format", template, selector]))
    require(observed["name"] == selector and isinstance(observed["id"], str) and observed["id"], "Swarm service identity differs")
    mode = record.get("swarm_mode", "replicated")
    require(set(observed["mode"]) == {"Global" if mode == "global" else "Replicated"}, "Swarm service mode differs")
    task_ids = run(base + ["service", "ps", "--no-trunc", "-q", observed["id"]]).split()
    # Address the immutable service ID after identity discovery, not a name that
    # could now refer to a different replacement.
    if mode == "global":
        constraint = "node.id==" + hashlib.sha256(observed["id"].encode()).hexdigest()[:25]
        nodes = run(base + ["node", "ls", "--no-trunc", "-q"]).split()
        require(nodes and constraint.split("==")[1] not in nodes, "cannot establish a nonmatching containment placement")
        # Quiesce first so task objects remain inspectable until writer exit.
        # Remove only after exit proof; the ordinary deploy recreates it.
        run(base + ["service", "update", "--detach=true", "--constraint-add", constraint, observed["id"]])
    else:
        run(base + ["service", "scale", "--detach=true", observed["id"] + "=0"])
    terminal = {"shutdown", "complete", "failed", "rejected", "remove", "orphaned"}
    deadline = time.monotonic() + 60
    for _ in range(30):
        task_ids = sorted(set(task_ids) | set(run(base + ["service", "ps", "--no-trunc", "-q", observed["id"]]).split()))
        # Disappearing task metadata is inconclusive, not evidence of exit.
        states = [json.loads(run(base + ["inspect", "--type", "task", "--format", "{{json .Status.State}}", task])) for task in task_ids]
        if all(state in terminal for state in states):
            if mode == "global":
                run(base + ["service", "rm", observed["id"]])
            return {
                "changed": True,
                "contained": True,
                "service_id": observed["id"],
                "mode": mode,
                "recovery": "rerun the selected service deployment; retained configs, data and firewall protection are unchanged",
            }
        if time.monotonic() >= deadline:
            break
        sleep(2)
    raise ValueError(
        "selected Swarm tasks did not stop; reservation and protection retained; inspect saved selected service/task IDs before retry"
    )
