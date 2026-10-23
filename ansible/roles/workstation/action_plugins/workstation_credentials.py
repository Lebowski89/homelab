"""Keep interactive input within one action, outside facts and task results."""

from __future__ import annotations

from ansible.errors import AnsibleError, AnsiblePromptInterrupt, AnsiblePromptNoninteractive
from ansible.module_utils.common.text.converters import to_text
from ansible.plugins.action import ActionBase

SETUP = (
    "Run skynet run workstation credentials from an interactive terminal, or use the existing "
    "NetBox-independent workstation bootstrap with --tags workstation_credentials. "
    "For local provisioning sudo, use --ask-become-pass independently of saved managed-host credentials."
)
PROMPTS = {
    "vault": "Existing Ansible Vault encryption password (do not choose a new password)",
    "become": "Managed-host sudo password supplied by Skynet (not automatically this workstation's local sudo password)",
}


class ActionModule(ActionBase):
    """Inspect all destinations before collecting any missing credentials."""

    _VALID_ARGS = frozenset({"directory", "vault_file", "become_file", "owner"})
    _supports_check_mode = True

    def run(self, tmp=None, task_vars=None):
        result = super().run(tmp, task_vars)
        values = {}
        try:
            arguments = dict(self._task.args, operation="inspect")
            inspected = self._execute_module(module_name="workstation_credential_files", module_args=arguments, task_vars=task_vars)
            if inspected.get("failed"):
                return dict(result, failed=True, msg=inspected["msg"])
            missing = inspected["missing"]
            if self._task.check_mode:
                return dict(result, changed=inspected["changed"], missing=missing, created=[])
            for kind in missing:
                first = self._display.prompt_until(PROMPTS[kind] + ":", private=True, interrupt_input=(b"\x03", b"\x04"))
                if not first.strip() or any(char in first for char in (b"\x00", b"\r", b"\n")):
                    return dict(result, failed=True, msg="Empty or invalid password rejected; no password files were written. " + SETUP)
                second = self._display.prompt_until("Confirm " + PROMPTS[kind] + ":", private=True, interrupt_input=(b"\x03", b"\x04"))
                if first != second:
                    return dict(result, failed=True, msg="Password confirmation did not match; no password files were written. " + SETUP)
                values[kind] = to_text(first, errors="strict")
            applied = self._execute_module(
                module_name="workstation_credential_files",
                module_args=dict(arguments, operation="apply", values=values),
                task_vars=task_vars,
            )
            # Do not forward module invocation data or any secret-bearing objects.
            if applied.get("failed"):
                return dict(result, failed=True, msg=applied["msg"])
            return dict(result, changed=applied["changed"], missing=[], created=applied["created"])
        except AnsiblePromptNoninteractive:
            return dict(result, failed=True, msg="Credential input is required but interactive prompting is unavailable. " + SETUP)
        except (AnsiblePromptInterrupt, KeyboardInterrupt, EOFError):
            return dict(result, failed=True, msg="Credential setup cancelled; no password files were written. " + SETUP)
        except (AnsibleError, UnicodeError):
            return dict(result, failed=True, msg="Credential setup could not complete safely. " + SETUP)
        finally:
            values.clear()
