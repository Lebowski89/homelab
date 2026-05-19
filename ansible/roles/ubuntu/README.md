<!-- DOCSIBLE START -->

# 📃 Role overview

## ubuntu





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/04/11 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [ubuntu_apt_env_vars](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L3)   | dict | `{}` |    
| [ubuntu_apt_env_vars.**DEBIAN_FRONTEND**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L4)   | str | `noninteractive` |    
| [ubuntu_apt_env_vars.**DEBIAN_PRIORITY**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L5)   | str | `critical` |    
| [ubuntu_ansible_repo_root](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L7)   | str | `/opt` |    
| [ubuntu_ansible_repo_dirname](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L8)   | str | `homelab` |    
| [ubuntu_ansible_repo_path](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L9)   | str | `{{ ubuntu_ansible_repo_root }}/{{ ubuntu_ansible_repo_dirname }}` |    
| [ubuntu_ansible_dirname](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L10)   | str | `ansible` |    
| [ubuntu_ansible_path](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L11)   | str | `{{ ubuntu_ansible_repo_path }}/{{ ubuntu_ansible_dirname }}` |    
| [ubuntu_manage_repo_clone](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L13)   | bool | `True` |    
| [ubuntu_repo_url](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L14)   | str | `https://github.com/Lebowski89/homelab.git` |    
| [ubuntu_repo_version](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L15)   | str | `main` |    
| [ubuntu_ansible_opt_path](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L17)   | str | `/opt/ansible` |    
| [ubuntu_ansible_venv_path](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L18)   | str | `{{ ubuntu_ansible_opt_path }}/ansible-venv` |    
| [ubuntu_ansible_secrets_path](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L19)   | str | `{{ ubuntu_ansible_opt_path }}/.secrets` |    
| [ubuntu_ansible_become_pass_file](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L20)   | str | `{{ ubuntu_ansible_secrets_path }}/.ansible_become_pass` |    
| [ubuntu_ansible_vault_pass_file](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L21)   | str | `{{ ubuntu_ansible_secrets_path }}/.ansible_vault_pass` |    
| [ubuntu_skynet_install](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L23)   | bool | `True` |    
| [ubuntu_skynet_install_path](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L24)   | str | `/usr/local/bin/skynet` |    
| [ubuntu_skynet_doctor_ping_target](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L25)   | str | `tags_skynet` |    
| [ubuntu_skynet_docker_services_vars](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L26)   | str | `{{ ubuntu_ansible_path }}/group_vars/all/docker_services.yml` |    
| [ubuntu_sysctl_file](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L28)   | str | `/etc/sysctl.d/99-ubuntu-tuning.conf` |    
| [ubuntu_sysctl_settings](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L30)   | dict | `{}` |    
| [ubuntu_sysctl_settings.fs.inotify.**max_user_watches**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L31)   | int | `524288` |    
| [ubuntu_sysctl_settings.net.core.**default_qdisc**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L32)   | str | `fq` |    
| [ubuntu_sysctl_settings.net.core.**netdev_budget**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L33)   | int | `50000` |    
| [ubuntu_sysctl_settings.net.core.**netdev_max_backlog**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L34)   | int | `100000` |    
| [ubuntu_sysctl_settings.net.core.**rmem_max**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L35)   | int | `67108864` |    
| [ubuntu_sysctl_settings.net.core.**somaxconn**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L36)   | int | `4096` |    
| [ubuntu_sysctl_settings.net.core.**wmem_max**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L37)   | int | `67108864` |    
| [ubuntu_sysctl_settings.net.ipv4.conf.all.**accept_redirects**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L38)   | int | `0` |    
| [ubuntu_sysctl_settings.net.ipv4.conf.all.**accept_source_route**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L39)   | int | `0` |    
| [ubuntu_sysctl_settings.net.ipv4.conf.all.**secure_redirects**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L40)   | int | `0` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_adv_win_scale**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L41)   | int | `2` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_congestion_control**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L42)   | str | `bbr` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_fin_timeout**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L43)   | int | `10` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_max_syn_backlog**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L44)   | int | `30000` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_max_tw_buckets**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L45)   | int | `2000000` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_mtu_probing**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L46)   | int | `1` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_rfc1337**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L47)   | int | `1` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_rmem**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L48)   | str | `4096 87380 33554432` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_sack**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L49)   | int | `1` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_slow_start_after_idle**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L50)   | int | `0` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_tw_reuse**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L51)   | int | `2` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_window_scaling**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L52)   | int | `1` |    
| [ubuntu_sysctl_settings.net.ipv4.**tcp_wmem**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L53)   | str | `4096 87380 33554432` |    
| [ubuntu_sysctl_settings.net.ipv4.**udp_rmem_min**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L54)   | int | `8192` |    
| [ubuntu_sysctl_settings.net.ipv4.**udp_wmem_min**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L55)   | int | `8192` |    
| [ubuntu_sysctl_settings.vm.**dirty_background_ratio**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L56)   | int | `10` |    
| [ubuntu_sysctl_settings.vm.**dirty_ratio**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L57)   | int | `15` |    
| [ubuntu_sysctl_settings.vm.**swappiness**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L58)   | int | `10` |    
| [ubuntu_sysctl_settings.net.ipv4.neigh.default.**gc_thresh1**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L59)   | int | `1024` |    
| [ubuntu_sysctl_settings.net.ipv4.neigh.default.**gc_thresh2**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L60)   | int | `2048` |    
| [ubuntu_sysctl_settings.net.ipv4.neigh.default.**gc_thresh3**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L61)   | int | `4096` |    
| [ubuntu_pam_limits](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L63)   | list | `[]` |    
| [ubuntu_pam_limits.**0**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L64)   | dict | `{}` |    
| [ubuntu_pam_limits.0.**domain**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L64)   | str | `*` |    
| [ubuntu_pam_limits.0.**limit_type**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L65)   | str | `-` |    
| [ubuntu_pam_limits.0.**limit_item**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L66)   | str | `nofile` |    
| [ubuntu_pam_limits.0.**value**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L67)   | str | `100000` |    
| [ubuntu_pam_limits.**1**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L68)   | dict | `{}` |    
| [ubuntu_pam_limits.1.**domain**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L68)   | str | `*` |    
| [ubuntu_pam_limits.1.**limit_type**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L69)   | str | `soft` |    
| [ubuntu_pam_limits.1.**limit_item**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L70)   | str | `memlock` |    
| [ubuntu_pam_limits.1.**value**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L71)   | str | `unlimited` |    
| [ubuntu_pam_limits.**2**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L72)   | dict | `{}` |    
| [ubuntu_pam_limits.2.**domain**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L72)   | str | `*` |    
| [ubuntu_pam_limits.2.**limit_type**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L73)   | str | `hard` |    
| [ubuntu_pam_limits.2.**limit_item**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L74)   | str | `memlock` |    
| [ubuntu_pam_limits.2.**value**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L75)   | str | `unlimited` |    
| [ubuntu_defaults_netplan_config](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L77)   | str | `netplan-config.yaml` |    
| [ubuntu_netplan_config_path](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L78)   | str | `/etc/netplan/{{ ubuntu_defaults_netplan_config }}` |    
| [ubuntu_defaults_netplan_gateway](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L80)   | str | `<multiline value: folded_strip>` |    
| [ubuntu_defaults_netplan_nameservers](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L87)   | str | `<multiline value: folded_strip>` |    
| [ubuntu_netplan_prefix](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L97)   | int | `24` |    
| [ubuntu_nic_tuning_enabled](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L99)   | bool | `True` |    
| [ubuntu_vnstat_enabled](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L100)   | bool | `True` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Install common apt packages | ansible.builtin.include_tasks | False | ubuntu,ubuntu_apt |
| Clone Homelab repo | ansible.builtin.include_tasks | True | ubuntu,ubuntu_repo |
| Setup Python venv | ansible.builtin.include_tasks | True | ubuntu,ubuntu_venv |
| Install required collections and pip packages | ansible.builtin.include_tasks | True | ubuntu,ubuntu_requirements |
| Install Skynet wrapper | ansible.builtin.include_tasks | True | ubuntu,ubuntu_skynet |
| Tune sysctl settings | ansible.builtin.include_tasks | False | ubuntu,ubuntu_sysctl |
| Set PAM limits | ansible.builtin.include_tasks | False | ubuntu,ubuntu_pam |
| Configure network tuning | ansible.builtin.include_tasks | False | ubuntu,ubuntu_network |
| Configure Netplan | ansible.builtin.include_tasks | True | ubuntu,ubuntu_netplan |

