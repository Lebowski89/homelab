<!-- DOCSIBLE START -->

# 📃 Role overview

## hugo





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/07/09 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [hugo_fs_host](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L3)   | str | `{{ docker_services_primary_manager }}` |    
| [hugo_root_path](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L4)   | str | `{{ hostvars[docker_services_primary_manager].docker_host_appdata_root }}` |    
| [hugo_site_path](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L5)   | str | `{{ hugo_root_path }}/blog` |    
| [hugo_theme_path](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L6)   | str | `{{ hugo_site_path }}/themes/terminal` |    
| [hugo_image](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L7)   | str | `ghcr.io/gohugoio/hugo:v0.163.3` |    
| [hugo_directory_paths](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L9)   | list | `[]` |    
| [hugo_directory_paths.**0**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L10)   | dict | `{}` |    
| [hugo_directory_paths.0.**path**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L10)   | str | `{{ hugo_site_path }}` |    
| [hugo_directory_paths.0.**state**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L11)   | str | `directory` |    
| [hugo_directory_paths.0.**mode**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L12)   | str | `0755` |    
| [hugo_directory_paths.**1**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L13)   | dict | `{}` |    
| [hugo_directory_paths.1.**path**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L13)   | str | `{{ hugo_site_path }}/.github` |    
| [hugo_directory_paths.1.**state**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L14)   | str | `directory` |    
| [hugo_directory_paths.1.**mode**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L15)   | str | `0755` |    
| [hugo_directory_paths.**2**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L16)   | dict | `{}` |    
| [hugo_directory_paths.2.**path**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L16)   | str | `{{ hugo_site_path }}/.github/workflows` |    
| [hugo_directory_paths.2.**state**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L17)   | str | `directory` |    
| [hugo_directory_paths.2.**mode**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L18)   | str | `0755` |    
| [hugo_copy_items](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L20)   | list | `[]` |    
| [hugo_copy_items.**0**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L21)   | dict | `{}` |    
| [hugo_copy_items.0.**src**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L21)   | str | `files/favicon.png` |    
| [hugo_copy_items.0.**dest**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L22)   | str | `{{ hugo_site_path }}/static/favicon.png` |    
| [hugo_copy_items.0.**mode**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L23)   | str | `0664` |    
| [hugo_copy_items.0.**force**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L24)   | bool | `False` |    
| [hugo_copy_items.0.**wait**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L25)   | bool | `True` |    
| [hugo_copy_items.0.**wait_timeout**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L26)   | int | `30` |    
| [hugo_copy_items.**1**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L27)   | dict | `{}` |    
| [hugo_copy_items.1.**src**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L27)   | str | `files/og-image.png` |    
| [hugo_copy_items.1.**dest**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L28)   | str | `{{ hugo_site_path }}/static/og-image.png` |    
| [hugo_copy_items.1.**mode**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L29)   | str | `0664` |    
| [hugo_copy_items.1.**force**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L30)   | bool | `False` |    
| [hugo_copy_items.1.**wait**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L31)   | bool | `True` |    
| [hugo_copy_items.1.**wait_timeout**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L32)   | int | `30` |    
| [hugo_copy_items.**2**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L33)   | dict | `{}` |    
| [hugo_copy_items.2.**src**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L33)   | str | `files/terminal.css` |    
| [hugo_copy_items.2.**dest**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L34)   | str | `{{ hugo_site_path }}/static/terminal.css` |    
| [hugo_copy_items.2.**mode**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L35)   | str | `0664` |    
| [hugo_copy_items.2.**force**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L36)   | bool | `False` |    
| [hugo_copy_items.2.**wait**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L37)   | bool | `True` |    
| [hugo_copy_items.2.**wait_timeout**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L38)   | int | `30` |    
| [hugo_copy_items.**3**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L39)   | dict | `{}` |    
| [hugo_copy_items.3.**src**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L39)   | str | `files/pages.yaml` |    
| [hugo_copy_items.3.**dest**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L40)   | str | `{{ hugo_site_path }}/.github/workflows/hugo.yaml` |    
| [hugo_copy_items.3.**mode**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L41)   | str | `0664` |    
| [hugo_copy_items.3.**force**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L42)   | bool | `False` |    
| [hugo_copy_items.3.**wait**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L43)   | bool | `True` |    
| [hugo_copy_items.3.**wait_timeout**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L44)   | int | `30` |    
| [hugo_templates](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L46)   | list | `[]` |    
| [hugo_templates.**0**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L47)   | dict | `{}` |    
| [hugo_templates.0.**src**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L47)   | str | `hugo.yaml.j2` |    
| [hugo_templates.0.**dest**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L48)   | str | `{{ hugo_site_path }}/hugo.yaml` |    
| [hugo_templates.0.**mode**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L49)   | str | `0664` |    
| [hugo_templates.0.**force**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L50)   | bool | `True` |    
| [hugo_cloudflare_zone](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L52)   | str |  |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Hugo ¦ Ensure directories exist | ansible.builtin.file | False |  |
| Hugo ¦ Copy files | ansible.builtin.copy | False |  |
| Hugo ¦ Wait for copied files | ansible.builtin.wait_for | True |  |
| Hugo ¦ Render templates | ansible.builtin.template | False |  |
| Hugo ¦ Check if site exists | ansible.builtin.stat | False |  |
| Hugo ¦ Generate new Hugo site | community.docker.docker_container | True |  |
| Hugo ¦ Manage theme submodule | block | False |  |
| Hugo ¦ Check if repo already initialized | ansible.builtin.stat | False |  |
| Hugo ¦ Init git repo | ansible.builtin.command | True |  |
| Hugo ¦ Check if theme submodule exists | ansible.builtin.stat | False |  |
| Hugo ¦ Add Terminal theme submodule | ansible.builtin.command | True |  |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
