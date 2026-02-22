# Infrastructure (Homelab) as Code

+ Driven by Ansible and Docker Swarm
+ Infisical for Secrets Management
+ Authelia and Traefik for SSO/Reverse Proxy
+ HA PostgreSQL (Patroni + etcd) as primary database storage
+ A large focus on media-centric services (especially arrs and companion apps).

## Goals

+ To automate the deployment of docker apps/services (using Ansible/Infisical/Docker Swarm, etc)
+ To automate all settings/configs/database needs I have for an app/service during a single run
+ To be able to run this role on a fresh OS/VM and have an app/service deploy with my settings each time.

Detailed documentation is available in the `docs` folder.