
- `configs.yml`: Attaches Docker configs to a service definition.
- `env_file.yml`: Normalizes and attaches one or more `env_file` entries to a service.
- `env.yml`: Merges environment variables into a service, with configurable precedence and merge strategy.
- `ports.yml`: Normalizes port mappings and applies them differently for compose/container vs swarm deploy modes.
- `secrets.yml`: Attaches secrets for swarm mode and converts secret references into bind-mounted secret files for compose/container mode.
- `shm.yml`: Sets `shm_size` for a service.
- `tmpfs.yml`: Normalizes, and merges tmpfs mounts for non-Swarm services.
- `volumes.yml`: Normalizes, validates, and merges service volume mounts from mapping, list, or legacy inputs.
