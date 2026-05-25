<!-- DOCSIBLE START -->

# 📃 Role overview

## docker_services





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/05/25 |














### Tasks


#### File: tasks/compose/00_init.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure docker_services_compose_stacks exists on mgt | ansible.builtin.set_fact | False |
| Load this stack's current docker_services_compose_services | ansible.builtin.set_fact | True |

#### File: tasks/compose/01_base/sub_tasks/service_base.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Normalize effective stack deploy type | ansible.builtin.set_fact | False |
| Set base service definition | ansible.builtin.set_fact | False |

#### File: tasks/compose/01_base/sub_tasks/stack_networks.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure docker_services_stack_name is provided | ansible.builtin.assert | False |
| Ensure stack_network_names is provided (list or mapping) | ansible.builtin.assert | False |
| Normalize stack networks input into a mapping | ansible.builtin.set_fact | False |
| Default external=true for any network defs that omit it | ansible.builtin.set_fact | True |
| Merge into docker_services_compose_stacks[docker_services_stack_name].networks (centralized on mgt) | ansible.builtin.set_fact | False |

#### File: tasks/compose/01_base/sub_tasks/stack_volumes.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure docker_services_stack_name is provided | ansible.builtin.assert | False |
| Ensure stack_volume_names is provided (list or mapping) | ansible.builtin.assert | False |
| Normalize stack volumes input into a mapping | ansible.builtin.set_fact | False |
| Default external=true for any volume defs that omit it | ansible.builtin.set_fact | True |
| Merge into docker_services_compose_stacks[docker_services_stack_name].volumes (centralized on mgt) | ansible.builtin.set_fact | False |

#### File: tasks/compose/01_base/tasker.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Register networks needed by this stack | ansible.builtin.include_tasks | True |
| Register external volumes needed by this stack | ansible.builtin.include_tasks | True |
| Normalize network_mode for container deploys (derive network_mode + is_container) | ansible.builtin.set_fact | True |
| Normalize network_mode for container deploys (derive has_network_mode) | ansible.builtin.set_fact | True |
| Build service networks list | ansible.builtin.set_fact | True |
| Set base service variables | ansible.builtin.include_tasks | True |

#### File: tasks/compose/02_runtime/sub_tasks/caps.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Ensure caps_target is valid | ansible.builtin.assert | False |
| Ensure caps_action is valid | ansible.builtin.assert | False |
| Normalize caps input | ansible.builtin.set_fact | False |
| Add caps for service (append/replace/append_unique) | ansible.builtin.set_fact | False |

#### File: tasks/compose/02_runtime/sub_tasks/command.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Ensure command_action is valid | ansible.builtin.assert | False |
| Select command input | ansible.builtin.set_fact | False |
| Fail if no command provided | ansible.builtin.fail | True |
| Normalize command list input | ansible.builtin.set_fact | True |
| Normalize command | ansible.builtin.set_fact | False |
| Read existing command | ansible.builtin.set_fact | False |
| Normalize existing/new command values for merge actions | ansible.builtin.set_fact | False |
| Compute final command | ansible.builtin.set_fact | False |
| Set command for service (append/replace/append_unique) | ansible.builtin.set_fact | False |

#### File: tasks/compose/02_runtime/sub_tasks/depends_on.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Ensure depends_on_action is valid | ansible.builtin.assert | False |
| Normalize depends_on input | ansible.builtin.set_fact | False |
| Attach depends_on to service | ansible.builtin.set_fact | False |

#### File: tasks/compose/02_runtime/sub_tasks/devices.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Ensure devices_action is valid | ansible.builtin.assert | False |
| Normalize devices input | ansible.builtin.set_fact | False |
| Add devices for service (append/replace/append_unique) | ansible.builtin.set_fact | False |

#### File: tasks/compose/02_runtime/sub_tasks/healthcheck.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Ensure health_test is provided | ansible.builtin.assert | False |
| Normalize healthcheck test into list form | ansible.builtin.set_fact | False |
| Attach healthcheck to service | ansible.builtin.set_fact | False |

#### File: tasks/compose/02_runtime/sub_tasks/security_opt.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Ensure security_opt_action is valid | ansible.builtin.assert | False |
| Normalize security_opt input | ansible.builtin.set_fact | False |
| Attach security_opt to service | ansible.builtin.set_fact | False |

