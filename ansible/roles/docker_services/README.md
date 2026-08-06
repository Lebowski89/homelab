<!-- DOCSIBLE START -->

# 📃 Role overview

## docker_services





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/08/06 |








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


#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Docker services ¦ Initialize service | ansible.builtin.include_tasks | False |  |
| Docker services ¦ Check image drift | ansible.builtin.include_tasks | True |  |
| Docker services ¦ Prepare service | ansible.builtin.include_tasks | False |  |
| Docker services ¦ Build Compose configuration | ansible.builtin.include_tasks | False |  |
| Docker services ¦ Save stack configuration | ansible.builtin.include_tasks | False |  |

#### File: tasks/sub_tasks/cleanup.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Cleanup ¦ Choose stack name | ansible.builtin.set_fact | False |
| Cleanup ¦ Validate stack name | ansible.builtin.assert | False |
| Cleanup ¦ Remove standalone Compose project | block | True |
| Cleanup ¦ Check for existing Compose file | ansible.builtin.stat | False |
| Cleanup ¦ Stop and remove Compose project | community.docker.docker_compose_v2 | True |
| Cleanup ¦ Remove Compose file | ansible.builtin.file | False |
| Cleanup ¦ Remove standalone secret files | ansible.builtin.file | False |
| Cleanup ¦ Remove standalone stack directory | ansible.builtin.file | False |
| Cleanup ¦ Remove Swarm stack | block | True |
| Cleanup ¦ Remove Swarm stack from cluster | community.docker.docker_stack | False |
| Cleanup ¦ Remove Swarm stack file | ansible.builtin.file | False |

#### File: tasks/sub_tasks/compose.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Compose ¦ Load saved stack configurations | ansible.builtin.set_fact | False |  |
| Compose ¦ Load existing services for this stack | ansible.builtin.set_fact | True |  |
| Compose ¦ Add stack networks | ansible.builtin.include_tasks | True |  |
| Compose ¦ Read standalone network mode | ansible.builtin.set_fact | True |  |
| Compose ¦ Check whether standalone network mode is set | ansible.builtin.set_fact | True |  |
| Compose ¦ Build service network list | ansible.builtin.set_fact | True |  |
| Compose ¦ Add stack volumes | ansible.builtin.include_tasks | True |  |
| Compose ¦ Build base service | ansible.builtin.include_tasks | True |  |
| Compose ¦ Add security options | ansible.builtin.include_tasks | True |  |
| Compose ¦ Add no-new-privileges security option | ansible.builtin.include_tasks | True |  |
| Compose ¦ Add sysctls | ansible.builtin.include_tasks | True |  |
| Compose ¦ Add service dependencies | ansible.builtin.include_tasks | True |  |
| Compose ¦ Add Linux capabilities | ansible.builtin.include_tasks | True |  |
| Compose ¦ Drop Linux capabilities | ansible.builtin.include_tasks | True |  |
| Compose ¦ Add devices | ansible.builtin.include_tasks | True |  |
| Compose ¦ Add command | ansible.builtin.include_tasks | True |  |
| Compose ¦ Add healthcheck | ansible.builtin.include_tasks | True |  |
| Compose ¦ Set container user | ansible.builtin.include_tasks | True |  |
| Compose ¦ Add environment variables | ansible.builtin.include_tasks | True |  |
| Compose ¦ Add environment files | ansible.builtin.include_tasks | True |  |
| Compose ¦ Add secrets | ansible.builtin.include_tasks | True |  |
| Compose ¦ Add Swarm configs | ansible.builtin.include_tasks | True |  |
| Compose ¦ Add published ports | ansible.builtin.include_tasks | True |  |
| Compose ¦ Add tmpfs mounts | ansible.builtin.include_tasks | True |  |
| Compose ¦ Add volumes | ansible.builtin.include_tasks | True |  |
| Compose ¦ Add /dev/shm tmpfs | ansible.builtin.include_tasks | True |  |
| Compose ¦ Set shared-memory size | ansible.builtin.include_tasks | True |  |
| Compose ¦ Add service labels | ansible.builtin.include_tasks | True |  |
| Compose ¦ Add Swarm deployment settings | ansible.builtin.include_tasks | True |  |

