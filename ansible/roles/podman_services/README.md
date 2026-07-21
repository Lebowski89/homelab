<!-- DOCSIBLE START -->

# 📃 Role overview

## podman_services



Description: Manage data-driven Podman Quadlet services.

| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/07/21 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [podman_services_quadlet_dir](defaults/main.yml#L2)   | str | `/etc/containers/systemd` |    
| [podman_services_action_remove](defaults/main.yml#L3)   | str | `{{ 'remove' in (ansible_run_tags ¦ default([])) }}` |    
| [podman_services_action_recreate](defaults/main.yml#L4)   | str | `{{ 'recreate' in (ansible_run_tags ¦ default([])) }}` |    
| [podman_services_action_update](defaults/main.yml#L5)   | str | `{{ 'update' in (ansible_run_tags ¦ default([])) }}` |    
| [podman_services_action_drift](defaults/main.yml#L6)   | str | `{{ 'drift' in (ansible_run_tags ¦ default([])) }}` |    
| [podman_services_action_bootstrap](defaults/main.yml#L7)   | str | `{{ 'bootstrap' in (ansible_run_tags ¦ default([])) }}` |    
| [podman_services_state](defaults/main.yml#L8)   | str | `<multiline value: folded_strip>` |    
| [podman_services_pull_images](defaults/main.yml#L17)   | bool | `True` |    
| [podman_services_traefik_delegate](defaults/main.yml#L18)   | str | `{{ docker_services_primary_manager ¦ default('mgt') }}` |    
| [podman_services_traefik_dynamic_dir](defaults/main.yml#L19)   | str | `/opt/traefik/dynamic` |    
| [podman_services_traefik_dynamic_owner](defaults/main.yml#L20)   | str | `1000` |    
| [podman_services_traefik_dynamic_group](defaults/main.yml#L21)   | str | `1000` |    
| [podman_services_infisical_delegate](defaults/main.yml#L22)   | str | `{{ docker_services_primary_manager ¦ default('mgt') }}` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Podman services ¦ Normalize service | ansible.builtin.set_fact | False |  |
| Podman services ¦ Reset per-service transient facts | ansible.builtin.set_fact | False |  |
| Podman services ¦ Assert inventory target matches selected host | ansible.builtin.assert | False |  |
| Podman services ¦ Build Infisical lookup parameters for manager endpoint | ansible.builtin.set_fact | True |  |
| Podman services ¦ Assert Infisical lookup parameters for secrets | ansible.builtin.assert | True |  |
| Podman ¦ Ensure system Quadlet directory exists | ansible.builtin.file | False |  |
| Podman services ¦ Ensure host data paths exist | ansible.builtin.file | True |  |
| Podman services ¦ Render network Quadlet | ansible.builtin.template | True |  |
| Podman services ¦ Render volume Quadlets | ansible.builtin.template | True |  |
| Podman services ¦ Render protected environment file | ansible.builtin.template | True |  |
| Podman services ¦ Resolve Infisical secret values | ansible.builtin.set_fact | True |  |
| Podman services ¦ Create/update Podman secrets | containers.podman.podman_secret | True |  |
| Podman services ¦ Report check-mode PostgreSQL database plan | ansible.builtin.debug | True |  |
| Podman services ¦ Render container Quadlet | ansible.builtin.template | True |  |
| Podman services ¦ Pull exact image when allowed | containers.podman.podman_image | True |  |
| Podman services ¦ Compute restart requirement | ansible.builtin.set_fact | False |  |
| Podman services ¦ Stop container before changed dedicated network lifecycle | ansible.builtin.systemd_service | True |  |
| Podman services ¦ Stop generated dedicated network after changed lifecycle | ansible.builtin.systemd_service | True |  |
| Podman services ¦ Check changed dedicated network still exists | ansible.builtin.command | True |  |
| Podman services ¦ Remove changed dedicated network if still present | ansible.builtin.command | True |  |
| Podman services ¦ Flush Quadlet daemon-reload handlers before lifecycle | ansible.builtin.meta | False |  |
| Podman services ¦ Validate Quadlets with Podman generator dry run | ansible.builtin.command | True |  |
| Podman services ¦ Verify generated systemd unit | ansible.builtin.command | True |  |
| Podman services ¦ Start service for deploy/bootstrap | ansible.builtin.systemd_service | True |  |
| Podman services ¦ Restart service when update inputs changed | ansible.builtin.systemd_service | True |  |
| Podman services ¦ Recreate service unconditionally | ansible.builtin.systemd_service | True |  |
| Podman services ¦ Render private Traefik host backend on manager | ansible.builtin.template | True |  |
| Podman services ¦ Check container unit load state for removal | ansible.builtin.command | True |  |
| Podman services ¦ Stop service for removal without deleting data | ansible.builtin.systemd_service | True |  |
| Podman services ¦ Stop generated network unit for removal | ansible.builtin.systemd_service | True |  |
| Podman services ¦ Check dedicated network still exists for removal | ansible.builtin.command | True |  |
| Podman services ¦ Remove dedicated network if still present | ansible.builtin.command | True |  |
| Podman services ¦ Remove generated Quadlet and environment files only | ansible.builtin.file | True |  |
| Podman services ¦ Remove private Traefik host backend | ansible.builtin.file | True |  |
| Podman services ¦ Drift check current image reference | ansible.builtin.command | True |  |
| Podman services ¦ Classify image reference drift | ansible.builtin.set_fact | True |  |
| Podman services ¦ Report Podman image reference drift | ansible.builtin.debug | True |  |
| Podman services ¦ Report no Podman image reference drift | ansible.builtin.debug | True |  |
| Podman services ¦ Flush removal daemon-reload handlers | ansible.builtin.meta | False |  |







## Author Information
homelab

#### License

MIT

#### Minimum Ansible Version

2.16

#### Platforms

No platforms specified.

#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
