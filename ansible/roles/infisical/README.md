<!-- DOCSIBLE START -->

# 📃 Role overview

## infisical





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/07/21 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [infisical_enc_key](defaults/main.yml#L9)   | str |  |    
| [infisical_jwt_key](defaults/main.yml#L10)   | str |  |    
| [infisical_postgres_user](defaults/main.yml#L11)   | str |  |    
| [infisical_postgres_pass](defaults/main.yml#L12)   | str |  |    
| [infisical_redis_password](defaults/main.yml#L13)   | str |  |    
| [infisical_domain](defaults/main.yml#L14)   | str |  |    
| [infisical_smtp_email](defaults/main.yml#L15)   | str |  |    
| [infisical_smtp_user](defaults/main.yml#L16)   | str |  |    
| [infisical_smtp_pass](defaults/main.yml#L17)   | str |  |    
| [infisical_smtp_sender](defaults/main.yml#L18)   | str |  |    
| [infisical_redis_required_docker_secrets](defaults/main.yml#L20)   | dict | `{}` |    
| [infisical_redis_required_docker_secrets.**infisical_redis_password_secret**](defaults/main.yml#L21)   | str | `{{ infisical_redis_password }}` |    
| [infisical_redis_docker_secrets](defaults/main.yml#L23)   | str | `{{ infisical_redis_required_docker_secrets }}` |    
| [infisical_redis_secrets_files_path](defaults/main.yml#L25)   | str | `{{ infisical_base_path }}/secrets` |    
| [infisical_name](defaults/main.yml#L31)   | str | `infisical` |    
| [infisical_stack](defaults/main.yml#L32)   | str | `infisical` |    
| [infisical_compose_file](defaults/main.yml#L33)   | str | `infisical-compose.yml` |    
| [infisical_compose_path](defaults/main.yml#L34)   | str | `{{ infisical_base_path }}/{{ infisical_compose_file }}` |    
| [infisical_image](defaults/main.yml#L36)   | str | `docker.io/infisical/infisical:v0.162.6` |    
| [infisical_timezone](defaults/main.yml#L37)   | str | `{{ timezone ¦ default('Australia/Melbourne') }}` |    
| [infisical_puid](defaults/main.yml#L38)   | str | `{{ docker_host_puid ¦ default('1000') }}` |    
| [infisical_pgid](defaults/main.yml#L39)   | str | `{{ docker_host_pgid ¦ default('1000') }}` |    
| [infisical_port](defaults/main.yml#L40)   | int | `8066` |    
| [infisical_base_path](defaults/main.yml#L41)   | str | `{{ docker_host_appdata_root ¦ default('/opt') }}/infisical` |    
| [infisical_env_path](defaults/main.yml#L42)   | str | `{{ infisical_base_path }}/.env` |    
| [infisical_smtp_host](defaults/main.yml#L44)   | str | `smtp.porkbun.com` |    
| [infisical_smtp_port](defaults/main.yml#L45)   | int | `587` |    
| [infisical_frontend_fqdn](defaults/main.yml#L47)   | str | `{{ infisical_name }}.int.{{ infisical_domain }}` |    
| [infisical_frontend_address](defaults/main.yml#L48)   | str | `https://{{ infisical_frontend_fqdn }}:8443` |    
| [infisical_backend_address](defaults/main.yml#L49)   | str | `http://{{ infisical_name }}:8080` |    
| [infisical_docker_network](defaults/main.yml#L51)   | str | `overlay` |    
| [infisical_logging](defaults/main.yml#L53)   | dict | `{}` |    
| [infisical_logging.**driver**](defaults/main.yml#L54)   | str | `json-file` |    
| [infisical_logging.**options**](defaults/main.yml#L55)   | dict | `{}` |    
| [infisical_logging.options.**max-size**](defaults/main.yml#L56)   | str | `50m` |    
| [infisical_logging.options.**max-file**](defaults/main.yml#L57)   | str | `5` |    
| [infisical_logging.options.**compress**](defaults/main.yml#L58)   | str | `true` |    
| [infisical_restart_policy](defaults/main.yml#L60)   | str | `unless-stopped` |    
| [infisical_redis_name](defaults/main.yml#L66)   | str | `infisical-redis` |    
| [infisical_redis_image](defaults/main.yml#L67)   | str | `valkey/valkey:9.1-alpine` |    
| [infisical_redis_puid](defaults/main.yml#L68)   | str | `{{ docker_host_puid ¦ default('1000') }}` |    
| [infisical_redis_pgid](defaults/main.yml#L69)   | str | `{{ docker_host_pgid ¦ default('1000') }}` |    
| [infisical_redis_path](defaults/main.yml#L70)   | str | `{{ infisical_base_path }}/redis` |    
| [infisical_postgres_name](defaults/main.yml#L78)   | str | `haproxy` |    
| [infisical_postgres_port](defaults/main.yml#L79)   | int | `5432` |    
| [infisical_postgres_db_name](defaults/main.yml#L80)   | str | `infisical` |    
| [infisical_traefik_enable](defaults/main.yml#L86)   | bool | `True` |    
| [infisical_traefik_dynamic_dir](defaults/main.yml#L87)   | str | `/opt/traefik/dynamic` |    
| [infisical_traefik_entrypoint](defaults/main.yml#L88)   | str | `https_private` |    
| [infisical_traefik_authelia_enable](defaults/main.yml#L89)   | bool | `False` |    
| [infisical_traefik_crowdsec_enable](defaults/main.yml#L90)   | bool | `False` |    
| [infisical_traefik_headers_middleware](defaults/main.yml#L91)   | str | `secure-headers@file` |    
| [infisical_traefik_middleware_chain](defaults/main.yml#L92)   | str | `{{ infisical_name }}-ui-chain` |    
| [infisical_traefik_certresolver](defaults/main.yml#L93)   | str | `dns-cloudflare` |    
| [infisical_traefik_tls_options](defaults/main.yml#L94)   | str | `securetls@file` |    
| [infisical_traefik_dynamic_owner](defaults/main.yml#L95)   | int | `1000` |    
| [infisical_traefik_dynamic_group](defaults/main.yml#L96)   | int | `1000` |    





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
| Infisical ¦ Render Traefik dynamic file | ansible.builtin.template | True |  |
| Infisical ¦ Import compose file | ansible.builtin.template | False |  |
| Infisical ¦ Compose stack up | community.docker.docker_compose_v2 | False |  |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
