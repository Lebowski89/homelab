from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: login
short_description: Perform a login operation against Infisical
version_added: "1.2.0"
author:
  - Infisical Inc.
description:
  - Performs a login operation against Infisical, returning login data containing an access token.
  - The login data can be registered and reused across multiple subsequent tasks to avoid repeated authentication.
  - This is useful for playbooks that need to fetch multiple secrets, as it reduces the number of authentication requests.
extends_documentation_fragment:
  - infisical.vault.auth.login

seealso:
  - module: infisical.vault.read_secrets
    description: Use the login data with read_secrets to fetch secrets without re-authenticating.

notes:
  - The returned login data contains the access token and can be registered for reuse in subsequent tasks.
"""

EXAMPLES = r"""
# Login with universal auth and register the result
- name: Login to Infisical
  infisical.vault.login:
    url: "https://app.infisical.com"
    auth_method: universal_auth
    universal_auth_client_id: "{{ client_id }}"
    universal_auth_client_secret: "{{ client_secret }}"
  register: infisical_login

# Use the registered login data with read_secrets
- name: Read secrets using cached login
  infisical.vault.read_secrets:
    login_data: "{{ infisical_login.login_data }}"
    project_id: "my-project-id"
    env_slug: "prod"
    path: "/"
  register: secrets

# Login with OIDC auth
- name: Login with OIDC
  infisical.vault.login:
    auth_method: oidc_auth
    identity_id: "{{ identity_id }}"
    jwt: "{{ jwt_token }}"
  register: infisical_login

# Login with token auth
- name: Login with token
  infisical.vault.login:
    auth_method: token_auth
    token: "{{ my_token }}"
  register: infisical_login
"""

RETURN = r"""
login_data:
  description: >
    A dictionary containing the login data that can be passed directly to other modules.
    Use C({{ infisical_login.login_data }}) when passing to C(read_secrets) for example.
  returned: success
  type: dict
  contains:
    url:
      description: The Infisical instance URL.
      type: str
    access_token:
      description: The access token for API authentication.
      type: str
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.infisical.vault.plugins.module_utils._authenticator import (
    InfisicalAuthenticator,
)

def run_module():
    module_args = dict(
        url=dict(type='str', default='https://app.infisical.com'),
        auth_method=dict(
            type='str',
            default='universal_auth',
            choices=['universal_auth', 'oidc_auth', 'token_auth']
        ),
        universal_auth_client_id=dict(type='str'),
        universal_auth_client_secret=dict(type='str', no_log=True),
        identity_id=dict(type='str'),
        jwt=dict(type='str', no_log=True),
        token=dict(type='str', no_log=True),
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    # In check mode, just return success without actually authenticating
    if module.check_mode:
        check_login_data = {
            'url': module.params['url'],
            'access_token': '<check_mode_token>',
        }
        module.exit_json(
            changed=False,
            login_data=check_login_data
        )

    try:
        authenticator = InfisicalAuthenticator(
            url=module.params['url'],
            auth_method=module.params['auth_method'],
            client_id=module.params['universal_auth_client_id'],
            client_secret=module.params['universal_auth_client_secret'],
            identity_id=module.params['identity_id'],
            jwt=module.params['jwt'],
            token=module.params['token'],
        )
        
        login_data = authenticator.login()
        
        module.exit_json(
            changed=False,
            login_data=login_data
        )
    except (ImportError, ValueError) as e:
        module.fail_json(msg=str(e))
    except Exception as e:
        module.fail_json(msg=f"Unexpected error during login: {type(e).__name__}: {e}")


def main():
    run_module()


if __name__ == '__main__':
    main()

