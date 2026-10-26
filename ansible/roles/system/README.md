<!-- DOCSIBLE START -->

# 📃 Role overview

## system





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/10/26 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [system_packages_enabled](defaults/main.yml#L3)   | bool | `True` |    
| [system_sysctl_enabled](defaults/main.yml#L4)   | bool | `True` |    
| [system_limits_enabled](defaults/main.yml#L5)   | bool | `True` |    
| [system_guest_agent_enabled](defaults/main.yml#L6)   | bool | `True` |    
| [system_extra_packages](defaults/main.yml#L7)   | list | `[]` |    
| [system_package_cache_valid_time](defaults/main.yml#L8)   | int | `3600` |    
| [system_sysctl_file](defaults/main.yml#L11)   | str | `/etc/sysctl.d/99-ubuntu-tuning.conf` |    
| [system_limits_file](defaults/main.yml#L12)   | str | `/etc/security/limits.d/99-ubuntu.conf` |    
| [system_limits](defaults/main.yml#L13)   | list | `[]` |    
| [system_limits.**0**](defaults/main.yml#L14)   | dict | `{}` |    
| [system_limits.0.**domain**](defaults/main.yml#L14)   | str | `*` |    
| [system_limits.0.**type**](defaults/main.yml#L15)   | str | `-` |    
| [system_limits.0.**item**](defaults/main.yml#L16)   | str | `nofile` |    
| [system_limits.0.**value**](defaults/main.yml#L17)   | int | `100000` |    
| [system_swap_enabled](defaults/main.yml#L21)   | bool | `False` |    
| [system_swap_path](defaults/main.yml#L22)   | str | `/swapfile` |    
| [system_swap_size_mb](defaults/main.yml#L23)   | int | `2048` |    
| [system_nic_interfaces](defaults/main.yml#L26)   | dict | `{}` |    
| [system_nic_migrate_legacy](defaults/main.yml#L28)   | bool | `False` |    
| [system_updates_upgrade](defaults/main.yml#L31)   | bool | `True` |    
| [system_updates_autoremove](defaults/main.yml#L32)   | bool | `False` |    
| [system_updates_autoclean](defaults/main.yml#L33)   | bool | `False` |    
| [system_resolved_enabled](defaults/main.yml#L37)   | bool | `False` |    
| [system_resolved_disable_stub](defaults/main.yml#L38)   | bool | `False` |    
| [system_resolved_manage_resolv_conf](defaults/main.yml#L39)   | str | `{{ system_resolved_disable_stub }}` |    
| [system_resolved_manage_nsswitch](defaults/main.yml#L40)   | bool | `True` |    
| [system_resolved_nsswitch_path](defaults/main.yml#L41)   | str | `/etc/nsswitch.conf` |    
| [system_resolved_nsswitch_backup](defaults/main.yml#L42)   | bool | `True` |    
| [system_resolved_nsswitch_hosts_line](defaults/main.yml#L43)   | str | `hosts:          files resolve [!UNAVAIL=return] dns` |    
| [system_resolved_packages](defaults/main.yml#L44)   | list | `[]` |    
| [system_resolved_packages.**0**](defaults/main.yml#L44)   | str | `libnss-resolve` |    
| [system_resolved_service_name](defaults/main.yml#L45)   | str | `systemd-resolved` |    
| [system_resolved_config_dir](defaults/main.yml#L46)   | str | `/etc/systemd/resolved.conf.d` |    
| [system_resolved_dropin_path](defaults/main.yml#L47)   | str | `{{ system_resolved_config_dir }}/99-skynet.conf` |    
| [system_resolved_resolv_conf_path](defaults/main.yml#L48)   | str | `/etc/resolv.conf` |    
| [system_resolved_resolv_conf_target](defaults/main.yml#L49)   | str | `/run/systemd/resolve/resolv.conf` |    
| [system_resolved_fallback_dns](defaults/main.yml#L50)   | list | `[]` |    
| [system_resolved_fallback_dns.**0**](defaults/main.yml#L50)   | str | `1.1.1.1` |    
| [system_resolved_fallback_dns.**1**](defaults/main.yml#L50)   | str | `9.9.9.9` |    
| [system_resolved_cleanup_dropins](defaults/main.yml#L51)   | list | `[]` |    
| [system_resolved_cleanup_dropins.**0**](defaults/main.yml#L52)   | str | `/etc/systemd/resolved.conf.d/no-stub-listener.conf` |    
| [system_apt_environment](defaults/main.yml#L54)   | dict | `{}` |    
| [system_apt_environment.**DEBIAN_FRONTEND**](defaults/main.yml#L55)   | str | `noninteractive` |    
| [system_apt_environment.**DEBIAN_PRIORITY**](defaults/main.yml#L56)   | str | `critical` |    
| [system_sysctl_settings](defaults/main.yml#L58)   | dict | `{}` |    
| [system_sysctl_settings.fs.inotify.**max_user_watches**](defaults/main.yml#L59)   | int | `524288` |    
| [system_sysctl_settings.net.core.**default_qdisc**](defaults/main.yml#L60)   | str | `fq` |    
| [system_sysctl_settings.net.core.**rmem_max**](defaults/main.yml#L61)   | int | `67108864` |    
| [system_sysctl_settings.net.core.**somaxconn**](defaults/main.yml#L62)   | int | `4096` |    
| [system_sysctl_settings.net.core.**wmem_max**](defaults/main.yml#L63)   | int | `67108864` |    
| [system_sysctl_settings.net.ipv4.conf.all.**accept_redirects**](defaults/main.yml#L64)   | int | `0` |    
| [system_sysctl_settings.net.ipv4.conf.all.**accept_source_route**](defaults/main.yml#L65)   | int | `0` |    
| [system_sysctl_settings.net.ipv4.conf.all.**secure_redirects**](defaults/main.yml#L66)   | int | `0` |    
| [system_sysctl_settings.net.ipv4.**tcp_congestion_control**](defaults/main.yml#L67)   | str | `bbr` |    
| [system_sysctl_settings.net.ipv4.**tcp_fin_timeout**](defaults/main.yml#L68)   | int | `10` |    
| [system_sysctl_settings.net.ipv4.**tcp_max_syn_backlog**](defaults/main.yml#L69)   | int | `30000` |    
| [system_sysctl_settings.net.ipv4.**tcp_max_tw_buckets**](defaults/main.yml#L70)   | int | `2000000` |    
| [system_sysctl_settings.net.ipv4.**tcp_mtu_probing**](defaults/main.yml#L71)   | int | `1` |    
| [system_sysctl_settings.net.ipv4.**tcp_rfc1337**](defaults/main.yml#L72)   | int | `1` |    
| [system_sysctl_settings.net.ipv4.**tcp_rmem**](defaults/main.yml#L73)   | str | `4096 87380 33554432` |    
| [system_sysctl_settings.net.ipv4.**tcp_sack**](defaults/main.yml#L74)   | int | `1` |    
| [system_sysctl_settings.net.ipv4.**tcp_slow_start_after_idle**](defaults/main.yml#L75)   | int | `0` |    
| [system_sysctl_settings.net.ipv4.**tcp_tw_reuse**](defaults/main.yml#L76)   | int | `2` |    
| [system_sysctl_settings.net.ipv4.**tcp_window_scaling**](defaults/main.yml#L77)   | int | `1` |    
| [system_sysctl_settings.net.ipv4.**tcp_wmem**](defaults/main.yml#L78)   | str | `4096 87380 33554432` |    
| [system_sysctl_settings.net.ipv4.**udp_rmem_min**](defaults/main.yml#L79)   | int | `8192` |    
| [system_sysctl_settings.net.ipv4.**udp_wmem_min**](defaults/main.yml#L80)   | int | `8192` |    
| [system_sysctl_settings.net.ipv4.neigh.default.**gc_thresh1**](defaults/main.yml#L81)   | int | `1024` |    
| [system_sysctl_settings.net.ipv4.neigh.default.**gc_thresh2**](defaults/main.yml#L82)   | int | `2048` |    
| [system_sysctl_settings.net.ipv4.neigh.default.**gc_thresh3**](defaults/main.yml#L83)   | int | `4096` |    
| [system_sysctl_settings.vm.**dirty_background_ratio**](defaults/main.yml#L84)   | int | `10` |    
| [system_sysctl_settings.vm.**dirty_ratio**](defaults/main.yml#L85)   | int | `15` |    
| [system_sysctl_settings.vm.**swappiness**](defaults/main.yml#L86)   | int | `10` |    


### Vars

**These are variables with higher priority**
#### File: vars/Debian.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [system_platform_packages](vars/Debian.yml#L2)   | list | `[]` |    
| [system_platform_packages.**0**](vars/Debian.yml#L3)   | str | `python3` |    
| [system_platform_packages.**1**](vars/Debian.yml#L4)   | str | `python3-apt` |    
| [system_platform_packages.**2**](vars/Debian.yml#L5)   | str | `ca-certificates` |    
| [system_platform_packages.**3**](vars/Debian.yml#L6)   | str | `curl` |    
| [system_platform_packages.**4**](vars/Debian.yml#L7)   | str | `wget` |    
| [system_platform_packages.**5**](vars/Debian.yml#L8)   | str | `git` |    
| [system_platform_packages.**6**](vars/Debian.yml#L9)   | str | `jq` |    
| [system_platform_packages.**7**](vars/Debian.yml#L10)   | str | `rsync` |    
| [system_platform_packages.**8**](vars/Debian.yml#L11)   | str | `logrotate` |    
| [system_platform_packages.**9**](vars/Debian.yml#L12)   | str | `nano` |    
| [system_platform_packages.**10**](vars/Debian.yml#L13)   | str | `unzip` |    
| [system_platform_packages.**11**](vars/Debian.yml#L14)   | str | `tree` |    
| [system_platform_packages.**12**](vars/Debian.yml#L15)   | str | `lsof` |    
#### File: vars/RedHat.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [system_platform_packages](vars/RedHat.yml#L4)   | list | `[]` |    
| [system_platform_packages.**0**](vars/RedHat.yml#L5)   | str | `python3` |    
| [system_platform_packages.**1**](vars/RedHat.yml#L6)   | str | `ca-certificates` |    
| [system_platform_packages.**2**](vars/RedHat.yml#L7)   | str | `wget` |    
| [system_platform_packages.**3**](vars/RedHat.yml#L8)   | str | `git` |    
| [system_platform_packages.**4**](vars/RedHat.yml#L9)   | str | `jq` |    
| [system_platform_packages.**5**](vars/RedHat.yml#L10)   | str | `rsync` |    
| [system_platform_packages.**6**](vars/RedHat.yml#L11)   | str | `logrotate` |    
| [system_platform_packages.**7**](vars/RedHat.yml#L12)   | str | `nano` |    
| [system_platform_packages.**8**](vars/RedHat.yml#L13)   | str | `unzip` |    
| [system_platform_packages.**9**](vars/RedHat.yml#L14)   | str | `tree` |    
| [system_platform_packages.**10**](vars/RedHat.yml#L15)   | str | `lsof` |    


### Tasks


#### File: tasks/cleanup.yml

| Name | Module | Has Conditions | Comments |
| ---- | ------ | -------------- | -------- |
| System cleanup ¦ Inspect legacy NIC tuning files | ansible.builtin.stat | False | Preserve legacy settings by default. Only an explicit, validated replacement
may retire the exact unit and generated script previously owned by ubuntu. |
| System cleanup ¦ Read regular legacy NIC tuning files | ansible.builtin.slurp | True |  |
| System cleanup ¦ Identify unchanged role-owned NIC tuning | ansible.builtin.set_fact | False |  |
| System cleanup ¦ Require an explicit verified transition before replacing a legacy tuner | ansible.builtin.assert | True |  |
| System cleanup ¦ Disable unchanged legacy NIC tuning | ansible.builtin.systemd_service | True |  |
| System cleanup ¦ Remove unchanged legacy NIC tuning files | ansible.builtin.file | True |  |
| System cleanup ¦ Report preserved legacy NIC tuning | ansible.builtin.debug | True |  |

#### File: tasks/limits.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| System ¦ Retire blanket memlock rules from the old role-owned file | ansible.builtin.lineinfile | False |
| System ¦ Configure login-session limits | community.general.pam_limits | False |

#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| System ¦ Validate platform and feature selection | ansible.builtin.include_tasks | False |  |
| System ¦ Install baseline packages | ansible.builtin.include_tasks | True |  |
| System ¦ Configure kernel settings | ansible.builtin.include_tasks | True |  |
| System ¦ Configure login-session limits | ansible.builtin.include_tasks | True |  |
| System ¦ Configure explicitly enabled emergency swap | ansible.builtin.include_tasks | True |  |
| System ¦ Configure optional host resolver | ansible.builtin.include_tasks | True |  |
| System ¦ Configure explicitly selected NIC settings | ansible.builtin.include_tasks | False |  |
| System ¦ Inspect legacy NIC tuning and explicit transition | ansible.builtin.include_tasks | False |  |
| System ¦ Perform explicitly requested package maintenance | ansible.builtin.include_tasks | True |  |

#### File: tasks/nic.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| System NIC ¦ Inspect existing role persistence | ansible.builtin.stat | False |
| System NIC ¦ Configure selected devices and retire removed selections | block | True |
| System NIC ¦ Inspect persistence artifact ownership | ansible.builtin.stat | False |
| System NIC ¦ Read existing regular persistence artifacts | ansible.builtin.slurp | True |
| System NIC ¦ Refuse unrelated persistence artifacts | ansible.builtin.assert | True |
| System NIC ¦ Install inspection tools using APT | ansible.builtin.apt | True |
| System NIC ¦ Install inspection tools using DNF | ansible.builtin.dnf | True |
| System NIC ¦ Validate all selected hardware and capabilities before changes | ansible.builtin.command | True |
| System NIC ¦ Record completed preflight | ansible.builtin.set_fact | False |
| System NIC ¦ Transition the former role-owned tuner explicitly | ansible.builtin.include_tasks | False |
| System NIC ¦ Escape selected interface instance names | ansible.builtin.command | False |
| System NIC ¦ Inspect enabled instances | ansible.builtin.find | False |
| System NIC ¦ Disable removed interface selections without resetting hardware | ansible.builtin.systemd_service | True |
| System NIC ¦ Ensure NetworkManager dispatcher directory exists | ansible.builtin.file | False |
| System NIC ¦ Write shared settings and persistence | ansible.builtin.template | False |
| System NIC ¦ Enable device-bound instances | ansible.builtin.systemd_service | True |
| System NIC ¦ Apply configuration changes or repair detected drift | ansible.builtin.systemd_service | True |
| System NIC ¦ Explain check-mode hardware verification boundary | ansible.builtin.debug | True |

#### File: tasks/packages.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| System ¦ Install APT baseline packages | ansible.builtin.apt | True |
| System ¦ Install DNF baseline packages | ansible.builtin.dnf | True |
| System ¦ Install QEMU Guest Agent for virtual machines | block | True |
| System ¦ Install guest agent using APT | ansible.builtin.apt | True |
| System ¦ Install guest agent using DNF | ansible.builtin.dnf | True |
| System ¦ Enable and start QEMU Guest Agent | ansible.builtin.systemd_service | True |

#### File: tasks/resolved.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| System resolver ¦ Assert supported host | ansible.builtin.assert | False |
| System resolver ¦ Install NSS resolver packages | ansible.builtin.apt | True |
| System resolver ¦ Ensure systemd-resolved is enabled and running | ansible.builtin.systemd | False |
| System resolver ¦ Ensure resolved config directory exists | ansible.builtin.file | False |
| System resolver ¦ Remove stale unmanaged resolved drop-ins | ansible.builtin.file | True |
| System resolver ¦ Configure systemd-resolved drop-in | ansible.builtin.copy | False |
| System resolver ¦ Apply DNS stub listener changes before dependent services | ansible.builtin.meta | True |
| System resolver ¦ Point resolv.conf at resolved upstream file | ansible.builtin.file | True |
| System resolver ¦ Ensure NSS uses systemd-resolved before plain DNS | ansible.builtin.lineinfile | True |

#### File: tasks/swap.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| PostgreSQL emergency swap ¦ Discover active swap sources | ansible.builtin.command | False |
| PostgreSQL emergency swap ¦ Discover persistent swap sources | ansible.builtin.command | False |
| PostgreSQL emergency swap ¦ Normalize discovered swap sources | ansible.builtin.set_fact | False |
| PostgreSQL emergency swap ¦ Identify administrator-provided swap | ansible.builtin.set_fact | False |
| PostgreSQL emergency swap ¦ Inspect managed path | ansible.builtin.stat | False |
| PostgreSQL emergency swap ¦ Inspect existing managed path signature | ansible.builtin.command | True |
| PostgreSQL emergency swap ¦ Refuse to overwrite an unrelated managed path | ansible.builtin.assert | True |
| PostgreSQL emergency swap ¦ Preserve administrator-provided swap | ansible.builtin.debug | True |
| PostgreSQL emergency swap ¦ Reconcile managed swap file | block | True |
| PostgreSQL emergency swap ¦ Allocate managed file | ansible.builtin.command | False |
| PostgreSQL emergency swap ¦ Protect managed file | ansible.builtin.file | True |
| PostgreSQL emergency swap ¦ Format newly allocated file | ansible.builtin.command | True |
| PostgreSQL emergency swap ¦ Persist managed file | ansible.builtin.lineinfile | False |
| PostgreSQL emergency swap ¦ Activate managed file | ansible.builtin.command | True |
| PostgreSQL emergency swap ¦ Report safe check-mode plan | ansible.builtin.debug | True |

#### File: tasks/sysctl.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| System ¦ Remove retired keys only from the role-owned sysctl file | ansible.builtin.lineinfile | False |
| System ¦ Persist shared kernel settings | ansible.posix.sysctl | False |

#### File: tasks/updates.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| System updates ¦ Upgrade installed APT packages | ansible.builtin.apt | True |
| System updates ¦ Upgrade installed DNF packages | ansible.builtin.dnf | True |
| System updates ¦ Remove unused APT dependencies when requested | ansible.builtin.apt | True |
| System updates ¦ Clean obsolete APT cache when requested | ansible.builtin.apt | True |
| System updates ¦ Remove unused DNF dependencies when requested | ansible.builtin.dnf | True |

#### File: tasks/validate.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| System ¦ Inspect image-based deployment marker | ansible.builtin.stat | False |
| System ¦ Reject unsupported platforms before changes | ansible.builtin.assert | False |
| System ¦ Validate boolean feature flags | ansible.builtin.assert | False |
| System ¦ Reject unsupported cache maintenance | ansible.builtin.assert | True |
| System ¦ Validate optional resolver support | ansible.builtin.assert | True |
| System ¦ Validate swap inputs before discovery | ansible.builtin.assert | True |
| System NIC ¦ Validate interface selection mapping | ansible.builtin.assert | False |
| System NIC ¦ Validate selected names and independent boolean settings | ansible.builtin.assert | False |
| System NIC ¦ Reset preflight result for this role invocation | ansible.builtin.set_fact | False |
| System ¦ Select native package list | ansible.builtin.include_vars | False |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
