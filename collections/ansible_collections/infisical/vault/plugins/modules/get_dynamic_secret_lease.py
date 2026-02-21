from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: get_dynamic_secret_lease
short_description: Get a dynamic secret lease from Infisical
version_added: "1.2.0"
author:
  - Infisical Inc.
description:
  - Retrieve a dynamic secret lease by ID from Infisical.
  - Returns the lease details including expiration time and associated dynamic secret.
extends_documentation_fragment:
  - infisical.vault.auth

options:
  project_slug:
    description: The slug of the project containing the dynamic secret.
    type: str
    required: true
  env_slug:
    description: The environment slug where the dynamic secret is located.
    type: str
    required: true
  path:
    description: "The folder path where the dynamic secret is located. For example: /services/backend"
    type: str
    default: "/"
  lease_id:
    description: The ID of the lease to retrieve.
    type: str
    required: true

seealso:
  - module: infisical.vault.login
    description: Use the login module to authenticate once and reuse the session.
  - module: infisical.vault.create_dynamic_secret_lease
    description: Create a new lease.
  - module: infisical.vault.renew_dynamic_secret_lease
    description: Renew an existing lease.
  - module: infisical.vault.delete_dynamic_secret_lease
    description: Revoke a lease.
"""

EXAMPLES = r"""
# Get a lease by ID
- name: Get lease details
  infisical.vault.get_dynamic_secret_lease:
    login_data: "{{ infisical_login.login_data }}"
    project_slug: "my-project"
    env_slug: "dev"
    path: "/"
    lease_id: "{{ created_lease.lease.id }}"
  register: lease_details

- name: Display lease expiration
  debug:
    msg: "Lease expires at: {{ lease_details.lease.expireAt }}"
"""

RETURN = r"""
lease:
  description: The lease information.
  returned: success
  type: dict
  contains:
    id:
      description: The unique identifier of the lease.
      type: str
    expireAt:
      description: The expiration timestamp of the lease.
      type: str
    createdAt:
      description: The creation timestamp.
      type: str
    updatedAt:
      description: The last update timestamp.
      type: str
    version:
      description: The version number of the lease.
      type: int
    dynamicSecretId:
      description: The ID of the dynamic secret this lease belongs to.
      type: str
    externalEntityId:
      description: The external entity ID.
      type: str
    status:
      description: The status of the lease.
      type: str
    statusDetails:
      description: Details about the status.
      type: str
    dynamicSecret:
      description: The associated dynamic secret configuration.
      type: dict
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.infisical.vault.plugins.module_utils._authenticator import (
    InfisicalAuthenticator,
    create_client_from_login_data,
)


def get_sdk_client(module, login_data=None):
    """Get an authenticated Infisical SDK client."""
    if login_data is not None:
        try:
            return create_client_from_login_data(login_data)
        except (ImportError, ValueError) as e:
            module.fail_json(msg=str(e))
    
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
        return authenticator.authenticate()
    except (ImportError, ValueError) as e:
        module.fail_json(msg=str(e))


def run_module():
    module_args = dict(
        login_data=dict(type='dict', no_log=True),
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
        project_slug=dict(type='str', required=True),
        env_slug=dict(type='str', required=True),
        path=dict(type='str', default='/'),
        lease_id=dict(type='str', required=True),
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    if module.check_mode:
        module.exit_json(
            changed=False,
            lease={'id': module.params['lease_id']},
        )

    try:
        login_data = module.params.get('login_data')
        client = get_sdk_client(module, login_data=login_data)
        
        lease = client.dynamic_secrets.leases.get(
            lease_id=module.params['lease_id'],
            project_slug=module.params['project_slug'],
            environment_slug=module.params['env_slug'],
            path=module.params['path'],
        )
        
        module.exit_json(
            changed=False,
            lease=lease.to_dict(),
        )
    except Exception as e:
        module.fail_json(msg=f"Error getting dynamic secret lease: {type(e).__name__}: {e}")


def main():
    run_module()


if __name__ == '__main__':
    main()

