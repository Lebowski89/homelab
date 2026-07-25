# Service runtime refactor

## Transitional architecture

Service orchestration now has three responsibility boundaries:

1. `service_catalog` loads definitions, expands targets, preserves tag/enabled selection, and chooses `docker` or `podman` (defaulting legacy definitions to Docker).
2. `service_common` prepares paths, copies static assets, renders application templates, manages shared Traefik dynamic files, and validates and retrieves runtime-neutral Infisical values. It receives an already-normalized service and explicit target/controller hosts. It does not choose a runtime or create runtime resources.
3. `docker_services` and `podman_services` remain runtime adapters. Docker retains Compose/Swarm and batched stack deployment; Podman retains Quadlets and immediate per-service lifecycle operations.

During this transition the runtime roles call named `service_common` entry points directly. A dispatcher is intentionally deferred. The desired eventual order is:

```text
service_catalog
  -> shared preparation
  -> selected runtime adapter
  -> shared integrations
```

Docker continues to build Compose state inside the selected-service loop and deploy all accumulated stacks after the loop. Podman continues to handle each selected service immediately.

## Common role interface

The required context is explicit: `service_common_name`, `service_common_runtime`, `service_common_action`, `service_common_service`, `service_common_target_hosts`, and `service_common_controller_host`. Ownership, host-specific ownership defaults, application template variables, and Traefik location/zone settings are optional adapter inputs with safe defaults.

The common role never derives target topology from Docker fields. Docker passes `docker_services_fs_hosts_effective`; Podman passes its selected inventory host after translating `host_paths` to the existing portable `paths` preparation input.

The focused Infisical entry point accepts `service_common_infisical_secrets_map`, `service_common_infisical_lookup_params`, `service_common_infisical_fail_on_empty`, and `service_common_environment`, plus adapter-supplied legacy declarations during the compatibility window. For every service it resets and separately returns `service_common_infisical_config` (normalized lookup declarations and policy), `service_common_infisical_values` (all fetched values keyed by `var`), value-free `service_common_secret_declarations`, and the final scalar `service_common_resolved_environment`. Lookup-only entries have no `secret` mapping and can feed environments or shared configuration without creating a runtime secret. An Infisical lookup may declare an optional non-empty `check_mode_value`; check mode uses that declaration-owned stand-in when present and otherwise uses `__CHECK_MODE_REDACTED_INFISICAL_<var>__`. This metadata is never sent to Infisical and does not affect live resolution. Check mode validates the complete declaration and environment graph without lookup or materialization, so downstream configuration shape remains testable.


Shared Traefik files use `<service-name>-dynamic.yml`. A successful render removes the distinct legacy Podman `<service-name>.yml`; removal deletes both names idempotently. Explicit `backend_host` is resolved before any inventory lookup, while `backend_host_inventory` resolves `local_ip` only when needed. Thus n8n resolves its host backend to the n8n VM address on port 5678 without a duplicate runtime-specific Traefik definition.

## Deliberately retained runtime responsibilities

`docker_services` retains target/schema compatibility, deploy-host calculation, cleanup, Compose construction and filters, labels, ports, volumes, Docker secrets, Swarm configs, stack accumulation/deployment, image drift, and the application-specific tasks below.

`podman_services` retains exact-image and UID/GID validation, dedicated-network validation, Podman secrets and replacement policy, images, Quadlet rendering, generated systemd units, lifecycle operations, and image drift.

Infisical declaration validation, retrieval, empty-value enforcement, and canonical environment resolution are shared through `service_common_infisical_values` and `service_common_resolved_environment`. The old `service_common_secret_values` name remains only as a temporary internal compatibility alias. Docker recreates its flattened or dictionary compatibility facts after lookup, preserving environment placeholder resolution and deployment-host propagation. Docker still owns Docker secret selection, Swarm secrets, protected standalone secret files, and application bootstraps. Podman still owns `containers.podman.podman_secret`, secret replacement policy, mount metadata, and Quadlet rendering. Both adapters keep runtime materialization outside `service_common`.

