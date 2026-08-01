<!-- DOCSIBLE START -->

# 📃 Role overview

## podman_services





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/08/02 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [podman_services_quadlet_dir](defaults/main.yml#L3)   | str | `/etc/containers/systemd` |    
| [podman_services_action_remove](defaults/main.yml#L4)   | str | `{{ 'remove' in (ansible_run_tags ¦ default([])) }}` |    
| [podman_services_action_recreate](defaults/main.yml#L5)   | str | `{{ 'recreate' in (ansible_run_tags ¦ default([])) }}` |    
| [podman_services_action_update](defaults/main.yml#L6)   | str | `{{ 'update' in (ansible_run_tags ¦ default([])) }}` |    
| [podman_services_action_drift](defaults/main.yml#L7)   | str | `{{ 'drift' in (ansible_run_tags ¦ default([])) }}` |    
| [podman_services_action_bootstrap](defaults/main.yml#L8)   | str | `{{ 'bootstrap' in (ansible_run_tags ¦ default([])) }}` |    
| [podman_services_common_action](defaults/main.yml#L9)   | str | `<multiline value: folded_strip>` |    
| [podman_services_state](defaults/main.yml#L17)   | str | `<multiline value: folded_strip>` |    
| [podman_services_pull_images](defaults/main.yml#L26)   | bool | `True` |    
| [podman_services_traefik_delegate](defaults/main.yml#L27)   | str | `{{ podman_services_controller_host }}` |    
| [podman_services_traefik_dynamic_dir](defaults/main.yml#L28)   | str | `/opt/traefik/dynamic` |    
| [podman_services_traefik_dynamic_owner](defaults/main.yml#L29)   | str | `1000` |    
| [podman_services_traefik_dynamic_group](defaults/main.yml#L30)   | str | `1000` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Podman services ¦ Include initialization tasks | ansible.builtin.include_tasks | False |  |
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
| Drift ¦ Check current image reference | ansible.builtin.command | True |  |
| Drift ¦ Classify image reference drift | ansible.builtin.set_fact | True |  |
| Drift ¦ Report Podman image reference drift | ansible.builtin.debug | True |  |
| Drift ¦ Report no Podman image reference drift | ansible.builtin.debug | True |  |

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

#### File: tasks/sub_tasks/lifecycle.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Lifecycle ¦ Flush Quadlet daemon-reload handlers before lifecycle | ansible.builtin.meta | False |  |
| Lifecycle ¦ Validate Quadlets with Podman generator dry run | ansible.builtin.command | True |  |
| Lifecycle ¦ Verify generated systemd unit | ansible.builtin.command | True |  |
| Lifecycle ¦ Start service for deploy/bootstrap | ansible.builtin.systemd_service | True |  |
| Lifecycle ¦ Restart service when update inputs changed | ansible.builtin.systemd_service | True |  |
| Lifecycle ¦ Recreate service unconditionally | ansible.builtin.systemd_service | True |  |

#### File: tasks/sub_tasks/network.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Network ¦ Report retained managed network definition change | ansible.builtin.debug | True |  |

#### File: tasks/sub_tasks/prepare.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Prep ¦ Ensure system Quadlet directory exists | ansible.builtin.file | False |  |
| Prep ¦ Render network Quadlet | ansible.builtin.template | True |  |
| Prep ¦ Render volume Quadlets | ansible.builtin.template | True |  |
| Prep ¦ Render protected environment file | ansible.builtin.template | True |  |
| Prep ¦ Render container Quadlet | ansible.builtin.template | True |  |

#### File: tasks/sub_tasks/remove.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Remove ¦ Check container unit load state for removal | ansible.builtin.command | True |  |
| Remove ¦ Stop service for removal without deleting data | ansible.builtin.systemd_service | True |  |
| Remove ¦ Stop managed network unit for removal | ansible.builtin.systemd_service | True |  |
| Remove ¦ Check managed network still exists for removal | ansible.builtin.command | True |  |
| Remove ¦ Remove managed network if still present | ansible.builtin.command | True |  |
| Remove ¦ Remove generated Quadlet and environment files only | ansible.builtin.file | True |  |

#### File: tasks/sub_tasks/secrets/materialize.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Prep ¦ Create or update Podman-native secrets | containers.podman.podman_secret | False |  |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
