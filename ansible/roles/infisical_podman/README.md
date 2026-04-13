<!-- DOCSIBLE START -->

# 📃 Role overview

## infisical_podman





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/04/13 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [infisical_podman_name](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L3)   | str | `infisical` |    
| [infisical_podman_image](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L4)   | str | `infisical/infisical:v0.159.1` |    
| [infisical_podman_port](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L5)   | int | `8066` |    
| [infisical_podman_path](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L6)   | str | `/opt/{{ infisical_podman_name }}` |    
| [infisical_podman_enc_key](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L7)   | str |  |    
| [infisical_podman_jwt_key](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L8)   | str |  |    
| [timezone](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L10)   | str | `UTC` |    
| [puid](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L11)   | int | `1000` |    
| [pgid](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L12)   | int | `1000` |    
| [infisical_podman_network](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L14)   | str | `infisical` |    
| [infisical_podman_postgres_name](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L16)   | str | `infisical-postgres` |    
| [infisical_podman_postgres_image](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L17)   | str | `postgres:18.3` |    
| [infisical_podman_postgres_port](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L18)   | int | `5432` |    
| [infisical_podman_postgres_path](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L19)   | str | `{{ infisical_podman_path }}/postgres` |    
| [infisical_podman_postgres_user](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L20)   | str |  |    
| [infisical_podman_postgres_pass](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L21)   | str |  |    
| [infisical_podman_expose_postgres](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L22)   | bool | `False` |    
| [infisical_podman_redis_name](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L24)   | str | `infisical-redis` |    
| [infisical_podman_redis_image](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L25)   | str | `redis:8.6.2-alpine3.23` |    
| [infisical_podman_redis_port](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L26)   | int | `6390` |    
| [infisical_podman_redis_path](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L27)   | str | `{{ infisical_podman_path }}/redis` |    
| [infisical_podman_redis_key](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L28)   | str |  |    
| [infisical_podman_expose_redis](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L29)   | bool | `False` |    
| [infisical_podman_smtp_email](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L31)   | str |  |    
| [infisical_podman_smtp_host](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L32)   | str |  |    
| [infisical_podman_smtp_port](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L33)   | str |  |    
| [infisical_podman_smtp_user](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L34)   | str |  |    
| [infisical_podman_smtp_pass](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L35)   | str |  |    
| [infisical_podman_smtp_sender](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L36)   | str |  |    
| [infisical_podman_site_url](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L38)   | str | `http://localhost:8080` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Stop Infisical quadlet services | ansible.builtin.systemd_service | False | infisical_podman_recreate,infisical_podman_remove |
| Remove Infisical quadlet files | ansible.builtin.file | False | infisical_podman_recreate,infisical_podman_remove |
| Reload systemd after quadlet removal | ansible.builtin.systemd_service | False | infisical_podman_remove |
| Create Infisical quadlet directories | ansible.builtin.file | False | infisical_podman_bootstrap,infisical_podman_deploy,infisical_podman_recreate |
| Template Infisical Podman env file | ansible.builtin.template | False | infisical_podman_bootstrap,infisical_podman_deploy,infisical_podman_recreate |
| Template Infisical Podman quadlets | ansible.builtin.template | False | infisical_podman_deploy,infisical_podman_recreate |
| Reload systemd for quadlet generator | ansible.builtin.systemd_service | False | infisical_podman_deploy,infisical_podman_recreate |
| Start Infisical quadlet services | ansible.builtin.systemd_service | False | infisical_podman_deploy,infisical_podman_recreate |


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

  Start-->|Task| Stop_Infisical_quadlet_services0[stop infisical quadlet services]:::task
  Stop_Infisical_quadlet_services0-->|Task| Remove_Infisical_quadlet_files1[remove infisical quadlet files]:::task
  Remove_Infisical_quadlet_files1-->|Task| Reload_systemd_after_quadlet_removal2[reload systemd after quadlet removal]:::task
  Reload_systemd_after_quadlet_removal2-->|Task| Create_Infisical_quadlet_directories3[create infisical quadlet directories]:::task
  Create_Infisical_quadlet_directories3-->|Task| Template_Infisical_Podman_env_file4[template infisical podman env file]:::task
  Template_Infisical_Podman_env_file4-->|Task| Template_Infisical_Podman_quadlets5[template infisical podman quadlets]:::task
  Template_Infisical_Podman_quadlets5-->|Task| Reload_systemd_for_quadlet_generator6[reload systemd for quadlet generator]:::task
  Reload_systemd_for_quadlet_generator6-->|Task| Start_Infisical_quadlet_services7[start infisical quadlet services]:::task
  Start_Infisical_quadlet_services7-->End
```







#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