#### File: tasks/sub_tasks/apt.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure python and apt prerequisites are installed | ansible.builtin.apt | False |
| Install common packages | ansible.builtin.apt | False |
| Ensure qemu-guest-agent is enabled and running | ansible.builtin.systemd | False |
| Upgrade installed packages | ansible.builtin.apt | False |
| Remove unnecessary packages | ansible.builtin.apt | False |

#### File: tasks/sub_tasks/netplan.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Assert local_ip is defined for netplan | ansible.builtin.assert | False |
| Find existing netplan configs | ansible.builtin.find | False |
| Remove unmanaged netplan configs | ansible.builtin.file | True |
| Render netplan config | ansible.builtin.template | False |

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

#### File: tasks/sub_tasks/repo.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure repo root exists | ansible.builtin.file | False |
| Clone homelab repo | ansible.builtin.git | True |

#### File: tasks/sub_tasks/requirements.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Assert requirements.txt exists | ansible.builtin.stat | False |
| Fail if requirements.txt is missing | ansible.builtin.fail | True |
| Install Python packages from requirements.txt | ansible.builtin.pip | False |
| Assert Ansible collections requirements file exists | ansible.builtin.stat | False |
| Fail if Ansible collections requirements file is missing | ansible.builtin.fail | True |
| Install Ansible collections from requirements.yml | ansible.builtin.command | False |

