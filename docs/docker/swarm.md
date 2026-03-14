# Docker Swarm

The `docker` role includes tasks that:

1) Initiate Docker Swarm on the target management machine
2) Join target worker (and additional manager) nodes to the Swarm
3) Create an overlay Docker network for internal app communication

These Swarm tasks make use of group_vars and run tags during the init and join process:

- `docker_swarm_primary_manager` (group_var - designates the primary Swarm manager)
- `skynet raw --tags docker_swarm` (Initiates and then joins managers and workers)
- `skynet limit (target_host) raw --tags docker_swarm_init` (Initiates the Swarm on a single manager)
- `skynet limit (target_host) raw --tags docker_swarm_join` (Joins a single worker or manager to the Swarm)
- `skynet raw --tags docker_swarm_network` (Creates the Overlay Network. Delegated to the `docker_swarm_primary_manager`)

Swarm managers and workers are defined in the hosts.ini file:

```ini
[swarm_managers]
localhost
mgt

[swarm_workers]
unraid
plex

[swarm:children]
swarm_managers
swarm_workers
```

## Docker Swarm Network

All Swarm/Non-Swarm services are connected to a single Docker overlay network. 

This network allows:

- Backend communication between services across all the Docker Swarm nodes
- No exposed ports at all for most services when combined with Traefik.

The following vars are included in the docker role defaults:

```yaml
docker_network: 'overlay'
docker_network_driver: 'overlay'
docker_network_subnet: '172.98.0.0/24'
```

In the past I used to have a variety of bridge networks to isolate backend communication to services that actually need to communicate with each other. But I cannot be bothered with this now and don't see much upside for doing so.

## Why Swarm?

Why not? It's simple, it's stable and perfect for a Homelab.

I don't need the complications of Kubernetes.

This isn't some study project to get a job, this repo runs my Homelab.

Saying that, this repo supports both Swarm and Non-Swarm services via service vars:

Swarm:

```yml
  deploy:
    type: swarm
```

Non-Swarm:

```yml
  deploy:
    type: container
```

For my use-case, even Swarm is often over-kill, as:

1) I typically only need a single replica - high availability is not too important for most apps
2) Each machine / VM is purpose built with certain services in mind (downloaders on UnRaid, Plex on QuickSync Mini-PC, etc)

Even my high-available Postgres cluster is formed primarily of non-swarm containers with a global HAProxy service.

However, I do enjoy the better Secrets handling of Swarm and I make extensive use of the overlay network across nodes.
