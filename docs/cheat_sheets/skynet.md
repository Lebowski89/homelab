# Skynet Wrapper

`skynet` is the convenience wrapper for running this repository’s Ansible automation.

It standardises how the homelab playbook is executed by wrapping `ansible-playbook`, `ansible-lint`, `yamllint`, `ruff`, inventory checks, vault/become password files, and common role/service tags behind a simpler command interface.

The wrapper is installed on the Ansible manager host and is mainly intended to be run from the management VM.

## What it does

`skynet` provides a consistent entrypoint for:

* Deploying catalog services through their declared Docker or Podman runtime.
* Updating existing catalog services.
* Removing services.
* Recreating services.
* Running check mode before real changes.
* Running role/action tags without remembering raw Ansible tag names.
* Running lint checks for YAML, Ansible, and Python helper modules.
* Running basic repository/playbook health checks.
* Listing known service tags and role/action targets.
* Passing through raw `ansible-playbook` arguments when needed.

It does **not** replace Ansible. It is a thin wrapper around this repository’s existing Ansible playbook, inventory, roles, service variable files, and tags.

## Defaults

The wrapper uses these default paths unless overridden with environment variables:

| Item                       | Purpose                                               |
| -------------------------- | ----------------------------------------------------- |
| `PLAYBOOK`                 | Main Ansible playbook path                            |
| `INVENTORY`                | NetBox dynamic inventory path                         |
| `ANSIBLE_CONFIG`           | Repository Ansible config                             |
| `BECOME_PASS_FILE`         | Become/sudo password file                             |
| `VAULT_PASS_FILE`          | Ansible Vault password file                           |
| `DOCKER_SERVICES_DIR`      | Directory containing catalog service variable files   |
| `ANSIBLE_VENV_PATH`        | Python virtual environment containing Ansible tooling |
| `REPO_ROOT`                | Repository root used for linting                      |
| `PYTHON_LIBRARY_PATH`      | Custom Python module path checked by Ruff             |
| `ANSIBLE_LOG_PATH`         | Ansible log output path                               |
| `ANSIBLE_COLLECTIONS_PATH` | Repository-managed Ansible collections path           |

By default, service tags are discovered from:

```text
<repo-root>/ansible/group_vars/all/services/
```

Each enabled service file in that directory can define service-level tags and optional target-level tags.

Example override:

```bash
PLAYBOOK=/opt/homelab/ansible/playbook.yml skynet check all
```

Example service directory override (the environment variable retains its legacy name):

```bash
DOCKER_SERVICES_DIR=/opt/homelab/ansible/group_vars/all/services skynet tags
```

## Common workflow

A typical safe workflow is:

```bash
skynet lint
skynet doctor
skynet check all
```

Then run a targeted deploy/update/recreate if the check passes:

```bash
skynet recreate authelia
```

or for role/action targets:

```bash
skynet run infisical-podman deploy
```

## Core commands

### `skynet lint`

Runs repository linting:

```bash
skynet lint
```

This currently runs:

* `yamllint` against tracked YAML files.
* `ruff check` against the custom Python modules.
* `ruff format --check`.
* `ansible-lint` against the Ansible directory.

Use this before committing changes.

### `skynet doctor`

Runs basic health checks for the local Ansible setup:

```bash
skynet doctor
```

Checks include:

* Playbook exists.
* Inventory exists.
* `ansible.cfg` exists.
* `ansible-playbook` is available.
* Inventory parses.
* Playbook syntax check passes.
* `--list-tags` works.
* Service variable directory exists.
* Service variable files are present.
* Vault password file exists.
* Important Ansible collections are installed.

Optional ping check:

```bash
skynet doctor --ping
```

The ping target defaults to the configured doctor ping target.

### `skynet check`

Runs Ansible in check mode with diff enabled:

```bash
skynet check <target>
```

For catalog services, this uses the normal service tag flow and the runtime declared by each selected service:

```bash
skynet check authelia
skynet check nzbhydra2
skynet check plex
skynet check all
```

For role/action targets, it resolves friendly target names to raw Ansible tags:

```bash
skynet check infisical-podman
skynet check infisical-podman recreate
skynet check ubuntu sysctl
skynet check docker swarm
```

