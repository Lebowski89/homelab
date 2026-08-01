# Service definitions

Each YAML file in this directory describes one service and the runtime that
runs it. Docker and Podman share the same basic layout, so changing runtime
does not mean rewriting the whole service.

The order below is for people, not Ansible. It keeps similar settings together
and makes services easier to compare. For merge rules and complete examples,
see the [service definition style guide](../../../../docs/service-definition-style.md).

> [!NOTE]
> A key appearing in this guide does not mean every runtime supports it.
> Docker and Podman still validate their own features and reject combinations
> they cannot safely run.

## Order at a glance

Use the same order in a base service and in each target. Skip any section that
the service does not need.

| Order | Comment heading | What belongs here |
| ----: | --------------- | ----------------- |
| 1 | Identity | Whether the service runs, which runtime owns it, and the names used to select and deploy it. |
| 2 | Image/process | The container image and how its main process starts. |
| 3 | Environment/secrets | Environment variables, secret declarations, and configuration inputs. |
| 4 | Application preparation | Work that must happen before the runtime renders or starts the service. |
| 5 | Connectivity | Networks, ports, DNS, and links to other services. |
| 6 | Filesystem | Host directories, copied files, templates, volumes, and temporary storage. |
| 7 | Devices/security | Hardware access, Linux permissions, and resource limits. |
| 8 | Health | How the runtime decides whether the service is healthy. |
| 9 | Integrations | Repository-managed Traefik, Theme Park, and PostgreSQL setup. |
| 10 | Runtime/lifecycle | Deployment placement, runtime-only options, cleanup, and drift behavior. |
| 11 | Targets | Named variations of the base service. This section is always last. |

## Key reference

### 1. Identity

| Key | What it means |
| --- | ------------- |
| `enabled` | Turns the service on or off without deleting its definition. |
| `runtime` | Chooses the adapter that runs the service: `docker` or `podman`. |
| `tags` | Groups related services so commands such as `skynet check arrs` can select them together. |
| `name` | The service name given to the runtime. If omitted, the top-level service key is used. |
| `description` | A human-readable summary shown where the runtime supports one. |
| `stack` | The Docker Compose or Swarm project name. Services with the same stack are deployed together. |

### 2. Image/process

| Key | What it means |
| --- | ------------- |
| `image` | The exact container image and tag to run. Keep the tag pinned. |
| `hostname` | The hostname the application sees from inside the container. |
| `container_name` | Forces a literal name for a non-Swarm Docker container. |
| `user` | The user ID the process runs as. Portable Podman services use `UID:GID`. |
| `group` | A separate process group where the selected adapter supports one. Prefer `UID:GID` in `user` for portable services. |
| `working_dir` | The directory the application starts in inside the container. |
| `entrypoint` | Replaces the image's built-in startup program. |
| `command` | Replaces or adds the arguments passed to the startup program. |

### 3. Environment, secrets, and configuration

| Key | What it means |
| --- | ------------- |
| `environment` | Environment variables passed to the application. Values can refer to inventory data or resolved secrets. |
| `env_file` | One or more files whose variables are loaded into the container. |
| `infisical` | Declares which values to fetch from Infisical. It contains names and paths, never the secret values themselves. |
| `secrets` | Attaches value-free runtime secret names to the service. Secret lifecycle intent belongs to `infisical.secrets_map[].secret.update_policy`. |
| `swarm_configs` | Creates Docker Swarm config objects from repository files or templates. |
| `configs` | Mounts declared Swarm config objects into the service. |
| `swarm_env_templates` | Renders environment files onto the Docker deployment host before the service is deployed. |
| `settings` | Application-specific values used by repository templates. These are not automatically passed as environment variables. |

Within `infisical.secrets_map`, keep each declaration in this order: `var`,
`path`, `name`, optional `check_mode_value`, then optional `secret`. Within
`secret`, use `name`, optional `target`, `uid`, `gid`, `mode`, then optional
`update_policy`. The policy defaults to `preserve`; use `reconcile` only when
update/recreate should rotate the resolved value. `fail_on_empty` also defaults to
true, so omit it unless the service intentionally accepts an empty lookup.
`check_mode_value` is exceptional: the common default is
`__CHECK_MODE_REDACTED_INFISICAL_<var>__`, and an explicit visibly synthetic
value is needed only when downstream validation requires a specific shape.

### 4. Application preparation

| Key | What it means |
| --- | ------------- |
| `paths_vault` | File locations used by Vaultwarden's preparation handler for its generated token and password. This is not a general path list. |
| `application_prepare` | Selects an application-specific preparation handler and its options. |
| `prep` | Extra input needed by that handler, such as the address of another service. Its contents depend on the application. |