#### File: tasks/compose/02_runtime/sub_tasks/sysctls.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Sysctls ¦ Validate input | ansible.builtin.assert | False |
| Sysctls ¦ Normalize sysctls dict (drop empty/omit, stringify values) | ansible.builtin.set_fact | False |
| Sysctls ¦ Attach sysctls to service | ansible.builtin.set_fact | True |

#### File: tasks/compose/02_runtime/sub_tasks/user.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Set user for service | ansible.builtin.set_fact | False |

#### File: tasks/compose/02_runtime/tasker.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Set security_opt | ansible.builtin.include_tasks | True |
| Set sysctls | ansible.builtin.include_tasks | True |
| Set depends_on | ansible.builtin.include_tasks | True |
| Add Linux capabilities (cap_add) | ansible.builtin.include_tasks | True |
| Drop Linux capabilities (cap_drop) | ansible.builtin.include_tasks | True |
| Add devices | ansible.builtin.include_tasks | True |
| Set command variable | ansible.builtin.include_tasks | True |
| Set healthcheck variable | ansible.builtin.include_tasks | True |
| Set user variable | ansible.builtin.include_tasks | True |

#### File: tasks/compose/03_io/sub_tasks/configs.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Configs ¦ Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Configs ¦ Ensure configs_list is a list | ansible.builtin.assert | False |
| Configs ¦ Resolve effective config sources | ansible.builtin.set_fact | False |
| Configs ¦ Attach configs to service (replace) | ansible.builtin.set_fact | False |

#### File: tasks/compose/03_io/sub_tasks/env.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Ensure environment_action is valid | ansible.builtin.assert | False |
| Normalize environment inputs | ansible.builtin.set_fact | False |
| Build final environment dict | ansible.builtin.set_fact | False |
| Attach environment to service | ansible.builtin.set_fact | False |

#### File: tasks/compose/03_io/sub_tasks/env_file.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Normalize env_file to list | ansible.builtin.set_fact | False |
| Attach env_file to service | ansible.builtin.set_fact | False |

#### File: tasks/compose/03_io/sub_tasks/ports.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Ensure ports_action is valid | ansible.builtin.assert | False |
| Normalize effective stack deploy type | ansible.builtin.set_fact | False |
| Build new port entries (ports/ports_list/legacy single) | ansible.builtin.set_fact | False |
| Validate new ports entries are dicts with required keys | ansible.builtin.assert | False |
| Reset working ports list (prevent cross-service bleed) | ansible.builtin.set_fact | False |
| Canonicalise new ports (types + defaults) | ansible.builtin.set_fact | False |
| Validate port protocols are tcp/udp | ansible.builtin.assert | False |
| Compute merged ports list | ansible.builtin.set_fact | False |
| Attach ports to service | ansible.builtin.set_fact | False |

#### File: tasks/compose/03_io/sub_tasks/secrets.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Ensure secrets is a list (accept string or list) | ansible.builtin.set_fact | False |
| Attach secrets list to service (swarm) | ansible.builtin.set_fact | True |
| Convert secrets to bind-mount volumes (compose) | ansible.builtin.set_fact | True |
| Attach secret mounts to service volumes (compose) | ansible.builtin.set_fact | True |

#### File: tasks/compose/03_io/sub_tasks/shm.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Set SHM size for service | ansible.builtin.set_fact | False |

#### File: tasks/compose/03_io/sub_tasks/tmpfs.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure tmpfs_action is valid | ansible.builtin.assert | False |
| Normalise tmpfs entries to list | ansible.builtin.set_fact | False |
| Merge tmpfs entries into compose services | ansible.builtin.set_fact | False |

#### File: tasks/compose/03_io/sub_tasks/volumes.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Ensure volumes_action is valid | ansible.builtin.assert | False |
| Build raw volume entries (mapping OR list OR legacy single) | ansible.builtin.set_fact | False |
| Validate raw volume entries are dicts | ansible.builtin.assert | False |
| Reset working volumes list (prevent cross-service bleed) | ansible.builtin.set_fact | False |
| Canonicalise new volume entries | ansible.builtin.set_fact | False |
| Validate canonical volume entries | ansible.builtin.assert | False |
| Capture existing volumes list | ansible.builtin.set_fact | False |
| Compute merged volumes list (append/replace/append_unique) | ansible.builtin.set_fact | False |
| Attach volumes to service | ansible.builtin.set_fact | False |