`check` is intended to preview changes. It should not be used as proof that every runtime mutation is possible, but it is useful for catching template, variable, inventory, syntax, and check-mode safety issues.

### `skynet deploy`

Deploys one or more service targets through their declared runtime:

```bash
skynet deploy authelia
skynet deploy grafana prometheus
```

Alias:

```bash
skynet install authelia
```

`install` is treated as `deploy`.

### `skynet update`

Runs the update path for a service or all services:

```bash
skynet update authelia
skynet update plex
skynet update all
```

Use this when image/tag updates or service updates should be applied without a full recreate.

`update` is intended for catalog service targets. For role/action targets, use `skynet run <role-target> [action]`.

### `skynet recreate`

Runs the recreate path:

```bash
skynet recreate authelia
skynet recreate nzbhydra2
```

For role/action targets, this can also map to the role’s recreate tag:

```bash
skynet recreate infisical-podman
```

Equivalent explicit form:

```bash
skynet run infisical-podman recreate
```

### `skynet remove`

Runs the remove path:

```bash
skynet remove authelia
```

Alias:

```bash
skynet reset authelia
```

For role/action targets:

```bash
skynet remove infisical-podman
```

Equivalent explicit form:

```bash
skynet run infisical-podman remove
```

### `skynet bootstrap`

Runs bootstrap tags:

```bash
skynet bootstrap netbox
skynet bootstrap infisical-podman
```

For catalog services, this passes the normal `bootstrap,<tag>` Ansible tag combination.

For role/action targets, it maps to the role-specific bootstrap tag where supported.

### `skynet run`

Runs a role/action target directly.

Syntax:

```bash
skynet run <role-target> [action]
```

Examples:

```bash
skynet run infisical-podman deploy
skynet run infisical-podman recreate
skynet run infisical-podman remove
skynet run ubuntu sysctl
skynet run docker swarm
skynet run opentofu pve-user
```

If no action is supplied, `deploy` is assumed:

```bash
skynet run infisical-podman
```

is equivalent to:

```bash
skynet run infisical-podman deploy
```

Alias:

```bash
skynet target <role-target> [action]
```

## Role/action targets

Use:

```bash
skynet targets
```

to list supported role/action mappings.

Role/action targets are manually mapped inside the wrapper’s `role_tag()` function.

### NetBox

| Command                       | Raw tag            |
| ----------------------------- | ------------------ |
| `skynet run netbox bootstrap` | `netbox_bootstrap` |
| `skynet run netbox deploy`    | `netbox_deploy`    |
| `skynet run netbox recreate`  | `netbox_recreate`  |
| `skynet run netbox remove`    | `netbox_remove`    |

### Ubuntu

| Command                          | Raw tag               |
| -------------------------------- | --------------------- |
| `skynet run ubuntu`              | `ubuntu`              |
| `skynet run ubuntu apt`          | `ubuntu_apt`          |
| `skynet run ubuntu repo`         | `ubuntu_repo`         |
| `skynet run ubuntu venv`         | `ubuntu_venv`         |
| `skynet run ubuntu requirements` | `ubuntu_requirements` |
| `skynet run ubuntu skynet`       | `ubuntu_skynet`       |
| `skynet run ubuntu sysctl`       | `ubuntu_sysctl`       |
| `skynet run ubuntu pam`          | `ubuntu_pam`          |
| `skynet run ubuntu network`      | `ubuntu_network`      |
| `skynet run ubuntu netplan`      | `ubuntu_netplan`      |

### Docker

| Command                                 | Raw tag                           |
| --------------------------------------- | --------------------------------- |
| `skynet run docker`                     | `docker`                          |
| `skynet run docker install`             | `docker_install`                  |
| `skynet run docker prune`               | `docker_prune`                    |
| `skynet run docker prune-dangling`      | `docker_prune_dangling`           |
| `skynet run docker prune-unused`        | `docker_prune_unused`             |
| `skynet run docker prune-volumes`       | `docker_prune_volumes`            |
| `skynet run docker prune-timer`         | `docker_prune_timer`              |
| `skynet run docker prune-unraid-script` | `docker_prune_unraid_user_script` |
| `skynet run docker swarm`               | `docker_swarm`                    |
| `skynet run docker swarm-init`          | `docker_swarm_init`               |
| `skynet run docker swarm-join`          | `docker_swarm_join`               |
| `skynet run docker swarm-network`       | `docker_swarm_network`            |
| `skynet run docker swarm-labels`        | `docker_swarm_labels`             |

