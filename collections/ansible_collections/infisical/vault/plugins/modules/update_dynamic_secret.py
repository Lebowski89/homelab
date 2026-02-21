from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: update_dynamic_secret
short_description: Update a dynamic secret in Infisical
version_added: "1.2.0"
author:
  - Infisical Inc.
description:
  - Update an existing dynamic secret configuration in Infisical.
  - You can update the name, TTL settings, provider inputs, and metadata.
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
    description: The current name of the dynamic secret to update.
    type: str
    required: true
  new_name:
    description: The new name for the dynamic secret (if renaming).
    type: str
  inputs:
    description:
      - Updated provider-specific configuration inputs.
      - The structure varies depending on the provider type.
    type: dict
  default_ttl:
    description:
      - The new default time to live for leases.
      - Example values are "1h", "30m", "24h".
    type: str
  max_ttl:
    description:
      - The new maximum time to live for leases.
      - Example values are "24h", "7d".
    type: str
  metadata:
    description:
      - Updated list of metadata items with 'key' and 'value'.
    type: list
    elements: dict
  username_template:
    description:
      - The new username template for the dynamic secret.
    type: str

seealso:
  - module: infisical.vault.login
    description: Use the login module to authenticate once and reuse the session.
  - module: infisical.vault.get_dynamic_secret
    description: Get a dynamic secret by name.
  - module: infisical.vault.create_dynamic_secret
    description: Create a new dynamic secret.
  - module: infisical.vault.delete_dynamic_secret
    description: Delete a dynamic secret.
"""

EXAMPLES = r"""
# Update a dynamic secret's TTL
- name: Update dynamic secret TTL
  infisical.vault.update_dynamic_secret:
    login_data: "{{ infisical_login.login_data }}"
    project_slug: "my-project"
    env_slug: "dev"
    path: "/"
    name: "postgres-dev"
    default_ttl: "2h"
    max_ttl: "48h"
  register: updated_secret

# Rename a dynamic secret
- name: Rename dynamic secret
  infisical.vault.update_dynamic_secret:
    login_data: "{{ infisical_login.login_data }}"
    project_slug: "my-project"
    env_slug: "dev"
    path: "/"
    name: "postgres-dev"
    new_name: "postgres-development"
  register: renamed_secret

# Update dynamic secret with username template
- name: Update dynamic secret username template
  infisical.vault.update_dynamic_secret:
    login_data: "{{ infisical_login.login_data }}"
    project_slug: "my-project"
    env_slug: "dev"
    path: "/"
    name: "postgres-dev"
    username_template: "svc_{{identity.name}}_{{random(6)}}"
  register: updated_secret
"""

RETURN = r"""
dynamic_secret:
  description: The updated dynamic secret.
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
    usernameTemplate:
      description: The username template for the dynamic secret.
      type: str
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
        new_name=dict(type='str'),
        inputs=dict(type='dict', no_log=True),
        default_ttl=dict(type='str'),
        max_ttl=dict(type='str'),
        metadata=dict(type='list', elements='dict'),
        username_template=dict(type='str'),
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    if module.check_mode:
        module.exit_json(
            changed=True,
            dynamic_secret={'name': module.params.get('new_name') or module.params['name']},
        )

    try:
        login_data = module.params.get('login_data')
        client = get_sdk_client(module, login_data=login_data)
        
        update_kwargs = dict(
            name=module.params['name'],
            project_slug=module.params['project_slug'],
            environment_slug=module.params['env_slug'],
            path=module.params['path'],
        )
        
        if module.params.get('new_name') is not None:
            update_kwargs['new_name'] = module.params['new_name']
        if module.params.get('inputs') is not None:
            update_kwargs['inputs'] = module.params['inputs']
        if module.params.get('default_ttl') is not None:
            update_kwargs['default_ttl'] = module.params['default_ttl']
        if module.params.get('max_ttl') is not None:
            update_kwargs['max_ttl'] = module.params['max_ttl']
        if module.params.get('metadata') is not None:
            update_kwargs['metadata'] = module.params['metadata']
        if module.params.get('username_template') is not None:
            update_kwargs['username_template'] = module.params['username_template']
        
        dynamic_secret = client.dynamic_secrets.update(**update_kwargs)
        
        module.exit_json(
            changed=True,
            dynamic_secret=dynamic_secret.to_dict(),
        )
    except Exception as e:
        module.fail_json(msg=f"Error updating dynamic secret: {type(e).__name__}: {e}")


def main():
    run_module()


if __name__ == '__main__':
    main()

