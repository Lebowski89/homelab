#!/usr/bin/python
"""Documentation shim for the read-only installed-prerequisite action."""

from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r"""
---
module: service_operational_check
short_description: Inspect managed runtime metadata and audit installed protection
description: Reuses existing execution ownership and firewall checks without installing policy.
options:
  phase:
    description: Read managed runtime metadata or audit installed protection.
    type: str
    choices: [runtime, protection]
    required: true
  metadata:
    description: Value-free effective service metadata, never environments or secret values.
    type: dict
    required: true
  inventory_host:
    description: Exact endpoint inventory host for delegated protection checks.
    type: str
author: Homelab maintainers
"""


def main():
    module = AnsibleModule(
        argument_spec={
            "phase": {"type": "str", "required": True},
            "metadata": {"type": "dict", "required": True},
            "inventory_host": {"type": "str"},
        },
        supports_check_mode=True,
    )
    module.fail_json(msg="This module requires its controller-side action plugin")


if __name__ == "__main__":
    main()
