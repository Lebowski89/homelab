# Docker Swarm

The `docker` role includes tasks that:

1) Initiate Docker Swarm on the target management machine
2) Join target worker (and additional manager) nodes to the Swarm

These Swarm tasks make use of group_vars and run tags during the init and join process:

- `docker_swarm_primary_manager` (group_var - designates the primary Swarm manager)
- `skynet raw --tags docker_swarm` (Initiates and then joins managers and workers)
- `skynet limit (target_host) raw --tags docker_swarm_init` (Initiates the Swarm on a single manager)
- `skynet limit (target_host) raw --tags docker_swarm_join` (Joins a single worker or manager to the Swarm)

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

# Why Swarm?

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
2) Each machine / VM is purpose built with certain apps in mind (download apps on UnRaid, Plex apps on QuickSync Mini-PC, etc)

Even my high-available Postgres cluster is formed primarily of non-swarm containers with a global HAProxy service.

However, I do enjoy the better Secrets handling of Swarm and I make extensive use of the overlay network across nodes.
