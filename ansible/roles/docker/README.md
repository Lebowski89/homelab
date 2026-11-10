<!-- DOCSIBLE START -->

# 📃 Role overview

## docker





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/11/10 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [docker_packages](defaults/main.yml#L3)   | str | `<multiline value: folded_strip>` |    
| [docker_prereq_packages](defaults/main.yml#L7)   | str | `{{ docker_platform_prereq_packages[ansible_facts.os_family] }}` |    
| [docker_apt_arch_map](defaults/main.yml#L9)   | dict | `{}` |    
| [docker_apt_arch_map.**x86_64**](defaults/main.yml#L10)   | str | `amd64` |    
| [docker_apt_arch_map.**aarch64**](defaults/main.yml#L11)   | str | `arm64` |    
| [docker_apt_arch_map.**armv7l**](defaults/main.yml#L12)   | str | `armhf` |    
| [docker_apt_arch_map.**ppc64le**](defaults/main.yml#L13)   | str | `ppc64el` |    
| [docker_apt_arch](defaults/main.yml#L15)   | str | `{{ docker_apt_arch_map[ansible_facts.architecture] ¦ default(ansible_facts.architecture) }}` |    
| [docker_repo_url](defaults/main.yml#L17)   | str | `https://download.docker.com/linux/{{ docker_repo_platform }}` |    
| [docker_repo_suite](defaults/main.yml#L19)   | str | `{{ 'trixie' if ansible_facts.distribution == 'LMDE' else ansible_facts.distribution_release }}` |    
| [docker_rpm_key_url](defaults/main.yml#L20)   | str | `{{ docker_repo_url }}/gpg` |    
| [docker_rpm_key_fingerprint](defaults/main.yml#L21)   | str | `060A61C51B558A7F742B77AAC52FEB6B621E9F35` |    
| [docker_rpm_baseurl](defaults/main.yml#L22)   | str | `{{ docker_repo_url }}/$releasever/$basearch/{{ docker_repo_channel }}` |    
| [docker_repo_channel](defaults/main.yml#L23)   | str | `stable` |    
| [docker_keyring_dir](defaults/main.yml#L24)   | str | `/etc/apt/keyrings` |    
| [docker_keyring_file](defaults/main.yml#L25)   | str | `/etc/apt/keyrings/docker.asc` |    
| [docker_repo_filename](defaults/main.yml#L26)   | str | `docker` |    
| [docker_install_compose_plugin](defaults/main.yml#L28)   | bool | `True` |    
| [docker_manage_user](defaults/main.yml#L29)   | bool | `False` |    
| [docker_user](defaults/main.yml#L30)   | str |  |    
| [docker_selinux_enable](defaults/main.yml#L33)   | bool | `False` |    
| [docker_swarm_join_availability](defaults/main.yml#L36)   | str | `active` |    
| [docker_network](defaults/main.yml#L38)   | str | `overlay` |    
| [docker_network_driver](defaults/main.yml#L39)   | str | `overlay` |    
| [docker_network_subnet](defaults/main.yml#L40)   | str | `172.98.0.0/24` |    
| [docker_prune_threshold_percent](defaults/main.yml#L42)   | int | `80` |    
| [docker_prune_filesystem_path](defaults/main.yml#L43)   | str | `/` |    
| [docker_prune_until](defaults/main.yml#L44)   | str | `168h` |    
| [docker_prune_images](defaults/main.yml#L46)   | bool | `True` |    
| [docker_prune_containers](defaults/main.yml#L47)   | bool | `True` |    
| [docker_prune_builder_cache](defaults/main.yml#L48)   | bool | `True` |    
| [docker_prune_networks](defaults/main.yml#L49)   | bool | `False` |    
| [docker_prune_volumes](defaults/main.yml#L50)   | bool | `False` |    
| [docker_prune_manage_timer](defaults/main.yml#L52)   | bool | `True` |    
| [docker_prune_timer_name](defaults/main.yml#L53)   | str | `docker-prune-safe` |    
| [docker_prune_timer_on_calendar](defaults/main.yml#L54)   | str | `Sun *-*-* 04:30:00` |    
| [docker_prune_timer_randomized_delay_sec](defaults/main.yml#L55)   | str | `1h` |    
| [docker_prune_script_path](defaults/main.yml#L56)   | str | `/usr/local/sbin/docker-prune-safe` |    
| [docker_prune_timer_min_usage_percent](defaults/main.yml#L60)   | int | `0` |    
| [docker_prune_unraid_user_script_manage](defaults/main.yml#L62)   | bool | `True` |    
| [docker_prune_unraid_user_script_name](defaults/main.yml#L63)   | str | `docker-prune-safe` |    
| [docker_prune_unraid_user_scripts_root](defaults/main.yml#L64)   | str | `/boot/config/plugins/user.scripts/scripts` |    
| [docker_prune_unraid_user_script_dir](defaults/main.yml#L65)   | str | `{{ docker_prune_unraid_user_scripts_root }}/{{ docker_prune_unraid_user_script_name }}` |    
| [docker_prune_unraid_user_script_path](defaults/main.yml#L66)   | str | `{{ docker_prune_unraid_user_script_dir }}/script` |    


### Vars

**These are variables with higher priority**
#### File: vars/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [docker_repo_platform](vars/main.yml#L3)   | str | `<multiline value: folded_strip>` |    
| [docker_platform_prereq_packages](vars/main.yml#L6)   | dict | `{}` |    
| [docker_platform_prereq_packages.**Debian**](vars/main.yml#L7)   | list | `[]` |    
| [docker_platform_prereq_packages.Debian.**0**](vars/main.yml#L7)   | str | `ca-certificates` |    
| [docker_platform_prereq_packages.Debian.**1**](vars/main.yml#L7)   | str | `curl` |    
| [docker_platform_prereq_packages.Debian.**2**](vars/main.yml#L7)   | str | `python3-debian` |    
| [docker_platform_prereq_packages.**RedHat**](vars/main.yml#L8)   | str | `{{ ['ca-certificates'] + (['python3-docker'] if ansible_facts.distribution == 'Fedora' else []) }}` |    
| [docker_conflicting_packages](vars/main.yml#L10)   | list | `[]` |    
| [docker_conflicting_packages.**0**](vars/main.yml#L11)   | str | `podman-docker` |    
| [docker_conflicting_packages.**1**](vars/main.yml#L12)   | str | `containerd` |    
| [docker_conflicting_packages.**2**](vars/main.yml#L13)   | str | `runc` |    
| [docker_conflicting_packages.**3**](vars/main.yml#L14)   | str | `docker.io` |    
| [docker_conflicting_packages.**4**](vars/main.yml#L15)   | str | `docker-compose` |    
| [docker_conflicting_packages.**5**](vars/main.yml#L16)   | str | `docker-compose-v2` |    
| [docker_conflicting_packages.**6**](vars/main.yml#L17)   | str | `docker-doc` |    
| [docker_conflicting_packages.**7**](vars/main.yml#L18)   | str | `docker-buildx` |    
| [docker_conflicting_packages.**8**](vars/main.yml#L18)   | str | `docker` |    
| [docker_conflicting_packages.**9**](vars/main.yml#L20)   | str | `docker-client` |    
| [docker_conflicting_packages.**10**](vars/main.yml#L21)   | str | `docker-client-latest` |    
| [docker_conflicting_packages.**11**](vars/main.yml#L22)   | str | `docker-common` |    
| [docker_conflicting_packages.**12**](vars/main.yml#L23)   | str | `docker-latest` |    
| [docker_conflicting_packages.**13**](vars/main.yml#L24)   | str | `docker-latest-logrotate` |    
| [docker_conflicting_packages.**14**](vars/main.yml#L25)   | str | `docker-logrotate` |    
| [docker_conflicting_packages.**15**](vars/main.yml#L26)   | str | `docker-selinux` |    
| [docker_conflicting_packages.**16**](vars/main.yml#L27)   | str | `docker-engine-selinux` |    
| [docker_conflicting_packages.**17**](vars/main.yml#L27)   | str | `docker-engine` |    
| [docker_conflicting_packages.**18**](vars/main.yml#L29)   | str | `moby-engine` |    
| [docker_conflicting_packages.**19**](vars/main.yml#L30)   | str | `moby-cli` |    
| [docker_conflicting_packages.**20**](vars/main.yml#L31)   | str | `moby-containerd` |    
| [docker_conflicting_packages.**21**](vars/main.yml#L32)   | str | `moby-runc` |    


### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Docker ¦ Detect externally managed Unraid installation | ansible.builtin.stat | True |  |
| Docker ¦ Retain Unraid managed installation | ansible.builtin.debug | True |  |
| Install Docker | ansible.builtin.include_tasks | True | docker,docker_install |
| Configure Docker Swarm | ansible.builtin.include_tasks | True | docker,docker_swarm,docker_swarm_init,docker_swarm_join,docker_swarm_network,docker_swarm_labels |
| Docker Prune Cleanup | ansible.builtin.include_tasks | False | docker_prune,docker_prune_dangling,docker_prune_unused,docker_prune_volumes |
| Docker Prune Timer | ansible.builtin.include_tasks | False | docker_prune_timer |
| Docker Prune Unraid User Script | ansible.builtin.include_tasks | False | docker_prune_unraid_user_script |

#### File: tasks/sub_tasks/install.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Docker ¦ Validate platform and package conflicts | ansible.builtin.import_tasks | False |
| Docker ¦ Inspect the explicit SELinux transition before installation | ansible.builtin.import_tasks | True |
| Docker ¦ Prepare Rocky 10 bridge kernel support | ansible.builtin.import_tasks | True |
| Docker ¦ Preview installation in check mode | ansible.builtin.debug | True |
| Docker ¦ Install APT repository and packages | ansible.builtin.import_tasks | True |
| Docker ¦ Install RPM repository and packages | ansible.builtin.import_tasks | True |
| Docker ¦ Apply the explicit SELinux configuration | ansible.builtin.import_tasks | True |
| Docker ¦ Enable and start the daemon | ansible.builtin.systemd_service | True |
| Docker ¦ Verify the requested SELinux capability | block | True |
| Docker SELinux ¦ Verify the local daemon advertises SELinux privately | ansible.builtin.uri | False |
| Ensure docker group exists | ansible.builtin.group | True |
| Add user to docker group | ansible.builtin.user | True |

#### File: tasks/sub_tasks/install/apt.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure apt prerequisites are installed | ansible.builtin.apt | False |
| Ensure Docker keyring directory exists | ansible.builtin.file | False |
| Download Docker GPG key | ansible.builtin.get_url | False |
| Add Docker apt repository | ansible.builtin.deb822_repository | False |
| Find legacy APT source files | ansible.builtin.find | False |
| Remove the previous Docker one-line repository entry | ansible.builtin.lineinfile | False |
| Refresh APT after Docker repository changes | ansible.builtin.apt | True |
| Install Docker packages | ansible.builtin.apt | False |

#### File: tasks/sub_tasks/install/rocky_kernel.yml

| Name | Module | Has Conditions | Comments |
| ---- | ------ | -------------- | -------- |
| Docker ¦ Validate the running Rocky kernel identity | ansible.builtin.assert | False | Minimal/cloud EL10 images can omit xt_addrtype. Match the booted kernel,
rather than installing an unrelated latest kernel and requiring a reboot.
Require the RPM capability: DNF's Ansible adapter can silently skip an older
NEVRA request when another kernel supplement version is already installed. |
| Docker ¦ Inspect address-type match module availability | ansible.builtin.command | False |  |
| Docker ¦ Preview the missing Rocky kernel supplement | ansible.builtin.debug | True |  |
| Docker ¦ Supply address-type match support for the running kernel | block | True |  |
| Docker ¦ Install the matching Rocky kernel supplement | ansible.builtin.dnf | False |  |
| Docker ¦ Verify the running kernel supplement package is installed | ansible.builtin.command | False |  |
| Docker ¦ Verify the installed address-type match module | ansible.builtin.command | False |  |

#### File: tasks/sub_tasks/install/rpm.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Docker ¦ Install RPM prerequisites | ansible.builtin.dnf | False |
| Docker ¦ Trust the Docker RPM signing key | ansible.builtin.rpm_key | False |
| Docker ¦ Configure the Docker RPM repository | ansible.builtin.yum_repository | False |
| Docker ¦ Install RPM runtime packages | ansible.builtin.dnf | False |

#### File: tasks/sub_tasks/install/selinux.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Docker SELinux ¦ Inspect the installed service before writing configuration | ansible.builtin.import_tasks | False |
| Docker SELinux ¦ Ensure the distribution container policy is installed | ansible.builtin.dnf | False |
| Docker SELinux ¦ Ensure the daemon configuration directory | ansible.builtin.file | True |
| Docker SELinux ¦ Validate and persist only the requested configuration change | block | True |
| Docker SELinux ¦ Validate the candidate before replacing daemon.json privately | ansible.builtin.copy | False |
| Docker SELinux ¦ Restart only the idle daemon requiring the capability change | ansible.builtin.systemd_service | True |

#### File: tasks/sub_tasks/install/selinux_preflight.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Docker SELinux ¦ Require an enforcing supported host | ansible.builtin.assert | False |
| Docker SELinux ¦ Inspect the standard daemon configuration | ansible.builtin.stat | False |
| Docker SELinux ¦ Require a regular configuration file | ansible.builtin.assert | False |
| Docker SELinux ¦ Read existing daemon settings privately | ansible.builtin.slurp | True |
| Docker SELinux ¦ Preserve unrelated daemon settings | block | False |
| Docker SELinux ¦ Parse the existing configuration privately | ansible.builtin.set_fact | False |
| Docker SELinux ¦ Require a JSON object | ansible.builtin.assert | False |
| Docker SELinux ¦ Derive the requested configuration privately | ansible.builtin.set_fact | False |
| Docker SELinux ¦ Inspect existing service state | ansible.builtin.service_facts | False |
| Docker SELinux ¦ Record the existing daemon state | ansible.builtin.set_fact | False |
| Docker SELinux ¦ Inspect the existing service launch | ansible.builtin.import_tasks | True |
| Docker SELinux ¦ Inspect an active daemon before changes | block | True |
| Docker SELinux ¦ Read only the local daemon metadata privately | ansible.builtin.uri | False |
| Docker SELinux ¦ Determine whether the active daemon needs a restart | ansible.builtin.set_fact | False |
| Docker SELinux ¦ Inspect running containers before a required restart | ansible.builtin.uri | True |
| Docker SELinux ¦ Require an idle standalone daemon for a transition | ansible.builtin.assert | True |
| Docker SELinux ¦ Explain deferred runtime checks in check mode | ansible.builtin.debug | True |

#### File: tasks/sub_tasks/install/selinux_unit.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Docker SELinux ¦ Inspect the effective systemd launch privately | ansible.builtin.command | False |
| Docker SELinux ¦ Require direct dockerd and unambiguous configuration ownership | ansible.builtin.assert | False |

#### File: tasks/sub_tasks/install/validate.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Docker ¦ Detect Atomic or OSTree deployment | ansible.builtin.stat | False |
| Docker ¦ Validate supported platform before changes | ansible.builtin.assert | False |
| Docker ¦ Validate installation options | ansible.builtin.assert | False |
| Docker ¦ Inspect installed packages before repository changes | ansible.builtin.package_facts | False |
| Docker ¦ Refuse conflicting runtime or CLI packages | ansible.builtin.assert | False |

#### File: tasks/sub_tasks/prune/cleanup.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Docker prune cleanup ¦ Get filesystem usage | ansible.builtin.command | False |
| Docker prune cleanup ¦ Parse filesystem usage percent | ansible.builtin.set_fact | False |
| Docker prune cleanup ¦ Show current usage | ansible.builtin.debug | False |
| Docker prune cleanup ¦ Run safe cleanup when above threshold | block | True |
| Docker prune cleanup ¦ Show Docker disk usage before cleanup | ansible.builtin.command | False |
| Docker prune cleanup ¦ Remove stopped containers older than retention | ansible.builtin.command | True |
| Docker prune cleanup ¦ Remove unused images older than retention | ansible.builtin.command | True |
| Docker prune cleanup ¦ Remove unused builder cache older than retention | ansible.builtin.command | True |
| Docker prune cleanup ¦ Remove unused networks older than retention | ansible.builtin.command | True |
| Docker prune cleanup ¦ Remove unused volumes | ansible.builtin.command | True |
| Docker prune cleanup ¦ Show Docker disk usage after cleanup | ansible.builtin.command | False |
| Docker prune cleanup ¦ Cleanup summary | ansible.builtin.debug | False |
| Docker prune cleanup ¦ Skip cleanup below threshold | ansible.builtin.debug | True |

#### File: tasks/sub_tasks/prune/timer.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Docker prune timer ¦ Set whether host supports systemd timers | ansible.builtin.set_fact | False |  |
| Docker prune timer ¦ Skip non-systemd hosts | ansible.builtin.debug | True |  |
| Docker prune timer ¦ Install safe prune script | ansible.builtin.copy | True |  |
| Docker prune timer ¦ Manage systemd job | ansible.builtin.include_role | True |  |

#### File: tasks/sub_tasks/prune/unraid_user_script.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Docker prune Unraid User Script ¦ Set whether host is Unraid-style non-systemd | ansible.builtin.set_fact | False |
| Docker prune Unraid User Script ¦ Skip unsupported hosts | ansible.builtin.debug | True |
| Docker prune Unraid User Script ¦ Check User Scripts plugin directory | ansible.builtin.stat | True |
| Docker prune Unraid User Script ¦ Assert User Scripts plugin exists | ansible.builtin.assert | True |
| Docker prune Unraid User Script ¦ Ensure script directory exists | ansible.builtin.file | True |
| Docker prune Unraid User Script ¦ Install safe prune script | ansible.builtin.copy | True |
| Docker prune Unraid User Script ¦ Show next manual step | ansible.builtin.debug | True |

#### File: tasks/sub_tasks/swarm.yml

| Name | Module | Has Conditions | Tags | Comments |
| ---- | ------ | -------------- | -----| -------- |
| Ensure this host is part of the swarm inventory | ansible.builtin.set_fact | False | docker_swarm_init,docker_swarm_join,docker_swarm_network,docker_swarm_labels |  |
| End swarm tasks for non-swarm hosts | ansible.builtin.meta | True | docker_swarm_init,docker_swarm_join,docker_swarm_network,docker_swarm_labels |  |
| Assert primary swarm manager is defined | ansible.builtin.assert | False | docker_swarm_init,docker_swarm_join,docker_swarm_network,docker_swarm_labels |  |
| Assert local_ip is defined for swarm node | ansible.builtin.assert | False | docker_swarm_init,docker_swarm_join,docker_swarm_network,docker_swarm_labels |  |
| Initialise swarm on primary manager | community.docker.docker_swarm | True | d,o,c,k,e,r,_,s,w,a,r,m,_,i,n,i,t |  |
| Join nodes to the existing Swarm | block | False | d,o,c,k,e,r,_,s,w,a,r,m,_,j,o,i,n |  |
| Validate Swarm join settings | ansible.builtin.assert | False |  |  |
| Inspect the primary manager without retrieving join tokens | ansible.builtin.uri | False |  |  |
| Verify the primary manager is available | ansible.builtin.assert | False |  |  |
| Inspect local Swarm membership | ansible.builtin.uri | False |  |  |
| Validate local Swarm state | ansible.builtin.assert | False |  |  |
| Inspect existing membership on the intended primary | ansible.builtin.uri | True |  |  |
| Verify existing membership and role | ansible.builtin.assert | True |  |  |
| Preview joining an inactive node | ansible.builtin.debug | True |  |  |
| Retrieve the required join token | ansible.builtin.command | True |  |  |
| Join the intended Swarm with the selected availability | ansible.builtin.uri | True |  | The Engine API supports join-time availability; the SDK-backed swarm
module does not. Sending JSON over the Unix socket also keeps the token
out of command arguments and needs no Python Docker SDK on the host. |
| Conduct overlay network tasks | block | True | d,o,c,k,e,r,_,s,w,a,r,m,_,n,e,t,w,o,r,k |  |
| Register overlay network | community.docker.docker_network_info | False |  |  |
| Create overlay network | community.docker.docker_network | True |  |  |
| Apply swarm node labels | community.docker.docker_node | True | d,o,c,k,e,r,_,s,w,a,r,m,_,l,a,b,e,l,s |  |
| Explain deferred configuration of the planned Swarm | ansible.builtin.debug | True | docker_swarm_network,docker_swarm_labels |  |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