#### File: tasks/sub_tasks/skynet.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Assert skynet install path is defined | ansible.builtin.assert | False |
| Create directories | ansible.builtin.file | False |
| Check for become password file | ansible.builtin.stat | False |
| Fail if become password file is missing | ansible.builtin.fail | True |
| Check for vault password file | ansible.builtin.stat | False |
| Fail if vault password file is missing | ansible.builtin.fail | True |
| Install templated skynet wrapper | ansible.builtin.template | True |

#### File: tasks/sub_tasks/sysctl.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Apply sysctl settings | ansible.posix.sysctl | False |
| Check whether netdev_budget_usecs exists | ansible.builtin.stat | False |
| Apply netdev_budget_usecs | ansible.posix.sysctl | True |
| Remove fs.file-max override | ansible.posix.sysctl | False |

#### File: tasks/sub_tasks/venv.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure Ansible opt path exists | ansible.builtin.file | False |
| Create Python virtualenv | ansible.builtin.command | False |
| Upgrade pip tooling in virtualenv | ansible.builtin.pip | False |


## Task Flow Graphs



### Graph for main.yml

```mermaid
flowchart TD
Start
classDef block stroke:#3498db,stroke-width:2px;
classDef task stroke:#4b76bb,stroke-width:2px;
classDef includeTasks stroke:#16a085,stroke-width:2px;
classDef importTasks stroke:#34495e,stroke-width:2px;
classDef includeRole stroke:#2980b9,stroke-width:2px;
classDef importRole stroke:#699ba7,stroke-width:2px;
classDef includeVars stroke:#8e44ad,stroke-width:2px;
classDef rescue stroke:#665352,stroke-width:2px;

  Start-->|Include task| Install_common_apt_packages_sub_tasks_apt_yml_0[install common apt packages<br>include_task: sub tasks apt yml]:::includeTasks
  Install_common_apt_packages_sub_tasks_apt_yml_0-->|Include task| Clone_Homelab_repo_sub_tasks_repo_yml_1[clone homelab repo<br>When: **tags ansible manager  in group names**<br>include_task: sub tasks repo yml]:::includeTasks
  Clone_Homelab_repo_sub_tasks_repo_yml_1-->|Include task| Setup_Python_venv_sub_tasks_venv_yml_2[setup python venv<br>When: **tags ansible manager  in group names**<br>include_task: sub tasks venv yml]:::includeTasks
  Setup_Python_venv_sub_tasks_venv_yml_2-->|Include task| Install_required_collections_and_pip_packages_sub_tasks_requirements_yml_3[install required collections and pip packages<br>When: **tags ansible manager  in group names**<br>include_task: sub tasks requirements yml]:::includeTasks
  Install_required_collections_and_pip_packages_sub_tasks_requirements_yml_3-->|Include task| Install_Skynet_wrapper_sub_tasks_skynet_yml_4[install skynet wrapper<br>When: **tags ansible manager  in group names**<br>include_task: sub tasks skynet yml]:::includeTasks
  Install_Skynet_wrapper_sub_tasks_skynet_yml_4-->|Include task| Tune_sysctl_settings_sub_tasks_sysctl_yml_5[tune sysctl settings<br>include_task: sub tasks sysctl yml]:::includeTasks
  Tune_sysctl_settings_sub_tasks_sysctl_yml_5-->|Include task| Set_PAM_limits_sub_tasks_pam_yml_6[set pam limits<br>include_task: sub tasks pam yml]:::includeTasks
  Set_PAM_limits_sub_tasks_pam_yml_6-->|Include task| Configure_network_tuning_sub_tasks_network_yml_7[configure network tuning<br>include_task: sub tasks network yml]:::includeTasks
  Configure_network_tuning_sub_tasks_network_yml_7-->|Include task| Configure_Netplan_sub_tasks_netplan_yml_8[configure netplan<br>When: **inventory hostname not in  groups  tags opentofu<br>managed     default**<br>include_task: sub tasks netplan yml]:::includeTasks
  Configure_Netplan_sub_tasks_netplan_yml_8-->End
```


