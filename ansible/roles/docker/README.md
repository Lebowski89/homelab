<!-- DOCSIBLE START -->

# 📃 Role overview

## docker





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/04/11 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [docker_packages](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L3)   | list | `[]` |    
| [docker_packages.**0**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L4)   | str | `docker-ce` |    
| [docker_packages.**1**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L5)   | str | `docker-ce-cli` |    
| [docker_packages.**2**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L6)   | str | `containerd.io` |    
| [docker_packages.**3**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L7)   | str | `docker-buildx-plugin` |    
| [docker_packages.**4**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L8)   | str | `docker-compose-plugin` |    
| [docker_prereq_packages](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L10)   | list | `[]` |    
| [docker_prereq_packages.**0**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L11)   | str | `ca-certificates` |    
| [docker_prereq_packages.**1**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L12)   | str | `curl` |    
| [docker_apt_arch_map](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L14)   | dict | `{}` |    
| [docker_apt_arch_map.**x86_64**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L15)   | str | `amd64` |    
| [docker_apt_arch_map.**aarch64**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L16)   | str | `arm64` |    
| [docker_apt_arch](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L18)   | str | `{{ docker_apt_arch_map[ansible_architecture] ¦ default(ansible_architecture) }}` |    
| [docker_repo_url](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L20)   | str | `https://download.docker.com/linux/ubuntu` |    
| [docker_repo_channel](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L21)   | str | `stable` |    
| [docker_keyring_dir](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L22)   | str | `/etc/apt/keyrings` |    
| [docker_keyring_file](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L23)   | str | `/etc/apt/keyrings/docker.asc` |    
| [docker_repo_filename](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L24)   | str | `docker` |    
| [docker_install_compose_plugin](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L26)   | bool | `True` |    
| [docker_manage_user](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L27)   | bool | `False` |    
| [docker_user](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L28)   | str |  |    
| [docker_network](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L30)   | str | `overlay` |    
| [docker_network_driver](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L31)   | str | `overlay` |    
| [docker_network_subnet](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L32)   | str | `172.98.0.0/24` |    
| [docker_prune_threshold_percent](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L34)   | int | `80` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Install Docker | ansible.builtin.include_tasks | True | docker,docker_install |
| Configure Docker Swarm | ansible.builtin.include_tasks | True | docker,docker_swarm,docker_swarm_init,docker_swarm_join,docker_swarm_network,docker_swarm_labels |
| Docker Prune | ansible.builtin.include_tasks | False | docker_prune,docker_prune_dangling,docker_prune_unused,docker_prune_volumes |

#### File: tasks/sub_tasks/install.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Assert supported OS | ansible.builtin.assert | False |
| Ensure apt prerequisites are installed | ansible.builtin.apt | False |
| Ensure Docker keyring directory exists | ansible.builtin.file | False |
| Download Docker GPG key | ansible.builtin.get_url | False |
| Add Docker apt repository | ansible.builtin.apt_repository | False |
| Install Docker packages | ansible.builtin.apt | False |
| Ensure docker group exists | ansible.builtin.group | True |
| Add user to docker group | ansible.builtin.user | True |

#### File: tasks/sub_tasks/prune.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Docker prune ¦ Get root filesystem usage | ansible.builtin.command | False |  |
| Docker prune ¦ Parse root filesystem usage percent | ansible.builtin.set_fact | False |  |
| Docker prune ¦ End play when usage is below threshold | ansible.builtin.meta | True |  |
| Remove dangling Docker images | ansible.builtin.command | False | d,o,c,k,e,r,_,p,r,u,n,e,_,d,a,n,g,l,i,n,g |
| Remove unused Docker images | ansible.builtin.command | False | d,o,c,k,e,r,_,p,r,u,n,e,_,u,n,u,s,e,d |
| Remove unused Docker volumes | ansible.builtin.command | False | d,o,c,k,e,r,_,p,r,u,n,e,_,v,o,l,u,m,e,s |

