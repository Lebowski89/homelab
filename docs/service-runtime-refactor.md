# Service runtime refactor

## Runtime-neutral architecture

Service orchestration now has five responsibility boundaries:

1. `service_catalog` loads definitions, selects and resolves targets with the canonical base-plus-target merge, preserves tag/enabled selection, and chooses `docker` or `podman` (defaulting legacy definitions to Docker).
2. The globally ordered dispatch materializes one selected service at a time on its dispatch host, runs the `service_common` Infisical/environment preflight exactly once, and snapshots the outputs into a host-local context owned by that service.
3. `service_prepare` validates explicitly declared application handlers and owns application preparation. It receives one current-service context and returns template variables, generated secret values, value-free generated secret declarations, and runtime/bootstrap requests as separate outputs. A narrow selected-runtime executor may run short-lived Docker or Podman containers solely for preparation; it always removes them before deployed-service rendering and lifecycle.
4. `service_common` validates and retrieves runtime-neutral Infisical values, resolves canonical environment values, prepares paths, copies static assets, renders application templates, manages shared Traefik dynamic files, and prepares PostgreSQL databases. It does not choose a runtime, contain application handlers, or create runtime resources.
5. `docker_services` and `podman_services` receive the concrete service and its explicit common context. Docker retains Compose/Swarm and batched stack deployment; Podman retains Quadlets and immediate per-service lifecycle operations. Both retain native secrets and deployed-service lifecycle.

```text
lightweight catalog selection
  -> selective host-local materialization
  -> common Infisical/environment preflight
  -> non-mutating application validation
  -> selected runtime adapter
  -> runtime cleanup
  -> application secret generation
  -> native secret materialization
  -> application template derivation
  -> common files and integrations
  -> application configuration/bootstrap
  -> runtime rendering and lifecycle
```

Docker continues to build Compose state inside the selected-service loop and deploy all accumulated stacks after the loop. Podman continues to handle each selected service immediately. Both adapters receive the same catalog-resolved configuration; neither adapter expands targets independently.

The canonical target merge recursively combines mappings, appends ordinary additive lists with append-rp semantics, removes exact duplicates, and lets target scalars override base scalars. `command`, `entrypoint`, and `healthcheck.test` replace their base lists. Target `runtime` overrides the base runtime, base and target `enabled` values both participate in selection, and `targets` is removed from the resolved configuration before adapter dispatch. The legacy `docker_services_merge_target` filter remains only as a compatibility wrapper around this catalog-owned implementation.

## Common role interface

The required context is explicit: `service_common_name`, `service_common_runtime`, `service_common_action`, `service_common_service`, `service_common_target_hosts`, and `service_common_controller_host`. Ownership, host-specific ownership defaults, application template variables, and Traefik location/zone settings are optional adapter inputs with safe defaults. The canonical service-host contract resolves `services_controller_host` from the validated singleton `tags_ansible_manager` inventory group and `services_storage_host` from `device_roles_storage`. `services_plex_host` remains an explicit value because NetBox does not yet expose a unique Plex role or tag, and `services_log_root` remains an explicit path. The controller is then passed as `service_catalog_controller_host` at the orchestration boundary; common preflight and Podman routing have no Docker-prefixed manager dependency.

Docker compatibility aliases flow in one direction from this canonical contract: `services_controller_host` to `docker_services_primary_manager`, `services_plex_host` to `docker_services_plex_host`, `services_storage_host` to `docker_services_unraid_host`, and `services_log_root` to `docker_services_log_root`. The aliases remain centralized at early orchestration and the Docker dispatch boundary for existing adapter and legacy-role consumers. They can be removed after those consumers accept the canonical inputs directly. Service definitions use only the neutral names.

The common role never derives target topology from Docker fields. Docker passes `docker_services_fs_hosts_effective`; Podman passes its selected inventory host after translating `host_paths` to the existing portable `paths` preparation input.

The focused Infisical entry point accepts `service_common_infisical_secrets_map`, `service_common_infisical_lookup_params`, `service_common_infisical_fail_on_empty`, and `service_common_environment`. For every service it resets and separately returns `service_common_infisical_config` (normalized lookup declarations and policy), `service_common_infisical_values` (all fetched values keyed by `var`), value-free `service_common_secret_declarations`, and the final scalar `service_common_resolved_environment`. Lookup-only entries have no `secret` mapping and can feed environments or shared configuration without creating a runtime secret. An Infisical lookup may declare an optional non-empty `check_mode_value`; check mode uses that declaration-owned stand-in when present and otherwise uses `__CHECK_MODE_REDACTED_INFISICAL_<var>__`. This metadata is never sent to Infisical and does not affect live resolution. Check mode validates the complete declaration and environment graph without lookup or materialization, so downstream configuration shape remains testable.

