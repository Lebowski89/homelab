<!-- DOCSIBLE START -->

# 📃 Role overview

## postgres_exporter





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/10/01 |








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


#### File: tasks/main.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Postgres_Exporter ¦ Validate database credential contract | ansible.builtin.assert | False |
| Postgres_Exporter ¦ Create postgres_exporter group | ansible.builtin.group | False |
| Postgres_Exporter ¦ Create postgres_exporter user | ansible.builtin.user | False |
| Postgres_Exporter ¦ Create configuration directory | ansible.builtin.file | False |
| Postgres_Exporter ¦ Install protected password file | ansible.builtin.template | False |
| Postgres_Exporter ¦ Install protected environment file | ansible.builtin.template | False |
| Postgres_Exporter ¦ Skip binary install in check mode | ansible.builtin.debug | True |
| Postgres_Exporter ¦ Download checksum-pinned archive | ansible.builtin.get_url | True |
| Postgres_Exporter ¦ Extract archive | ansible.builtin.unarchive | True |
| Postgres_Exporter ¦ Install binary | ansible.builtin.copy | True |
| Postgres_Exporter ¦ Install systemd unit | ansible.builtin.template | False |
| Postgres_Exporter ¦ Enable and start service | ansible.builtin.systemd | True |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