### Graph for sub_tasks/apt.yml

```mermaid
flowchart TD
Start
classDef block stroke:#3498db,stroke-width:2px;
classDef task stroke:#4b76bb,stroke-width:2px;
classDef includeTasks stroke:#16a085,stroke-width:2px;
classDef importTasks stroke:#34495e,stroke-width:2px;
classDef includeRole stroke:#2980b9,stroke-width:2px;
classDef importRole stroke:#699ba7,stroke-width:2px;
classDef includeVars stroke:#8e44ad,stroke-width:2px;
classDef rescue stroke:#665352,stroke-width:2px;

  Start-->|Task| Ensure_python_and_apt_prerequisites_are_installed0[ensure python and apt prerequisites are installed]:::task
  Ensure_python_and_apt_prerequisites_are_installed0-->|Task| Install_common_packages1[install common packages]:::task
  Install_common_packages1-->|Task| Ensure_qemu_guest_agent_is_enabled_and_running2[ensure qemu guest agent is enabled and running]:::task
  Ensure_qemu_guest_agent_is_enabled_and_running2-->|Task| Upgrade_installed_packages3[upgrade installed packages]:::task
  Upgrade_installed_packages3-->|Task| Remove_unnecessary_packages4[remove unnecessary packages]:::task
  Remove_unnecessary_packages4-->End
```


### Graph for sub_tasks/netplan.yml

```mermaid
flowchart TD
Start
classDef block stroke:#3498db,stroke-width:2px;
classDef task stroke:#4b76bb,stroke-width:2px;
classDef includeTasks stroke:#16a085,stroke-width:2px;
classDef importTasks stroke:#34495e,stroke-width:2px;
classDef includeRole stroke:#2980b9,stroke-width:2px;
classDef importRole stroke:#699ba7,stroke-width:2px;
classDef includeVars stroke:#8e44ad,stroke-width:2px;
classDef rescue stroke:#665352,stroke-width:2px;

  Start-->|Task| Assert_local_ip_is_defined_for_netplan0[assert local ip is defined for netplan]:::task
  Assert_local_ip_is_defined_for_netplan0-->|Task| Find_existing_netplan_configs1[find existing netplan configs]:::task
  Find_existing_netplan_configs1-->|Task| Remove_unmanaged_netplan_configs2[remove unmanaged netplan configs<br>When: **item path    ubuntu netplan config path**]:::task
  Remove_unmanaged_netplan_configs2-->|Task| Render_netplan_config3[render netplan config]:::task
  Render_netplan_config3-->End
```


### Graph for sub_tasks/network.yml

