# Compose

TLDR: These tasks take service vars, normalize and merge them, and produce template-ready compose structures.

The compose-generation tasks are organized into the following sub-categories:

## Init

**Summary:** Prepare compose generation by validating inputs and deriving common facts.

## Base

**Summary:** Build the core service definition and common compose structure.

### Tasks

**service_base:** Creates the baseline service definition (name, image/build, hostname/container name, etc).

**stack_networks:** Defines top-level compose networks for a stack and normalizes list/map input.

**stack_volumes:** Defines top-level compose volumes for a stack and normalizes list/map input.

## Runtime

**Summary:** Apply runtime behavior and container execution settings.

### Tasks

**caps:** Adds or replaces Linux capabilities (`cap_add` / `cap_drop`) for a service, with append/unique-append/merge modes.

**command:** Sets a service `command` with normalization for string/list input and optional append semantics.

**depends_on:** Normalizes and sets service `depends_on` entries.

**devices:** Adds device mappings to a service with append/replace behavior.

**healthcheck:** Builds and attaches a service `healthcheck` block, including normalized `test` command format.

**security_opt:** Adds or replaces `security_opt` entries for a service.

**sysctls:** Adds or replaces `sysctls` entries for a service.

**user:** Sets the runtime `user` for a service.

## IO

**Summary:** Attach service inputs/outputs such as networks, volumes, ports, configs, secrets, and environment.

### Tasks

**configs:** Attaches Docker configs to a service definition.

**env_file:** Normalizes and attaches one or more `env_file` entries to a service.

**env:** Merges environment variables into a service, with configurable precedence and merge strategy.

**ports:** Normalizes port mappings and applies them differently for compose/container vs swarm deploy modes.

**secrets:** Attaches swarm secrets / converts secret references into bind-mounted secret files for compose/container mode.

**shm:** Sets `shm_size` for a service.

**tmpfs:** Normalizes, and merges tmpfs mounts for non-Swarm services.

**volumes:** Normalizes, validates, and merges service volume mounts from mapping, list, or legacy inputs.

## Metadata

**Summary:** Apply service metadata such as labels.

### Tasks

**labels:** Merges and assigns labels to a service with precedence and merge controls.