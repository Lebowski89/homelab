<!-- DOCSIBLE START -->

# 📃 Role overview

## netbox





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/05/25 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [netbox_superuser_email](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L9)   | str |  |    
| [netbox_superuser_password](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L10)   | str |  |    
| [netbox_postgres_user](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L11)   | str |  |    
| [netbox_postgres_pass](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L12)   | str |  |    
| [netbox_redis_password](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L13)   | str |  |    
| [netbox_domain](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L14)   | str |  |    
| [netbox_required_docker_secrets](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L16)   | dict | `{}` |    
| [netbox_required_docker_secrets.**netbox_superuser_email_secret**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L17)   | str | `{{ netbox_superuser_email }}` |    
| [netbox_required_docker_secrets.**netbox_superuser_password_secret**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L18)   | str | `{{ netbox_superuser_password }}` |    
| [netbox_required_docker_secrets.**netbox_db_user_secret**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L19)   | str | `{{ netbox_postgres_user }}` |    
| [netbox_required_docker_secrets.**netbox_db_password_secret**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L20)   | str | `{{ netbox_postgres_pass }}` |    
| [netbox_required_docker_secrets.**netbox_redis_password_secret**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L21)   | str | `{{ netbox_redis_password }}` |    
| [netbox_docker_secrets](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L23)   | str | `{{ netbox_required_docker_secrets }}` |    
| [netbox_name](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L29)   | str | `netbox` |    
| [netbox_stack](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L30)   | str | `netbox` |    
| [netbox_compose_file](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L31)   | str | `netbox-compose.yml` |    
| [netbox_compose_path](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L32)   | str | `{{ netbox_base_path }}/{{ netbox_compose_file }}` |    
| [netbox_image](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L34)   | str | `lscr.io/linuxserver/netbox:v4.6.0-ls351` |    
| [netbox_timezone](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L35)   | str | `{{ timezone ¦ default('Australia/Melbourne') }}` |    
| [netbox_puid](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L36)   | str | `{{ docker_host_puid ¦ default('1000') }}` |    
| [netbox_pgid](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L37)   | str | `{{ docker_host_pgid ¦ default('1000') }}` |    
| [netbox_base_path](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L38)   | str | `{{ docker_host_appdata_root ¦ default('/opt') }}/netbox` |    
| [netbox_frontend_fqdn](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L40)   | str | `{{ netbox_name }}.int.{{ netbox_domain }}` |    
| [netbox_frontend_address](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L41)   | str | `https://{{ netbox_frontend_fqdn }}:8443` |    
| [netbox_backend_address](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L42)   | str | `http://{{ netbox_name }}:8000` |    
| [netbox_swarm_node_hostname](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L44)   | str | `{{ inventory_hostname }}` |    
| [netbox_docker_network](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L45)   | str | `overlay` |    
| [netbox_logging](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L47)   | dict | `{}` |    
| [netbox_logging.**driver**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L48)   | str | `json-file` |    
| [netbox_logging.**options**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L49)   | dict | `{}` |    
| [netbox_logging.options.**max-size**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L50)   | str | `50m` |    
| [netbox_logging.options.**max-file**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L51)   | str | `5` |    
| [netbox_logging.options.**compress**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L52)   | str | `true` |    
| [netbox_restart_policy](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L54)   | dict | `{}` |    
| [netbox_restart_policy.**condition**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L55)   | str | `on-failure` |    
| [netbox_restart_policy.**delay**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L56)   | str | `10s` |    
| [netbox_restart_policy.**max_attempts**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L57)   | int | `5` |    
| [netbox_restart_policy.**window**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L58)   | str | `2m` |    
| [netbox_redis_name](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L64)   | str | `netbox-redis` |    
| [netbox_redis_image](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L65)   | str | `valkey/valkey:9.1-alpine` |    
| [netbox_redis_puid](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L66)   | str | `{{ docker_host_puid ¦ default('1000') }}` |    
| [netbox_redis_pgid](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L67)   | str | `{{ docker_host_pgid ¦ default('1000') }}` |    
| [netbox_redis_path](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L68)   | str | `{{ netbox_base_path }}/redis` |    
| [netbox_postgres_name](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L74)   | str | `netbox-postgres` |    
| [netbox_postgres_image](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L75)   | str | `docker.io/library/postgres:18.4` |    
| [netbox_postgres_puid](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L76)   | str | `999` |    
| [netbox_postgres_pgid](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L77)   | str | `999` |    
| [netbox_postgres_path](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L78)   | str | `{{ netbox_base_path }}/postgres` |    
| [netbox_postgres_db_name](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L79)   | str | `netbox` |    
| [netbox_traefik_enable](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L85)   | bool | `True` |    
| [netbox_traefik_dynamic_dir](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L86)   | str | `/opt/traefik/dynamic` |    
| [netbox_traefik_entrypoint](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L87)   | str | `https_private` |    
| [netbox_traefik_authelia_enable](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L88)   | bool | `False` |    
| [netbox_traefik_crowdsec_enable](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L89)   | bool | `False` |    
| [netbox_traefik_headers_middleware](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L90)   | str | `netbox-headers@file` |    
| [netbox_traefik_middleware_chain](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L91)   | str | `{{ netbox_name }}-ui-chain` |    
| [netbox_traefik_certresolver](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L92)   | str | `dns-cloudflare` |    
| [netbox_traefik_tls_options](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L93)   | str | `securetls@file` |    
| [netbox_traefik_dynamic_owner](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L94)   | str | `1000` |    
| [netbox_traefik_dynamic_group](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L95)   | str | `1000` |    





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