```mermaid
flowchart TD
Start
classDef block stroke:#3498db,stroke-width:2px;
classDef task stroke:#4b76bb,stroke-width:2px;
classDef includeTasks stroke:#16a085,stroke-width:2px;
classDef importTasks stroke:#34495e,stroke-width:2px;
classDef includeRole stroke:#2980b9,stroke-width:2px;
classDef importRole stroke:#699ba7,stroke-width:2px;
classDef includeVars stroke:#8e44ad,stroke-width:2px;
classDef rescue stroke:#665352,stroke-width:2px;

  Start-->|Block Start| Configure_network_related_settings0_block_start_0[[configure network related settings<br>When: **ansible default ipv4 is defined and ansible<br>default ipv4 type     ether**]]:::block
  Configure_network_related_settings0_block_start_0-->|Task| Check_vnstat_config0[check vnstat config]:::task
  Check_vnstat_config0-->|Task| Set_vnstat_default_interface1[set vnstat default interface<br>When: **ubuntu vnstat enabled   bool and ubuntu vnstat<br>conf stat exists**]:::task
  Set_vnstat_default_interface1-->|Task| Gather_PCI_device_list2[gather pci device list]:::task
  Gather_PCI_device_list2-->|Task| Install_NIC_tuning_script3[install nic tuning script<br>When: **ubuntu nic tuning enabled   bool**]:::task
  Install_NIC_tuning_script3-->|Task| Install_NIC_tuning_systemd_unit4[install nic tuning systemd unit<br>When: **ubuntu nic tuning enabled   bool**]:::task
  Install_NIC_tuning_systemd_unit4-->|Task| Reload_systemd5[reload systemd<br>When: **ubuntu nic tuning enabled   bool and ubuntu nic<br>tuning unit changed**]:::task
  Reload_systemd5-->|Task| Enable_and_run_NIC_tuning_service6[enable and run nic tuning service<br>When: **ubuntu nic tuning enabled   bool**]:::task
  Enable_and_run_NIC_tuning_service6-.->|End of Block| Configure_network_related_settings0_block_start_0
  Enable_and_run_NIC_tuning_service6-->End
```


### Graph for sub_tasks/pam.yml

```mermaid
flowchart TD
Start
classDef block stroke:#3498db,stroke-width:2px;
classDef task stroke:#4b76bb,stroke-width:2px;
classDef includeTasks stroke:#16a085,stroke-width:2px;
classDef importTasks stroke:#34495e,stroke-width:2px;
classDef includeRole stroke:#2980b9,stroke-width:2px;
classDef importRole stroke:#699ba7,stroke-width:2px;
classDef includeVars stroke:#8e44ad,stroke-width:2px;
classDef rescue stroke:#665352,stroke-width:2px;

  Start-->|Task| Configure_PAM_limits0[configure pam limits]:::task
  Configure_PAM_limits0-->End
```


### Graph for sub_tasks/repo.yml

```mermaid
flowchart TD
Start
classDef block stroke:#3498db,stroke-width:2px;
classDef task stroke:#4b76bb,stroke-width:2px;
classDef includeTasks stroke:#16a085,stroke-width:2px;
classDef importTasks stroke:#34495e,stroke-width:2px;
classDef includeRole stroke:#2980b9,stroke-width:2px;
classDef importRole stroke:#699ba7,stroke-width:2px;
classDef includeVars stroke:#8e44ad,stroke-width:2px;
classDef rescue stroke:#665352,stroke-width:2px;

  Start-->|Task| Ensure_repo_root_exists0[ensure repo root exists]:::task
  Ensure_repo_root_exists0-->|Task| Clone_homelab_repo1[clone homelab repo<br>When: **ubuntu manage repo clone   bool**]:::task
  Clone_homelab_repo1-->End
```


### Graph for sub_tasks/requirements.yml

```mermaid
flowchart TD
Start
classDef block stroke:#3498db,stroke-width:2px;
classDef task stroke:#4b76bb,stroke-width:2px;
classDef includeTasks stroke:#16a085,stroke-width:2px;
classDef importTasks stroke:#34495e,stroke-width:2px;
classDef includeRole stroke:#2980b9,stroke-width:2px;
classDef importRole stroke:#699ba7,stroke-width:2px;
classDef includeVars stroke:#8e44ad,stroke-width:2px;
classDef rescue stroke:#665352,stroke-width:2px;

  Start-->|Task| Assert_requirements_txt_exists0[assert requirements txt exists]:::task
  Assert_requirements_txt_exists0-->|Task| Fail_if_requirements_txt_is_missing1[fail if requirements txt is missing<br>When: **not ubuntu requirements txt stat exists**]:::task
  Fail_if_requirements_txt_is_missing1-->|Task| Install_Python_packages_from_requirements_txt2[install python packages from requirements txt]:::task
  Install_Python_packages_from_requirements_txt2-->|Task| Assert_Ansible_collections_requirements_file_exists3[assert ansible collections requirements file<br>exists]:::task
  Assert_Ansible_collections_requirements_file_exists3-->|Task| Fail_if_Ansible_collections_requirements_file_is_missing4[fail if ansible collections requirements file is<br>missing<br>When: **not ubuntu ansible requirements yml stat exists**]:::task
  Fail_if_Ansible_collections_requirements_file_is_missing4-->|Task| Install_Ansible_collections_from_requirements_yml5[install ansible collections from requirements yml]:::task
  Install_Ansible_collections_from_requirements_yml5-->End
```