#### File: tasks/compose/03_io/tasker.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Set environment variables | ansible.builtin.include_tasks | True |
| Attach env_file to service | ansible.builtin.include_tasks | True |
| Set secrets variable (docker_services_svc format) | ansible.builtin.include_tasks | True |
| Set configs variable (swarm only) | ansible.builtin.include_tasks | True |
| Set ports variable | ansible.builtin.include_tasks | True |
| Set tmpfs variable | ansible.builtin.include_tasks | True |
| Set volumes variable | ansible.builtin.include_tasks | True |
| Add /dev/shm tmpfs for swarm | ansible.builtin.include_tasks | True |
| Set SHM size (compose only) | ansible.builtin.include_tasks | True |

#### File: tasks/compose/04_metadata/sub_tasks/labels.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Ensure labels_action is valid | ansible.builtin.assert | False |
| Ensure labels_precedence is valid | ansible.builtin.assert | False |
| Normalize labels input to mapping | ansible.builtin.set_fact | False |
| Build final labels dict | ansible.builtin.set_fact | False |
| Attach labels to service | ansible.builtin.set_fact | False |

#### File: tasks/compose/04_metadata/tasker.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Attach labels (service-level) | ansible.builtin.include_tasks | True |

#### File: tasks/deploy/sub_tasks/deploy_all.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| DeployAll ¦ Ensure docker_services_compose_stacks exists | ansible.builtin.set_fact | False |
| DeployAll ¦ Deploy each stack | ansible.builtin.include_tasks | True |

#### File: tasks/deploy/sub_tasks/deploy_config.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure docker_services_service_name is set | ansible.builtin.assert | False |
| Normalize deploy mode and capture raw replicas | ansible.builtin.set_fact | False |
| Validate deploy mode | ansible.builtin.assert | False |
| Validate deploy_replicas raw input | ansible.builtin.assert | True |
| Normalize deploy replicas | ansible.builtin.set_fact | False |
| Normalize deploy constraints into list | ansible.builtin.set_fact | False |
| Normalize optional deploy sub-dicts (treat omit as empty) | ansible.builtin.set_fact | False |
| Validate normalized deploy inputs | ansible.builtin.assert | False |
| Build deploy dict | ansible.builtin.set_fact | False |
| Attach deploy config to service | ansible.builtin.set_fact | False |

#### File: tasks/deploy/sub_tasks/deploy_one.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| DeployOne ¦ Validate inputs | ansible.builtin.assert | False |
| DeployOne ¦ Derive effective deploy host | ansible.builtin.set_fact | False |
| DeployOne ¦ Ensure /opt/stacks exists | ansible.builtin.file | False |
| DeployOne ¦ Render compose/stack file | ansible.builtin.template | False |
| DeployOne ¦ Swarm deploy | community.docker.docker_stack | True |
| DeployOne ¦ Compose deploy | community.docker.docker_compose_v2 | True |

#### File: tasks/deploy/tasker.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Set deploy config (swarm only, compose structure) | ansible.builtin.include_tasks | True |
| Persist compose into docker_services_compose_stacks[docker_services_stack_name_effective] (centralized queue) | ansible.builtin.set_fact | True |

#### File: tasks/init/sub_tasks/validate_svc.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Validate ¦ docker_services_svc is defined | ansible.builtin.assert | False |
| Validate ¦ docker_services_svc.name | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.image (required) | ansible.builtin.assert | False |
| Validate ¦ docker_services_svc.user | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.command shape | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.command string form | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.command list form | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.env_file shape | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.env_file string form | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.env_file list form | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.devices shape | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.cap_add shape | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.cap_drop shape | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.sysctls shape | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.deploy shape | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.deploy.type | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.deploy.mode | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.deploy.replicas | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.deploy.host (optional) | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.deploy.constraints | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.targets shape | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.targets entries are mappings | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.named_networks | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.named_volumes | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.paths shape | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.paths entries | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.paths mode formatting | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.templates shape | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.templates entries | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.templates mode formatting | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.copies shape | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.copies entries | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.infisical shape | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.infisical.secrets_map | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.infisical.secrets_map var names | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.infisical.secrets_map docker_secret names | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.postgres shape | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.postgres.databases | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.healthcheck shape | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.secrets shape | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.secrets string form | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.secrets list form is non-empty | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.secrets list items are strings or dicts | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.secrets string items are non-empty | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.secrets dict items have source and target | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.ports shape | ansible.builtin.assert | True |
| Validate ¦ Normalize ports items | ansible.builtin.set_fact | True |
| Validate ¦ docker_services_svc.ports entries | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.volumes shape | ansible.builtin.assert | True |
| Validate ¦ Normalize volume items | ansible.builtin.set_fact | True |
| Validate ¦ docker_services_svc.volumes entries basic | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.volumes required keys by type | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.environment shape | ansible.builtin.assert | True |
| Validate ¦ docker_services_svc.labels shape | ansible.builtin.assert | True |

