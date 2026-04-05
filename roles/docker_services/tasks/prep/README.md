# Prep

These preparation tasks are broken down into the following sub-categories:

1) cleanup          # Remove existing service that could conflict with deployment.
2) pre-filesystem   # Prepare prerequisites and bootstrap state needed before touching the target filesystem.
3) filesystem       # Create and manage required filesystem (dirs and files) state for the service.
4) post-filesystem  # Finalise configuration and initialisation of the prepared filesystem.

See the docs within each folder for details on the sub-tasks within.