# Operator workstations

Blacktop (LMDE) is the first operator workstation. In Ansible terminology it
acts as a control node; its inventory identity remains a workstation. Ansible
and Skynet execute on the workstation and SSH directly to managed hosts. `mgt` remains the
application controller host; it is not a proxy for workstation command execution.
See [the transition runbook](workstation-transition.md) for provisioning, private
handoff, acceptance, recovery, state ownership, switching and rollback.

The existing `workstation` role owns both the desktop baseline and a separate
workstation-tooling entry point, `tasks/tools.yml`. Ubuntu's legacy tooling
tags call that entry point without invoking desktop tasks. The `opentofu` role
retains Proxmox API-user configuration and forwards its installation entry point
to the workstation-owned installer. No server tuning or networking moves with
the workstation tooling.

## Supported platforms and prerequisites

The same role has Debian and Fedora package paths. Supported provisioning targets
are Debian/Ubuntu/LMDE using APT and systemd (Blacktop is LMDE 7 / Debian 13), and
conventional Fedora Desktop/KDE installations using DNF or DNF5 and systemd.
Fedora support is for the ordinary mutable installation, not every Fedora
derivative. Fedora 43/44 package conventions informed this implementation; actual
installation acceptance on the future workstation is still required.

Before any changes, every selected role entry checks gathered OS/package-manager
facts and `/run/ostree-booted`. Bazzite, Fedora Atomic variants such as Kinoite and
Silverblue, OSTree-booted hosts, non-Fedora RPM derivatives and unsupported package
managers fail before package installation. This role does not implement rpm-ostree,
bootc image changes, layering or a container-based workaround.

Initial operator preparation must provide an existing non-root user with sudo,
working system Python, the checkout and an Ansible bootstrap environment (Python
3.12 or newer, compatible with the pinned requirements) capable
of running the repository's pinned dependencies. Debian needs `python3-apt` for
APT modules; Fedora needs the system Python bindings matching its package manager
(`python3-libdnf5` for DNF5, `python3-dnf` for DNF). Use the system interpreter for
managed-host package modules, keeping the user-owned Ansible venv separate.
SSH connectivity, verified host keys and any Tailscale enrollment remain external
prerequisites when provisioning remotely. NetBox remains authoritative for those
connection and identity values.

`packages.yml` dispatches to `ansible.builtin.apt` or `ansible.builtin.dnf` from
the validated facts. Role defaults supply platform package profiles: for example,
Debian uses `openssh-client`, `python3-venv`, `python3-dev` and `build-essential`,
while Fedora uses `openssh-clients`, its normal Python venv module,
`python3-devel`, `gcc` and `make`. Shared tasks retain user identity, Git settings,
directories, repository preservation, dependency pins and collection installation.
Python's venv scheme determines the library directory rather than assuming `lib`
instead of `lib64`. Fedora uses `/etc/localtime`; Debian also retains `/etc/timezone`.

Package tasks use `state: present` with explicit package lists. Refreshing metadata
does not request a distribution upgrade. Empty package overrides skip installation;
invalid lists and the global `*` package selector are rejected. Check mode validates
configuration and shows requested package/tool plans, skipping package-manager,
repository, signing-key and download operations, pip/Galaxy installation, and
VS Code commands. These plans do not prove package availability or convergence.

## Inventory and host overrides

NetBox supplies `ansible_user`, SSH address/port, primary LAN address, host roots
and UID/GID values. `workstation_user` defaults to that connection user. Do not
repeat NetBox-owned identity or addressing in host variables.

`ansible/host_vars/blacktop.yml` enables workstation tooling and selects
`<user-home>/src/homelab`. Put workstation-specific role overrides in the
corresponding host file when NetBox does not already cover them. For an existing
checkout or worktree, override `workstation_repository_path` with its
absolute path. The role resolves the user's home and GID through getent; it does
not create or rename accounts.

## Independently selectable tooling

Use `ansible/workstation.yml` for provisioning without the service catalog or
NetBox service-host contract. Main-playbook workstation tags remain available.

| Tag | Behaviour |
| --- | --- |
| `workstation_tools` | Enabled workstation tools, in dependency order |
| `workstation_repository` | Preserve an existing checkout; clone only if explicitly enabled and destination absent |
| `workstation_ansible` | Python prerequisites, managed venv/ABI recovery and pinned `ansible/requirements.txt` dependencies |
| `workstation_collections` | Pinned `ansible/requirements.yml` collections in the configured collection path |
| `workstation_skynet` | Local wrapper, no credential values or inventory queries |
| `workstation_opentofu` | Platform package installer only; no Proxmox API-user work or infrastructure operations |

`workstation_tools_enabled` defaults to false and is enabled for Blacktop.
Venv, collections and Skynet switches default to true. OpenTofu installation and
repository cloning default to false; enable them explicitly with
`workstation_opentofu_enabled` and
`workstation_repository_clone`. Granular collection installation
requires the venv and checkout to exist first. Granular venv installation needs
the checkout's pinned requirements. Check mode skips Python/collection downloads
and OpenTofu installation; it does not prove those components are installed.

