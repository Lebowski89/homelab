<!-- DOCSIBLE START -->

# 📃 Role overview

## podman_services





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/08/03 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [podman_services_system_quadlet_dir](defaults/main.yml#L3)   | str | `/etc/containers/systemd` |    
| [podman_services_quadlet_dir](defaults/main.yml#L4)   | str | `{{ podman_services_system_quadlet_dir }}` |    
| [podman_services_rootless_home_root](defaults/main.yml#L5)   | str | `/var/lib` |    
| [podman_services_execution_state_dir](defaults/main.yml#L6)   | str | `/var/lib/podman-services` |    
| [podman_services_nologin_shell](defaults/main.yml#L7)   | str | `/usr/sbin/nologin` |    
| [podman_services_action_remove](defaults/main.yml#L8)   | str | `{{ 'remove' in (ansible_run_tags ¦ default([])) }}` |    
| [podman_services_action_recreate](defaults/main.yml#L9)   | str | `{{ 'recreate' in (ansible_run_tags ¦ default([])) }}` |    
| [podman_services_action_update](defaults/main.yml#L10)   | str | `{{ 'update' in (ansible_run_tags ¦ default([])) }}` |    
| [podman_services_action_drift](defaults/main.yml#L11)   | str | `{{ 'drift' in (ansible_run_tags ¦ default([])) }}` |    
| [podman_services_action_bootstrap](defaults/main.yml#L12)   | str | `{{ 'bootstrap' in (ansible_run_tags ¦ default([])) }}` |    
| [podman_services_common_action](defaults/main.yml#L13)   | str | `<multiline value: folded_strip>` |    
| [podman_services_state](defaults/main.yml#L21)   | str | `<multiline value: folded_strip>` |    
| [podman_services_pull_images](defaults/main.yml#L30)   | bool | `True` |    
| [podman_services_traefik_delegate](defaults/main.yml#L31)   | str | `{{ podman_services_controller_host }}` |    
| [podman_services_traefik_dynamic_dir](defaults/main.yml#L32)   | str | `/opt/traefik/dynamic` |    
| [podman_services_traefik_dynamic_owner](defaults/main.yml#L33)   | str | `1000` |    
| [podman_services_traefik_dynamic_group](defaults/main.yml#L34)   | str | `1000` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Podman services ¦ Include initialization tasks | ansible.builtin.include_tasks | False |  |
| Podman services ¦ Include execution preparation tasks | ansible.builtin.include_tasks | False |  |
| Podman services ¦ Check external network exists | ansible.builtin.command | True |  |
| Podman services ¦ Require external network | ansible.builtin.assert | True |  |
| Podman services ¦ Build runtime-neutral application context | ansible.builtin.set_fact | False |  |
| Podman services ¦ Validate application preparation | ansible.builtin.include_role | False |  |
| Podman services ¦ Snapshot reset application outputs | ansible.builtin.set_fact | False |  |
| Podman services ¦ Check deployed service unit before recreate preparation | ansible.builtin.command | True |  |
| Podman services ¦ Stop deployed service before recreate preparation | ansible.builtin.systemd_service | True |  |
| Podman services ¦ Generate runtime-neutral application secrets | ansible.builtin.include_role | True |  |
| Podman services ¦ Build effective current-service secret inputs | ansible.builtin.set_fact | False |  |
| Podman services ¦ Validate canonical secret attachments | ansible.builtin.assert | False |  |
| Podman services ¦ Attach effective native secret declarations | ansible.builtin.set_fact | False |  |
| Podman services ¦ Materialize Podman-native secrets | ansible.builtin.include_tasks | True |  |
| Podman services ¦ Derive runtime-neutral application template values | ansible.builtin.include_role | True |  |
| Podman services ¦ Snapshot application template values | ansible.builtin.set_fact | False |  |
| Podman services ¦ Prepare runtime-neutral host state | ansible.builtin.include_role | False |  |
| Podman services ¦ Apply runtime-neutral application configuration | ansible.builtin.include_role | True |  |
| Podman services ¦ Include preparation tasks | ansible.builtin.include_tasks | False |  |
| Podman services ¦ Include image tasks | ansible.builtin.include_tasks | False |  |
| Podman services ¦ Include changed network tasks | ansible.builtin.include_tasks | False |  |
| Podman services ¦ Include service lifecycle tasks | ansible.builtin.include_tasks | False |  |
| Podman services ¦ Include Traefik tasks | ansible.builtin.include_role | True |  |
| Podman services ¦ Include removal tasks | ansible.builtin.include_tasks | True |  |
| Podman services ¦ Remove runtime-neutral integrations | ansible.builtin.include_role | True |  |
| Podman services ¦ Include drift tasks | ansible.builtin.include_tasks | False |  |
| Podman services ¦ Include removal handler flush | ansible.builtin.include_tasks | True |  |

#### File: tasks/sub_tasks/drift.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Drift ¦ Initialize missing active-service inspection | ansible.builtin.set_fact | True |  |
| Drift ¦ Check current image reference | ansible.builtin.command | True |  |
| Drift ¦ Capture active-service inspection | ansible.builtin.set_fact | True |  |
| Drift ¦ Classify image reference drift | ansible.builtin.set_fact | True |  |
| Drift ¦ Report Podman image reference drift | ansible.builtin.debug | True |  |
| Drift ¦ Report no Podman image reference drift | ansible.builtin.debug | True |  |

#### File: tasks/sub_tasks/execution_prepare.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Execution ¦ Check persisted execution state | ansible.builtin.stat | False |  |
| Execution ¦ Read persisted execution state | ansible.builtin.slurp | True |  |
| Execution ¦ Parse persisted execution state | ansible.builtin.set_fact | False |  |
| Execution ¦ Validate persisted execution state | ansible.builtin.assert | True |  |
| Execution ¦ Check legacy rootful Quadlet | ansible.builtin.stat | True |  |
| Execution ¦ Derive active and previous execution owners | ansible.builtin.set_fact | False |  |
| Execution ¦ Derive selected execution owner | ansible.builtin.set_fact | False |  |
| Execution ¦ Materialize selected execution context | ansible.builtin.set_fact | False |  |
| Execution ¦ Inspect selected rootless account | ansible.builtin.getent | True |  |
| Execution ¦ Inspect selected rootless primary group | ansible.builtin.getent | True |  |
| Execution ¦ Inspect selected rootless home | ansible.builtin.stat | True |  |
| Execution ¦ Inspect selected account marker | ansible.builtin.stat | True |  |
| Execution ¦ Read selected account marker | ansible.builtin.slurp | True |  |
| Execution ¦ Parse selected account marker | ansible.builtin.set_fact | True |  |
| Execution ¦ Inspect existing account password lock | ansible.builtin.command | True |  |
| Execution ¦ Inspect existing account group membership | ansible.builtin.command | True |  |
| Execution ¦ Decide safe rootless account handling | ansible.builtin.set_fact | True |  |
| Execution ¦ Ensure execution state directory for account ownership | ansible.builtin.file | True |  |
| Execution ¦ Ensure account marker directory | ansible.builtin.file | True |  |
| Execution ¦ Provision dedicated rootless primary group | ansible.builtin.group | True |  |
| Execution ¦ Provision dedicated rootless account | ansible.builtin.user | True |  |
| Execution ¦ Read dedicated rootless account | ansible.builtin.getent | True |  |
| Execution ¦ Read dedicated rootless primary group | ansible.builtin.getent | True |  |
| Execution ¦ Snapshot rootless account runtime context | ansible.builtin.set_fact | True |  |
| Execution ¦ Check dedicated account password lock | ansible.builtin.command | True |  |
| Execution ¦ Check dedicated account group membership | ansible.builtin.command | True |  |
| Execution ¦ Require dedicated rootless account contract | ansible.builtin.assert | True |  |
| Execution ¦ Persist dedicated account ownership marker | ansible.builtin.copy | True |  |
| Execution ¦ Read subordinate UID declarations | ansible.builtin.slurp | True |  |
| Execution ¦ Read subordinate GID declarations | ansible.builtin.slurp | True |  |
| Execution ¦ Validate exact subordinate ID ranges | ansible.builtin.set_fact | True |  |
| Execution ¦ Check rootless account linger state | ansible.builtin.stat | True |  |
| Execution ¦ Enable rootless account linger | ansible.builtin.command | True |  |
| Execution ¦ Start rootless user manager | ansible.builtin.systemd_service | True |  |
| Execution ¦ Require rootless runtime directory | ansible.builtin.stat | True |  |
| Execution ¦ Ensure rootless Podman directories | ansible.builtin.file | True |  |
| Execution ¦ Verify rootless user manager | ansible.builtin.command | True |  |

#### File: tasks/sub_tasks/execution_transition.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Transition ¦ Derive previous execution resources | ansible.builtin.set_fact | False |  |
| Transition ¦ Validate previous resource metadata | ansible.builtin.assert | False |  |
| Transition ¦ Inspect previous rootless account | ansible.builtin.getent | True |  |
| Transition ¦ Inspect previous rootless primary group | ansible.builtin.getent | True |  |
| Transition ¦ Inspect previous rootless home | ansible.builtin.stat | True |  |
| Transition ¦ Inspect previous rootless password lock | ansible.builtin.command | True |  |
| Transition ¦ Inspect previous rootless group membership | ansible.builtin.command | True |  |
| Transition ¦ Require exact previous rootless account owner | ansible.builtin.assert | True |  |
| Transition ¦ Check previous system service state | ansible.builtin.command | True |  |
| Transition ¦ Check previous user service state | ansible.builtin.command | True |  |
| Transition ¦ Record whether previous service was active | ansible.builtin.set_fact | False |  |
| Transition ¦ Require previous manager query | ansible.builtin.assert | False |  |
| Transition ¦ Stop previous system service | ansible.builtin.systemd_service | True |  |
| Transition ¦ Stop previous user service | ansible.builtin.systemd_service | True |  |
| Transition ¦ Start and verify desired execution owner | block | False |  |
| Transition ¦ Start desired system service | ansible.builtin.command | True |  |
| Transition ¦ Start desired user service | ansible.builtin.command | True |  |
| Transition ¦ Verify desired system service | ansible.builtin.command | True |  |
| Transition ¦ Verify desired user service | ansible.builtin.command | True |  |
| Transition ¦ Require desired start and verification success | ansible.builtin.assert | False |  |
| Transition ¦ Inspect exact stale generated paths | ansible.builtin.stat | False |  |
| Transition ¦ Read exact stale generated files | ansible.builtin.slurp | True |  |
| Transition ¦ Require managed marker before stale deletion | ansible.builtin.assert | False |  |
| Transition ¦ Report unproven previous network retention | ansible.builtin.debug | True |  |
| Transition ¦ Query previous system managed network unit | ansible.builtin.command | True |  |
| Transition ¦ Query previous user managed network unit | ansible.builtin.command | True |  |
| Transition ¦ Require previous managed network unit query | ansible.builtin.assert | True |  |
| Transition ¦ Stop previous system managed network unit | ansible.builtin.systemd_service | True |  |
| Transition ¦ Stop previous user managed network unit | ansible.builtin.systemd_service | True |  |
| Transition ¦ Query previous managed network existence | ansible.builtin.command | True |  |
| Transition ¦ Remove proven unused previous managed network | ansible.builtin.command | True |  |
| Transition ¦ Verify previous managed network absence | ansible.builtin.command | True |  |
| Transition ¦ Require previous managed network absence | ansible.builtin.assert | True |  |
| Transition ¦ Remove exact marked stale generated files | ansible.builtin.file | True |  |
| Transition ¦ Reload previous system manager | ansible.builtin.systemd_service | True |  |
| Transition ¦ Reload previous user manager | ansible.builtin.command | True |  |

#### File: tasks/sub_tasks/flush_remove_handlers.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Podman services ¦ Flush removal daemon-reload handlers | ansible.builtin.meta | False |  |

#### File: tasks/sub_tasks/image.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Image ¦ Pull exact image when allowed | containers.podman.podman_image | True |  |
| Image ¦ Compute restart requirement | ansible.builtin.set_fact | False |  |

#### File: tasks/sub_tasks/init.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Init ¦ Assert catalog-resolved service config | ansible.builtin.assert | False |  |
| Init ¦ Normalize service | ansible.builtin.set_fact | False |  |
| Init ¦ Derive normalized systemd unit name | ansible.builtin.set_fact | False |  |
| Init ¦ Reset per-service transient facts | ansible.builtin.set_fact | False |  |
| Init ¦ Validate dispatch-owned common context | ansible.builtin.assert | False |  |
| Init ¦ Snapshot dispatch-owned common context | ansible.builtin.set_fact | False |  |
| Init ¦ Attach common environment and native secret declarations | ansible.builtin.set_fact | False |  |
| Init ¦ Snapshot runtime-neutral container host defaults | ansible.builtin.set_fact | False |  |
| Init ¦ Assert inventory target matches selected host | ansible.builtin.assert | False |  |
| Init ¦ Derive check-safe execution context | ansible.builtin.set_fact | False |  |

#### File: tasks/sub_tasks/lifecycle.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Lifecycle ¦ Flush Quadlet daemon-reload handlers before lifecycle | ansible.builtin.meta | False |  |
| Lifecycle ¦ Validate Quadlets with Podman generator dry run | ansible.builtin.command | True |  |
| Lifecycle ¦ Verify generated systemd unit | ansible.builtin.command | True |  |
| Lifecycle ¦ Validate user Quadlets with Podman generator dry run | ansible.builtin.command | True |  |
| Lifecycle ¦ Verify generated user systemd unit | ansible.builtin.command | True |  |
| Lifecycle ¦ Include safe execution transition | ansible.builtin.include_tasks | True |  |
| Lifecycle ¦ Start service for deploy/bootstrap | ansible.builtin.systemd_service | True |  |
| Lifecycle ¦ Restart service when update inputs changed | ansible.builtin.systemd_service | True |  |
| Lifecycle ¦ Recreate service unconditionally | ansible.builtin.systemd_service | True |  |
| Lifecycle ¦ Start user service for deploy/bootstrap | ansible.builtin.systemd_service | True |  |
| Lifecycle ¦ Restart user service when update inputs changed | ansible.builtin.systemd_service | True |  |
| Lifecycle ¦ Recreate user service unconditionally | ansible.builtin.systemd_service | True |  |
| Lifecycle ¦ Verify desired system service is active | ansible.builtin.command | True |  |
| Lifecycle ¦ Verify desired user service is active | ansible.builtin.command | True |  |
| Lifecycle ¦ Ensure execution state directory | ansible.builtin.file | True |  |
| Lifecycle ¦ Build successful execution resource metadata | ansible.builtin.set_fact | True |  |
| Lifecycle ¦ Persist successful execution owner | ansible.builtin.copy | True |  |

#### File: tasks/sub_tasks/network.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Network ¦ Report retained managed network definition change | ansible.builtin.debug | True |  |

#### File: tasks/sub_tasks/prepare.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Prep ¦ Ensure selected Quadlet directory exists | ansible.builtin.file | True |  |
| Prep ¦ Render network Quadlet | ansible.builtin.template | True |  |
| Prep ¦ Render volume Quadlets | ansible.builtin.template | True |  |
| Prep ¦ Render protected environment file | ansible.builtin.template | True |  |
| Prep ¦ Render container Quadlet | ansible.builtin.template | True |  |

#### File: tasks/sub_tasks/remove.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Remove ¦ Derive persisted active resources | ansible.builtin.set_fact | True |  |
| Remove ¦ Validate persisted active resources | ansible.builtin.assert | True |  |
| Remove ¦ Check container unit load state for removal | ansible.builtin.command | True |  |
| Remove ¦ Stop service for removal without deleting data | ansible.builtin.systemd_service | True |  |
| Remove ¦ Check user container unit load state for removal | ansible.builtin.command | True |  |
| Remove ¦ Stop user service for removal without deleting data | ansible.builtin.systemd_service | True |  |
| Remove ¦ Report unproven managed network retention | ansible.builtin.debug | True |  |
| Remove ¦ Stop system managed network unit for removal | ansible.builtin.systemd_service | True |  |
| Remove ¦ Stop user managed network unit for removal | ansible.builtin.systemd_service | True |  |
| Remove ¦ Check proven managed network still exists | ansible.builtin.command | True |  |
| Remove ¦ Remove proven managed network if present | ansible.builtin.command | True |  |
| Remove ¦ Inspect persisted generated paths | ansible.builtin.stat | True |  |
| Remove ¦ Read rootless generated files | ansible.builtin.slurp | True |  |
| Remove ¦ Require managed marker for rootless deletion | ansible.builtin.assert | True |  |
| Remove ¦ Remove persisted generated files only | ansible.builtin.file | True |  |
| Remove ¦ Remove persisted execution state after active cleanup | ansible.builtin.file | True |  |

#### File: tasks/sub_tasks/secrets/materialize.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Prep ¦ Create or update Podman-native secrets | containers.podman.podman_secret | False |  |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
