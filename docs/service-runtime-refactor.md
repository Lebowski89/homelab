# Service runtime refactor

The complete author-facing schema lives in the
[service-definition option reference](../ansible/group_vars/all/services/README.md);
this document explains ownership and architecture.

## Runtime-neutral architecture

Service orchestration now has five responsibility boundaries:

1. `service_catalog` loads definitions, requires every base service to declare `runtime: docker` or `runtime: podman`, selects and resolves targets with the canonical base-plus-target merge, and preserves tag/enabled selection. Targets inherit the validated base runtime and may explicitly override it with another supported runtime.
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

The canonical target merge recursively combines mappings, appends ordinary additive lists with append-rp semantics, removes exact duplicates, and lets target scalars override base scalars. `command`, `entrypoint`, and `healthcheck.test` replace their base lists. Target `runtime` overrides the base runtime, base and target `enabled` values both participate in selection, and `targets` is removed from the resolved configuration before adapter dispatch. `service_catalog_merge_target` is the sole target merger; runtime adapters do not expose or apply their own target-merge compatibility paths.

## Common role interface

The required context is explicit: `service_common_name`, `service_common_runtime`, `service_common_action`, `service_common_service`, `service_common_target_hosts`, and `service_common_controller_host`. Ownership, host-specific ownership defaults, application template variables, and Traefik location/zone settings are optional adapter inputs with safe defaults. The canonical service-host contract resolves `services_controller_host` from the validated singleton `tags_ansible_manager` inventory group and `services_storage_host` from `device_roles_storage`. `services_plex_host` remains an explicit value because NetBox does not yet expose a unique Plex role or tag, and `services_log_root` remains an explicit path. The controller is then passed as `service_catalog_controller_host` at the orchestration boundary; common preflight and Podman routing have no Docker-prefixed manager dependency.

The remaining Docker compatibility alias flows in one direction from this canonical contract: `services_controller_host` to `docker_services_primary_manager`. It remains centralized at early orchestration and the Docker dispatch boundary because the Docker adapter still uses it for manager-owned stack and drift state. Runtime-neutral roles, including PostgreSQL, consume `services_*` directly. The unused `docker_services_plex_host`, `docker_services_unraid_host`, and `docker_services_log_root` Ansible aliases have been removed. Service definitions use neutral names for host-variable references. Existing Swarm placement constraints and host label declarations deliberately retain literal `docker_services_primary_manager`, `docker_services_plex_host`, and `docker_services_unraid_host` node-label values because those strings identify current Docker node labels rather than Ansible variables.

The common role never derives target topology from Docker fields. Docker passes `docker_services_fs_hosts_effective`; Podman passes its selected inventory host after translating `host_paths` to the existing portable `paths` preparation input.

The focused Infisical entry point accepts `service_common_infisical_secrets_map`, `service_common_infisical_lookup_params`, `service_common_infisical_fail_on_empty`, and `service_common_environment`. For every service it resets and separately returns `service_common_infisical_config` (normalized lookup declarations and policy), `service_common_infisical_values` (all fetched values keyed by `var`), value-free `service_common_secret_declarations`, and the final scalar `service_common_resolved_environment`. Lookup-only entries have no `secret` mapping and can feed environments or shared configuration without creating a runtime secret. `fail_on_empty` defaults to true, so missing or empty fetched values fail unless a service deliberately opts out with false. An Infisical lookup may declare an optional non-empty `check_mode_value` only when downstream validation needs a specific safe shape; check mode uses that stand-in when present and otherwise uses `__CHECK_MODE_REDACTED_INFISICAL_<var>__`. This metadata is never sent to Infisical and does not affect live resolution. Check mode validates the complete declaration and environment graph without lookup or materialization, so downstream configuration shape remains testable.

