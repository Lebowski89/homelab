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
| [infisical_enc_key](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L9)   | str |  |    
| [infisical_jwt_key](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L10)   | str |  |    
| [infisical_postgres_user](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L11)   | str |  |    
| [infisical_postgres_pass](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L12)   | str |  |    
| [infisical_redis_password](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L13)   | str |  |    
| [infisical_domain](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L14)   | str |  |    
| [infisical_smtp_email](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L15)   | str |  |    
| [infisical_smtp_user](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L16)   | str |  |    
| [infisical_smtp_pass](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L17)   | str |  |    
| [infisical_smtp_sender](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L18)   | str |  |    
| [infisical_redis_required_docker_secrets](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L20)   | dict | `{}` |    
| [infisical_redis_required_docker_secrets.**infisical_redis_password_secret**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L21)   | str | `{{ infisical_redis_password }}` |    
| [infisical_redis_docker_secrets](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L23)   | str | `{{ infisical_redis_required_docker_secrets }}` |    
| [infisical_redis_secrets_files_path](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L25)   | str | `{{ infisical_base_path }}/secrets` |    
| [infisical_name](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L31)   | str | `infisical` |    
| [infisical_stack](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L32)   | str | `infisical` |    
| [infisical_compose_file](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L33)   | str | `infisical-compose.yml` |    
| [infisical_compose_path](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L34)   | str | `{{ infisical_base_path }}/{{ infisical_compose_file }}` |    
| [infisical_image](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L36)   | str | `docker.io/infisical/infisical:v0.160.4` |    
| [infisical_timezone](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L37)   | str | `{{ timezone ¦ default('Australia/Melbourne') }}` |    
| [infisical_puid](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L38)   | str | `{{ docker_host_puid ¦ default('1000') }}` |    
| [infisical_pgid](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L39)   | str | `{{ docker_host_pgid ¦ default('1000') }}` |    
| [infisical_port](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L40)   | int | `8066` |    
| [infisical_base_path](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L41)   | str | `{{ docker_host_appdata_root ¦ default('/opt') }}/infisical` |    
| [infisical_env_path](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L42)   | str | `{{ infisical_base_path }}/.env` |    
| [infisical_smtp_host](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L44)   | str | `smtp.porkbun.com` |    
| [infisical_smtp_port](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L45)   | int | `587` |    
| [infisical_frontend_fqdn](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L47)   | str | `{{ infisical_name }}.int.{{ infisical_domain }}` |    
| [infisical_frontend_address](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L48)   | str | `https://{{ infisical_frontend_fqdn }}:8443` |    
| [infisical_backend_address](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L49)   | str | `http://{{ infisical_name }}:8080` |    
| [infisical_docker_network](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L51)   | str | `overlay` |    
| [infisical_logging](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L53)   | dict | `{}` |    
| [infisical_logging.**driver**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L54)   | str | `json-file` |    
| [infisical_logging.**options**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L55)   | dict | `{}` |    
| [infisical_logging.options.**max-size**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L56)   | str | `50m` |    
| [infisical_logging.options.**max-file**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L57)   | str | `5` |    
| [infisical_logging.options.**compress**](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L58)   | str | `true` |    
| [infisical_restart_policy](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L60)   | str | `unless-stopped` |    
| [infisical_redis_name](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L66)   | str | `infisical-redis` |    
| [infisical_redis_image](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L67)   | str | `docker.io/library/redis:8.6-alpine` |    
| [infisical_redis_puid](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L68)   | str | `{{ docker_host_puid ¦ default('1000') }}` |    
| [infisical_redis_pgid](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L69)   | str | `{{ docker_host_pgid ¦ default('1000') }}` |    
| [infisical_redis_path](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L70)   | str | `{{ infisical_base_path }}/redis` |    
| [infisical_postgres_name](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L78)   | str | `haproxy` |    
| [infisical_postgres_port](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L79)   | int | `5432` |    
| [infisical_postgres_db_name](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L80)   | str | `infisical` |    
| [infisical_traefik_enable](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L86)   | bool | `True` |    
| [infisical_traefik_dynamic_dir](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L87)   | str | `/opt/traefik/dynamic` |    
| [infisical_traefik_entrypoint](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L88)   | str | `https_private` |    
| [infisical_traefik_authelia_enable](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L89)   | bool | `False` |    
| [infisical_traefik_crowdsec_enable](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L90)   | bool | `False` |    
| [infisical_traefik_headers_middleware](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L91)   | str | `secure-headers@file` |    
| [infisical_traefik_middleware_chain](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L92)   | str | `{{ infisical_name }}-ui-chain` |    
| [infisical_traefik_certresolver](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L93)   | str | `dns-cloudflare` |    
| [infisical_traefik_tls_options](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L94)   | str | `securetls@file` |    
| [infisical_traefik_dynamic_owner](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L95)   | int | `1000` |    
| [infisical_traefik_dynamic_group](https://github.com/Lebowski89/homelab/blob/main/defaults/main.yml#L96)   | int | `1000` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Infisical ¦ Assert required non-secret values are defined | ansible.builtin.assert | False |  |
| Infisical ¦ Check if compose file exists | ansible.builtin.stat | False |  |
| Infisical ¦ Compose down | community.docker.docker_compose_v2 | True |  |
| Infisical ¦ Remove compose file | ansible.builtin.file | False |  |
| Infisical ¦ Create directories | ansible.builtin.file | False |  |
| Infisical ¦ Template env file | ansible.builtin.template | False |  |
| Infisical ¦ Assert Docker secrets values are defined | ansible.builtin.assert | False |  |
| Infisical ¦ Create Docker secrets directory | ansible.builtin.file | False |  |
| Infisical ¦ Create Docker secrets files | ansible.builtin.copy | False |  |
| Infisical ¦ Render Traefik dynamic file | ansible.builtin.template | False |  |
| Infisical ¦ Import compose file | ansible.builtin.template | False |  |
| Infisical ¦ Compose stack up | community.docker.docker_compose_v2 | False |  |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