The ordered dispatcher stores these outputs in `service_catalog_common_context` with the service name, optional target, runtime, dispatch host, normalized lookup configuration, resolved environment, complete lookup values, and value-free native-secret declarations. It resets and validates that context before every adapter invocation. The lookup may execute on the configured controller, but the resulting facts and context remain owned by the original dispatch host. A failed declaration, lookup, empty-value policy, or environment resolution stops routing before Docker cleanup, Podman rendering, or native-secret mutation.

Shared Traefik files use `<service-name>-dynamic.yml`. A successful render removes the distinct legacy Podman `<service-name>.yml`; removal deletes both names idempotently. Explicit `backend_host` is resolved before any inventory lookup, while `backend_host_inventory` resolves `local_ip` only when needed. Thus n8n resolves its host backend to the n8n VM address on port 5678 without a duplicate runtime-specific Traefik definition.

## Deliberately retained runtime responsibilities

`docker_services` retains schema compatibility, deploy-host calculation, cleanup, Compose construction and filters, labels, ports, volumes, Docker secrets, Swarm configs, stack accumulation/deployment, and image drift.

`podman_services` retains exact-image and UID/GID validation, dedicated-network validation, Podman secrets and replacement policy, images, Quadlet rendering, generated systemd units, lifecycle operations, and image drift.

Drift email remains Docker-owned because it consumes the Docker image-drift accumulator and imports the Docker notification task. Its `docker_services_drift_email_*` variables, including the existing Docker-specific subject, are deliberately not migrated in this phase.

Infisical declaration validation, retrieval, empty-value enforcement, and canonical environment resolution are exclusively common-owned. Runtime adapters do not invoke the Infisical entry point and do not receive lookup paths, projects, environments, or credentials. Docker snapshots the context values, environment, and declarations it needs, then owns Docker secret selection, Swarm secrets, and protected standalone secret files. Podman snapshots the same common interfaces, then owns `containers.podman.podman_secret`, secret replacement policy, mount metadata, and Quadlet rendering. Both adapters keep native-secret materialization and permanent runtime state outside `service_common` and `service_prepare`.

PostgreSQL database preparation is runtime-neutral. After common Infisical resolution and before runtime rendering or lifecycle, `service_common` validates the canonical `postgres` declaration and idempotently ensures each declared database exists with `community.postgresql.postgresql_db state=present`. Database operations are delegated to `service_common_controller_host` and use the declared `user_var` and `password_var` from `service_common_infisical_values`. An explicit `host` bypasses inventory lookup; otherwise `host_inventory` defaults to the controller and resolves `local_ip` from only that inventory host. The former Docker-only Infisical `HOST` and `PORT` lookups were intentionally removed: addressing now comes from `postgres.host`, or `postgres.host_inventory` and the selected inventory host `local_ip`, while `postgres.port` defaults to `5432`. Docker and Podman secret materialization remain adapter-owned and are not part of database preparation.

Check mode validates Infisical declarations and the complete PostgreSQL schema, credential references, inventory host, and resolved address without fetching secrets or connecting to PostgreSQL. It reports only database names, host/inventory identity, and port. Temporary application containers, explicit bootstrap operations, and secret-bearing common templates are skipped, while paths, copies, non-sensitive templates, PostgreSQL intent, and Traefik structure remain checkable.

## Runtime-neutral container host inventory

Container ownership and storage defaults use the canonical inventory variables `container_host_puid`, `container_host_pgid`, `container_host_appdata_root`, and `container_host_data_root`. NetBox remains authoritative. The NetBox inventory composition prefers custom fields with those canonical names, falls back to the corresponding `docker_host_*` custom fields when a canonical field is missing or empty, and omits a value when neither field is present. The legacy composed variables remain available during the compatibility window.

Before service definitions are materialized, each inventory host publishes one runtime-neutral `container_host_defaults` mapping containing the effective `puid`, `pgid`, `appdata_root`, and `data_root` values. This also publishes canonical inventory facts for static inventories that still define only the legacy names. Explicit service values override these host defaults, and explicit target values override inherited base values through the canonical target merge. Docker and Podman snapshot the same host-local mapping for common filesystem preparation; no adapter-specific fallback is evaluated inside `service_common`.

Human-maintained service definitions now reference only the canonical `container_host_*` names for generic container ownership and storage. Existing NetBox and static-inventory `docker_host_*` inputs remain supported until the live NetBox custom fields have been created and populated and external consumers have migrated. Creating or migrating those live custom fields is deliberately deferred; this repository change does not assert that they already exist. The Terraform NetBox declarations and samples therefore continue to describe the legacy fields for now, and removing that compatibility boundary requires a separate inventory migration.

## Application-specific preparation

Each selected service declares an optional `application_prepare.handler`. The handler receives the concrete service, operation, resolved environment, current lookup values, value-free declarations, controller host, filesystem hosts, and host defaults. Validation resets all outputs before any runtime cleanup. Secret values are never placed in declarations.

