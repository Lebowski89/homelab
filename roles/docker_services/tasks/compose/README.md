# Compose

These compose-generation tasks are organized into the following sub-categories:

- **init**      # Prepare compose generation by validating inputs and deriving common facts
- **base**      # Build the core service definition and common compose structure
- **runtime**   # Apply runtime behavior and container execution settings
- **io**        # Attach service inputs/outputs such as networks, volumes, ports, configs, secrets, and environment
- **metadata**  # Apply service metadata such as labels

Together, these tasks take service vars, normalize and merge them, and produce template-ready compose structures.

See the docs within each folder for details on the sub-tasks within.
