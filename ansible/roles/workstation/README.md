# Workstation role

This role manages the Linux Mint Debian Edition 7 workstation baseline from
the repository and Ansible controller on `mgt`. The target must be a
Debian-family system using APT and systemd. NetworkManager remains the owner of
workstation networking.

The role installs baseline and general development packages, official
Microsoft Visual Studio Code packages and selected extensions, an optional Git
identity, and basic user directories. It also sets the configured timezone.
It does not install a homelab Ansible virtual environment or collections on
the workstation.

## Inventory and execution

The main `ansible/playbook.yml` dispatches this role to hosts in the
NetBox-generated `tags_workstation` group. From `mgt`, the normal operation
is:

```bash
skynet raw --tags workstation --limit blacktop
```

Podman is a separate role and operation:

```bash
skynet raw --tags podman_install --limit blacktop
```

The role defaults `workstation_user` from the existing `ansible_user`
inventory connection identity. It validates that account with getent and
derives its UID, GID, and home. Package, repository, and timezone changes use
privilege escalation; user files and commands use that resolved workstation
account.

Available workstation tags are `workstation`, `workstation_apt`,
`workstation_dev`, `workstation_vscode`, `workstation_shell`, and
`workstation_desktop`. The broad tag selects the complete role. Each granular
tag selects shared platform/user validation plus its relevant section.

## Configuration

NetBox remains the source of truth for the connection user, SSH port,
management address, LAN primary IP, tags, and container-host defaults.
Role-specific behavior remains configurable through role defaults:

* `workstation_vscode_extensions` controls extensions installed as the
  workstation user. The defaults cover Ansible, Python, and Remote SSH.
* `workstation_git_manage_config` defaults to `false`. Set it to `true` and
  provide non-empty `workstation_git_user_name` and
  `workstation_git_user_email` values to manage only an identity block in
  `~/.gitconfig`.

## Connectivity boundary and exclusions

Before the role can run, a fresh workstation needs an existing sudo-capable
local user, Python, SSH reachability, any required Tailscale enrolment, and
corresponding NetBox inventory data. These one-time connectivity prerequisites
are intentionally not bootstrapped by the role.

The role does not manage NetworkManager connections, Wi-Fi credentials,
Netplan, SSH server state, SSH keys or client configuration, Tailscale
authentication secrets, VS Code user settings, Cinnamon preferences, browser
data, personal files, or other secrets.
