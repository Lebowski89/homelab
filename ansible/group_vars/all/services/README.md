## Service file checklist

Before committing a new service file:

* The file starts with `---`.
* The top-level key matches the service name.
* `enabled: true` or `enabled: false` is set intentionally.
* Useful tags are defined.
* Target services use `targets:`.
* Target-specific tags are unique.
* Image tags are pinned.
* Secrets are not stored in plaintext.
* Sensitive templates have `no_log: true`.
* Required host paths are defined.
* Volumes point to correct hosts and paths.
* Placement constraints are correct (Swarm).
* Healthcheck is reliable or intentionally omitted.
* `skynet check <service>` passes.
* `skynet lint` passes.