#### File: tasks/sub_tasks/swarm.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Ensure this host is part of the swarm inventory | ansible.builtin.set_fact | False |  |
| End swarm tasks for non-swarm hosts | ansible.builtin.meta | True |  |
| Assert primary swarm manager is defined | ansible.builtin.assert | False |  |
| Assert local_ip is defined for swarm node | ansible.builtin.assert | False |  |
| Initialise swarm on primary manager | community.docker.docker_swarm | True | d,o,c,k,e,r,_,s,w,a,r,m,_,i,n,i,t |
| Get worker join token from primary manager | ansible.builtin.command | False | d,o,c,k,e,r,_,s,w,a,r,m,_,j,o,i,n |
| Get manager join token from primary manager | ansible.builtin.command | False | d,o,c,k,e,r,_,s,w,a,r,m,_,j,o,i,n |
| Store join tokens on primary manager hostvars | ansible.builtin.set_fact | False | d,o,c,k,e,r,_,s,w,a,r,m,_,j,o,i,n |
| Join additional managers to swarm | community.docker.docker_swarm | True | d,o,c,k,e,r,_,s,w,a,r,m,_,j,o,i,n |
| Join workers to swarm | community.docker.docker_swarm | True | d,o,c,k,e,r,_,s,w,a,r,m,_,j,o,i,n |
| Conduct overlay network tasks | block | False | d,o,c,k,e,r,_,s,w,a,r,m,_,n,e,t,w,o,r,k |
| Register overlay network | community.docker.docker_network_info | False |  |
| Create overlay network | community.docker.docker_network | True |  |
| Apply swarm node labels | community.docker.docker_node | True | d,o,c,k,e,r,_,s,w,a,r,m,_,l,a,b,e,l,s |


## Task Flow Graphs



### Graph for main.yml

```mermaid
flowchart TD
Start
classDef block stroke:#3498db,stroke-width:2px;
classDef task stroke:#4b76bb,stroke-width:2px;
classDef includeTasks stroke:#16a085,stroke-width:2px;
classDef importTasks stroke:#34495e,stroke-width:2px;
classDef includeRole stroke:#2980b9,stroke-width:2px;
classDef importRole stroke:#699ba7,stroke-width:2px;
classDef includeVars stroke:#8e44ad,stroke-width:2px;
classDef rescue stroke:#665352,stroke-width:2px;

  Start-->|Include task| Install_Docker_sub_tasks_install_yml_0[install docker<br>When: **inventory hostname in groups  docker install**<br>include_task: sub tasks install yml]:::includeTasks
  Install_Docker_sub_tasks_install_yml_0-->|Include task| Configure_Docker_Swarm_sub_tasks_swarm_yml_1[configure docker swarm<br>When: **inventory hostname in groups  swarm**<br>include_task: sub tasks swarm yml]:::includeTasks
  Configure_Docker_Swarm_sub_tasks_swarm_yml_1-->|Include task| Docker_Prune_sub_tasks_prune_yml_2[docker prune<br>include_task: sub tasks prune yml]:::includeTasks
  Docker_Prune_sub_tasks_prune_yml_2-->End
```


### Graph for sub_tasks/install.yml

```mermaid
flowchart TD
Start
classDef block stroke:#3498db,stroke-width:2px;
classDef task stroke:#4b76bb,stroke-width:2px;
classDef includeTasks stroke:#16a085,stroke-width:2px;
classDef importTasks stroke:#34495e,stroke-width:2px;
classDef includeRole stroke:#2980b9,stroke-width:2px;
classDef importRole stroke:#699ba7,stroke-width:2px;
classDef includeVars stroke:#8e44ad,stroke-width:2px;
classDef rescue stroke:#665352,stroke-width:2px;

  Start-->|Task| Assert_supported_OS0[assert supported os]:::task
  Assert_supported_OS0-->|Task| Ensure_apt_prerequisites_are_installed1[ensure apt prerequisites are installed]:::task
  Ensure_apt_prerequisites_are_installed1-->|Task| Ensure_Docker_keyring_directory_exists2[ensure docker keyring directory exists]:::task
  Ensure_Docker_keyring_directory_exists2-->|Task| Download_Docker_GPG_key3[download docker gpg key]:::task
  Download_Docker_GPG_key3-->|Task| Add_Docker_apt_repository4[add docker apt repository]:::task
  Add_Docker_apt_repository4-->|Task| Install_Docker_packages5[install docker packages]:::task
  Install_Docker_packages5-->|Task| Ensure_docker_group_exists6[ensure docker group exists<br>When: **docker manage user**]:::task
  Ensure_docker_group_exists6-->|Task| Add_user_to_docker_group7[add user to docker group<br>When: **docker manage user and docker user   length   0**]:::task
  Add_user_to_docker_group7-->End
```


### Graph for sub_tasks/prune.yml