The ordered dispatcher stores these outputs in `service_catalog_common_context` with the service name, optional target, runtime, dispatch host, normalized lookup configuration, resolved environment, complete lookup values, and value-free native-secret declarations. It resets and validates that context before every adapter invocation. The lookup may execute on the configured controller, but the resulting facts and context remain owned by the original dispatch host. A failed declaration, lookup, empty-value policy, or environment resolution stops routing before Docker cleanup, Podman rendering, or native-secret mutation.

Shared Traefik files use `<service-name>-dynamic.yml`. A successful render removes the distinct legacy Podman `<service-name>.yml`; removal deletes both names idempotently. Explicit `backend_host` is resolved before any inventory lookup, while `backend_host_inventory` resolves `local_ip` only when needed. Thus n8n resolves to its VM on port 5678 and Adminer resolves to the controller host on port 18080 without runtime-specific Traefik definitions.

## Deliberately retained runtime responsibilities

`docker_services` retains schema compatibility, deploy-host calculation, cleanup, Compose construction and filters, labels, ports, volumes, Docker secrets, Swarm configs, stack accumulation/deployment, and image drift.

`podman_services` retains exact-image and UID/GID validation, dedicated-network validation, Podman secrets and canonical policy translation, images, Quadlet rendering, generated systemd units, lifecycle operations, and image drift.

Drift email remains Docker-owned because it consumes the Docker image-drift accumulator and imports the Docker notification task. Its `docker_services_drift_email_*` variables, including the existing Docker-specific subject, are deliberately not migrated in this phase.

Infisical declaration validation, retrieval, empty-value enforcement, and canonical environment resolution are exclusively common-owned. Runtime adapters do not invoke the Infisical entry point and do not receive lookup paths, projects, environments, or credentials. Docker snapshots the context values, environment, and declarations it needs, then owns Docker secret selection, Swarm secrets, and protected standalone secret files. Podman snapshots the same common interfaces, then owns `containers.podman.podman_secret`, secret policy translation, mount metadata, and Quadlet rendering. Both adapters keep native-secret materialization and permanent runtime state outside `service_common` and `service_prepare`.

PostgreSQL database preparation is runtime-neutral. After common Infisical resolution and before runtime rendering or lifecycle, `service_common` validates the canonical `postgres` declaration and idempotently ensures each declared database exists with `community.postgresql.postgresql_db state=present`. Database operations are delegated to `service_common_controller_host` and use the declared `user_var` and `password_var` from `service_common_infisical_values`. An explicit `host` bypasses inventory lookup; otherwise `host_inventory` defaults to the controller and resolves `local_ip` from only that inventory host. The former Docker-only Infisical `HOST` and `PORT` lookups were intentionally removed: addressing now comes from `postgres.host`, or `postgres.host_inventory` and the selected inventory host `local_ip`, while `postgres.port` defaults to `5432`. Docker and Podman secret materialization remain adapter-owned and are not part of database preparation.

Check mode validates Infisical declarations and the complete PostgreSQL schema, credential references, inventory host, and resolved address without fetching secrets or connecting to PostgreSQL. It reports only database names, host/inventory identity, and port. Temporary application containers, explicit bootstrap operations, and secret-bearing common templates are skipped, while paths, copies, non-sensitive templates, PostgreSQL intent, and Traefik structure remain checkable.

## Runtime-neutral container host inventory

Container ownership and storage defaults use the canonical inventory variables `container_host_puid`, `container_host_pgid`, `container_host_appdata_root`, and `container_host_data_root`. NetBox remains authoritative. The NetBox inventory composition reads custom fields with those canonical names directly and omits a value when its canonical field is absent or empty.

Before service definitions are materialized, each inventory host publishes one runtime-neutral `container_host_defaults` mapping containing the effective `puid`, `pgid`, `appdata_root`, and `data_root` values. Explicit service values override these host defaults, and explicit target values override inherited base values through the canonical target merge. Docker and Podman snapshot the same host-local mapping for common filesystem preparation; no adapter-specific fallback is evaluated inside `service_common`.