#### File: tasks/init/tasker.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Normalize role interface vars (compat with old names) | ansible.builtin.set_fact | False |
| Ensure docker_services_service_cfg is provided | ansible.builtin.assert | False |
| Validate target exists when targets are defined | ansible.builtin.assert | False |
| Normalize service config (targets aware) | ansible.builtin.set_fact | False |
| Validate normalized service config | ansible.builtin.include_tasks | False |
| Derive common service context | ansible.builtin.set_fact | False |
| Derive stack name (multi-service per stack) | ansible.builtin.set_fact | False |
| Derive effective deploy host (swarm always on mgt) | ansible.builtin.set_fact | False |
| Derive effective stack key (avoid container host collisions) | ansible.builtin.set_fact | False |
| Derive effective filesystem hosts (dirs/templates/copies) | ansible.builtin.set_fact | False |
| Expand filesystem hosts if a group name was provided | ansible.builtin.set_fact | True |
| De-dupe filesystem hosts | ansible.builtin.set_fact | False |
| Assert container deploy has a single deploy.host | ansible.builtin.assert | True |
| Determine if this host should build/deploy compose artifacts | ansible.builtin.set_fact | False |

#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Init (validate + normalize) | ansible.builtin.include_tasks | False | deploy,update,remove,recreate,bootstrap |
| Prep ¦ cleanup tasks | ansible.builtin.include_tasks | False |  |
| Prep ¦ Pre-template tasks | ansible.builtin.include_tasks | False |  |
| Prep ¦ filesystem tasks | ansible.builtin.include_tasks | False |  |
| Prep ¦ Relevant services tasks | ansible.builtin.include_tasks | False |  |
| Compose ¦ Init tasks | ansible.builtin.include_tasks | False |  |
| Compose ¦ Service Base tasks | ansible.builtin.include_tasks | False |  |
| Compose ¦ Runtime tasks | ansible.builtin.include_tasks | False |  |
| Compose ¦ Input-Output tasks | ansible.builtin.include_tasks | False |  |
| Compose ¦ Metadata tasks | ansible.builtin.include_tasks | False |  |
| Run centralized deploy (once) | ansible.builtin.include_tasks | False | deploy,update,recreate |

#### File: tasks/prep/00_cleanup/sub_tasks/cleanup.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure docker_services_stack_name is set | ansible.builtin.assert | False |
| Cleanup container stack (compose) | block | True |
| Check if compose file exists | ansible.builtin.stat | False |
| Compose down | community.docker.docker_compose_v2 | True |
| Remove compose file | ansible.builtin.file | False |
| Remove container secret files directory (per-stack) | ansible.builtin.file | False |
| Remove stack directory if empty (optional) | ansible.builtin.file | False |
| Cleanup swarm stack | block | True |
| Stack down | community.docker.docker_stack | False |
| Remove stack file | ansible.builtin.file | False |

#### File: tasks/prep/00_cleanup/tasker.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Derive cleanup flags (stack-scoped) | ansible.builtin.set_fact | False | remove,recreate |
| Init cleaned-stacks tracker | ansible.builtin.set_fact | True | remove,recreate |
| Cleanup ¦ Determine if stack cleanup should run (once per stack) | ansible.builtin.set_fact | True |  |
| Remove existing stack (optional, once per stack) | ansible.builtin.include_tasks | True | remove,recreate |
| Mark stack as cleaned | ansible.builtin.set_fact | True | remove,recreate |

#### File: tasks/prep/01_pre_filesystem/sub_tasks/authelia/_keys.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Authelia keys ¦ Assert required inputs | ansible.builtin.assert | False |
| Authelia keys ¦ Resolve keys host (Swarm Manager) | ansible.builtin.set_fact | False |
| Authelia keys ¦ Determine if key already exists | ansible.builtin.set_fact | False |
| Authelia keys ¦ Determine if docker secret creation is enabled | ansible.builtin.set_fact | False |
| Authelia keys ¦ Ensure secret exists (provided key) | community.docker.docker_secret | True |
| Authelia keys ¦ Generate key (temporary container) | block | True |
| Authelia keys ¦ Run generator container | community.docker.docker_container | False |
| Authelia keys ¦ Extract generated value | ansible.builtin.shell | False |
| Authelia keys ¦ Mark generated this run | ansible.builtin.set_fact | False |
| Authelia keys ¦ Fail if generation produced empty output | ansible.builtin.assert | False |
| Authelia keys ¦ Save generated value as a mgt fact | ansible.builtin.set_fact | True |
| Authelia keys ¦ Ensure secret exists (generated key) | community.docker.docker_secret | True |

