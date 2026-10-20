# Shared tasks and explicitly scoped operations

Files here are task lists, not standalone playbooks. `playbook.yml` includes the
catalogue/host-contract tasks. `operations.yml` supplies the host, privilege and
variable context for the following independently selected operations:

| Task list | Required operation tag |
| --- | --- |
| `mgt-firewall.yml` | One of `mgt_firewall_install`, `mgt_firewall_observe`, `mgt_firewall_check`, `mgt_firewall_remove` |
| `worker-backend-firewall.yml` | One of `worker_backend_firewall_install`, `worker_backend_firewall_check`, `worker_backend_firewall_remove` |
| `haproxy-firewall-preflight.yml` | `haproxy_preflight` |
| `loki-alertmanager-route.yml` | `loki_alertmanager_route` |
| `prometheus-alertmanager-routes.yml` | `prometheus_alertmanager_routes` |
| `prometheus-haproxy-scrape.yml` | `prometheus_haproxy_scrape` |
| `prometheus-scraparr-scrape.yml` | `prometheus_scraparr_scrape` |
| `podman-pasta-signal.yml` | `podman_pasta_signal` (separately approved host prerequisite) |

No operation is selected by default or by `--tags all`. Select the exact tag;
`skynet raw` requires Ansible arguments. For an authorized HAProxy metadata plan,
for example:

```bash
PLAYBOOK=/opt/homelab/ansible/operations.yml \
  skynet raw --tags haproxy_preflight --check \
    -e @/private/reviewed-policy-inputs.json \
    -e haproxy_preflight_output=/private/fresh-candidate.json
```

Use the existing `skynet check/install/remove` firewall role interface and
`skynet run mgt-firewall observe`, with reviewed inputs, for firewall operations. The two small root
firewall wrappers remain compatible with the already installed `skynet`; the
template now selects `operations.yml`. No installed command is updated by this
repository reorganization.

The Loki/Prometheus configuration operations explicitly target existing Docker
Swarm instances. They are useful for future staged transitions, but are **not**
the update path for the migrated rootless mgt instances. Their existing runtime,
identity, acknowledgement and rollback guards remain in the Docker adapter.

Completed Romm diagnosis is archived under `/opt/ansible/migration/`. The pasta
repair task is retained as an explicit prerequisite: it requires reviewed before/after
profile hashes and never runs as part of ordinary application or Podman deployment. `bootstrap.yml` remains a standalone
recovery playbook so inventory/credential-provider recovery does not depend on
these operations or the full service catalogue. Executable support code is
documented separately in [operator/README.md](../operator/README.md).