Human-maintained service definitions reference only the canonical `container_host_*` names for generic container ownership and storage. The four canonical Text custom fields on `dcim.device` replace the former Docker-named fields while preserving their working value representation. OpenTofu owns the field definitions and host values, NetBox remains the source of truth, and Ansible dynamic inventory consumes them. Runtime selection stays in each service definition, and application-specific storage stays in service configuration rather than becoming generic host metadata.

## Application-specific preparation

Each selected service declares an optional `application_prepare.handler`. The handler receives the concrete service, operation, resolved environment, current lookup values, value-free declarations, controller host, filesystem hosts, and host defaults. Validation resets all outputs before any runtime cleanup. Secret values are never placed in declarations.

| Application | Application-owned work | Runtime-owned compatibility boundary |
| --- | --- | --- |
| qBittorrent | Validates the downloads/seeds password contract and derives the PBKDF2 template value before common templates. | None; the hash task is runtime-neutral and is available to either adapter. |
| Vaultwarden | Reads or creates the persistent Argon2 admin token and returns its value separately from its canonical declaration. | Docker or Podman materializes the resulting preserve-policy native secret. |
| Authelia | Validates the password/storage-key contract, generates session/JWT values, and derives the user hash with a selected-runtime temporary container. Values and value-free declarations remain separate. | Docker or Podman materializes the generated preserve-policy native secrets. The canonical Infisical storage-key declaration remains separate and is materialized once through the normal adapter path. |
| Plex | Validates the explicit bootstrap declaration; token, claim, and preference handling is application-owned. | `media_nfs` is a canonical managed Compose volume. Plex API/login/claim work runs only with the explicit `bootstrap` operation. This workflow remains Docker-only. |
| Bazarr | Validates all required and paired credentials before cleanup, starts a selected-runtime temporary container only when `config.yaml` is absent, and mutates the configuration after common paths exist. | The Docker or Podman executor guarantees temporary-container cleanup; deployed lifecycle remains adapter-owned. |
| NZBHydra2 | Validates required and optional credential pairs before cleanup, starts a selected-runtime temporary container only when `nzbhydra.yml` is absent, mutates the generated YAML, and verifies the final schema. | The Docker or Podman executor guarantees temporary-container cleanup; deployed lifecycle remains adapter-owned. |

Check mode runs declaration, handler, credential-reference, and bootstrap-contract validation. It does not perform Infisical lookups, runtime cleanup, secret generation/materialization, temporary container work, Plex API requests, application configuration mutation, or runtime lifecycle changes.

## Canonical portable service and secret schema

The Docker-shaped top-level service fields are the canonical portable schema. The Podman adapter maps them to its internal Quadlet structure. Every base service declares its runtime explicitly: existing Docker services use `runtime: docker`, while n8n, Adminer, The Lounge, and Homepage select Podman with `runtime: podman`. A missing or unsupported base runtime fails catalog validation; there is no implicit Docker default. Portable fields include `image`, numeric `user: UID:GID`, `environment`, `deploy.host`, canonical ports and volumes, `paths`, security fields, `healthcheck`, `infisical`, `postgres`, and `traefik`.

Podman additionally owns `deploy.execution`. Omission preserves rootful system
Quadlets. `mode: rootless` requires a dedicated `host_user` and selects that
account's user Quadlet directory, Podman storage, and user-systemd manager. The
host execution account is independent of the container's top-level numeric
`user`. Adminer uses the mount-free rootless subset. The Lounge adds a
validated bind-backed subset: an exact `/opt` path, a matching bind source,
adapter-owned recursive ownership, and an explicit `keep-id` mapping for the
application UID/GID. Homepage additionally exercises confined common managed
files: copy and template destinations must be normalized absolute proper
descendants of a declared bind source, explicit owner/group overrides are
forbidden, and extra `paths` entries may only remove descendants of that bind
tree. The common role therefore creates those files as the dedicated execution
account before the adapter's final recursive ownership reconciliation; the
adapter does not recursively change modes. Named volumes, tmpfs, native
secrets, and application-preparation fields remain unsupported for rootless
execution and fail before host mutation. This is deliberately not general
rootless filesystem parity outside declared bind trees.