#### File: tasks/prep/01_pre_filesystem/sub_tasks/authelia/tasker.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Authelia prep ¦ Generate argon2 + secrets (once) | block | True |
| Authelia prep ¦ Generate argon2 digest (users_database) | ansible.builtin.include_tasks | False |
| Authelia prep ¦ Ensure session key secret | ansible.builtin.include_tasks | False |
| Authelia prep ¦ Ensure storage key secret | ansible.builtin.include_tasks | False |
| Authelia prep ¦ IMPORTANT ¦ Persist storage key in Infisical | ansible.builtin.debug | True |
| Authelia prep ¦ Ensure JWT reset key secret | ansible.builtin.include_tasks | False |

#### File: tasks/prep/01_pre_filesystem/sub_tasks/infisical/_fetch.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure secrets_map is defined | ansible.builtin.assert | False |
| Ensure infisical_lookup_default_params is defined | ansible.builtin.assert | False |
| Initialize dict output (optional) | ansible.builtin.set_fact | True |
| Fetch secrets from Infisical (flattened vars) | ansible.builtin.set_fact | True |
| Fail if any fetched secret is empty (flattened) | ansible.builtin.assert | True |
| Fetch secrets from Infisical (dict output) | ansible.builtin.set_fact | True |
| Fail if any fetched secret is empty (dict output) | ansible.builtin.assert | True |

