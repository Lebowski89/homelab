# Fresh workstation setup

Run these steps on the workstation as your normal user with sudo access.
Use Debian/LMDE or conventional Fedora Desktop/KDE, with Python 3.12 or newer.

1. **Get the repository.** Open [homelab on GitHub](https://github.com/Lebowski89/homelab),
   select the branch containing the workstation changes (currently `refactor/workstation`),
   then **Code → Download ZIP** and extract it. Cloning that branch with your Git
   client also works. If you already have a checkout/worktree, use it as-is.

2. **Open a terminal in the repository folder. Install the initial prerequisites.**

   Debian / LMDE:

   ```bash
   sudo apt-get update
   sudo apt-get install git python3 python3-venv python3-pip
   ```

   Fedora — use this instead:

   ```bash
   sudo dnf install git python3 python3-pip
   ```

3. **Set the workstation name and paths.** These commands use Blacktop.
   For another machine, use its actual inventory hostname and add
   `workstation_tools_enabled: true` to `ansible/host_vars/<hostname>.yml`.

   ```bash
   workstation_name=blacktop
   checkout="$PWD"
   bootstrap_venv="$HOME/.local/share/homelab-bootstrap"
   python3 --version
   ```

   Check that Python is 3.12 or newer before continuing.

4. **Install the minimal Ansible needed to run the playbook.**

   ```bash
   python3 -m venv "$bootstrap_venv"
   "$bootstrap_venv/bin/python" -m pip install \
     "$(sed -n '/^ansible-core==/p' "$checkout/ansible/requirements.txt")"
   ```

   Encode the checkout path once, including any spaces:

   ```bash
   workstation_extra_vars="$("$bootstrap_venv/bin/python" -c \
     'import json, sys; print(json.dumps({"workstation_repository_path": sys.argv[1], "workstation_opentofu_enabled": True}))' \
     "$checkout")"
   ```

5. **Test without installing the workstation tools.** Enter your local sudo
   password when prompted. NetBox and application credentials are not needed.

   ```bash
   ANSIBLE_CONFIG="$checkout/ansible/bootstrap.cfg" \
     "$bootstrap_venv/bin/ansible-playbook" \
     -i "$workstation_name," -c local \
     "$checkout/ansible/playbook.yml" \
     -e "workstation_hosts=$workstation_name" \
     -e "$workstation_extra_vars" \
     --tags workstation_tools --check --ask-become-pass
   ```

   Expect `failed=0`. Warnings about missing `tags_service_controller` and
   `tags_skynet` groups are normal here; their application plays are skipped.

6. **Install Ansible, collections, OpenTofu and Skynet.** Same command without
   `--check`:

   ```bash
   ANSIBLE_CONFIG="$checkout/ansible/bootstrap.cfg" \
     "$bootstrap_venv/bin/ansible-playbook" \
     -i "$workstation_name," -c local \
     "$checkout/ansible/playbook.yml" \
     -e "workstation_hosts=$workstation_name" \
     -e "$workstation_extra_vars" \
     --tags workstation_tools --ask-become-pass
   ```

7. **Check the installed commands.**

   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   "$HOME/.local/share/homelab/ansible-venv/bin/ansible-playbook" --version
   tofu version
   skynet targets
   ```

For direct Ansible commands in this terminal:

```bash
source "$HOME/.local/share/homelab/ansible-venv/bin/activate"
ansible --version
```

Skynet uses that venv automatically. OpenTofu (`tofu`) is a system package.

Before remote management, privately configure `ansible/netbox.yml`, the required
encrypted Vault inputs, verified SSH access and the password-file paths under
`~/.config/homelab/` (`.ansible_become_pass` and `.ansible_vault_pass`). Preserve
HTTPS secret-store access and SSH host-key verification.

OpenTofu infrastructure/state operations remain blocked until an authoritative
shared state location and the required private state/variable handoff are resolved.


## Recovery when NetBox is unavailable

Use `ansible/bootstrap.yml` with a private static inventory based on
[`ansible/recovery.yml.sample`](../../ansible/recovery.yml.sample).
Set `ansible_host` to the verified numeric SSH address of the application host:
IPv4, IPv6 or IPv4-mapped IPv6. DNS names, brackets, CIDR suffixes and IPv6 scope
IDs are not supported. Loopback, unspecified and multicast addresses are rejected.
Keep SSH host-key verification enabled.

Fill in the host's numeric `local_ip`, absolute `container_host_appdata_root`,
non-negative UID/GID, DNS `services_internal_zone` and TCP port (1–65535).
These values are checked before either recovery role runs. Supply required
bootstrap secrets separately as encrypted Vault inputs; workstation setup above
needs none of them.