#### File: tasks/sub_tasks/compose/base.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose base ¦ Validate service name | ansible.builtin.assert | False |
| Compose base ¦ Read deploy type | ansible.builtin.set_fact | False |
| Compose base ¦ Create service definition | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/command.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose command ¦ Validate service name | ansible.builtin.assert | False |
| Compose command ¦ Validate update action | ansible.builtin.assert | False |
| Compose command ¦ Choose input value | ansible.builtin.set_fact | False |
| Compose command ¦ Require a command | ansible.builtin.fail | True |
| Compose command ¦ Convert command list to strings | ansible.builtin.set_fact | True |
| Compose command ¦ Convert command to a consistent form | ansible.builtin.set_fact | False |
| Compose command ¦ Read existing command | ansible.builtin.set_fact | False |
| Compose command ¦ Prepare values for merging | ansible.builtin.set_fact | False |
| Compose command ¦ Build final command | ansible.builtin.set_fact | False |
| Compose command ¦ Save command to service | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/configs.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose configs ¦ Validate service name | ansible.builtin.assert | False |
| Compose configs ¦ Validate config list | ansible.builtin.assert | False |
| Compose configs ¦ Resolve config names | ansible.builtin.set_fact | False |
| Compose configs ¦ Add configs to service | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/deploy.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose deploy settings ¦ Validate service name | ansible.builtin.assert | False |
| Compose deploy settings ¦ Build Swarm deploy settings | ansible.builtin.set_fact | False |
| Compose deploy settings ¦ Add deploy settings to service | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/env_file.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose environment files ¦ Validate service name | ansible.builtin.assert | False |
| Compose environment files ¦ Read environment file list | ansible.builtin.set_fact | False |
| Compose environment files ¦ Add environment files to service | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/environment.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose environment ¦ Validate service name | ansible.builtin.assert | False |
| Compose environment ¦ Validate update action | ansible.builtin.assert | False |
| Compose environment ¦ Read environment values | ansible.builtin.set_fact | False |
| Compose environment ¦ Build final environment | ansible.builtin.set_fact | False |
| Compose environment ¦ Add environment to service | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/healthcheck.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose healthcheck ¦ Validate service name | ansible.builtin.assert | False |
| Compose healthcheck ¦ Require healthcheck command | ansible.builtin.assert | False |
| Compose healthcheck ¦ Read healthcheck command | ansible.builtin.set_fact | False |
| Compose healthcheck ¦ Add healthcheck to service | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/labels.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose labels ¦ Validate service name | ansible.builtin.assert | False |
| Compose labels ¦ Read existing labels | ansible.builtin.set_fact | False |
| Compose labels ¦ Build final labels | ansible.builtin.set_fact | False |
| Compose labels ¦ Add labels to service | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/list_field.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose list field ¦ Validate service name | ansible.builtin.assert | False |
| Compose list field ¦ Validate field and update action | ansible.builtin.assert | False |
| Compose list field ¦ Read existing values | ansible.builtin.set_fact | False |
| Compose list field ¦ Build final values | ansible.builtin.set_fact | False |
| Compose list field ¦ Add values to service | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/ports.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose ports ¦ Validate service name | ansible.builtin.assert | False |
| Compose ports ¦ Read existing ports | ansible.builtin.set_fact | False |
| Compose ports ¦ Build final port list | ansible.builtin.set_fact | False |
| Compose ports ¦ Add ports to service | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/secrets.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose secrets ¦ Validate service name | ansible.builtin.assert | False |
| Compose secrets ¦ Build secret attachments | ansible.builtin.set_fact | False |
| Compose secrets ¦ Add Swarm secrets to service | ansible.builtin.set_fact | True |
| Compose secrets ¦ Build standalone secret mounts | ansible.builtin.set_fact | True |
| Compose secrets ¦ Add standalone secret mounts to service | ansible.builtin.set_fact | True |

#### File: tasks/sub_tasks/compose/shm.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose shared memory ¦ Validate service name | ansible.builtin.assert | False |
| Compose shared memory ¦ Set size | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/stack_resources.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose stack resources ¦ Validate stack name | ansible.builtin.assert | False |
| Compose stack resources ¦ Validate resource settings | ansible.builtin.assert | False |
| Compose stack resources ¦ Add resources to stack | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/sysctls.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose sysctls ¦ Validate settings | ansible.builtin.assert | False |
| Compose sysctls ¦ Read sysctl values | ansible.builtin.set_fact | False |
| Compose sysctls ¦ Add sysctls to service | ansible.builtin.set_fact | True |

