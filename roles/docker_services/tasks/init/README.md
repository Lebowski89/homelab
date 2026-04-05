# Init

These tasks initialise the role context by normalising the incoming service definition, resolving any target-specific overrides, and deriving the effective service, stack, host, and filesystem facts used throughout the role.

## Tasks

**validate_svc:** Validates normalized service fields (name/image/deploy/environment/ports/etc) for schema correctness.
