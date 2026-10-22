#!/usr/bin/python
"""Documentation stub for the controller-only firewall planning action."""

from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r"""
---
module: worker_backend_firewall_plan
short_description: Derive temporary worker backend ports from effective services
description: Templates endpoint metadata only, using the canonical target merger.
options:
  source_var:
    description: Name of the raw service mapping variable.
    type: str
    required: true
  workers:
    description: Worker inventory names permitted by this temporary policy.
    type: list
    elements: str
    required: true
  controller_address:
    description: Inventory-derived mgt source candidate, requiring operator verification.
    type: str
    required: true
author: Homelab maintainers
"""


def main():
    module = AnsibleModule(
        argument_spec={
            "source_var": {"type": "str", "required": True},
            "workers": {"type": "list", "elements": "str", "required": True},
            "controller_address": {"type": "str", "required": True},
        },
        supports_check_mode=True,
    )
    module.fail_json(msg="This module requires its controller-side action plugin")


if __name__ == "__main__":
    main()
