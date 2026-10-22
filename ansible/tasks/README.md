# Shared deployment plumbing

`playbook.yml` owns host contracts/default normalization, catalog selection,
preflight and Docker/Podman dispatch through these task lists. They are not
standalone playbooks. Runtime and application lifecycle ownership stays in the
existing roles.

Manual workflows live under [operations/](../operations/README.md), selected
explicitly through `operations.yml`. Firewall inventory/orchestration and both
implementations belong to [service_firewall](../../docs/service-firewall.md).

Four tiny task forwarders remain here solely for retained external imports:
`mgt-firewall.yml`, `worker-backend-firewall.yml`, `haproxy-firewall-preflight.yml`
and `podman-pasta-signal.yml`. They forward to operations/; they own no behavior.
The completed Swarm-only Loki/Prometheus route/scrape entry lists are archived,
and their old operation tags fail explicitly.
