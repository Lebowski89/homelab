from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase

from ansible_collections.infisical.vault.plugins.module_utils._authenticator import (
    InfisicalAuthenticator,
    create_client_from_login_data,
)
from ansible_collections.infisical.vault.plugins.module_utils._secrets import (
    clean_secret_dict,
)


DOCUMENTATION = r"""
name: read_secrets
author:
  - Infisical Inc.

short_description: Look up secrets stored in Infisical
description:
  - Retrieve secrets from Infisical, granted the caller has the right permissions to access the secret.
  - Secrets can be located either by their name for individual secret lookups or by environment/folder path to return all secrets within the given scope.
  - You can either provide authentication credentials directly, or use C(login_data) from a previous C(infisical.vault.login) lookup to reuse an authenticated session.
extends_documentation_fragment:
  - infisical.vault.auth.lookup

seealso:
  - ref: infisical.vault.login lookup
    description: Use the login lookup to authenticate once and reuse the session.

options:
  path:
    description: "The folder path where the requested secret resides. For example: /services/backend"
    required: True
    type: string
    version_added: 1.0.0
  env_slug:
    description: "Used to select from which environment (environment slug) secrets should be fetched from. Environment slug is the short name of a given environment"
    required: True
    type: string
    version_added: 1.0.0
  project_id:
    description: "The ID of the project where the secrets are stored"
    required: True
    type: string
    version_added: 1.0.0
  secret_name:
    description: The name of the secret that should be fetched. The name should be exactly as it appears in Infisical.
    required: False
    type: string
    version_added: 1.0.0
  as_dict:
    description: "Return the listed secrets as a dictionary within a list instead of a list of key-value pairs (defaults to False). When True, returns [{'SECRET_KEY': 'secret_value', ...}] instead of [{'key': 'SECRET_KEY', 'value': 'secret_value'}, ...]. This only applies when reading all secrets within a scope, not when reading a single secret by name."
    required: False
    type: bool
    version_added: 1.0.0
  raw:
    description: >
      Return the full secret object with all properties instead of just key/value.
      When True, returns all secret metadata including id, version, type, secretComment, createdAt, updatedAt, tags, etc.
      When combined with C(as_dict=True), returns a dictionary where keys are secret names and values are full secret objects.
    required: False
    type: bool
    default: False
    version_added: 1.2.0
"""

EXAMPLES = r"""
# Direct authentication (authenticates on each call)
vars:
  read_all_secrets_within_scope: "{{ lookup('infisical.vault.read_secrets', universal_auth_client_id='<client-id>', universal_auth_client_secret='<client-secret>', project_id='<project-id>', path='/', env_slug='dev', url='https://app.infisical.com') }}"
  # [{ "key": "HOST", "value": "google.com" }, { "key": "SMTP", "value": "gmail.smtp.edu" }]

  read_all_secrets_as_dict: "{{ lookup('infisical.vault.read_secrets', universal_auth_client_id='<client-id>', universal_auth_client_secret='<client-secret>', project_id='<project-id>', path='/', env_slug='dev', as_dict=True, url='https://app.infisical.com') }}"
  # {"HOST": "google.com", "SMTP": "gmail.smtp.edu"}

  read_secret_by_name_within_scope: "{{ lookup('infisical.vault.read_secrets', universal_auth_client_id='<client-id>', universal_auth_client_secret='<client-secret>', project_id='<project-id>', path='/', env_slug='dev', secret_name='HOST', url='https://app.infisical.com') }}"
  # [{ "key": "HOST", "value": "google.com" }]

# Using login_data from infisical.vault.login (recommended for multiple lookups)
# This avoids re-authenticating on each call
- name: Login to Infisical once
  set_fact:
    infisical_login: "{{ lookup('infisical.vault.login', url='https://app.infisical.com', auth_method='universal_auth', universal_auth_client_id='<client-id>', universal_auth_client_secret='<client-secret>') }}"

- name: Read database secrets using cached login
  set_fact:
    db_secrets: "{{ lookup('infisical.vault.read_secrets', login_data=infisical_login, project_id='<project-id>', path='/database', env_slug='prod') }}"

- name: Read API secrets using the same login (no re-authentication)
  set_fact:
    api_secrets: "{{ lookup('infisical.vault.read_secrets', login_data=infisical_login, project_id='<project-id>', path='/api', env_slug='prod') }}"

- name: Read a specific secret using cached login
  set_fact:
    api_key: "{{ lookup('infisical.vault.read_secrets', login_data=infisical_login, project_id='<project-id>', path='/api', env_slug='prod', secret_name='API_KEY') }}"

# Using raw=True to get full secret metadata
- name: Read all secrets with full metadata
  set_fact:
    raw_secrets: "{{ lookup('infisical.vault.read_secrets', login_data=infisical_login, project_id='<project-id>', path='/', env_slug='dev', raw=True) }}"
  # Returns: [{"id": "...", "secretKey": "HOST", "secretValue": "google.com", "version": 1, "type": "shared", ...}, ...]

- name: Read all secrets with full metadata as dict
  set_fact:
    raw_secrets_dict: "{{ lookup('infisical.vault.read_secrets', login_data=infisical_login, project_id='<project-id>', path='/', env_slug='dev', raw=True, as_dict=True) }}"
  # Returns: {"HOST": {"id": "...", "secretKey": "HOST", "secretValue": "google.com", "version": 1, ...}, ...}
"""