PostgreSQL database preparation is runtime-neutral. After common Infisical resolution and before runtime rendering or lifecycle, `service_common` validates the canonical `postgres` declaration and idempotently ensures each declared database exists with `community.postgresql.postgresql_db state=present`. Database operations are delegated to `service_common_controller_host` and use the declared `user_var` and `password_var` from `service_common_infisical_values`. An explicit `host` bypasses inventory lookup; otherwise `host_inventory` defaults to the controller and resolves `local_ip` from only that inventory host. The former Docker-only Infisical `HOST` and `PORT` lookups were intentionally removed: addressing now comes from `postgres.host`, or `postgres.host_inventory` and the selected inventory host `local_ip`, while `postgres.port` defaults to `5432`. Docker and Podman secret materialization remain adapter-owned and are not part of database preparation.

Check mode validates Infisical declarations and the complete PostgreSQL schema, credential references, inventory host, and resolved address without fetching secrets or connecting to PostgreSQL. It reports only database names, host/inventory identity, and port. Docker runtime/application bootstraps and secret-bearing common templates are skipped, while paths, copies, non-sensitive templates, PostgreSQL intent, and Traefik structure remain checkable.

## Application-specific preparation inventory

| Application | Current characteristics | Host and timing | Suggested follow-up |
| --- | --- | --- | --- |
| Authelia | Generates Argon2/random keys with a temporary Docker container, creates Docker secrets, and can require Infisical-backed inputs. | Controller/primary manager; generates missing values and otherwise reconciles secrets. | Keep runtime materialization in Docker; move portable key intent to `service_prepare` only after secret return values are defined. |
| Plex | Discovers or claims a server, obtains a token, and mutates preferences through HTTP/XML flows. Uses claim/token secrets rather than role-owned application assets. | Plex deployment/filesystem host plus controller facts; a mix of first-boot discovery and repeatable preference updates. | Prefer `service_prepare` because remote API lifecycle and first-boot state are larger than common file preparation. |
| qBittorrent | Hashes UI passwords through the custom module; common config templates consume the resulting hashes. | Controller with work delegated to the selected filesystem host; repeatable before template rendering. | A future `service_common/tasks/apps/qbittorrent.yml` can return generic template variables if both runtimes use the same config. |
| Bazarr | Starts a temporary Docker container when configuration is absent, then mutates YAML with API, Arr, subtitle, and PostgreSQL values. | Selected filesystem/deployment host; first-boot generation followed by repeatable mutation. | Use `service_prepare` and separate first-boot generation from idempotent configuration. |
| NZBHydra2 | Inspects/generates application configuration and mutates it with indexer/downloader/API values. | Selected filesystem host; first-boot-sensitive plus repeatable mutations. | Use `service_prepare`; define a runtime-neutral config contract before removing the temporary Docker dependency. |
| Vaultwarden | Generates password/salt/Argon2 material, writes protected local files, and creates a Docker secret. | Selected filesystem host for files and controller for Docker secret materialization; first-boot generation. | Split portable token generation from adapter-owned secret materialization in the dedicated secret refactor. |

These tasks stay in `docker_services` for now. Moving them solely to shrink that role would mix first-boot application orchestration, runtime resources, remote APIs, and common host preparation in one role.

## Canonical portable service and secret schema

The Docker-shaped top-level service fields are the canonical portable schema. Phase 1 maps them to the existing Podman internal structure; n8n is the first migrated service and now selects Podman primarily with `runtime: podman`. Portable fields include `image`, numeric `user: UID:GID`, `environment`, `deploy.host`, canonical ports and volumes, `paths`, security fields, `healthcheck`, `infisical`, `postgres`, and `traefik`.

Canonical environment entries are either scalar literals, a direct Infisical reference, or a narrowly composed template:

```yaml
environment:
  TZ: Australia/Melbourne
  SESSION_TOKEN:
    value_from:
      infisical: application_token
  APPLICATION_URL:
    value_template: "https://app.${cloudflare_zone}:8443/price/$$5"
```

