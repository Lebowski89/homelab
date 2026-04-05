# Sub-tasks

Purpose:

- `deploy_all.yml`: Iterates through all prepared stacks and deploys each one.
- `deploy_config.yml`: Builds the `deploy` section for a service (mode, replicas, resources, constraints, restart/update/rollback policies, labels).
- `deploy_one.yml`: Renders stack compose artifacts and deploys a single stack on the effective deploy host.