#### File: tasks/prep/01_pre_filesystem/sub_tasks/infisical/_resolver.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| EnvResolve ¦ Determine fail-on-empty behavior | ansible.builtin.set_fact | True |
| EnvResolve ¦ Initialize resolved environment + placeholder key list | ansible.builtin.set_fact | True |
| EnvResolve ¦ Resolve placeholders into docker_services_env_resolved | ansible.builtin.set_fact | True |
| EnvResolve ¦ Replace docker_services_svc.environment with resolved values | ansible.builtin.set_fact | True |
| EnvResolve ¦ Fail if any placeholders remain (means resolver didn't run) | ansible.builtin.fail | True |
| EnvResolve ¦ Fail if any placeholder-resolved env key is empty | ansible.builtin.assert | True |

#### File: tasks/prep/01_pre_filesystem/sub_tasks/infisical/_secrets.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Secrets ¦ Reset working list (prevent cross-service bleed) | ansible.builtin.set_fact | False |
| Secrets ¦ Resolve deploy host | ansible.builtin.set_fact | False |
| Secrets ¦ Resolve effective secrets host (swarm -> mgt, else deploy host) | ansible.builtin.set_fact | False |
| Secrets ¦ Build desired secret items from secrets_map (opt-in via docker_secret) | ansible.builtin.set_fact | False |
| Secrets ¦ Dedupe by name (keep first), keep empties for visibility | ansible.builtin.set_fact | False |
| Secrets ¦ Warn about empty secret values (if any) | ansible.builtin.debug | True |
| Create Docker secrets (swarm) | community.docker.docker_secret | True |
| Ensure secrets directory exists on deploy host (compose/container) | ansible.builtin.file | True |
| Remove secret path if it exists but is a directory (compose/container pre-clean) | ansible.builtin.file | True |
| Write secret files on deploy host (compose/container) | ansible.builtin.copy | True |
| Verify secret paths exist and are files (compose/container) | ansible.builtin.stat | True |
| Fail if any secret path is not a file (compose/container) | ansible.builtin.assert | True |

#### File: tasks/prep/01_pre_filesystem/sub_tasks/infisical/tasker.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Prep ¦ Fetch Infisical secrets (docker_services_svc.infisical) | ansible.builtin.include_tasks | True |  |
| Prep ¦ Resolve Infisical placeholders in docker_services_svc.environment | ansible.builtin.include_tasks | True |  |
| Prep ¦ Propagate Infisical flattened vars to deploy host | ansible.builtin.set_fact | True |  |
| Prep ¦ Propagate Infisical dict to deploy host | ansible.builtin.set_fact | True |  |
| Prep ¦ Create docker secrets / files from Infisical secrets_map | ansible.builtin.include_tasks | True |  |

#### File: tasks/prep/01_pre_filesystem/sub_tasks/postgres.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Postgres ¦ Ensure creds exist (fetch from Infisical if missing) | block | True |
| Postgres ¦ Detect if creds are missing | ansible.builtin.set_fact | False |
| Postgres ¦ Fetch postgres_user/postgres_pass from Infisical (only if missing) | ansible.builtin.include_tasks | True |
| Postgres ¦ Assert creds are now present | ansible.builtin.assert | False |
| Prepare Postgres docker secret | community.docker.docker_secret | True |
| Normalize postgres database list from docker_services_svc schema | ansible.builtin.set_fact | True |
| Ping for existing database(s) | community.postgresql.postgresql_ping | True |
| Create postgres database(s) if missing | community.postgresql.postgresql_db | True |

#### File: tasks/prep/01_pre_filesystem/sub_tasks/qbittorrent.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Qbit prep ¦ Set derived vars | ansible.builtin.set_fact | False |
| Qbit prep ¦ Assert downloads-instance password is present | ansible.builtin.assert | True |
| Qbit prep ¦ Generate downloads-instance pass | qbittorrent_passwd | True |
| Qbit prep ¦ Assert seeds-instance password is present | ansible.builtin.assert | True |
| Qbit prep ¦ Generate seeds-instance pass | qbittorrent_passwd | True |

#### File: tasks/prep/01_pre_filesystem/sub_tasks/swarm_configs/_absent.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Swarm configs ¦ List existing swarm config names | ansible.builtin.command | False |
| Swarm configs ¦ Find matching configs for absent base name | ansible.builtin.set_fact | False |
| Swarm configs ¦ Record absent config base name | ansible.builtin.set_fact | False |
| Swarm configs ¦ Remove absent configs by base-name match | community.docker.docker_config | True |

#### File: tasks/prep/01_pre_filesystem/sub_tasks/swarm_configs/_present.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Swarm configs ¦ Render desired config content | ansible.builtin.set_fact | False |
| Swarm configs ¦ Hash rendered content | ansible.builtin.set_fact | False |
| Swarm configs ¦ Ensure versioned config exists | community.docker.docker_config | False |
| Swarm configs ¦ Store effective config mapping | ansible.builtin.set_fact | False |

#### File: tasks/prep/01_pre_filesystem/sub_tasks/swarm_configs/tasker.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Swarm configs ¦ Ensure swarm_configs is a list | ansible.builtin.assert | False |
| Swarm configs ¦ Resolve deploy host (swarm manager) | ansible.builtin.set_fact | False |
| Swarm configs ¦ Initialize effective config maps | ansible.builtin.set_fact | False |
| Swarm configs ¦ Validate each config spec | ansible.builtin.assert | False |
| Swarm configs ¦ Process absent configs | ansible.builtin.include_tasks | True |
| Swarm configs ¦ Process present configs | ansible.builtin.include_tasks | True |

#### File: tasks/prep/01_pre_filesystem/tasker.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Prep ¦ Infisical Secrets | ansible.builtin.include_tasks | False |  |
| Prep ¦ Swarm configs | ansible.builtin.include_tasks | True |  |
| Prep ¦ Authelia key material (argon2/session/jwt/storage) | ansible.builtin.include_tasks | True |  |
| Create Postgres database | ansible.builtin.include_tasks | True | deploy,update,recreate |
| Hash qBittorrent passwords | ansible.builtin.include_tasks | True | deploy,update,recreate |

#### File: tasks/prep/02_filesystem/sub_tasks/copies.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Copy files (role-relative src) | ansible.builtin.copy | False |
| Wait for copied files (optional) | ansible.builtin.wait_for | True |

#### File: tasks/prep/02_filesystem/sub_tasks/dynamic.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Cloudflare ¦ Detect if zone is missing | ansible.builtin.set_fact | False |
| Cloudflare ¦ Fetch cloudflare_zone from Infisical (only if missing) | ansible.builtin.include_tasks | True |
| Render Traefik dynamic file (on traefik host) | ansible.builtin.template | False |

#### File: tasks/prep/02_filesystem/sub_tasks/paths.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Validate each path spec | ansible.builtin.assert | False |
| Apply filesystem state on deploy host | ansible.builtin.file | False |

#### File: tasks/prep/02_filesystem/sub_tasks/templates.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Render templates on deploy host | ansible.builtin.template | False |

#### File: tasks/prep/02_filesystem/tasker.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Create filesystem paths (on filesystem hosts) | ansible.builtin.include_tasks | True | deploy,update,recreate |
| Copy static files (on filesystem hosts) | ansible.builtin.include_tasks | True | deploy,update,recreate |
| Render templates (on filesystem host) | ansible.builtin.include_tasks | True | deploy,update,recreate |
| Render swarm env templates (always on services manager) | ansible.builtin.include_tasks | True | deploy,update,recreate |
| Render traefik dynamic files | ansible.builtin.include_tasks | True | deploy,update,recreate |

#### File: tasks/prep/03_post_filesystem/sub_tasks/bazarr.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Bazarr prep ¦ Set derived vars | ansible.builtin.set_fact | False |
| Bazarr prep ¦ Set secret vars | ansible.builtin.set_fact | False |
| Bazarr prep ¦ Set postgres vars | ansible.builtin.set_fact | True |
| Bazarr prep ¦ Assert postgres inputs are complete | ansible.builtin.assert | True |
| Bazarr prep ¦ Ensure config dir exists | ansible.builtin.file | False |
| Bazarr prep ¦ Check config exists | ansible.builtin.stat | False |
| Bazarr prep ¦ Generate Bazarr config (temp container) | block | True |
| Bazarr prep ¦ Start temp container to generate config | community.docker.docker_container | False |
| Bazarr prep ¦ Wait for config.yaml to appear | ansible.builtin.wait_for | False |
| Bazarr prep ¦ Give Bazarr time to finish writing config | ansible.builtin.pause | False |
| Bazarr prep ¦ Configure api setting | yedit | False |
| Bazarr prep ¦ Configure misc settings | yedit | False |
| Bazarr prep ¦ Configure opensubtitlescom settings | yedit | False |
| Bazarr prep ¦ Configure radarr settings | yedit | False |
| Bazarr prep ¦ Configure sonarr settings | yedit | False |
| Bazarr prep ¦ Configure postgres settings | yedit | False |

#### File: tasks/prep/03_post_filesystem/sub_tasks/nzbhydra2.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| NZBHydra2 prep ¦ Set filesystem host | ansible.builtin.set_fact | False |
| NZBHydra2 prep ¦ Set derived vars | ansible.builtin.set_fact | False |
| NZBHydra2 prep ¦ Assert required secrets are present | ansible.builtin.assert | False |
| NZBHydra2 prep ¦ Assert altHUB secrets are complete when used | ansible.builtin.assert | False |
| NZBHydra2 prep ¦ Assert NZBGeek secrets are complete when used | ansible.builtin.assert | False |
| NZBHydra2 prep ¦ Assert Drunken Slug secrets are complete when used | ansible.builtin.assert | False |
| NZBHydra2 prep ¦ Ensure config dir exists | ansible.builtin.file | False |
| NZBHydra2 prep ¦ Check config exists | ansible.builtin.stat | False |
| NZBHydra2 prep ¦ Generate nzbhydra.yml (temp container) | block | True |
| NZBHydra2 prep ¦ Start temp container to generate config | community.docker.docker_container | False |
| NZBHydra2 prep ¦ Wait for config to appear | ansible.builtin.wait_for | False |
| NZBHydra2 prep ¦ Wait for config file size to stabilize | ansible.builtin.shell | False |
| NZBHydra2 prep ¦ Build config facts | ansible.builtin.set_fact | False |
| NZBHydra2 prep ¦ Set auth user | yedit | False |
| NZBHydra2 prep ¦ Set API key | yedit | False |
| NZBHydra2 prep ¦ Replace downloaders list | block | False |
| NZBHydra2 prep ¦ Remove existing downloaders | yedit | False |
| NZBHydra2 prep ¦ Write managed downloaders | yedit | False |
| NZBHydra2 prep ¦ Replace indexers list | block | False |
| NZBHydra2 prep ¦ Remove existing indexers | yedit | False |
| NZBHydra2 prep ¦ Write managed indexers | yedit | False |
| NZBHydra2 prep ¦ Ensure config file permissions are restricted | ansible.builtin.file | False |
| NZBHydra2 prep ¦ Slurp config | ansible.builtin.slurp | False |
| NZBHydra2 prep ¦ Parse config YAML | ansible.builtin.set_fact | False |
| NZBHydra2 prep ¦ Assert API key set | ansible.builtin.assert | False |
| NZBHydra2 prep ¦ Assert SABnzbd downloader is set | ansible.builtin.assert | False |
| NZBHydra2 prep ¦ Assert configured indexers were written | ansible.builtin.assert | False |

#### File: tasks/prep/03_post_filesystem/sub_tasks/plex/_claim.yml

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

#### File: tasks/prep/03_post_filesystem/sub_tasks/plex/_preferences.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Preferences ¦ Conduct preferences.xml tasks | block | False |
| Preferences ¦ Set derived vars | ansible.builtin.set_fact | False |
| Preferences ¦ Check if Preferences.xml exists | ansible.builtin.stat | False |
| Preferences ¦ Read Preferences.xml attributes | community.general.xml | True |
| Preferences ¦ Remove Preferences.xml if malformed | ansible.builtin.file | True |
| Preferences ¦ Derive flags from Preferences.xml | ansible.builtin.set_fact | True |
| Preferences ¦ Fix TranscoderTempDirectory | community.general.xml | True |

#### File: tasks/prep/03_post_filesystem/sub_tasks/plex/_token.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Token ¦ Set file ownership facts | ansible.builtin.set_fact | False |
| Token ¦ Check if plex.ini exists | ansible.builtin.stat | False |
| Token ¦ Set client identifier fact | block | True |
| Token ¦ Lookup client_identifier | ansible.builtin.set_fact | False |
| Token ¦ Generate new identifier | ansible.builtin.set_fact | True |
| Token ¦ Set token variable if previously saved | ansible.builtin.set_fact | True |
| Token ¦ Set docker_services_plex_no_token status | ansible.builtin.set_fact | False |
| Token ¦ Check if Token is valid | ansible.builtin.uri | True |
| Token ¦ Generate New Token | block | True |
| Token ¦ Generate PIN | ansible.builtin.uri | False |
| Token ¦ Login prompt | ansible.builtin.pause | False |
| Token ¦ Check PIN | ansible.builtin.uri | False |
| Token ¦ Set docker_services_plex_auth_token variable | ansible.builtin.set_fact | False |
| Token ¦ Check if new Token is valid | ansible.builtin.uri | False |
| Token ¦ Fail if new token is invalid | ansible.builtin.fail | True |
| Token ¦ Add Client Identifier to plex.ini | community.general.ini_file | False |
| Token ¦ Add Token to plex.ini | community.general.ini_file | False |
| Token ¦ Display Token | ansible.builtin.debug | False |

#### File: tasks/prep/03_post_filesystem/sub_tasks/plex/tasker.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Plex prep ¦ Set derived vars | ansible.builtin.set_fact | False |
| Plex prep ¦ Assert derived hosts are valid | ansible.builtin.assert | False |
| Plex prep ¦ Create media volume (NFS) | community.docker.docker_volume | False |
| Plex prep ¦ Include Plex token tasks | ansible.builtin.include_tasks | False |
| Plex prep ¦ Include Plex preferences.xml tasks | ansible.builtin.include_tasks | False |
| Plex prep ¦ Include Plex claim tasks | ansible.builtin.include_tasks | False |

#### File: tasks/prep/03_post_filesystem/sub_tasks/vaultwarden.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Vaultwarden prep ¦ Set derived vars | ansible.builtin.set_fact | False |
| Vaultwarden prep ¦ Ensure vaultwarden dir exists | ansible.builtin.file | False |
| Vaultwarden prep ¦ Check if admin token file exists | ansible.builtin.stat | False |
| Vaultwarden prep ¦ Read existing token | ansible.builtin.slurp | True |
| Vaultwarden prep ¦ Create new admin token | block | True |
| Vaultwarden prep ¦ Generate random password | ansible.builtin.command | False |
| Vaultwarden prep ¦ Save generated password | ansible.builtin.copy | False |
| Vaultwarden prep ¦ Generate random salt | ansible.builtin.command | False |
| Vaultwarden prep ¦ Generate Argon2 PHC string | ansible.builtin.command | False |
| Vaultwarden prep ¦ Save argon2 token | ansible.builtin.copy | False |
| Vaultwarden prep ¦ Set admin token fact | ansible.builtin.set_fact | False |
| Vaultwarden prep ¦ Assert token looks like PHC argon2 string | ansible.builtin.assert | False |
| Vaultwarden prep ¦ Ensure docker secret exists | community.docker.docker_secret | False |

#### File: tasks/prep/03_post_filesystem/tasker.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Prep ¦ Plex (claims/token/etc) | ansible.builtin.include_tasks | True |  |
| Prep ¦ Bazarr | ansible.builtin.include_tasks | True |  |
| Prep ¦ NZBHydra2 | ansible.builtin.include_tasks | True |  |
| Prep ¦ Vaultwarden | ansible.builtin.include_tasks | True |  |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
