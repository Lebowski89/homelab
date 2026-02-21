from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: delete_secret
short_description: Delete a secret from Infisical
version_added: "1.2.0"
author:
  - Infisical Inc.
description:
  - Delete a secret from Infisical by its name.
  - The secret must exist at the specified path and environment.
extends_documentation_fragment:
  - infisical.vault.auth

options:
  project_id:
    description: The ID of the project where the secret is stored.
    type: str
    required: true
  env_slug:
    description: >
      The environment slug where the secret is stored.
      Environment slug is the short name of a given environment.
    type: str
    required: true
  path:
    description: "The folder path where the secret resides. For example: /services/backend"
    type: str
    required: true
  secret_name:
    description: The name of the secret to delete.
    type: str
    required: true

seealso:
  - module: infisical.vault.login
    description: Use the login module to authenticate once and reuse the session.
  - module: infisical.vault.read_secrets
    description: Read secrets from Infisical.
  - module: infisical.vault.create_secret
    description: Create a new secret.
  - module: infisical.vault.update_secret
    description: Update an existing secret.
"""

EXAMPLES = r"""
# Delete a secret with direct authentication
- name: Delete a secret
  infisical.vault.delete_secret:
    url: "https://app.infisical.com"
    auth_method: universal_auth
    universal_auth_client_id: "{{ client_id }}"
    universal_auth_client_secret: "{{ client_secret }}"
    project_id: "my-project-id"
    env_slug: "dev"
    path: "/"
    secret_name: "OLD_SECRET"
  register: deleted_secret

# Delete a secret using login_data
- name: Login to Infisical
  infisical.vault.login:
    url: "https://app.infisical.com"
    auth_method: universal_auth
    universal_auth_client_id: "{{ client_id }}"
    universal_auth_client_secret: "{{ client_secret }}"
  register: infisical_login

- name: Delete a secret
  infisical.vault.delete_secret:
    login_data: "{{ infisical_login.login_data }}"
    project_id: "my-project-id"
    env_slug: "prod"
    path: "/database"
    secret_name: "DEPRECATED_SECRET"
  register: deleted_secret
"""

RETURN = r"""
secret:
  description: The deleted secret.
  returned: success
  type: dict
  contains:
    id:
      description: The unique identifier of the secret.
      type: str
    workspace:
      description: The workspace/project ID where the secret resided.
      type: str
    environment:
      description: The environment slug.
      type: str
    version:
      description: The version number of the secret.
      type: int
    type:
      description: The type of secret (shared or personal).
      type: str
    secretKey:
      description: The name of the secret.
      type: str
    secretValue:
      description: The value of the secret.
      type: str
    secretComment:
      description: The comment associated with the secret.
      type: str
    createdAt:
      description: The creation timestamp.
      type: str
    updatedAt:
      description: The last update timestamp.
      type: str
    secretMetadata:
      description: Additional metadata for the secret.
      type: dict
    secretValueHidden:
      description: Whether the secret value is hidden.
      type: bool
    secretReminderNote:
      description: A note for the secret reminder.
      type: str
    secretReminderRepeatDays:
      description: Number of days between secret reminder repeats.
      type: int
    skipMultilineEncoding:
      description: Whether multiline encoding was skipped.
      type: bool
    secretPath:
      description: The path where the secret was stored.
      type: str
    tags:
      description: List of tags that were attached to the secret.
      type: list
      elements: dict
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.infisical.vault.plugins.module_utils._authenticator import (
    InfisicalAuthenticator,
    create_client_from_login_data,
)
from ansible_collections.infisical.vault.plugins.module_utils._secrets import (
    clean_secret_dict,
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
        project_id=dict(type='str', required=True),
        env_slug=dict(type='str', required=True),
        path=dict(type='str', required=True),
        secret_name=dict(type='str', required=True),
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    if module.check_mode:
        module.exit_json(
            changed=True,
            secret={'secretKey': module.params['secret_name']},
        )

    try:
        login_data = module.params.get('login_data')
        client = get_sdk_client(module, login_data=login_data)
        
        secret = client.secrets.delete_secret_by_name(
            secret_name=module.params['secret_name'],
            project_id=module.params['project_id'],
            environment_slug=module.params['env_slug'],
            secret_path=module.params['path'],
        )
        
        module.exit_json(
            changed=True,
            secret=clean_secret_dict(secret.to_dict()),
        )
    except Exception as e:
        module.fail_json(msg=f"Error deleting secret: {type(e).__name__}: {e}")


def main():
    run_module()


if __name__ == '__main__':
    main()