### 5. Connectivity

| Key | What it means |
| --- | ------------- |
| `depends_on` | Starts standalone Compose dependencies before this service. It does not replace a health check. |
| `named_networks` | Declares the networks the service joins. Docker keeps its existing multi-network behavior. Podman currently accepts one: `external: false` makes it role-managed, while `external: true` joins an existing network without creating or deleting it. |
| `ports` | Publishes container ports on the host, including protocol, host address, and Swarm publish mode when needed. |
| `expose` | Makes ports available to other containers without publishing them on the host. |
| `extra_hosts` | Adds fixed hostname-to-address entries inside the container. |
| `dns` | Chooses the DNS servers used inside the container. |

### 6. Filesystem and storage

| Key | What it means |
| --- | ------------- |
| `paths` | Creates or checks host directories and files before the service starts. |
| `copies` | Copies a static repository file onto the service host. |
| `templates` | Renders a Jinja template onto the service host using the current service values. |
| `named_volumes` | Declares Docker or Podman-managed volumes that exist separately from a container. |
| `volumes` | Mounts host paths, named volumes, or temporary filesystems into the container. |
| `tmpfs` | Adds memory-backed temporary mounts. Their contents disappear when the container stops. |

### 7. Devices, security, and resources

| Key | What it means |
| --- | ------------- |
| `devices` | Passes host hardware, such as a GPU or tuner, into the container. |
| `device_cgroup_rules` | Allows access to matching device types without listing every device path. |
| `cgroup` | Chooses whether a standalone Docker container shares the host's cgroup namespace or gets a private one. |
| `cap_add` | Gives the container specific Linux capabilities it would not normally have. |
| `cap_drop` | Removes Linux capabilities the application does not need. |
| `security_opt` | Passes runtime security options such as seccomp or `no-new-privileges`. |
| `no_new_privileges` | Stops processes in the container from gaining extra privileges. |
| `read_only` | Makes the container's root filesystem read-only. Writable volumes still work. |
| `privileged` | Gives the container broad access to the host. Use only when narrower device or capability settings will not work. |
| `sysctls` | Sets supported kernel options inside the container. |
| `ulimits` | Sets process limits such as the number of open files. |
| `shm_size` | Sets the size of `/dev/shm` for a standalone Docker container. |
| `shm_tmpfs_size` | Creates a sized `/dev/shm` temporary filesystem for a Swarm service. |

### 8. Health

| Key | What it means |
| --- | ------------- |
| `healthcheck` | Defines the command and timings used to mark the container healthy or unhealthy. |

### 9. Integrations

| Key | What it means |
| --- | ------------- |
| `traefik` | Creates the Traefik route for the service, including exposure, port, and optional SSO. |
| `themepark` | Applies a ThemePark skin to supported web applications. |
| `postgres` | Ensures the service's PostgreSQL users or databases exist before deployment. Credentials come from the service's Infisical declarations. |

### 10. Runtime and lifecycle

| Key | What it means |
| --- | ------------- |
| `labels` | Adds runtime labels used by tooling, monitoring, or features not covered by a dedicated integration. |
| `cleanup` | Controls whether Docker removes the existing stack during remove or recreate operations. |
| `deploy` | Chooses standalone container or Swarm mode, the host, replicas, placement, restart policy, and resource profile. |
| `container` | A runtime-specific container block kept in the canonical order for compatibility. Prefer the portable top-level keys for new definitions. |
| `systemd` | Sets Podman systemd dependencies and restart behavior with `after`, `restart`, and `restart_sec`. Docker services cannot use this field. |
| `runtime_options` | Holds remaining adapter-specific extensions. Podman network and systemd settings are first-class fields and do not belong here. |
| `drift` | Runtime-specific options for checking whether the running service still matches its declaration. |

### 11. Targets

| Key | What it means |
| --- | ------------- |
| `targets` | Named variations (including multiple instances, agents or redis companions) that inherit the base service and override only what differs. `targets` is always the final base-service key, and a target cannot contain another `targets` block. |

## Service file checklist

Before committing a new service file:

- The file starts with `---`.
- The top-level key matches the service name.
- `enabled` is set intentionally.
- `runtime` is explicitly `docker` or `podman`.
- Useful and unique selection tags are present.
- Immediate service and target keys follow the order above.
- `targets` is last, and targets are not nested.
- The image uses a pinned tag.
- No secret values are stored in the file.
- Secret-bearing tasks, including templates, set both `no_log: true` and `diff: false`.
- Required host paths and volume sources point to the right host.
- Swarm placement constraints use the correct node labels.
- The health check is reliable or intentionally omitted.
- `skynet check <service>` passes.
- `skynet lint` passes.
