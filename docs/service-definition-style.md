# Service definition style

Service definitions under `ansible/group_vars/all/services` use one layout for
both Docker and Podman. This is a source-layout convention only: mapping order
does not select a runtime or change service behavior. Keep existing values,
list order, comments, quoting, and Jinja expressions intact when applying it.

For types, defaults, validation, nested fields, lifecycle effects, and runtime
limitations, use the
[authoritative option reference](../ansible/group_vars/all/services/README.md).

Every base service must include exactly one supported runtime declaration,
`runtime: docker` or `runtime: podman`. A missing base runtime is invalid and
does not default to Docker. Targets inherit the validated base runtime and add
`runtime` only when intentionally overriding it with another supported adapter.
Catalog selection remains lightweight; linear, globally ordered dispatch then
materializes only the current selected service on its dispatch host.

## Canonical order

Within the immediate mapping for a service or target, use the following
sections and key order. Omit keys that do not apply, and leave one blank line
between populated sections.

1. Identity and selection: `enabled`, `runtime`, `tags`, `name`, `description`,
   `stack`.
2. Image and process: `image`, `hostname`, `container_name`, `user`, `pid`,
   `cgroup`, `entrypoint`, `command`.
3. Environment, secrets, and configuration inputs: `environment`, `env_file`,
   `infisical`, `secrets`, `swarm_configs`, `configs`,
   `swarm_env_templates`, `settings`.
4. Application preparation: `paths_vault`, `application_prepare`, `prep`.
5. Connectivity: `depends_on`, `named_networks`, `networks`, `network_mode`,
   `ports`.
6. Filesystem and storage: `paths`, `copies`, `templates`, `named_volumes`,
   `volumes`, `tmpfs`.
7. Devices, security, and resources: `devices`, `cap_add`, `cap_drop`,
   `security_opt`, `no_new_privileges`, `read_only`, `sysctls`, `shm_size`,
   `shm_tmpfs_size`.
8. Health: `healthcheck`.
9. Integrations: `traefik`, `themepark`, `postgres`. New Theme Park
   configuration belongs under `traefik.themepark`; the top-level key remains in
   the layout only for existing definitions and has no runtime consumer.
10. Runtime and lifecycle: `labels`, `cleanup`, `deploy`, `systemd`.
11. Target overrides: `targets`.

The repository-specific keys added to the original proposed order have explicit
homes:

- `container_name` is process identity beside `hostname`.
- `swarm_configs` declares configuration resources before `configs` attaches
  them; `settings` contains application configuration inputs.
- `paths_vault` supplies filesystem inputs to application preparation and
  therefore precedes `application_prepare`.
- `pid` and `cgroup` are standalone Docker process/runtime controls;
  `shm_tmpfs_size` is a Swarm resource control.
- `named_networks` is the canonical network declaration for both adapters.
  Podman currently accepts one entry and uses `external` to distinguish a
  role-managed network from one managed elsewhere.
- `systemd` contains Podman-native unit dependencies and restart policy.

Unknown immediate keys are not placed heuristically. Add any new portable or
runtime-specific key deliberately to this guide and the ordering test.

## Targets

Shared configuration belongs in the base mapping. `targets` is always the last
base key, target order is preserved, and each target uses the same canonical
order for only the values it overrides. Do not copy inherited base values into
a target for visual completeness, and do not add `runtime` unless that target
really changes adapter. Target mappings merge recursively, additive lists use
append-rp semantics without exact duplicates, and `command`, `entrypoint`, and
`healthcheck.test` replace their inherited lists. Nested `targets` are invalid.

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
optional `secret`. `infisical.fail_on_empty` is a sibling of `secrets_map` and
controls the overall lookup configuration. It defaults to `true` and should be
omitted; set it to `false` only when the service intentionally permits empty
lookup values:

```yaml
infisical:
  fail_on_empty: false
  secrets_map:
    - var: optional_value
      path: /Synthetic
      name: OPTIONAL_VALUE
```

`check_mode_value` is also optional: omit it for the deterministic
`__CHECK_MODE_REDACTED_INFISICAL_<var>__` default, and use a visibly synthetic
override only when downstream validation needs a hostname, port, email, URL,
or another particular shape. Within `secret`, use `name`, optional `target`,
`uid`, `gid`, `mode`, then optional `update_policy`. The exact policy values are
`preserve` and `reconcile`; omission defaults safely to `preserve`. Do not sort the declarations alphabetically. In `paths`,
parents precede their children. Keep configuration and data/media volumes, and
primary and ancillary ports, in meaningful application order.

The unit test enforces immediate base and target key order and the explicit
Infisical declaration convention. Runtime normalization, target inheritance,
and execution behavior remain owned by their existing filters and roles.

## Cross-service application endpoints

Service topology is supplied by the NetBox global Config Context through the
dynamic inventory variables `services_public_zone`, `services_internal_zone`,
and `services_private_https_port`. Service code must consume those composed
variables rather than raw `config_context` data or Infisical domain values, and
must not derive the internal zone from the public zone. Infisical remains the
source for credentials and other secret material.

Cross-service HTTP/API integrations should use the provider's stable private
application FQDN when that provider exposes one, rather than runtime-local
Docker or Podman DNS. Runtime-local addressing remains appropriate for tightly
coupled infrastructure, monitoring and control-plane traffic, and container
self-healthchecks. When an application has no private route, use another stable
interface such as an inventory-derived host address instead of inventing a new
Traefik route.