#### File: tasks/sub_tasks/compose/user.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose user ¦ Validate service name | ansible.builtin.assert | False |
| Compose user ¦ Set container user | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/compose/volumes.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Compose volumes ¦ Validate service name | ansible.builtin.assert | False |
| Compose volumes ¦ Read existing volumes | ansible.builtin.set_fact | False |
| Compose volumes ¦ Build final volume list | ansible.builtin.set_fact | False |
| Compose volumes ¦ Add volumes to service | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/deploy/all.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Deploy ¦ Load saved stack configurations | ansible.builtin.set_fact | False |  |
| Deploy ¦ Deploy each saved stack | ansible.builtin.include_tasks | True |  |

#### File: tasks/sub_tasks/deploy/stack.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Deploy stack ¦ Validate stack settings | ansible.builtin.assert | False |
| Deploy stack ¦ Choose deploy host | ansible.builtin.set_fact | False |
| Deploy stack ¦ Ensure stack directory exists | ansible.builtin.file | False |
| Deploy stack ¦ Render stack file | ansible.builtin.template | False |
| Deploy stack ¦ Deploy Swarm stack | community.docker.docker_stack | True |
| Deploy stack ¦ Deploy Compose project | community.docker.docker_compose_v2 | True |

#### File: tasks/sub_tasks/drift/image.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Image drift ¦ Set target label | ansible.builtin.set_fact | False |
| Image drift ¦ Check whether service has an image | ansible.builtin.set_fact | False |
| Image drift ¦ Skip service without an image | ansible.builtin.debug | True |
| Image drift ¦ Build comparison details | ansible.builtin.set_fact | True |
| Image drift ¦ Read live Swarm image | ansible.builtin.command | True |
| Image drift ¦ Prepare live Swarm image for comparison | ansible.builtin.set_fact | True |
| Image drift ¦ Build Compose lookup details | ansible.builtin.set_fact | True |
| Image drift ¦ Read live Compose image | ansible.builtin.shell | True |
| Image drift ¦ Prepare live Compose image for comparison | ansible.builtin.set_fact | True |
| Image drift ¦ Compare desired and live images | ansible.builtin.set_fact | True |
| Image drift ¦ Report missing service or container | ansible.builtin.debug | True |
| Image drift ¦ Report changed image | ansible.builtin.debug | True |
| Image drift ¦ Report current image | ansible.builtin.debug | True |
| Image drift ¦ Add result to summary | ansible.builtin.set_fact | True |

#### File: tasks/sub_tasks/drift/notify_email.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Image drift email ¦ Build message | ansible.builtin.set_fact | True |
| Image drift email ¦ Send notification | community.general.mail | True |

#### File: tasks/sub_tasks/init.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Initialize ¦ Accept legacy role variable names | ansible.builtin.set_fact | False |  |
| Initialize ¦ Validate service configuration input | ansible.builtin.assert | False |  |
| Initialize ¦ Load service configuration | ansible.builtin.set_fact | False |  |
| Initialize ¦ Validate shared service context | ansible.builtin.assert | False |  |
| Initialize ¦ Reset per-service state | ansible.builtin.set_fact | False |  |
| Initialize ¦ Load shared service context | ansible.builtin.set_fact | False |  |
| Initialize ¦ Validate Docker secret attachments | ansible.builtin.set_fact | False |  |
| Initialize ¦ Add resolved environment to service | ansible.builtin.set_fact | False |  |
| Initialize ¦ Decide whether service schema validation is needed | ansible.builtin.set_fact | False |  |
| Initialize ¦ Validate service schema | ansible.builtin.include_tasks | True |  |
| Initialize ¦ Set service name, deploy type, deploy host, and action | ansible.builtin.set_fact | False |  |
| Initialize ¦ Set stack name | ansible.builtin.set_fact | False |  |
| Initialize ¦ Choose deploy host | ansible.builtin.set_fact | False |  |
| Initialize ¦ Choose stack key | ansible.builtin.set_fact | False |  |
| Initialize ¦ Choose filesystem hosts | ansible.builtin.set_fact | False |  |
| Initialize ¦ Expand filesystem host group | ansible.builtin.set_fact | True |  |
| Initialize ¦ Remove duplicate filesystem hosts | ansible.builtin.set_fact | False |  |
| Initialize ¦ Validate filesystem hosts | ansible.builtin.assert | False |  |
| Initialize ¦ Reset container host defaults | ansible.builtin.set_fact | False |  |
| Initialize ¦ Build container host defaults | ansible.builtin.set_fact | False |  |
| Initialize ¦ Require one host for standalone Docker | ansible.builtin.assert | True |  |
| Initialize ¦ Check whether this host builds Compose | ansible.builtin.set_fact | False |  |

