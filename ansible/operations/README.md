# Explicit manual operations

These are task lists, not standalone playbooks. `../operations.yml` supplies host,
privilege and variable context. No operation runs by default or with `--tags all`.

| Task list | Exact selector | Purpose |
| --- | --- | --- |
| `mgt-firewall.yml` | `mgt_firewall_install`, `mgt_firewall_check`, `mgt_firewall_observe`, `mgt_firewall_remove` (one) | Canonical service_firewall mgt profile |
| `worker-backend-firewall.yml` | `worker_backend_firewall_install`, `worker_backend_firewall_check`, `worker_backend_firewall_remove` (one) | Canonical service_firewall workers profile |
| `haproxy-firewall-preflight.yml` | `haproxy_preflight` | Bounded metadata/routes for an explicitly prepared provider/caller transition; never ordinary application maintenance |
| `podman-pasta-signal.yml` | `podman_pasta_signal` | Explicitly approved, checksum-guarded host security prerequisite; never implicit deployment |

For an authorised read-only HAProxy plan (`skynet raw` requires Ansible arguments):

```bash
PLAYBOOK=/opt/homelab/ansible/operations.yml \
  skynet raw --tags haproxy_preflight --check \
    -e @/private/reviewed-policy-inputs.json \
    -e haproxy_preflight_output=/private/fresh-candidate.json
```

For routine application maintenance, use `skynet deploy <service>`,
`skynet update <service>` or `skynet recreate <service>`.
Firewall work is separate: `skynet check <firewall-role>` plans installation in
Ansible check mode; `skynet run <firewall-role> check` audits installed protection
without changing it. Use `skynet run mgt-firewall observe` to inspect caller
identities, and the existing install/remove commands only for approved policy
changes. See the [supported firewall commands](../../docs/service-firewall.md#supported-operator-commands)
for private vars-file overrides.
The retired `loki_alertmanager_route`, `prometheus_alertmanager_routes`,
`prometheus_haproxy_scrape` and `prometheus_scraparr_scrape` tags still fail
explicitly. Their Docker patching tasks, filters and reload/recovery helpers have
been removed; direct imports are unsupported. Existing private archives and
rollback material are unchanged. Edit canonical service configuration and use
`skynet update loki` or `skynet update prometheus` through the selected runtime;
ordinary Docker/Swarm deployment and current rootless generation remain supported.

See [ownership and compatibility](../../docs/service-firewall.md),
[shared tasks](../tasks/README.md), and [executable tools](../operator/README.md).
Independent `bootstrap.yml` remains the inventory/credential-provider recovery
entry point. No live use is authorised merely by retaining a workflow.
