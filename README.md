# Infrastructure (Homelab) as Code

+ Driven by Ansible and Docker Swarm
+ Infisical for Secrets Management
+ Authelia and Traefik for SSO/Reverse Proxy
+ HA PostgreSQL (Patroni + etcd) as primary database storage
+ A large focus on media-centric services (especially arrs and companion apps)
## Helper documentation

Detailed documentation for role helpers is available at `roles/docker_services/helpers/README.md`.

## Ansible module inventory (grouped)

Below is a grouped list of Ansible modules currently used in this repository, with short descriptions.

### `ansible.builtin`

| Module | What it is used for |
| --- | --- |
| `ansible.builtin.assert` | Validate assumptions and fail early when inputs/state are invalid. |
| `ansible.builtin.command` | Run commands without shell expansion. |
| `ansible.builtin.copy` | Copy rendered/static content to managed hosts. |
| `ansible.builtin.debug` | Print values/messages for troubleshooting and visibility. |
| `ansible.builtin.fail` | Stop execution with an explicit failure message. |
| `ansible.builtin.file` | Manage file/dir/link state, ownership, and permissions. |
| `ansible.builtin.include_role` | Reuse a role from within another play/task flow. |
| `ansible.builtin.include_tasks` | Dynamically include task files. |
| `ansible.builtin.include_vars` | Load variable files at runtime. |
| `ansible.builtin.package_facts` | Gather installed package information from hosts. |
| `ansible.builtin.pause` | Wait/prompt (for retries, human steps, or timing gaps). |
| `ansible.builtin.set_fact` | Build derived variables during execution. |
| `ansible.builtin.shell` | Run shell commands where shell features are required. |
| `ansible.builtin.slurp` | Read remote file contents as base64 data. |
| `ansible.builtin.stat` | Check remote path/file presence and metadata. |
| `ansible.builtin.template` | Render Jinja2 templates to managed hosts. |
| `ansible.builtin.uri` | Call HTTP APIs/endpoints (for service setup/queries). |
| `ansible.builtin.wait_for` | Wait for ports/files/conditions before continuing. |

### `community.docker`

| Module | What it is used for |
| --- | --- |
| `community.docker.docker_compose_v2` | Manage Docker Compose v2 projects. |
| `community.docker.docker_config` | Manage Docker Swarm configs. |
| `community.docker.docker_container` | Manage one-off or helper containers. |
| `community.docker.docker_secret` | Manage Docker Swarm secrets. |
| `community.docker.docker_stack` | Deploy/update/remove Docker Swarm stacks. |
| `community.docker.docker_volume` | Manage Docker volumes. |

### `community.general`

| Module | What it is used for |
| --- | --- |
| `community.general.cloudflare_dns` | Create/update/delete Cloudflare DNS records. |
| `community.general.ini_file` | Update INI-style configuration files. |
| `community.general.ipify_facts` | Fetch public IP facts via ipify. |
| `community.general.ipinfoio_facts` | Fetch network/location facts via ipinfo.io. |
| `community.general.xml` | Read/update XML documents. |

### `community.postgresql`

| Module | What it is used for |
| --- | --- |
| `community.postgresql.postgresql_db` | Create/drop/manage PostgreSQL databases. |
| `community.postgresql.postgresql_ping` | Check PostgreSQL connectivity/availability. |

### Custom / non-FQCN modules in use

| Module | What it is used for |
| --- | --- |
| `qbittorrent_passwd` | Generate qBittorrent-compatible password hashes in prep tasks. |
| `yedit` | Edit YAML keys/values in-place in existing config files. |

> Notes:
> - This list is derived from module invocations in playbooks and role task files.
> - `qbittorrent_passwd` and `yedit` are used in short-form names in this repo (non-FQCN form).


### Dependency notes (`requirements.yml` vs Python deps)

- `requirements.yml` is for **Ansible Galaxy collections/roles**.
- Some modules also need **Python libraries on the Ansible control node** (for example `community.postgresql.*` needs `psycopg2`).
- Controller-side Python dependencies are listed in `requirements.txt`.

Install both before running playbooks:

```bash
ansible-galaxy collection install -r requirements.yml
pip install -r requirements.txt
```