#### File: tasks/sub_tasks/prepare.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Prepare ¦ Build application context | ansible.builtin.set_fact | False |  |
| Prepare ¦ Validate application settings | ansible.builtin.include_role | False |  |
| Prepare ¦ Save application validation results | ansible.builtin.set_fact | False |  |
| Cleanup ¦ Read cleanup settings | ansible.builtin.set_fact | False |  |
| Cleanup ¦ Start cleaned-stack tracker | ansible.builtin.set_fact | True |  |
| Cleanup ¦ Decide whether cleanup is needed | ansible.builtin.set_fact | True |  |
| Cleanup ¦ Remove existing deployment | ansible.builtin.include_tasks | True |  |
| Cleanup ¦ Record cleaned stack | ansible.builtin.set_fact | True |  |
| Prepare ¦ Generate application secrets | ansible.builtin.include_role | True |  |
| Prepare ¦ Save generated application secrets | ansible.builtin.set_fact | True |  |
| Secrets ¦ Combine shared and generated secrets | ansible.builtin.set_fact | False |  |
| Secrets ¦ Validate service secret attachments | ansible.builtin.set_fact | False |  |
| Secrets ¦ Manage Docker secrets | ansible.builtin.include_tasks | True |  |
| Prepare ¦ Build application template values | ansible.builtin.include_role | True |  |
| Prepare ¦ Save application template values | ansible.builtin.set_fact | False |  |
| Prepare ¦ Prepare shared files and integrations | ansible.builtin.include_role | False |  |
| Prepare ¦ Render Swarm environment templates | ansible.builtin.include_role | True |  |
| Prepare ¦ Apply application configuration | ansible.builtin.include_role | True |  |
| Prepare ¦ Run Plex bootstrap | ansible.builtin.include_role | True |  |
| Swarm configs ¦ Manage service configs | ansible.builtin.include_tasks | True |  |

#### File: tasks/sub_tasks/save_stack.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Save stack ¦ Store completed Compose configuration | ansible.builtin.set_fact | True |

#### File: tasks/sub_tasks/secrets/manage.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Docker secrets ¦ Choose deploy host | ansible.builtin.set_fact | False |
| Docker secrets ¦ Choose secrets host | ansible.builtin.set_fact | False |
| Docker secrets ¦ Build requested secrets | ansible.builtin.set_fact | False |
| Docker secrets ¦ Reject empty secret values | ansible.builtin.assert | False |
| Docker secrets ¦ Inspect existing Swarm secrets | ansible.builtin.command | True |
| Docker secrets ¦ Read Swarm secret inspection results | ansible.builtin.set_fact | False |
| Docker secrets ¦ List existing Swarm secrets | ansible.builtin.set_fact | False |
| Docker secrets ¦ Protect unmanaged Swarm secrets | ansible.builtin.assert | True |
| Docker secrets ¦ Create required Swarm secrets | community.docker.docker_secret | True |
| Docker secrets ¦ Ensure standalone secrets directory exists | ansible.builtin.file | True |
| Docker secrets ¦ Inspect standalone secret paths | ansible.builtin.stat | True |
| Docker secrets ¦ Remove incompatible standalone secret paths | ansible.builtin.file | True |
| Docker secrets ¦ Report standalone secret path repair in check mode | ansible.builtin.debug | True |
| Docker secrets ¦ Write standalone secret files | ansible.builtin.copy | True |
| Docker secrets ¦ Enforce standalone secret permissions | ansible.builtin.file | True |
| Docker secrets ¦ Verify standalone secret files | ansible.builtin.stat | True |
| Docker secrets ¦ Require valid standalone secret files | ansible.builtin.assert | True |

#### File: tasks/sub_tasks/swarm_configs/create.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Swarm configs ¦ Render config content | ansible.builtin.set_fact | False |
| Swarm configs ¦ Build versioned config name | ansible.builtin.set_fact | False |
| Swarm configs ¦ Create versioned config | community.docker.docker_config | False |
| Swarm configs ¦ Record active config | ansible.builtin.set_fact | False |

#### File: tasks/sub_tasks/swarm_configs/manage.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Swarm configs ¦ Validate config list | ansible.builtin.assert | False |  |
| Swarm configs ¦ Reset config state | ansible.builtin.set_fact | False |  |
| Swarm configs ¦ Validate config settings | ansible.builtin.assert | False |  |
| Swarm configs ¦ Remove configs marked absent | ansible.builtin.include_tasks | True |  |
| Swarm configs ¦ Create configs marked present | ansible.builtin.include_tasks | True |  |

