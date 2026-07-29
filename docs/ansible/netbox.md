# NetBox Dynamic Inventory

This homelab uses NetBox as the infrastructure source of truth for Ansible inventory.

Traditional Ansible inventory management via `hosts.ini` has been replaced with a dynamic inventory powered by the `netbox.netbox.nb_inventory` plugin.

---

## Why NetBox?

Using NetBox eliminates duplicated infrastructure data across:

- `hosts.ini`
- `group_vars`
- Terraform/OpenTofu
- DNS records
- documentation

Instead, inventory metadata is centrally managed and dynamically exposed to Ansible.

# Migration steps - `hosts.ini` to NetBox

Here are the actual steps I took to replace my `hosts.ini` driven inventory with NetBox.

---

## Inventory groups to NetBox tags

Most former `hosts.ini` groups were replaced with NetBox tags.

Tags are created in NetBox under:

```text
Customization → Tags
```

Child groups from `hosts.ini` were replaced with broader parent-style tags. For example, instead of recreating this directly:

```ini
[swarm:children]
swarm_managers
swarm_workers
```

I created a broad `swarm` tag and also kept the more specific `swarm_manager` and `swarm_worker` tags.

---

## Original `hosts.ini`

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

---

## NetBox tags

The replacement NetBox tags are:

- `skynet`
- `ansible_manager`
- `docker`
- `docker_install`
- `swarm`
- `swarm_manager`
- `swarm_worker`
- `haproxy`
- `postgres`
- `opentofu`
- `opentofu_install`
- `opentofu_managed`
- `opentofu_pve_user`

These tags are assigned to the relevant hosts/devices within NetBox.

---

## Tags to Ansible groups

The NetBox inventory plugin creates Ansible groups from NetBox tags by prefixing them with `tags_`.

| NetBox tag | Ansible group |
|---|---|
| `skynet` | `tags_skynet` |
| `ansible_manager` | `tags_ansible_manager` |
| `docker` | `tags_docker` |
| `docker_install` | `tags_docker_install` |
| `swarm` | `tags_swarm` |
| `swarm_manager` | `tags_swarm_manager` |
| `swarm_worker` | `tags_swarm_worker` |
| `haproxy` | `tags_haproxy` |
| `postgres` | `tags_postgres` |
| `opentofu` | `tags_opentofu` |
| `opentofu_install` | `tags_opentofu_install` |
| `opentofu_managed` | `tags_opentofu_managed` |
| `opentofu_pve_user` | `tags_opentofu_pve_user` |

---

## Pointing playbooks and tasks to new NetBox tags

The main playbook changed from:

```yaml
hosts: skynet
```

to:

```yaml
hosts: tags_skynet
```

Host group conditionals changed from static inventory group lookups:

```yaml
inventory_hostname in groups['docker']
```

to checking the current host's dynamic group membership:

```yaml
"'tags_docker' in group_names"
```

`group_names` is an Ansible magic variable. It contains the list of groups the current host belongs to during play execution.

For example, a Postgres host may have:

```yaml
group_names:
  - device_roles_server
  - tags_opentofu
  - tags_opentofu_managed
  - tags_postgres
  - tags_skynet
```

Direct group lookups still work, but the group name now includes the `tags_` prefix.

For example, this old lookup:

```yaml
"http://{{ hostvars[groups['postgres'][0]].local_ip }}:{{ postgres_patroni_restapi_port }}/cluster"
```

became:

```yaml
"http://{{ hostvars[groups['tags_postgres'][0]].local_ip }}:{{ postgres_patroni_restapi_port }}/cluster"
```

For the most part, the migration was about replacing old static group names with the new NetBox-generated `tags_*` group names.

---

## NetBox inventory file

The real `netbox.yml` file is not committed because it contains my private NetBox endpoint and API token.

Instead, the repo includes:

```text
netbox.yml.sample
```

To use the repo, copy the sample:

```bash
cp netbox.yml.sample netbox.yml
```

Then update the real local file:

```yaml
api_endpoint: https://your-netbox-url.example.com
token: your-netbox-api-token
```

The real `netbox.yml` is ignored by Git.

---

## Required NetBox custom fields

The following custom fields are expected on NetBox devices:

| Name | Type | Purpose |
|---|---|---|
| `tailscale_ip` | Text | Primary Ansible connection address |
| `ansible_user` | Text | SSH username |
| `ssh_port` | Text | SSH port |
| `container_host_puid` | Text | Runtime-neutral default container process UID |
| `container_host_pgid` | Text | Runtime-neutral default container process GID |
| `container_host_appdata_root` | Text | Absolute root for persistent application configuration |
| `container_host_data_root` | Text | Absolute root for shared or bulk service data |

These are used by the dynamic inventory `compose` block to build standard Ansible connection variables:

```yaml
compose:
  ansible_host: custom_fields['tailscale_ip'] | default(primary_ip4.address | regex_replace('/.*', ''), true)
  ansible_user: custom_fields['ansible_user'] | default('mgt', true)
  ansible_port: custom_fields['ssh_port'] | default('22', true)
```

The OpenTofu module under `terraform/netbox` owns these custom-field definitions and their per-host values. NetBox is the source of truth, and the dynamic inventory is the consumer. The canonical fields preserve the former working Text representation under runtime-neutral names and may remain empty for devices where a default does not apply.

The runtime-neutral migration is complete: inventory reads the four canonical custom fields directly, and the superseded Docker-named fields are no longer defined or exported. Runtime selection remains in service definitions, and service-specific storage remains application configuration.

---

## Updating Skynet to use NetBox

The Skynet wrapper script was updated to use the NetBox inventory file by default.

From:

```bash
INVENTORY="${INVENTORY:-{{ ubuntu_ansible_path }}/hosts.ini}"
```

to:

```bash
INVENTORY="${INVENTORY:-{{ ubuntu_ansible_path }}/netbox.yml}"
```

The wrapper also gained an inventory helper command:

```bash
skynet inventory
```

and:

```bash
skynet inventory --list
```

This makes it easier to inspect the generated NetBox inventory without manually calling `ansible-inventory`.

---

## Validating the migration

After the dynamic inventory was configured, I validated it with:

```bash
ansible-inventory -i netbox.yml --graph
```

Then tested connectivity:

```bash
ansible tags_skynet -i netbox.yml -m ping
```

And checked the Skynet wrapper:

```bash
skynet doctor --ping
```

Useful additional checks:

```bash
ansible tags_postgres -i netbox.yml -m debug -a "var=group_names"
ansible tags_swarm -i netbox.yml -m debug -a "var=group_names"
ansible tags_ansible_manager -i netbox.yml -m debug -a "var=ansible_connection"
```

---

## Removing `hosts.ini`

After the dynamic inventory was tested successfully, `hosts.ini` was no longer required for normal operation.

It can be removed or kept only as a temporary fallback during the migration.

NetBox is now the source of truth for:

- Host inventory
- Host grouping
- Tailscale IP addresses
- SSH users
- Infrastructure metadata
- Role/group membership
