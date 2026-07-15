<!-- DOCSIBLE START -->

# 📃 Role overview

## resolved





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/07/15 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [resolved_packages](defaults/main.yml#L3)   | list | `[]` |    
| [resolved_packages.**0**](defaults/main.yml#L4)   | str | `libnss-resolve` |    
| [resolved_apt_env_vars](defaults/main.yml#L6)   | dict | `{}` |    
| [resolved_apt_env_vars.**DEBIAN_FRONTEND**](defaults/main.yml#L7)   | str | `noninteractive` |    
| [resolved_apt_env_vars.**DEBIAN_PRIORITY**](defaults/main.yml#L8)   | str | `critical` |    
| [resolved_service_name](defaults/main.yml#L10)   | str | `systemd-resolved` |    
| [resolved_disable_stub](defaults/main.yml#L13)   | bool | `False` |    
| [resolved_config_dir](defaults/main.yml#L15)   | str | `/etc/systemd/resolved.conf.d` |    
| [resolved_dropin_path](defaults/main.yml#L16)   | str | `{{ resolved_config_dir }}/99-skynet.conf` |    
| [resolved_manage_resolv_conf](defaults/main.yml#L20)   | str | `{{ resolved_disable_stub }}` |    
| [resolved_resolv_conf_path](defaults/main.yml#L21)   | str | `/etc/resolv.conf` |    
| [resolved_resolv_conf_target](defaults/main.yml#L22)   | str | `/run/systemd/resolve/resolv.conf` |    
| [resolved_fallback_dns](defaults/main.yml#L24)   | list | `[]` |    
| [resolved_fallback_dns.**0**](defaults/main.yml#L25)   | str | `1.1.1.1` |    
| [resolved_fallback_dns.**1**](defaults/main.yml#L26)   | str | `9.9.9.9` |    
| [resolved_cleanup_dropins](defaults/main.yml#L28)   | list | `[]` |    
| [resolved_cleanup_dropins.**0**](defaults/main.yml#L29)   | str | `/etc/systemd/resolved.conf.d/no-stub-listener.conf` |    
| [resolved_manage_nsswitch](defaults/main.yml#L34)   | bool | `True` |    
| [resolved_nsswitch_path](defaults/main.yml#L35)   | str | `/etc/nsswitch.conf` |    
| [resolved_nsswitch_backup](defaults/main.yml#L36)   | bool | `True` |    
| [resolved_nsswitch_hosts_line](defaults/main.yml#L37)   | str | `hosts:          files resolve [!UNAVAIL=return] dns` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Resolved ¦ Assert supported host | ansible.builtin.assert | False |
| Resolved ¦ Install NSS resolver packages | ansible.builtin.apt | True |
| Resolved ¦ Ensure systemd-resolved is enabled and running | ansible.builtin.systemd | False |
| Resolved ¦ Ensure resolved config directory exists | ansible.builtin.file | False |
| Resolved ¦ Remove stale unmanaged resolved drop-ins | ansible.builtin.file | True |
| Resolved ¦ Configure systemd-resolved drop-in | ansible.builtin.copy | False |
| Resolved ¦ Apply DNS stub listener changes before dependent services | ansible.builtin.meta | True |
| Resolved ¦ Allow Proxmox LXC to manage resolv.conf | ansible.builtin.file | True |
| Resolved ¦ Point resolv.conf at resolved upstream file | ansible.builtin.file | True |
| Resolved ¦ Ensure NSS uses systemd-resolved before plain DNS | ansible.builtin.lineinfile | True |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