Canonical does not mean every Docker-owned field is portable. The Podman adapter
validates the complete top-level mapping and rejects unknown or unimplemented
fields instead of discarding them. Changing only `runtime` is invalid while
Docker-only behavior remains. Podman requires an explicit `deploy.type` to be
`container` and rejects Swarm `profile` and `constraints`; only the
single-instance `replicated`/`replicas: 1` form is portable. An explicit
canonical `name` consistently controls the Podman container, `.container`,
`.env`, and derived `.service` names, while omitted base and target names keep
the existing catalog and base-target defaults.

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
        update_policy: reconcile
    - var: template_only_token
      path: /App
      name: TEMPLATE_TOKEN
```

`secret.name` is a runtime resource name; `target` defaults to `/run/secrets/<name>` and must be absolute; UID/GID are numeric strings; and mode is a quoted four-digit octal string. `update_policy` accepts exactly `preserve` or `reconcile` and defaults to `preserve`; deprecated secret-level `runtime_options` fail with migration guidance. Values are never copied into declaration metadata.

Repository service definitions now use only canonical Infisical lookup declarations, typed environment references, and canonical value-free secret declarations. The runtime-specific `secrets_map[].docker_secret` and Podman lookup metadata, duplicated lookup/materialization declarations, and exact whole-value `__INFISICAL__:var` placeholder have been removed rather than retained as dormant compatibility paths. Unsupported legacy lookup fields fail validation. Existing Docker top-level `secrets` remains available only for runtime-generated or externally managed Docker secrets, and existing Docker `env_file` rendering is unchanged.

`service_common` owns lookup and environment validation, lookup normalization, value retrieval, empty-value enforcement, and canonical secret policy validation. Docker owns `community.docker.docker_secret`, protected standalone files, and Compose/Swarm attachment. Podman owns `containers.podman.podman_secret`, policy translation, and Quadlet `Secret=` lines.

For Docker Swarm, canonical targets must be directly beneath `/run/secrets`; the adapter translates the absolute path to Swarm's filename target and uses long syntax when target or UID/GID/mode metadata requires it. `preserve` inspects the exact secret and creates it only when missing. `reconcile` does the same during deploy/bootstrap, while update/recreate invokes the module's content-aware replacement path for Ansible-managed secrets; unmanaged existing secrets are rejected rather than silently reported as reconciled. Swarm secret objects are replaced rather than mutated in place, and an in-use replacement failure is surfaced without logging the value. Standalone Docker creates missing protected files without overwriting them under `preserve`; `reconcile` overwrites only on update/recreate, while owner, group, mode, and file-type verification remain enforced. Legacy Docker string attachments keep their previous render form.

Podman maps `preserve` to `force: false` and `skip_existing: true` for every action. It maps `reconcile` to `force: true` and `skip_existing: false` only during update/recreate. Because Podman cannot compare stored secret contents, this reconciliation recreates the native secret and relies on the existing failure-aware service restart path. Both adapters leave runtime-native secret removal under their existing adapter-owned remove behavior.

`named_networks` is the canonical network location for both adapters. Podman
currently accepts one entry: `external: false` is role-managed and
`external: true` is attached without lifecycle ownership and must already exist
in the destination host Podman network store. Live deploy/update/recreate/
bootstrap checks the exact validated name before cleanup, secret materialization,
rendering, or lifecycle work; check mode and remove make no external-network
preflight call. Podman-only systemd
policy uses the top-level `systemd` mapping and is rejected for an effective
Docker service. Service-level `runtime_options.podman.network` and
`runtime_options.podman.systemd` are retired. Secret-level runtime options are also retired; `secret.update_policy` is the single runtime-neutral lifecycle contract consumed by both adapters.
Docker and Podman networks with the same name are still separate resources.
Managed Podman networks remain preferred for isolated services; cross-runtime
communication uses published host endpoints or another deliberate network path.
Changing `runtime` is a schema-level choice, not installation: the destination
host must already have the selected runtime and supported version installed.

Static tests prove normalized portable-field equivalence and render structure; they do not prove live Docker/Podman behavioral parity. The n8n proof renders its trusted-address `host_ip` bind through both adapters; the Adminer proof covers its managed Podman network and controller-host Traefik endpoint; Docker Swarm rejects `host_ip` explicitly. Swarm-only networks, configs, placement, replicas, application-specific preparation, and runtime installation remain adapter or operator concerns.

Inventory topology and host identity remain unchanged. NetBox remains authoritative, services continue to resolve existing `local_ip`, hostnames, `deploy.host`, and Traefik inventory references, and no canonical address is hard-coded.

## Compatibility closeout audit

Phase 4A audited the refactor's compatibility paths against production tasks, repository service definitions, effective base-plus-target configurations, tests, documentation, and inventory declarations.

| Mechanism | Classification | Producer and consumers |
| --- | --- | --- |
| Docker-prefixed catalog selection and target-merge filters | **Remove now** | The compatibility filters and their tests were the only references. Dispatch already uses `service_catalog_effective`, `service_catalog_select`, and `service_catalog_merge_target`, so the wrappers and their obsolete implicit runtime default were removed. |
| `service_common_secret_values` | **Remove now** | No producer or production consumer remains. The explicit interfaces are `service_common_infisical_values` and value-free `service_common_secret_declarations`. |
| Missing-runtime Docker default | **Remove now** | No implementation path remains. Catalog construction and target merging reject a missing base runtime; stale documentation was corrected. |
| Exact `__INFISICAL__:var` environment placeholder | **Remove now** | No production or service-definition consumer remains. Typed `value_from.infisical` and `value_template` entries are canonical, while tests retain rejection/absence coverage. |
| `secrets_map[].docker_secret`, `secrets_map[].podman_secret`, and old Podman lookup metadata | **Remove now** | Common declaration validation rejects these fields and no repository definition uses them. Canonical `secret` metadata remains runtime-neutral. |
| Nested Podman service input and singular top-level Podman `network` | **Remove now** | Only transition tests used the old `container`, `env`, `host_paths`, legacy volume, and singular network forms. The adapter now accepts canonical `named_networks` and top-level `systemd`; secret lifecycle is expressed only through runtime-neutral `secret.update_policy`. |
| Top-level `secrets` name attachments | **Retain intentionally** | These are not lookup metadata. Docker services and application preparation use them for generated or externally managed native secrets; Podman accepts only value-free names. |
| Neutral-to-Docker `docker_services_primary_manager` host alias | **Retain intentionally** | Docker stack accumulation/deployment and Docker image-drift state still use this manager alias. PostgreSQL and other runtime-neutral roles consume `services_controller_host`; the other unused Docker host aliases were removed. |
| Literal Docker Swarm placement label values | **Retain intentionally** | Current service definitions and host label declarations use `docker_services_primary_manager`, `docker_services_plex_host`, and `docker_services_unraid_host`. Renaming them requires a node-label migration. |
| Docker-specific drift email and Plex bootstrap/API path | **Retain intentionally** | Both have deliberate Docker-owned consumers and are not portable common preparation. |
| Application-preparation entry points under `docker_services` | **Remove now** | No obsolete entry point or wrapper remains after `service_prepare`; runtime adapters consume its explicit outputs and retain only native materialization/lifecycle work. |

Repository tests and documentation are not treated as production consumers. Negative tests remain where they prove that removed lookup metadata and placeholders fail or are absent; compatibility-only tests for removed executable paths were deleted.


## Remaining sequence

1. Replace the remaining explicit Docker-only Plex bootstrap boundary only when equivalent Podman API/bootstrap behavior is intentionally implemented.
2. Migrate additional portable runtime behavior one service at a time, proving equivalent common configuration plus runtime-specific Compose or Quadlet output.
