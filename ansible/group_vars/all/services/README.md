# Service-definition option reference

This is the authoritative author-facing reference for
`ansible/group_vars/all/services/*.yml`. It documents the schema implemented by
`service_catalog`, `service_common`, `service_prepare`, `docker_services`, and
`podman_services`. Generic Docker Compose or Podman options are not supported
unless they appear here.

The [style guide](../../../../docs/service-definition-style.md) defines the
preferred key order. Ordering is for readability; it does not change behavior.

> [!IMPORTANT]
> Every base service must declare `runtime: docker` or `runtime: podman`. There
> is no implicit Docker default. The destination host must already provide the
> chosen runtime. Podman validates the complete effective declaration: changing only
> `runtime` is invalid while Docker-only or otherwise unsupported fields remain.

## Contents

- [Schema fundamentals](#schema-fundamentals)
- [Defaults at a glance](#defaults-at-a-glance)
- [Identity and process](#identity-and-process)
- [Environment](#environment)
- [Infisical and native secrets](#infisical-and-native-secrets)
- [Connectivity](#connectivity)
- [Filesystem and storage](#filesystem-and-storage)
- [Devices and security](#devices-and-security)
- [Health checks](#health-checks)
- [Traefik](#traefik)
- [PostgreSQL](#postgresql)
- [Deployment and placement](#deployment-and-placement)
- [Podman systemd](#podman-systemd)
- [Application preparation](#application-preparation)
- [Actions and lifecycle](#actions-and-lifecycle)
- [Runtime compatibility](#runtime-compatibility)
- [Examples](#examples)
- [Removed and unsupported fields](#removed-and-unsupported-fields)

## Schema fundamentals

Each file is a YAML mapping. Its top-level key is the catalog name and its value
is the base declaration. A service with `targets` produces one selectable entry
per target; the base is not separately dispatched.

### Catalog and identity options

| Option | Type | Required | Default | Runtime | Owner | Description |
| ------ | ---- | -------- | ------- | ------- | ----- | ----------- |
| `enabled` | Boolean-like | No | `true` | N/A | `service_catalog` | Includes or excludes the base. On a target, both base and target must be enabled. |
| `runtime` | String enum | Yes | None | N/A | `service_catalog` | Exactly `docker` or `podman`. A target inherits it and may override it. |
| `tags` | String or list of strings | No | `[]` | N/A | `service_catalog` | Adds selection tags. The catalog name is always added; a target also gains its target name. Duplicates are removed in first-seen order. |
| `name` | Non-empty resource-name string | No | Base catalog name or base-target role prefix | Both | `docker_services` / `podman_services` | Runtime service/container name. For Podman it consistently names `ContainerName=`, `.container`, `.env`, and the derived `.service`; it does not change catalog selection. |
| `description` | Non-empty string | No | `<name> Podman service` | Podman | `podman_services` | Text rendered as the Quadlet unit description. |
| `stack` | String | No | Effective service name | Docker | `docker_services` | Compose/Swarm project name. Standalone Docker adds its deploy host to the internal stack key. |
| `targets` | Mapping of target names to mappings | No | Absent | N/A | `service_catalog` | Named variants. Target order is selection order; nested `targets` are rejected. |
| `targets.<name>.enabled` | Boolean-like | No | `true` | N/A | `service_catalog` | Enables the target only when the base is also enabled. |
| `targets.<name>.runtime` | String enum | No | Base `runtime` | N/A | `service_catalog` | Changes the adapter for this target. Other fields use the same tables as a base service. |

Catalog booleans accept booleans, `0`/`1`, and case-insensitive
`true`/`false`, `yes`/`no`, and `on`/`off` strings. Prefer YAML booleans.

### Base-plus-target merge

`service_catalog_merge_target` is the only merger used by both adapters.

| Value | Merge behavior |
| ----- | -------------- |
| Mappings | Merge recursively; target leaves override base leaves. |
| Ordinary lists | Append-rp: base entries also present in the target are removed, then target entries are appended. Exact duplicates remain once. |
| Scalars or unlike types | Target replaces base. |
| `command` and `entrypoint` | Target replaces base, including list forms. |
| `healthcheck.test` | Target replaces the inherited test; other health fields merge. |
| `runtime` | Inherited unless explicitly overridden. |
| `targets` | Removed before dispatch. Nested targets are invalid. |

Selection uses lightweight metadata. The chosen configuration is materialized
once on its dispatch host immediately before common preflight and adapter
dispatch, so inventory-derived values resolve in the correct host context.

### Host roles

| Host role | Derivation | Purpose |
| --------- | ---------- | ------- |
| Dispatch host | Docker Swarm: controller/primary manager. Docker standalone: `deploy.host`, else controller. Podman: `deploy.host`, else catalog name. | Owns current-service facts and runs common normalization plus adapter work. |
| Controller host | Orchestration-provided `service_common_controller_host`. | Runs the narrowly delegated Infisical lookup, PostgreSQL calls, Traefik rendering, and manager work without taking ownership of per-service facts. |
| Filesystem hosts | Docker: `deploy.host` may be a host/group/list for Swarm; standalone requires one host. Podman: dispatch host. | Receive paths, copies, and templates. Defaults come from canonical `container_host_*` inventory values. |

## Defaults at a glance

| Omitted value | Kind | Effective behavior |
| ------------- | ---- | ------------------ |
| `enabled` | Schema default | `true`. |
| Target `runtime` | Derived | Required base runtime. |
| `name` | Derived | Catalog/role service name. |
| `infisical.fail_on_empty` | Schema default | `true`; missing/blank live values fail before runtime cleanup. |
| `infisical.secrets_map[].check_mode_value` | Derived | `__CHECK_MODE_REDACTED_INFISICAL_<var>__`. |
| `infisical.secrets_map[].secret.target` | Derived | `/run/secrets/<secret.name>`. |
| `infisical.secrets_map[].secret.update_policy` | Schema default | `preserve`. |
| `postgres.port` | Schema default | `5432`. |
| `postgres.user_var` / `password_var` | Schema default | `postgres_user` / `postgres_pass`. |
| PostgreSQL address | Derived | `host_inventory` becomes the controller and `host` becomes that host's `local_ip`. |
| `deploy.type` | Docker role default | `swarm`. Podman always runs one local Quadlet instance. |
| `deploy.execution.mode` | Podman default | `rootful`. Existing Podman services keep system Quadlets unless they opt into rootless execution. |
| `deploy.mode` / `replicas` | Role default | Docker: `replicated` / `1`; Podman accepts only those explicit values. |
| `deploy.profile` | Docker role default | `none`. Non-`none` profiles are Swarm-only. |
| `paths[].state` | Common default | `directory`. |
| `paths[].owner` / `group` | Derived | Target-host PUID/PGID, then `1000`/`1000`. |
| `paths[].mode` | Adapter default | Docker `0755`; Podman `0750`. |
| `copies[].force` | Common default | `false`. |
| `templates[].mode` / `force` / `no_log` | Common default | `0664` / `true` / `false`. |
| `volumes[].type` / `read_only` | Schema default | `bind` / `false`. |
| `ports[].protocol` | Schema default | `tcp`. Docker Swarm `mode` defaults to `ingress`. |
| Health timings | Adapter default | Docker: `1m`, `15s`, `3`, `30s`; Podman: `30s`, `10s`, `3`, `60s`. |
| Podman `no_new_privileges` | Quadlet default | `true` even when omitted. |
| `systemd.restart` / `restart_sec` / `timeout_start_sec` | Podman default | `on-failure` / `15s` / omitted. |
| `cleanup.enable` / `force` | Docker default | `true` / `false`. |

## Identity and process

| Option | Type | Required | Default | Runtime | Owner | Description |
| ------ | ---- | -------- | ------- | ------- | ----- | ----------- |
| `image` | Non-empty string | Yes | None | Both | `docker_services` / `podman_services` | Image reference. Podman requires an explicit non-`latest` tag. Repository definitions should always pin an exact tag. |
| `user` | String | No | Image default | Both | `docker_services` / `podman_services` | Docker passes a Compose user string. Podman requires exactly `UID:GID` with two non-negative numeric IDs and renders separate `User=` and `Group=`. |
| `hostname` | String | No | Runtime-native | Docker | `docker_services` | Compose hostname; empty values are omitted. |
| `container_name` | String | No | Compose-generated name | Docker | `docker_services` | Forces a literal name only for `deploy.type: container`. Usually unnecessary because Compose derives project/service/index names. |
| `pid` | Non-empty string | No | Runtime-native | Docker | `docker_services` | Compose PID namespace value; no repository enum is enforced. |
| `cgroup` | String enum | No | Runtime-native | Docker | `docker_services` | Only `host` or `private` is rendered. |
| `entrypoint` | Non-empty string or list | No | Image default | Docker | `docker_services` | Replaces the image entrypoint and is replace-only during target merge. |
| `command` | Non-empty string or list of non-empty strings | No | Image default | Docker | `docker_services` | Replaces the Compose command and is replace-only during target merge. |

No service fields currently exist for working directory, init, stop signal,
stop timeout, or pull policy. Podman pulling is controlled by the role default
`podman_services_pull_images: true`, not a service key.

## Environment

| Option | Type | Required | Default | Runtime | Owner | Description |
| ------ | ---- | -------- | ------- | ------- | ----- | ----------- |
| `environment` | Mapping | No | `{}` | Both | `service_common` | Environment names mapped to direct scalars or one typed form. Common normalization runs before adapter rendering. |
| `environment.<NAME>` | String, integer, Boolean, null, or typed mapping | No | None | Both | `service_common` | Names match `[A-Za-z_][A-Za-z0-9_]*`. Floats, lists, arbitrary mappings, line breaks, and NUL bytes are rejected. |
| `environment.<NAME>.value_from` | Mapping | Conditional | None | Both | `service_common` | Must be the only key in the value. |
| `environment.<NAME>.value_from.infisical` | Identifier string | Conditional | None | Both | `service_common` | References a `var` declared by this service. The resolved scalar retains its type. |
| `environment.<NAME>.value_template` | String | Conditional | None | Both | `service_common` | Must be the only key and contain at least one `${var}` reference. |
| `env_file` | Non-empty string or list of strings | No | Omitted | Docker | `docker_services` | Attaches existing Compose environment files. Podman writes a protected generated file from resolved `environment`. |

Template substitution is single-pass. `${var}` inserts a fetched scalar; null
becomes empty text, booleans become lowercase text, and `$$` produces one
literal dollar. Bare dollar signs, unknown variables, and mixed typed shapes
are invalid. With `fail_on_empty: false`, an absent reference resolves empty.

```yaml
environment:
  LOG_LEVEL: info
  WORKERS: 2
  FEATURE_ENABLED: false
  OPTIONAL_VALUE: null
  API_VALUE:
    value_from:
      infisical: api_value
  PUBLIC_URL:
    value_template: "https://demo.${example_zone}/price/$$5"
```

## Infisical and native secrets

### Lookup declaration

| Option | Type | Required | Default | Runtime | Owner | Description |
| ------ | ---- | -------- | ------- | ------- | ----- | ----------- |
| `infisical` | Mapping | No | `{}` | Both | `service_common` | Runtime-neutral lookup configuration; outputs are reset between services. |
| `infisical.secrets_map` | List of mappings | No | `[]` | Both | `service_common` | Ordered declarations. Duplicate vars and conflicting native-secret names are rejected. |
| `infisical.fail_on_empty` | Strict Boolean-like | No | `true` | Both | `service_common` | Missing or blank live values fail. Use false only when every consumer accepts empty. |
| `infisical.secrets_map[].var` | Identifier string | Yes | None | Both | `service_common` | Local key used by environment, PostgreSQL, templates, and preparation handlers. |
| `infisical.secrets_map[].path` | Non-empty string | Yes | None | Both | `service_common` | Lookup path. |
| `infisical.secrets_map[].name` | Non-empty string | Yes | None | Both | `service_common` | Lookup secret name. |
| `infisical.secrets_map[].check_mode_value` | Non-empty string | No | `__CHECK_MODE_REDACTED_INFISICAL_<var>__` | Both | `service_common` | Optional synthetic shape used only in check mode; never sent to Infisical. |
| `infisical.secrets_map[].secret` | Mapping | No | Lookup-only | Both | `service_common` | Adds a value-free runtime-native secret declaration. |

Check mode validates and builds stand-ins without a lookup. Live lookup may be
controller-delegated, but inputs and resulting facts remain dispatch-host owned.
Value-bearing tasks use `no_log: true` and `diff: false`; errors list variable
names, never values.

### Native-secret declaration

| Option | Type | Required | Default | Runtime | Owner | Description |
| ------ | ---- | -------- | ------- | ------- | ----- | ----------- |
| `infisical.secrets_map[].secret.name` | Resource-name string | Yes | None | Both | `service_common` | Matches `[A-Za-z0-9][A-Za-z0-9_.-]*`. |
| `infisical.secrets_map[].secret.target` | Absolute path | No | `/run/secrets/<name>` | Both | `service_common` | Docker Swarm requires a path directly beneath `/run/secrets`. |
| `infisical.secrets_map[].secret.uid` | Numeric string | No | Runtime/container user | Both | `docker_services` / `podman_services` | Owner ID inside the container. |
| `infisical.secrets_map[].secret.gid` | Numeric string | No | Runtime/container group | Both | `docker_services` / `podman_services` | Group ID inside the container. |
| `infisical.secrets_map[].secret.mode` | Quoted octal string | No | Podman `0400`; runtime-specific otherwise | Both | `docker_services` / `podman_services` | Exactly four digits beginning with `0`. |
| `infisical.secrets_map[].secret.update_policy` | String enum | No | `preserve` | Both | `docker_services` / `podman_services` | Exactly `preserve` or `reconcile`. |
| `secrets` | Docker: string/list of strings or mappings; Podman: list of names | No | `[]` | Both | `docker_services` / `podman_services` | Attaches declared, generated, or externally managed native secrets. Podman accepts value-free names only. |
| `secrets[].source` | Resource name | Conditional | None | Docker | `docker_services` | Required for a Docker long-syntax mapping attachment. |
| `secrets[].target` | String | Conditional | None | Docker | `docker_services` | Required for a Docker long-syntax mapping attachment. |

| Policy/action | Missing | Existing |
| ------------- | ------- | -------- |
| `preserve`, all materializing actions | Create | Keep unchanged. |
| `reconcile`, deploy/bootstrap | Create | Keep unchanged. |
| `reconcile`, update/recreate | Create | Docker content-aware replacement or protected-file overwrite; Podman force-recreates because stored content cannot be compared. |
| remove | Adapter-owned | Docker removes service attachments; Podman intentionally preserves native secrets. |

Docker Swarm objects are immutable, so in-use replacement can fail safely.
Standalone Docker uses protected files. Podman renders `Secret=` metadata.
Check mode creates nothing.

## Connectivity

### Ports

`ports` accepts a named mapping or a list. Mapping names are for readability.

| Option | Type | Required | Default | Runtime | Owner | Description |
| ------ | ---- | -------- | ------- | ------- | ----- | ----------- |
| `ports` | Mapping or list of mappings | No | `[]` | Both | `docker_services` / `podman_services` | Publishes container ports. |
| `ports[].published` | Integer-like | Yes | None | Both | `docker_services` / `podman_services` | Host port. Podman enforces `1..65535`; Docker requires integer conversion. |
| `ports[].target` | Integer-like | Yes | None | Both | `docker_services` / `podman_services` | Container port. Podman enforces `1..65535`. |
| `ports[].protocol` | String enum | No | `tcp` | Both | `docker_services` / `podman_services` | Exactly `tcp` or `udp`. |
| `ports[].host_ip` | IPv4 string | No | All interfaces | Both | `docker_services` / `podman_services` | Binds a host address. Docker Swarm rejects it; IPv6 is not supported. |
| `ports[].mode` | String | No | `ingress` | Docker | `docker_services` | Swarm publish mode. Omitted for standalone and rejected by Podman. |

### Networks and dependencies

| Option | Type | Required | Default | Runtime | Owner | Description |
| ------ | ---- | -------- | ------- | ------- | ----- | ----------- |
| `named_networks` | Mapping | No | `{}` | Both | `docker_services` / `podman_services` | Docker supports multiple entries; Podman supports zero or one mapping entry. |
| `named_networks.<key>.name` | Resource-name string | No | Mapping key | Both | `docker_services` / `podman_services` | Runtime-visible name. |
| `named_networks.<key>.external` | Strict Boolean-like | No | Docker `true`; Podman `false` | Both | `docker_services` / `podman_services` | External resources are attached but not owned. Live Podman deploy/update/recreate/bootstrap first requires the exact network in the Podman network store. |
| `named_networks.<key>.driver` | String | No | Runtime-native | Both | `docker_services` / `podman_services` | Docker passes it to Compose. Podman accepts `bridge`, `ipvlan`, or `macvlan` and rejects it on an external network. |
| `networks` | List | No | Keys of `named_networks`, else `[docker_network]` | Docker | `docker_services` | Legacy direct Compose attachment list. Prefer `named_networks`. |
| `network_mode` | Non-empty string | No | Omitted | Docker | `docker_services` | Compose network mode. When set, normal network attachments are omitted. |
| `depends_on` | String or list | No | `[]` | Docker | `docker_services` | Compose start ordering, not a health guarantee. |

Docker named resources default to external. Non-external definitions are
Compose-owned with the stack. Podman generates one managed `.network` Quadlet
when `external: false`, preserves it on update/recreate, and removes it only on
explicit remove. External Podman networks are never rendered or deleted. They must already exist in
the destination host Podman network store; a Docker network with the same name is
a separate resource and does not satisfy the live preflight. Managed Podman
networks remain the preferred default for isolated services. Cross-runtime
communication requires published host endpoints or another deliberately designed
network path.

There are no service keys for `expose`, DNS servers, or extra hosts.

## Filesystem and storage

Common filesystem work runs on resolved filesystem hosts during
deploy/update/recreate/bootstrap, not drift or remove.

### Paths

| Option | Type | Required | Default | Runtime | Owner | Description |
| ------ | ---- | -------- | ------- | ------- | ----- | ----------- |
| `paths` | List of mappings | No | `[]` | Both | `service_common` | Ensures host filesystem objects. Podman paths must normalize within `/opt`. |
| `paths[].path` | Non-empty path string | Yes | None | Both | `service_common` | Destination on every filesystem host. |
| `paths[].state` | String enum | No | `directory` | Both | `service_common` | `absent`, `directory`, `file`, `hard`, `link`, or `touch`. |
| `paths[].src` | Non-empty string | Conditional | None | Both | `service_common` | Required for `hard` and `link`. |
| `paths[].owner` | User/ID | No | Host PUID, then `1000` | Both | `service_common` | Filesystem owner. Omit it for a rootless Podman bind source; the adapter assigns its dedicated execution account. |
| `paths[].group` | Group/ID | No | Host PGID, then `1000` | Both | `service_common` | Filesystem group. Omit it for a rootless Podman bind source; the adapter assigns its dedicated execution account. |
| `paths[].mode` | Octal-looking string | No | Docker `0755`; Podman `0750` | Both | `service_common` | Docker validation accepts three or four octal digits. |
| `paths[].force` | Boolean-like | No | `false` | Both | `service_common` | Passed to `ansible.builtin.file`, mainly for link replacement. |

There is no author-facing recursive option. List parents before children;
ordinary directory trees are not recursively re-owned or re-moded. As a narrow
exception, the Podman adapter recursively assigns each validated rootless bind
source—which must be a normalized proper descendant of `/opt`—to its dedicated
execution account before rendering the Quadlet. It does
not recursively change file modes.

### Copies and templates

| Option | Type | Required | Default | Runtime | Owner | Description |
| ------ | ---- | -------- | ------- | ------- | ----- | ----------- |
| `copies` | List of mappings | No | `[]` | Both | `service_common` | Copies static role files to each filesystem host. |
| `copies[].src` | Non-empty string | Yes | None | Both | `service_common` | Path relative to the common role, commonly under `files/`. |
| `copies[].dest` | Non-empty string | Yes | None | Both | `service_common` | Destination path. |
| `copies[].owner` | User or ID | No | Host PUID, then `1000` | Both | `service_common` | Destination owner. |
| `copies[].group` | Group or ID | No | Host PGID, then `1000` | Both | `service_common` | Destination group. |
| `copies[].mode` | Mode string | No | Module default | Both | `service_common` | Explicit destination mode. |
| `copies[].force` | Boolean-like | No | `false` | Both | `service_common` | Replaces differing existing content when true. |
| `copies[].wait` | Boolean-like | No | `false` | Both | `service_common` | Waits for `dest` after copying. |
| `copies[].wait_timeout` | Integer-like seconds | No | `30` | Both | `service_common` | Wait limit when `wait` is true. |
| `templates` | List of mappings | No | `[]` | Both | `service_common` | Renders from `service_common/templates` to every filesystem host. |
| `templates[].src` | Non-empty string | Yes | None | Both | `service_common` | Common-template-relative source. |
| `templates[].dest` | Non-empty string | Yes | None | Both | `service_common` | Destination path. |
| `templates[].owner` | User or ID | No | Host PUID, then `1000` | Both | `service_common` | Destination owner. |
| `templates[].group` | Group or ID | No | Host PGID, then `1000` | Both | `service_common` | Destination group. |
| `templates[].mode` | Mode string | No | `0664` | Both | `service_common` | Docker validation accepts three or four octal digits. |
| `templates[].force` | Boolean-like | No | `true` | Both | `service_common` | Replaces changed destination content. |
| `templates[].no_log` | Boolean-like | No | `false` | Both | `service_common` | Hides secret-bearing rendering and disables diff; such templates are skipped in check mode. |
| `swarm_env_templates` | List of template mappings | No | `[]` | Docker | `docker_services` + `service_common` | Same nested fields as `templates`, rendered on the controller for Compose `env_file` use. |

### Mounts and named volumes

`volumes` accepts a named mapping or list. Mapping names are descriptive only.

| Option | Type | Required | Default | Runtime | Owner | Description |
| ------ | ---- | -------- | ------- | ------- | ----- | ----------- |
| `volumes` | Mapping or list of mappings | No | `[]` | Both | `docker_services` / `podman_services` | Bind, named-volume, or tmpfs mounts. |
| `volumes[].type` | String enum | No | `bind` | Both | `docker_services` / `podman_services` | `bind`, `volume`, or `tmpfs`. |
| `volumes[].source` | Non-empty string | Conditional | None | Both | `docker_services` / `podman_services` | Required for bind and named volumes; omitted for tmpfs. |
| `volumes[].target` | Non-empty string | Yes | None | Both | `docker_services` / `podman_services` | Container path. |
| `volumes[].read_only` | Boolean-like | No | `false` | Both | `docker_services` / `podman_services` | Mounts read-only. |
| `volumes[].tmpfs` | Mapping | No | `{}` | Both | `docker_services` / `podman_services` | Tmpfs options. |
| `volumes[].tmpfs.size` | Non-negative integer | No | Runtime-native | Both | `docker_services` / `podman_services` | Passed to Compose or rendered as Quadlet `size=`. |
| `volumes[].tmpfs.mode` | Passed-through value | No | Runtime-native | Podman | `podman_services` | Rendered as Quadlet `mode=`; no octal-format validation is currently imposed. |
| `named_volumes` | Mapping | No | `{}` | Docker | `docker_services` | Stack-level Compose volumes, defaulting to external. Podman creates Quadlets from `volumes[].type: volume`. |
| `named_volumes.<key>.name` | String | No | Compose default | Docker | `docker_services` | Explicit runtime name. |
| `named_volumes.<key>.external` | Boolean-like | No | `true` | Docker | `docker_services` | Expects a volume owned outside the stack. |
| `named_volumes.<key>.driver` | String | No | Runtime-native | Docker | `docker_services` | Compose volume driver. |
| `named_volumes.<key>.driver_opts` | Mapping | No | `{}` | Docker | `docker_services` | Compose driver options. |
| `tmpfs` | String or list | No | `[]` | Docker | `docker_services` | Compose tmpfs shorthand. Prefer `volumes[].type: tmpfs` for portability. |

Podman removes generated volume Quadlet files on explicit remove but preserves
application data. Bind source existence should be declared through `paths`.

### Docker Swarm configs

| Option | Type | Required | Default | Runtime | Owner | Description |
| ------ | ---- | -------- | ------- | ------- | ----- | ----------- |
| `swarm_configs` | List of mappings | No | `[]` | Docker | `docker_services` | Creates versioned Docker config objects before rendering. |
| `swarm_configs[].name` | Non-empty string | Yes | None | Docker | `docker_services` | Stable logical name referenced by `configs[].source`. |
| `swarm_configs[].state` | String enum | No | `present` | Docker | `docker_services` | `present` or `absent`. |
| `swarm_configs[].data` | String | Conditional | None | Docker | `docker_services` | Inline content; present items require `data` or `src`. |
| `swarm_configs[].src` | Non-empty path | Conditional | None | Docker | `docker_services` | Controller-side file/template lookup source; `.j2` is templated. |
| `swarm_configs[].data_is_template` | Boolean-like | No | `false` | Docker | `docker_services` | Forces `src` through Jinja template lookup. |
| `swarm_configs[].labels` | Mapping | No | Omitted | Docker | `docker_services` | Labels on the versioned config object. |
| `configs` | Non-empty list of mappings | No | `[]` | Docker | `docker_services` | Attaches configs after logical names become versioned names. |
| `configs[].source` | String | Yes | None | Docker | `docker_services` | Logical or external config name. |
| `configs[].target` | String | No | Compose default | Docker | `docker_services` | Container target passed through to Compose. |
| `configs[].mode` | Mode value | No | Compose default | Docker | `docker_services` | Compose config mode metadata. |

## Devices and security

| Option | Type | Required | Default | Runtime | Owner | Description |
| ------ | ---- | -------- | ------- | ------- | ----- | ----------- |
| `devices` | List of non-empty strings | No | `[]` | Docker | `docker_services` | Compose device mappings. |
| `cap_add` | List of non-empty strings | No | `[]` | Both | `docker_services` / `podman_services` | Adds Linux capabilities. |
| `cap_drop` | List of non-empty strings | No | `[]` | Both | `docker_services` / `podman_services` | Drops Linux capabilities. |
| `security_opt` | String or list | No | `[]` | Docker | `docker_services` | Compose security options. |
| `no_new_privileges` | Strict Boolean-like | No | Docker omitted/false; Podman `true` | Both | `docker_services` / `podman_services` | Docker accepts true only for standalone; Podman defaults to `NoNewPrivileges=true`. |
| `read_only` | Strict Boolean-like | No | `false` | Podman | `podman_services` | Read-only container root filesystem. |
| `sysctls` | Mapping | No | `{}` | Docker | `docker_services` | Compose sysctl mapping. |
| `shm_size` | String/size | No | Runtime-native | Docker | `docker_services` | Compose `/dev/shm` size. |
| `shm_tmpfs_size` | Positive integer bytes | No | Omitted | Docker | `docker_services` | Adds a sized `/dev/shm` tmpfs volume. |

There are no options for a separate process group, device cgroup rules,
privileged mode, ulimits, or IPC namespace. The adapters do not pass arbitrary
runtime security keys through.

## Health checks

| Option | Type | Required | Default | Runtime | Owner | Description |
| ------ | ---- | -------- | ------- | ------- | ----- | ----------- |
| `healthcheck` | Mapping | No | Omitted | Both | `docker_services` / `podman_services` | Enables runtime health checking. |
| `healthcheck.test` | Non-empty string or list of non-empty strings | Conditional | None | Both | `docker_services` / `podman_services` | String becomes Docker `CMD-SHELL`. Lists may begin `CMD`, `CMD-SHELL`, or `NONE`; Podman maps `NONE` to `none`. Target value replaces base. |
| `healthcheck.interval` | Runtime duration | No | Docker `1m`; Podman `30s` | Both | `docker_services` / `podman_services` | Time between checks. |
| `healthcheck.timeout` | Runtime duration | No | Docker `15s`; Podman `10s` | Both | `docker_services` / `podman_services` | Maximum check duration. |
| `healthcheck.retries` | Integer-like | No | `3` | Both | `docker_services` / `podman_services` | Failures before unhealthy. |
| `healthcheck.start_period` | Runtime duration | No | Docker `30s`; Podman `60s` | Both | `docker_services` / `podman_services` | Initial grace period. |

`NONE` is the supported disable form; there is no
`healthcheck.disable` option.

## Traefik

`service_common` renders controller-owned
`<service-name>-dynamic.yml` for either runtime and removes it on explicit
service removal. Service mode normally targets a Docker service name; host mode
targets an inventory-derived or explicit host address.

| Option | Type | Required | Default | Runtime | Owner | Description |
| ------ | ---- | -------- | ------- | ------- | ----- | ----------- |
| `traefik` | Mapping | No | `{}` | Both | `service_common` | Runtime-neutral route declaration. |
| `traefik.enable` | Boolean-like | No | `false` | Both | `service_common` | Creates/removes the dynamic route on relevant actions. |
| `traefik.exposure` | String enum | No | `public` | Both | `service_common` | `public` uses public zone/entrypoint; `private` derives `int.<base-zone>` and the private entrypoint. |
| `traefik.zone` | Non-empty string | Conditional | Common base zone | Both | `service_common` | Explicit frontend zone; required only without a common base zone. |
| `traefik.subdomain` | String | No | Effective service name | Both | `service_common` | Frontend label in `<subdomain>.<zone>`. |
| `traefik.port` | Positive integer-like | Conditional | None | Both | `service_common` | Backend port. |
| `traefik.backend_mode` | String enum | No | `service` | Both | `service_common` | `service` targets effective service name; `host` resolves a host address. |
| `traefik.backend_url` | Non-empty string | No | Derived | Both | `service_common` | Complete URL; bypasses host/scheme construction, although `port` is still validated. |
| `traefik.backend_host` | Non-empty string | Conditional | None | Both | `service_common` | Direct address for host mode. |
| `traefik.backend_host_inventory` | Inventory hostname | Conditional | First filesystem host | Both | `service_common` | Resolves that host's `local_ip` in host mode. |
| `traefik.backend_scheme` | Non-empty string | No | `http` | Both | `service_common` | Scheme used to construct a backend URL. |
| `traefik.entrypoint` | Non-empty string | No | `https` public; `https_private` private | Both | `service_common` | Router entrypoint. |
| `traefik.sso` | String | No | Disabled | Both | `service_common` | Exactly `authelia` enables Authelia middleware. |
| `traefik.middleware_chain` | Non-empty string | No | `<name>-ui-chain` or `<name>-private-ui-chain` | Both | `service_common` | Middleware chain reference. |
| `traefik.headers_middleware` | Non-empty string | No | `secure-headers@file` | Both | `service_common` | Headers middleware reference. |
| `traefik.internal_api` | Boolean | No | `false` | Both | `service_common` | Enables the internal API router. Use a YAML Boolean; current code uses Python truthiness. |
| `traefik.internal_api_rules` | List | No | `[]` | Both | `service_common` | Extra internal API rule fragments. |
| `traefik.themepark` | Mapping | No | `{}` | Both | `service_common` | Enabled only when both nested values are non-empty. |
| `traefik.themepark.app` | String | Conditional | None | Both | `service_common` | Theme Park application identifier. |
| `traefik.themepark.theme` | String | Conditional | None | Both | `service_common` | Theme name. |

## PostgreSQL

| Option | Type | Required | Default | Runtime | Owner | Description |
| ------ | ---- | -------- | ------- | ------- | ----- | ----------- |
| `postgres` | Mapping | No | `{}` | Both | `service_common` | Runtime-neutral database preparation; unknown nested fields are rejected. |
| `postgres.enable` | Strict Boolean-like | No | `false` | Both | `service_common` | Enables reconciliation. |
| `postgres.databases` | Non-empty string or list of strings | Conditional | `[]` | Both | `service_common` | Required when enabled; every database is ensured present. |
| `postgres.port` | Integer | No | `5432` | Both | `service_common` | `1..65535`; booleans and numeric strings are rejected. |
| `postgres.user_var` | Identifier string | No | `postgres_user` | Both | `service_common` | Current-service Infisical login-user variable. |
| `postgres.password_var` | Identifier string | No | `postgres_pass` | Both | `service_common` | Current-service Infisical login-password variable. |
| `postgres.host` | Non-empty string | No | None | Both | `service_common` | Explicit address; mutually exclusive with `host_inventory`. |
| `postgres.host_inventory` | Inventory hostname | No | Controller host | Both | `service_common` | Resolves `local_ip` from exactly this host; mutually exclusive with `host`. |

Enabled definitions must declare both credential variables in their effective
`infisical.secrets_map`. Live deploy/update/recreate/bootstrap ensures databases
on the controller with hidden credentials. Check mode validates the complete
plan without lookup or database connection.

## Deployment and placement

### Common deployment metadata

| Option | Type | Required | Default | Runtime | Owner | Description |
| ------ | ---- | -------- | ------- | ------- | ----- | ----------- |
| `deploy` | Mapping | No | `{}` | Both | `docker_services` / `podman_services` | Placement and lifecycle metadata. |
| `deploy.type` | String enum | No | Docker `swarm`; Podman single instance | Both | `docker_services` / `podman_services` | Docker accepts `swarm`/`container`. When supplied for Podman it must be exactly `container`; `swarm` is rejected. |
| `deploy.host` | Host/group/list for Docker Swarm; one host for standalone/Podman | No | Docker controller; Podman catalog name | Both | `service_catalog` + `docker_services` / `podman_services` | Dispatch/filesystem placement. Swarm constraints, not this value, determine runtime node placement. |
| `deploy.execution.mode` | String enum | No | `rootful` | Podman | `podman_services` | Selects `rootful` system Quadlets or `rootless` user Quadlets for container deployments. Docker rejects this Podman-owned declaration. |
| `deploy.execution.host_user` | Host account name | Conditional | None | Podman | `podman_services` | Required when `mode` is `rootless` and must use the reserved `podman-` prefix. This dedicated locked, non-interactive host account owns Podman storage and its user systemd manager; it is separate from top-level container `user`. Existing accounts are reused only when persisted service ownership and the complete account contract match. |
| `deploy.execution.userns` | Mapping | Conditional | None | Podman | `podman_services` | Required for rootless bind mounts. Selects the validated `keep-id` mapping that makes the dedicated host account appear as the application UID/GID inside the container. |
| `deploy.execution.userns.mode` | String enum | Conditional | None | Podman | `podman_services` | Exactly `keep-id`. |
| `deploy.execution.userns.uid` | Numeric ID | Conditional | None | Podman | `podman_services` | Required with `userns` and must be between `0` and `65535`. Quadlet renders it in `UserNS=keep-id:uid=...`. |
| `deploy.execution.userns.gid` | Numeric ID | Conditional | None | Podman | `podman_services` | Required with `userns` and must be between `0` and `65535`. Quadlet renders it in `UserNS=keep-id:...,gid=...`. |
| `deploy.mode` | String enum | No | `replicated` | Both | `docker_services` / `podman_services` | Docker accepts `replicated`/`global`; Podman only `replicated`. |
| `deploy.replicas` | Non-negative integer-like | No | `1` | Both | `docker_services` / `podman_services` | Docker replica count; Podman accepts only `1`. |
| `deploy.profile` | Non-empty string | No | `none` | Docker | `docker_services` | `none`, `standard`, `careful`, or `stateless_ha`. Non-`none` is invalid for standalone; Podman rejects the field. |
| `deploy.constraints` | String or list of strings | No | `[]` | Docker | `docker_services` | Literal Swarm constraints. Docker node-label names are not inventory variables; Podman rejects the field. |

### Docker Swarm deploy mappings

| Option | Type | Required | Default | Runtime | Owner | Description |
| ------ | ---- | -------- | ------- | ------- | ----- | ----------- |
| `deploy.restart_policy` | Mapping | No | Selected profile | Docker | `docker_services` | Recursive profile override passed to Compose. Common keys: `condition`, `delay`, `max_attempts`, `window`. |
| `deploy.update_config` | Mapping | No | Selected profile | Docker | `docker_services` | Recursive profile override. Profiles use `parallelism`, `delay`, `failure_action`, `order`. |
| `deploy.rollback_config` | Mapping | No | Selected profile | Docker | `docker_services` | Recursive profile override. Profiles use `parallelism`, `delay`, `order`. |
| `deploy.resources` | Mapping | No | Selected profile/omitted | Docker | `docker_services` | Compose limits/reservations mapping. Nested fields are passed through, not repository-whitelisted. |

| Profile | Restart | Update | Rollback |
| ------- | ------- | ------ | -------- |
| `none` | None | None | None |
| `standard` | on-failure, 10s delay, 5 attempts, 2m window | one at a time, 10s delay, rollback, stop-first | one at a time, 10s delay, stop-first |
| `careful` | Same as standard | one at a time, 30s delay, rollback, stop-first | one at a time, 30s delay, stop-first |
| `stateless_ha` | on-failure, 5s delay, 5 attempts, 2m window | one at a time, 5s delay, rollback, start-first | one at a time, 5s delay, start-first |

### Other Docker-only runtime fields

| Option | Type | Required | Default | Runtime | Owner | Description |
| ------ | ---- | -------- | ------- | ------- | ----- | ----------- |
| `labels` | Mapping or list | No | `[]` | Docker | `docker_services` | Compose labels; appended with new mapping values winning. |
| `cleanup` | Mapping | No | `{enable: true, force: false}` | Docker | `docker_services` | Controls stack/container cleanup for remove/recreate. |
| `cleanup.enable` | Boolean-like | No | `true` | Docker | `docker_services` | Allows cleanup. |
| `cleanup.force` | Boolean-like | No | `false` | Docker | `docker_services` | Allows repeated cleanup of the same stack in one run. |
| `settings` | Mapping | No | Template-specific | Docker | `docker_services` | Application template input currently consumed by HAProxy; not automatically passed to the container. |

## Podman systemd

Top-level `systemd` is valid only for an effective Podman service. Docker
catalog validation rejects it.

| Option | Type | Required | Default | Runtime | Owner | Description |
| ------ | ---- | -------- | ------- | ------- | ----- | ----------- |
| `systemd` | Mapping | No | `{}` | Podman | `podman_services` | Quadlet dependency/restart settings; unknown fields are rejected. |
| `systemd.after` | List of non-empty unit names | No | `[]` | Podman | `podman_services` | Renders one `After=` line per entry. |
| `systemd.restart` | Non-empty string | No | `on-failure` | Podman | `podman_services` | Passed to `Restart=`; no repository enum is maintained. |
| `systemd.restart_sec` | Non-empty string | No | `15s` | Podman | `podman_services` | Passed to `RestartSec=`. |
| `systemd.timeout_start_sec` | Non-empty string | No | Omitted | Podman | `podman_services` | Passed to `TimeoutStartSec=`; bounds how long systemd waits for startup and does not delay a successful start. |

## Application preparation

| Option | Type | Required | Default | Runtime | Owner | Description |
| ------ | ---- | -------- | ------- | ------- | ----- | ----------- |
| `application_prepare` | Mapping | No | `{}` | Both | `service_prepare` | Selects one registered handler. |
| `application_prepare.handler` | String enum | No | Empty/no handler | Both | `service_prepare` | `authelia`, `qbittorrent`, `plex`, `bazarr`, `nzbhydra2`, or `vaultwarden`. |
| `application_prepare.bootstrap` | Mapping | Conditional | `{}` | Docker | `service_prepare` | Plex bootstrap settings only. |
| `application_prepare.bootstrap.enabled` | Strict YAML Boolean | Conditional | None | Docker | `service_prepare` | Allows Plex API/token/claim work only with explicit bootstrap action. |
| `prep` | Mapping | Conditional | `{}` | Both | `service_prepare` | Non-secret connection input for Bazarr/NZBHydra2. |
| `paths_vault` | Mapping | Conditional | None | Both | `service_prepare` | Persistent Vaultwarden token paths; not a general path list. |

### Handler-specific fields

| Option | Type | Required | Default | Runtime | Owner | Description |
| ------ | ---- | -------- | ------- | ------- | ----- | ----------- |
| `prep.radarr.host` | Non-empty string | Conditional | None | Both | `service_prepare` | Radarr address written into Bazarr config. |
| `prep.radarr.port` | Non-empty value | Conditional | None | Both | `service_prepare` | Radarr port. |
| `prep.sonarr.host` | Non-empty string | Conditional | None | Both | `service_prepare` | Sonarr address. |
| `prep.sonarr.port` | Non-empty value | Conditional | None | Both | `service_prepare` | Sonarr port. |
| `prep.postgres.host` | Non-empty string | Conditional | None | Both | `service_prepare` | Application-side database address, separate from common reconciliation addressing. |
| `prep.postgres.port` | Non-empty value | Conditional | None | Both | `service_prepare` | Application-side database port. |
| `prep.sabnzbd.url` | String | No | `http://sabnzbd:8080` | Both | `service_prepare` | Downloader URL. |
| `paths_vault.vault_dir` | Non-empty path | Conditional | None | Both | `service_prepare` | Persistent directory, created mode `0700`. |
| `paths_vault.vault_token_file` | Non-empty path | Conditional | None | Both | `service_prepare` | Argon2 PHC token file. |
| `paths_vault.vault_pass_file` | Non-empty path | Conditional | None | Both | `service_prepare` | Generated source-password file. |
| `paths_vault.vault_secret_name` | Non-empty resource name | Conditional | None | Both | `service_prepare` | Generated preserve-policy native-secret name. |

| Handler | Behavior/actions | Contract |
| ------- | ---------------- | -------- |
| Authelia | Generates session/JWT values and derives a password hash on deploy/update/recreate/bootstrap. | Needs declared `authelia_pass` and `authelia_storage_key`. Uses a selected-runtime temporary container outside check mode. No extra fields beyond handler. |
| qBittorrent | Derives PBKDF2 template value on deploy/update/recreate/bootstrap. | Name must be `qbittorrent` or `qbittorrent-xs` with matching declared password. No extra fields. |
| Plex | Runs only under explicit bootstrap, never check mode. | Docker-only; requires strict bootstrap flag and managed `named_volumes.media_nfs` with Docker local-driver options. |
| Conditional | Creates initial config only when absent, then updates it on deploy/update/recreate. | Requires listed `prep` fields and declared API values; optional subtitle credentials must be paired. |
| NZBHydra2 | Creates initial YAML only when absent, then manages auth/downloader/indexers on deploy/update/recreate. | Required values and every optional provider user/API pair must be complete. |
| Conditional | Reads or creates a persistent Argon2 token on deploy/update/recreate/bootstrap. | Requires all `paths_vault` fields; partial files are removed after failure. |

Validation occurs before destructive runtime cleanup. Outputs reset per service.
Preparation containers use the selected runtime, never enter deployed state,
never start in check mode, and are removed after success or failure.

## Actions and lifecycle

| Action | Common/preparation | Docker | Podman |
| ------ | ------------------ | ------ | ------ |
| deploy | Lookup/environment preflight; handler work; PostgreSQL, files, Traefik. | Build/deploy Compose or Swarm; create missing secrets/configs. | Render Quadlets/env; pull per role default; create missing secrets; start. |
| update | Same common preparation. | Re-render/redeploy; reconcile secrets may rotate. | Re-render/restart as needed; reconcile secrets force-recreate. |
| recreate | Lookup and validation finish before cleanup. | Remove existing stack/container once, then rebuild. | Stop existing unit, reconcile, render, start; preserve network. |
| bootstrap | Common preparation plus bootstrap-tagged handlers. | Normal deploy path; optional explicit Plex bootstrap. | Normal path; Plex is rejected. |
| remove | No lookup/application mutation; remove common Traefik route. | Remove runtime artifacts when cleanup enabled. | Stop service; remove generated files and owned network; preserve data/secrets. |
| drift | Common declaration/environment preflight and non-mutating handler interface validation. | Compare declared image with live Swarm/Compose reference. | Compare exact desired image reference with Podman inspect. |
| check mode | Validate catalog, graph, preparation contracts, database intent, files, route, and render plan. | “Changed” results are predictions; no lookup, connection, secret/config/image/runtime lifecycle, cleanup, or deploy. | Same boundary; no lookup, secret, image, systemd, network, or container mutation. |

Drift compares the deployed image reference. It does not query a registry for a
newer digest, and there is no service-level `drift` mapping.

## Runtime compatibility

Podman rejects every top-level field outside its catalog, adapter, common, and
application-preparation contracts. A runtime-only edit is therefore not a valid
migration when Docker-only fields such as `command`, `entrypoint`, configs,
devices, Swarm profiles, or constraints remain. Add behavior deliberately to
the adapter before migrating a service that needs it.

| Section | Docker | Podman | Classification |
| ------- | ------ | ------ | -------------- |
| Environment | Common resolution; Compose and optional `env_file` | Common resolution; protected env file | Portable with rendering differences |
| Infisical | Common-owned | Common-owned | Runtime-neutral |
| Native secrets | Swarm objects/protected files | Podman secrets/Quadlet metadata | Supported with lifecycle limits |
| Ports | Swarm/standalone long syntax | `PublishPort=` | Portable except `mode`/`host_ip` split |
| Named networks | Multiple; default external | Zero/one; managed by default, external preflight required | Supported with separate runtime stores |
| Volumes | Bind, named, tmpfs | Bind, volume Quadlets, tmpfs | Portable core; ownership differs |
| Devices/security | Devices/sysctls/standalone options plus capabilities | Capabilities, read-only root, no-new-privileges | Supported with limitations |
| Health | Compose defaults | Quadlet defaults | Portable with different defaults |
| Traefik | Common dynamic file | Common dynamic file | Runtime-neutral preparation |
| PostgreSQL | Common reconciliation | Common reconciliation | Runtime-neutral preparation |
| Deployment | Swarm or standalone | One local Quadlet; explicit type must be `container` | Runtime-specific |
| Systemd | Rejected | Supported top-level mapping | Podman-only |
| Application preparation | All; Plex bootstrap Docker-only | All except Plex | Supported with handler limits |
| Drift | Swarm/Compose inspection | Podman inspection | Runtime-specific |

Tests establish schema/render contracts, not live parity for every service.

## Examples

These are synthetic and are not deployed definitions.

### Minimal Docker service

```yaml
example_docker:
  enabled: true
  runtime: docker
  tags: [examples]
  stack: example-docker

  image: registry.example.invalid/demo/app:1.2.3

  deploy:
    type: swarm
    profile: standard
```

### Minimal Podman service

```yaml
example_podman:
  enabled: true
  runtime: podman
  tags: [examples]
  description: Synthetic Podman example

  image: registry.example.invalid/demo/app:1.2.3
  user: "1000:1000"

  deploy:
    type: container
    host: example_podman
```

### Infisical lookup-only environment

```yaml
example_lookup:
  enabled: true
  runtime: docker
  tags: [examples]

  image: registry.example.invalid/demo/app:1.2.3

  environment:
    API_VALUE:
      value_from:
        infisical: api_value
    PUBLIC_URL:
      value_template: "https://demo.${example_zone}"
  infisical:
    secrets_map:
      - var: api_value
        path: /Synthetic
        name: API_VALUE
      - var: example_zone
        path: /Synthetic
        name: EXAMPLE_ZONE
        check_mode_value: example.invalid

  deploy:
    type: container
    host: example_host
```

### Native secret with default preserve policy

```yaml
example_preserve:
  enabled: true
  runtime: podman
  tags: [examples]

  image: registry.example.invalid/demo/app:1.2.3
  user: "1000:1000"

  infisical:
    secrets_map:
      - var: application_key
        path: /Synthetic
        name: APPLICATION_KEY
        secret:
          name: example_application_key
          uid: "1000"
          gid: "1000"
          mode: "0400"
  secrets: [example_application_key]

  deploy:
    type: container
    host: example_preserve
```

### Native secret with reconcile policy

```yaml
example_reconcile:
  enabled: true
  runtime: docker
  tags: [examples]

  image: registry.example.invalid/demo/app:1.2.3

  infisical:
    secrets_map:
      - var: rotating_key
        path: /Synthetic
        name: ROTATING_KEY
        secret:
          name: example_rotating_key
          target: /run/secrets/example_rotating_key
          update_policy: reconcile
  secrets: [example_rotating_key]

  deploy:
    type: swarm
```

### Inheriting target

```yaml
example_family:
  enabled: true
  runtime: docker
  tags: [examples]

  image: registry.example.invalid/demo/app:1.2.3

  environment:
    LOG_LEVEL: info
  infisical:
    secrets_map:
      - var: database_user
        path: /Synthetic
        name: DATABASE_USER

  deploy:
    type: swarm

  targets:
    secondary:
      name: example-secondary

      environment:
        INSTANCE: secondary
      infisical:
        secrets_map:
          - var: secondary_api
            path: /Synthetic
            name: SECONDARY_API
```

### Podman network and systemd policy

```yaml
example_quadlet:
  enabled: true
  runtime: podman
  tags: [examples]

  image: registry.example.invalid/demo/app:1.2.3
  user: "1000:1000"

  named_networks:
    example-net:
      name: example-net
      driver: bridge
      external: false

  ports:
    web:
      published: 8080
      target: 8080
      protocol: tcp

  deploy:
    type: container
    host: example_quadlet
  systemd:
    after: [network-online.target]
    restart: on-failure
    restart_sec: 15s
    timeout_start_sec: 900s
```

For complete Podman examples, see `adminer.yml` and `n8n.yml`. For
base-plus-target inheritance, see `radarr.yml` and `sonarr.yml`. Their values are
environment-specific; this reference defines the schema.

## Removed and unsupported fields

These are not supported option-table entries:

- `infisical.secrets_map[].docker_secret`,
  `infisical.secrets_map[].podman_secret`, and old Podman lookup metadata;
- exact `__INFISICAL__:var` environment placeholders;
- secret `immutable`, `replace`, and secret-level `runtime_options` (use
  `secret.update_policy`);
- legacy Podman `container`, `env`, `host_paths`, singular `network`,
  `runtime_options.podman.network`, and `runtime_options.podman.systemd`;
- top-level `themepark` (use `traefik.themepark`);
- generic Compose keys with no repository consumer: `group`, `working_dir`,
  `init`, `stop_signal`, `stop_grace_period`, `pull_policy`,
  `device_cgroup_rules`, `privileged`, `ulimits`, `expose`, `extra_hosts`, and
  `dns`;
- service-level `drift` options.

Strict normalizers reject many retired fields. Older Docker paths without a
top-level whitelist may ignore others; that does not make them supported.
Introduce a field deliberately in its owner, behavioral tests, this reference,
and the ordering guide.

## Author checklist

- Start with `---` and use one catalog key.
- Declare `enabled` intentionally and `runtime` explicitly.
- Follow the style guide; keep `targets` last.
- Pin the image tag.
- Never store secret values; declare lookup paths and value-free metadata.
- Put shared values in the base and target-only differences under `targets`.
- Use canonical `container_host_*` inventory values instead of duplicating host
  identity/storage facts.
- Check runtime limitations before changing `runtime`.
- Run repository validation and a safe check-mode plan before live deployment.