```mermaid
flowchart TD
Start
classDef block stroke:#3498db,stroke-width:2px;
classDef task stroke:#4b76bb,stroke-width:2px;
classDef includeTasks stroke:#16a085,stroke-width:2px;
classDef importTasks stroke:#34495e,stroke-width:2px;
classDef includeRole stroke:#2980b9,stroke-width:2px;
classDef importRole stroke:#699ba7,stroke-width:2px;
classDef includeVars stroke:#8e44ad,stroke-width:2px;
classDef rescue stroke:#665352,stroke-width:2px;

  Start-->|Task| Docker_prune___Get_root_filesystem_usage0[docker prune   get root filesystem usage]:::task
  Docker_prune___Get_root_filesystem_usage0-->|Task| Docker_prune___Parse_root_filesystem_usage_percent1[docker prune   parse root filesystem usage percent]:::task
  Docker_prune___Parse_root_filesystem_usage_percent1-->|Task| Docker_prune___End_play_when_usage_is_below_threshold2[docker prune   end play when usage is below<br>threshold<br>When: **docker prune root usage percent    docker prune<br>threshold percent   int**]:::task
  Docker_prune___End_play_when_usage_is_below_threshold2-->|Task| Remove_dangling_Docker_images3[remove dangling docker images]:::task
  Remove_dangling_Docker_images3-->|Task| Remove_unused_Docker_images4[remove unused docker images]:::task
  Remove_unused_Docker_images4-->|Task| Remove_unused_Docker_volumes5[remove unused docker volumes]:::task
  Remove_unused_Docker_volumes5-->End
```


### Graph for sub_tasks/swarm.yml

```mermaid
flowchart TD
Start
classDef block stroke:#3498db,stroke-width:2px;
classDef task stroke:#4b76bb,stroke-width:2px;
classDef includeTasks stroke:#16a085,stroke-width:2px;
classDef importTasks stroke:#34495e,stroke-width:2px;
classDef includeRole stroke:#2980b9,stroke-width:2px;
classDef importRole stroke:#699ba7,stroke-width:2px;
classDef includeVars stroke:#8e44ad,stroke-width:2px;
classDef rescue stroke:#665352,stroke-width:2px;

  Start-->|Task| Ensure_this_host_is_part_of_the_swarm_inventory0[ensure this host is part of the swarm inventory]:::task
  Ensure_this_host_is_part_of_the_swarm_inventory0-->|Task| End_swarm_tasks_for_non_swarm_hosts1[end swarm tasks for non swarm hosts<br>When: **not docker swarm enabled   bool**]:::task
  End_swarm_tasks_for_non_swarm_hosts1-->|Task| Assert_primary_swarm_manager_is_defined2[assert primary swarm manager is defined]:::task
  Assert_primary_swarm_manager_is_defined2-->|Task| Assert_local_ip_is_defined_for_swarm_node3[assert local ip is defined for swarm node]:::task
  Assert_local_ip_is_defined_for_swarm_node3-->|Task| Initialise_swarm_on_primary_manager4[initialise swarm on primary manager<br>When: **inventory hostname    docker swarm primary manager**]:::task
  Initialise_swarm_on_primary_manager4-->|Task| Get_worker_join_token_from_primary_manager5[get worker join token from primary manager]:::task
  Get_worker_join_token_from_primary_manager5-->|Task| Get_manager_join_token_from_primary_manager6[get manager join token from primary manager]:::task
  Get_manager_join_token_from_primary_manager6-->|Task| Store_join_tokens_on_primary_manager_hostvars7[store join tokens on primary manager hostvars]:::task
  Store_join_tokens_on_primary_manager_hostvars7-->|Task| Join_additional_managers_to_swarm8[join additional managers to swarm<br>When: **inventory hostname in groups  swarm managers   and<br>inventory hostname    docker swarm primary manager**]:::task
  Join_additional_managers_to_swarm8-->|Task| Join_workers_to_swarm9[join workers to swarm<br>When: **inventory hostname in groups  swarm workers**]:::task
  Join_workers_to_swarm9-->|Block Start| Conduct_overlay_network_tasks10_block_start_0[[conduct overlay network tasks]]:::block
  Conduct_overlay_network_tasks10_block_start_0-->|Task| Register_overlay_network0[register overlay network]:::task
  Register_overlay_network0-->|Task| Create_overlay_network1[create overlay network<br>When: **not docker network result exists**]:::task
  Create_overlay_network1-.->|End of Block| Conduct_overlay_network_tasks10_block_start_0
  Create_overlay_network1-->|Task| Apply_swarm_node_labels11[apply swarm node labels<br>When: **inventory hostname in groups  swarm   and docker<br>swarm node labels is defined and docker swarm node<br>labels   length   0**]:::task
  Apply_swarm_node_labels11-->End
```







#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