#### File: tasks/sub_tasks/swarm_configs/remove.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Swarm configs ¦ List existing configs | ansible.builtin.command | False |
| Swarm configs ¦ Find configs to remove | ansible.builtin.set_fact | False |
| Swarm configs ¦ Record removed config | ansible.builtin.set_fact | False |
| Swarm configs ¦ Remove matching configs | community.docker.docker_config | True |

#### File: tasks/sub_tasks/validate/service.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Validate service ¦ Require service configuration | ansible.builtin.assert | False |
| Validate service ¦ Check optional service name | ansible.builtin.assert | True |
| Validate service ¦ Require service image | ansible.builtin.assert | False |
| Validate service ¦ Check optional container user | ansible.builtin.assert | True |
| Validate service ¦ Check command type | ansible.builtin.assert | True |
| Validate service ¦ Check command string | ansible.builtin.assert | True |
| Validate service ¦ Check command list | ansible.builtin.assert | True |
| Validate service ¦ Check environment file type | ansible.builtin.assert | True |
| Validate service ¦ Check environment file string | ansible.builtin.assert | True |
| Validate service ¦ Check environment file list | ansible.builtin.assert | True |
| Validate service ¦ Check device list | ansible.builtin.assert | True |
| Validate service ¦ Check added capabilities | ansible.builtin.assert | True |
| Validate service ¦ Check dropped capabilities | ansible.builtin.assert | True |
| Validate service ¦ Check no-new-privileges setting | ansible.builtin.assert | True |
| Validate service ¦ Check sysctl settings | ansible.builtin.assert | True |
| Validate service ¦ Check deploy settings | ansible.builtin.assert | True |
| Validate service ¦ Check deploy type | ansible.builtin.assert | True |
| Validate service ¦ Check deploy profile | ansible.builtin.assert | True |
| Validate service ¦ Require Swarm for non-default deploy profiles | ansible.builtin.assert | True |
| Validate service ¦ Check Swarm deploy mode | ansible.builtin.assert | True |
| Validate service ¦ Check replica count | ansible.builtin.assert | True |
| Validate service ¦ Check deploy host | ansible.builtin.assert | True |
| Validate service ¦ Check placement constraints | ansible.builtin.assert | True |
| Validate service ¦ Check restart policy | ansible.builtin.assert | True |
| Validate service ¦ Check update settings | ansible.builtin.assert | True |
| Validate service ¦ Check rollback settings | ansible.builtin.assert | True |
| Validate service ¦ Check resource limits | ansible.builtin.assert | True |
| Validate service ¦ Check targets mapping | ansible.builtin.assert | True |
| Validate service ¦ Check target entries | ansible.builtin.assert | True |
| Validate service ¦ Check named networks | ansible.builtin.assert | True |
| Validate service ¦ Check named volumes | ansible.builtin.assert | True |
| Validate service ¦ Check path list | ansible.builtin.assert | True |
| Validate service ¦ Check path entries | ansible.builtin.assert | True |
| Validate service ¦ Check path permissions | ansible.builtin.assert | True |
| Validate service ¦ Check template list | ansible.builtin.assert | True |
| Validate service ¦ Check template entries | ansible.builtin.assert | True |
| Validate service ¦ Check template permissions | ansible.builtin.assert | True |
| Validate service ¦ Check copy list | ansible.builtin.assert | True |
| Validate service ¦ Check copy entries | ansible.builtin.assert | True |
| Validate service ¦ Check healthcheck | ansible.builtin.assert | True |
| Validate service ¦ Check secrets setting | ansible.builtin.assert | True |
| Validate service ¦ Check secret string | ansible.builtin.assert | True |
| Validate service ¦ Require non-empty secret list | ansible.builtin.assert | True |
| Validate service ¦ Check secret list entries | ansible.builtin.assert | True |
| Validate service ¦ Check secret names | ansible.builtin.assert | True |
| Validate service ¦ Check secret attachment fields | ansible.builtin.assert | True |
| Validate service ¦ Check ports setting | ansible.builtin.assert | True |
| Validate service ¦ Prepare port entries for validation | ansible.builtin.set_fact | True |
| Validate service ¦ Check port entries | ansible.builtin.assert | True |
| Validate service ¦ Check volumes setting | ansible.builtin.assert | True |
| Validate service ¦ Prepare volume entries for validation | ansible.builtin.set_fact | True |
| Validate service ¦ Check volume entries | ansible.builtin.assert | True |
| Validate service ¦ Check volume fields by type | ansible.builtin.assert | True |
| Validate service ¦ Check environment settings | ansible.builtin.assert | True |
| Validate service ¦ Check service labels | ansible.builtin.assert | True |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
