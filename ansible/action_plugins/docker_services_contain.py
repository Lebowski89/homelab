"""Use ordinary delegation for selected-service manager and node evidence."""

import json
from pathlib import Path

from ansible.errors import AnsibleActionFail
from ansible.plugins.action import ActionBase

SOURCE = Path(__file__).resolve().parents[1] / "roles/docker_services/files/contain.py"


class ActionModule(ActionBase):
    _VALID_ARGS = frozenset({"phase", "runtime", "inventory_host", "snapshot", "node", "observations"})
    _supports_check_mode = True

    def run(self, tmp=None, task_vars=None):
        variables = task_vars or {}
        result = super().run(tmp, variables)
        args = self._task.args
        record, phase = args.get("runtime", {}), args.get("phase")
        binding = record.get("binding", {})
        if (
            phase not in {"quiesce", "observe", "verify"}
            or binding.get("runtime") != "docker"
            or "selector" not in binding
            or "compose" in binding
        ):
            raise AnsibleActionFail("Failure containment requires one exact Swarm service and a supported evidence phase")
        if self._task.check_mode:
            return dict(result, changed=False, skipped=True, contained=False)
        host = args["inventory_host"]
        node = args.get("node", {})
        if phase == "observe" and node.get("host") != host:
            raise AnsibleActionFail("Containment node observation must use its manager-resolved inventory host")
        snapshot = args.get("snapshot", {})
        if phase != "quiesce" and (
            snapshot.get("selector") != binding["selector"] or snapshot.get("mode") != record.get("swarm_mode", "replicated")
        ):
            raise AnsibleActionFail("Containment snapshot belongs to another service or mode")
        inventory = {}
        for name in variables.get("groups", {}).get("all", []):
            labels = variables["hostvars"][name].get("docker_swarm_node_labels", {})
            if labels.get("ansible_host") == name:
                inventory[name] = {key: labels[key] for key in ["ansible_host", "docker_services_host"] if key in labels}
        data = {
            "phase": phase,
            "runtime": record,
            "inventory": inventory,
            "snapshot": snapshot,
            "node": node,
            "observations": args.get("observations", []),
        }
        source = (
            SOURCE.read_text()
            + """
import sys
try:
    data=json.load(sys.stdin)
    if data['phase']=='quiesce': result=quiesce_swarm(data['runtime'],data['inventory'])
    elif data['phase']=='observe': result=observe_node(data['snapshot'],data['node'])
    else: result=verify_swarm(data['snapshot'],data['observations'],data['inventory'])
    print(json.dumps(result))
except (ValueError, RuntimeError, KeyError, TypeError) as error:
    print(json.dumps({'failed':True,'changed':False,'contained':False,'msg':str(error)[:300]}))
except (OSError, subprocess.SubprocessError):
    print(json.dumps({'failed':True,'changed':False,'contained':False,'msg':'bounded Docker evidence query unavailable'}))
"""
        )
        observed = self._execute_module(
            module_name="ansible.builtin.command",
            module_args={
                "argv": [
                    variables["hostvars"][host].get("ansible_facts", {}).get("discovered_interpreter_python", "/usr/bin/python3"),
                    "-c",
                    source,
                ],
                "stdin": json.dumps(data),
                "expand_argument_vars": False,
            },
            task_vars=variables,
        )
        # Do not return the streamed source, input request or module invocation.
        if observed.get("rc") != 0 or observed.get("failed") or observed.get("unreachable"):
            return dict(
                result,
                failed=True,
                changed=False,
                contained=False,
                msg=f"{host} containment {phase}: evidence unavailable or identity/writer state differs; protection/reservation retained",
            )
        payload = json.loads(observed["stdout"])
        if payload.get("failed"):
            payload["msg"] = f"{host} containment {phase}: {payload['msg']}; protection/reservation retained"
        return dict(result, **payload)
