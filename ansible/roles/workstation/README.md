<!-- DOCSIBLE START -->

# 📃 Role overview

## workstation





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/09/26 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [workstation_user](defaults/main.yml#L3)   | str | `{{ ansible_user }}` |    
| [workstation_timezone](defaults/main.yml#L4)   | str | `Australia/Melbourne` |    
| [workstation_packages](defaults/main.yml#L6)   | list | `[]` |    
| [workstation_packages.**0**](defaults/main.yml#L7)   | str | `ca-certificates` |    
| [workstation_packages.**1**](defaults/main.yml#L8)   | str | `curl` |    
| [workstation_packages.**2**](defaults/main.yml#L9)   | str | `gnupg` |    
| [workstation_packages.**3**](defaults/main.yml#L10)   | str | `jq` |    
| [workstation_packages.**4**](defaults/main.yml#L11)   | str | `openssh-client` |    
| [workstation_packages.**5**](defaults/main.yml#L12)   | str | `ripgrep` |    
| [workstation_packages.**6**](defaults/main.yml#L13)   | str | `rsync` |    
| [workstation_packages.**7**](defaults/main.yml#L14)   | str | `wget` |    
| [workstation_dev_packages](defaults/main.yml#L16)   | list | `[]` |    
| [workstation_dev_packages.**0**](defaults/main.yml#L17)   | str | `git` |    
| [workstation_dev_packages.**1**](defaults/main.yml#L18)   | str | `python3` |    
| [workstation_dev_packages.**2**](defaults/main.yml#L19)   | str | `python3-pip` |    
| [workstation_dev_packages.**3**](defaults/main.yml#L20)   | str | `python3-venv` |    
| [workstation_desktop_packages](defaults/main.yml#L22)   | list | `[]` |    
| [workstation_desktop_packages.**0**](defaults/main.yml#L23)   | str | `xdg-user-dirs` |    
| [workstation_apt_update_cache](defaults/main.yml#L25)   | bool | `True` |    
| [workstation_vscode_enabled](defaults/main.yml#L27)   | bool | `True` |    
| [workstation_vscode_key_url](defaults/main.yml#L28)   | str | `https://packages.microsoft.com/keys/microsoft.asc` |    
| [workstation_vscode_key_path](defaults/main.yml#L29)   | str | `/usr/share/keyrings/microsoft-vscode.asc` |    
| [workstation_vscode_repository_path](defaults/main.yml#L30)   | str | `/etc/apt/sources.list.d/vscode.sources` |    
| [workstation_vscode_extensions](defaults/main.yml#L31)   | list | `[]` |    
| [workstation_vscode_extensions.**0**](defaults/main.yml#L32)   | str | `redhat.ansible` |    
| [workstation_vscode_extensions.**1**](defaults/main.yml#L33)   | str | `ms-python.python` |    
| [workstation_vscode_extensions.**2**](defaults/main.yml#L34)   | str | `ms-vscode-remote.remote-ssh` |    
| [workstation_git_manage_config](defaults/main.yml#L36)   | bool | `False` |    
| [workstation_git_user_name](defaults/main.yml#L37)   | str |  |    
| [workstation_git_user_email](defaults/main.yml#L38)   | str |  |    
| [workstation_shell_directories](defaults/main.yml#L40)   | list | `[]` |    
| [workstation_shell_directories.**0**](defaults/main.yml#L41)   | str | `{{ workstation_user_home }}/.local/bin` |    
| [workstation_xdg_directories](defaults/main.yml#L43)   | list | `[]` |    
| [workstation_xdg_directories.**0**](defaults/main.yml#L44)   | str | `{{ workstation_user_home }}/Desktop` |    
| [workstation_xdg_directories.**1**](defaults/main.yml#L45)   | str | `{{ workstation_user_home }}/Documents` |    
| [workstation_xdg_directories.**2**](defaults/main.yml#L46)   | str | `{{ workstation_user_home }}/Downloads` |    
| [workstation_xdg_directories.**3**](defaults/main.yml#L47)   | str | `{{ workstation_user_home }}/Music` |    
| [workstation_xdg_directories.**4**](defaults/main.yml#L48)   | str | `{{ workstation_user_home }}/Pictures` |    
| [workstation_xdg_directories.**5**](defaults/main.yml#L49)   | str | `{{ workstation_user_home }}/Public` |    
| [workstation_xdg_directories.**6**](defaults/main.yml#L50)   | str | `{{ workstation_user_home }}/Templates` |    
| [workstation_xdg_directories.**7**](defaults/main.yml#L51)   | str | `{{ workstation_user_home }}/Videos` |    





### Tasks


#### File: tasks/apt.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation APT ¦ Install baseline packages | ansible.builtin.apt | True |

#### File: tasks/desktop.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation Desktop ¦ Install desktop packages | ansible.builtin.apt | True |
| Workstation Desktop ¦ Ensure XDG user directories exist | ansible.builtin.file | False |

#### File: tasks/development.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation Development ¦ Install development packages | ansible.builtin.apt | True |
| Workstation Development ¦ Manage Git identity block | ansible.builtin.blockinfile | True |

#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Workstation ¦ Validate configuration and resolve user | ansible.builtin.include_tasks | False |  |
| Workstation ¦ Configure timezone | ansible.builtin.include_tasks | False |  |
| Workstation ¦ Install baseline packages | ansible.builtin.include_tasks | False |  |
| Workstation ¦ Configure development tooling | ansible.builtin.include_tasks | False |  |
| Workstation ¦ Configure Visual Studio Code | ansible.builtin.include_tasks | True |  |
| Workstation ¦ Configure shell directories | ansible.builtin.include_tasks | False |  |
| Workstation ¦ Configure desktop baseline | ansible.builtin.include_tasks | False |  |

#### File: tasks/shell.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation Shell ¦ Ensure user shell directories exist | ansible.builtin.file | False |

#### File: tasks/timezone.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation ¦ Check timezone data file | ansible.builtin.stat | False |
| Workstation ¦ Validate timezone data file | ansible.builtin.assert | False |
| Workstation ¦ Set local timezone link | ansible.builtin.file | False |
| Workstation ¦ Record local timezone | ansible.builtin.copy | False |

#### File: tasks/validate.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation ¦ Validate supported platform | ansible.builtin.assert | False |
| Workstation ¦ Validate primary role variables | ansible.builtin.assert | False |
| Workstation ¦ Validate optional Git identity | ansible.builtin.assert | True |
| Workstation ¦ Read workstation user account | ansible.builtin.getent | False |
| Workstation ¦ Validate workstation user account | ansible.builtin.assert | False |
| Workstation ¦ Resolve workstation user facts | ansible.builtin.set_fact | False |
| Workstation ¦ Validate user path variables | ansible.builtin.assert | False |

#### File: tasks/vscode.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Workstation VS Code ¦ Install repository prerequisites | ansible.builtin.apt | False |
| Workstation VS Code ¦ Install Microsoft signing key | ansible.builtin.get_url | False |
| Workstation VS Code ¦ Configure Microsoft repository | ansible.builtin.copy | False |
| Workstation VS Code ¦ Install Visual Studio Code | ansible.builtin.apt | False |
| Workstation VS Code ¦ Check for Visual Studio Code command | ansible.builtin.stat | False |
| Workstation VS Code ¦ List installed extensions | ansible.builtin.command | True |
| Workstation VS Code ¦ Install configured extensions | ansible.builtin.command | True |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
