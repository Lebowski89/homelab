"""Execute only the Docker adapter's selected-service failure containment."""

import json
from pathlib import Path

from ansible.errors import AnsibleActionFail
from ansible.plugins.action import ActionBase

SOURCE = Path(__file__).resolve().parents[1] / "roles/docker_services/files/contain.py"


class ActionModule(ActionBase):
    _VALID_ARGS = frozenset({"runtime", "inventory_host"})
    _supports_check_mode = True

    def run(self, tmp=None, task_vars=None):
        variables = task_vars or {}
        result = super().run(tmp, variables)
        record = self._task.args.get("runtime", {})
        binding = record.get("binding", {})
        if binding.get("runtime") != "docker" or "selector" not in binding or "compose" in binding:
            raise AnsibleActionFail("Failure containment requires one exact Swarm service")
        if record.get("swarm_mode", "replicated") not in {"replicated", "global"}:
            raise AnsibleActionFail("Unsupported Swarm containment mode")
        if self._task.check_mode:
            return dict(result, changed=False, skipped=True)
        host = self._task.args["inventory_host"]
        source = (
            SOURCE.read_text()
            + """
import sys
try:
    print(json.dumps(contain_swarm(json.load(sys.stdin)['runtime'])))
except (OSError, ValueError, RuntimeError, KeyError, TypeError, subprocess.SubprocessError) as error:
    print('Docker containment: ' + str(error), file=sys.stderr)
    sys.exit(1)
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
                "stdin": json.dumps({"runtime": record}),
                "expand_argument_vars": False,
            },
            task_vars=variables,
        )
        # Never return the embedded command/source or the module invocation.
        if observed.get("rc") != 0 or observed.get("failed") or observed.get("unreachable"):
            lines = observed.get("stderr", "selected-service containment failed").strip().splitlines()
            return dict(
                result,
                failed=True,
                changed=False,
                msg=host
                + ": "
                + (lines[-1][:600] if lines else "selected-service containment failed")
                + "; protection/reservation retained until writer absence is proved",
            )
        return dict(result, **json.loads(observed["stdout"]))
