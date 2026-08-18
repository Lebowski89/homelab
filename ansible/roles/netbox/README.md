<!-- DOCSIBLE START -->

# 📃 Role overview

## netbox





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/08/19 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [netbox_superuser_email](defaults/main.yml#L9)   | str |  |    
| [netbox_superuser_password](defaults/main.yml#L10)   | str |  |    
| [netbox_postgres_user](defaults/main.yml#L11)   | str |  |    
| [netbox_postgres_pass](defaults/main.yml#L12)   | str |  |    
| [netbox_redis_password](defaults/main.yml#L13)   | str |  |    
| [netbox_domain](defaults/main.yml#L15)   | str |  |    
| [netbox_required_docker_secrets](defaults/main.yml#L17)   | dict | `{}` |    
| [netbox_required_docker_secrets.**netbox_superuser_email_secret**](defaults/main.yml#L18)   | str | `{{ netbox_superuser_email }}` |    
| [netbox_required_docker_secrets.**netbox_superuser_password_secret**](defaults/main.yml#L19)   | str | `{{ netbox_superuser_password }}` |    
| [netbox_required_docker_secrets.**netbox_db_user_secret**](defaults/main.yml#L20)   | str | `{{ netbox_postgres_user }}` |    
| [netbox_required_docker_secrets.**netbox_db_password_secret**](defaults/main.yml#L21)   | str | `{{ netbox_postgres_pass }}` |    
| [netbox_required_docker_secrets.**netbox_redis_password_secret**](defaults/main.yml#L22)   | str | `{{ netbox_redis_password }}` |    
| [netbox_docker_secrets](defaults/main.yml#L24)   | str | `{{ netbox_required_docker_secrets }}` |    
| [netbox_name](defaults/main.yml#L30)   | str | `netbox` |    
| [netbox_stack](defaults/main.yml#L31)   | str | `netbox` |    
| [netbox_compose_file](defaults/main.yml#L32)   | str | `netbox-compose.yml` |    
| [netbox_compose_path](defaults/main.yml#L33)   | str | `{{ netbox_base_path }}/{{ netbox_compose_file }}` |    
| [netbox_image](defaults/main.yml#L35)   | str | `lscr.io/linuxserver/netbox:v4.6.0-ls351` |    
| [netbox_timezone](defaults/main.yml#L36)   | str | `{{ timezone ¦ default('Australia/Melbourne') }}` |    
| [netbox_puid](defaults/main.yml#L37)   | str | `{{ container_host_puid ¦ default('1000') }}` |    
| [netbox_pgid](defaults/main.yml#L38)   | str | `{{ container_host_pgid ¦ default('1000') }}` |    
| [netbox_base_path](defaults/main.yml#L39)   | str | `{{ container_host_appdata_root ¦ default('/opt') }}/netbox` |    
| [netbox_frontend_fqdn](defaults/main.yml#L41)   | str | `{{ netbox_name }}.int.{{ netbox_domain }}` |    
| [netbox_frontend_address](defaults/main.yml#L42)   | str | `https://{{ netbox_frontend_fqdn }}:8443` |    
| [netbox_backend_address](defaults/main.yml#L43)   | str | `http://{{ netbox_name }}:8000` |    
| [netbox_swarm_node_hostname](defaults/main.yml#L45)   | str | `{{ inventory_hostname }}` |    
| [netbox_docker_network](defaults/main.yml#L46)   | str | `overlay` |    
| [netbox_logging](defaults/main.yml#L48)   | dict | `{}` |    
| [netbox_logging.**driver**](defaults/main.yml#L49)   | str | `json-file` |    
| [netbox_logging.**options**](defaults/main.yml#L50)   | dict | `{}` |    
| [netbox_logging.options.**max-size**](defaults/main.yml#L51)   | str | `50m` |    
| [netbox_logging.options.**max-file**](defaults/main.yml#L52)   | str | `5` |    
| [netbox_logging.options.**compress**](defaults/main.yml#L53)   | str | `true` |    
| [netbox_restart_policy](defaults/main.yml#L55)   | dict | `{}` |    
| [netbox_restart_policy.**condition**](defaults/main.yml#L56)   | str | `on-failure` |    
| [netbox_restart_policy.**delay**](defaults/main.yml#L57)   | str | `10s` |    
| [netbox_restart_policy.**max_attempts**](defaults/main.yml#L58)   | int | `5` |    
| [netbox_restart_policy.**window**](defaults/main.yml#L59)   | str | `2m` |    
| [netbox_redis_name](defaults/main.yml#L65)   | str | `netbox-redis` |    
| [netbox_redis_image](defaults/main.yml#L66)   | str | `valkey/valkey:9.1-alpine` |    
| [netbox_redis_puid](defaults/main.yml#L67)   | str | `{{ container_host_puid ¦ default('1000') }}` |    
| [netbox_redis_pgid](defaults/main.yml#L68)   | str | `{{ container_host_pgid ¦ default('1000') }}` |    
| [netbox_redis_path](defaults/main.yml#L69)   | str | `{{ netbox_base_path }}/redis` |    
| [netbox_postgres_name](defaults/main.yml#L75)   | str | `netbox-postgres` |    
| [netbox_postgres_image](defaults/main.yml#L76)   | str | `docker.io/library/postgres:18.4` |    
| [netbox_postgres_puid](defaults/main.yml#L77)   | str | `999` |    
| [netbox_postgres_pgid](defaults/main.yml#L78)   | str | `999` |    
| [netbox_postgres_path](defaults/main.yml#L79)   | str | `{{ netbox_base_path }}/postgres` |    
| [netbox_postgres_db_name](defaults/main.yml#L80)   | str | `netbox` |    
| [netbox_traefik_enable](defaults/main.yml#L86)   | bool | `True` |    
| [netbox_traefik_dynamic_dir](defaults/main.yml#L87)   | str | `/opt/traefik/dynamic` |    
| [netbox_traefik_entrypoint](defaults/main.yml#L88)   | str | `https_private` |    
| [netbox_traefik_authelia_enable](defaults/main.yml#L89)   | bool | `False` |    
| [netbox_traefik_crowdsec_enable](defaults/main.yml#L90)   | bool | `False` |    
| [netbox_traefik_headers_middleware](defaults/main.yml#L91)   | str | `netbox-headers@file` |    
| [netbox_traefik_middleware_chain](defaults/main.yml#L92)   | str | `{{ netbox_name }}-ui-chain` |    
| [netbox_traefik_certresolver](defaults/main.yml#L93)   | str | `dns-cloudflare` |    
| [netbox_traefik_tls_options](defaults/main.yml#L94)   | str | `securetls@file` |    
| [netbox_traefik_dynamic_owner](defaults/main.yml#L95)   | str | `1000` |    
| [netbox_traefik_dynamic_group](defaults/main.yml#L96)   | str | `1000` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| NetBox ¦ Assert required non-secret values are defined | ansible.builtin.assert | False |  |
| NetBox ¦ Remove stack | community.docker.docker_stack | False |  |
| NetBox ¦ Remove compose file | ansible.builtin.file | False |  |
| NetBox ¦ Create directories | ansible.builtin.file | False |  |
| NetBox ¦ Assert Docker secrets values are defined | ansible.builtin.assert | False |  |
| NetBox ¦ Ensure Docker Swarm secrets exist | community.docker.docker_secret | False |  |
| NetBox ¦ Render Traefik dynamic file | ansible.builtin.template | False |  |
| NetBox ¦ Render compose file | ansible.builtin.template | False |  |
| NetBox ¦ Deploy stack | community.docker.docker_stack | False |  |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