Tooling tasks are grouped under `tasks/tools/`, selected by `tasks/tools.yml`.
Shared platform and package tasks remain at the top level.

OpenTofu package installation is now in `tasks/tools/opentofu.yml` with
`workstation_opentofu_*` defaults. Defaults select `tofu=1.11.*` on Debian or
`tofu-1.11.*` on Fedora, matching
all committed `~> 1.11.0` constraints. An absent compatible package is an error;
there is no fallback to a newer minor version. Installing the binary does not
approve state or infrastructure operations.

Debian retains the vendor APT source and two signing keys, with an idempotent
dearmor step when the downloaded repository key changes or its binary is missing.
Fedora uses the vendor RPM source with both keys, package-signature verification
and TLS verification. The RPM source's metadata-signature setting follows the
vendor instructions; package signatures remain required. Upstream also documents
Fedora's native `opentofu` package; the vendor `tofu` package is chosen here to
request the required 1.11.x line explicitly. Failure to find a compatible version
does not fall back to the latest release. Installation guidance:
[OpenTofu Debian](https://opentofu.org/docs/intro/install/deb/),
[OpenTofu RPM](https://opentofu.org/docs/intro/install/rpm/),
[OpenTofu Fedora](https://opentofu.org/docs/intro/install/fedora/).

VS Code uses Microsoft's signed Debian source on Debian and its signed RPM
repository on Fedora; extension management remains common and runs as
`workstation_user`. Repository and key formats stay platform-specific, following
[Microsoft's Linux installation guidance](https://code.visualstudio.com/docs/setup/linux).

## Paths and command compatibility

| Purpose | Workstation default |
| --- | --- |
| Checkout | `<home>/homelab`; Blacktop overrides to `<home>/src/homelab` |
| Virtualenv | `<home>/.local/share/homelab/ansible-venv` |
| Collections | `<home>/.local/share/homelab/collections` |
| Skynet | `<home>/.local/bin/skynet` |
| Private configuration/password-file directory | `<home>/.config/homelab` |
| Log | `<home>/.local/state/homelab/ansible.log` |

All paths have `workstation_*` overrides in role defaults. Existing
repositories and Git worktrees are never fetched, checked out, reset or switched
to `main`, including when optional cloning is enabled. The clone version applies
only to a new absent destination. An existing invalid destination fails without
being modified. Requirements and collections are consumed from that chosen
checkout rather than a fixed machine-wide path.

Skynet retains its commands and environment overrides: `PLAYBOOK`, `INVENTORY`,
`REPO_ROOT`, `ANSIBLE_CONFIG`, `ANSIBLE_VENV_PATH`, `ANSIBLE_COLLECTIONS_PATH`,
`ANSIBLE_LOG_PATH`, password-file paths, service directories and binary overrides.
`REPO_ROOT` selects the default playbook, inventory and config; a supplied
`PLAYBOOK` still derives its repository root when `REPO_ROOT` is unset.
`skynet run workstation tools`, `ansible` (or `venv`), `collections`, `skynet`, `repo`, and
`opentofu` dispatch through the workstation-only playbook. `WORKSTATION_PLAYBOOK`
can override that entry point. Other established role/service commands remain.
No command wraps SSH to `mgt` to run Ansible there.

The legacy Ubuntu adapter retains `/opt/homelab`, `/opt/ansible/ansible-venv`,
repository collections, `/usr/local/bin/skynet` and existing `ubuntu_*` command tags. `ubuntu_requirements` continues to select Python dependencies and
collections. Existing clones are now preserved instead of updated, intentionally.
The `mgt` managed-host interpreter remains in its host vars for application
preparation and PostgreSQL hooks, independently of the executing workstation.
Do not remove that interpreter during tooling retirement without separately
replacing and validating those host dependencies.

## Per-machine options and commands

Keep OS-level package defaults in the role. Blacktop's existing host file enables
tooling and chooses its checkout; it does not duplicate NetBox user/address data.
For the future conventional Fedora KDE workstation, add options to
`ansible/host_vars/<actual-inventory-hostname>.yml` once that identity is known:

```yaml
workstation_tools_enabled: true
workstation_repository_path: "{{ workstation_user_home }}/src/homelab"
workstation_repository_clone: false  # preserve the existing checkout/worktree
workstation_ansible_enabled: true
workstation_ansible_collections_enabled: true
workstation_skynet_enabled: true
workstation_opentofu_enabled: true   # binary installation only; state gate remains
workstation_vscode_enabled: true
workstation_git_manage_config: false
# An empty list can opt out of an optional package group on this machine:
# workstation_desktop_packages: []
```

No Fedora hostname, user, IP address, extra controller role or inventory category
is introduced by this example. Override `workstation_user` only when the tooling
owner intentionally differs from the NetBox connection user. Effective package
lists (`workstation_packages`, `workstation_dev_packages`,
`workstation_desktop_packages`, `workstation_ansible_prereq_packages`) can be
overridden per host without changing another platform's defaults.

After the explicit private handoff and authorised connectivity setup, existing
commands remain available for either platform:

```bash
skynet limit blacktop run workstation ansible
skynet limit blacktop run workstation collections
skynet limit blacktop run workstation skynet
skynet limit blacktop run workstation opentofu
```

The last command requires `workstation_opentofu_enabled: true`. The historical
`workstation_apt` tag continues to select baseline packages on either platform,
using DNF on Fedora. Other existing `workstation_*` tags keep their selection
behaviour. These inventory-backed commands are later operator actions, not
offline validation; check mode still requires a connection to the selected host.
For fresh local provisioning without NetBox, use `ansible/workstation.yml` with
an explicit single-host local inventory, `workstation_hosts`, `ansible_user`,
and the existing checkout path as shown in the transition runbook. Apply that
same pattern to the Fedora workstation's actual hostname.

Workstations execute their own tooling and SSH directly to managed hosts.
`services_controller_host` still names the application host: mgt retains service
placement, runtime accounts and delegated operations. The unresolved OpenTofu
state-transition gate in the runbook is unchanged.

## Desktop scope

The pre-existing baseline still manages timezone, platform/development packages,
VS Code, optional Git identity, shell and XDG directories. NetworkManager retains
workstation networking. No Wi-Fi, Netplan, SSH credentials, personal settings,
server sysctl, firewall or runtime-account changes are part of workstation setup.
Gaming software, graphics drivers, desktop replacement and performance tuning
are outside this role change.

Generated role READMEs remain owned by Docsible and the repository's
`.github/workflows/ansible-docs.yml` workflow. Do not hand-edit them. Once Docsible
is available, run only `docsible --role ansible/roles/workstation --comments
--output README.md` and the equivalent commands for `ubuntu` and `opentofu`,
then inspect diffs. Docsible was unavailable during this preparation; generated
READMEs have not been refreshed.

## Platform-extension validation

This extension preserves the existing transition edits and Blacktop host options.
Changed role files group into platform validation/package dispatch (`platform.yml`,
`packages.yml`, `apt.yml`, `dnf.yml`, defaults and common baseline tasks), shared
Ansible/VS Code/OpenTofu entry points, and Debian/Fedora repository installers.
The retained OpenTofu role forwards check mode as well as installation to the
workstation entry point. Tests extend `test_workstation.py`,
`test_workstation_tooling.py` and `test_ubuntu_netplan.py`; the transition runbook
links to these platform prerequisites. Generated READMEs remain unchanged.

Repository-only checks for this extension:

- `/opt/ansible/ansible-venv/bin/python -m pytest tests/unit/test_workstation.py tests/unit/test_workstation_tooling.py tests/unit/test_ubuntu_netplan.py tests/unit/test_services_host_contract.py tests/unit/test_netbox_workstation.py --basetemp /tmp/homelab-fedora-workstation/final --tb=short -q`: **152 passed**.
- `/opt/ansible/ansible-venv/bin/python -m pytest tests/unit -m 'not integration' --basetemp /tmp/homelab-fedora-workstation/fast --tb=short -q`: **2,034 passed**. The venv was first on PATH, with a task-specific `/tmp` directory.
- `/opt/ansible/ansible-venv/bin/ansible-lint --offline ansible/roles/workstation ansible/roles/opentofu/tasks/sub_tasks/install.yml`: passed.
- `/opt/ansible/ansible-venv/bin/yamllint ansible/roles/workstation`: passed.
- `/opt/ansible/ansible-venv/bin/ruff check` and `ruff format --check` on the three affected test files: passed. Installed Ruff 0.17.1 matches the repository pin.
- Localhost-only `ansible-playbook -i localhost, <playbook> --syntax-check`: passed for `workstation.yml`, `playbook.yml` and `bootstrap.yml`, using an orchestration mirror under `/tmp/homelab-fedora-workstation/syntax` without private inventory or group_vars/Vault inputs.
- `git diff --check` and local documentation-link checks: passed.

The configured venv contains Ansible 2.21.4 versus pinned 2.21.5, and ansible-lint
26.8.0 versus pinned 26.10.1. Those available versions ran successfully; exact
pinned-version validation remains outstanding. No dependencies were installed
or upgraded. Docsible remains unavailable and was not run. The unrelated full
subprocess integration suite was not repeated after the previous Go/tooling and
temporary-quota failures recorded in the transition runbook.

Platform tests execute real Ansible selection and rendering with fake host
operations. They prove routing, options, shared-user ownership, feature selection,
check-mode isolation and rejection before mutation; they do not establish that
packages actually install or converge on Fedora/LMDE. A separately authorised
installation/second-run acceptance on the real machines remains the next step.
No live hosts, infrastructure APIs, credential stores, databases or container
runtimes were contacted; external access was limited to public upstream
installation documentation. No private credentials or state were accessed, and
nothing was staged, committed, pushed, deployed or applied.

Suggested commit title: `feat(workstation): support Debian and Fedora provisioning`.
