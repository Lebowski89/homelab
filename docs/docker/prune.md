# Docker Prune

The `docker` role includes three housekeeping tasks that:

1) Prune dangling Docker images (untagged images)
2) Prune unused Docker images (images not associated with any service (including those in use or stopped))
3) Prune unused Docker volumes (removes all unused local Docker volumes)

These functions are accessed via the use of the following run-tags:

- `skynet raw --tags docker_prune` (Run all three tasks)
- `skynet raw --tags docker_prune_dangling` (Prune dangling images)
- `skynet raw --tags docker_prune_unused` (Prune unused images)
- `skynet raw --tags docker_prune_volumes` (Prune unused volumes)
- `skynet limit (target_host) raw --tags docker_swarm_prune` (Run all prune tasks on a single host)
- `skynet limit (target_host) raw --tags docker_swarm_prune_dangling` (Run one prune task on a single host)

Due to their destructive/situational nature/potential for data loss, these tasks are excluded from the `docker` tag.

Note: I prefer bind mounts whenever. If you're someone who heavily utilises local Docker volumes, you'd probably take more precautions about removing unused volumes.
