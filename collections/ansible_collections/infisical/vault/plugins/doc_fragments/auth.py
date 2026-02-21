from __future__ import absolute_import, division, print_function
__metaclass__ = type


# Shared option definitions
_URL_MODULE = """
  url:
    description: Point to your self-hosted instance of Infisical.
    type: str
    default: "https://app.infisical.com"
"""

_URL_LOOKUP = """
  url:
    description: Point to your self-hosted instance of Infisical.
    default: "https://app.infisical.com"
    env:
      - name: INFISICAL_URL
    required: False
    type: string
"""

_AUTH_METHOD_MODULE = """
  auth_method:
    description: The method to use to authenticate with Infisical.
    type: str
    default: universal_auth
    choices:
      - universal_auth
      - oidc_auth
      - token_auth
"""

_AUTH_METHOD_LOOKUP = """
  auth_method:
    description: The method to use to authenticate with Infisical.
    required: False
    type: string
    default: universal_auth
    choices:
      - universal_auth
      - oidc_auth
      - token_auth
    env:
      - name: INFISICAL_AUTH_METHOD
"""

_UNIVERSAL_AUTH_MODULE = """
  universal_auth_client_id:
    description: The Machine Identity Client ID used to authenticate (for universal_auth).
    type: str
  universal_auth_client_secret:
    description: The Machine Identity Client Secret used to authenticate (for universal_auth).
    type: str
    no_log: true
"""

_UNIVERSAL_AUTH_LOOKUP = """
  universal_auth_client_id:
    description: The Machine Identity Client ID used to authenticate.
    env:
      - name: UNIVERSAL_AUTH_MACHINE_IDENTITY_CLIENT_ID
      - name: INFISICAL_UNIVERSAL_AUTH_CLIENT_ID
    required: False
    type: string
  universal_auth_client_secret:
    description: The Machine Identity Client Secret used to authenticate.
    env:
      - name: UNIVERSAL_AUTH_MACHINE_IDENTITY_CLIENT_SECRET
      - name: INFISICAL_UNIVERSAL_AUTH_CLIENT_SECRET
    required: False
    type: string
"""

_OIDC_AUTH_MODULE = """
  identity_id:
    description: The identity ID of the user that should be authenticated (for OIDC auth).
    type: str
  jwt:
    description: The JWT of the user that should be authenticated (for OIDC auth).
    type: str
    no_log: true
"""

_OIDC_AUTH_LOOKUP = """
  identity_id:
    description: The identity ID of the user that should be authenticated (for OIDC auth).
    env:
      - name: INFISICAL_MACHINE_IDENTITY_ID
    required: False
    type: string
  jwt:
    description: The JWT of the user that should be authenticated (for OIDC auth).
    required: False
    type: string
    env:
      - name: INFISICAL_JWT
      - name: INFISICAL_OIDC_AUTH_JWT
"""

_TOKEN_AUTH_MODULE = """
  token:
    description: >
      An access token used to authenticate with Infisical. This can be either a Machine Identity Token Auth token
      or a User JWT token. Both token types can be used interchangeably with this field.
    type: str
    no_log: true
"""

_TOKEN_AUTH_LOOKUP = """
  token:
    description: >
      An access token used to authenticate with Infisical. This can be either a Machine Identity Token Auth token
      or a User JWT token. Both token types can be used interchangeably with this field.
    required: False
    type: string
    env:
      - name: INFISICAL_TOKEN
"""

_LOGIN_DATA_MODULE = """
  login_data:
    description:
      - Login data from a previous C(infisical.vault.login) operation.
      - When provided, the access token from the login data will be used, avoiding re-authentication.
      - This should be a dictionary containing C(url) and C(access_token) keys.
    type: dict
"""

_LOGIN_DATA_LOOKUP = """
  login_data:
    description:
      - Login data from a previous C(infisical.vault.login) lookup.
      - When provided, the access token from the login data will be used, avoiding re-authentication.
      - This is mutually exclusive with direct authentication options (auth_method, universal_auth_client_id, etc.).
    required: False
    type: dict
"""

_LOGIN_DATA_NOTE = """
notes:
  - When using C(login_data), the C(url), C(auth_method), and authentication credential parameters are ignored.
"""


class ModuleDocFragment:
    """Documentation fragment for Infisical authentication options."""

    # Authentication options for login module (no login_data option)
    LOGIN = r"""
options:
{url}{auth_method}{universal_auth}{oidc_auth}{token_auth}
""".format(
        url=_URL_MODULE,
        auth_method=_AUTH_METHOD_MODULE,
        universal_auth=_UNIVERSAL_AUTH_MODULE,
        oidc_auth=_OIDC_AUTH_MODULE,
        token_auth=_TOKEN_AUTH_MODULE,
    )

    # Standard authentication options for modules (includes login_data)
    DOCUMENTATION = r"""
options:
{login_data}{url}{auth_method}{universal_auth}{oidc_auth}{token_auth}
{note}
""".format(
        login_data=_LOGIN_DATA_MODULE,
        url=_URL_MODULE,
        auth_method=_AUTH_METHOD_MODULE,
        universal_auth=_UNIVERSAL_AUTH_MODULE,
        oidc_auth=_OIDC_AUTH_MODULE,
        token_auth=_TOKEN_AUTH_MODULE,
        note=_LOGIN_DATA_NOTE,
    )

    # Authentication options for lookup plugins (with env vars, includes login_data)
    LOOKUP = r"""
options:
{login_data}{url}{auth_method}{universal_auth}{oidc_auth}{token_auth}
{note}
""".format(
        login_data=_LOGIN_DATA_LOOKUP,
        url=_URL_LOOKUP,
        auth_method=_AUTH_METHOD_LOOKUP,
        universal_auth=_UNIVERSAL_AUTH_LOOKUP,
        oidc_auth=_OIDC_AUTH_LOOKUP,
        token_auth=_TOKEN_AUTH_LOOKUP,
        note=_LOGIN_DATA_NOTE,
    )

    # Authentication options for login lookup (no login_data, with env vars)
    LOOKUP_LOGIN = r"""
options:
{url}{auth_method}{universal_auth}{oidc_auth}{token_auth}
""".format(
        url=_URL_LOOKUP,
        auth_method=_AUTH_METHOD_LOOKUP,
        universal_auth=_UNIVERSAL_AUTH_LOOKUP,
        oidc_auth=_OIDC_AUTH_LOOKUP,
        token_auth=_TOKEN_AUTH_LOOKUP,
    )
