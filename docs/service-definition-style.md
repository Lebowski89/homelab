# Service definition style

Service definitions under `ansible/group_vars/all/services` use one layout for
both Docker and Podman. This is a source-layout convention only: mapping order
does not select a runtime or change service behavior. Keep existing values,
list order, comments, quoting, and Jinja expressions intact when applying it.

## Canonical order

Within the immediate mapping for a service or target, use the following
sections and key order. Omit keys that do not apply, and leave one blank line
between populated sections.

1. Identity and selection: `enabled`, `runtime`, `tags`, `name`, `description`,
   `stack`.
2. Image and process: `image`, `hostname`, `container_name`, `user`, `group`,
   `working_dir`, `entrypoint`, `command`.
3. Environment, secrets, and configuration inputs: `environment`, `env_file`,
   `infisical`, `secrets`, `swarm_configs`, `configs`,
   `swarm_env_templates`, `settings`.
4. Application preparation: `paths_vault`, `application_prepare`, `prep`.
5. Connectivity: `depends_on`, `network`, `named_networks`, `ports`, `expose`,
   `extra_hosts`, `dns`.
6. Filesystem and storage: `paths`, `copies`, `templates`, `named_volumes`,
   `volumes`, `tmpfs`.
7. Devices, security, and resources: `devices`, `device_cgroup_rules`, `cgroup`,
   `cap_add`, `cap_drop`, `security_opt`, `no_new_privileges`, `read_only`,
   `privileged`, `sysctls`, `ulimits`, `shm_size`, `shm_tmpfs_size`.
8. Health: `healthcheck`.
9. Integrations: `traefik`, `themepark`, `postgres`.
10. Runtime and lifecycle: `labels`, `cleanup`, `deploy`, `container`, `systemd`,
    `runtime_options`, `drift`.
11. Target overrides: `targets`.

The repository-specific keys added to the original proposed order have explicit
homes:

- `container_name` is process identity beside `hostname`.
- `swarm_configs` declares configuration resources before `configs` attaches
  them; `settings` contains application configuration inputs.
- `paths_vault` supplies filesystem inputs to application preparation and
  therefore precedes `application_prepare`.
- `cgroup` and `shm_tmpfs_size` are runtime security/resource controls.
- `runtime_options` contains adapter-specific network and systemd policy and
  belongs with runtime lifecycle fields.

Unknown immediate keys are not placed heuristically. Add any new portable or
runtime-specific key deliberately to this guide and the ordering test.

## Targets

Shared configuration belongs in the base mapping. `targets` is always the last
base key, target order is preserved, and each target uses the same canonical
order for only the values it overrides. Do not copy inherited base values into
a target for visual completeness, and do not add `runtime` unless that target
really changes adapter. Nested `targets` are invalid.

```yaml
example:
  enabled: true
  runtime: docker
  tags: [example]
  stack: example

  image: example/image:1.0

  environment:
    TZ: "{{ timezone }}"
  infisical:
    fail_on_empty: true
    secrets_map: []

  named_networks:
    overlay:
      external: true

  paths: []
  volumes: {}

  traefik:
    enable: true

  deploy:
    type: swarm
    host: "{{ services_storage_host }}"
```

A base-plus-target definition keeps all shared facts before `targets`:

```yaml
example:
  enabled: true
  runtime: docker
  tags: [example]
  stack: example

  image: example/image:1.0

  environment:
    TZ: "{{ timezone }}"

  named_networks:
    overlay:
      external: true

  deploy:
    type: swarm
    host: "{{ services_storage_host }}"

  targets:
    primary:
      name: example-primary

      environment:
        INSTANCE_NAME: primary

      ports:
        - published: 1234
          target: 1234

      volumes:
        config:
          type: bind
          source: /opt/example-primary
          target: /config

      healthcheck:
        test: [CMD, healthcheck]

      traefik:
        port: 1234
```

## Nested mappings

The root order is not applied recursively to arbitrary application data.
Preserve meaningful grouping and comments in `environment`, `postgres`,
`deploy`, `container`, `traefik`, volume declarations, and other nested
mappings. Prefer alphabetical order only for simple flat environment maps when
it improves readability.

Within `infisical.secrets_map`, preserve logical list grouping. Each declaration
orders its keys as `var`, `path`, `name`, optional `check_mode_value`, then
optional `secret`. Do not sort the declarations alphabetically. In `paths`,
parents precede their children. Keep configuration and data/media volumes, and
primary and ancillary ports, in meaningful application order.

The unit test enforces immediate base and target key order and the explicit
Infisical declaration convention. Runtime normalization, target inheritance,
and execution behavior remain owned by their existing filters and roles.
