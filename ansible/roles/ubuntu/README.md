<!-- DOCSIBLE START -->

# 📃 Role overview

## ubuntu





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/10/23 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [ubuntu_apt_base_packages](defaults/main.yml#L3)   | list | `[]` |    
| [ubuntu_apt_base_packages.**0**](defaults/main.yml#L4)   | str | `python3` |    
| [ubuntu_apt_base_packages.**1**](defaults/main.yml#L5)   | str | `python3-apt` |    
| [ubuntu_apt_base_packages.**2**](defaults/main.yml#L6)   | str | `ca-certificates` |    
| [ubuntu_apt_base_packages.**3**](defaults/main.yml#L7)   | str | `apt-utils` |    
| [ubuntu_apt_common_packages](defaults/main.yml#L9)   | list | `[]` |    
| [ubuntu_apt_common_packages.**0**](defaults/main.yml#L10)   | str | `curl` |    
| [ubuntu_apt_common_packages.**1**](defaults/main.yml#L11)   | str | `wget` |    
| [ubuntu_apt_common_packages.**2**](defaults/main.yml#L12)   | str | `git` |    
| [ubuntu_apt_common_packages.**3**](defaults/main.yml#L13)   | str | `jq` |    
| [ubuntu_apt_common_packages.**4**](defaults/main.yml#L14)   | str | `rsync` |    
| [ubuntu_apt_common_packages.**5**](defaults/main.yml#L15)   | str | `logrotate` |    
| [ubuntu_apt_common_packages.**6**](defaults/main.yml#L16)   | str | `nano` |    
| [ubuntu_apt_common_packages.**7**](defaults/main.yml#L17)   | str | `unzip` |    
| [ubuntu_apt_common_packages.**8**](defaults/main.yml#L18)   | str | `tree` |    
| [ubuntu_apt_common_packages.**9**](defaults/main.yml#L19)   | str | `lsof` |    
| [ubuntu_apt_python_packages](defaults/main.yml#L21)   | list | `[]` |    
| [ubuntu_apt_python_packages.**0**](defaults/main.yml#L22)   | str | `python3-pip` |    
| [ubuntu_apt_python_packages.**1**](defaults/main.yml#L23)   | str | `python3-venv` |    
| [ubuntu_apt_build_packages](defaults/main.yml#L25)   | list | `[]` |    
| [ubuntu_apt_build_packages.**0**](defaults/main.yml#L26)   | str | `build-essential` |    
| [ubuntu_apt_build_packages.**1**](defaults/main.yml#L27)   | str | `python3-dev` |    
| [ubuntu_apt_build_packages.**2**](defaults/main.yml#L28)   | str | `gcc` |    
| [ubuntu_apt_build_packages.**3**](defaults/main.yml#L29)   | str | `g++` |    
| [ubuntu_apt_build_packages.**4**](defaults/main.yml#L30)   | str | `make` |    
| [ubuntu_apt_admin_packages](defaults/main.yml#L32)   | list | `[]` |    
| [ubuntu_apt_admin_packages.**0**](defaults/main.yml#L33)   | str | `zip` |    
| [ubuntu_apt_admin_packages.**1**](defaults/main.yml#L34)   | str | `p7zip-full` |    
| [ubuntu_apt_admin_packages.**2**](defaults/main.yml#L35)   | str | `argon2` |    
| [ubuntu_apt_admin_packages.**3**](defaults/main.yml#L36)   | str | `pwgen` |    
| [ubuntu_apt_admin_packages.**4**](defaults/main.yml#L37)   | str | `htop` |    
| [ubuntu_apt_admin_packages.**5**](defaults/main.yml#L38)   | str | `iotop` |    
| [ubuntu_apt_admin_packages.**6**](defaults/main.yml#L39)   | str | `nload` |    
| [ubuntu_apt_admin_packages.**7**](defaults/main.yml#L40)   | str | `ncdu` |    
| [ubuntu_apt_admin_packages.**8**](defaults/main.yml#L41)   | str | `mc` |    
| [ubuntu_apt_admin_packages.**9**](defaults/main.yml#L42)   | str | `dnsutils` |    
| [ubuntu_apt_admin_packages.**10**](defaults/main.yml#L43)   | str | `screen` |    
| [ubuntu_apt_admin_packages.**11**](defaults/main.yml#L44)   | str | `tmux` |    
| [ubuntu_apt_admin_packages.**12**](defaults/main.yml#L45)   | str | `apache2-utils` |    
| [ubuntu_apt_admin_packages.**13**](defaults/main.yml#L46)   | str | `moreutils` |    
| [ubuntu_apt_admin_packages.**14**](defaults/main.yml#L47)   | str | `man-db` |    
| [ubuntu_apt_admin_packages.**15**](defaults/main.yml#L48)   | str | `unrar-free` |    
| [ubuntu_apt_network_packages](defaults/main.yml#L50)   | list | `[]` |    
| [ubuntu_apt_network_packages.**0**](defaults/main.yml#L51)   | str | `vnstat` |    
| [ubuntu_apt_network_packages.**1**](defaults/main.yml#L52)   | str | `pciutils` |    
| [ubuntu_apt_network_packages.**2**](defaults/main.yml#L53)   | str | `ethtool` |    
| [ubuntu_apt_firewall_packages](defaults/main.yml#L55)   | list | `[]` |    
| [ubuntu_apt_firewall_packages.**0**](defaults/main.yml#L56)   | str | `ufw` |    
| [ubuntu_apt_docker_packages](defaults/main.yml#L58)   | list | `[]` |    
| [ubuntu_apt_postgres_packages](defaults/main.yml#L59)   | list | `[]` |    
| [ubuntu_apt_postgres_packages.**0**](defaults/main.yml#L60)   | str | `acl` |    
| [ubuntu_apt_swarm_packages](defaults/main.yml#L61)   | list | `[]` |    
| [ubuntu_apt_haproxy_packages](defaults/main.yml#L62)   | list | `[]` |    
| [ubuntu_apt_opentofu_packages](defaults/main.yml#L63)   | list | `[]` |    
| [ubuntu_apt_env_vars](defaults/main.yml#L65)   | dict | `{}` |    
| [ubuntu_apt_env_vars.**DEBIAN_FRONTEND**](defaults/main.yml#L66)   | str | `noninteractive` |    
| [ubuntu_apt_env_vars.**DEBIAN_PRIORITY**](defaults/main.yml#L67)   | str | `critical` |    
| [ubuntu_sysctl_file](defaults/main.yml#L69)   | str | `/etc/sysctl.d/99-ubuntu-tuning.conf` |    
| [ubuntu_sysctl_settings](defaults/main.yml#L71)   | dict | `{}` |    
| [ubuntu_sysctl_settings.fs.inotify.**max_user_watches**](defaults/main.yml#L72)   | int | `524288` |    
| [ubuntu_sysctl_settings.net.core.**default_qdisc**](defaults/main.yml#L73)   | str | `fq` |    
| [ubuntu_sysctl_settings.net.core.**netdev_budget**](defaults/main.yml#L74)   | int | `50000` |    
| [ubuntu_sysctl_settings.net.core.**netdev_max_backlog**](defaults/main.yml#L75)   | int | `100000` |    
| [ubuntu_sysctl_settings.net.core.**rmem_max**](defaults/main.yml#L76)   | int | `67108864` |    
| [ubuntu_sysctl_settings.net.core.**somaxconn**](defaults/main.yml#L77)   | int | `4096` |    
| [ubuntu_sysctl_settings.net.core.**wmem_max**](defaults/main.yml#L78)   | int | `67108864` |    
| [ubuntu_sysctl_settings.net.ipv4.conf.all.**accept_redirects**](defaults/main.yml#L79)   | int | `0` |    
| [ubuntu_sysctl_settings.net.ipv4.conf.all.**accept_source_route**](defaults/main.yml#L80)   | int | `0` |    
| [ubuntu_sysctl_settings.net.ipv4.conf.all.**secure_redirects**](defaults/main.yml#L81)   | int | `0` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_adv_win_scale**](defaults/main.yml#L82)   | int | `2` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_congestion_control**](defaults/main.yml#L83)   | str | `bbr` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_fin_timeout**](defaults/main.yml#L84)   | int | `10` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_max_syn_backlog**](defaults/main.yml#L85)   | int | `30000` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_max_tw_buckets**](defaults/main.yml#L86)   | int | `2000000` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_mtu_probing**](defaults/main.yml#L87)   | int | `1` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_rfc1337**](defaults/main.yml#L88)   | int | `1` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_rmem**](defaults/main.yml#L89)   | str | `4096 87380 33554432` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_sack**](defaults/main.yml#L90)   | int | `1` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_slow_start_after_idle**](defaults/main.yml#L91)   | int | `0` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_tw_reuse**](defaults/main.yml#L92)   | int | `2` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_window_scaling**](defaults/main.yml#L93)   | int | `1` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_wmem**](defaults/main.yml#L94)   | str | `4096 87380 33554432` |    
| [ubuntu_sysctl_settings.net.ipv4.**udp_rmem_min**](defaults/main.yml#L95)   | int | `8192` |    
| [ubuntu_sysctl_settings.net.ipv4.**udp_wmem_min**](defaults/main.yml#L96)   | int | `8192` |    
| [ubuntu_sysctl_settings.net.ipv4.neigh.default.**gc_thresh1**](defaults/main.yml#L97)   | int | `1024` |    
| [ubuntu_sysctl_settings.net.ipv4.neigh.default.**gc_thresh2**](defaults/main.yml#L98)   | int | `2048` |    
| [ubuntu_sysctl_settings.net.ipv4.neigh.default.**gc_thresh3**](defaults/main.yml#L99)   | int | `4096` |    
| [ubuntu_sysctl_settings.vm.**dirty_background_ratio**](defaults/main.yml#L100)   | int | `10` |    
| [ubuntu_sysctl_settings.vm.**dirty_ratio**](defaults/main.yml#L101)   | int | `15` |    
| [ubuntu_sysctl_settings.vm.**swappiness**](defaults/main.yml#L102)   | int | `10` |    
| [ubuntu_postgres_emergency_swap_enabled](defaults/main.yml#L104)   | bool | `False` |    
| [ubuntu_postgres_emergency_swap_path](defaults/main.yml#L105)   | str | `/swapfile` |    
| [ubuntu_postgres_emergency_swap_size_mb](defaults/main.yml#L106)   | int | `2048` |    
| [ubuntu_pam_limits](defaults/main.yml#L108)   | list | `[]` |    
| [ubuntu_pam_limits.**0**](defaults/main.yml#L109)   | dict | `{}` |    
| [ubuntu_pam_limits.0.**domain**](defaults/main.yml#L109)   | str | `*` |    
| [ubuntu_pam_limits.0.**limit_type**](defaults/main.yml#L110)   | str | `-` |    
| [ubuntu_pam_limits.0.**limit_item**](defaults/main.yml#L111)   | str | `nofile` |    
| [ubuntu_pam_limits.0.**value**](defaults/main.yml#L112)   | str | `100000` |    
| [ubuntu_pam_limits.**1**](defaults/main.yml#L113)   | dict | `{}` |    
| [ubuntu_pam_limits.1.**domain**](defaults/main.yml#L113)   | str | `*` |    
| [ubuntu_pam_limits.1.**limit_type**](defaults/main.yml#L114)   | str | `soft` |    
| [ubuntu_pam_limits.1.**limit_item**](defaults/main.yml#L115)   | str | `memlock` |    
| [ubuntu_pam_limits.1.**value**](defaults/main.yml#L116)   | str | `unlimited` |    
| [ubuntu_pam_limits.**2**](defaults/main.yml#L117)   | dict | `{}` |    
| [ubuntu_pam_limits.2.**domain**](defaults/main.yml#L117)   | str | `*` |    
| [ubuntu_pam_limits.2.**limit_type**](defaults/main.yml#L118)   | str | `hard` |    
| [ubuntu_pam_limits.2.**limit_item**](defaults/main.yml#L119)   | str | `memlock` |    
| [ubuntu_pam_limits.2.**value**](defaults/main.yml#L120)   | str | `unlimited` |    
| [ubuntu_netplan_enabled](defaults/main.yml#L122)   | bool | `True` |    
| [ubuntu_netplan_disable_cloud_init_networking](defaults/main.yml#L123)   | bool | `True` |    
| [ubuntu_netplan_verify_address](defaults/main.yml#L124)   | bool | `True` |    
| [ubuntu_netplan_interface](defaults/main.yml#L125)   | str |  |    
| [ubuntu_defaults_netplan_config](defaults/main.yml#L127)   | str | `netplan-config.yaml` |    
| [ubuntu_netplan_config_path](defaults/main.yml#L128)   | str | `/etc/netplan/{{ ubuntu_defaults_netplan_config }}` |    
| [ubuntu_defaults_netplan_gateway](defaults/main.yml#L130)   | str | `<multiline value: folded_strip>` |    
| [ubuntu_defaults_netplan_nameservers](defaults/main.yml#L137)   | str | `<multiline value: folded_strip>` |    
| [ubuntu_netplan_nameservers](defaults/main.yml#L147)   | str | `{{ ubuntu_defaults_netplan_nameservers }}` |    
| [ubuntu_netplan_search_domains](defaults/main.yml#L148)   | list | `[]` |    
| [ubuntu_netplan_prefix](defaults/main.yml#L149)   | int | `24` |    
| [ubuntu_nic_tuning_enabled](defaults/main.yml#L151)   | bool | `True` |    
| [ubuntu_vnstat_enabled](defaults/main.yml#L152)   | bool | `True` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Ubuntu ¦ Install common packages | ansible.builtin.include_tasks | True |  |
| Ubuntu ¦ Install PostgreSQL backup prerequisites | ansible.builtin.include_tasks | True |  |
| Ubuntu ¦ Tune sysctl settings | ansible.builtin.include_tasks | True |  |
| Ubuntu ¦ Configure PostgreSQL emergency swap | ansible.builtin.include_tasks | True |  |
| Ubuntu ¦ Set PAM limits | ansible.builtin.include_tasks | False |  |
| Ubuntu ¦ Configure network tuning | ansible.builtin.include_tasks | False |  |
| Ubuntu ¦ Configure Netplan | ansible.builtin.include_tasks | True |  |

#### File: tasks/sub_tasks/apt.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ubuntu APT ¦ Build effective package profile list | ansible.builtin.set_fact | False |
| Ubuntu APT ¦ Build selected package list | ansible.builtin.set_fact | False |
| Ubuntu APT ¦ Install selected packages | ansible.builtin.apt | True |
| Ubuntu APT ¦ Install qemu-guest-agent on virtual guests | ansible.builtin.apt | True |
| Ubuntu APT ¦ Ensure qemu-guest-agent is enabled and running | ansible.builtin.systemd | True |
| Ubuntu APT ¦ Upgrade installed packages | ansible.builtin.apt | True |
| Ubuntu APT ¦ Check for unnecessary packages | ansible.builtin.command | True |
| Ubuntu APT ¦ Remove unnecessary packages | ansible.builtin.command | True |
| Ubuntu APT ¦ Autoclean package cache | ansible.builtin.command | True |
| Ubuntu APT ¦ Remove explicitly unwanted packages | ansible.builtin.apt | True |

#### File: tasks/sub_tasks/netplan.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Normalize Netplan address and interface inputs | ansible.builtin.set_fact | False |
| Resolve effective Netplan interface | ansible.builtin.set_fact | False |
| Assert Netplan inputs are valid | ansible.builtin.assert | False |
| Disable cloud-init network configuration | ansible.builtin.copy | True |
| Remove cloud-init network configuration disablement | ansible.builtin.file | True |
| Find existing Netplan configs | ansible.builtin.find | False |
| Remove unmanaged Netplan configs | ansible.builtin.file | True |
| Render Netplan config | ansible.builtin.template | False |
| Apply pending Netplan changes | ansible.builtin.meta | False |
| Refresh network facts after Netplan apply | ansible.builtin.setup | True |
| Verify expected static IPv4 address is assigned | ansible.builtin.assert | True |

#### File: tasks/sub_tasks/network.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Configure network-related settings | block | True |
| Check vnstat config | ansible.builtin.stat | False |
| Set vnstat default interface | ansible.builtin.lineinfile | True |
| Gather PCI device list | ansible.builtin.command | False |
| Install NIC tuning script | ansible.builtin.template | True |
| Install NIC tuning systemd unit | ansible.builtin.copy | True |
| Reload systemd | ansible.builtin.systemd_service | True |
| Enable and run NIC tuning service | ansible.builtin.systemd_service | True |

#### File: tasks/sub_tasks/pam.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Configure PAM limits | community.general.pam_limits | False |

#### File: tasks/sub_tasks/postgres_backup_prerequisites.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ubuntu PostgreSQL backup prerequisites ¦ Install package profile | ansible.builtin.apt | False |

#### File: tasks/sub_tasks/postgres_emergency_swap.yml

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

#### File: tasks/sub_tasks/sysctl.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Apply sysctl settings | ansible.posix.sysctl | False |
| Check whether netdev_budget_usecs exists | ansible.builtin.stat | False |
| Apply netdev_budget_usecs | ansible.posix.sysctl | True |
| Remove fs.file-max override | ansible.posix.sysctl | False |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
