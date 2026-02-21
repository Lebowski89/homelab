from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: read_secrets
short_description: Read secrets from Infisical
version_added: "1.2.0"
author:
  - Infisical Inc.
description:
  - Retrieve secrets from Infisical, granted the caller has the right permissions to access the secret.
  - Secrets can be located either by their name for individual secret lookups or by environment/folder path to return all secrets within the given scope.
  - You can either provide authentication credentials directly, or use C(login_data) from a previous C(infisical.vault.login) task to reuse an authenticated session.
extends_documentation_fragment:
  - infisical.vault.auth

options:
  project_id:
    description: The ID of the project where the secrets are stored.
    type: str
    required: true
  env_slug:
    description: >
      The environment slug to fetch secrets from.
      Environment slug is the short name of a given environment.
    type: str
    required: true
  path:
    description: "The folder path where the requested secret resides. For example: /services/backend"
    type: str
    required: true
  secret_name:
    description: >
      The name of the secret that should be fetched.
      The name should be exactly as it appears in Infisical.
      If not provided, all secrets at the given path will be returned.
    type: str
  as_dict:
    description: >
      Return the listed secrets as a dictionary instead of a list of key-value pairs.
      When True, returns {'SECRET_KEY': 'secret_value', ...} instead of [{'key': 'SECRET_KEY', 'value': 'secret_value'}, ...].
      This only applies when reading all secrets within a scope, not when reading a single secret by name.
    type: bool
    default: false
  raw:
    description: >
      Return the full secret object with all properties instead of just key/value.
      When True, returns all secret metadata including id, version, type, secretComment, createdAt, updatedAt, tags, etc.
      When combined with C(as_dict=True), returns a dictionary where keys are secret names and values are full secret objects.
    type: bool
    default: false

seealso:
  - module: infisical.vault.login
    description: Use the login module to authenticate once and reuse the session.
"""

EXAMPLES = r"""
# Direct authentication (authenticates on each call)
- name: Read all secrets in a path
  infisical.vault.read_secrets:
    url: "https://app.infisical.com"
    auth_method: universal_auth
    universal_auth_client_id: "{{ client_id }}"
    universal_auth_client_secret: "{{ client_secret }}"
    project_id: "my-project-id"
    env_slug: "dev"
    path: "/"
  register: all_secrets

# Read secrets as a dictionary
- name: Read all secrets as dict
  infisical.vault.read_secrets:
    url: "https://app.infisical.com"
    auth_method: universal_auth
    universal_auth_client_id: "{{ client_id }}"
    universal_auth_client_secret: "{{ client_secret }}"
    project_id: "my-project-id"
    env_slug: "dev"
    path: "/"
    as_dict: true
  register: secrets_dict

# Using login_data from infisical.vault.login (recommended for multiple calls)
- name: Login to Infisical once
  infisical.vault.login:
    url: "https://app.infisical.com"
    auth_method: universal_auth
    universal_auth_client_id: "{{ client_id }}"
    universal_auth_client_secret: "{{ client_secret }}"
  register: infisical_login

- name: Read database secrets using cached login
  infisical.vault.read_secrets:
    login_data: "{{ infisical_login.login_data }}"
    project_id: "my-project-id"
    env_slug: "prod"
    path: "/database"
  register: db_secrets

- name: Read API secrets using the same login (no re-authentication)
  infisical.vault.read_secrets:
    login_data: "{{ infisical_login.login_data }}"
    project_id: "my-project-id"
    env_slug: "prod"
    path: "/api"
  register: api_secrets

# Read a specific secret by name
- name: Read a specific secret
  infisical.vault.read_secrets:
    login_data: "{{ infisical_login.login_data }}"
    project_id: "my-project-id"
    env_slug: "prod"
    path: "/"
    secret_name: "DATABASE_URL"
  register: db_url_secret

# Using raw=True to get full secret metadata
- name: Read all secrets with full metadata
  infisical.vault.read_secrets:
    login_data: "{{ infisical_login.login_data }}"
    project_id: "my-project-id"
    env_slug: "dev"
    path: "/"
    raw: true
  register: raw_secrets
  # Returns secrets with all properties: id, version, type, secretComment, createdAt, updatedAt, tags, etc.

- name: Read all secrets with full metadata as dict
  infisical.vault.read_secrets:
    login_data: "{{ infisical_login.login_data }}"
    project_id: "my-project-id"
    env_slug: "dev"
    path: "/"
    raw: true
    as_dict: true
  register: raw_secrets_dict
  # Returns: {"SECRET_NAME": {"id": "...", "secretKey": "SECRET_NAME", "secretValue": "...", "version": 1, ...}, ...}
