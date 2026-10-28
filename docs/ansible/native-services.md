# Native service configuration

`ansible/roles/native_services` owns Alloy, Node Exporter, Keepalived and native
Technitium. Each has matching files in `tasks/`, `defaults/` and `handlers/`:

| Entry point | Existing variable prefix | Existing tag | Inventory selection |
| --- | --- | --- | --- |
| `alloy` | `alloy_native_` | `alloy_native` | `tags_podman` |
| `node_exporter` | `node_exporter_` | `node_exporter` | `tags_node_exporter` |
| `keepalived` | `keepalived_` | `keepalived` | `tags_keepalived` |
| `technitium` | `technitium_native_` | `technitium_native` | `tags_technitium_native` |

The playbook selects the three files together using standard Ansible role entry
points. For example:

```yaml
ansible.builtin.include_role:
  name: native_services
  tasks_from: alloy
  defaults_from: alloy
  handlers_from: alloy
  apply:
    tags: [alloy_native]
```

Keep the outer task's existing tag and host condition too. There is no default
entry point that installs every service. Separate defaults preserve normal role
default precedence and prevent selecting Node Exporter, for example, from
requiring Alloy's Loki endpoint variables. The scoped entries in
`.ansible-lint-ignore` preserve the existing public prefixes; other naming rules
remain enabled.

Templates are grouped under `templates/alloy/`, `templates/node_exporter/` and
`templates/keepalived/`. Technitium's resolver drop-in remains inline. Handlers
retain their notification names, conditions and service arguments. Installation
procedures stay explicit: package-created Alloy accounts and journal access,
verified Node Exporter archives, Keepalived VRRP/DNS validation, and Technitium's
download-before-resolver-change sequence have different ownership and ordering
requirements, so a shared provisioning abstraction would obscure them.

## Existing operator commands

Skynet command mappings and check-mode dispatch are unchanged:

- `skynet deploy <target>`, `skynet install <target>`, `skynet run <target>` and
  `skynet check <target>` work for `alloy-native`, `node-exporter`,
  `technitium-native` and `keepalived`.
- `skynet run <target> run` retains the existing explicit `run` action.
- `skynet run <target> install` remains available for Alloy, Node Exporter and
  Technitium. Keepalived's explicit actions remain `deploy` and `run`.
- The existing `skynet limit <hostpattern> ...` prefix still limits these commands.

All calls remain at their existing positions in `ansible/playbook.yml`, with the
same fact gathering, host conditions and tag propagation. No supported external
caller of the old role names was found, so the four superseded role directories
were removed without compatibility shims. Their generated READMEs were removed
with those directories; the documentation workflow generates the new role README.

## Phase boundary and deferred observations

This is a structural consolidation. Variables, defaults, rendered contents,
paths, ownership, service names, restart notifications and check-mode conditions
are retained. Alloy, Keepalived and Technitium retain their Debian-family gates;
Node Exporter's existing Linux archive installation has no new OS gate.

Alloy still uses the deprecated `ansible.builtin.apt_repository`. Its deb822
migration is separate work because it requires source cleanup and cache behavior
validation. Existing Technitium check-mode limitations also remain: the role's
resolver/service/installer/readiness steps were not redesigned in this pass.

The next catalogue phase must explicitly define native declarations, selection
and lifecycle semantics before introducing `runtime: native`. These services are
not fed into the container-only loader. OS portability is separate work requiring
package/repository, account, resolver and systemd validation on each intended OS;
Rocky/Fedora support has not been added. Infisical remains Podman bootstrap and
recovery orchestration. PostgreSQL and the other roles are unchanged.
