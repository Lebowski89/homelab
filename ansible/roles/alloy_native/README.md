<!-- DOCSIBLE START -->

# 📃 Role overview

## alloy_native





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/10/01 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [alloy_native_keyring_dir](defaults/main.yml#L3)   | str | `/etc/apt/keyrings` |    
| [alloy_native_keyring_file](defaults/main.yml#L4)   | str | `/etc/apt/keyrings/grafana.asc` |    
| [alloy_native_repo_url](defaults/main.yml#L5)   | str | `https://apt.grafana.com` |    
| [alloy_native_repo_suite](defaults/main.yml#L6)   | str | `stable` |    
| [alloy_native_repo_filename](defaults/main.yml#L7)   | str | `grafana` |    
| [alloy_native_packages](defaults/main.yml#L8)   | list | `[]` |    
| [alloy_native_packages.**0**](defaults/main.yml#L8)   | str | `alloy` |    
| [alloy_native_service_name](defaults/main.yml#L9)   | str | `alloy` |    
| [alloy_native_user](defaults/main.yml#L9)   | str | `alloy` |    
| [alloy_native_group](defaults/main.yml#L9)   | str | `alloy` |    
| [alloy_native_config_dir](defaults/main.yml#L13)   | str | `/etc/alloy` |    
| [alloy_native_config_path](defaults/main.yml#L14)   | str | `/etc/alloy/config.alloy` |    
| [alloy_native_journal_groups](defaults/main.yml#L15)   | list | `[]` |    
| [alloy_native_journal_groups.**0**](defaults/main.yml#L16)   | str | `adm` |    
| [alloy_native_journal_groups.**1**](defaults/main.yml#L17)   | str | `systemd-journal` |    
| [alloy_native_loki_url](defaults/main.yml#L18)   | str | `<multiline value: folded_strip>` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Alloy native ¦ Assert supported OS | ansible.builtin.assert | False |
| Alloy native ¦ Ensure apt keyring directory exists | ansible.builtin.file | False |
| Alloy native ¦ Download Grafana package signing key | ansible.builtin.get_url | False |
| Alloy native ¦ Configure Grafana apt repository | ansible.builtin.apt_repository | False |
| Alloy native ¦ Install Alloy and ACL support | ansible.builtin.apt | False |
| Alloy native ¦ Read local system groups | ansible.builtin.getent | False |
| Alloy native ¦ Resolve available journal reader groups | ansible.builtin.set_fact | False |
| Alloy native ¦ Grant journal access to package service account | ansible.builtin.user | True |
| Alloy native ¦ Ensure configuration directory exists | ansible.builtin.file | False |
| Alloy native ¦ Render collector configuration | ansible.builtin.template | False |
| Alloy native ¦ Enable and start service | ansible.builtin.systemd_service | False |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
