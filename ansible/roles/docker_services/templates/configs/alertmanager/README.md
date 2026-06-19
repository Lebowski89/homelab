# Alertmanager alert flow

Alert flow is intentionally small and boring for the first rollout:

```text
Prometheus -> Alertmanager -> alertmanager-gotify-bridge -> Gotify
```

## Secrets

`alertmanager-gotify-bridge` reads the Gotify application token from its env file. The env file is rendered by Ansible from the Infisical secret:

- path: `/Gotify`
- name: `ALERTMANAGER_TOKEN`
- rendered variable: `GOTIFY_TOKEN`

No Gotify token value should be committed to this repository.

## Enabled rule files

Prometheus currently renders and loads only these rule files:

- `infrastructure.yml`
- `applications.yml`

The enabled rules only use metrics from scrape jobs defined in `prometheus.yml.j2`:

- `up` for Prometheus, Alertmanager, and alertmanager-gotify-bridge target health
- `alertmanager_gotify_bridge_gotify_up` from alertmanager-gotify-bridge `/metrics`
- `traefik_service_requests_total` from the Traefik scrape target
- `haproxy_server_up` from the HAProxy scrape target

The Gotify bridge `/metrics` endpoint is documented by the upstream project and exports bridge request counters plus Gotify health metrics.

## Future rules intentionally not enabled yet

The following alert ideas should stay disabled until the matching exporter and exact metric names/semantics are confirmed in this repo's Prometheus setup:

- Docker Swarm desired/running replica mismatch
- container restart loops
- certificate expiry
- backup freshness and absent backup metrics
- Postgres/Patroni leader and replica lag
- ZFS pool health
- SMART disk health/errors
- Uptime Kuma monitor state
- node filesystem disk usage via node_exporter

When enabling backup freshness, include both stale and absent-metric alerts. When enabling SMART/ZFS alerts, prefer current failing state or explicit counters over `increase()` on health/status gauges.

## Test alert

After deployment, send a temporary test alert through Alertmanager from a machine that can reach the private Alertmanager endpoint:

```bash
curl -XPOST http://alertmanager:9093/api/v2/alerts \
  -H 'Content-Type: application/json' \
  -d '[{"labels":{"alertname":"TestGotifyNotification","severity":"warning"},"annotations":{"summary":"Test alert from Alertmanager","description":"This verifies Prometheus -> Alertmanager -> Gotify bridge -> Gotify delivery."}}]'
```

## Config validation

Render and validate the alerting templates with:

```bash
ansible/roles/docker_services/scripts/validate-alerting-configs.sh
```

The script first YAML-parses the Alertmanager and Prometheus service definition files, renders the Jinja templates to a temporary directory, then runs:

```bash
promtool check config prometheus.local-validation.yml
promtool check rules rules/infrastructure.yml
promtool check rules rules/applications.yml
amtool check-config alertmanager.yml
```

The Prometheus config check uses a validation-only rendered config whose `rule_files` entry points at the rendered rule directory. Rule files are also validated one at a time so Docker-based validation does not rely on shell glob expansion inside the container.
