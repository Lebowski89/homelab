<!-- DOCSIBLE START -->

# 📃 Role overview

## technitium_native





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/07/15 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [technitium_native_install_script_url](https://github.com/Lebowski89/homelab/blob/qol/various/defaults/main.yml#L3)   | str | `https://download.technitium.com/dns/install.sh` |    
| [technitium_native_install_script_path](https://github.com/Lebowski89/homelab/blob/qol/various/defaults/main.yml#L4)   | str | `/tmp/technitium-dns-install.sh` |    
| [technitium_native_service_name](https://github.com/Lebowski89/homelab/blob/qol/various/defaults/main.yml#L6)   | str | `dns` |    
| [technitium_native_web_port](https://github.com/Lebowski89/homelab/blob/qol/various/defaults/main.yml#L7)   | int | `5380` |    
| [technitium_native_dns_port](https://github.com/Lebowski89/homelab/blob/qol/various/defaults/main.yml#L8)   | int | `53` |    
| [technitium_native_config_dir](https://github.com/Lebowski89/homelab/blob/qol/various/defaults/main.yml#L10)   | str | `/etc/dns` |    
| [technitium_native_install_marker](https://github.com/Lebowski89/homelab/blob/qol/various/defaults/main.yml#L11)   | str | `/opt/technitium/dns/DnsServerApp.dll` |    
| [technitium_native_resolved_dns_servers](https://github.com/Lebowski89/homelab/blob/qol/various/defaults/main.yml#L13)   | list | `[]` |    
| [technitium_native_resolved_dns_servers.**0**](https://github.com/Lebowski89/homelab/blob/qol/various/defaults/main.yml#L14)   | str | `192.168.80.53` |    
| [technitium_native_resolved_dns_servers.**1**](https://github.com/Lebowski89/homelab/blob/qol/various/defaults/main.yml#L15)   | str | `192.168.80.54` |    
| [technitium_native_disable_resolved_stub](https://github.com/Lebowski89/homelab/blob/qol/various/defaults/main.yml#L17)   | bool | `True` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Technitium native ¦ Assert supported OS | ansible.builtin.assert | False |
| Technitium native ¦ Install prerequisite packages | ansible.builtin.apt | False |
| Technitium native ¦ Download installer before changing local DNS | ansible.builtin.get_url | False |
| Technitium native ¦ Ensure resolved config directory exists | ansible.builtin.file | True |
| Technitium native ¦ Disable systemd-resolved DNS stub | ansible.builtin.copy | True |
| Technitium native ¦ Point resolv.conf at real resolved output | ansible.builtin.file | True |
| Technitium native ¦ Flush resolver changes before install | ansible.builtin.meta | False |
| Technitium native ¦ Verify DNS still works after resolver change | ansible.builtin.command | False |
| Technitium native ¦ Run installer | ansible.builtin.command | False |
| Technitium native ¦ Enable and start service | ansible.builtin.systemd | False |
| Technitium native ¦ Wait for web console | ansible.builtin.wait_for | False |
| Technitium native ¦ Wait for DNS listener | ansible.builtin.wait_for | False |
| Technitium native ¦ Test local DNS recursion | ansible.builtin.command | False |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