### Hugo

| Command                     | Raw tag          |
| --------------------------- | ---------------- |
| `skynet run hugo bootstrap` | `hugo_bootstrap` |
| `skynet run hugo deploy`    | `hugo_bootstrap` |
| `skynet run hugo submodule` | `hugo_submodule` |

### Infisical

| Command                          | Raw tag               |
| -------------------------------- | --------------------- |
| `skynet run infisical bootstrap` | `infisical_bootstrap` |
| `skynet run infisical deploy`    | `infisical_deploy`    |
| `skynet run infisical recreate`  | `infisical_recreate`  |
| `skynet run infisical remove`    | `infisical_remove`    |

### OpenTofu

| Command                        | Raw tag             |
| ------------------------------ | ------------------- |
| `skynet run opentofu`          | `opentofu`          |
| `skynet run opentofu install`  | `opentofu_install`  |
| `skynet run opentofu pve-user` | `opentofu_pve_user` |

### Postgres

| Command                                   | Raw tag                        |
| ----------------------------------------- | ------------------------------ |
| `skynet run postgres`                     | `postgres`                     |
| `skynet run postgres apt`                 | `postgres_apt`                 |
| `skynet run postgres etcd`                | `postgres_etcd`                |
| `skynet run postgres etcd-reset`          | `postgres_etcd_reset`          |
| `skynet run postgres patroni`             | `postgres_patroni`             |
| `skynet run postgres patroni-reset`       | `postgres_patroni_reset`       |
| `skynet run postgres backup`              | `postgres_backup`              |
| `skynet run postgres restore`             | `postgres_restore`             |
| `skynet run postgres admin`               | `postgres_admin`               |
| `skynet run postgres admin-uptime-kuma`   | `postgres_admin_uptime_kuma`   |
| `skynet run postgres admin-nuke-node`     | `postgres_admin_nuke_node`     |
| `skynet run postgres admin-fix-owner`     | `postgres_admin_fix_owner`     |
| `skynet run postgres admin-update-pg-hba` | `postgres_admin_update_pg_hba` |

### Podman

| Command                     | Raw tag          |
| --------------------------- | ---------------- |
| `skynet run podman`         | `podman`         |
| `skynet run podman install` | `podman_install` |

### Infisical Podman

| Command                                 | Raw tag                      |
| --------------------------------------- | ---------------------------- |
| `skynet run infisical-podman bootstrap` | `infisical_podman_bootstrap` |
| `skynet run infisical-podman deploy`    | `infisical_podman_deploy`    |
| `skynet run infisical-podman recreate`  | `infisical_podman_recreate`  |
| `skynet run infisical-podman remove`    | `infisical_podman_remove`    |

## Service targets

Docker and Podman services are managed using service names and tags defined in the per-service variable files under:

```text
ansible/group_vars/all/services/
```

Each service file can define:

* a top-level service name,
* `enabled: true` or `enabled: false`,
* service-level tags,
* optional target-level tags under `targets:`.

`skynet tags` scans this directory and prints tags from enabled services and enabled targets.

List available tags, including role/action tags and catalog service tags:

```bash
skynet tags
```

Examples:

```bash
skynet check authelia
skynet deploy authelia
skynet update authelia
skynet recreate authelia
skynet remove authelia
```

Multiple service tags can be supplied:

```bash
skynet check grafana prometheus loki
skynet deploy radarr sonarr prowlarr
```

Update all services:

```bash
skynet update all
```

Check all services:

```bash
skynet check all
```

### Service-level and target-level tags

A single-target service can define tags directly:

```yaml
grafana:
  enabled: true
  tags: [apps, monitoring, pgsql, grafana]
```

A multi-target service can define shared service tags and target-specific tags:

