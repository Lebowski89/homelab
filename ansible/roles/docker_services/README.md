<!-- DOCSIBLE START -->

# 📃 Role overview

## docker_services





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/07/09 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [docker_services_default_deploy_profile](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L3)   | str | `none` |    
| [docker_services_deploy_profiles](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L5)   | dict | `{}` |    
| [docker_services_deploy_profiles.**none**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L6)   | dict | `{}` |    
| [docker_services_deploy_profiles.**standard**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L8)   | dict | `{}` |    
| [docker_services_deploy_profiles.standard.**restart_policy**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L9)   | dict | `{}` |    
| [docker_services_deploy_profiles.standard.restart_policy.**condition**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L10)   | str | `on-failure` |    
| [docker_services_deploy_profiles.standard.restart_policy.**delay**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L11)   | str | `10s` |    
| [docker_services_deploy_profiles.standard.restart_policy.**max_attempts**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L12)   | int | `5` |    
| [docker_services_deploy_profiles.standard.restart_policy.**window**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L13)   | str | `2m` |    
| [docker_services_deploy_profiles.standard.**update_config**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L14)   | dict | `{}` |    
| [docker_services_deploy_profiles.standard.update_config.**parallelism**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L15)   | int | `1` |    
| [docker_services_deploy_profiles.standard.update_config.**delay**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L16)   | str | `10s` |    
| [docker_services_deploy_profiles.standard.update_config.**failure_action**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L17)   | str | `rollback` |    
| [docker_services_deploy_profiles.standard.update_config.**order**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L18)   | str | `stop-first` |    
| [docker_services_deploy_profiles.standard.**rollback_config**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L19)   | dict | `{}` |    
| [docker_services_deploy_profiles.standard.rollback_config.**parallelism**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L20)   | int | `1` |    
| [docker_services_deploy_profiles.standard.rollback_config.**delay**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L21)   | str | `10s` |    
| [docker_services_deploy_profiles.standard.rollback_config.**order**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L22)   | str | `stop-first` |    
| [docker_services_deploy_profiles.**careful**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L24)   | dict | `{}` |    
| [docker_services_deploy_profiles.careful.**restart_policy**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L25)   | dict | `{}` |    
| [docker_services_deploy_profiles.careful.restart_policy.**condition**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L26)   | str | `on-failure` |    
| [docker_services_deploy_profiles.careful.restart_policy.**delay**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L27)   | str | `10s` |    
| [docker_services_deploy_profiles.careful.restart_policy.**max_attempts**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L28)   | int | `5` |    
| [docker_services_deploy_profiles.careful.restart_policy.**window**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L29)   | str | `2m` |    
| [docker_services_deploy_profiles.careful.**update_config**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L30)   | dict | `{}` |    
| [docker_services_deploy_profiles.careful.update_config.**parallelism**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L31)   | int | `1` |    
| [docker_services_deploy_profiles.careful.update_config.**delay**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L32)   | str | `30s` |    
| [docker_services_deploy_profiles.careful.update_config.**failure_action**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L33)   | str | `rollback` |    
| [docker_services_deploy_profiles.careful.update_config.**order**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L34)   | str | `stop-first` |    
| [docker_services_deploy_profiles.careful.**rollback_config**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L35)   | dict | `{}` |    
| [docker_services_deploy_profiles.careful.rollback_config.**parallelism**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L36)   | int | `1` |    
| [docker_services_deploy_profiles.careful.rollback_config.**delay**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L37)   | str | `30s` |    
| [docker_services_deploy_profiles.careful.rollback_config.**order**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L38)   | str | `stop-first` |    
| [docker_services_deploy_profiles.**stateless_ha**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L40)   | dict | `{}` |    
| [docker_services_deploy_profiles.stateless_ha.**restart_policy**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L41)   | dict | `{}` |    
| [docker_services_deploy_profiles.stateless_ha.restart_policy.**condition**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L42)   | str | `on-failure` |    
| [docker_services_deploy_profiles.stateless_ha.restart_policy.**delay**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L43)   | str | `5s` |    
| [docker_services_deploy_profiles.stateless_ha.restart_policy.**max_attempts**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L44)   | int | `5` |    
| [docker_services_deploy_profiles.stateless_ha.restart_policy.**window**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L45)   | str | `2m` |    
| [docker_services_deploy_profiles.stateless_ha.**update_config**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L46)   | dict | `{}` |    
| [docker_services_deploy_profiles.stateless_ha.update_config.**parallelism**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L47)   | int | `1` |    
| [docker_services_deploy_profiles.stateless_ha.update_config.**delay**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L48)   | str | `5s` |    
| [docker_services_deploy_profiles.stateless_ha.update_config.**failure_action**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L49)   | str | `rollback` |    
| [docker_services_deploy_profiles.stateless_ha.update_config.**order**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L50)   | str | `start-first` |    
| [docker_services_deploy_profiles.stateless_ha.**rollback_config**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L51)   | dict | `{}` |    
| [docker_services_deploy_profiles.stateless_ha.rollback_config.**parallelism**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L52)   | int | `1` |    
| [docker_services_deploy_profiles.stateless_ha.rollback_config.**delay**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L53)   | str | `5s` |    
| [docker_services_deploy_profiles.stateless_ha.rollback_config.**order**](https://github.com/Lebowski89/homelab/blob/renovate/docker.io-infisical-infisical-0.160.x/defaults/main.yml#L54)   | str | `start-first` |    





### Tasks


#### File: tasks/_compose.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose - Init ¦ Ensure docker_services_compose_stacks exists | ansible.builtin.set_fact | False |
| Compose - Init ¦ Load this stack's current docker_services_compose_services | ansible.builtin.set_fact | True |
| Compose - Base ¦ Register networks needed by this stack | ansible.builtin.include_tasks | True |
| Compose - Base ¦ Normalize network_mode for container deploys | ansible.builtin.set_fact | True |
| Compose - Base ¦ Normalize network_mode for container deploys | ansible.builtin.set_fact | True |
| Compose - Base ¦ Build service networks list | ansible.builtin.set_fact | True |
| Compose - Base ¦ Register external volumes needed by this stack | ansible.builtin.include_tasks | True |
| Compose - Base ¦ Set base service variables | ansible.builtin.include_tasks | True |
| Compose - Runtime ¦ Set security_opt | ansible.builtin.include_tasks | True |
| Compose - Runtime ¦ Set sysctls | ansible.builtin.include_tasks | True |
| Compose - Runtime ¦ Set depends_on | ansible.builtin.include_tasks | True |
| Compose - Runtime ¦ Add Linux capabilities (cap_add) | ansible.builtin.include_tasks | True |
| Compose - Runtime ¦ Drop Linux capabilities (cap_drop) | ansible.builtin.include_tasks | True |
| Compose - Runtime ¦ Add devices | ansible.builtin.include_tasks | True |
| Compose - Runtime ¦ Set command variable | ansible.builtin.include_tasks | True |
| Compose - Runtime ¦ Set healthcheck variable | ansible.builtin.include_tasks | True |
| Compose - Runtime ¦ Set user variable | ansible.builtin.include_tasks | True |
| Compose - IO ¦ Set environment variables | ansible.builtin.include_tasks | True |
| Compose - IO ¦ Attach env_file to service | ansible.builtin.include_tasks | True |
| Compose - IO ¦ Set secrets variable | ansible.builtin.include_tasks | True |
| Compose - IO ¦ Set Swarm configs variable | ansible.builtin.include_tasks | True |
| Compose - IO ¦ Set ports variable | ansible.builtin.include_tasks | True |
| Compose - IO ¦ Set tmpfs variable | ansible.builtin.include_tasks | True |
| Compose - IO ¦ Set volumes variable | ansible.builtin.include_tasks | True |
| Compose - IO ¦ Add /dev/shm tmpfs | ansible.builtin.include_tasks | True |
| Compose - IO ¦ Set SHM size | ansible.builtin.include_tasks | True |
| Compose - Metadata ¦ Attach service labels | ansible.builtin.include_tasks | True |

#### File: tasks/_deploy.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Deploy ¦ Set deploy config (swarm only, compose structure) | ansible.builtin.include_tasks | True |
| Deploy ¦ Persist compose into docker_services_compose_stacks[docker_services_stack_name_effective] | ansible.builtin.set_fact | True |

#### File: tasks/_init.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Init ¦ Normalize role interface vars (compat with old names) | ansible.builtin.set_fact | False |  |
| Init ¦ Ensure docker_services_service_cfg is provided | ansible.builtin.assert | False |  |
| Init ¦ Derive effective target name | ansible.builtin.set_fact | False |  |
| Init ¦ Normalize service config | ansible.builtin.set_fact | False |  |
| Init ¦ Determine whether schema validation should run | ansible.builtin.set_fact | False |  |
| Init ¦ Validate normalized service config | ansible.builtin.include_tasks | True |  |
| Init ¦ Derive common service context | ansible.builtin.set_fact | False |  |
| Init ¦ Derive stack name | ansible.builtin.set_fact | False |  |
| Init ¦ Derive effective deploy host | ansible.builtin.set_fact | False |  |
| Init ¦ Derive effective stack key | ansible.builtin.set_fact | False |  |
| Init ¦ Derive effective filesystem hosts | ansible.builtin.set_fact | False |  |
| Init ¦ Expand filesystem hosts if a group name was provided | ansible.builtin.set_fact | True |  |
| Init ¦ De-dupe filesystem hosts | ansible.builtin.set_fact | False |  |
| Init ¦ Assert container deploy has a single deploy.host | ansible.builtin.assert | True |  |
| Init ¦ Determine if this host should build/deploy compose artifacts | ansible.builtin.set_fact | False |  |

#### File: tasks/_prep.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Prep - Cleanup ¦ Derive cleanup flags | ansible.builtin.set_fact | False |  |
| Prep - Cleanup ¦ Init cleaned-stacks tracker | ansible.builtin.set_fact | True |  |
| Prep - Cleanup ¦ Determine if stack cleanup should run | ansible.builtin.set_fact | True |  |
| Prep - Cleanup ¦ Remove existing stack | ansible.builtin.include_tasks | True |  |
| Prep - Cleanup ¦ Mark stack as cleaned | ansible.builtin.set_fact | True |  |
| Prep - Infisical ¦ Include tasker | ansible.builtin.include_tasks | False |  |
| Prep - Swarm configs ¦ Include tasker | ansible.builtin.include_tasks | True |  |
| Prep - Authelia ¦ Include bootstrap tasks | ansible.builtin.include_tasks | True |  |
| Prep - Postgres ¦ Create Postgres database | ansible.builtin.include_tasks | True |  |
| Prep - qBittorrent ¦ Include bootstrap tasks | ansible.builtin.include_tasks | True |  |
| Prep - Paths ¦ Create filesystem paths | ansible.builtin.include_tasks | True |  |
| Prep - Copies ¦ Copy files | ansible.builtin.include_tasks | True |  |
| Prep - Templates ¦ Render templates | ansible.builtin.include_tasks | True |  |
| Prep - Swarm Env Templates ¦ Render templates | ansible.builtin.include_tasks | True |  |
| Prep - Traefik ¦ Render dynamic files | ansible.builtin.include_tasks | True |  |
| Prep - Plex ¦ Include bootstrap tasks | ansible.builtin.include_tasks | True |  |
| Prep - Bazarr ¦ Include bootstrap tasks | ansible.builtin.include_tasks | True |  |
| Prep - NZBHydra2 ¦ Include bootstrap tasks | ansible.builtin.include_tasks | True |  |
| Prep - Vaultwarden ¦ Include bootstrap tasks | ansible.builtin.include_tasks | True |  |

#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Init ¦ Include tasks | ansible.builtin.include_tasks | False |  |
| Drift ¦ Include image drift check | ansible.builtin.include_tasks | True |  |
| Prep ¦ Include tasks | ansible.builtin.include_tasks | False |  |
| Compose ¦ Include tasks | ansible.builtin.include_tasks | False |  |
| Deploy ¦ Include tasks | ansible.builtin.include_tasks | False |  |

#### File: tasks/sub_tasks/compose/command.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose - Command ¦ Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Compose - Command ¦ Ensure command_action is valid | ansible.builtin.assert | False |
| Compose - Command ¦ Select command input | ansible.builtin.set_fact | False |
| Compose - Command ¦ Fail if no command provided | ansible.builtin.fail | True |
| Compose - Command ¦ Normalize command list input | ansible.builtin.set_fact | True |
| Compose - Command ¦ Normalize command | ansible.builtin.set_fact | False |
| Compose - Command ¦ Read existing command | ansible.builtin.set_fact | False |
| Compose - Command ¦ Normalize existing/new command values for merge actions | ansible.builtin.set_fact | False |
| Compose - Command ¦ Compute final command | ansible.builtin.set_fact | False |
| Compose - Command ¦ Set command for service | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/env.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose - Env ¦ Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Compose - Env ¦ Ensure environment_action is valid | ansible.builtin.assert | False |
| Compose - Env ¦ Normalize environment inputs | ansible.builtin.set_fact | False |
| Compose - Env ¦ Build final environment dict | ansible.builtin.set_fact | False |
| Compose - Env ¦ Attach environment to service | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/env_file.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose - Env File ¦ Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Compose - Env File ¦ Normalize env_file to list | ansible.builtin.set_fact | False |
| Compose - Env File ¦ Attach env_file to service | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/healthcheck.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose - Healthcheck ¦ Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Compose - Healthcheck ¦ Ensure health_test is provided | ansible.builtin.assert | False |
| Compose - Healthcheck ¦ Normalize healthcheck test into list form | ansible.builtin.set_fact | False |
| Compose - Healthcheck ¦ Attach healthcheck to service | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/labels.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose - Labels ¦ Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Compose - Labels ¦ Capture existing labels | ansible.builtin.set_fact | False |
| Compose - Labels ¦ Build final labels dict | ansible.builtin.set_fact | False |
| Compose - Labels ¦ Attach labels to service | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/list_field.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose - List Field ¦ Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Compose - List Field ¦ Validate field and action | ansible.builtin.assert | False |
| Compose - List Field ¦ Capture existing field list | ansible.builtin.set_fact | False |
| Compose - List Field ¦ Merge field list | ansible.builtin.set_fact | False |
| Compose - List Field ¦ Attach field to service | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/ports.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose - Ports ¦ Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Compose - Ports ¦ Capture existing ports list | ansible.builtin.set_fact | False |
| Compose - Ports ¦ Compute merged ports list | ansible.builtin.set_fact | False |
| Compose - Ports ¦ Attach ports to service | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/secrets.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose - Secrets ¦ Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Compose - Secrets ¦ Ensure secrets is a list | ansible.builtin.set_fact | False |
| Compose - Secrets ¦ Attach secrets list to service | ansible.builtin.set_fact | True |
| Compose - Secrets ¦ Convert secrets to bind-mount volumes | ansible.builtin.set_fact | True |
| Compose - Secrets ¦ Attach secret mounts to service volumes | ansible.builtin.set_fact | True |

#### File: tasks/sub_tasks/compose/service_base.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose - Base ¦ Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Compose - Base ¦ Normalize effective stack deploy type | ansible.builtin.set_fact | False |
| Compose - Base ¦ Set base service definition | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/shm.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose - SHM ¦ Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Compose - SHM ¦ Set SHM size for service | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/stack_resources.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose - Stack Resources ¦ Ensure docker_services_stack_name is provided | ansible.builtin.assert | False |
| Compose - Stack Resources ¦ Validate resource type and input | ansible.builtin.assert | False |
| Compose - Stack Resources ¦ Merge resources into stack | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/swarm_configs.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose - Swarm Configs ¦ Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Compose - Swarm Configs ¦ Ensure configs_list is a list | ansible.builtin.assert | False |
| Compose - Swarm Configs ¦ Resolve effective config sources | ansible.builtin.set_fact | False |
| Compose - Swarm Configs ¦ Attach configs to service | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/sysctls.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose - Sysctls ¦ Validate input | ansible.builtin.assert | False |
| Compose - Sysctls ¦ Normalize sysctls dict | ansible.builtin.set_fact | False |
| Compose - Sysctls ¦ Attach sysctls to service | ansible.builtin.set_fact | True |

#### File: tasks/sub_tasks/compose/user.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose - User ¦ Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Compose - User ¦ Set user for service | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/volumes.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose - Volumes ¦ Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Compose - Volumes ¦ Capture existing volumes list | ansible.builtin.set_fact | False |
| Compose - Volumes ¦ Compute merged volumes list | ansible.builtin.set_fact | False |
| Compose - Volumes ¦ Attach volumes to service | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/deploy/all.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Deploy - All ¦ Ensure docker_services_compose_stacks exists | ansible.builtin.set_fact | False |
| Deploy - All ¦ Deploy each stack | ansible.builtin.include_tasks | True |

#### File: tasks/sub_tasks/deploy/config.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Deploy - Config ¦ Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Deploy - Config ¦ Build deploy dict | ansible.builtin.set_fact | False |
| Deploy - Config ¦ Attach deploy config to service | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/deploy/one.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Deploy - One ¦ Validate inputs | ansible.builtin.assert | False |
| Deploy - One ¦ Derive effective deploy host | ansible.builtin.set_fact | False |
| Deploy - One ¦ Ensure /opt/stacks exists | ansible.builtin.file | False |
| Deploy - One ¦ Render compose/stack file | ansible.builtin.template | False |
| Deploy - One ¦ Swarm deploy | community.docker.docker_stack | True |
| Deploy - One ¦ Compose deploy | community.docker.docker_compose_v2 | True |

#### File: tasks/sub_tasks/drift/image.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Drift ¦ Derive clean service target label | ansible.builtin.set_fact | False |
| Drift ¦ Determine whether image drift check applies | ansible.builtin.set_fact | False |
| Drift ¦ Skip services without an image | ansible.builtin.debug | True |
| Drift ¦ Derive drift context | ansible.builtin.set_fact | True |
| Drift ¦ Inspect live Swarm service image | ansible.builtin.command | True |
| Drift ¦ Normalise live Swarm service image | ansible.builtin.set_fact | True |
| Drift ¦ Derive Compose service context | ansible.builtin.set_fact | True |
| Drift ¦ Inspect live Compose container image | ansible.builtin.shell | True |
| Drift ¦ Normalise live Compose container image | ansible.builtin.set_fact | True |
| Drift ¦ Determine image drift state | ansible.builtin.set_fact | True |
| Drift ¦ Report missing runtime service/container | ansible.builtin.debug | True |
| Drift ¦ Report image drift | ansible.builtin.debug | True |
| Drift ¦ Report image is current | ansible.builtin.debug | True |
| Drift ¦ Add service to drift summary | ansible.builtin.set_fact | True |

#### File: tasks/sub_tasks/drift/notify_email.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Drift Notify ¦ Ensure SMTP creds exist | block | True |
| Drift Notify ¦ Detect if SMTP creds are missing | ansible.builtin.set_fact | False |
| Drift Notify ¦ Fetch SMTP creds from Infisical | ansible.builtin.include_tasks | True |
| Drift Notify ¦ Assert SMTP creds are now present | ansible.builtin.assert | False |
| Drift Notify ¦ Build image drift email body | ansible.builtin.set_fact | True |
| Drift Notify ¦ Send image drift email | community.general.mail | True |

#### File: tasks/sub_tasks/init/validate.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Init - Validate ¦ Assert docker_services_svc is defined and is a mapping | ansible.builtin.assert | False |
| Init - Validate ¦ docker_services_svc.name | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.image (required) | ansible.builtin.assert | False |
| Init - Validate ¦ docker_services_svc.user | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.command shape | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.command string form | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.command list form | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.env_file shape | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.env_file string form | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.env_file list form | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.devices shape | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.cap_add shape | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.cap_drop shape | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.sysctls shape | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.deploy shape | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.deploy.type | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.deploy.profile | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.deploy.profile is swarm-only | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.deploy.mode | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.deploy.replicas | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.deploy.host (optional) | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.deploy.constraints | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.deploy.restart_policy | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.deploy.update_config | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.deploy.rollback_config | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.deploy.resources | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.targets shape | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.targets entries are mappings | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.named_networks | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.named_volumes | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.paths shape | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.paths entries | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.paths mode formatting | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.templates shape | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.templates entries | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.templates mode formatting | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.copies shape | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.copies entries | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.infisical shape | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.infisical.secrets_map | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.infisical.secrets_map var names | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.infisical.secrets_map docker_secret names | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.postgres shape | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.postgres.databases | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.healthcheck shape | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.secrets shape | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.secrets string form | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.secrets list form is non-empty | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.secrets list items are strings or dicts | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.secrets string items are non-empty | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.secrets dict items have source and target | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.ports shape | ansible.builtin.assert | True |
| Init - Validate ¦ Normalize ports items | ansible.builtin.set_fact | True |
| Init - Validate ¦ docker_services_svc.ports entries | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.volumes shape | ansible.builtin.assert | True |
| Init - Validate ¦ Normalize volume items | ansible.builtin.set_fact | True |
| Init - Validate ¦ docker_services_svc.volumes entries basic | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.volumes required keys by type | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.environment shape | ansible.builtin.assert | True |
| Init - Validate ¦ docker_services_svc.labels shape | ansible.builtin.assert | True |

#### File: tasks/sub_tasks/prep/authelia/_keys.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - Authelia Keys ¦ Assert required inputs | ansible.builtin.assert | False |
| Prep - Authelia Keys ¦ Resolve keys host | ansible.builtin.set_fact | False |
| Prep - Authelia Keys ¦ Determine if key already exists | ansible.builtin.set_fact | False |
| Prep - Authelia Keys ¦ Determine if docker secret creation is enabled | ansible.builtin.set_fact | False |
| Prep - Authelia Keys ¦ Ensure secret exists | community.docker.docker_secret | True |
| Prep - Authelia Keys ¦ Report missing key in check mode | ansible.builtin.debug | True |
| Prep - Authelia Keys ¦ Set check-mode placeholder generated value | ansible.builtin.set_fact | True |
| Prep - Authelia Keys ¦ Generate key | block | True |
| Prep - Authelia Keys ¦ Run generator container | community.docker.docker_container | False |
| Prep - Authelia Keys ¦ Extract generated value | ansible.builtin.shell | False |
| Prep - Authelia Keys ¦ Mark generated this run | ansible.builtin.set_fact | False |
| Prep - Authelia Keys ¦ Fail if generation produced empty output | ansible.builtin.assert | False |
| Prep - Authelia Keys ¦ Save generated value as a mgt fact | ansible.builtin.set_fact | True |
| Prep - Authelia Keys ¦ Ensure secret exists (generated key) | community.docker.docker_secret | True |

#### File: tasks/sub_tasks/prep/authelia/tasker.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - Authelia ¦ Generate argon2 + secrets | block | True |
| Prep - Authelia ¦ Generate argon2 digest | ansible.builtin.include_tasks | False |
| Prep - Authelia ¦ Ensure session key secret | ansible.builtin.include_tasks | False |
| Prep - Authelia ¦ Ensure storage key secret | ansible.builtin.include_tasks | False |
| Prep - Authelia ¦ Persist storage key in Infisical | ansible.builtin.debug | True |
| Prep - Authelia ¦ Ensure JWT reset key secret | ansible.builtin.include_tasks | False |

#### File: tasks/sub_tasks/prep/bazarr.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - Bazarr ¦ Set derived vars | ansible.builtin.set_fact | False |
| Prep - Bazarr ¦ Set secret vars | ansible.builtin.set_fact | False |
| Prep - Bazarr ¦ Set postgres vars | ansible.builtin.set_fact | True |
| Prep - Bazarr ¦ Assert postgres inputs are complete | ansible.builtin.assert | True |
| Prep - Bazarr ¦ Ensure config dir exists | ansible.builtin.file | False |
| Prep - Bazarr ¦ Check config exists | ansible.builtin.stat | False |
| Prep - Bazarr ¦ Generate config | block | True |
| Prep - Bazarr ¦ Start temp container to generate config | community.docker.docker_container | False |
| Prep - Bazarr ¦ Wait for config.yaml to appear | ansible.builtin.wait_for | False |
| Prep - Bazarr ¦ Give Bazarr time to finish writing config | ansible.builtin.pause | False |
| Prep - Bazarr ¦ Configure api setting | yedit | False |
| Prep - Bazarr ¦ Configure misc settings | yedit | False |
| Prep - Bazarr ¦ Configure opensubtitlescom settings | yedit | False |
| Prep - Bazarr ¦ Configure radarr settings | yedit | False |
| Prep - Bazarr ¦ Configure sonarr settings | yedit | False |
| Prep - Bazarr ¦ Configure postgres settings | yedit | False |

#### File: tasks/sub_tasks/prep/cleanup.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - Cleanup ¦ Derive cleanup stack name | ansible.builtin.set_fact | False |
| Prep - Cleanup ¦ Ensure cleanup stack name is set | ansible.builtin.assert | False |
| Prep - Cleanup ¦ Cleanup container stack | block | True |
| Prep - Cleanup ¦ Check if compose file exists | ansible.builtin.stat | False |
| Prep - Cleanup ¦ Compose down | community.docker.docker_compose_v2 | True |
| Prep - Cleanup ¦ Remove compose file | ansible.builtin.file | False |
| Prep - Cleanup ¦ Remove container secret files directory | ansible.builtin.file | False |
| Prep - Cleanup ¦ Remove stack directory if empty | ansible.builtin.file | False |
| Prep - Cleanup ¦ Cleanup swarm stack | block | True |
| Prep - Cleanup ¦ Stack down | community.docker.docker_stack | False |
| Prep - Cleanup ¦ Remove stack file | ansible.builtin.file | False |

#### File: tasks/sub_tasks/prep/copies.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - Copies ¦ Copy files | ansible.builtin.copy | False |
| Prep - Copies ¦ Wait for copied files | ansible.builtin.wait_for | True |

#### File: tasks/sub_tasks/prep/infisical/_fetch.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - Infisical Fetch ¦ Ensure secrets_map is defined | ansible.builtin.assert | False |
| Prep - Infisical Fetch ¦ Ensure infisical_lookup_default_params is defined | ansible.builtin.assert | False |
| Prep - Infisical Fetch ¦ Initialize dict output | ansible.builtin.set_fact | True |
| Prep - Infisical Fetch ¦ Fetch secrets from Infisical | ansible.builtin.set_fact | True |
| Prep - Infisical Fetch ¦ Fail if any fetched secret is empty | ansible.builtin.assert | True |
| Prep - Infisical Fetch ¦ Fetch secrets from Infisical | ansible.builtin.set_fact | True |
| Prep - Infisical Fetch ¦ Fail if any fetched secret is empty | ansible.builtin.assert | True |

#### File: tasks/sub_tasks/prep/infisical/_resolver.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - Infisical Resolver ¦ Determine fail-on-empty behavior | ansible.builtin.set_fact | True |
| Prep - Infisical Resolver ¦ Initialize resolved environment + placeholder key list | ansible.builtin.set_fact | True |
| Prep - Infisical Resolver ¦ Resolve placeholders | ansible.builtin.set_fact | True |
| Prep - Infisical Resolver ¦ Replace docker_services_svc.environment with resolved values | ansible.builtin.set_fact | True |
| Prep - Infisical Resolver ¦ Fail if any placeholders remain | ansible.builtin.fail | True |
| Prep - Infisical Resolver ¦ Fail if any placeholder-resolved env key is empty | ansible.builtin.assert | True |

#### File: tasks/sub_tasks/prep/infisical/_secrets.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - Infisical Secrets ¦ Reset working list | ansible.builtin.set_fact | False |
| Prep - Infisical Secrets ¦ Resolve deploy host | ansible.builtin.set_fact | False |
| Prep - Infisical Secrets ¦ Resolve effective secrets host | ansible.builtin.set_fact | False |
| Prep - Infisical Secrets ¦ Build desired secret items from secrets_map | ansible.builtin.set_fact | False |
| Prep - Infisical Secrets ¦ Dedupe by name (keep first), keep empties for visibility | ansible.builtin.set_fact | False |
| Prep - Infisical Secrets ¦ Warn about empty secret values | ansible.builtin.debug | True |
| Prep - Infisical Secrets ¦ Create Docker Swarm secrets | community.docker.docker_secret | True |
| Prep - Infisical Secrets ¦ Ensure secrets directory exists on deploy host | ansible.builtin.file | True |
| Prep - Infisical Secrets ¦ Remove secret path if it exists but is a directory | ansible.builtin.file | True |
| Prep - Infisical Secrets ¦ Write secret files on deploy host | ansible.builtin.copy | True |
| Prep - Infisical Secrets ¦ Verify secret paths exist and are files | ansible.builtin.stat | True |
| Prep - Infisical Secrets ¦ Fail if any secret path is not a file | ansible.builtin.assert | True |

#### File: tasks/sub_tasks/prep/infisical/tasker.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Prep - Infisical Fetch ¦ Include tasks | ansible.builtin.include_tasks | True |  |
| Prep - Infisical Resolver ¦ Include tasks on deploy host | ansible.builtin.include_tasks | True |  |
| Prep - Infisical Resolver ¦ Propagate Infisical flattened vars to deploy host | ansible.builtin.set_fact | True |  |
| Prep - Infisical Resolver ¦ Propagate Infisical dict to deploy host | ansible.builtin.set_fact | True |  |
| Prep - Infisical Secrets ¦ Include tasks | ansible.builtin.include_tasks | True |  |

#### File: tasks/sub_tasks/prep/nzbhydra2.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - NZBHydra2 ¦ Set filesystem host | ansible.builtin.set_fact | False |
| Prep - NZBHydra2 ¦ Set derived vars | ansible.builtin.set_fact | False |
| Prep - NZBHydra2 ¦ Assert required secrets are present | ansible.builtin.assert | False |
| Prep - NZBHydra2 ¦ Assert altHUB secrets are complete when used | ansible.builtin.assert | False |
| Prep - NZBHydra2 ¦ Assert NZBGeek secrets are complete when used | ansible.builtin.assert | False |
| Prep - NZBHydra2 ¦ Assert Drunken Slug secrets are complete when used | ansible.builtin.assert | False |
| Prep - NZBHydra2 ¦ Ensure config dir exists | ansible.builtin.file | False |
| Prep - NZBHydra2 ¦ Check config exists | ansible.builtin.stat | False |
| Prep - NZBHydra2 ¦ Report missing config in check mode | ansible.builtin.debug | True |
| Prep - NZBHydra2 ¦ Determine whether config can be managed | ansible.builtin.set_fact | False |
| Prep - NZBHydra2 ¦ Generate config | block | True |
| Prep - NZBHydra2 ¦ Start temp container to generate config | community.docker.docker_container | False |
| Prep - NZBHydra2 ¦ Wait for config to appear | ansible.builtin.wait_for | False |
| Prep - NZBHydra2 ¦ Wait for config file size to stabilize | ansible.builtin.shell | False |
| Prep - NZBHydra2 ¦ Build config facts | ansible.builtin.set_fact | False |
| Prep - NZBHydra2 ¦ Set auth user | yedit | True |
| Prep - NZBHydra2 ¦ Set API key | yedit | True |
| Prep - NZBHydra2 ¦ Report API key update in check mode | ansible.builtin.debug | True |
| Prep - NZBHydra2 ¦ Replace downloaders list | block | True |
| Prep - NZBHydra2 ¦ Remove existing downloaders | yedit | False |
| Prep - NZBHydra2 ¦ Write managed downloaders | yedit | False |
| Prep - NZBHydra2 ¦ Replace indexers list | block | True |
| Prep - NZBHydra2 ¦ Remove existing indexers | yedit | False |
| Prep - NZBHydra2 ¦ Write managed indexers | yedit | False |
| Prep - NZBHydra2 ¦ Report managed config update in check mode | ansible.builtin.debug | True |
| Prep - NZBHydra2 ¦ Ensure config file permissions are restricted | ansible.builtin.file | True |
| Prep - NZBHydra2 ¦ Slurp config | ansible.builtin.slurp | True |
| Prep - NZBHydra2 ¦ Parse config YAML | ansible.builtin.set_fact | True |
| Prep - NZBHydra2 ¦ Assert API key set | ansible.builtin.assert | True |
| Prep - NZBHydra2 ¦ Assert SABnzbd downloader is set | ansible.builtin.assert | True |
| Prep - NZBHydra2 ¦ Assert configured indexers were written | ansible.builtin.assert | True |

#### File: tasks/sub_tasks/prep/paths.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - Paths ¦ Validate each path spec | ansible.builtin.assert | False |
| Prep - Paths ¦ Apply filesystem state on deploy host | ansible.builtin.file | False |

#### File: tasks/sub_tasks/prep/plex/_claim.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Claim ¦ Set derived vars | ansible.builtin.set_fact | False |
| Claim ¦ Load token + client identifier from token host | ansible.builtin.set_fact | False |
| Claim ¦ Assert required vars exist | ansible.builtin.assert | False |
| Claim ¦ Check if Plex server is already claimed | ansible.builtin.stat | False |
| Claim ¦ Read Preferences.xml | community.general.xml | True |
| Claim ¦ Determine claimed status | ansible.builtin.set_fact | False |
| Claim ¦ Request claim token from plex.tv | ansible.builtin.uri | True |
| Claim ¦ Persist claim code to token host | ansible.builtin.set_fact | True |
| Claim ¦ Validate claim code | ansible.builtin.assert | True |
| Claim ¦ Report claim status | ansible.builtin.debug | False |

#### File: tasks/sub_tasks/prep/plex/_preferences.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - Plex Preferences ¦ Conduct preferences.xml tasks | block | False |
| Prep - Plex Preferences ¦ Set derived vars | ansible.builtin.set_fact | False |
| Prep - Plex Preferences ¦ Check if Preferences.xml exists | ansible.builtin.stat | False |
| Prep - Plex Preferences ¦ Read Preferences.xml attributes | community.general.xml | True |
| Prep - Plex Preferences ¦ Remove Preferences.xml if malformed | ansible.builtin.file | True |
| Prep - Plex Preferences ¦ Derive flags from Preferences.xml | ansible.builtin.set_fact | True |
| Prep - Plex Preferences ¦ Fix TranscoderTempDirectory | community.general.xml | True |

#### File: tasks/sub_tasks/prep/plex/_token.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - Plex Token ¦ Set file ownership facts | ansible.builtin.set_fact | False |
| Prep - Plex Token ¦ Check if plex.ini exists | ansible.builtin.stat | False |
| Prep - Plex Token ¦ Set client identifier fact | block | True |
| Prep - Plex Token ¦ Lookup client_identifier | ansible.builtin.set_fact | False |
| Prep - Plex Token ¦ Generate new identifier | ansible.builtin.set_fact | True |
| Prep - Plex Token ¦ Set token variable if previously saved | ansible.builtin.set_fact | True |
| Prep - Plex Token ¦ Set docker_services_plex_no_token status | ansible.builtin.set_fact | False |
| Prep - Plex Token ¦ Check if Token is valid | ansible.builtin.uri | True |
| Prep - Plex Token ¦ Generate New Token | block | True |
| Prep - Plex Token ¦ Generate PIN | ansible.builtin.uri | False |
| Prep - Plex Token ¦ Login prompt | ansible.builtin.pause | False |
| Prep - Plex Token ¦ Check PIN | ansible.builtin.uri | False |
| Prep - Plex Token ¦ Set docker_services_plex_auth_token variable | ansible.builtin.set_fact | False |
| Prep - Plex Token ¦ Check if new Token is valid | ansible.builtin.uri | False |
| Prep - Plex Token ¦ Fail if new token is invalid | ansible.builtin.fail | True |
| Prep - Plex Token ¦ Add Client Identifier to plex.ini | community.general.ini_file | False |
| Prep - Plex Token ¦ Add Token to plex.ini | community.general.ini_file | False |
| Prep - Plex Token ¦ Report token status | ansible.builtin.debug | True |

#### File: tasks/sub_tasks/prep/plex/tasker.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - Plex Prep ¦ Set derived vars | ansible.builtin.set_fact | False |
| Prep - Plex Prep ¦ Assert derived hosts are valid | ansible.builtin.assert | False |
| Prep - Plex Volume ¦ Create media volume (NFS) | community.docker.docker_volume | False |
| Prep - Plex Token ¦ Include token tasks | ansible.builtin.include_tasks | False |
| Prep - Plex Preferences ¦ Include Plex preferences.xml tasks | ansible.builtin.include_tasks | False |
| Prep - Plex Claim ¦ Include claim server tasks | ansible.builtin.include_tasks | False |

#### File: tasks/sub_tasks/prep/postgres.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - Postgres ¦ Ensure creds exist | block | True |
| Prep - Postgres ¦ Detect if creds are missing | ansible.builtin.set_fact | False |
| Prep - Postgres ¦ Fetch Postgres creds from Infisical | ansible.builtin.include_tasks | True |
| Prep - Postgres ¦ Assert creds are now present | ansible.builtin.assert | False |
| Prep - Postgres ¦ Prepare docker secret | community.docker.docker_secret | True |
| Prep - Postgres ¦ Normalize postgres database list | ansible.builtin.set_fact | True |
| Prep - Postgres ¦ Ping for existing database(s) | community.postgresql.postgresql_ping | True |
| Prep - Postgres ¦ Create database(s) if missing | community.postgresql.postgresql_db | True |

#### File: tasks/sub_tasks/prep/qbittorrent.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - qBittorrent ¦ Set derived vars | ansible.builtin.set_fact | False |
| Prep - qBittorrent ¦ Assert downloads-instance password is present | ansible.builtin.assert | True |
| Prep - qBittorrent ¦ Generate downloads-instance pass | qbittorrent_passwd | True |
| Prep - qBittorrent ¦ Store downloads-instance pass hash | ansible.builtin.set_fact | True |
| Prep - qBittorrent ¦ Assert downloads-instance pass hash was generated | ansible.builtin.assert | True |
| Prep - qBittorrent ¦ Assert seeds-instance password is present | ansible.builtin.assert | True |
| Prep - qBittorrent ¦ Generate seeds-instance pass | qbittorrent_passwd | True |
| Prep - qBittorrent ¦ Store seeds-instance pass hash | ansible.builtin.set_fact | True |
| Prep - qBittorrent ¦ Assert seeds-instance pass hash was generated | ansible.builtin.assert | True |

#### File: tasks/sub_tasks/prep/swarm_configs/_absent.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - Swarm Configs (Absent) ¦ List existing config names | ansible.builtin.command | False |
| Prep - Swarm Configs (Absent) ¦ Find matching configs | ansible.builtin.set_fact | False |
| Prep - Swarm Configs (Absent) ¦ Record absent config base name | ansible.builtin.set_fact | False |
| Prep - Swarm Configs (Absent) ¦ Remove absent configs | community.docker.docker_config | True |

#### File: tasks/sub_tasks/prep/swarm_configs/_present.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - Swarm Configs (Present) ¦ Render desired config content | ansible.builtin.set_fact | False |
| Prep - Swarm Configs (Present) ¦ Hash rendered content | ansible.builtin.set_fact | False |
| Prep - Swarm Configs (Present) ¦ Ensure versioned config exists | community.docker.docker_config | False |
| Prep - Swarm Configs (Present) ¦ Store effective config mapping | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/prep/swarm_configs/tasker.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - Swarm Configs ¦ Ensure swarm_configs is a list | ansible.builtin.assert | False |
| Prep - Swarm Configs ¦ Resolve deploy host (swarm manager) | ansible.builtin.set_fact | False |
| Prep - Swarm Configs ¦ Initialize effective config maps | ansible.builtin.set_fact | False |
| Prep - Swarm Configs ¦ Validate each config spec | ansible.builtin.assert | False |
| Prep - Swarm Configs ¦ Process absent configs | ansible.builtin.include_tasks | True |
| Prep - Swarm Configs ¦ Process present configs | ansible.builtin.include_tasks | True |

#### File: tasks/sub_tasks/prep/templates.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - Templates ¦ Render templates on deploy host | ansible.builtin.template | False |

#### File: tasks/sub_tasks/prep/traefik.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - Traefik ¦ Detect if zone is missing | ansible.builtin.set_fact | False |
| Prep - Traefik ¦ Fetch cloudflare_zone from Infisical | ansible.builtin.include_tasks | True |
| Prep - Traefik ¦ Render dynamic file | ansible.builtin.template | False |

#### File: tasks/sub_tasks/prep/vaultwarden.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - Vaultwarden ¦ Set derived vars | ansible.builtin.set_fact | False |
| Prep - Vaultwarden ¦ Ensure vaultwarden dir exists | ansible.builtin.file | False |
| Prep - Vaultwarden ¦ Check if admin token file exists | ansible.builtin.stat | False |
| Prep - Vaultwarden ¦ Read existing token | ansible.builtin.slurp | True |
| Prep - Vaultwarden ¦ Create new admin token | block | True |
| Prep - Vaultwarden ¦ Generate random password | ansible.builtin.command | False |
| Prep - Vaultwarden ¦ Save generated password | ansible.builtin.copy | False |
| Prep - Vaultwarden ¦ Generate random salt | ansible.builtin.command | False |
| Prep - Vaultwarden ¦ Generate Argon2 PHC string | ansible.builtin.command | False |
| Prep - Vaultwarden ¦ Save argon2 token | ansible.builtin.copy | False |
| Prep - Vaultwarden ¦ Set admin token fact | ansible.builtin.set_fact | False |
| Prep - Vaultwarden ¦ Assert token looks like PHC argon2 string | ansible.builtin.assert | False |
| Prep - Vaultwarden ¦ Ensure docker secret exists | community.docker.docker_secret | False |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
