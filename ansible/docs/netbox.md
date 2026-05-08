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
