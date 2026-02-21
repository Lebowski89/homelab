from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase

from ansible_collections.infisical.vault.plugins.module_utils._authenticator import (
    InfisicalAuthenticator,
)


DOCUMENTATION = r"""
name: login
author:
  - Infisical Inc.
version_added: "1.2.0"

short_description: Perform a login operation against Infisical
description:
  - Performs a login operation against Infisical, returning login data containing an access token.
  - The login data can be cached and reused across multiple subsequent lookups to avoid repeated authentication.
  - This is useful for playbooks that need to fetch multiple secrets, as it reduces the number of authentication requests.
extends_documentation_fragment:
  - infisical.vault.auth.lookup_login

seealso:
  - ref: infisical.vault.read_secrets lookup
    description: Use the login_data with read_secrets to fetch secrets without re-authenticating.

notes:
  - This lookup does not use the term string and will not work correctly in loops. Only a single response will be returned.
  - The returned login_data contains the access token and can be stored in an Ansible variable for reuse.
"""

EXAMPLES = r"""
# Login once and reuse the login_data for multiple secret lookups
- name: Login to Infisical
  set_fact:
    infisical_login: "{{ lookup('infisical.vault.login', url='https://app.infisical.com', auth_method='universal_auth', universal_auth_client_id='<client-id>', universal_auth_client_secret='<client-secret>') }}"

- name: Read secrets using the cached login
  set_fact:
    db_secrets: "{{ lookup('infisical.vault.read_secrets', login_data=infisical_login, project_id='<project-id>', path='/database', env_slug='prod') }}"

- name: Read more secrets using the same login (no re-authentication)
  set_fact:
    api_secrets: "{{ lookup('infisical.vault.read_secrets', login_data=infisical_login, project_id='<project-id>', path='/api', env_slug='prod') }}"

# Using OIDC authentication
- name: Login with OIDC
  set_fact:
    infisical_login: "{{ lookup('infisical.vault.login', auth_method='oidc_auth', identity_id='<identity-id>', jwt='<jwt-token>') }}"

# Using token authentication
- name: Login with token
  set_fact:
    infisical_login: "{{ lookup('infisical.vault.login', auth_method='token_auth', token='<your-token>') }}"

# Display login info (for debugging - avoid in production as it exposes the token)
- name: Show login data structure
  debug:
    msg: "Logged in to {{ infisical_login.url }}"
"""

RETURN = r"""
_raw:
  description:
    - A dictionary containing login data that can be passed to other lookups.
    - Contains the URL and access token needed for subsequent API calls.
  type: list
  elements: dict
  contains:
    url:
      description: The Infisical instance URL used for authentication.
      type: str
      returned: always
    access_token:
      description: The access token for API authentication. Pass this via login_data to read_secrets.
      type: str
      returned: always
"""


class LookupModule(LookupBase):

    def run(self, terms, variables=None, **kwargs):
        self.set_options(var_options=variables, direct=kwargs)

        authenticator = InfisicalAuthenticator(
            url=self.get_option('url'),
            auth_method=self.get_option('auth_method'),
            client_id=self.get_option('universal_auth_client_id'),
            client_secret=self.get_option('universal_auth_client_secret'),
            identity_id=self.get_option('identity_id'),
            jwt=self.get_option('jwt'),
            token=self.get_option('token'),
        )
        
        try:
            login_data = authenticator.login()
            return [login_data]
        except (ImportError, ValueError) as e:
            raise AnsibleError(f"Configuration error during Infisical login: {e}")
        except Exception as e:
            raise AnsibleError(f"Failed to login to Infisical: {type(e).__name__}: {e}")
