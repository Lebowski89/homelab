# Docker Role

This role conducts various Docker-related tasks

- The role is conditionally run on hosts within the `[docker:children]` hosts.ini grouping
- The run tags (detailed below) dictate which tasks are run within the role during a play
- The role makes use of role-specific defaults, group_vars and host_vars (detailed below).

## Docker Install

These tasks install Docker on a target host.

- The install process is an ansible automated version of the official Docker install steps for Ubuntu.
- The majority of variables required for the install are in the role defaults (packages, repo facts, etc).
- The defaults are typically universal across all hosts where I install Docker.

Relevant host.ini groups: `[docker_install]`

Relevant run tags: `docker`, `docker_install`

Relevant host_vars:
  - `docker_manage_user`  # Ensures docker group exists and adds user to it (if bool)
  - `docker_user`         # User to add to the docker group (if `docker_manage_user` is bool).

## Docker Swarm

The `docker` role includes Swarm tasks that:

1) Initiate Docker Swarm on the target management machine
2) Join target worker (and additional manager) nodes to the Swarm
3) Apply Swarm Node labels to hosts
4) Create an overlay Docker network for internal app communication

Relevant hosts.ini groups: 
`[swarm_managers]`
`[swarm_workers]`
`[swarm:children]`

Relevant run tags: 
  - `docker`
  - `docker_swarm`
  - `docker_swarm_init`
  - `docker_swarm_join`
  - `docker_swarm_network`

Relevant group_vars:
  - `docker_swarm_primary_manager`  # Designates the primary Swarm manager

Relevant host_vars:
  - `docker_swarm_node_labels`      # Desired Swarm Node labels for that host.
  - `docker_swarm_hostname`         # Node hostname (used for the node labels task).

Example uses of the run tags

- `skynet raw --tags docker_swarm`                            # Initiates and then joins managers and workers
- `skynet limit (target_host) raw --tags docker_swarm_init`   # Initiates the Swarm on a single manager
- `skynet limit (target_host) raw --tags docker_swarm_join`   # Joins a single worker or manager to the Swarm
- `skynet raw --tags docker_swarm_labels`                     # Sets Swarm node labels for all relevant hosts
- `skynet limit (target_host) raw --tags docker_swarm_labels` # Sets Swarm node labels for one host
- `skynet raw --tags docker_swarm_network`                    # Creates the Docker Overlay network

### Docker Swarm Network

All Swarm/Non-Swarm services are connected to a single Docker overlay network (defined in role defaults). 

This network allows:

- Backend communication between services across all the Docker Swarm nodes
- No exposed ports at all for most services when combined with Traefik.

Previously, I used a variety of bridge networks to restrict backend communication to services that need to communicate, but I cannot be bothered with this now and don't see much upside for doing so. A single Overlay network it is for me.

## Docker Prune

These housekeeping tasks:

1) Prune dangling Docker images (untagged images)
2) Prune unused Docker images (images not associated with any service (including those in use or stopped))
3) Prune unused Docker volumes (removes all unused local Docker volumes)

Relevant run tags:
  - `docker_prune`
  - `docker_prune_dangling`
  - `docker_prune_unused`
  - `docker_prune_volumes`

Due to their destructive/situational nature/potential for data loss, these tasks are excluded from the `docker` tag.

Example uses of relevant run-tags:

- `skynet raw --tags docker_prune`                                     # Run all three tasks
- `skynet raw --tags docker_prune_dangling`                            # Prune dangling images
- `skynet raw --tags docker_prune_unused`                              # Prune unused images
- `skynet raw --tags docker_prune_volumes`                             # Prune unused volumes
- `skynet limit (target_host) raw --tags docker_swarm_prune`           # Run all prune tasks on a single host
- `skynet limit (target_host) raw --tags docker_swarm_prune_dangling`  # Run one prune task on a single host

Note:
- I prefer bind mounts whenever possible and only use an NFS Docker volume for Plex
- Those that heavily utilise local Docker volumes would probably take more precautions when pruning unused volumes.