"""

RETURN = r"""
secrets:
  description: >
    The secrets retrieved from Infisical.
    When C(secret_name) is provided, returns a list with a single secret.
    When C(as_dict) is True, returns a dictionary of secret key-value pairs.
    When C(raw) is True, returns full secret objects with all properties.
    When C(raw) and C(as_dict) are both True, returns a dictionary mapping secret names to full secret objects.
  returned: success
  type: raw
  sample:
    - key: "DATABASE_URL"
      value: "postgres://localhost:5432/db"
  contains:
    key:
      description: The name of the secret (when C(raw=False)).
      type: str
    value:
      description: The value of the secret (when C(raw=False)).
      type: str
    id:
      description: The unique identifier of the secret (when C(raw=True)).
      type: str
    workspace:
      description: The workspace/project ID where the secret resides (when C(raw=True)).
      type: str
    environment:
      description: The environment slug (when C(raw=True)).
      type: str
    version:
      description: The version number of the secret (when C(raw=True)).
      type: int
    type:
      description: The type of secret - shared or personal (when C(raw=True)).
      type: str
    secretKey:
      description: The name of the secret (when C(raw=True)).
      type: str
    secretValue:
      description: The value of the secret (when C(raw=True)).
      type: str
    secretComment:
      description: The comment associated with the secret (when C(raw=True)).
      type: str
    createdAt:
      description: The creation timestamp (when C(raw=True)).
      type: str
    updatedAt:
      description: The last update timestamp (when C(raw=True)).
      type: str
    secretMetadata:
      description: Additional metadata for the secret (when C(raw=True)).
      type: dict
    secretValueHidden:
      description: Whether the secret value is hidden (when C(raw=True)).
      type: bool
    secretReminderNote:
      description: A note for the secret reminder (when C(raw=True)).
      type: str
    secretReminderRepeatDays:
      description: Number of days between secret reminder repeats (when C(raw=True)).
      type: int
    skipMultilineEncoding:
      description: Whether multiline encoding was skipped (when C(raw=True)).
      type: bool
    secretPath:
      description: The path where the secret is stored (when C(raw=True)).
      type: str
    tags:
      description: List of tags attached to the secret (when C(raw=True)).
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
    
    # Otherwise, authenticate fresh
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


def get_single_secret(client, project_id, secret_name, environment, path, raw=False):
    """Fetch a single secret by name."""
    secret = client.secrets.get_secret_by_name(
        secret_name=secret_name,
        project_id=project_id,
        environment_slug=environment,
        secret_path=path
    )
    if raw:
        return [clean_secret_dict(secret.to_dict())]
    return [{"value": secret.secretValue, "key": secret.secretKey}]


def get_all_secrets(client, project_id, environment, path, as_dict=False, raw=False):
    """Fetch all secrets within the specified scope."""
    secrets = client.secrets.list_secrets(
        project_id=project_id,
        environment_slug=environment,
        secret_path=path
    )

    if as_dict:
        if raw:
            return {s.secretKey: clean_secret_dict(s.to_dict()) for s in secrets.secrets}
        return {s.secretKey: s.secretValue for s in secrets.secrets}
    else:
        if raw:
            return [clean_secret_dict(s.to_dict()) for s in secrets.secrets]
        return [{"value": s.secretValue, "key": s.secretKey} for s in secrets.secrets]


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
        secret_name=dict(type='str'),
        as_dict=dict(type='bool', default=False),
        raw=dict(type='bool', default=False),
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    # In check mode, just return success without actually fetching secrets
    if module.check_mode:
        module.exit_json(
            changed=False,
            secrets=[],
        )

    try:
        login_data = module.params.get('login_data')
        client = get_sdk_client(module, login_data=login_data)
        
        project_id = module.params['project_id']
        env_slug = module.params['env_slug']
        path = module.params['path']
        secret_name = module.params.get('secret_name')
        as_dict = module.params['as_dict']
        raw = module.params['raw']
        
        if secret_name:
            secrets = get_single_secret(client, project_id, secret_name, env_slug, path, raw)
        else:
            secrets = get_all_secrets(client, project_id, env_slug, path, as_dict, raw)
        
        module.exit_json(
            changed=False,
            secrets=secrets,
        )
    except Exception as e:
        import traceback
        module.fail_json(
            msg=f"Error fetching secrets: {type(e).__name__}: {e}",
            exception=traceback.format_exc()
        )


def main():
    run_module()


if __name__ == '__main__':
    main()

