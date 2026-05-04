<!-- DOCSIBLE START -->

# 📃 Role overview

## infisical





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/04/11 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [infisical_name](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L3)   | str | `infisical` |    
| [infisical_image](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L4)   | str | `docker.io/infisical/infisical:v0.159.22` |    
| [infisical_port](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L5)   | int | `8066` |    
| [infisical_path](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L6)   | str | `/opt/{{ infisical_name }}` |    
| [infisical_enc_key](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L7)   | str |  |    
| [infisical_jwt_key](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L8)   | str |  |    
| [infisical_postgres_name](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L10)   | str | `infisical-postgres` |    
| [infisical_postgres_image](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L11)   | str | `docker.io/library/postgres:18.3` |    
| [infisical_postgres_path](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L12)   | str | `{{ infisical_path }}/postgres` |    
| [infisical_postgres_user](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L13)   | str |  |    
| [infisical_postgres_pass](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L14)   | str |  |    
| [infisical_redis_name](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L16)   | str | `infisical-redis` |    
| [infisical_redis_image](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L17)   | str | `docker.io/library/redis:8.6-alpine` |    
| [infisical_redis_path](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L18)   | str | `{{ infisical_path }}/redis` |    
| [infisical_redis_key](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L19)   | str |  |    
| [infisical_smtp_email](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L21)   | str |  |    
| [infisical_smtp_host](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L22)   | str |  |    
| [infisical_smtp_port](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L23)   | str |  |    
| [infisical_smtp_user](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L24)   | str |  |    
| [infisical_smtp_pass](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L25)   | str |  |    
| [infisical_smtp_sender](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L26)   | str |  |    
| [infisical_secret_files](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L28)   | dict | `{}` |    
| [infisical_secret_files.postgres_user.**txt**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L29)   | str | `{{ infisical_postgres_user }}` |    
| [infisical_secret_files.postgres_pass.**txt**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L29)   | str | `{{ infisical_postgres_pass }}` |    
| [infisical_secret_files.redis_key.**txt**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L29)   | str | `{{ infisical_redis_key }}` |    
| [infisical_domain](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L33)   | str |  |    
| [infisical_backend_host](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L34)   | str | `{{ hostvars[docker_services_primary_manager].local_ip }}` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Check if compose file exists | ansible.builtin.stat | False | infisical_recreate,infisical_remove |
| Infisical compose down | community.docker.docker_compose_v2 | True | infisical_recreate,infisical_remove |
| Remove compose file | ansible.builtin.file | False | infisical_recreate,infisical_remove |
| Create directories | ansible.builtin.file | False | infisical_bootstrap,infisical_deploy,infisical_recreate |
| Template env file | ansible.builtin.template | False | infisical_bootstrap,infisical_deploy,infisical_recreate |
| Render Traefik dynamic file | ansible.builtin.template | False | infisical_deploy,infisical_recreate |
| Create Infisical secret files | ansible.builtin.copy | False | infisical_bootstrap,infisical_deploy,infisical_recreate |
| Import Infisical compose file | ansible.builtin.template | False | infisical_deploy,infisical_recreate |
| Infisical compose stack up | community.docker.docker_compose_v2 | False | infisical_deploy,infisical_recreate |


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

  Start-->|Task| Check_if_compose_file_exists0[check if compose file exists]:::task
  Check_if_compose_file_exists0-->|Task| Infisical_compose_down1[infisical compose down<br>When: **infisical existing compose yaml stat exists**]:::task
  Infisical_compose_down1-->|Task| Remove_compose_file2[remove compose file]:::task
  Remove_compose_file2-->|Task| Create_directories3[create directories]:::task
  Create_directories3-->|Task| Template_env_file4[template env file]:::task
  Template_env_file4-->|Task| Render_Traefik_dynamic_file5[render traefik dynamic file]:::task
  Render_Traefik_dynamic_file5-->|Task| Create_Infisical_secret_files6[create infisical secret files]:::task
  Create_Infisical_secret_files6-->|Task| Import_Infisical_compose_file7[import infisical compose file]:::task
  Import_Infisical_compose_file7-->|Task| Infisical_compose_stack_up8[infisical compose stack up]:::task
  Infisical_compose_stack_up8-->End
```







#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
