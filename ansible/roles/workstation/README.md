<!-- DOCSIBLE START -->

# 📃 Role overview

## workstation





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/10/23 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [workstation_user](defaults/main.yml#L4)   | str | `{{ ansible_user ¦ default((ansible_facts ¦ default({})).get('user_id', '')) }}` |    
| [workstation_timezone](defaults/main.yml#L5)   | str | `Australia/Melbourne` |    
| [workstation_tools_enabled](defaults/main.yml#L8)   | bool | `False` |    
| [workstation_ansible_enabled](defaults/main.yml#L9)   | bool | `True` |    
| [workstation_ansible_collections_enabled](defaults/main.yml#L10)   | bool | `True` |    
| [workstation_skynet_enabled](defaults/main.yml#L11)   | bool | `True` |    
| [workstation_opentofu_enabled](defaults/main.yml#L12)   | bool | `False` |    
| [workstation_repository_clone](defaults/main.yml#L13)   | bool | `False` |    
| [workstation_repository_url](defaults/main.yml#L14)   | str | `https://github.com/Lebowski89/homelab.git` |    
| [workstation_repository_version](defaults/main.yml#L15)   | str | `main` |    
| [workstation_repository_path](defaults/main.yml#L16)   | str | `{{ workstation_user_home }}/homelab` |    
| [workstation_ansible_path](defaults/main.yml#L17)   | str | `{{ workstation_repository_path }}/ansible` |    
| [workstation_ansible_tools_path](defaults/main.yml#L18)   | str | `{{ workstation_user_home }}/.local/share/homelab` |    
| [workstation_ansible_venv_path](defaults/main.yml#L19)   | str | `{{ workstation_ansible_tools_path }}/ansible-venv` |    
| [workstation_ansible_collections_path](defaults/main.yml#L20)   | str | `{{ workstation_ansible_tools_path }}/collections` |    
| [workstation_secrets_path](defaults/main.yml#L21)   | str | `{{ workstation_user_home }}/.config/homelab` |    
| [workstation_become_pass_file](defaults/main.yml#L22)   | str | `{{ workstation_secrets_path }}/.ansible_become_pass` |    
| [workstation_vault_pass_file](defaults/main.yml#L23)   | str | `{{ workstation_secrets_path }}/.ansible_vault_pass` |    
| [workstation_skynet_install_path](defaults/main.yml#L24)   | str | `{{ workstation_user_home }}/.local/bin/skynet` |    
| [workstation_skynet_owner](defaults/main.yml#L25)   | str | `{{ workstation_user }}` |    
| [workstation_skynet_group](defaults/main.yml#L26)   | str | `{{ workstation_user_gid }}` |    
| [workstation_skynet_doctor_ping_target](defaults/main.yml#L27)   | str | `tags_skynet` |    
| [workstation_ansible_log_path](defaults/main.yml#L28)   | str | `{{ workstation_user_home }}/.local/state/homelab/ansible.log` |    
| [workstation_package_profiles](defaults/main.yml#L31)   | dict | `{}` |    
| [workstation_package_profiles.**debian**](defaults/main.yml#L32)   | dict | `{}` |    
| [workstation_package_profiles.debian.**baseline**](defaults/main.yml#L33)   | list | `[]` |    
| [workstation_package_profiles.debian.baseline.**0**](defaults/main.yml#L33)   | str | `ca-certificates` |    
| [workstation_package_profiles.debian.baseline.**1**](defaults/main.yml#L33)   | str | `curl` |    
| [workstation_package_profiles.debian.baseline.**2**](defaults/main.yml#L33)   | str | `gnupg` |    
| [workstation_package_profiles.debian.baseline.**3**](defaults/main.yml#L33)   | str | `jq` |    
| [workstation_package_profiles.debian.baseline.**4**](defaults/main.yml#L33)   | str | `openssh-client` |    
| [workstation_package_profiles.debian.baseline.**5**](defaults/main.yml#L33)   | str | `ripgrep` |    
| [workstation_package_profiles.debian.baseline.**6**](defaults/main.yml#L33)   | str | `rsync` |    
| [workstation_package_profiles.debian.baseline.**7**](defaults/main.yml#L33)   | str | `wget` |    
| [workstation_package_profiles.debian.**development**](defaults/main.yml#L34)   | list | `[]` |    
| [workstation_package_profiles.debian.development.**0**](defaults/main.yml#L34)   | str | `git` |    
| [workstation_package_profiles.debian.development.**1**](defaults/main.yml#L34)   | str | `python3` |    
| [workstation_package_profiles.debian.development.**2**](defaults/main.yml#L34)   | str | `python3-pip` |    
| [workstation_package_profiles.debian.development.**3**](defaults/main.yml#L34)   | str | `python3-venv` |    
| [workstation_package_profiles.debian.**desktop**](defaults/main.yml#L35)   | list | `[]` |    
| [workstation_package_profiles.debian.desktop.**0**](defaults/main.yml#L35)   | str | `xdg-user-dirs` |    
| [workstation_package_profiles.debian.**ansible**](defaults/main.yml#L36)   | list | `[]` |    
| [workstation_package_profiles.debian.ansible.**0**](defaults/main.yml#L36)   | str | `python3` |    
| [workstation_package_profiles.debian.ansible.**1**](defaults/main.yml#L36)   | str | `python3-venv` |    
| [workstation_package_profiles.debian.ansible.**2**](defaults/main.yml#L36)   | str | `python3-pip` |    
| [workstation_package_profiles.debian.ansible.**3**](defaults/main.yml#L36)   | str | `python3-dev` |    
| [workstation_package_profiles.debian.ansible.**4**](defaults/main.yml#L36)   | str | `build-essential` |    
| [workstation_package_profiles.debian.**signing**](defaults/main.yml#L37)   | list | `[]` |    
| [workstation_package_profiles.debian.signing.**0**](defaults/main.yml#L37)   | str | `ca-certificates` |    
| [workstation_package_profiles.debian.signing.**1**](defaults/main.yml#L37)   | str | `gnupg` |    
| [workstation_package_profiles.debian.signing.**2**](defaults/main.yml#L37)   | str | `python3-apt` |    
| [workstation_package_profiles.debian.**opentofu**](defaults/main.yml#L38)   | list | `[]` |    
| [workstation_package_profiles.debian.opentofu.**0**](defaults/main.yml#L38)   | str | `tofu=1.11.*` |    
| [workstation_package_profiles.**fedora**](defaults/main.yml#L39)   | dict | `{}` |    
| [workstation_package_profiles.fedora.**baseline**](defaults/main.yml#L40)   | list | `[]` |    
| [workstation_package_profiles.fedora.baseline.**0**](defaults/main.yml#L40)   | str | `ca-certificates` |    
| [workstation_package_profiles.fedora.baseline.**1**](defaults/main.yml#L40)   | str | `curl` |    
| [workstation_package_profiles.fedora.baseline.**2**](defaults/main.yml#L40)   | str | `gnupg2` |    
| [workstation_package_profiles.fedora.baseline.**3**](defaults/main.yml#L40)   | str | `jq` |    
| [workstation_package_profiles.fedora.baseline.**4**](defaults/main.yml#L40)   | str | `openssh-clients` |    
| [workstation_package_profiles.fedora.baseline.**5**](defaults/main.yml#L40)   | str | `ripgrep` |    
| [workstation_package_profiles.fedora.baseline.**6**](defaults/main.yml#L40)   | str | `rsync` |    
| [workstation_package_profiles.fedora.baseline.**7**](defaults/main.yml#L40)   | str | `wget` |    
| [workstation_package_profiles.fedora.**development**](defaults/main.yml#L41)   | list | `[]` |    
| [workstation_package_profiles.fedora.development.**0**](defaults/main.yml#L41)   | str | `git` |    
| [workstation_package_profiles.fedora.development.**1**](defaults/main.yml#L41)   | str | `python3` |    
| [workstation_package_profiles.fedora.development.**2**](defaults/main.yml#L41)   | str | `python3-pip` |    
| [workstation_package_profiles.fedora.**desktop**](defaults/main.yml#L42)   | list | `[]` |    
| [workstation_package_profiles.fedora.desktop.**0**](defaults/main.yml#L42)   | str | `xdg-user-dirs` |    
| [workstation_package_profiles.fedora.**ansible**](defaults/main.yml#L43)   | list | `[]` |    
| [workstation_package_profiles.fedora.ansible.**0**](defaults/main.yml#L43)   | str | `python3` |    
| [workstation_package_profiles.fedora.ansible.**1**](defaults/main.yml#L43)   | str | `python3-pip` |    
| [workstation_package_profiles.fedora.ansible.**2**](defaults/main.yml#L43)   | str | `python3-devel` |    
| [workstation_package_profiles.fedora.ansible.**3**](defaults/main.yml#L43)   | str | `gcc` |    
| [workstation_package_profiles.fedora.ansible.**4**](defaults/main.yml#L43)   | str | `make` |    
| [workstation_package_profiles.fedora.**signing**](defaults/main.yml#L44)   | list | `[]` |    
| [workstation_package_profiles.fedora.signing.**0**](defaults/main.yml#L44)   | str | `ca-certificates` |    
| [workstation_package_profiles.fedora.signing.**1**](defaults/main.yml#L44)   | str | `gnupg2` |    
| [workstation_package_profiles.fedora.**opentofu**](defaults/main.yml#L45)   | list | `[]` |    
| [workstation_package_profiles.fedora.opentofu.**0**](defaults/main.yml#L45)   | str | `tofu-1.11.*` |    
| [workstation_packages](defaults/main.yml#L47)   | str | `{{ workstation_package_profiles[workstation_platform].baseline }}` |    
| [workstation_dev_packages](defaults/main.yml#L48)   | str | `{{ workstation_package_profiles[workstation_platform].development }}` |    
| [workstation_desktop_packages](defaults/main.yml#L49)   | str | `{{ workstation_package_profiles[workstation_platform].desktop }}` |    
| [workstation_ansible_prereq_packages](defaults/main.yml#L50)   | str | `{{ workstation_package_profiles[workstation_platform].ansible }}` |    
| [workstation_apt_update_cache](defaults/main.yml#L52)   | bool | `True` |    
| [workstation_dnf_update_cache](defaults/main.yml#L53)   | bool | `True` |    
| [workstation_vscode_enabled](defaults/main.yml#L55)   | bool | `True` |    
| [workstation_vscode_key_url](defaults/main.yml#L56)   | str | `https://packages.microsoft.com/keys/microsoft.asc` |    
| [workstation_vscode_key_path](defaults/main.yml#L57)   | str | `/usr/share/keyrings/microsoft-vscode.asc` |    
| [workstation_vscode_repository_path](defaults/main.yml#L58)   | str | `/etc/apt/sources.list.d/vscode.sources` |    
| [workstation_vscode_extensions](defaults/main.yml#L59)   | list | `[]` |    
| [workstation_vscode_extensions.**0**](defaults/main.yml#L60)   | str | `redhat.ansible` |    
| [workstation_vscode_extensions.**1**](defaults/main.yml#L61)   | str | `ms-python.python` |    
| [workstation_vscode_extensions.**2**](defaults/main.yml#L62)   | str | `ms-vscode-remote.remote-ssh` |    
| [workstation_git_manage_config](defaults/main.yml#L64)   | bool | `False` |    
| [workstation_git_user_name](defaults/main.yml#L65)   | str |  |    
| [workstation_git_user_email](defaults/main.yml#L66)   | str |  |    
| [workstation_shell_directories](defaults/main.yml#L68)   | list | `[]` |    
| [workstation_shell_directories.**0**](defaults/main.yml#L69)   | str | `{{ workstation_user_home }}/.local/bin` |    
| [workstation_xdg_directories](defaults/main.yml#L71)   | list | `[]` |    
| [workstation_xdg_directories.**0**](defaults/main.yml#L72)   | str | `{{ workstation_user_home }}/Desktop` |    
| [workstation_xdg_directories.**1**](defaults/main.yml#L73)   | str | `{{ workstation_user_home }}/Documents` |    
| [workstation_xdg_directories.**2**](defaults/main.yml#L74)   | str | `{{ workstation_user_home }}/Downloads` |    
| [workstation_xdg_directories.**3**](defaults/main.yml#L75)   | str | `{{ workstation_user_home }}/Music` |    
| [workstation_xdg_directories.**4**](defaults/main.yml#L76)   | str | `{{ workstation_user_home }}/Pictures` |    
| [workstation_xdg_directories.**5**](defaults/main.yml#L77)   | str | `{{ workstation_user_home }}/Public` |    
| [workstation_xdg_directories.**6**](defaults/main.yml#L78)   | str | `{{ workstation_user_home }}/Templates` |    
| [workstation_xdg_directories.**7**](defaults/main.yml#L79)   | str | `{{ workstation_user_home }}/Videos` |    
| [workstation_opentofu_prereq_packages](defaults/main.yml#L81)   | str | `{{ workstation_package_profiles[workstation_platform].signing }}` |    
| [workstation_opentofu_source_url](defaults/main.yml#L83)   | str | `https://packages.opentofu.org/opentofu/tofu/any/` |    
| [workstation_opentofu_source_suite](defaults/main.yml#L84)   | str | `any` |    
| [workstation_opentofu_keyring_dir](defaults/main.yml#L85)   | str | `/etc/apt/keyrings` |    
| [workstation_opentofu_keyring_file](defaults/main.yml#L86)   | str | `/etc/apt/keyrings/opentofu.gpg` |    
| [workstation_opentofu_keyring_file_repo](defaults/main.yml#L87)   | str | `/etc/apt/keyrings/opentofu-repo.gpg` |    
| [workstation_opentofu_repo_filename](defaults/main.yml#L88)   | str | `opentofu` |    
| [workstation_opentofu_packages](defaults/main.yml#L90)   | str | `{{ workstation_package_profiles[workstation_platform].opentofu }}` |    
| [workstation_opentofu_rpm_baseurl](defaults/main.yml#L91)   | str | `https://packages.opentofu.org/opentofu/tofu/rpm_any/rpm_any/$basearch` |    
| [workstation_opentofu_signing_keys](defaults/main.yml#L92)   | list | `[]` |    
| [workstation_opentofu_signing_keys.**0**](defaults/main.yml#L93)   | str | `https://get.opentofu.org/opentofu.gpg` |    
| [workstation_opentofu_signing_keys.**1**](defaults/main.yml#L94)   | str | `https://packages.opentofu.org/opentofu/tofu/gpgkey` |    
| [workstation_vscode_rpm_baseurl](defaults/main.yml#L95)   | str | `https://packages.microsoft.com/yumrepos/vscode` |    





### Tasks


#### File: tasks/apt.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation APT ¦ Install selected packages | ansible.builtin.apt | False |

#### File: tasks/debian/vscode.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation VS Code ¦ Install repository prerequisites | ansible.builtin.apt | False |
| Workstation VS Code ¦ Install Microsoft signing key | ansible.builtin.get_url | False |
| Workstation VS Code ¦ Configure Microsoft repository | ansible.builtin.copy | False |
| Workstation VS Code ¦ Install Visual Studio Code | ansible.builtin.apt | False |

#### File: tasks/desktop.yml

| Name | Module | Has Conditions | Comments |
| ---- | ------ | -------------- | -------- |
| Workstation Desktop ¦ Install desktop packages | ansible.builtin.include_tasks | False |  |
| Workstation Desktop ¦ Ensure XDG user directories exist | ansible.builtin.file | False | Omitting mode preserves permissions on existing private directories. |

#### File: tasks/development.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation Development ¦ Install development packages | ansible.builtin.include_tasks | False |
| Workstation Development ¦ Manage Git identity block | ansible.builtin.blockinfile | True |

#### File: tasks/dnf.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation DNF ¦ Install selected packages | ansible.builtin.dnf | False |

#### File: tasks/fedora/vscode.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation VS Code ¦ Install Fedora repository prerequisites | ansible.builtin.include_tasks | False |
| Workstation VS Code ¦ Import Microsoft RPM signing key | ansible.builtin.rpm_key | False |
| Workstation VS Code ¦ Configure Microsoft RPM repository | ansible.builtin.yum_repository | False |
| Workstation VS Code ¦ Install Visual Studio Code on Fedora | ansible.builtin.include_tasks | False |

#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Workstation ¦ Configure automation tooling | ansible.builtin.include_tasks | True |  |
| Workstation ¦ Validate configuration and resolve user | ansible.builtin.include_tasks | False |  |
| Workstation ¦ Configure timezone | ansible.builtin.include_tasks | False |  |
| Workstation ¦ Install baseline packages | ansible.builtin.include_tasks | False |  |
| Workstation ¦ Configure development tooling | ansible.builtin.include_tasks | False |  |
| Workstation ¦ Configure Visual Studio Code | ansible.builtin.include_tasks | True |  |
| Workstation ¦ Configure shell directories | ansible.builtin.include_tasks | False |  |
| Workstation ¦ Configure desktop baseline | ansible.builtin.include_tasks | False |  |

#### File: tasks/packages.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation Packages ¦ Validate effective package selection | ansible.builtin.assert | False |
| Workstation Packages ¦ Report check-mode package plan | ansible.builtin.debug | True |
| Workstation Packages ¦ Install selected platform packages | ansible.builtin.include_tasks | True |

#### File: tasks/platform.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation ¦ Detect image-based deployment | ansible.builtin.stat | False |
| Workstation ¦ Reject unsupported host package management | ansible.builtin.assert | False |
| Workstation ¦ Select platform package configuration | ansible.builtin.set_fact | False |

#### File: tasks/shell.yml

| Name | Module | Has Conditions | Comments |
| ---- | ------ | -------------- | -------- |
| Workstation Shell ¦ Ensure user shell directories exist | ansible.builtin.file | False | Omitting mode preserves permissions on existing private directories. |

#### File: tasks/timezone.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation ¦ Check timezone data file | ansible.builtin.stat | False |
| Workstation ¦ Validate timezone data file | ansible.builtin.assert | False |
| Workstation ¦ Set local timezone link | ansible.builtin.file | False |
| Workstation ¦ Record local timezone | ansible.builtin.copy | True |

#### File: tasks/tools.yml

| Name | Module | Has Conditions | Tags | Comments |
| ---- | ------ | -------------- | -----| -------- |
| Workstation Ansible ¦ Validate and resolve ownership | ansible.builtin.import_tasks | False |  | Workstation administration tools, independently selectable from the desktop baseline. |
| Workstation Repository ¦ Install optional clone prerequisites | ansible.builtin.include_tasks | True |  |  |
| Workstation Repository ¦ Preserve or optionally clone checkout | ansible.builtin.include_tasks | True |  |  |
| Workstation Ansible ¦ Install Python virtualenv prerequisites | ansible.builtin.include_tasks | True |  |  |
| Workstation Ansible ¦ Prepare virtualenv and pinned Python dependencies | ansible.builtin.include_tasks | True |  |  |
| Workstation Ansible ¦ Install pinned Ansible collections | ansible.builtin.include_tasks | True |  |  |
| Workstation Skynet ¦ Install local wrapper | ansible.builtin.include_tasks | True |  |  |
| Workstation OpenTofu ¦ Install without infrastructure operations | ansible.builtin.include_tasks | True |  |  |

#### File: tasks/tools/ansible.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation Ansible ¦ Ensure Ansible tooling path exists | ansible.builtin.file | False |
| Workstation Ansible ¦ Determine Python ABI directory | ansible.builtin.command | False |
| Workstation Ansible ¦ Check existing Ansible virtualenv interpreter | ansible.builtin.stat | False |
| Workstation Ansible ¦ Determine virtualenv library directory | ansible.builtin.command | False |
| Workstation Ansible ¦ Check matching Ansible virtualenv site-packages | ansible.builtin.stat | False |
| Workstation Ansible ¦ Probe existing Ansible virtualenv interpreter | ansible.builtin.command | True |
| Workstation Ansible ¦ Recreate Ansible virtualenv after Python ABI drift | ansible.builtin.command | True |
| Workstation Ansible ¦ Create missing Ansible virtualenv | ansible.builtin.command | True |
| Workstation Ansible ¦ Upgrade pip tooling in virtualenv | ansible.builtin.pip | False |
| Workstation Ansible ¦ Install repository-pinned Python requirements | ansible.builtin.import_tasks | False |

#### File: tasks/tools/ansible_collections.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation Ansible ¦ Assert Ansible collections requirements file exists | ansible.builtin.stat | False |
| Workstation Ansible ¦ Fail if Ansible collections requirements file is missing | ansible.builtin.fail | True |
| Workstation Ansible ¦ Install Ansible collections from requirements.yml | ansible.builtin.command | False |
| Workstation Ansible ¦ Locate existing collections after an unchanged installation | ansible.builtin.command | True |
| Workstation Ansible ¦ Explain why collection installation was unchanged | ansible.builtin.debug | True |

#### File: tasks/tools/ansible_python.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation Ansible ¦ Assert requirements.txt exists | ansible.builtin.stat | False |
| Workstation Ansible ¦ Fail if requirements.txt is missing | ansible.builtin.fail | True |
| Workstation Ansible ¦ Install Python packages from requirements.txt | ansible.builtin.pip | False |

#### File: tasks/tools/debian/opentofu.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation OpenTofu ¦ Ensure apt prerequisites are installed | ansible.builtin.apt | False |
| Workstation OpenTofu ¦ Ensure OpenTofu keyring directory exists | ansible.builtin.file | False |
| Workstation OpenTofu ¦ Download OpenTofu package signing key | ansible.builtin.get_url | False |
| Workstation OpenTofu ¦ Download OpenTofu repository key | ansible.builtin.get_url | False |
| Workstation OpenTofu ¦ Check dearmored repository key | ansible.builtin.stat | False |
| Workstation OpenTofu ¦ Dearmor OpenTofu repository key | ansible.builtin.command | True |
| Workstation OpenTofu ¦ Keep repository key readable by APT | ansible.builtin.file | False |
| Workstation OpenTofu ¦ Add OpenTofu apt repository | ansible.builtin.apt_repository | False |
| Workstation OpenTofu ¦ Install OpenTofu packages | ansible.builtin.apt | False |

#### File: tasks/tools/fedora/opentofu.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation OpenTofu ¦ Install Fedora repository prerequisites | ansible.builtin.include_tasks | False |
| Workstation OpenTofu ¦ Import RPM signing keys | ansible.builtin.rpm_key | False |
| Workstation OpenTofu ¦ Configure verified RPM package repository | ansible.builtin.yum_repository | False |
| Workstation OpenTofu ¦ Install compatible Fedora package | ansible.builtin.include_tasks | False |

#### File: tasks/tools/opentofu.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation OpenTofu ¦ Validate installation platform | ansible.builtin.import_tasks | False |
| Workstation OpenTofu ¦ Report check-mode installation plan | ansible.builtin.debug | True |
| Workstation OpenTofu ¦ Install platform package and repository | ansible.builtin.include_tasks | True |

#### File: tasks/tools/repository.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation Repository ¦ Inspect checkout destination | ansible.builtin.stat | False |
| Workstation Repository ¦ Require existing checkout or explicit clone opt-in | ansible.builtin.assert | False |
| Workstation Repository ¦ Create parent for new optional clone | ansible.builtin.file | True |
| Workstation Repository ¦ Clone only into an absent destination | ansible.builtin.git | True |
| Workstation Repository ¦ Check existing repository interface without changing Git state | ansible.builtin.stat | True |
| Workstation Repository ¦ Require valid checkout interface | ansible.builtin.assert | True |

#### File: tasks/tools/skynet.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation Skynet ¦ Inspect Skynet directories | ansible.builtin.stat | False |
| Workstation Skynet ¦ Create missing Skynet directories | ansible.builtin.file | True |
| Workstation Skynet ¦ Install local Skynet wrapper | ansible.builtin.template | False |

#### File: tasks/tools/validate_tools.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation ¦ Validate tooling platform | ansible.builtin.import_tasks | False |
| Workstation ¦ Validate platform and switches | ansible.builtin.assert | False |
| Workstation ¦ Resolve existing user account | ansible.builtin.getent | False |
| Workstation ¦ Require non-root tooling owner | ansible.builtin.assert | False |
| Workstation ¦ Resolve user paths | ansible.builtin.set_fact | False |
| Workstation ¦ Validate absolute paths | ansible.builtin.assert | False |

#### File: tasks/validate.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation ¦ Validate supported platform | ansible.builtin.import_tasks | False |
| Workstation ¦ Validate primary role variables | ansible.builtin.assert | False |
| Workstation ¦ Validate optional Git identity | ansible.builtin.assert | True |
| Workstation ¦ Read workstation user account | ansible.builtin.getent | False |
| Workstation ¦ Validate workstation user account | ansible.builtin.assert | False |
| Workstation ¦ Resolve workstation user facts | ansible.builtin.set_fact | False |
| Workstation ¦ Validate user path variables | ansible.builtin.assert | False |

#### File: tasks/vscode.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation VS Code ¦ Validate installation platform | ansible.builtin.import_tasks | False |
| Workstation VS Code ¦ Report check-mode installation plan | ansible.builtin.debug | True |
| Workstation VS Code ¦ Install platform package and repository | ansible.builtin.include_tasks | True |
| Workstation VS Code ¦ Check for Visual Studio Code command | ansible.builtin.stat | False |
| Workstation VS Code ¦ List installed extensions | ansible.builtin.command | True |
| Workstation VS Code ¦ Install configured extensions | ansible.builtin.command | True |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
