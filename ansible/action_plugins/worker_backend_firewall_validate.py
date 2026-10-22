"""Validate firewall inputs locally before creating files on a worker."""

from __future__ import annotations

import importlib.util
from copy import deepcopy
from pathlib import Path

from ansible.errors import AnsibleActionFail
from ansible.plugins.action import ActionBase

_SPEC = importlib.util.spec_from_file_location(
    "worker_firewall_validation", Path(__file__).resolve().parents[1] / "roles/service_firewall/files/worker-backend-firewall.py"
)
_HELPER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_HELPER)


def validate(policy, require_verified):
    """Validate planning inputs strictly; an unconfirmed boolean is plan-only."""
    if type(require_verified) is not bool or type(policy.get("sources_verified")) is not bool:
        raise ValueError("source confirmation and require_verified must be booleans")
    candidate = deepcopy(policy)
    if not require_verified:
        candidate["sources_verified"] = True
    _HELPER.validate_policy(candidate)
    return True


class ActionModule(ActionBase):
    _VALID_ARGS = frozenset({"policy", "require_verified"})
    _supports_check_mode = True

    def run(self, tmp=None, task_vars=None):
        result = super().run(tmp, task_vars or {})
        try:
            validate(self._task.args["policy"], self._task.args["require_verified"])
        except (ValueError, TypeError) as error:
            raise AnsibleActionFail(str(error)) from error
        result["changed"] = False
        return result