### Graph for sub_tasks/skynet.yml

```mermaid
flowchart TD
Start
classDef block stroke:#3498db,stroke-width:2px;
classDef task stroke:#4b76bb,stroke-width:2px;
classDef includeTasks stroke:#16a085,stroke-width:2px;
classDef importTasks stroke:#34495e,stroke-width:2px;
classDef includeRole stroke:#2980b9,stroke-width:2px;
classDef importRole stroke:#699ba7,stroke-width:2px;
classDef includeVars stroke:#8e44ad,stroke-width:2px;
classDef rescue stroke:#665352,stroke-width:2px;

  Start-->|Task| Assert_skynet_install_path_is_defined0[assert skynet install path is defined]:::task
  Assert_skynet_install_path_is_defined0-->|Task| Create_directories1[create directories]:::task
  Create_directories1-->|Task| Check_for_become_password_file2[check for become password file]:::task
  Check_for_become_password_file2-->|Task| Fail_if_become_password_file_is_missing3[fail if become password file is missing<br>When: **not ubuntu become pass file stat stat exists**]:::task
  Fail_if_become_password_file_is_missing3-->|Task| Check_for_vault_password_file4[check for vault password file]:::task
  Check_for_vault_password_file4-->|Task| Fail_if_vault_password_file_is_missing5[fail if vault password file is missing<br>When: **tags ansible manager  in group names and not<br>ubuntu vault pass file stat stat exists**]:::task
  Fail_if_vault_password_file_is_missing5-->|Task| Install_templated_skynet_wrapper6[install templated skynet wrapper<br>When: **ubuntu skynet install   bool**]:::task
  Install_templated_skynet_wrapper6-->End
```


### Graph for sub_tasks/sysctl.yml

```mermaid
flowchart TD
Start
classDef block stroke:#3498db,stroke-width:2px;
classDef task stroke:#4b76bb,stroke-width:2px;
classDef includeTasks stroke:#16a085,stroke-width:2px;
classDef importTasks stroke:#34495e,stroke-width:2px;
classDef includeRole stroke:#2980b9,stroke-width:2px;
classDef importRole stroke:#699ba7,stroke-width:2px;
classDef includeVars stroke:#8e44ad,stroke-width:2px;
classDef rescue stroke:#665352,stroke-width:2px;

  Start-->|Task| Apply_sysctl_settings0[apply sysctl settings]:::task
  Apply_sysctl_settings0-->|Task| Check_whether_netdev_budget_usecs_exists1[check whether netdev budget usecs exists]:::task
  Check_whether_netdev_budget_usecs_exists1-->|Task| Apply_netdev_budget_usecs2[apply netdev budget usecs<br>When: **ubuntu netdev budget usecs stat exists and ubuntu<br>defaults sysctl netdev budget usecs is defined**]:::task
  Apply_netdev_budget_usecs2-->|Task| Remove_fs_file_max_override3[remove fs file max override]:::task
  Remove_fs_file_max_override3-->End
```


### Graph for sub_tasks/venv.yml

```mermaid
flowchart TD
Start
classDef block stroke:#3498db,stroke-width:2px;
classDef task stroke:#4b76bb,stroke-width:2px;
classDef includeTasks stroke:#16a085,stroke-width:2px;
classDef importTasks stroke:#34495e,stroke-width:2px;
classDef includeRole stroke:#2980b9,stroke-width:2px;
classDef importRole stroke:#699ba7,stroke-width:2px;
classDef includeVars stroke:#8e44ad,stroke-width:2px;
classDef rescue stroke:#665352,stroke-width:2px;

  Start-->|Task| Ensure_Ansible_opt_path_exists0[ensure ansible opt path exists]:::task
  Ensure_Ansible_opt_path_exists0-->|Task| Create_Python_virtualenv1[create python virtualenv]:::task
  Create_Python_virtualenv1-->|Task| Upgrade_pip_tooling_in_virtualenv2[upgrade pip tooling in virtualenv]:::task
  Upgrade_pip_tooling_in_virtualenv2-->End
```







#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
