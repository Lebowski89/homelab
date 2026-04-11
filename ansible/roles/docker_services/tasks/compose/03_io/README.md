# Tasks

**configs:** Attaches Docker configs to a service definition.

**env_file:** Normalizes and attaches one or more `env_file` entries to a service.

**env:** Merges environment variables into a service, with configurable precedence and merge strategy.

**ports:** Normalizes port mappings and applies them differently for compose/container vs swarm deploy modes.

**secrets:** Attaches swarm secrets / converts secret references into bind-mounted secret files for compose/container mode.

**shm:** Sets `shm_size` for a service.

**tmpfs:** Normalizes, and merges tmpfs mounts for non-Swarm services.

**volumes:** Normalizes, validates, and merges service volume mounts from mapping, list, or legacy inputs.