RETURN = r"""
_list:
  description:
    - When C(raw=False) (default) and C(as_dict=False), returns a list of dictionaries with 'key' and 'value' keys.
    - When C(raw=False) and C(as_dict=True), returns a list containing a single dictionary mapping secret names to values.
    - When C(raw=True), returns a list of full secret objects with all properties.
    - When C(raw=True) and C(as_dict=True), returns a list containing a single dictionary mapping secret names to full secret objects.
  type: list
  elements: raw
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


class LookupModule(LookupBase):

    def _get_sdk_client(self, login_data=None):
        """Get an authenticated Infisical SDK client.
        
        Args:
            login_data: Optional login data dict from infisical.vault.login lookup.
                       Contains url and access_token for authentication.
        
        Returns:
            An authenticated InfisicalSDKClient instance
        """
        # If login_data is provided, create a client using the saved token
        if login_data is not None:
            try:
                return create_client_from_login_data(login_data)
            except (ImportError, ValueError) as e:
                raise AnsibleError(f"Configuration error creating client from login_data: {e}")
            except Exception as e:
                raise AnsibleError(f"Failed to create client from login_data: {type(e).__name__}: {e}")
        
        # Otherwise, authenticate fresh
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
            return authenticator.authenticate()
        except (ImportError, ValueError) as e:
            raise AnsibleError(f"Configuration error during Infisical authentication: {e}")
        except Exception as e:
            raise AnsibleError(f"Failed to authenticate with Infisical: {type(e).__name__}: {e}")

    def run(self, terms, variables=None, **kwargs):
        self.set_options(var_options=variables, direct=kwargs)

        # Get login_data if provided
        login_data = kwargs.get('login_data')
        client = self._get_sdk_client(login_data=login_data)

        secret_name = kwargs.get('secret_name')
        as_dict = kwargs.get('as_dict', False)
        raw = kwargs.get('raw', False)
        env_slug = kwargs.get('env_slug')
        path = kwargs.get('path')
        project_id = kwargs.get('project_id')

        if secret_name:
            return self._get_single_secret(client, project_id, secret_name, env_slug, path, raw)
        else:
            return self._get_all_secrets(client, project_id, env_slug, path, as_dict, raw)

    def _get_single_secret(self, client, project_id, secret_name, environment, path, raw=False):
        """Fetch a single secret by name."""
        try:
            secret = client.secrets.get_secret_by_name(
                secret_name=secret_name,
                project_id=project_id,
                environment_slug=environment,
                secret_path=path
            )
            if raw:
                return [clean_secret_dict(secret.to_dict())]
            return [{"value": secret.secretValue, "key": secret.secretKey}]
        except Exception as e:
            raise AnsibleError(f"Error fetching secret '{secret_name}': {e}")

    def _get_all_secrets(self, client, project_id, environment="dev", path="/", as_dict=False, raw=False):
        """Fetch all secrets within the specified scope."""
        try:
            secrets = client.secrets.list_secrets(
                project_id=project_id,
                environment_slug=environment,
                secret_path=path
            )

            if as_dict:
                if raw:
                    return [{s.secretKey: clean_secret_dict(s.to_dict()) for s in secrets.secrets}]
                return [{s.secretKey: s.secretValue for s in secrets.secrets}]
            else:
                if raw:
                    return [clean_secret_dict(s.to_dict()) for s in secrets.secrets]
                return [{"value": s.secretValue, "key": s.secretKey} for s in secrets.secrets]
        except Exception as e:
            raise AnsibleError(f"Error fetching secrets: {e}")
