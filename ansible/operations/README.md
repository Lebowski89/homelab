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

Use the existing `skynet check/install/remove` firewall commands and
`skynet run mgt-firewall observe`. All original overrides remain supported.
Completed Swarm-only Loki/Prometheus route/scrape tags fail explicitly; their
sources/tests are archived. Do not replay them against migrated services.

See [ownership and compatibility](../../docs/service-firewall.md),
[shared tasks](../tasks/README.md), and [executable tools](../operator/README.md).
Independent `bootstrap.yml` remains the inventory/credential-provider recovery
entry point. No live use is authorised merely by retaining a workflow.
