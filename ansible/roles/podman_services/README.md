<!-- DOCSIBLE START -->

# 📃 Role overview

## podman_services





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/07/25 |








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
| [podman_services_traefik_delegate](defaults/main.yml#L27)   | str | `{{ docker_services_primary_manager ¦ default('mgt') }}` |    
| [podman_services_traefik_dynamic_dir](defaults/main.yml#L28)   | str | `/opt/traefik/dynamic` |    
| [podman_services_traefik_dynamic_owner](defaults/main.yml#L29)   | str | `1000` |    
| [podman_services_traefik_dynamic_group](defaults/main.yml#L30)   | str | `1000` |    
| [podman_services_infisical_delegate](defaults/main.yml#L31)   | str | `{{ docker_services_primary_manager ¦ default('mgt') }}` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Podman services ¦ Include initialization tasks | ansible.builtin.include_tasks | False |  |
| Podman services ¦ Resolve common Infisical values and environment | ansible.builtin.include_role | True |  |
| Podman services ¦ Attach common resolved environment | ansible.builtin.set_fact | True |  |
| Podman services ¦ Prepare runtime-neutral host state | ansible.builtin.include_role | False |  |
| Podman services ¦ Include preparation tasks | ansible.builtin.include_tasks | False |  |
| Podman services ¦ Include image tasks | ansible.builtin.include_tasks | False |  |
| Podman services ¦ Include changed network tasks | ansible.builtin.include_tasks | False |  |
| Podman services ¦ Include service lifecycle tasks | ansible.builtin.include_tasks | False |  |
| Podman services ¦ Include Traefik tasks | ansible.builtin.include_role | True |  |
| Podman services ¦ Include removal tasks | ansible.builtin.include_tasks | False |  |
| Podman services ¦ Remove runtime-neutral integrations | ansible.builtin.include_role | True |  |
| Podman services ¦ Include drift tasks | ansible.builtin.include_tasks | False |  |
| Podman services ¦ Flush removal daemon-reload handlers | ansible.builtin.meta | False |  |

#### File: tasks/sub_tasks/drift.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Drift ¦ Check current image reference | ansible.builtin.command | True |  |
| Drift ¦ Classify image reference drift | ansible.builtin.set_fact | True |  |
| Drift ¦ Report Podman image reference drift | ansible.builtin.debug | True |  |
| Drift ¦ Report no Podman image reference drift | ansible.builtin.debug | True |  |

#### File: tasks/sub_tasks/image.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Image ¦ Pull exact image when allowed | containers.podman.podman_image | True |  |
| Image ¦ Compute restart requirement | ansible.builtin.set_fact | False |  |

#### File: tasks/sub_tasks/init.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Init ¦ Normalize service | ansible.builtin.set_fact | False |  |
| Init ¦ Derive normalized systemd unit name | ansible.builtin.set_fact | False |  |
| Init ¦ Reset per-service transient facts | ansible.builtin.set_fact | False |  |
| Init ¦ Assert inventory target matches selected host | ansible.builtin.assert | False |  |
| Init ¦ Build Infisical lookup parameters for manager endpoint | ansible.builtin.set_fact | True |  |
| Init ¦ Assert Infisical lookup parameters for secrets | ansible.builtin.assert | True |  |

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
| Network ¦ Stop container before changed dedicated network lifecycle | ansible.builtin.systemd_service | True |  |
| Network ¦ Stop generated dedicated network after changed lifecycle | ansible.builtin.systemd_service | True |  |
| Network ¦ Check changed dedicated network still exists | ansible.builtin.command | True |  |
| Network ¦ Remove changed dedicated network if still present | ansible.builtin.command | True |  |

#### File: tasks/sub_tasks/prepare.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Prep ¦ Ensure system Quadlet directory exists | ansible.builtin.file | False |  |
| Prep ¦ Render network Quadlet | ansible.builtin.template | True |  |
| Prep ¦ Render volume Quadlets | ansible.builtin.template | True |  |
| Prep ¦ Render protected environment file | ansible.builtin.template | True |  |
| Prep ¦ Create/update Podman secrets | containers.podman.podman_secret | True |  |
| Prep ¦ Report check-mode PostgreSQL database plan | ansible.builtin.debug | True |  |
| Prep ¦ Render container Quadlet | ansible.builtin.template | True |  |

#### File: tasks/sub_tasks/remove.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Remove ¦ Check container unit load state for removal | ansible.builtin.command | True |  |
| Remove ¦ Stop service for removal without deleting data | ansible.builtin.systemd_service | True |  |
| Remove ¦ Stop generated network unit for removal | ansible.builtin.systemd_service | True |  |
| Remove ¦ Check dedicated network still exists for removal | ansible.builtin.command | True |  |
| Remove ¦ Remove dedicated network if still present | ansible.builtin.command | True |  |
| Remove ¦ Remove generated Quadlet and environment files only | ansible.builtin.file | True |  |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
