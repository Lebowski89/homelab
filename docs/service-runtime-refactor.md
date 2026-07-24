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

The focused Infisical entry point accepts `service_common_infisical_secrets_map`, `service_common_infisical_lookup_params`, and `service_common_infisical_fail_on_empty`. It resets `service_common_secret_values` for every service and returns a dictionary keyed by each declaration's `var`. Check mode validates declarations but performs no lookup.

Shared Traefik files use `<service-name>-dynamic.yml`. A successful render removes the distinct legacy Podman `<service-name>.yml`; removal deletes both names idempotently. Explicit `backend_host` is resolved before any inventory lookup, while `backend_host_inventory` resolves `local_ip` only when needed. Thus n8n resolves its host backend to the n8n VM address on port 5678 without a duplicate runtime-specific Traefik definition.

## Deliberately retained runtime responsibilities

`docker_services` retains target/schema compatibility, deploy-host calculation, cleanup, Compose construction and filters, labels, ports, volumes, Docker secrets, Swarm configs, stack accumulation/deployment, image drift, PostgreSQL preparation, and the application-specific tasks below.

`podman_services` retains exact-image and UID/GID validation, dedicated-network validation, Podman secrets and replacement policy, images, Quadlet rendering, generated systemd units, lifecycle operations, and image drift.

Infisical declaration validation, retrieval, and empty-value enforcement are shared through `service_common_secret_values`. Docker recreates its flattened or dictionary compatibility facts after lookup, preserving environment placeholder resolution and deployment-host propagation. Docker still owns Docker secret selection, Swarm secrets, protected standalone secret files, PostgreSQL preparation, and application bootstraps. Podman still owns `containers.podman.podman_secret`, secret replacement policy, mount metadata, and Quadlet rendering. Both adapters keep runtime materialization outside `service_common`.

Check mode validates Infisical declarations but does not fetch secrets or recreate Docker compatibility facts. Docker runtime/application bootstraps and secret-bearing common templates are skipped, while paths, copies, non-sensitive templates, and Traefik structure remain checkable.

Automatic PostgreSQL creation is not common behavior. Existing Docker workflows keep their established database preparation. Podman only reports declared requirements in check mode and never creates a database. The n8n database therefore remains an explicit operation through the established Docker/services workflow. A future `service_database` role or `database_bootstrap` task should be invoked explicitly, never as an implicit step of every runtime deployment.

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

## Future canonical service schema

A later migration can normalize legacy Docker definitions and current Podman definitions into an internal structure such as:

```yaml
name: example
container:
  image: registry.example/example:1.2.3
  uid: "1000"
  gid: "1000"
environment: {}
published_ports: []
mounts: []
host_paths: []
secrets: []
postgres: {}
traefik: {}
runtime_options:
  docker: {}
  podman: {}
```

Portable services could then change only `runtime`. Swarm-only capabilities such as overlay networks, Swarm configs, placement constraints, replicas, and related deployment policy must remain under `runtime_options.docker`. Podman-specific Quadlet/systemd policy belongs under `runtime_options.podman`.

Migration must preserve the catalog compatibility path while accepting both legacy Docker fields (`image`, `environment`, `paths`, `copies`, `templates`, `ports`, `volumes`, `deploy`) and current Podman fields (`container.image`, `env`, `host_paths`, `container.ports`, `container.mounts`, `container.systemd`). Definitions should migrate individually with Docker/Podman render parity tests rather than through a bulk rewrite.

## Remaining sequence

1. Move suitable application preparation into `service_common/tasks/apps/` or, preferably for lifecycle-heavy applications, a dedicated `service_prepare` role.
2. In Phase 2B, introduce canonical runtime-neutral secret declarations while keeping both compatibility inputs, then migrate n8n.
3. Add `service_dispatch` only after normalized shared preparation and integration inputs are stable.
4. Migrate portable services one at a time, proving equivalent common configuration plus runtime-specific Compose or Quadlet output for each service.