```yaml
radarr:
  enabled: true
  tags: [apps, arrs, pgsql, radarr]

  targets:
    radarr:
      enabled: true
      tags: [radarr_main]

    radarr_4k:
      enabled: true
      tags: [radarr_4k]
```

This allows:

```bash
skynet check radarr
skynet check radarr_main
skynet check radarr_4k
```

Disabled services or targets are not listed by `skynet tags`.

## Inventory helpers

Show inventory graph:

```bash
skynet inventory
```

or:

```bash
skynet inventory --graph
```

Show full inventory JSON:

```bash
skynet inventory --list
```

## Limit to a host or group

Use `limit` to restrict a run to an inventory host or group:

```bash
skynet limit mgt check infisical-podman
skynet limit unraid check nzbhydra2
skynet limit tags_docker run docker swarm
```

The command after the limit works the same as normal:

```bash
skynet limit mgt run ubuntu skynet
```

## Raw Ansible passthrough

Use `raw` when the wrapper does not expose the exact operation you need:

```bash
skynet raw --list-tags
skynet raw --syntax-check
skynet raw --tags infisical_podman_deploy
skynet raw --check --diff --tags postgres_backup
```

This is the escape hatch for advanced or unusual playbook runs.

## Syntax check

Run Ansible syntax check:

```bash
skynet syntax
```

## Versions

Print tool and path information:

```bash
skynet versions
```

This is useful when debugging the active Ansible virtual environment, inventory path, playbook path, service vars directory, or lint tooling.

## CI-style local check

Run lint and doctor together:

```bash
skynet ci
```

This does not replace GitHub Actions, but gives a quick local confidence check.

## Logging

`skynet` sets `ANSIBLE_LOG_PATH` by default to:

```text
<repo-root>/.ansible/ansible.log
```

The `.ansible/` directory should not be committed.

Sensitive tasks should use `no_log: true`, especially when rendering templates or handling secrets.

When running check mode with `--diff`, be careful: diffs can expose rendered config contents unless the task or template item disables diff output or uses `no_log`.

## Check mode notes

`skynet check` runs:

```bash
ansible-playbook --check --diff
```

This is useful, but not identical to a real run.

Some tasks must intentionally skip or change behaviour in check mode, especially tasks that:

* Create containers temporarily.
* Generate secrets.
* Start services after templating systemd/quadlet files.
* Read back files that would only be written during a real run.
* Clone or update the same Git repository the playbook is running from.

If check mode says something “would change”, it does not necessarily mean the change has actually been written to disk.

## Recommended usage patterns

Before committing:

```bash
skynet lint
skynet doctor
skynet check all
```

Before changing a single service:

```bash
skynet check authelia
skynet recreate authelia
```

Before changing a role/action target:

```bash
skynet check infisical-podman recreate
skynet run infisical-podman recreate
```

Before touching host-level Ubuntu config:

```bash
skynet check ubuntu sysctl
skynet run ubuntu sysctl
```

Before modifying Swarm setup:

```bash
skynet check docker swarm
skynet run docker swarm
```

## Quick reference

| Command                        | Purpose                                       |
| ------------------------------ | --------------------------------------------- |
| `skynet lint`                  | Run YAML, Python, and Ansible linting         |
| `skynet doctor`                | Check local Ansible setup                     |
| `skynet check all`             | Check all catalog services                    |
| `skynet check <service>`       | Check one catalog service                     |
| `skynet deploy <service>`      | Deploy one catalog service                    |
| `skynet update <service>`      | Update one catalog service                    |
| `skynet update all`            | Update all catalog services                   |
| `skynet recreate <service>`    | Recreate one catalog service                  |
| `skynet remove <service>`      | Remove one catalog service                    |
| `skynet run <role> [action]`   | Run a role/action target                      |
| `skynet check <role> [action]` | Check a role/action target                    |
| `skynet targets`               | List role/action target mappings              |
| `skynet tags`                  | List known role and catalog service tags      |
| `skynet inventory`             | Show inventory graph                          |
| `skynet inventory --list`      | Show full inventory JSON                      |
| `skynet syntax`                | Run Ansible syntax check                      |
| `skynet versions`              | Show wrapper/tool path information            |
| `skynet raw ...`               | Pass arguments directly to `ansible-playbook` |

