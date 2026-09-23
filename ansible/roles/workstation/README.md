# Workstation role

This role provides the initial local workstation baseline for Linux Mint Debian
Edition 7 (Debian 13, Cinnamon). It requires a Debian-family system using APT
and systemd. NetworkManager remains the owner of workstation networking.

The role installs a small package baseline, the repository's Python and
Ansible development environment in the interactive user's home directory,
official Microsoft Visual Studio Code packages and selected extensions, an
optional Git identity, and basic user directories. It also sets the configured
timezone.

## Run locally

From the repository root, bootstrap Ansible and then run the dedicated local
playbook:

```bash
sudo ./scripts/bootstrap-workstation.sh
ansible-playbook -i localhost, ansible/workstation.yml --ask-become-pass --tags workstation
```

After the first complete run, use the role-managed virtual environment:

```bash
ANSIBLE_COLLECTIONS_PATH="$HOME/.local/share/ansible/collections" \
  "$HOME/.local/share/homelab/ansible-venv/bin/ansible-playbook" \
  -i localhost, ansible/workstation.yml --ask-become-pass --tags workstation
```

If `skynet` is already installed, its existing path overrides provide an
equivalent local path without changing the server-oriented defaults:

```bash
PLAYBOOK="$PWD/ansible/workstation.yml" \
INVENTORY="localhost," \
ANSIBLE_CONFIG="$PWD/ansible/ansible.cfg" \
ANSIBLE_VENV_PATH="$HOME/.local/share/homelab/ansible-venv" \
skynet raw --ask-become-pass --tags workstation
```

Available tags are `workstation`, `workstation_apt`, `workstation_dev`,
`workstation_vscode`, `workstation_shell`, and `workstation_desktop`. The broad
`workstation` tag selects every section. Each granular tag also selects shared
platform, variable, and user-account validation.

## Configuration

Override role defaults with `--extra-vars`, a local untracked vars file, or a
future workstation-specific inventory. In particular:

* `workstation_vscode_extensions` controls extensions installed as the
  workstation user. The defaults cover Ansible, Python, and Remote SSH.
* `workstation_git_manage_config` defaults to `false`. Set it to `true` and
  provide non-empty `workstation_git_user_name` and
  `workstation_git_user_email` values to manage only an identity block in
  `~/.gitconfig`.
* `workstation_ansible_venv_path` defaults beneath the user's home rather than
  using the server manager's `/opt/ansible` layout.

The role intentionally does not manage NetworkManager connections, Wi-Fi
credentials, Netplan, SSH server state, SSH keys or client configuration,
VS Code settings, Cinnamon preferences, personal files, or other secrets.
Copy or create SSH private keys manually outside this repository.
