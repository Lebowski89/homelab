#!/usr/bin/python
"""Documentation stub for the controller-side firewall validator."""

from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r"""
---
module: worker_backend_firewall_validate
short_description: Validate exact firewall sources and policy inputs locally
description: Performs no host mutation or secret lookup.
options:
  policy:
    description: The value-free firewall policy.
    type: dict
    required: true
  require_verified:
    description: Whether live installation requires source confirmation.
    type: bool
    required: true
author: Homelab maintainers
"""


def main():
    module = AnsibleModule(
        argument_spec={"policy": {"type": "dict", "required": True}, "require_verified": {"type": "bool", "required": True}},
        supports_check_mode=True,
    )
    module.fail_json(msg="This module requires its controller-side action plugin")


if __name__ == "__main__":
    main()
