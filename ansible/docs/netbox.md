# NetBox Dynamic Inventory

This homelab uses NetBox as the infrastructure source of truth for Ansible inventory.

Traditional Ansible inventory management via `hosts.ini` has been replaced with a dynamic inventory powered by the `netbox.netbox.nb_inventory` plugin.

NetBox now manages:

- Host inventory
- Host grouping
- Tailscale IP addresses
- SSH users
- Infrastructure metadata
- Role/group membership

---

## Why NetBox?

Using NetBox eliminates duplicated infrastructure data across:

- `hosts.ini`
- `group_vars`
- Terraform/OpenTofu
- DNS records
- documentation

Instead, inventory metadata is centrally managed and dynamically exposed to Ansible.

Examples:

- `tags_postgres`
- `tags_swarm`
- `tags_swarm_manager`
- `tags_ansible_manager`

These groups are generated automatically from NetBox tags.

---

## Inventory Configuration

The repository uses a dynamic inventory file:

```text
netbox.yml
```

Example:

```yaml
plugin: netbox.netbox.nb_inventory

api_endpoint: https://netbox.example.com
token: "{{ lookup('env', 'NETBOX_TOKEN') }}"

validate_certs: false

interfaces: true
virtual_chassis: false

query_filters:
  - has_primary_ip: 'true'

group_by:
  - device_roles
  - tags

compose:
  ansible_host: "{{ custom_fields['tailscale_ip'] | default(primary_ip4.address | regex_replace('/.*', ''), true) }}"
  ansible_user: "{{ custom_fields['ansible_user'] | default('mgt', true) }}"
  ansible_port: "{{ custom_fields['ssh_port'] | default('22', true) }}"
```

---

## Required NetBox Custom Fields

The following custom fields are expected on NetBox devices:

| Name | Purpose |
|---|---|
| `tailscale_ip` | Primary Ansible connection address |
| `ansible_user` | SSH username |
| `ssh_port` | SSH port |

---

## Tags → Ansible Groups

NetBox tags automatically become Ansible groups.

Example:

| NetBox Tag | Ansible Group |
|---|---|
| `postgres` | `tags_postgres` |
| `swarm` | `tags_swarm` |
| `swarm_manager` | `tags_swarm_manager` |
| `ansible_manager` | `tags_ansible_manager` |

This allows playbooks to use:

```yaml
when: "'tags_postgres' in group_names"
```

instead of maintaining static inventory groups manually.

---

## Useful Commands

Validate inventory:

```bash
skynet inventory
```

Dump full inventory:

```bash
skynet inventory --list
```

Run connectivity test:

```bash
skynet doctor --ping
```

---

## Legacy Inventory

`hosts.ini` has been deprecated and retained only as a temporary fallback during migration.

---

## Migration steps - hosts.ini to Netbox

Here is the actual steps I took to replace my hosts.ini driven inventory with Netbox.

### Inventory groups to Netbox tags

Each inventory group becomes a tag inside Netbox. Tags are found in Netbox in Customization/Tags.

**Hosts.ini:**

```ini
[skynet]
mgt ansible_connection=local ansible_user= ansible_python_interpreter=
unraid ansible_host= ansible_user=
plex ansible_host= ansible_user=
pve1 ansible_host= ansible_user=
pg95 ansible_host= ansible_user=
pg96 ansible_host= ansible_user=
pg97 ansible_host= ansible_user=

[opentofu_install]
mgt

[opentofu_pve_user]
pve1

[opentofu_managed]
pg95
pg96
pg97

[opentofu:children]
opentofu_install
opentofu_pve_user

[ansible_managers]
mgt

[docker_install]
mgt
plex

[swarm_managers]
mgt

[swarm_workers]
unraid
plex

[swarm:children]
swarm_managers
swarm_workers

[docker:children]
docker_install
swarm_managers
swarm_workers

[postgres]
pg95
pg96
pg97

[haproxy]
mgt
plex
unraid
```

**Netbox tags:**

- skynet
- ansible_manager
- docker
- docker_install
- swarm
- swarm_manager
- swarm_worker
- haproxy
- postgres
- opentofu
- opentofu_install
- opentofu_managed
- opentofu_pve_user

These tags are then assigned to relevant hosts (devices) within Netbox.

### Pointing Playbook and tasks to new Netbox tags

For example, the playbook went from:

```yaml
  hosts: skynet
```
to:

```yaml
  hosts: tags_skynet
```

Hosts group conditionals went from:

```yaml
inventory_hostname in groups['docker']
```

to:

```yaml
"'tags_docker' in group_names"
```

Hostvars lookups went from:

```yaml
"http://{{ hostvars[groups['postgres'][0]].local_ip }}:{{ postgres_patroni_restapi_port }}/cluster"
```

to:

```yaml
"http://{{ hostvars[groups['tags_postgres'][0]].local_ip }}:{{ postgres_patroni_restapi_port }}/cluster"
```

And so on. For the most part, it was about adding 'tags_' before the tag name.

### Updating 'Skynet' to use Netbox

Lastly, I updated my Skynet wrapper script to make use of my Netbox.yml file.

From:

```yaml
INVENTORY="${INVENTORY:-{{ ubuntu_ansible_path }}/hosts.ini}"
```

to:

```yaml
INVENTORY="${INVENTORY:-{{ ubuntu_ansible_path }}/netbox.yml}"
```

With some Netbox relevant conditionals added.

### Removing hosts.ini

Once the above steps are completed, Netbox fully replaces the hosts.ini file, and the hosts file can be removed.