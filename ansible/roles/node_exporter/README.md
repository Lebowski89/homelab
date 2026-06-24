<!-- DOCSIBLE START -->

# 📃 Role overview

## node_exporter





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/06/24 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [node_exporter_version](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L3)   | str | `1.10.1` |    
| [node_exporter_arch](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L4)   | str | `amd64` |    
| [node_exporter_user](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L5)   | str | `node_exporter` |    
| [node_exporter_group](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L6)   | str | `node_exporter` |    
| [node_exporter_install_dir](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L8)   | str | `/usr/local/bin` |    
| [node_exporter_textfile_dir](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L9)   | str | `/var/lib/node_exporter/textfile_collector` |    
| [node_exporter_listen_address](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L11)   | str | `0.0.0.0:9100` |    
| [node_exporter_enabled_collectors](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L13)   | list | `[]` |    
| [node_exporter_enabled_collectors.**0**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L14)   | str | `systemd` |    
| [node_exporter_enabled_collectors.**1**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L15)   | str | `textfile` |    
| [node_exporter_disabled_collectors](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L17)   | list | `[]` |    
| [node_exporter_extra_args](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L19)   | list | `[]` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Create node_exporter group | ansible.builtin.group | False |
| Create node_exporter user | ansible.builtin.user | False |
| Create node_exporter textfile collector directory | ansible.builtin.file | False |
| Download node_exporter archive | ansible.builtin.get_url | False |
| Extract node_exporter archive | ansible.builtin.unarchive | False |
| Install node_exporter binary | ansible.builtin.copy | False |
| Install node_exporter systemd unit | ansible.builtin.template | False |
| Enable and start node_exporter | ansible.builtin.systemd | False |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
