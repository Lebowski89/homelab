## Helpers

This project uses helpers (aka builders) that ready each docker service/stack for deployment. The facts in the service vars are sent through these helpers and the end result is a complete compose file ready to run with everything it needs (with desired settings).

## `compose/`

- `caps.yml`: Adds or replaces Linux capabilities (`cap_add` / `cap_drop`) for a service, with append and unique-append merge modes.
- `command.yml`: Sets a service `command` with normalization for string/list input and optional append semantics when list-based commands are used.
- `configs.yml`: Attaches Docker configs to a service definition.
- `depends_on.yml`: Normalizes and sets service `depends_on` entries.
- `deploy.yml`: Builds the `deploy` section for a service (mode, replicas, resources, constraints, restart/update/rollback policies, labels).
- `devices.yml`: Adds device mappings to a service with append/replace behavior.
- `env_file.yml`: Normalizes and attaches one or more `env_file` entries to a service.
- `environment.yml`: Merges environment variables into a service, with configurable precedence and merge strategy.
- `healthcheck.yml`: Builds and attaches a service `healthcheck` block, including normalized `test` command format.
- `labels.yml`: Merges and assigns labels to a service with precedence and merge controls.
- `ports.yml`: Normalizes port mappings and applies them differently for compose/container vs swarm deploy modes.
- `secrets.yml`: Attaches secrets for swarm mode and converts secret references into bind-mounted secret files for compose/container mode.
- `security_opt.yml`: Adds or replaces `security_opt` entries for a service.
- `service_base.yml`: Creates the baseline service definition (name, image/build, hostname/container name, restart policy, pull policy, and optional metadata).
- `shm.yml`: Sets `shm_size` for a service.
- `stack_networks.yml`: Defines top-level compose networks for a stack and normalizes list/map input.
- `stack_volumes.yml`: Defines top-level compose volumes for a stack and normalizes list/map input.
- `user.yml`: Sets the runtime `user` for a service.
- `validate.yml`: Performs top-level compose validation across all generated services before rendering/deploy.
- `validate_service.yml`: Validates a service object shape (directories, env, compose extras, deploy host, etc.).
- `validate_svc.yml`: Validates normalized service fields (name/image/deploy/environment/ports/etc.) for schema correctness.
- `volumes.yml`: Normalizes, validates, and merges service volume mounts from mapping, list, or legacy inputs.

## `deploy/`

- `deploy_all.yml`: Iterates through all prepared stacks and deploys each one.
- `deploy_one.yml`: Renders stack compose artifacts and deploys a single stack on the effective deploy host.

## `infisical/`

- `distribute.yml`: Copies fetched secret values from a source host into host variables, either from flattened keys or a source dictionary.
- `fetch.yml`: Looks up secrets from Infisical based on a `secrets_map`, outputting flattened vars and/or a dictionary.

## `prep/`

- `cleanup.yml`: Removes existing apps/services for the current deploy mode (compose/container or swarm).
- `cloudflare_creds.yml`: Ensures Cloudflare credentials/zone values exist, fetching from Infisical when needed.
- `cloudflare_dns.yml`: Creates or updates Cloudflare DNS records for a target domain/host.
- `copies.yml`: Copies role-relative files to target destinations on the deploy host.
- `paths.yml`: Ensures directories/files exist with expected ownership, permissions, and state.
- `postgres.yml`: Ensures Postgres credentials/secrets are available and can ping/create requested databases.
- `resolve_env.yml`: Replaces infisical placeholder put in place due to svc facts being loaded before infisical fetch.
- `secrets.yml`: Normalizes secret inputs and materializes Docker secrets (swarm) or secret files (compose/container).
- `swarm_configs.yml`: Creates/removes Docker Swarm configs from inline data or source files/templates.
- `templates.yml`: Renders Jinja templates to destination paths on the deploy host.