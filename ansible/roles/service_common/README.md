<!-- DOCSIBLE START -->

# 📃 Role overview

## service_common





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/07/29 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [service_common_name](defaults/main.yml#L3)   | str |  |    
| [service_common_runtime](defaults/main.yml#L4)   | str |  |    
| [service_common_action](defaults/main.yml#L5)   | str |  |    
| [service_common_service](defaults/main.yml#L6)   | dict | `{}` |    
| [service_common_target_hosts](defaults/main.yml#L7)   | list | `[]` |    
| [service_common_controller_host](defaults/main.yml#L8)   | str |  |    
| [service_common_default_owner](defaults/main.yml#L9)   | str | `1000` |    
| [service_common_default_group](defaults/main.yml#L10)   | str | `1000` |    
| [service_common_default_mode](defaults/main.yml#L11)   | str | `0755` |    
| [service_common_host_defaults](defaults/main.yml#L12)   | dict | `{}` |    
| [service_common_template_vars](defaults/main.yml#L13)   | dict | `{}` |    
| [service_common_infisical_secrets_map](defaults/main.yml#L14)   | list | `[]` |    
| [service_common_infisical_lookup_params](defaults/main.yml#L15)   | dict | `{}` |    
| [service_common_infisical_fail_on_empty](defaults/main.yml#L16)   | bool | `True` |    
| [service_common_environment](defaults/main.yml#L17)   | dict | `{}` |    
| [service_common_infisical_config](defaults/main.yml#L18)   | dict | `{}` |    
| [service_common_infisical_values](defaults/main.yml#L19)   | dict | `{}` |    
| [service_common_secret_declarations](defaults/main.yml#L20)   | list | `[]` |    
| [service_common_resolved_environment](defaults/main.yml#L21)   | dict | `{}` |    
| [service_common_traefik_base_zone](defaults/main.yml#L22)   | str |  |    
| [service_common_traefik_dynamic_dir](defaults/main.yml#L23)   | str | `/opt/traefik/dynamic` |    
| [service_common_traefik_owner](defaults/main.yml#L24)   | str | `1000` |    
| [service_common_traefik_group](defaults/main.yml#L25)   | str | `1000` |    
| [service_common_prepare_actions](defaults/main.yml#L26)   | list | `[]` |    
| [service_common_prepare_actions.**0**](defaults/main.yml#L26)   | str | `deploy` |    
| [service_common_prepare_actions.**1**](defaults/main.yml#L26)   | str | `update` |    
| [service_common_prepare_actions.**2**](defaults/main.yml#L26)   | str | `recreate` |    
| [service_common_prepare_actions.**3**](defaults/main.yml#L26)   | str | `bootstrap` |    
| [service_common_remove_actions](defaults/main.yml#L27)   | list | `[]` |    
| [service_common_remove_actions.**0**](defaults/main.yml#L27)   | str | `remove` |    





### Tasks


#### File: tasks/copies.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Service common copies ¦ Copy static files | ansible.builtin.copy | False |
| Service common copies ¦ Wait for copied files | ansible.builtin.wait_for | True |

#### File: tasks/infisical.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Service common Infisical ¦ Reset all per-service outputs | ansible.builtin.set_fact | False |  |
| Service common Infisical ¦ Validate and normalize declarations | ansible.builtin.set_fact | False |  |
| Service common Infisical ¦ Publish lookup config and value-free secret declarations | ansible.builtin.set_fact | False |  |
| Service common environment ¦ Validate and normalize canonical environment | ansible.builtin.set_fact | False |  |
| Service common Infisical ¦ Validate lookup parameters | ansible.builtin.assert | True |  |
| Service common Infisical ¦ Publish current-service lookup request | ansible.builtin.set_fact | True |  |
| Service common Infisical ¦ Fetch requested values | ansible.builtin.set_fact | True |  |
| Service common Infisical ¦ Enforce empty-value policy | ansible.builtin.set_fact | True |  |
| Service common Infisical ¦ Build deterministic check-mode values | ansible.builtin.set_fact | True |  |
| Service common environment ¦ Resolve canonical environment | ansible.builtin.set_fact | False |  |

#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Service common ¦ Include interface validation | ansible.builtin.include_tasks | False |  |
| Service common ¦ Include shared preparation | ansible.builtin.include_tasks | True |  |
| Service common ¦ Include shared Traefik integration | ansible.builtin.include_tasks | True |  |
| Service common ¦ Include shared integration removal | ansible.builtin.include_tasks | True |  |

#### File: tasks/paths.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Service common paths ¦ Validate each path specification | ansible.builtin.assert | False |
| Service common paths ¦ Apply filesystem state on target host | ansible.builtin.file | False |

#### File: tasks/postgres.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Service common PostgreSQL ¦ Validate and normalize declaration | ansible.builtin.set_fact | False |  |
| Service common PostgreSQL ¦ Report check-mode database plan | ansible.builtin.debug | True |  |
| Service common PostgreSQL ¦ Ensure declared databases exist | community.postgresql.postgresql_db | True |  |

#### File: tasks/prepare.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Service common prepare ¦ Include interface validation | ansible.builtin.include_tasks | False |  |
| Service common prepare ¦ Include PostgreSQL database preparation | ansible.builtin.include_tasks | True |  |
| Service common prepare ¦ Require target hosts for filesystem preparation | ansible.builtin.assert | True |  |
| Service common prepare ¦ Include path preparation per target | ansible.builtin.include_tasks | True |  |
| Service common prepare ¦ Include static copies per target | ansible.builtin.include_tasks | True |  |
| Service common prepare ¦ Include application templates per target | ansible.builtin.include_tasks | True |  |

#### File: tasks/remove_integrations.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Service common remove integrations ¦ Include interface validation | ansible.builtin.include_tasks | False |  |
| Service common remove integrations ¦ Resolve canonical and legacy Traefik paths | ansible.builtin.set_fact | False |  |
| Service common remove integrations ¦ Remove canonical and legacy Traefik configurations | ansible.builtin.file | False |  |

#### File: tasks/templates.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Service common templates ¦ Render application templates on target host | ansible.builtin.template | True |

#### File: tasks/traefik.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Service common Traefik ¦ Include interface validation | ansible.builtin.include_tasks | False |  |
| Service common Traefik ¦ Resolve runtime-neutral render context | ansible.builtin.set_fact | False |  |
| Service common Traefik ¦ Resolve canonical and legacy paths | ansible.builtin.set_fact | False |  |
| Service common Traefik ¦ Render canonical dynamic configuration | ansible.builtin.template | False |  |
| Service common Traefik ¦ Remove distinct legacy Podman configuration after render | ansible.builtin.file | True |  |

#### File: tasks/validate.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Service common ¦ Validate role interface | ansible.builtin.assert | False |
| Service common ¦ Validate target hosts | ansible.builtin.assert | True |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
