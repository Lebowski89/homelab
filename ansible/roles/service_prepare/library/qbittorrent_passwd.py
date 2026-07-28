#!/usr/bin/python
import base64
import hashlib
import os

from ansible.module_utils.basic import AnsibleModule


def qbittorrent_passwd(plain_passwd):
    try:
        ITERATIONS = 100_000
        SALT_SIZE = 16

        salt = os.urandom(SALT_SIZE)
        h = hashlib.pbkdf2_hmac("sha512", plain_passwd.encode(), salt, ITERATIONS)
        return f"@ByteArray({base64.b64encode(salt).decode()}:{base64.b64encode(h).decode()})"
    except Exception as err:
        raise ValueError(f"Error generating password hash: {err}") from err


def main():
    module_args = dict(password=dict(type="str", required=True, no_log=True))

    result = dict(changed=False, msg="")

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    try:
        result["msg"] = qbittorrent_passwd(module.params["password"])
    except ValueError as err:
        module.fail_json(msg=str(err))

    module.exit_json(**result)


if __name__ == "__main__":
    main()
