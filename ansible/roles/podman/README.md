<!-- DOCSIBLE START -->

# 📃 Role overview

## podman





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/11/10 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [podman_install_enable](defaults/main.yml#L3)   | bool | `True` |    
| [podman_state](defaults/main.yml#L4)   | str | `present` |    
| [podman_update_cache](defaults/main.yml#L5)   | bool | `True` |    
| [podman_cache_valid_time](defaults/main.yml#L6)   | int | `3600` |    
| [podman_min_version](defaults/main.yml#L7)   | str | `5.4.2` |    
| [podman_docker_iptables_compatibility](defaults/main.yml#L9)   | bool | `False` |    
| [podman_quadlet_generator_paths](defaults/main.yml#L10)   | list | `[]` |    
| [podman_quadlet_generator_paths.**0**](defaults/main.yml#L11)   | str | `/usr/lib/systemd/system-generators/podman-system-generator` |    
| [podman_quadlet_generator_paths.**1**](defaults/main.yml#L11)   | str | `/lib/systemd/system-generators/podman-system-generator` |    
| [podman_packages](defaults/main.yml#L13)   | str | `{{ podman_platform_packages[ansible_facts.os_family] }}` |    
| [podman_install_extra_packages](defaults/main.yml#L14)   | list | `[]` |    
| [podman_shared_network_name](defaults/main.yml#L15)   | str | `mgt-services` |    
| [podman_shared_network_dns_bind_port](defaults/main.yml#L16)   | int | `5533` |    


### Vars

**These are variables with higher priority**
#### File: vars/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [podman_platform_packages](vars/main.yml#L3)   | dict | `{}` |    
| [podman_platform_packages.**Debian**](vars/main.yml#L4)   | list | `[]` |    
| [podman_platform_packages.Debian.**0**](vars/main.yml#L6)   | str | `acl` |    
| [podman_platform_packages.Debian.**1**](vars/main.yml#L7)   | str | `podman` |    
| [podman_platform_packages.Debian.**2**](vars/main.yml#L8)   | str | `crun` |    
| [podman_platform_packages.Debian.**3**](vars/main.yml#L9)   | str | `netavark` |    
| [podman_platform_packages.Debian.**4**](vars/main.yml#L10)   | str | `aardvark-dns` |    
| [podman_platform_packages.Debian.**5**](vars/main.yml#L11)   | str | `containernetworking-plugins` |    
| [podman_platform_packages.Debian.**6**](vars/main.yml#L12)   | str | `uidmap` |    
| [podman_platform_packages.Debian.**7**](vars/main.yml#L13)   | str | `slirp4netns` |    
| [podman_platform_packages.Debian.**8**](vars/main.yml#L14)   | str | `passt` |    
| [podman_platform_packages.Debian.**9**](vars/main.yml#L15)   | str | `fuse-overlayfs` |    
| [podman_platform_packages.Debian.**10**](vars/main.yml#L16)   | str | `dbus-user-session` |    
| [podman_platform_packages.**RedHat**](vars/main.yml#L17)   | list | `[]` |    
| [podman_platform_packages.RedHat.**0**](vars/main.yml#L18)   | str | `acl` |    
| [podman_platform_packages.RedHat.**1**](vars/main.yml#L19)   | str | `podman` |    
| [podman_platform_packages.RedHat.**2**](vars/main.yml#L20)   | str | `crun` |    
| [podman_platform_packages.RedHat.**3**](vars/main.yml#L21)   | str | `netavark` |    
| [podman_platform_packages.RedHat.**4**](vars/main.yml#L22)   | str | `aardvark-dns` |    
| [podman_platform_packages.RedHat.**5**](vars/main.yml#L23)   | str | `passt` |    
| [podman_platform_packages.RedHat.**6**](vars/main.yml#L24)   | str | `fuse-overlayfs` |    
| [podman_platform_packages.RedHat.**7**](vars/main.yml#L25)   | str | `shadow-utils` |    
| [podman_platform_packages.RedHat.**8**](vars/main.yml#L26)   | str | `dbus-broker` |    
| [podman_platform_packages.RedHat.**9**](vars/main.yml#L27)   | str | `systemd-pam` |    
| [podman_platform_packages.RedHat.**10**](vars/main.yml#L28)   | str | `container-selinux` |    


### Tasks


#### File: tasks/apt.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Podman ¦ Install APT runtime packages | ansible.builtin.apt | False |

#### File: tasks/firewall_compatibility.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Podman compatibility ¦ Explain deferred provider checks in check mode | ansible.builtin.debug | True |
| Podman compatibility ¦ Validate the selected installed provider | block | True |
| Podman compatibility ¦ Inspect only local rootful runtime metadata | ansible.builtin.command | False |
| Podman compatibility ¦ Resolve provider metadata | ansible.builtin.set_fact | False |
| Podman compatibility ¦ Require the reviewed Netavark iptables provider | ansible.builtin.assert | False |
| Podman compatibility ¦ Inspect both families of compatibility tools | ansible.builtin.command | False |
| Podman compatibility ¦ Require consistent nf_tables tools | ansible.builtin.assert | False |
| Podman compatibility ¦ Ensure the system configuration directory | ansible.builtin.file | True |
| Podman compatibility ¦ Persist the explicit compatibility provider | ansible.builtin.copy | True |
| Podman compatibility ¦ Retire only this role's provider choice | ansible.builtin.file | True |

#### File: tasks/firewall_compatibility_inspect.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Podman compatibility ¦ Discover operator configuration without reading its values | ansible.builtin.find | True |
| Podman compatibility ¦ Require inspectable configuration files | ansible.builtin.assert | True |
| Podman compatibility ¦ Inspect existing provider declarations privately | ansible.builtin.slurp | True |
| Podman compatibility ¦ Detect competing provider ownership privately | ansible.builtin.set_fact | True |
| Podman compatibility ¦ Refuse competing operator provider declarations | ansible.builtin.assert | True |
| Podman compatibility ¦ Inspect configuration environment overrides privately | ansible.builtin.command | True |
| Podman compatibility ¦ Record whether the execution environment selects another configuration | ansible.builtin.set_fact | True |
| Podman compatibility ¦ Require the ordinary host configuration context | ansible.builtin.assert | True |
| Podman compatibility ¦ Inspect the local runtime binary before a provider transition | ansible.builtin.stat | True |
| Podman compatibility ¦ Inspect running rootful containers before changing the provider | ansible.builtin.command | True |
| Podman compatibility ¦ Inspect rootless container monitors before changing the host default | ansible.builtin.command | True |
| Podman compatibility ¦ Require quiescent Podman users for a provider transition | ansible.builtin.assert | True |

#### File: tasks/firewall_compatibility_preflight.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Podman compatibility ¦ Inspect the role-owned provider drop-in | ansible.builtin.stat | False |
| Podman compatibility ¦ Refuse ambiguous configuration ownership | ansible.builtin.assert | False |
| Podman compatibility ¦ Read existing managed configuration privately | ansible.builtin.slurp | True |
| Podman compatibility ¦ Determine ownership without publishing file contents | ansible.builtin.set_fact | False |
| Podman compatibility ¦ Preserve externally edited configuration | ansible.builtin.assert | False |
| Podman compatibility ¦ Inspect an explicit provider transition | ansible.builtin.import_tasks | True |

#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Podman ¦ Validate platform and package choices | ansible.builtin.import_tasks | False |  |
| Podman ¦ Preview package installation in check mode | ansible.builtin.debug | True |  |
| Podman ¦ Inspect compatibility configuration before package changes | ansible.builtin.import_tasks | False |  |
| Podman ¦ Install distribution packages | ansible.builtin.include_tasks | True |  |
| Podman ¦ Validate installed runtime capabilities | ansible.builtin.import_tasks | False |  |
| Podman ¦ Configure the explicit Docker compatibility choice | ansible.builtin.import_tasks | False |  |

#### File: tasks/rootful_dns.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Podman rootful DNS ¦ Validate forwarding port | ansible.builtin.assert | False |
| Podman rootful DNS ¦ Ensure configuration drop-in directory | ansible.builtin.file | False |
| Podman rootful DNS ¦ Configure only the netavark DNS bind port | ansible.builtin.template | False |

#### File: tasks/rpm.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Podman ¦ Install RPM runtime packages | ansible.builtin.dnf | False |

#### File: tasks/shared_network.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Podman shared network ¦ Validate central network inputs | ansible.builtin.assert | False |  |
| Podman shared network ¦ Gather platform and SELinux facts | ansible.builtin.setup | False |  |
| Podman shared network ¦ Validate supported platform before changes | ansible.builtin.import_tasks | False |  |
| Podman shared network ¦ Validate the separately installed runtime | ansible.builtin.import_tasks | False |  |
| Podman shared network ¦ Inspect the rootful runtime before changes | ansible.builtin.include_tasks | True |  |
| Podman shared network ¦ Explain deferred runtime verification | ansible.builtin.debug | True |  |
| Podman shared network ¦ Configure non-conflicting rootful bridge DNS | ansible.builtin.include_tasks | False |  |
| Podman shared network ¦ Ensure system Quadlet directory | ansible.builtin.file | False |  |
| Podman shared network ¦ Write persistent central bridge | ansible.builtin.template | False |  |
| Podman shared network ¦ Reload system manager | ansible.builtin.systemd_service | True |  |
| Podman shared network ¦ Start central bridge | ansible.builtin.systemd_service | True |  |

#### File: tasks/shared_network_inspect.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Podman shared network ¦ Inspect the local runtime host | ansible.builtin.command | False |
| Podman shared network ¦ Resolve only current runtime metadata | ansible.builtin.set_fact | False |
| Podman shared network ¦ Require local rootful Netavark with DNS support | ansible.builtin.assert | False |
| Podman shared network ¦ Inspect distribution networking helpers | ansible.builtin.stat | False |
| Podman shared network ¦ Require executable Netavark and Aardvark providers | ansible.builtin.assert | False |
| Podman shared network ¦ Inspect the selected existing network | ansible.builtin.command | False |
| Podman shared network ¦ Read existing network properties | ansible.builtin.command | True |
| Podman shared network ¦ Refuse an incompatible existing network | ansible.builtin.assert | True |
| Podman shared network ¦ Inspect the previously managed DNS drop-in | ansible.builtin.stat | False |
| Podman shared network ¦ Refuse to replace a DNS configuration symlink or directory | ansible.builtin.assert | False |
| Podman shared network ¦ Read the existing DNS port declaration | ansible.builtin.slurp | True |
| Podman shared network ¦ Determine whether the DNS port declaration changes | ansible.builtin.set_fact | False |
| Podman shared network ¦ Inspect running rootful network users before changing DNS | ansible.builtin.command | True |
| Podman shared network ¦ Require quiescent bridge users for a DNS port change | ansible.builtin.assert | True |
| Podman shared network ¦ Inspect firewall service state without changing it | ansible.builtin.service_facts | False |
| Podman shared network ¦ Report preserved firewall ownership | ansible.builtin.debug | False |

#### File: tasks/validate.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Podman ¦ Validate supported platform | ansible.builtin.import_tasks | False |
| Podman ¦ Validate installation options | ansible.builtin.assert | False |
| Podman ¦ Inspect cgroup v2 before installation | ansible.builtin.stat | False |
| Podman ¦ Assert cgroup v2 | ansible.builtin.assert | False |
| Podman ¦ Inspect installed packages before installation | ansible.builtin.package_facts | False |
| Podman ¦ Reject Docker CLI replacement and conflicting runtime choices | ansible.builtin.assert | False |

#### File: tasks/validate_platform.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Podman ¦ Detect Atomic or OSTree deployment | ansible.builtin.stat | False |
| Podman ¦ Assert supported host | ansible.builtin.assert | False |

#### File: tasks/validate_runtime.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Podman ¦ Check installed version | ansible.builtin.command | False |
| Podman ¦ Defer runtime validation in fresh-host check mode | ansible.builtin.debug | True |
| Podman ¦ Assert Quadlet-capable version | ansible.builtin.assert | True |
| Podman ¦ Check system Quadlet generator | ansible.builtin.stat | True |
| Podman ¦ Record system Quadlet generator path | ansible.builtin.set_fact | True |
| Podman ¦ Assert system Quadlet generator exists | ansible.builtin.assert | True |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
