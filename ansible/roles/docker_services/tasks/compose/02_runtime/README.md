# Tasks

**caps:** Adds or replaces Linux capabilities (`cap_add` / `cap_drop`) for a service, with append/unique-append/merge modes.

**command:** Sets a service `command` with normalization for string/list input and optional append semantics.

**depends_on:** Normalizes and sets service `depends_on` entries.

**devices:** Adds device mappings to a service with append/replace behavior.

**healthcheck:** Builds and attaches a service `healthcheck` block, including normalized `test` command format.

**security_opt:** Adds or replaces `security_opt` entries for a service.

**sysctls:** Adds or replaces `sysctls` entries for a service.

**user:** Sets the runtime `user` for a service.
