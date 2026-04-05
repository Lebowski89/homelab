# Sub-tasks

The purpose of these are pretty self-explanatory from their filename:

- `caps.yml`: Adds or replaces Linux capabilities (`cap_add` / `cap_drop`) for a service, with append/unique-append/merge modes.
- `command.yml`: Sets a service `command` with normalization for string/list input and optional append semantics.
- `depends_on.yml`: Normalizes and sets service `depends_on` entries.
- `devices.yml`: Adds device mappings to a service with append/replace behavior.
- `healthcheck.yml`: Builds and attaches a service `healthcheck` block, including normalized `test` command format.
- `security_opt.yml`: Adds or replaces `security_opt` entries for a service.
- `sysctls.yml`: Adds or replaces `sysctls` entries for a service.
- `user.yml`: Sets the runtime `user` for a service.
