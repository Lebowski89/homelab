<!-- DOCSIBLE START -->

# 📃 Role overview

## docker_services





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/08/02 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [docker_services_default_deploy_profile](defaults/main.yml#L3)   | str | `none` |    
| [docker_services_deploy_profiles](defaults/main.yml#L5)   | dict | `{}` |    
| [docker_services_deploy_profiles.**none**](defaults/main.yml#L6)   | dict | `{}` |    
| [docker_services_deploy_profiles.**standard**](defaults/main.yml#L8)   | dict | `{}` |    
| [docker_services_deploy_profiles.standard.**restart_policy**](defaults/main.yml#L9)   | dict | `{}` |    
| [docker_services_deploy_profiles.standard.restart_policy.**condition**](defaults/main.yml#L10)   | str | `on-failure` |    
| [docker_services_deploy_profiles.standard.restart_policy.**delay**](defaults/main.yml#L11)   | str | `10s` |    
| [docker_services_deploy_profiles.standard.restart_policy.**max_attempts**](defaults/main.yml#L12)   | int | `5` |    
| [docker_services_deploy_profiles.standard.restart_policy.**window**](defaults/main.yml#L13)   | str | `2m` |    
| [docker_services_deploy_profiles.standard.**update_config**](defaults/main.yml#L14)   | dict | `{}` |    
| [docker_services_deploy_profiles.standard.update_config.**parallelism**](defaults/main.yml#L15)   | int | `1` |    
| [docker_services_deploy_profiles.standard.update_config.**delay**](defaults/main.yml#L16)   | str | `10s` |    
| [docker_services_deploy_profiles.standard.update_config.**failure_action**](defaults/main.yml#L17)   | str | `rollback` |    
| [docker_services_deploy_profiles.standard.update_config.**order**](defaults/main.yml#L18)   | str | `stop-first` |    
| [docker_services_deploy_profiles.standard.**rollback_config**](defaults/main.yml#L19)   | dict | `{}` |    
| [docker_services_deploy_profiles.standard.rollback_config.**parallelism**](defaults/main.yml#L20)   | int | `1` |    
| [docker_services_deploy_profiles.standard.rollback_config.**delay**](defaults/main.yml#L21)   | str | `10s` |    
| [docker_services_deploy_profiles.standard.rollback_config.**order**](defaults/main.yml#L22)   | str | `stop-first` |    
| [docker_services_deploy_profiles.**careful**](defaults/main.yml#L24)   | dict | `{}` |    
| [docker_services_deploy_profiles.careful.**restart_policy**](defaults/main.yml#L25)   | dict | `{}` |    
| [docker_services_deploy_profiles.careful.restart_policy.**condition**](defaults/main.yml#L26)   | str | `on-failure` |    
| [docker_services_deploy_profiles.careful.restart_policy.**delay**](defaults/main.yml#L27)   | str | `10s` |    
| [docker_services_deploy_profiles.careful.restart_policy.**max_attempts**](defaults/main.yml#L28)   | int | `5` |    
| [docker_services_deploy_profiles.careful.restart_policy.**window**](defaults/main.yml#L29)   | str | `2m` |    
| [docker_services_deploy_profiles.careful.**update_config**](defaults/main.yml#L30)   | dict | `{}` |    
| [docker_services_deploy_profiles.careful.update_config.**parallelism**](defaults/main.yml#L31)   | int | `1` |    
| [docker_services_deploy_profiles.careful.update_config.**delay**](defaults/main.yml#L32)   | str | `30s` |    
| [docker_services_deploy_profiles.careful.update_config.**failure_action**](defaults/main.yml#L33)   | str | `rollback` |    
| [docker_services_deploy_profiles.careful.update_config.**order**](defaults/main.yml#L34)   | str | `stop-first` |    
| [docker_services_deploy_profiles.careful.**rollback_config**](defaults/main.yml#L35)   | dict | `{}` |    
| [docker_services_deploy_profiles.careful.rollback_config.**parallelism**](defaults/main.yml#L36)   | int | `1` |    
| [docker_services_deploy_profiles.careful.rollback_config.**delay**](defaults/main.yml#L37)   | str | `30s` |    
| [docker_services_deploy_profiles.careful.rollback_config.**order**](defaults/main.yml#L38)   | str | `stop-first` |    
| [docker_services_deploy_profiles.**stateless_ha**](defaults/main.yml#L40)   | dict | `{}` |    
| [docker_services_deploy_profiles.stateless_ha.**restart_policy**](defaults/main.yml#L41)   | dict | `{}` |    
| [docker_services_deploy_profiles.stateless_ha.restart_policy.**condition**](defaults/main.yml#L42)   | str | `on-failure` |    
| [docker_services_deploy_profiles.stateless_ha.restart_policy.**delay**](defaults/main.yml#L43)   | str | `5s` |    
| [docker_services_deploy_profiles.stateless_ha.restart_policy.**max_attempts**](defaults/main.yml#L44)   | int | `5` |    
| [docker_services_deploy_profiles.stateless_ha.restart_policy.**window**](defaults/main.yml#L45)   | str | `2m` |    
| [docker_services_deploy_profiles.stateless_ha.**update_config**](defaults/main.yml#L46)   | dict | `{}` |    
| [docker_services_deploy_profiles.stateless_ha.update_config.**parallelism**](defaults/main.yml#L47)   | int | `1` |    
| [docker_services_deploy_profiles.stateless_ha.update_config.**delay**](defaults/main.yml#L48)   | str | `5s` |    
| [docker_services_deploy_profiles.stateless_ha.update_config.**failure_action**](defaults/main.yml#L49)   | str | `rollback` |    
| [docker_services_deploy_profiles.stateless_ha.update_config.**order**](defaults/main.yml#L50)   | str | `start-first` |    
| [docker_services_deploy_profiles.stateless_ha.**rollback_config**](defaults/main.yml#L51)   | dict | `{}` |    
| [docker_services_deploy_profiles.stateless_ha.rollback_config.**parallelism**](defaults/main.yml#L52)   | int | `1` |    
| [docker_services_deploy_profiles.stateless_ha.rollback_config.**delay**](defaults/main.yml#L53)   | str | `5s` |    
| [docker_services_deploy_profiles.stateless_ha.rollback_config.**order**](defaults/main.yml#L54)   | str | `start-first` |    





### Tasks


#### File: tasks/_compose.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Compose - Init ¦ Ensure docker_services_compose_stacks exists | ansible.builtin.set_fact | False |  |
| Compose - Init ¦ Load this stack's current docker_services_compose_services | ansible.builtin.set_fact | True |  |
| Compose - Base ¦ Register networks needed by this stack | ansible.builtin.include_tasks | True |  |
| Compose - Base ¦ Normalize network_mode for container deploys | ansible.builtin.set_fact | True |  |
| Compose - Base ¦ Normalize network_mode for container deploys | ansible.builtin.set_fact | True |  |
| Compose - Base ¦ Build service networks list | ansible.builtin.set_fact | True |  |
| Compose - Base ¦ Register external volumes needed by this stack | ansible.builtin.include_tasks | True |  |
| Compose - Base ¦ Set base service variables | ansible.builtin.include_tasks | True |  |
| Compose - Runtime ¦ Set security_opt | ansible.builtin.include_tasks | True |  |
| Compose - Runtime ¦ Add canonical no-new-privileges security option | ansible.builtin.include_tasks | True |  |
| Compose - Runtime ¦ Set sysctls | ansible.builtin.include_tasks | True |  |
| Compose - Runtime ¦ Set depends_on | ansible.builtin.include_tasks | True |  |
| Compose - Runtime ¦ Add Linux capabilities (cap_add) | ansible.builtin.include_tasks | True |  |
| Compose - Runtime ¦ Drop Linux capabilities (cap_drop) | ansible.builtin.include_tasks | True |  |
| Compose - Runtime ¦ Add devices | ansible.builtin.include_tasks | True |  |
| Compose - Runtime ¦ Set command variable | ansible.builtin.include_tasks | True |  |
| Compose - Runtime ¦ Set healthcheck variable | ansible.builtin.include_tasks | True |  |
| Compose - Runtime ¦ Set user variable | ansible.builtin.include_tasks | True |  |
| Compose - IO ¦ Set environment variables | ansible.builtin.include_tasks | True |  |
| Compose - IO ¦ Attach env_file to service | ansible.builtin.include_tasks | True |  |
| Compose - IO ¦ Set secrets variable | ansible.builtin.include_tasks | True |  |
| Compose - IO ¦ Set Swarm configs variable | ansible.builtin.include_tasks | True |  |
| Compose - IO ¦ Set ports variable | ansible.builtin.include_tasks | True |  |
| Compose - IO ¦ Set tmpfs variable | ansible.builtin.include_tasks | True |  |
| Compose - IO ¦ Set volumes variable | ansible.builtin.include_tasks | True |  |
| Compose - IO ¦ Add /dev/shm tmpfs | ansible.builtin.include_tasks | True |  |
| Compose - IO ¦ Set SHM size | ansible.builtin.include_tasks | True |  |
| Compose - Metadata ¦ Attach service labels | ansible.builtin.include_tasks | True |  |

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
| Init ¦ Use catalog-resolved service config | ansible.builtin.set_fact | False |  |
| Init ¦ Validate dispatch-owned common context | ansible.builtin.assert | False |  |
| Init ¦ Reset per-service common snapshots | ansible.builtin.set_fact | False |  |
| Init ¦ Snapshot dispatch-owned common context | ansible.builtin.set_fact | False |  |
| Init ¦ Validate Docker secret attachment metadata before cleanup | ansible.builtin.set_fact | False |  |
| Init ¦ Attach common resolved environment | ansible.builtin.set_fact | False |  |
| Init ¦ Determine whether schema validation should run | ansible.builtin.set_fact | False |  |
| Init ¦ Validate normalized service config | ansible.builtin.include_tasks | True |  |
| Init ¦ Derive common service context | ansible.builtin.set_fact | False |  |
| Init ¦ Derive stack name | ansible.builtin.set_fact | False |  |
| Init ¦ Derive effective deploy host | ansible.builtin.set_fact | False |  |
| Init ¦ Derive effective stack key | ansible.builtin.set_fact | False |  |
| Init ¦ Derive effective filesystem hosts | ansible.builtin.set_fact | False |  |
| Init ¦ Expand filesystem hosts if a group name was provided | ansible.builtin.set_fact | True |  |
| Init ¦ De-dupe filesystem hosts | ansible.builtin.set_fact | False |  |
| Init ¦ Validate effective filesystem hosts | ansible.builtin.assert | False |  |
| Init ¦ Initialize runtime-neutral container host defaults | ansible.builtin.set_fact | False |  |
| Init ¦ Build runtime-neutral container host defaults | ansible.builtin.set_fact | False |  |
| Init ¦ Assert container deploy has a single deploy.host | ansible.builtin.assert | True |  |
| Init ¦ Determine if this host should build/deploy compose artifacts | ansible.builtin.set_fact | False |  |

#### File: tasks/_prep.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Prep - Application validation ¦ Build runtime-neutral context | ansible.builtin.set_fact | False |  |
| Prep - Application validation ¦ Validate current service | ansible.builtin.include_role | False |  |
| Prep - Application validation ¦ Snapshot reset outputs | ansible.builtin.set_fact | False |  |
| Prep - Cleanup ¦ Derive cleanup flags | ansible.builtin.set_fact | False |  |
| Prep - Cleanup ¦ Init cleaned-stacks tracker | ansible.builtin.set_fact | True |  |
| Prep - Cleanup ¦ Determine if stack cleanup should run | ansible.builtin.set_fact | True |  |
| Prep - Cleanup ¦ Remove existing stack | ansible.builtin.include_tasks | True |  |
| Prep - Cleanup ¦ Mark stack as cleaned | ansible.builtin.set_fact | True |  |
| Prep - Application secrets ¦ Run runtime-neutral generation | ansible.builtin.include_role | True |  |
| Prep - Application secrets ¦ Snapshot portable generation outputs | ansible.builtin.set_fact | True |  |
| Prep - Application secrets ¦ Build effective current-service secret inputs | ansible.builtin.set_fact | False |  |
| Prep - Application secrets ¦ Validate effective attachment metadata | ansible.builtin.set_fact | False |  |
| Prep - Secrets ¦ Materialize Docker-native secrets | ansible.builtin.include_tasks | True |  |
| Prep - Application templates ¦ Derive runtime-neutral values | ansible.builtin.include_role | True |  |
| Prep - Application templates ¦ Snapshot portable values | ansible.builtin.set_fact | False |  |
| Prep - Service common ¦ Prepare files and Traefik integration | ansible.builtin.include_role | False |  |
| Prep - Swarm environment templates ¦ Render templates | ansible.builtin.include_role | True |  |
| Prep - Application configuration ¦ Apply runtime-neutral configuration | ansible.builtin.include_role | True |  |
| Prep - Application bootstrap ¦ Run explicit Plex bootstrap | ansible.builtin.include_role | True |  |
| Prep - Swarm configs ¦ Include tasker | ansible.builtin.include_tasks | True |  |

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
| Compose - Secrets ¦ Normalize legacy and canonical attachments | ansible.builtin.set_fact | False |
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

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Deploy - All ¦ Ensure docker_services_compose_stacks exists | ansible.builtin.set_fact | False |  |
| Deploy - All ¦ Deploy each stack | ansible.builtin.include_tasks | True |  |

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
| Init - Validate ¦ docker_services_svc.no_new_privileges | ansible.builtin.assert | True |
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

#### File: tasks/sub_tasks/prep/secrets.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - Secrets ¦ Resolve deploy host | ansible.builtin.set_fact | False |
| Prep - Secrets ¦ Resolve effective secrets host | ansible.builtin.set_fact | False |
| Prep - Secrets ¦ Build desired secret items from effective declarations | ansible.builtin.set_fact | False |
| Prep - Secrets ¦ Reject empty secret values before materialization | ansible.builtin.assert | False |
| Prep - Secrets ¦ Inspect exact Docker Swarm secrets | ansible.builtin.command | True |
| Prep - Secrets ¦ Classify exact Docker Swarm secret inspections | ansible.builtin.set_fact | False |
| Prep - Secrets ¦ Resolve existing Docker Swarm secrets | ansible.builtin.set_fact | False |
| Prep - Secrets ¦ Reject unmanaged existing secrets before reconciliation | ansible.builtin.assert | True |
| Prep - Secrets ¦ Create Docker Swarm secrets | community.docker.docker_secret | True |
| Prep - Secrets ¦ Ensure secrets directory exists on deploy host | ansible.builtin.file | True |
| Prep - Secrets ¦ Remove secret path if it exists but is a directory | ansible.builtin.file | True |
| Prep - Secrets ¦ Write secret files on deploy host | ansible.builtin.copy | True |
| Prep - Secrets ¦ Enforce secret file ownership and mode | ansible.builtin.file | True |
| Prep - Secrets ¦ Verify secret paths exist and are files | ansible.builtin.stat | True |
| Prep - Secrets ¦ Fail if any secret path is not a file | ansible.builtin.assert | True |

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









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
