# LMDE workstation setup

The workstation automation supports Linux Mint Debian Edition 7 on its Debian
13 base with Cinnamon, systemd, APT, and NetworkManager. It runs locally and is
separate from the NetBox inventory and Ubuntu server role.

## Fresh installation

Install Git, clone this repository, and run the thin bootstrap:

```bash
sudo apt update
sudo apt install git ca-certificates
git clone https://github.com/Lebowski89/homelab.git
cd homelab
sudo ./scripts/bootstrap-workstation.sh
```

The bootstrap installs only enough Debian packages to execute the real Ansible
configuration. Apply the complete workstation role with:

```bash
ansible-playbook -i localhost, ansible/workstation.yml --ask-become-pass --tags workstation
```

The first complete run creates a pinned project Ansible virtual environment
under `~/.local/share/homelab/ansible-venv` and installs the repository's
declared collections beneath `~/.local/share/ansible/collections`. See the
[role README](../ansible/roles/workstation/README.md) for the subsequent-run
and Skynet commands, configurable variables, and granular tags.

## Scope and manual migration

NetworkManager retains full control of networking. The role does not install
or configure Netplan and does not manage Wi-Fi networks or credentials. It
also leaves SSH keys and client configuration, VS Code settings, Cinnamon
customization, browser data, personal files, and secrets untouched.

Move existing SSH keys manually using a secure out-of-band method, preserve
their restrictive permissions, and verify host keys before first use. Do not
add private keys to this repository.
