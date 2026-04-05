# Compose

These compose-generation tasks are organized into the following sub-categories:

00) init      # Prepare compose generation by validating inputs and deriving common facts
01) base      # Build the core service definition and common compose structure
02) runtime   # Apply runtime behavior and container execution settings
03) io        # Attach service inputs/outputs such as networks, volumes, ports, configs, secrets, and environment
04) metadata  # Apply service metadata such as labels

Together, these tasks take service vars, normalize and merge them, and produce template-ready compose structures.

See the docs within each folder for details on the sub-tasks within.