| Application | Application-owned work | Runtime-owned compatibility boundary |
| --- | --- | --- |
| qBittorrent | Validates the downloads/seeds password contract and derives the PBKDF2 template value before common templates. | None; the hash task is runtime-neutral and is available to either adapter. |
| Vaultwarden | Reads or creates the persistent Argon2 admin token and returns its value separately from its canonical declaration. | Docker or Podman materializes the resulting immutable native secret. |
| Authelia | Validates the password/storage-key contract, generates session/JWT values, and derives the user hash with a selected-runtime temporary container. Values and value-free declarations remain separate. | Docker or Podman materializes the generated immutable native secrets. The canonical Infisical storage-key declaration remains separate and is materialized once through the normal adapter path. |
| Plex | Validates the explicit bootstrap declaration; token, claim, and preference handling is application-owned. | `media_nfs` is a canonical managed Compose volume. Plex API/login/claim work runs only with the explicit `bootstrap` operation. This workflow remains Docker-only. |
| Bazarr | Validates all required and paired credentials before cleanup, starts a selected-runtime temporary container only when `config.yaml` is absent, and mutates the configuration after common paths exist. | The Docker or Podman executor guarantees temporary-container cleanup; deployed lifecycle remains adapter-owned. |
| NZBHydra2 | Validates required and optional credential pairs before cleanup, starts a selected-runtime temporary container only when `nzbhydra.yml` is absent, mutates the generated YAML, and verifies the final schema. | The Docker or Podman executor guarantees temporary-container cleanup; deployed lifecycle remains adapter-owned. |

Check mode runs declaration, handler, credential-reference, and bootstrap-contract validation. It does not perform Infisical lookups, runtime cleanup, secret generation/materialization, temporary container work, Plex API requests, application configuration mutation, or runtime lifecycle changes.

## Canonical portable service and secret schema

The Docker-shaped top-level service fields are the canonical portable schema. Phase 1 maps them to the existing Podman internal structure. Every base service now declares its runtime explicitly: existing Docker services use `runtime: docker`, while n8n selects Podman with `runtime: podman`. The missing-runtime Docker default remains as transitional compatibility for external or legacy declarations. Portable fields include `image`, numeric `user: UID:GID`, `environment`, `deploy.host`, canonical ports and volumes, `paths`, security fields, `healthcheck`, `infisical`, `postgres`, and `traefik`.

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

Repository service definitions now use only canonical Infisical lookup declarations, typed environment references, and canonical value-free secret declarations. The runtime-specific `secrets_map[].docker_secret` and Podman lookup metadata, duplicated lookup/materialization declarations, and exact whole-value `__INFISICAL__:var` placeholder have been removed rather than retained as dormant compatibility paths. Unsupported legacy lookup fields fail validation. Existing Docker top-level `secrets` remains available only for runtime-generated or externally managed Docker secrets, and existing Docker `env_file` rendering is unchanged.

`service_common` owns lookup and environment validation, lookup normalization, value retrieval, empty-value enforcement, and final scalar environment resolution. Docker owns `community.docker.docker_secret`, protected standalone files, and Compose/Swarm attachment. Podman owns `containers.podman.podman_secret`, replacement policy, and Quadlet `Secret=` lines.

For Docker Swarm, canonical targets must be directly beneath `/run/secrets`; the adapter translates the absolute path to Swarm's filename target and uses long syntax when target or UID/GID/mode metadata requires it. Arbitrary canonical Swarm targets are rejected. Standalone Docker writes a protected host file and bind-mounts it at the canonical absolute target, applying canonical file ownership/mode when provided. Legacy Docker string attachments keep their previous render form.

Podman-only network and systemd lifecycle policy belongs under `runtime_options.podman`. Those options are ignored by Docker Compose. Changing `runtime` is a schema-level choice, not installation: the destination host must already have the selected runtime and supported version installed.

Static tests prove normalized portable-field equivalence and render structure; they do not prove live Docker/Podman behavioral parity. The n8n proof renders its trusted-address `host_ip` bind through both the Docker standalone and Podman adapters; Docker Swarm rejects `host_ip` explicitly. Swarm-only networks, configs, placement, replicas, application-specific preparation, and runtime installation remain adapter or operator concerns.

Inventory topology and host identity remain unchanged. NetBox remains authoritative, services continue to resolve existing `local_ip`, hostnames, `deploy.host`, and Traefik inventory references, and no canonical address is hard-coded.


## Remaining sequence

1. Replace the remaining explicit Docker-only Plex bootstrap boundary only when equivalent Podman API/bootstrap behavior is intentionally implemented.
2. Migrate additional portable runtime behavior one service at a time, proving equivalent common configuration plus runtime-specific Compose or Quadlet output.
