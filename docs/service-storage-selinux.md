# SELinux and application bind mounts

Storage labeling is explicit per canonical bind mount. Existing declarations
retain their labels and rendering when `selinux` is omitted. UID/GID ownership,
read-only access, rootless user namespaces and subordinate-ID allocations keep
their existing contracts. This feature does not disable SELinux, grant runtime
capabilities or change firewall policy.

```yaml
volumes:
  config:
    type: bind
    source: "{{ container_host_appdata_root }}/example"
    target: /config
    read_only: false
    selinux: shared
```

| `selinux` | Podman / standalone Docker | Docker Swarm |
| --- | --- | --- |
| `preserve` (default) | Leave the source's existing labels unchanged. | Leave operator-managed host labels unchanged. |
| `shared` | Use runtime `:z` relabeling. | Persist `container_file_t:s0` on the declared host path and restore its policy labels. |
| `private` | Use runtime `:Z` relabeling for one container. | Rejected: Swarm cannot apply private bind-mount relabeling. |

The behavior follows [Podman's volume labeling](https://docs.podman.io/en/latest/markdown/podman-run.1.html)
and [Docker's bind-mount restrictions](https://docs.docker.com/engine/storage/bind-mounts/#configure-the-selinux-label).
Shared labels permit sharing across containers; use them only for intended
shared access. Private sources must be exclusive to that container. Conflicting
private policies on overlapping mounts within a service fail validation. Paths
shared by independent services require a consistent explicit shared/preserved
policy; no service may privately relabel another service's data.

Automatic relabeling requires a matching owned `paths` entry or a managed
copy/template destination. Sources must be strictly below the target host's
existing inventory-derived application/data roots. Broad roots, system/runtime
paths, symlink sources, paths escaping their approved roots and special files
are rejected. Parent symlinks are resolved and checked against the resolved
inventory root. Existing read-only mount flags are preserved.

Choose `preserve` for externally managed storage, host sockets, system mounts,
shared data roots and filesystem-specific policies such as NFS. Arrange and
verify their access policy explicitly before migration. Declaring `preserve`
does not verify that the existing policy permits container access.

For Swarm, the Docker adapter requests generic filesystem contexts from
`service_common` on every declared filesystem host, after publication protection
is staged. Only Fedora/Rocky with known enabled SELinux state installs the RPM
policy tools, updates the exact `sefcontext` mapping and restores the owned path.
New files are reconciled after filesystem preparation and before deployment.
Restoration does not cross nested filesystems. Policy mappings and labels are
retained on application removal with the persistent data; retiring them requires
an explicit storage maintenance decision.

Temporary preparation containers inherit shared labeling from their current
service's bind declarations. Private binds are rejected for shared preparation:
a temporary container must not steal the permanent container's private label.
No raw relabel/chown mount options are accepted in preparation requests.

Check mode validates scope and reports deferred policy work. It does not install
tools, write policy mappings, relabel paths or run containers. Missing paths and
unavailable SELinux bindings are reported without claiming label verification;
normal execution requires a known SELinux state. Disabled SELinux is preserved.

No application definition is migrated by this infrastructure change. Validate
representative rootful/rootless workloads, actual file access, persistence and
second-run convergence on an isolated enforcing host before migrating services.
Firewall and shared-network/DNS policy remain separate phases.
