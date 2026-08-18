<!-- DOCSIBLE START -->

# 📃 Role overview

## podman_services





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/08/16 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [podman_services_system_quadlet_dir](defaults/main.yml#L3)   | str | `/etc/containers/systemd` |    
| [podman_services_quadlet_dir](defaults/main.yml#L4)   | str | `{{ podman_services_system_quadlet_dir }}` |    
| [podman_services_rootless_home_root](defaults/main.yml#L5)   | str | `/var/lib` |    
| [podman_services_rootless_pasta_subnet](defaults/main.yml#L6)   | str | `10.0.2.0/24` |    
| [podman_services_rootless_pasta_gateway](defaults/main.yml#L7)   | str | `10.0.2.2` |    
| [podman_services_rootless_pasta_dns_forward](defaults/main.yml#L8)   | str | `10.0.2.3` |    
| [podman_services_execution_state_dir](defaults/main.yml#L9)   | str | `/var/lib/podman-services` |    
| [podman_services_nologin_shell](defaults/main.yml#L10)   | str | `/usr/sbin/nologin` |    
| [podman_services_action_remove](defaults/main.yml#L11)   | str | `{{ 'remove' in (ansible_run_tags ¦ default([])) }}` |    
| [podman_services_action_recreate](defaults/main.yml#L12)   | str | `{{ 'recreate' in (ansible_run_tags ¦ default([])) }}` |    
| [podman_services_action_update](defaults/main.yml#L13)   | str | `{{ 'update' in (ansible_run_tags ¦ default([])) }}` |    
| [podman_services_action_drift](defaults/main.yml#L14)   | str | `{{ 'drift' in (ansible_run_tags ¦ default([])) }}` |    
| [podman_services_action_bootstrap](defaults/main.yml#L15)   | str | `{{ 'bootstrap' in (ansible_run_tags ¦ default([])) }}` |    
| [podman_services_common_action](defaults/main.yml#L16)   | str | `<multiline value: folded_strip>` |    
| [podman_services_state](defaults/main.yml#L24)   | str | `<multiline value: folded_strip>` |    
| [podman_services_pull_images](defaults/main.yml#L33)   | bool | `True` |    
| [podman_services_traefik_delegate](defaults/main.yml#L34)   | str | `{{ podman_services_controller_host }}` |    
| [podman_services_traefik_dynamic_dir](defaults/main.yml#L35)   | str | `/opt/traefik/dynamic` |    
| [podman_services_traefik_dynamic_owner](defaults/main.yml#L36)   | str | `1000` |    
| [podman_services_traefik_dynamic_group](defaults/main.yml#L37)   | str | `1000` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Podman services ¦ Initialize service | ansible.builtin.include_tasks | False |  |
| Podman services ¦ Prepare execution environment | ansible.builtin.include_tasks | False |  |
| Podman services ¦ Check configured external network | ansible.builtin.command | True |  |
| Podman services ¦ Verify configured external network exists | ansible.builtin.assert | True |  |
| Podman services ¦ Build application preparation context | ansible.builtin.set_fact | False |  |
| Podman services ¦ Validate application settings | ansible.builtin.include_role | False |  |
| Podman services ¦ Store validated application outputs | ansible.builtin.set_fact | False |  |
| Podman services ¦ Check service before recreate | ansible.builtin.command | True |  |
| Podman services ¦ Stop service before recreate | ansible.builtin.systemd_service | True |  |
| Podman services ¦ Generate application secrets | ansible.builtin.include_role | True |  |
| Podman services ¦ Combine service secret values and definitions | ansible.builtin.set_fact | False |  |
| Podman services ¦ Validate secret attachments | ansible.builtin.assert | False |  |
| Podman services ¦ Add Podman secret definitions | ansible.builtin.set_fact | False |  |
| Podman services ¦ Manage Podman secrets | ansible.builtin.include_tasks | True |  |
| Podman services ¦ Build application template values | ansible.builtin.include_role | True |  |
| Podman services ¦ Store application template values | ansible.builtin.set_fact | False |  |
| Podman services ¦ Prepare service files and directories | ansible.builtin.include_role | False |  |
| Podman services ¦ Set rootless bind mount ownership | ansible.builtin.file | True |  |
| Podman services ¦ Configure application | ansible.builtin.include_role | True |  |
| Podman services ¦ Write Quadlet files | ansible.builtin.include_tasks | False |  |
| Podman services ¦ Prepare container image | ansible.builtin.include_tasks | False |  |
| Podman services ¦ Check managed network changes | ansible.builtin.include_tasks | False |  |
| Podman services ¦ Manage service state | ansible.builtin.include_tasks | False |  |
| Podman services ¦ Configure Traefik integration | ansible.builtin.include_role | True |  |
| Podman services ¦ Remove Podman service | ansible.builtin.include_tasks | True |  |
| Podman services ¦ Remove service integrations | ansible.builtin.include_role | True |  |
| Podman services ¦ Check image drift | ansible.builtin.include_tasks | False |  |
| Podman services ¦ Finish service removal | ansible.builtin.include_tasks | True |  |

#### File: tasks/sub_tasks/check_quadlets.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Check mode ¦ Reset planned Quadlet changes | ansible.builtin.set_fact | False |  |
| Check mode ¦ Build network Quadlet preview | ansible.builtin.set_fact | True |  |
| Check mode ¦ Build volume Quadlet previews | ansible.builtin.set_fact | False |  |
| Check mode ¦ Build environment file preview | ansible.builtin.set_fact | True |  |
| Check mode ¦ Build container Quadlet preview | ansible.builtin.set_fact | False |  |
| Check mode ¦ Validate generated Quadlet previews | ansible.builtin.assert | False |  |
| Check mode ¦ Build safe preview metadata | ansible.builtin.set_fact | False |  |
| Check mode ¦ Check existing generated files | ansible.builtin.stat | False |  |
| Check mode ¦ Read existing generated files | ansible.builtin.slurp | True |  |
| Check mode ¦ Compare planned and existing generated files | ansible.builtin.set_fact | False |  |
| Check mode ¦ Report planned file change | ansible.builtin.debug | True |  |
| Check mode ¦ Clear secret values from preview state | ansible.builtin.set_fact | False |  |

#### File: tasks/sub_tasks/execution.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Execution ¦ Check saved execution state | ansible.builtin.stat | False |  |
| Execution ¦ Read saved execution state | ansible.builtin.slurp | True |  |
| Execution ¦ Load saved execution state | ansible.builtin.set_fact | False |  |
| Execution ¦ Validate saved execution state version | ansible.builtin.assert | True |  |
| Execution ¦ Validate saved execution state | ansible.builtin.assert | True |  |
| Execution ¦ Check for legacy rootful Quadlet | ansible.builtin.stat | True |  |
| Execution ¦ Determine current execution settings | ansible.builtin.set_fact | False |  |
| Execution ¦ Store current execution settings | ansible.builtin.set_fact | False |  |
| Execution ¦ Select execution settings for this action | ansible.builtin.set_fact | False |  |
| Execution ¦ Apply selected execution settings | ansible.builtin.set_fact | False |  |
| Execution ¦ Validate managed rootless pasta configuration | ansible.builtin.set_fact | True |  |
| Execution ¦ Report planned rootless pasta configuration | ansible.builtin.debug | True |  |
| Execution ¦ Read host IPv4 routes for pasta conflict detection | ansible.builtin.command | True |  |
| Execution ¦ Detect conflicting host IPv4 routes | ansible.builtin.set_fact | True |  |
| Execution ¦ Reject conflicting host IPv4 routes | ansible.builtin.assert | True |  |
| Execution ¦ Check selected rootless account | ansible.builtin.getent | True |  |
| Execution ¦ Check selected rootless primary group | ansible.builtin.getent | True |  |
| Execution ¦ Check selected rootless home | ansible.builtin.stat | True |  |
| Execution ¦ Check selected account marker | ansible.builtin.stat | True |  |
| Execution ¦ Read selected account marker | ansible.builtin.slurp | True |  |
| Execution ¦ Load selected account marker | ansible.builtin.set_fact | True |  |
| Execution ¦ Check existing account password lock | ansible.builtin.command | True |  |
| Execution ¦ Check existing account group membership | ansible.builtin.command | True |  |
| Execution ¦ Decide how to manage rootless account | ansible.builtin.set_fact | True |  |
| Execution ¦ Ensure execution state directory exists | ansible.builtin.file | True |  |
| Execution ¦ Ensure account marker directory exists | ansible.builtin.file | True |  |
| Execution ¦ Create dedicated rootless primary group | ansible.builtin.group | True |  |
| Execution ¦ Create dedicated rootless account | ansible.builtin.user | True |  |
| Execution ¦ Read dedicated rootless account details | ansible.builtin.getent | True |  |
| Execution ¦ Read dedicated rootless primary group details | ansible.builtin.getent | True |  |
| Execution ¦ Store rootless account runtime details | ansible.builtin.set_fact | True |  |
| Execution ¦ Check dedicated account password lock | ansible.builtin.command | True |  |
| Execution ¦ Check dedicated account group membership | ansible.builtin.command | True |  |
| Execution ¦ Verify dedicated rootless account settings | ansible.builtin.assert | True |  |
| Execution ¦ Save dedicated account ownership marker | ansible.builtin.copy | True |  |
| Execution ¦ Read subordinate UID ranges | ansible.builtin.slurp | True |  |
| Execution ¦ Read subordinate GID ranges | ansible.builtin.slurp | True |  |
| Execution ¦ Validate subordinate ID ranges | ansible.builtin.set_fact | True |  |
| Execution ¦ Check rootless account linger state | ansible.builtin.stat | True |  |
| Execution ¦ Enable rootless account linger | ansible.builtin.command | True |  |
| Execution ¦ Start rootless user systemd manager | ansible.builtin.systemd_service | True |  |
| Execution ¦ Verify rootless runtime directory exists | ansible.builtin.stat | True |  |
| Execution ¦ Ensure rootless Podman directories exist | ansible.builtin.file | True |  |
| Execution ¦ Manage rootless pasta network drop-in | ansible.builtin.template | True |  |
| Execution ¦ Verify rootless user systemd manager | ansible.builtin.command | True |  |

#### File: tasks/sub_tasks/finish_remove.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Removal ¦ Apply pending systemd reloads | ansible.builtin.meta | False |  |

#### File: tasks/sub_tasks/image.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Image ¦ Pull configured container image | containers.podman.podman_image | True |  |
| Image ¦ Decide whether service restart is needed | ansible.builtin.set_fact | False |  |

#### File: tasks/sub_tasks/image_drift.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Image drift ¦ Initialize service inspection result | ansible.builtin.set_fact | True |  |
| Image drift ¦ Check running container image | ansible.builtin.command | True |  |
| Image drift ¦ Store running container image | ansible.builtin.set_fact | True |  |
| Image drift ¦ Compare desired and running images | ansible.builtin.set_fact | True |  |
| Image drift ¦ Report Podman image drift | ansible.builtin.debug | True |  |
| Image drift ¦ Report image is current | ansible.builtin.debug | True |  |

#### File: tasks/sub_tasks/init.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Init ¦ Validate selected service configuration | ansible.builtin.assert | False |  |
| Init ¦ Build Podman service settings | ansible.builtin.set_fact | False |  |
| Init ¦ Set systemd service name | ansible.builtin.set_fact | False |  |
| Init ¦ Reset temporary service state | ansible.builtin.set_fact | False |  |
| Init ¦ Validate shared service context | ansible.builtin.assert | False |  |
| Init ¦ Store shared service context | ansible.builtin.set_fact | False |  |
| Init ¦ Add environment and secret settings | ansible.builtin.set_fact | False |  |
| Init ¦ Store container host defaults | ansible.builtin.set_fact | False |  |
| Init ¦ Verify service is running on selected host | ansible.builtin.assert | False |  |
| Init ¦ Set initial execution settings | ansible.builtin.set_fact | False |  |

#### File: tasks/sub_tasks/network_changes.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Network ¦ Report managed network change that requires recreate | ansible.builtin.debug | True |  |

#### File: tasks/sub_tasks/quadlets.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Quadlets ¦ Preview rootless Quadlet changes | ansible.builtin.include_tasks | True |  |
| Quadlets ¦ Ensure Quadlet directory exists | ansible.builtin.file | True |  |
| Quadlets ¦ Write network Quadlet | ansible.builtin.template | True |  |
| Quadlets ¦ Write volume Quadlets | ansible.builtin.template | True |  |
| Quadlets ¦ Write protected environment file | ansible.builtin.template | True |  |
| Quadlets ¦ Write container Quadlet | ansible.builtin.template | True |  |

#### File: tasks/sub_tasks/remove.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Remove ¦ Load saved resources for removal | ansible.builtin.set_fact | True |  |
| Remove ¦ Report resources kept from legacy state | ansible.builtin.debug | True |  |
| Remove ¦ Validate saved resources before removal | ansible.builtin.assert | True |  |
| Remove ¦ Check system service before removal | ansible.builtin.command | True |  |
| Remove ¦ Stop system service without deleting data | ansible.builtin.systemd_service | True |  |
| Remove ¦ Check user service before removal | ansible.builtin.command | True |  |
| Remove ¦ Stop user service without deleting data | ansible.builtin.systemd_service | True |  |
| Remove ¦ Report network kept because ownership is unverified | ansible.builtin.debug | True |  |
| Remove ¦ Stop managed system network service | ansible.builtin.systemd_service | True |  |
| Remove ¦ Stop managed user network service | ansible.builtin.systemd_service | True |  |
| Remove ¦ Check managed network before removal | ansible.builtin.command | True |  |
| Remove ¦ Remove managed network if present | ansible.builtin.command | True |  |
| Remove ¦ Check saved generated files | ansible.builtin.stat | True |  |
| Remove ¦ Read existing managed generated files | ansible.builtin.slurp | True |  |
| Remove ¦ Verify files are Ansible-managed before deletion | ansible.builtin.assert | True |  |
| Remove ¦ Remove saved generated files | ansible.builtin.file | True |  |
| Remove ¦ Remove saved execution state | ansible.builtin.file | True |  |

#### File: tasks/sub_tasks/secrets/manage.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Secrets ¦ Create or update Podman secrets | containers.podman.podman_secret | False |  |

#### File: tasks/sub_tasks/service_state.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Service ¦ Apply pending Quadlet changes | ansible.builtin.meta | False |  |
| Service ¦ Validate system Quadlets with Podman generator | ansible.builtin.command | True |  |
| Service ¦ Validate generated systemd service | ansible.builtin.command | True |  |
| Service ¦ Validate user Quadlets with Podman generator | ansible.builtin.command | True |  |
| Service ¦ Validate generated user systemd service | ansible.builtin.command | True |  |
| Service ¦ Switch execution settings when needed | ansible.builtin.include_tasks | True |  |
| Service ¦ Start system service | ansible.builtin.systemd_service | True |  |
| Service ¦ Restart system service when configuration changed | ansible.builtin.systemd_service | True |  |
| Service ¦ Restart system service for recreate | ansible.builtin.systemd_service | True |  |
| Service ¦ Start user service | ansible.builtin.systemd_service | True |  |
| Service ¦ Restart user service when configuration changed | ansible.builtin.systemd_service | True |  |
| Service ¦ Restart user service for recreate | ansible.builtin.systemd_service | True |  |
| Service ¦ Verify system service is active | ansible.builtin.command | True |  |
| Service ¦ Verify user service is active | ansible.builtin.command | True |  |
| Service ¦ Ensure execution state directory exists | ansible.builtin.file | True |  |
| Service ¦ Record managed resources after successful start | ansible.builtin.set_fact | True |  |
| Service ¦ Save successful execution state | ansible.builtin.copy | True |  |

#### File: tasks/sub_tasks/switch_execution.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Execution switch ¦ Determine previous Quadlet directory | ansible.builtin.set_fact | False |  |
| Execution switch ¦ Determine resources from previous execution | ansible.builtin.set_fact | False |  |
| Execution switch ¦ Report resources kept from legacy state | ansible.builtin.debug | True |  |
| Execution switch ¦ Validate previous resource records | ansible.builtin.assert | False |  |
| Execution switch ¦ Check previous rootless account | ansible.builtin.getent | True |  |
| Execution switch ¦ Check previous rootless primary group | ansible.builtin.getent | True |  |
| Execution switch ¦ Check previous rootless home | ansible.builtin.stat | True |  |
| Execution switch ¦ Check previous rootless password lock | ansible.builtin.command | True |  |
| Execution switch ¦ Check previous rootless group membership | ansible.builtin.command | True |  |
| Execution switch ¦ Verify previous rootless account ownership | ansible.builtin.assert | True |  |
| Execution switch ¦ Check previous system service state | ansible.builtin.command | True |  |
| Execution switch ¦ Check previous user service state | ansible.builtin.command | True |  |
| Execution switch ¦ Record previous service state | ansible.builtin.set_fact | False |  |
| Execution switch ¦ Verify previous service state check succeeded | ansible.builtin.assert | False |  |
| Execution switch ¦ Stop previous system service | ansible.builtin.systemd_service | True |  |
| Execution switch ¦ Stop previous user service | ansible.builtin.systemd_service | True |  |
| Execution switch ¦ Start service with new execution settings | block | False |  |
| Execution switch ¦ Start new system service | ansible.builtin.command | True |  |
| Execution switch ¦ Start new user service | ansible.builtin.command | True |  |
| Execution switch ¦ Verify new system service | ansible.builtin.command | True |  |
| Execution switch ¦ Verify new user service | ansible.builtin.command | True |  |
| Execution switch ¦ Confirm new service started successfully | ansible.builtin.assert | False |  |
| Execution switch ¦ Check old generated files | ansible.builtin.stat | False |  |
| Execution switch ¦ Read old generated files | ansible.builtin.slurp | True |  |
| Execution switch ¦ Verify old files are Ansible-managed before deletion | ansible.builtin.assert | False |  |
| Execution switch ¦ Report previous network kept because ownership is unverified | ansible.builtin.debug | True |  |
| Execution switch ¦ Check previous system network service | ansible.builtin.command | True |  |
| Execution switch ¦ Check previous user network service | ansible.builtin.command | True |  |
| Execution switch ¦ Verify previous network service check succeeded | ansible.builtin.assert | True |  |
| Execution switch ¦ Stop previous system network service | ansible.builtin.systemd_service | True |  |
| Execution switch ¦ Stop previous user network service | ansible.builtin.systemd_service | True |  |
| Execution switch ¦ Check previous managed network | ansible.builtin.command | True |  |
| Execution switch ¦ Remove unused previous managed network | ansible.builtin.command | True |  |
| Execution switch ¦ Verify previous managed network was removed | ansible.builtin.command | True |  |
| Execution switch ¦ Confirm previous managed network is gone | ansible.builtin.assert | True |  |
| Execution switch ¦ Remove old Ansible-managed generated files | ansible.builtin.file | True |  |
| Execution switch ¦ Reload previous systemd manager | ansible.builtin.systemd_service | True |  |
| Execution switch ¦ Reload previous user systemd manager | ansible.builtin.command | True |  |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
