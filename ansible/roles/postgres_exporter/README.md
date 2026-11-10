<!-- DOCSIBLE START -->

# 📃 Role overview

## postgres_exporter





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/11/10 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [postgres_exporter_version](defaults/main.yml#L3)   | str | `0.20.1` |    
| [postgres_exporter_arch](defaults/main.yml#L4)   | str | `amd64` |    
| [postgres_exporter_checksum](defaults/main.yml#L5)   | str | `<multiline value: folded_strip>` |    
| [postgres_exporter_archive_name](defaults/main.yml#L7)   | str | `postgres_exporter-{{ postgres_exporter_version }}.linux-{{ postgres_exporter_arch }}.tar.gz` |    
| [postgres_exporter_release_base_url](defaults/main.yml#L8)   | str | `<multiline value: folded_strip>` |    
| [postgres_exporter_download_url](defaults/main.yml#L10)   | str | `{{ postgres_exporter_release_base_url }}/{{ postgres_exporter_archive_name }}` |    
| [postgres_exporter_archive_path](defaults/main.yml#L11)   | str | `/tmp/{{ postgres_exporter_archive_name }}` |    
| [postgres_exporter_extract_dir](defaults/main.yml#L12)   | str | `/tmp/postgres_exporter-{{ postgres_exporter_version }}.linux-{{ postgres_exporter_arch }}` |    
| [postgres_exporter_install_dir](defaults/main.yml#L13)   | str | `/usr/local/bin` |    
| [postgres_exporter_user](defaults/main.yml#L15)   | str | `postgres_exporter` |    
| [postgres_exporter_group](defaults/main.yml#L16)   | str | `postgres_exporter` |    
| [postgres_exporter_config_dir](defaults/main.yml#L17)   | str | `/etc/postgres_exporter` |    
| [postgres_exporter_environment_file](defaults/main.yml#L18)   | str | `{{ postgres_exporter_config_dir }}/environment` |    
| [postgres_exporter_password_file](defaults/main.yml#L19)   | str | `{{ postgres_exporter_config_dir }}/password` |    
| [postgres_exporter_listen_address](defaults/main.yml#L20)   | str | `{{ local_ip }}:9187` |    
| [postgres_exporter_database_host](defaults/main.yml#L22)   | str | `127.0.0.1` |    
| [postgres_exporter_database_port](defaults/main.yml#L23)   | int | `5432` |    
| [postgres_exporter_database_name](defaults/main.yml#L24)   | str | `{{ postgres_monitor_database }}` |    
| [postgres_exporter_database_user](defaults/main.yml#L25)   | str | `{{ postgres_monitor_role_name }}` |    
| [postgres_exporter_database_password](defaults/main.yml#L26)   | str | `{{ postgres_monitor_role_pass }}` |    





### Tasks


#### File: tasks/install.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Postgres_Exporter ¦ Validate database credential contract | ansible.builtin.assert | False |
| Postgres_Exporter ¦ Install APT archive prerequisites | ansible.builtin.apt | True |
| Postgres_Exporter ¦ Install RPM archive and SELinux prerequisites | ansible.builtin.dnf | True |
| Postgres_Exporter ¦ Refresh RPM SELinux facts after installing bindings | ansible.builtin.setup | True |
| Postgres_Exporter ¦ Require known RPM SELinux status | ansible.builtin.assert | True |
| Postgres_Exporter ¦ Create postgres_exporter group | ansible.builtin.group | False |
| Postgres_Exporter ¦ Create postgres_exporter user | ansible.builtin.user | False |
| Postgres_Exporter ¦ Create configuration directory | ansible.builtin.file | False |
| Postgres_Exporter ¦ Install protected password file | ansible.builtin.template | False |
| Postgres_Exporter ¦ Install protected environment file | ansible.builtin.template | False |
| Postgres_Exporter ¦ Ensure the selected binary directory exists | ansible.builtin.file | False |
| Postgres_Exporter ¦ Download checksum-pinned archive | ansible.builtin.get_url | False |
| Postgres_Exporter ¦ Extract archive | ansible.builtin.unarchive | False |
| Postgres_Exporter ¦ Install binary | ansible.builtin.copy | False |
| Postgres_Exporter ¦ Prepare enforcing RPM executable labels | ansible.builtin.import_tasks | True |
| Postgres_Exporter ¦ Install systemd unit | ansible.builtin.template | False |
| Postgres_Exporter ¦ Enable and start service | ansible.builtin.systemd_service | False |

#### File: tasks/main.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Postgres_Exporter ¦ Validate platform and installation inputs | ansible.builtin.import_tasks | False |
| Postgres_Exporter ¦ Preview installation in check mode | ansible.builtin.debug | True |
| Postgres_Exporter ¦ Install and configure the exporter | ansible.builtin.import_tasks | True |

#### File: tasks/platform.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Postgres_Exporter ¦ Gather missing platform facts | ansible.builtin.setup | True |
| Postgres_Exporter ¦ Detect Atomic or OSTree deployment | ansible.builtin.stat | False |
| Postgres_Exporter ¦ Validate supported platform before changes | ansible.builtin.assert | False |
| Postgres_Exporter ¦ Require a pinned archive and safe managed paths | ansible.builtin.assert | False |

#### File: tasks/selinux.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Postgres_Exporter ¦ Persist a label for only the managed executable | community.general.sefcontext | False |
| Postgres_Exporter ¦ Restore only the managed executable label | community.general.serestorecon | False |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
