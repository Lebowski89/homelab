"""Record aggregate changes only; never task arguments, results or secret values."""

import json
import os
from pathlib import Path

from ansible.plugins.callback import CallbackBase


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "aggregate"
    CALLBACK_NAME = "vm_stats"
    CALLBACK_NEEDS_ENABLED = True

    def v2_runner_on_failed(self, result, ignore_errors=False):
        # Identify the deliberately absent fixture input without retaining
        # arbitrary errors, task arguments, resolved values or secret text.
        failures = [result.result, *result.result.get("results", [])]
        if any("molecule/shared/fixtures/missing.j2" in str(failure.get("msg", "")) for failure in failures):
            self._expected_prepare_failure = True
        # Ansible 2.21 censors no_log result mappings, including loop items.
        # Its public exception summary still exposes the diagnostic printed by
        # Ansible. Retain only whether that actual error names our missing input;
        # never serialize the error, task arguments or resolved secret values.
        summary = getattr(result, "exception", None)
        events = [summary.event] if summary is not None else []
        while events:
            event = events.pop()
            if "molecule/shared/fixtures/missing.j2" in event.msg:
                self._expected_prepare_failure = True
            events.extend(event.events or [])
            if event.chain is not None:
                events.append(event.chain.event)

    def v2_runner_item_on_failed(self, result):
        self.v2_runner_on_failed(result)

    def v2_playbook_on_stats(self, stats):
        target = os.environ.get("HOMELAB_VM_STATS")
        if target:
            path = Path(target)
            event = {
                "operation": os.environ.get("HOMELAB_VM_OPERATION", ""),
                "hosts": {host: stats.summarize(host) for host in stats.processed},
                "expected_preparation_failure": getattr(self, "_expected_prepare_failure", False),
            }
            path.write_text(json.dumps(event))
            path.chmod(0o600)
            history = path.with_name("dispatch-events.jsonl")
            with history.open("a") as stream:
                stream.write(json.dumps(event) + "\n")
            history.chmod(0o600)
