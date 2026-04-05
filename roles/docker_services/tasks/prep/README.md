# Prep

These preparation tasks are broken down into the following sub-categories:

- cleanup          # Remove existing service that could conflict with deployment.
- pre-filesystem   # Prepare prerequisites and bootstrap state needed before touching the target filesystem.
- filesystem       # Create and manage required filesystem (dirs and files) state for the service.
- post-filesystem  # Finalise configuration and initialisation of the prepared filesystem.

See the docs within each folder for details on the sub-tasks within.