## Adding new role targets to `skynet`

`skynet` supports two broad kinds of targets:

1. **Catalog service targets**, which are discovered from service variable files under `ansible/group_vars/all/services/`, explicitly declare `runtime: docker` or `runtime: podman`, and are used with commands like:

```bash
skynet check authelia
skynet recreate plex
skynet update all
```

2. **Role/action targets**, which are explicitly mapped inside the wrapper and used with commands like:

```bash
skynet check infisical-podman recreate
skynet run ubuntu sysctl
skynet run docker swarm
```

This section explains how to add new Ansible role tags to the wrapper.

### When to add a role/action target

Add a role/action target when a role has its own tags and is not managed through the service catalog loop.

Good examples:

```text
ubuntu_sysctl
docker_swarm
opentofu_pve_user
infisical_podman_recreate
postgres_backup
```

These are better exposed as:

```bash
skynet run ubuntu sysctl
skynet run docker swarm
skynet run opentofu pve-user
skynet run infisical-podman recreate
skynet run postgres backup
```

Do **not** add normal catalog service names here. Services should continue to use the service/tag flow from their service variable files:

```bash
skynet check authelia
skynet recreate nzbhydra2
skynet update all
```

### Step 1: Add the tag to the playbook

First, make sure the role or task is tagged in `ansible/playbook.yml`.

Example:

```yaml
- name: Include Example role
  when: inventory_hostname == services_controller_host
  ansible.builtin.include_role:
    name: example
  tags:
    - example_bootstrap
    - example_deploy
    - example_recreate
    - example_remove
```

For smaller task-level actions, use more specific tags:

```yaml
- name: Include Example role
  ansible.builtin.include_role:
    name: example
  tags:
    - example
    - example_config
    - example_service
    - example_cleanup
```

### Step 2: Add the mapping to `role_tag()`

Open the `skynet` wrapper template:

```text
ansible/roles/ubuntu/templates/skynet.j2
```

Find the `role_tag()` function.

Add a new block to the `case "${target}:${action}" in` section.

Example for a role with lifecycle-style tags:

```bash
example:bootstrap)    echo "example_bootstrap" ;;
example:deploy)       echo "example_deploy" ;;
example:recreate)     echo "example_recreate" ;;
example:remove)       echo "example_remove" ;;
```

This enables:

```bash
skynet run example bootstrap
skynet run example deploy
skynet run example recreate
skynet run example remove
```

It also enables check mode:

```bash
skynet check example deploy
skynet check example recreate
```

If no action is supplied, `deploy` is used by default:

```bash
skynet run example
skynet check example
```

Both map to:

```text
example_deploy
```

### Step 3: Add the target to `print_targets()`

Find the `print_targets()` function and add a matching documentation block.

Example:

```text
  example:
    bootstrap -> example_bootstrap
    deploy    -> example_deploy
    recreate  -> example_recreate
    remove    -> example_remove
```

This makes the target visible when running:

```bash
skynet targets
```

### Step 4: Test the wrapper mapping

After installing or templating the updated wrapper, check that the target appears:

```bash
skynet targets
```

Then test check mode:

```bash
skynet check example
skynet check example recreate
```

For a real run:

```bash
skynet run example deploy
```

Use `raw` to compare the underlying tag behaviour:

```bash
skynet raw --check --diff --tags example_deploy
```

This should behave the same as:

```bash
skynet check example deploy
```

### Naming conventions

Use hyphens in the wrapper command and underscores in Ansible tags.

Wrapper target:

```text
infisical-podman
```

Ansible tag:

```text
infisical_podman_deploy
```

Command:

```bash
skynet run infisical-podman deploy
```

This keeps CLI usage readable while preserving normal Ansible tag naming.

### Recommended action names

Prefer these standard action names where possible:

| Action      | Use for                                                           |
| ----------- | ----------------------------------------------------------------- |
| `bootstrap` | First-time setup, directories, initial config, prerequisite setup |
| `deploy`    | Normal apply/deploy path                                          |
| `recreate`  | Stop/remove/recreate flow                                         |
| `remove`    | Destructive removal                                               |
| `install`   | Package or tool installation                                      |
| `config`    | Configuration-only changes                                        |
| `backup`    | Backup tasks                                                      |
| `restore`   | Restore tasks                                                     |
| `admin`     | Administrative/maintenance tasks                                  |

Examples:

```bash
skynet run postgres backup
skynet run postgres restore
skynet run opentofu pve-user
skynet run docker swarm
skynet run ubuntu sysctl
```

### Example: adding a new `example` role

#### 1. Add role tags in `playbook.yml`

```yaml
- name: Include Example role
  when: inventory_hostname == services_controller_host
  ansible.builtin.include_role:
    name: example
  tags:
    - example_bootstrap
    - example_deploy
    - example_recreate
    - example_remove
```

#### 2. Add mappings to `role_tag()`

```bash
example:bootstrap)    echo "example_bootstrap" ;;
example:deploy)       echo "example_deploy" ;;
example:recreate)     echo "example_recreate" ;;
example:remove)       echo "example_remove" ;;
```

#### 3. Add documentation to `print_targets()`

```text
  example:
    bootstrap -> example_bootstrap
    deploy    -> example_deploy
    recreate  -> example_recreate
    remove    -> example_remove
```

#### 4. Test

```bash
skynet targets
skynet check example
skynet check example recreate
skynet run example deploy
```

### Example: adding a role with task-specific actions

For a role like:

```yaml
- name: Include Backup role
  ansible.builtin.include_role:
    name: backup
  tags:
    - backup
    - backup_config
    - backup_run
    - backup_prune
```

Add this to `role_tag()`:

```bash
backup:deploy)    echo "backup" ;;
backup:config)    echo "backup_config" ;;
backup:run)       echo "backup_run" ;;
backup:prune)     echo "backup_prune" ;;
```

Add this to `print_targets()`:

```text
  backup:
    deploy -> backup
    config -> backup_config
    run    -> backup_run
    prune  -> backup_prune
```

Then use:

```bash
skynet check backup config
skynet run backup run
skynet run backup prune
```

### Avoiding tag confusion

If the command is for a catalog service, use the service command style:

```bash
skynet check authelia
skynet recreate plex
skynet update all
```

If the command is for a role or task group, use the role/action style:

```bash
skynet check ubuntu sysctl
skynet run docker swarm
skynet run infisical-podman recreate
```

If the wrapper does not expose a target yet, use `raw` temporarily:

```bash
skynet raw --check --diff --tags some_new_tag
```

Then add a proper role/action mapping later if the tag becomes part of regular workflow.

### Maintenance checklist

When adding a new role/action target:

* Add or confirm the Ansible tag exists in `playbook.yml` or the relevant role/tasks.
* Add the mapping to `role_tag()`.
* Add the target documentation to `print_targets()`.
* Run `skynet targets`.
* Run `skynet check <target> [action]`.
* Run `skynet lint`.
* Run `skynet doctor`.
* Run `skynet check all` if the change affects shared playbook logic.

## Adding new service tags

Service tags are defined in the relevant service variable file under:

```text
ansible/group_vars/all/services/
```

For a single-target service:

```yaml
example:
  enabled: true
  runtime: docker
  tags: [apps, example]
```

For a multi-target service:

```yaml
example:
  enabled: true
  runtime: docker
  tags: [apps, example]

  targets:
    main:
      enabled: true
      tags: [example_main]

    worker:
      enabled: true
      tags: [example_worker]
```

Then check tag discovery:

```bash
skynet tags
```

Expected selectors:

```text
example
apps
example_main
example_worker
```

Use service-level tags for broad selection and target-level tags for selecting one specific target.

Examples:

```bash
skynet check example
skynet check example_main
skynet check example_worker
```

Disabled services and disabled targets are skipped by `skynet tags`:

```yaml
example:
  enabled: false
  tags: [apps, example]
```

```yaml
example:
  enabled: true
  tags: [apps, example]

  targets:
    main:
      enabled: true
      tags: [example_main]

    worker:
      enabled: false
      tags: [example_worker]
```
