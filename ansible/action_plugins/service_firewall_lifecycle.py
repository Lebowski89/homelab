"""Run only the firewall-owned part of a normal service operation."""

import importlib.util
import json
from pathlib import Path

from ansible.errors import AnsibleActionFail
from ansible.plugins.action import ActionBase
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[1] / "roles/service_firewall"


def source_module(source, name):
    return (
        "import types\n"
        + name
        + " = types.ModuleType("
        + repr(name)
        + ")\n"
        + "exec(compile("
        + repr(source)
        + ", "
        + repr(name)
        + ", 'exec'), "
        + name
        + ".__dict__)\n"
    )


def remote_source(profile):
    spec = importlib.util.spec_from_file_location("lifecycle_bundle", ROOT / "files/bundle.py")
    bundle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bundle)
    installed_helper = bundle.bundled_helper(profile)
    helper = installed_helper
    # The helper is bundled exactly as at its persistent destination. Defining
    # __file__ keeps legacy imports and diagnostics working without a temp file.
    helper = (
        "__file__ = '/etc/skynet-lifecycle-inline.py'\n" + helper
        if "from __future__" not in helper
        else helper.replace(
            "from __future__ import annotations", "from __future__ import annotations\n__file__ = '/etc/skynet-lifecycle-inline.py'", 1
        )
    )
    source = source_module(helper, "helper")
    source += source_module((ROOT / "files/lifecycle.py").read_text(), "engine")
    source += source_module((ROOT / "files/lifecycle_remote.py").read_text(), "remote")
    source += "remote.policy_engine = engine\n"
    source += """
import json, sys
try:
    print(json.dumps(remote.run_lifecycle(engine, helper, json.load(sys.stdin)), sort_keys=True))
except (OSError, ValueError, RuntimeError, KeyError, TypeError, remote.subprocess.SubprocessError) as error:
    print('Service firewall: ' + str(error), file=sys.stderr)
    sys.exit(1)
"""
    return installed_helper, source


class ActionModule(ActionBase):
    _VALID_ARGS = frozenset({"plan", "phase", "inventory_host", "policy", "profile"})
    _supports_check_mode = True

    def run(self, tmp=None, task_vars=None):
        variables = task_vars or {}
        result = super().run(tmp, variables)
        args = self._task.args
        if args.get("phase") == "install":
            if "plan" in args or args.get("profile") not in {"mgt", "workers"} or not isinstance(args.get("policy"), dict):
                raise AnsibleActionFail("Install requires one profile/policy, without a service plan")
            policy = args["policy"]
            host = args["inventory_host"]
            plan = {
                "managed": True,
                "profile": {host: args["profile"]},
                "service": "administrative-install",
                "runtime": {},
                "action": "install",
                "endpoints": policy.get("endpoints", []),
                "callers": {},
                "inventory": {host: policy["inventory_address"]},
                "controller": host,
                "token": "administrative-install",
            }
        else:
            if (
                "policy" in args
                or "profile" in args
                or args.get("phase")
                not in {
                    "inspect",
                    "stage",
                    "prepare_remove",
                    "finish",
                    "remove",
                    "probe",
                    "counters",
                    "abort",
                    "addresses",
                    "cancel",
                    "activate",
                }
            ):
                raise AnsibleActionFail("Choose one supported service lifecycle phase and plan")
            plan = args["plan"]
        if not plan["managed"] or self._task.check_mode:
            return dict(result, changed=False, skipped=True)
        host = self._task.args["inventory_host"]
        phase = self._task.args["phase"]
        try:
            profile = "mgt" if phase in {"probe", "addresses"} else plan["profile"][host]
            unraid = host == variables["services_storage_host"]
            request = {
                "service": plan["service"],
                "runtime": plan["runtime"],
                "action": plan["action"],
                "host": host,
                "address": plan["inventory"][host],
                "profile": profile,
                "endpoints": [{k: v for k, v in e.items() if k != "host"} for e in plan["endpoints"] if e.get("host", host) == host],
                "callers": plan["callers"],
                "dependents": plan.get("dependents", []),
                "sources": plan.get("sources"),
                "source_addresses": plan.get("source_addresses", []),
                "root": (
                    "/etc/skynet-mgt-firewall"
                    if profile == "mgt"
                    else "/boot/config/skynet-worker-backend-firewall"
                    if unraid
                    else "/etc/skynet-worker-backend-firewall"
                ),
            }
            if phase == "probe":
                request["endpoints"] = [{**e, "address": plan["inventory"][e["host"]]} for e in plan["endpoints"]]
            helper, source = remote_source(profile)
            units = {}
            if profile == "mgt":
                environment = Environment(undefined=StrictUndefined)
                context = {"mgt_firewall_root": request["root"], "mgt_firewall_plan": {"endpoints": request["endpoints"]}}
                for name in [
                    "skynet-mgt-firewall.service",
                    "skynet-mgt-firewall-reconcile.service",
                    "skynet-mgt-firewall-reconcile.timer",
                    "docker-ordering.conf",
                ]:
                    destination = "/etc/systemd/system/" + (
                        "docker.service.d/45-skynet-mgt-firewall.conf" if name == "docker-ordering.conf" else name
                    )
                    units[destination] = (
                        environment.from_string((ROOT / ("templates/mgt/" + name + ".j2")).read_text()).render(**context) + "\n"
                    )
            args = {
                "argv": [
                    variables["hostvars"][host].get("ansible_facts", {}).get("discovered_interpreter_python", "/usr/bin/python3"),
                    "-c",
                    source,
                ],
                "stdin": json.dumps(
                    {
                        "request": request,
                        "phase": phase,
                        "token": plan["token"],
                        "helper": helper,
                        "units": units,
                        "policy": args.get("policy"),
                    }
                ),
                "expand_argument_vars": False,
            }
            observed = self._execute_module(module_name="ansible.builtin.command", module_args=args, task_vars=variables)
            if observed.get("rc") != 0 or observed.get("failed") or observed.get("unreachable"):
                # Never return the command module's invocation/embedded source.
                message = observed.get("stderr", "remote firewall transaction failed").strip().splitlines()
                raise ValueError(message[-1][:600] if message else "remote firewall transaction failed")
            return dict(result, **json.loads(observed["stdout"]))
        except (ValueError, KeyError, TypeError, OSError) as error:
            # A failed result participates in the task's bounded retry loop.
            # Raising an action exception would bypass health/removal polling.
            return dict(
                result,
                changed=False,
                failed=True,
                msg=f"{host} {phase}: {error}. Protection is retained; inspect the selected service operation before retrying.",
            )
