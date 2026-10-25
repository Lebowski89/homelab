# Skynet cheat sheet

Run Skynet from your configured workstation. Services use the Docker or Podman
runtime declared in `ansible/group_vars/all/services/`.

## Find a command or target

```bash
skynet help       # Syntax, aliases and environment overrides
skynet tags       # Available Ansible tags
skynet targets    # Supported role/action targets
```

## Services

| Command | Use |
| --- | --- |
| `skynet check <service>` | Preview deployment changes with check mode and diff |
| `skynet deploy <service>` | Deploy the declared configuration |
| `skynet update <service>` | Apply the service's update operation |
| `skynet recreate <service>` | Run its recreate operation |
| `skynet remove <service>` | Run its removal operation |
| `skynet drift <service>` | Run its drift checks |

Pass multiple service tags, or use `all` for all catalog services:

```bash
skynet check grafana prometheus
skynet update all
```

Check mode is a preview, not proof that deployment will succeed. Ordinary
service lifecycle commands also manage the service's declared firewall
protection; use [firewall operations](../service-firewall.md) for policy-only work.

## Limit to a host or group

Put `limit <host-or-group>` before the command:

```bash
skynet limit mgt check homepage
skynet limit unraid update radarr
```

## Roles and host configuration

Use `skynet targets` to find supported targets and actions:

```bash
skynet check <target> [action]
skynet run <target> [action]
skynet limit pve1 run opentofu pve-user
```

The default action is `deploy`. Only actions listed by the wrapper are supported.

## Bootstrap and recovery

```bash
skynet run workstation credentials  # Set up missing local credential files
skynet run netbox deploy             # Deploy using static bootstrap inventory
skynet run netbox recreate           # Recreate using static bootstrap inventory
skynet limit pve1 bootstrap tailscale
```

NetBox operations use `ansible/inventory/netbox-bootstrap.yml` and the existing
encrypted NetBox Vault file without requiring its API. See
[workstation setup](workstation-setup.md#deploy-or-recover-netbox) for prerequisites.

Tailscale bootstrap uses the selected guest mapping in `ansible/host_vars/pve1.yml`.
It does not support check mode.

## Troubleshooting and local checks

| Command | Use |
| --- | --- |
| `skynet versions` | Show active paths, log location and tool versions |
| `skynet doctor` | Check operator setup and inventory access |
| `skynet doctor --ping` | Also test the configured ping target |
| `skynet inventory` | Show the inventory graph |
| `skynet syntax` | Check playbook syntax |
| `skynet lint` | Run repository linting |
| `skynet ci` | Run lint, configured pytest suite and doctor checks |

For test selection and costs, see [testing](../testing.md).

## Raw Ansible arguments and overrides

```bash
skynet raw --check --diff --tags <tag> -e @/path/to/private-inputs.yml
```

Use `VAULT_PASS_FILE` and `BECOME_PASS_FILE` to override credential-file paths.
Use `PLAYBOOK`, `INVENTORY` and `ANSIBLE_CONFIG` to override execution settings.
See `skynet help` for the complete list; `skynet versions` shows the active paths.

For adding or changing services, see [service definitions](../service-definition-style.md).
