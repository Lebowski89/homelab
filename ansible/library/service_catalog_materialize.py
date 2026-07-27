#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule


def main():
    module = AnsibleModule(
        argument_spec={
            "source_var": {"type": "str", "required": True},
            "selected": {"type": "list", "elements": "dict", "required": True},
        },
        supports_check_mode=True,
    )
    module.fail_json(msg="service_catalog_materialize requires its controller-side action plugin")


if __name__ == "__main__":
    main()
