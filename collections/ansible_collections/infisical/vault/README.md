# Infisical Collection

This Ansible Infisical collection includes a variety of Ansible content to help automate the management of Infisical services. This collection is maintained by the Infisical team.

[View full documentation](https://infisical.com/docs/integrations/platforms/ansible)

## Ansible version compatibility

Tested with the Ansible Core >= 2.12.0 versions, and the current development version of Ansible. Ansible Core versions prior to 2.12.0 have not been tested.

## Python version compatibility

This collection depends on the Infisical SDK for Python. 

Requires Python 3.7 or greater.

## Installing this collection

You can install the Infisical collection with the Ansible Galaxy CLI:

```bash
ansible-galaxy collection install infisical.vault
```

The python module dependencies are not installed by `ansible-galaxy`. They can be manually installed using pip:

```bash
pip install infisicalsdk
```

## Using this collection

You can either call modules by their Fully Qualified Collection Name (FQCN), such as `infisical.vault.read_secrets`, or you can call modules by their short name if you list the `infisical.vault` collection in the playbook's `collections` keyword.

## Authentication

The Infisical Ansible Collection supports Universal Auth, OIDC, and Token Auth for authenticating against Infisical.

### Login Plugin (Recommended)

The recommended approach is to use the `login` lookup or module to authenticate once and reuse the credentials across multiple tasks. This reduces authentication overhead and makes playbooks cleaner.
You can also provide the authentication details directly on the plugins.

**Using the login module:**

```yaml
- name: Login to Infisical
  infisical.vault.login:
    url: "https://app.infisical.com"
    auth_method: universal_auth
    universal_auth_client_id: "{{ client_id }}"
    universal_auth_client_secret: "{{ client_secret }}"
  register: infisical_login

- name: Read secrets using cached login
  infisical.vault.read_secrets:
    login_data: "{{ infisical_login.login_data }}"
    project_id: "{{ project_id }}"
    env_slug: "dev"
    path: "/"
    as_dict: true
  register: secrets

- name: Use the secrets
  debug:
    msg: "Database URL is {{ secrets.secrets.DATABASE_URL }}"
```

**Using inline credentials:**

```yaml
- name: Read secrets with inline credentials
  set_fact:
    secrets: "{{ lookup('infisical.vault.read_secrets',
      url='https://app.infisical.com',
      auth_method='universal_auth',
      universal_auth_client_id=client_id,
      universal_auth_client_secret=client_secret,
      project_id=project_id,
      env_slug='dev',
      path='/',
      as_dict=true
    ) }}"

- name: Use the secrets
  debug:
    msg: "Database URL is {{ secrets.DATABASE_URL }}"
```

### Universal Auth

Using Universal Auth for authentication is the most straight-forward way to get started. You need to provide the Client ID and Client Secret of your Infisical Machine Identity.

You can provide the parameters through environment variables:

| Parameter Name               | Environment Variable Name                |
| ---------------------------- | ---------------------------------------- |
| auth_method                  | `INFISICAL_AUTH_METHOD`                  |
| universal_auth_client_id     | `INFISICAL_UNIVERSAL_AUTH_CLIENT_ID`     |
| universal_auth_client_secret | `INFISICAL_UNIVERSAL_AUTH_CLIENT_SECRET` |

### OIDC Auth

To use OIDC Auth, you'll need to provide the ID of your machine identity and the OIDC JWT for authentication.

> **Note:** OIDC Auth requires `infisicalsdk` version 1.0.10 or newer.

| Parameter Name  | Environment Variable Name |
| --------------- | ------------------------- |
| auth_method     | `INFISICAL_AUTH_METHOD`   |
| identity_id     | `INFISICAL_IDENTITY_ID`   |
| jwt             | `INFISICAL_JWT`           |

### Token Auth

Token Auth allows you to authenticate directly with an access token. This can be either a [Machine Identity Token Auth](https://infisical.com/docs/documentation/platform/identities/token-auth) token or a User JWT token.

> **Note:** Token Auth requires `infisicalsdk` version 1.0.13 or newer.

| Parameter Name | Environment Variable Name |
| -------------- | ------------------------- |
| auth_method    | `INFISICAL_AUTH_METHOD`   |
| token          | `INFISICAL_TOKEN`         |

## Available Plugins and Modules

### Lookups
- `infisical.vault.login` - Authenticate and return reusable login data
- `infisical.vault.read_secrets` - Read secrets from Infisical

### Modules

**Static Secrets:**
- `infisical.vault.login` - Authenticate and return reusable login data
- `infisical.vault.read_secrets` - Read secrets from Infisical
- `infisical.vault.create_secret` - Create a new secret
- `infisical.vault.update_secret` - Update an existing secret
- `infisical.vault.delete_secret` - Delete a secret

**Dynamic Secrets:**
- `infisical.vault.create_dynamic_secret` - Create a dynamic secret
- `infisical.vault.get_dynamic_secret` - Get a dynamic secret by name
- `infisical.vault.update_dynamic_secret` - Update a dynamic secret
- `infisical.vault.delete_dynamic_secret` - Delete a dynamic secret

**Dynamic Secret Leases:**
- `infisical.vault.create_dynamic_secret_lease` - Create a lease (generates credentials)
- `infisical.vault.get_dynamic_secret_lease` - Get lease details
- `infisical.vault.renew_dynamic_secret_lease` - Renew an existing lease
- `infisical.vault.delete_dynamic_secret_lease` - Delete/revoke a lease

## Examples

### Reading Secrets

```yaml
---
- name: Read secrets from Infisical
  hosts: localhost
  gather_facts: false

  tasks:
    - name: Login to Infisical
      infisical.vault.login:
        url: "https://app.infisical.com"
        auth_method: universal_auth
        universal_auth_client_id: "{{ lookup('env', 'INFISICAL_CLIENT_ID') }}"
        universal_auth_client_secret: "{{ lookup('env', 'INFISICAL_CLIENT_SECRET') }}"
      register: infisical_login

    - name: Read all secrets as dictionary
      infisical.vault.read_secrets:
        login_data: "{{ infisical_login.login_data }}"
        project_id: "your-project-id"
        env_slug: "dev"
        path: "/"
        as_dict: true
      register: secrets

    - name: Use the secrets
      debug:
        msg: "Database: {{ secrets.secrets.DATABASE_URL }}"
```

### Managing Secrets (CRUD)

```yaml
- name: Create a secret
  infisical.vault.create_secret:
    login_data: "{{ infisical_login.login_data }}"
    project_id: "{{ project_id }}"
    env_slug: "dev"
    path: "/"
    secret_name: "API_KEY"
    secret_value: "my-api-key"

- name: Update a secret
  infisical.vault.update_secret:
    login_data: "{{ infisical_login.login_data }}"
    project_id: "{{ project_id }}"
    env_slug: "dev"
    path: "/"
    secret_name: "API_KEY"
    secret_value: "new-api-key"

- name: Delete a secret
  infisical.vault.delete_secret:
    login_data: "{{ infisical_login.login_data }}"
    project_id: "{{ project_id }}"
    env_slug: "dev"
    path: "/"
    secret_name: "API_KEY"
```

### Dynamic Secrets

Dynamic secrets generate credentials on-demand with automatic expiration. They support various providers like SQL databases, AWS, GCP, Azure, and more.

```yaml
# Create a dynamic secret for PostgreSQL
- name: Create a PostgreSQL dynamic secret
  infisical.vault.create_dynamic_secret:
    login_data: "{{ infisical_login.login_data }}"
    project_slug: "my-project"
    env_slug: "dev"
    path: "/"
    name: "postgres-dev"
    provider_type: "sql-database"
    inputs:
      client: "postgres"
      host: "localhost"
      port: 5432
      database: "mydb"
      username: "admin"
      password: "admin-password"
      creationStatement: "CREATE USER \"{{username}}\" WITH PASSWORD '{{password}}';"
      revocationStatement: "DROP USER \"{{username}}\";"
    default_ttl: "1h"
    max_ttl: "24h"
  register: dynamic_secret

# Create a lease to get credentials
- name: Get database credentials
  infisical.vault.create_dynamic_secret_lease:
    login_data: "{{ infisical_login.login_data }}"
    project_slug: "my-project"
    env_slug: "dev"
    path: "/"
    dynamic_secret_name: "postgres-dev"
    ttl: "30m"
  register: lease

# Use the generated credentials
- name: Connect to database
  community.postgresql.postgresql_query:
    login_host: localhost
    login_user: "{{ lease.data.DB_USERNAME }}"
    login_password: "{{ lease.data.DB_PASSWORD }}"
    db: mydb
    query: "SELECT version();"

# Revoke the credentials when done
- name: Delete the lease
  infisical.vault.delete_dynamic_secret_lease:
    login_data: "{{ infisical_login.login_data }}"
    project_slug: "my-project"
    env_slug: "dev"
    path: "/"
    lease_id: "{{ lease.lease.id }}"
```
