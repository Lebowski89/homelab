from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase

HAS_INFISICAL = False
INFISICAL_VERSION = None


try:
    from infisical_sdk import InfisicalSDKClient
    HAS_INFISICAL = True

except ImportError as e:
    HAS_INFISICAL = False


if HAS_INFISICAL:
    try:
        from importlib.metadata import version
        INFISICAL_VERSION = version('infisicalsdk')  # Note: package name might differ
    except ImportError:
        # Fallback for Python < 3.8
        import pkg_resources
        INFISICAL_VERSION = pkg_resources.get_distribution('infisicalsdk').version
    except Exception:
        INFISICAL_VERSION = "unknown"


DOCUMENTATION = r"""
name: read_secrets
author:
  - Infisical Inc.

short_description: Look up secrets stored in Infisical
description:
  - Retrieve secrets from Infisical, granted the caller has the right permissions to access the secret.
  - Secrets can be located either by their name for individual secret loopups or by environment/folder path to return all secrets within the given scope.

options:

  auth_method:
    description: The method to use to authenticate with Infisical
    required: False
    type: string
    version_added: 1.1.3
    default: universal_auth
    choices:
      - universal_auth
      - oidc_auth
    env:
      - name: INFISICAL_AUTH_METHOD
  universal_auth_client_id:
    description: The Machine Identity Client ID used to authenticate
    env:
      - name: UNIVERSAL_AUTH_MACHINE_IDENTITY_CLIENT_ID
      - name: INFISICAL_UNIVERSAL_AUTH_CLIENT_ID
    required: False
    type: string
    version_added: 1.0.0
  universal_auth_client_secret:
    description: The Machine Identity Client Secret used to authenticate
    env:
      - name: UNIVERSAL_AUTH_MACHINE_IDENTITY_CLIENT_SECRET
      - name: INFISICAL_UNIVERSAL_AUTH_CLIENT_SECRET
    required: False
    type: string
    version_added: 1.0.0
  url:
    description: Point to your self hosted instance of Infisical
    default: "https://app.infisical.com"
    env:
      - name: INFISICAL_URL
    required: False
    type: string
    version_added: 1.0.0
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
  identity_id:
    description: The identity ID of the user that should be authenticated
    env:
      - name: INFISICAL_MACHINE_IDENTITY_ID
    required: False
    type: string
    version_added: 1.1.3
  jwt:
    description: The JWT of the user that should be authenticated
    required: False
    type: string
    version_added: 1.1.3
    env:
      - name: INFISICAL_JWT
      - name: INFISICAL_OIDC_AUTH_JWT
"""

EXAMPLES = r"""
vars:
  read_all_secrets_within_scope: "{{ lookup('infisical_vault', universal_auth_client_id='<>', universal_auth_client_secret='<>', project_id='<>', path='/', env_slug='dev', url='https://spotify.infisical.com') }}"
  # [{ "key": "HOST", "value": "google.com" }, { "key": "SMTP", "value": "gmail.smtp.edu" }]

  read_all_secrets_as_dict: "{{ lookup('infisical_vault', universal_auth_client_id='<>', universal_auth_client_secret='<>', project_id='<>', path='/', env_slug='dev', as_dict=True, url='https://spotify.infisical.com') }}"
  # {"HOST": "google.com", "SMTP": "gmail.smtp.edu"}

  read_secret_by_name_within_scope: "{{ lookup('infisical_vault', universal_auth_client_id='<>', universal_auth_client_secret='<>', project_id='<>', path='/', env_slug='dev', secret_name='HOST', url='https://spotify.infisical.com') }}"
  # [{ "key": "HOST", "value": "google.com" }]
"""



def parse_version_tuple(version_string):
    if version_string == "unknown":
        return (0, 0, 0)  # assume very old version
    
    try:
        parts = version_string.split('.')
        # haandle missing parts (example: "1.2" becomes "1.2.0")
        while len(parts) < 3:
            parts.append('0')
        
        return tuple(int(part) for part in parts[:3])  # only take first 3 parts
    except (ValueError, AttributeError):
        return (0, 0, 0)


def check_minimum_version(current_version, minimum_version):
    """Check if current version meets minimum requirement."""
    current_tuple = parse_version_tuple(current_version)
    minimum_tuple = parse_version_tuple(minimum_version)
    return current_tuple >= minimum_tuple


class LookupModule(LookupBase):

    def get_sdk_client(self):
      url = self.get_option("url")
      client = InfisicalSDKClient(host=url)

      method = self.get_option("auth_method")

      if method == "universal_auth":

        machine_identity_client_id = self.get_option("universal_auth_client_id")
        machine_identity_client_secret = self.get_option("universal_auth_client_secret")

        if not machine_identity_client_id or not machine_identity_client_secret:
            raise AnsibleError("universal_auth_client_id or universal_auth_client_secret is not set. Please set them to use universal auth.")

        client.auth.universal_auth.login(
            machine_identity_client_id,
            machine_identity_client_secret
        )

      elif method == "oidc_auth":

        # make sure the infisicalsdk version is at least 1.0.10
        if not check_minimum_version(INFISICAL_VERSION, "1.0.10"):
            raise AnsibleError("Please upgrade the infisicalsdk to at least 1.0.10 to use oidc auth.")

        identity_id = self.get_option("identity_id")
        jwt = self.get_option("jwt")

        if not identity_id or not jwt:
            raise AnsibleError("identity_id or jwt is not set. Please set them to use oidc auth.")

        client.auth.oidc_auth.login(
            identity_id,
            jwt
        )
      else:
        raise AnsibleError(f"Invalid auth method. Please use universal_auth or oidc_auth. You provided {method}")

      return client



    def run(self, terms, variables=None, **kwargs):

        self.set_options(var_options=variables, direct=kwargs)
        if not HAS_INFISICAL:
            raise AnsibleError("Please pip install infisicalsdk to use the infisical_vault lookup module.")

        client = self.get_sdk_client()

        secretName = kwargs.get('secret_name')
        asDict = kwargs.get('as_dict')
        envSlug = kwargs.get('env_slug')
        path = kwargs.get('path')
        project_id = kwargs.get('project_id')

        if secretName:
            return self.get_single_secret(
                client,
                project_id,
                secretName,
                envSlug,
                path,
            )
        else:
            return self.get_all_secrets(client, project_id, envSlug, path, asDict)

    def get_single_secret(
            self,
            client,
            project_id,
            secret_name,
            environment,
            path
    ):
        try:
            secret = client.secrets.get_secret_by_name(
                secret_name=secret_name,
                project_id=project_id,
                environment_slug=environment,
                secret_path=path
            )

            return [{"value": secret.secretValue, "key": secret.secretKey}]
        except Exception as e:
            raise AnsibleError(f"Error fetching single secret {e}")

    def get_all_secrets(self, client, project_id, environment="dev", path="/", asDict=False):
        try:
            secrets = client.secrets.list_secrets(
                project_id=project_id,
                environment_slug=environment,
                secret_path=path
            )

            if asDict:
                return [{s.secretKey: s.secretValue for s in secrets.secrets}]
            else:
                return [{"value": s.secretValue, "key": s.secretKey} for s in secrets.secrets]
        except Exception as e:
            raise AnsibleError(f"Error fetching all secrets {e}")

