# LMDE workstation management

`blacktop` is managed as a normal remote Ansible target from the `mgt`
controller:

```text
mgt / /opt/homelab -> NetBox dynamic inventory -> SSH/Tailscale -> blacktop
```

The repository, Ansible virtual environment, collections, and Skynet wrapper
remain on `mgt`. The workstation does not clone or execute the homelab
repository locally. NetBox supplies its connection identity, addressing,
container-host defaults, and the `skynet`, `workstation`, `podman`, and
`podman_install` tags.

## Controller workflow

From the repository on `mgt`, the normal workstation operation is:

```bash
skynet raw --tags workstation --limit blacktop
```

Podman installation remains independently selectable:

```bash
skynet raw --tags podman_install --limit blacktop
```

These commands use the main `ansible/playbook.yml` and NetBox dynamic
inventory. The workstation role is selected through the generated
`tags_workstation` group; the playbook contains no workstation hostname
special case. See the
[role README](../ansible/roles/workstation/README.md) for granular tags and
configuration.

## Initial connectivity boundary

A fresh LMDE installation needs one-time preparation before configuration can
be initiated from `mgt`:

* an existing local interactive user with sudo capability;
* Python required for normal Ansible module execution;
* SSH reachability from `mgt`;
* Tailscale enrolment and addressing when Tailscale is the management path;
* matching NetBox device, primary LAN IP, connection custom fields, and tags.

This connectivity bootstrap is deliberately external to the workstation role:
the role cannot establish the network and credentials required to execute
itself. Wi-Fi credentials, private SSH keys, Tailscale authentication secrets,
and other personal or bootstrap secrets must stay outside this repository.

## Managed scope

The role manages the timezone, baseline APT and development packages, Visual
Studio Code repository/package/extensions, optional Git identity, shell
directories, and XDG desktop directories. Privileged machine changes run as
root; user-owned changes run as the NetBox-derived Ansible connection user
after the role resolves that account's UID, GID, and home with getent.

NetworkManager retains full control of workstation networking. The role does
not manage NetworkManager connections, Wi-Fi credentials, Netplan, SSH keys or
client configuration, VS Code user settings, Cinnamon customization, browser
data, personal files, or secrets.
