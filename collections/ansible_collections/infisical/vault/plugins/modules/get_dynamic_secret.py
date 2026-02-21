from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: get_dynamic_secret
short_description: Get a dynamic secret from Infisical
version_added: "1.2.0"
author:
  - Infisical Inc.
description:
  - Retrieve a dynamic secret configuration by name from Infisical.
  - This returns the dynamic secret metadata, not the generated credentials.
  - To generate credentials, use the create_dynamic_secret_lease module.
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
  name:
    description: The name of the dynamic secret to retrieve.
    type: str
    required: true

seealso:
  - module: infisical.vault.login
    description: Use the login module to authenticate once and reuse the session.
  - module: infisical.vault.create_dynamic_secret
    description: Create a new dynamic secret.
  - module: infisical.vault.create_dynamic_secret_lease
    description: Create a lease to generate credentials.
"""

EXAMPLES = r"""
# Get a dynamic secret by name
- name: Get a dynamic secret
  infisical.vault.get_dynamic_secret:
    login_data: "{{ infisical_login.login_data }}"
    project_slug: "my-project"
    env_slug: "dev"
    path: "/"
    name: "postgres-dev"
  register: dynamic_secret

- name: Display the dynamic secret
  debug:
    var: dynamic_secret.dynamic_secret
"""

RETURN = r"""
dynamic_secret:
  description: The dynamic secret configuration.
  returned: success
  type: dict
  contains:
    id:
      description: The unique identifier of the dynamic secret.
      type: str
    name:
      description: The name of the dynamic secret.
      type: str
    version:
      description: The version number of the dynamic secret.
      type: int
    type:
      description: The provider type.
      type: str
    folderId:
      description: The folder ID where the dynamic secret is stored.
      type: str
    createdAt:
      description: The creation timestamp.
      type: str
    updatedAt:
      description: The last update timestamp.
      type: str
    defaultTTL:
      description: The default TTL for leases.
      type: str
    maxTTL:
      description: The maximum TTL for leases.
      type: str
    status:
      description: The status of the dynamic secret.
      type: str
    statusDetails:
      description: Details about the status.
      type: str
    metadata:
      description: Metadata key-value pairs.
      type: list
    inputs:
      description: The provider-specific configuration inputs.
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
        name=dict(type='str', required=True),
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    if module.check_mode:
        module.exit_json(
            changed=False,
            dynamic_secret={'name': module.params['name']},
        )

    try:
        login_data = module.params.get('login_data')
        client = get_sdk_client(module, login_data=login_data)
        
        dynamic_secret = client.dynamic_secrets.get_by_name(
            name=module.params['name'],
            project_slug=module.params['project_slug'],
            environment_slug=module.params['env_slug'],
            path=module.params['path'],
        )
        
        module.exit_json(
            changed=False,
            dynamic_secret=dynamic_secret.to_dict(),
        )
    except Exception as e:
        module.fail_json(msg=f"Error getting dynamic secret: {type(e).__name__}: {e}")


def main():
    run_module()


if __name__ == '__main__':
    main()