`value_from.infisical` and every `${identifier}` in `value_template` must name a `var` declared in the same service `infisical.secrets_map`. Templates perform only single-pass `${identifier}` substitution; they do not evaluate Jinja, shell syntax, Python formatting, or references contained inside fetched values. `$$` produces one literal dollar sign. The common resolver runs before shared file preparation and runtime rendering, and Docker and Podman replace their initially normalized environment with `service_common_resolved_environment`, so typed mappings never reach Compose, Quadlet, or environment-file serializers.

A materialized secret is declared next to its Infisical lookup:

```yaml
infisical:
  fail_on_empty: true
  secrets_map:
    - var: app_password
      path: /App
      name: PASSWORD
      secret:
        name: app_password_secret
        target: /run/secrets/app_password_secret
        uid: "1000"
        gid: "1000"
        mode: "0400"
        runtime_options:
          podman:
            immutable: false
            replace: true
    - var: template_only_token
      path: /App
      name: TEMPLATE_TOKEN
```

`secret.name` is a runtime resource name; `target` defaults to `/run/secrets/<name>` and must be absolute; UID/GID are numeric strings; and mode is a quoted four-digit octal string. Only strict `immutable` and `replace` booleans are accepted under `secret.runtime_options.podman`, and both cannot be true. Values are never copied into declaration metadata.

Existing Docker `secrets_map[].docker_secret`, Docker top-level `secrets`, and legacy Podman top-level secret entries remain accepted. Docker also retains the exact whole-value `__INFISICAL__:var` environment placeholder as a compatibility adapter for unchanged services; it does not support inline interpolation and runs only after canonical resolution. Existing Docker `env_file` handling is unchanged, and Podman does not implement the magic placeholder. Equivalent canonical and legacy declarations deduplicate; incompatible targets, variables, metadata, lookup coordinates, or policies fail rather than choosing one. Compatibility code is intentionally retained during per-service migration.

`service_common` owns lookup and environment validation, lookup normalization, value retrieval, empty-value enforcement, and final scalar environment resolution. Docker owns `community.docker.docker_secret`, protected standalone files, and Compose/Swarm attachment. Podman owns `containers.podman.podman_secret`, replacement policy, and Quadlet `Secret=` lines.

For Docker Swarm, canonical targets must be directly beneath `/run/secrets`; the adapter translates the absolute path to Swarm's filename target and uses long syntax when target or UID/GID/mode metadata requires it. Arbitrary canonical Swarm targets are rejected. Standalone Docker writes a protected host file and bind-mounts it at the canonical absolute target, applying canonical file ownership/mode when provided. Legacy Docker string attachments keep their previous render form.

Podman-only network and systemd lifecycle policy belongs under `runtime_options.podman`. Those options are ignored by Docker Compose. Changing `runtime` is a schema-level choice, not installation: the destination host must already have the selected runtime and supported version installed.

Static tests prove normalized portable-field equivalence and render structure; they do not prove live Docker/Podman behavioral parity. The n8n proof renders its trusted-address `host_ip` bind through both the Docker standalone and Podman adapters; Docker Swarm rejects `host_ip` explicitly. Swarm-only networks, configs, placement, replicas, application-specific preparation, and runtime installation remain adapter or operator concerns.

Inventory topology and naming are outside Phase 2B. NetBox remains authoritative, services continue to resolve existing `local_ip`, hostnames, `deploy.host`, and Traefik inventory references, and no canonical address is hard-coded. Renaming legacy inventory variables from `docker_host_*` to runtime-neutral `container_host_*` is a separate future compatibility migration, not part of the service declaration refactor.


## Remaining sequence

1. Move suitable application preparation into `service_common/tasks/apps/` or, preferably for lifecycle-heavy applications, a dedicated `service_prepare` role.
2. Add `service_dispatch` only after normalized shared preparation and integration inputs are stable.
3. Migrate additional portable services one at a time, retaining compatibility and proving equivalent common configuration plus runtime-specific Compose or Quadlet output.
