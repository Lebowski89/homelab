<!-- DOCSIBLE START -->

# 📃 Role overview

## keepalived





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/07/15 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [keepalived_config_path](defaults/main.yml#L3)   | str | `/etc/keepalived/keepalived.conf` |    
| [keepalived_check_script_path](defaults/main.yml#L4)   | str | `/usr/local/sbin/check-technitium-dns.sh` |    
| [keepalived_dns_check_query](defaults/main.yml#L6)   | str | `dns01.skynet` |    
| [keepalived_dns_check_type](defaults/main.yml#L7)   | str | `A` |    
| [keepalived_dns_check_server](defaults/main.yml#L8)   | str | `127.0.0.1` |    
| [keepalived_dns_check_timeout](defaults/main.yml#L9)   | int | `1` |    
| [keepalived_dns_check_tries](defaults/main.yml#L10)   | int | `1` |    
| [keepalived_script_interval](defaults/main.yml#L12)   | int | `2` |    
| [keepalived_script_timeout](defaults/main.yml#L13)   | int | `2` |    
| [keepalived_script_fall](defaults/main.yml#L14)   | int | `3` |    
| [keepalived_script_rise](defaults/main.yml#L15)   | int | `2` |    
| [keepalived_script_weight](defaults/main.yml#L16)   | int | `-80` |    
| [keepalived_dns_group](defaults/main.yml#L18)   | str | `tags_keepalived` |    
| [keepalived_host_ip](defaults/main.yml#L19)   | str | `{{ local_ip ¦ default('') }}` |    
| [keepalived_host_interface](defaults/main.yml#L20)   | str | `{{ ansible_default_ipv4.interface ¦ default('') }}` |    
| [keepalived_host_mode](defaults/main.yml#L21)   | str | `native` |    
| [keepalived_instances](defaults/main.yml#L22)   | dict | `{}` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Keepalived ¦ Set host config | ansible.builtin.set_fact | False |
| Keepalived ¦ Validate common config | ansible.builtin.assert | False |
| Keepalived ¦ Validate peer inventory addresses | ansible.builtin.assert | False |
| Keepalived ¦ Validate each VRRP instance | ansible.builtin.assert | False |
| Keepalived ¦ Include native backend | ansible.builtin.include_tasks | True |

#### File: tasks/native.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Keepalived native ¦ Assert supported OS | ansible.builtin.assert | False |
| Keepalived native ¦ Install packages | ansible.builtin.apt | False |
| Keepalived native ¦ Ensure config directory exists | ansible.builtin.file | False |
| Keepalived native ¦ Install DNS health check script | ansible.builtin.template | False |
| Keepalived native ¦ Render keepalived config | ansible.builtin.template | False |
| Keepalived native ¦ Enable and start keepalived | ansible.builtin.systemd_service | True |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
