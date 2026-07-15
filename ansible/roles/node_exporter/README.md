<!-- DOCSIBLE START -->

# 📃 Role overview

## node_exporter





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/07/15 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [node_exporter_version](defaults/main.yml#L3)   | str | `1.10.1` |    
| [node_exporter_arch](defaults/main.yml#L4)   | str | `amd64` |    
| [node_exporter_user](defaults/main.yml#L6)   | str | `node_exporter` |    
| [node_exporter_group](defaults/main.yml#L7)   | str | `node_exporter` |    
| [node_exporter_release_url](defaults/main.yml#L9)   | str | `https://github.com/prometheus/node_exporter/releases/download/v{{ node_exporter_version }}` |    
| [node_exporter_archive_name](defaults/main.yml#L10)   | str | `node_exporter-{{ node_exporter_version }}.linux-{{ node_exporter_arch }}.tar.gz` |    
| [node_exporter_download_url](defaults/main.yml#L11)   | str | `{{ node_exporter_release_url }}/{{ node_exporter_archive_name }}` |    
| [node_exporter_archive_path](defaults/main.yml#L12)   | str | `/tmp/{{ node_exporter_archive_name }}` |    
| [node_exporter_extract_dir](defaults/main.yml#L13)   | str | `/tmp/node_exporter-{{ node_exporter_version }}.linux-{{ node_exporter_arch }}` |    
| [node_exporter_checksum](defaults/main.yml#L15)   | str | `sha256:{{ node_exporter_release_url }}/sha256sums.txt` |    
| [node_exporter_install_dir](defaults/main.yml#L17)   | str | `/usr/local/bin` |    
| [node_exporter_textfile_dir](defaults/main.yml#L18)   | str | `/var/lib/node_exporter/textfile_collector` |    
| [node_exporter_listen_address](defaults/main.yml#L20)   | str | `0.0.0.0:9100` |    
| [node_exporter_enabled_collectors](defaults/main.yml#L22)   | list | `[]` |    
| [node_exporter_enabled_collectors.**0**](defaults/main.yml#L23)   | str | `systemd` |    
| [node_exporter_enabled_collectors.**1**](defaults/main.yml#L24)   | str | `processes` |    
| [node_exporter_enabled_collectors.**2**](defaults/main.yml#L25)   | str | `textfile` |    
| [node_exporter_disabled_collectors](defaults/main.yml#L27)   | list | `[]` |    
| [node_exporter_extra_args](defaults/main.yml#L29)   | list | `[]` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Node_Exporter ¦ Create node_exporter group | ansible.builtin.group | False |
| Node_Exporter ¦ Create node_exporter user | ansible.builtin.user | False |
| Node_Exporter ¦ Create node_exporter textfile collector directory | ansible.builtin.file | False |
| Node_Exporter ¦ Skip node_exporter binary install in check mode | ansible.builtin.debug | True |
| Node_Exporter ¦ Download node_exporter archive | ansible.builtin.get_url | True |
| Node_Exporter ¦ Extract node_exporter archive | ansible.builtin.unarchive | True |
| Node_Exporter ¦ Install node_exporter binary | ansible.builtin.copy | True |
| Node_Exporter ¦ Install node_exporter systemd unit | ansible.builtin.template | False |
| Node_Exporter ¦ Enable and start node_exporter | ansible.builtin.systemd | True |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
