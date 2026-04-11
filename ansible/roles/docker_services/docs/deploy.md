# Deploy

**Summary:** These tasks template the final compose file and bring up the services (both Swarm and non-Swarm)

## Tasks

**deploy_all:** Iterates through all prepared stacks and deploys each one.

**deploy_config:** Builds the `deploy` section for a service (mode, replicas, resources, constraints, restart/update/rollback policies, labels).

**deploy_one:** Renders stack compose artifacts and deploys a single stack on the effective deploy host.
