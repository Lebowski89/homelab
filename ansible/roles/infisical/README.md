<!-- DOCSIBLE START -->

# 📃 Role overview

## infisical





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/10/23 |








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
| [infisical_smtp_email](defaults/main.yml#L14)   | str |  |    
| [infisical_smtp_user](defaults/main.yml#L15)   | str |  |    
| [infisical_smtp_pass](defaults/main.yml#L16)   | str |  |    
| [infisical_smtp_sender](defaults/main.yml#L17)   | str |  |    
| [infisical_redis_required_docker_secrets](defaults/main.yml#L19)   | dict | `{}` |    
| [infisical_redis_required_docker_secrets.**infisical_redis_password_secret**](defaults/main.yml#L20)   | str | `{{ infisical_redis_password }}` |    
| [infisical_redis_docker_secrets](defaults/main.yml#L22)   | str | `{{ infisical_redis_required_docker_secrets }}` |    
| [infisical_redis_secrets_files_path](defaults/main.yml#L24)   | str | `{{ infisical_base_path }}/secrets` |    
| [infisical_name](defaults/main.yml#L30)   | str | `infisical` |    
| [infisical_stack](defaults/main.yml#L31)   | str | `infisical` |    
| [infisical_compose_file](defaults/main.yml#L32)   | str | `infisical-compose.yml` |    
| [infisical_compose_path](defaults/main.yml#L33)   | str | `{{ infisical_base_path }}/{{ infisical_compose_file }}` |    
| [infisical_image](defaults/main.yml#L35)   | str | `docker.io/infisical/infisical:v0.166.8` |    
| [infisical_timezone](defaults/main.yml#L36)   | str | `{{ timezone ¦ default('Australia/Melbourne') }}` |    
| [infisical_puid](defaults/main.yml#L37)   | str | `{{ container_host_puid ¦ default('1000') }}` |    
| [infisical_pgid](defaults/main.yml#L38)   | str | `{{ container_host_pgid ¦ default('1000') }}` |    
| [infisical_port](defaults/main.yml#L39)   | int | `8066` |    
| [infisical_base_path](defaults/main.yml#L40)   | str | `{{ container_host_appdata_root ¦ default('/opt') }}/infisical` |    
| [infisical_env_path](defaults/main.yml#L41)   | str | `{{ infisical_base_path }}/.env` |    
| [infisical_smtp_host](defaults/main.yml#L43)   | str | `smtp.porkbun.com` |    
| [infisical_smtp_port](defaults/main.yml#L44)   | int | `587` |    
| [infisical_frontend_fqdn](defaults/main.yml#L46)   | str | `{{ infisical_name }}.{{ services_internal_zone }}` |    
| [infisical_frontend_address](defaults/main.yml#L47)   | str | `https://{{ infisical_frontend_fqdn }}:{{ services_private_https_port }}` |    
| [infisical_backend_address](defaults/main.yml#L48)   | str | `http://{{ local_ip }}:{{ infisical_port }}` |    
| [infisical_docker_network](defaults/main.yml#L50)   | str | `overlay` |    
| [infisical_logging](defaults/main.yml#L52)   | dict | `{}` |    
| [infisical_logging.**driver**](defaults/main.yml#L53)   | str | `json-file` |    
| [infisical_logging.**options**](defaults/main.yml#L54)   | dict | `{}` |    
| [infisical_logging.options.**max-size**](defaults/main.yml#L55)   | str | `50m` |    
| [infisical_logging.options.**max-file**](defaults/main.yml#L56)   | str | `5` |    
| [infisical_logging.options.**compress**](defaults/main.yml#L57)   | str | `true` |    
| [infisical_restart_policy](defaults/main.yml#L59)   | str | `unless-stopped` |    
| [infisical_redis_name](defaults/main.yml#L65)   | str | `infisical-redis` |    
| [infisical_redis_image](defaults/main.yml#L66)   | str | `docker.io/valkey/valkey:9.2-alpine` |    
| [infisical_redis_puid](defaults/main.yml#L67)   | str | `{{ container_host_puid ¦ default('1000') }}` |    
| [infisical_redis_pgid](defaults/main.yml#L68)   | str | `{{ container_host_pgid ¦ default('1000') }}` |    
| [infisical_redis_path](defaults/main.yml#L69)   | str | `{{ infisical_base_path }}/redis` |    
| [infisical_postgres_name](defaults/main.yml#L77)   | str | `haproxy` |    
| [infisical_postgres_port](defaults/main.yml#L78)   | int | `5432` |    
| [infisical_postgres_db_name](defaults/main.yml#L79)   | str | `infisical` |    
| [infisical_traefik_enable](defaults/main.yml#L85)   | bool | `True` |    
| [infisical_traefik_dynamic_dir](defaults/main.yml#L86)   | str | `/opt/traefik/dynamic` |    
| [infisical_traefik_entrypoint](defaults/main.yml#L87)   | str | `https_private` |    
| [infisical_traefik_authelia_enable](defaults/main.yml#L88)   | bool | `False` |    
| [infisical_traefik_headers_middleware](defaults/main.yml#L89)   | str | `secure-headers@file` |    
| [infisical_traefik_middleware_chain](defaults/main.yml#L90)   | str | `{{ infisical_name }}-ui-chain` |    
| [infisical_traefik_certresolver](defaults/main.yml#L91)   | str | `dns-cloudflare` |    
| [infisical_traefik_tls_options](defaults/main.yml#L92)   | str | `securetls@file` |    
| [infisical_traefik_dynamic_owner](defaults/main.yml#L93)   | int | `1000` |    
| [infisical_traefik_dynamic_group](defaults/main.yml#L94)   | int | `1000` |    
| [infisical_podman_services](defaults/main.yml#L97)   | list | `[]` |    
| [infisical_podman_services.**0**](defaults/main.yml#L98)   | dict | `{}` |    
| [infisical_podman_services.0.**name**](defaults/main.yml#L98)   | str | `{{ infisical_redis_name }}` |    
| [infisical_podman_services.0.**runtime**](defaults/main.yml#L99)   | str | `podman` |    
| [infisical_podman_services.0.**image**](defaults/main.yml#L100)   | str | `{{ infisical_redis_image }}` |    
| [infisical_podman_services.0.**user**](defaults/main.yml#L101)   | str | `0:0` |    
| [infisical_podman_services.0.**environment**](defaults/main.yml#L102)   | dict | `{}` |    
| [infisical_podman_services.0.environment.**TZ**](defaults/main.yml#L103)   | str | `{{ infisical_timezone }}` |    
| [infisical_podman_services.0.environment.**PUID**](defaults/main.yml#L104)   | str | `{{ infisical_redis_puid }}` |    
| [infisical_podman_services.0.environment.**PGID**](defaults/main.yml#L105)   | str | `{{ infisical_redis_pgid }}` |    
| [infisical_podman_services.0.environment.**REDIS_PASSWORD_FILE**](defaults/main.yml#L106)   | str | `/run/secrets/infisical_redis_password_secret` |    
| [infisical_podman_services.0.**secrets**](defaults/main.yml#L107)   | list | `[]` |    
| [infisical_podman_services.0.secrets.**0**](defaults/main.yml#L108)   | str | `infisical_redis_password_secret` |    
| [infisical_podman_services.0.**named_networks**](defaults/main.yml#L109)   | dict | `{}` |    
| [infisical_podman_services.0.named_networks.**infisical-redis**](defaults/main.yml#L110)   | dict | `{}` |    
| [infisical_podman_services.0.named_networks.infisical-redis.**driver**](defaults/main.yml#L111)   | str | `bridge` |    
| [infisical_podman_services.0.named_networks.infisical-redis.**external**](defaults/main.yml#L112)   | bool | `False` |    
| [infisical_podman_services.0.**ports**](defaults/main.yml#L113)   | dict | `{}` |    
| [infisical_podman_services.0.ports.**cache**](defaults/main.yml#L114)   | dict | `{}` |    
| [infisical_podman_services.0.ports.cache.**host_ip**](defaults/main.yml#L115)   | str | `{{ local_ip }}` |    
| [infisical_podman_services.0.ports.cache.**published**](defaults/main.yml#L116)   | str | `{{ infisical_redis_backend_port }}` |    
| [infisical_podman_services.0.ports.cache.**target**](defaults/main.yml#L117)   | int | `6379` |    
| [infisical_podman_services.0.ports.cache.**protocol**](defaults/main.yml#L118)   | str | `tcp` |    
| [infisical_podman_services.0.**paths**](defaults/main.yml#L119)   | list | `[]` |    
| [infisical_podman_services.0.paths.**0**](defaults/main.yml#L121)   | dict | `{}` |    
| [infisical_podman_services.0.paths.0.**path**](defaults/main.yml#L121)   | str | `{{ infisical_redis_path }}` |    
| [infisical_podman_services.0.paths.0.**state**](defaults/main.yml#L122)   | str | `directory` |    
| [infisical_podman_services.0.paths.0.**mode**](defaults/main.yml#L123)   | str | `0755` |    
| [infisical_podman_services.0.**volumes**](defaults/main.yml#L124)   | dict | `{}` |    
| [infisical_podman_services.0.volumes.**data**](defaults/main.yml#L125)   | dict | `{}` |    
| [infisical_podman_services.0.volumes.data.**type**](defaults/main.yml#L126)   | str | `bind` |    
| [infisical_podman_services.0.volumes.data.**source**](defaults/main.yml#L127)   | str | `{{ infisical_redis_path }}` |    
| [infisical_podman_services.0.volumes.data.**target**](defaults/main.yml#L128)   | str | `/data` |    
| [infisical_podman_services.0.volumes.data.**read_only**](defaults/main.yml#L129)   | bool | `False` |    
| [infisical_podman_services.0.**no_new_privileges**](defaults/main.yml#L130)   | bool | `False` |    
| [infisical_podman_services.0.**operational_requirements**](defaults/main.yml#L131)   | dict | `{}` |    
| [infisical_podman_services.0.operational_requirements.**acl**](defaults/main.yml#L132)   | list | `[]` |    
| [infisical_podman_services.0.operational_requirements.acl.**0**](defaults/main.yml#L132)   | str | `bootstrap` |    
| [infisical_podman_services.0.operational_requirements.**ownership_transition**](defaults/main.yml#L133)   | bool | `True` |    
| [infisical_podman_services.0.**deploy**](defaults/main.yml#L134)   | dict | `{}` |    
| [infisical_podman_services.0.deploy.**type**](defaults/main.yml#L135)   | str | `container` |    
| [infisical_podman_services.0.deploy.**host**](defaults/main.yml#L136)   | str | `{{ inventory_hostname }}` |    
| [infisical_podman_services.0.deploy.**execution**](defaults/main.yml#L137)   | dict | `{}` |    
| [infisical_podman_services.0.deploy.execution.**mode**](defaults/main.yml#L138)   | str | `rootless` |    
| [infisical_podman_services.0.deploy.execution.**host_user**](defaults/main.yml#L139)   | str | `podman-infisical-redis` |    
| [infisical_podman_services.0.deploy.execution.**userns**](defaults/main.yml#L140)   | dict | `{}` |    
| [infisical_podman_services.0.deploy.execution.userns.**mode**](defaults/main.yml#L141)   | str | `keep-id` |    
| [infisical_podman_services.0.deploy.execution.userns.**uid**](defaults/main.yml#L142)   | str | `0` |    
| [infisical_podman_services.0.deploy.execution.userns.**gid**](defaults/main.yml#L143)   | str | `0` |    
| [infisical_podman_services.0.**systemd**](defaults/main.yml#L144)   | dict | `{}` |    
| [infisical_podman_services.0.systemd.**restart**](defaults/main.yml#L145)   | str | `always` |    
| [infisical_podman_services.0.systemd.**restart_sec**](defaults/main.yml#L146)   | str | `15s` |    
| [infisical_podman_services.0.systemd.**timeout_start_sec**](defaults/main.yml#L147)   | str | `600s` |    
| [infisical_podman_services.0.systemd.**after**](defaults/main.yml#L148)   | list | `[]` |    
| [infisical_podman_services.0.systemd.after.**0**](defaults/main.yml#L149)   | str | `network-online.target` |    
| [infisical_podman_services.0.**command**](defaults/main.yml#L150)   | list | `[]` |    
| [infisical_podman_services.0.command.**0**](defaults/main.yml#L151)   | str | `sh` |    
| [infisical_podman_services.0.command.**1**](defaults/main.yml#L152)   | str | `-c` |    
| [infisical_podman_services.0.command.**2**](defaults/main.yml#L152)   | str | `umask 077; printf 'requirepass "%s"\n' "$(sed 's/[\\"]/\\&/g' /run/secrets/infisical_redis_password_secret)" > /tmp/skynet-valkey.conf; exec valkey-server /tmp/skynet-valkey.conf` |    
| [infisical_podman_services.0.**healthcheck**](defaults/main.yml#L157)   | dict | `{}` |    
| [infisical_podman_services.0.healthcheck.**test**](defaults/main.yml#L158)   | list | `[]` |    
| [infisical_podman_services.0.healthcheck.test.**0**](defaults/main.yml#L159)   | str | `CMD-SHELL` |    
| [infisical_podman_services.0.healthcheck.test.**1**](defaults/main.yml#L160)   | str | `REDISCLI_AUTH="$(cat /run/secrets/infisical_redis_password_secret)" valkey-cli ping ¦ grep -q PONG` |    
| [infisical_podman_services.0.healthcheck.**interval**](defaults/main.yml#L161)   | str | `10s` |    
| [infisical_podman_services.0.healthcheck.**timeout**](defaults/main.yml#L162)   | str | `5s` |    
| [infisical_podman_services.0.healthcheck.**retries**](defaults/main.yml#L163)   | int | `5` |    
| [infisical_podman_services.0.healthcheck.**start_period**](defaults/main.yml#L164)   | str | `30s` |    
| [infisical_podman_services.0.**notify_healthy**](defaults/main.yml#L165)   | bool | `True` |    
| [infisical_podman_services.0.**tmpfs**](defaults/main.yml#L166)   | list | `[]` |    
| [infisical_podman_services.0.tmpfs.**0**](defaults/main.yml#L167)   | str | `/tmp:mode=1777` |    
| [infisical_podman_services.**1**](defaults/main.yml#L168)   | dict | `{}` |    
| [infisical_podman_services.1.**name**](defaults/main.yml#L168)   | str | `{{ infisical_name }}` |    
| [infisical_podman_services.1.**runtime**](defaults/main.yml#L169)   | str | `podman` |    
| [infisical_podman_services.1.**image**](defaults/main.yml#L170)   | str | `{{ infisical_image }}` |    
| [infisical_podman_services.1.**user**](defaults/main.yml#L171)   | str | `1001:1001` |    
| [infisical_podman_services.1.**environment**](defaults/main.yml#L172)   | dict | `{}` |    
| [infisical_podman_services.1.environment.**TZ**](defaults/main.yml#L173)   | str | `{{ infisical_timezone }}` |    
| [infisical_podman_services.1.environment.**PUID**](defaults/main.yml#L174)   | str | `{{ infisical_puid }}` |    
| [infisical_podman_services.1.environment.**PGID**](defaults/main.yml#L175)   | str | `{{ infisical_pgid }}` |    
| [infisical_podman_services.1.environment.**NODE_ENV**](defaults/main.yml#L176)   | str | `production` |    
| [infisical_podman_services.1.environment.**ENCRYPTION_KEY**](defaults/main.yml#L177)   | str | `{{ infisical_enc_key }}` |    
| [infisical_podman_services.1.environment.**AUTH_SECRET**](defaults/main.yml#L178)   | str | `{{ infisical_jwt_key }}` |    
| [infisical_podman_services.1.environment.**DB_CONNECTION_URI**](defaults/main.yml#L179)   | str | `<multiline value: folded_strip>` |    
| [infisical_podman_services.1.environment.**REDIS_URL**](defaults/main.yml#L182)   | str | `redis://:{{ infisical_redis_password ¦ urlencode }}@{{ local_ip }}:{{ infisical_redis_backend_port }}` |    
| [infisical_podman_services.1.environment.**SITE_URL**](defaults/main.yml#L183)   | str | `{{ infisical_frontend_address }}` |    
| [infisical_podman_services.1.environment.**SMTP_HOST**](defaults/main.yml#L184)   | str | `{{ infisical_smtp_host }}` |    
| [infisical_podman_services.1.environment.**SMTP_PORT**](defaults/main.yml#L185)   | str | `{{ infisical_smtp_port }}` |    
| [infisical_podman_services.1.environment.**SMTP_FROM_ADDRESS**](defaults/main.yml#L186)   | str | `{{ infisical_smtp_email }}` |    
| [infisical_podman_services.1.environment.**SMTP_FROM_NAME**](defaults/main.yml#L187)   | str | `{{ infisical_smtp_sender }}` |    
| [infisical_podman_services.1.environment.**SMTP_USERNAME**](defaults/main.yml#L188)   | str | `{{ infisical_smtp_user }}` |    
| [infisical_podman_services.1.environment.**SMTP_PASSWORD**](defaults/main.yml#L189)   | str | `{{ infisical_smtp_pass }}` |    
| [infisical_podman_services.1.**secrets**](defaults/main.yml#L190)   | list | `[]` |    
| [infisical_podman_services.1.**named_networks**](defaults/main.yml#L191)   | dict | `{}` |    
| [infisical_podman_services.1.named_networks.**infisical**](defaults/main.yml#L192)   | dict | `{}` |    
| [infisical_podman_services.1.named_networks.infisical.**driver**](defaults/main.yml#L193)   | str | `bridge` |    
| [infisical_podman_services.1.named_networks.infisical.**external**](defaults/main.yml#L194)   | bool | `False` |    
| [infisical_podman_services.1.**paths**](defaults/main.yml#L195)   | list | `[]` |    
| [infisical_podman_services.1.**volumes**](defaults/main.yml#L196)   | dict | `{}` |    
| [infisical_podman_services.1.**no_new_privileges**](defaults/main.yml#L197)   | bool | `False` |    
| [infisical_podman_services.1.**operational_requirements**](defaults/main.yml#L198)   | dict | `{}` |    
| [infisical_podman_services.1.operational_requirements.**acl**](defaults/main.yml#L199)   | list | `[]` |    
| [infisical_podman_services.1.operational_requirements.acl.**0**](defaults/main.yml#L199)   | str | `bootstrap` |    
| [infisical_podman_services.1.**deploy**](defaults/main.yml#L200)   | dict | `{}` |    
| [infisical_podman_services.1.deploy.**type**](defaults/main.yml#L201)   | str | `container` |    
| [infisical_podman_services.1.deploy.**host**](defaults/main.yml#L202)   | str | `{{ inventory_hostname }}` |    
| [infisical_podman_services.1.deploy.**execution**](defaults/main.yml#L203)   | dict | `{}` |    
| [infisical_podman_services.1.deploy.execution.**mode**](defaults/main.yml#L204)   | str | `rootless` |    
| [infisical_podman_services.1.deploy.execution.**host_user**](defaults/main.yml#L205)   | str | `podman-infisical` |    
| [infisical_podman_services.1.deploy.execution.**userns**](defaults/main.yml#L206)   | dict | `{}` |    
| [infisical_podman_services.1.deploy.execution.userns.**mode**](defaults/main.yml#L207)   | str | `keep-id` |    
| [infisical_podman_services.1.deploy.execution.userns.**uid**](defaults/main.yml#L208)   | str | `1001` |    
| [infisical_podman_services.1.deploy.execution.userns.**gid**](defaults/main.yml#L209)   | str | `1001` |    
| [infisical_podman_services.1.**systemd**](defaults/main.yml#L210)   | dict | `{}` |    
| [infisical_podman_services.1.systemd.**restart**](defaults/main.yml#L211)   | str | `always` |    
| [infisical_podman_services.1.systemd.**restart_sec**](defaults/main.yml#L212)   | str | `15s` |    
| [infisical_podman_services.1.systemd.**timeout_start_sec**](defaults/main.yml#L213)   | str | `600s` |    
| [infisical_podman_services.1.systemd.**after**](defaults/main.yml#L214)   | list | `[]` |    
| [infisical_podman_services.1.systemd.after.**0**](defaults/main.yml#L215)   | str | `network-online.target` |    
| [infisical_podman_services.1.**healthcheck**](defaults/main.yml#L216)   | dict | `{}` |    
| [infisical_podman_services.1.healthcheck.**test**](defaults/main.yml#L217)   | list | `[]` |    
| [infisical_podman_services.1.healthcheck.test.**0**](defaults/main.yml#L218)   | str | `CMD-SHELL` |    
| [infisical_podman_services.1.healthcheck.test.**1**](defaults/main.yml#L219)   | str | `node -e "fetch('http://127.0.0.1:8080/api/status').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"` |    
| [infisical_podman_services.1.healthcheck.**interval**](defaults/main.yml#L220)   | str | `10s` |    
| [infisical_podman_services.1.healthcheck.**timeout**](defaults/main.yml#L221)   | str | `5s` |    
| [infisical_podman_services.1.healthcheck.**retries**](defaults/main.yml#L222)   | int | `5` |    
| [infisical_podman_services.1.healthcheck.**start_period**](defaults/main.yml#L223)   | str | `30s` |    
| [infisical_podman_services.1.**notify_healthy**](defaults/main.yml#L224)   | bool | `True` |    
| [infisical_podman_services.1.**ports**](defaults/main.yml#L225)   | dict | `{}` |    
| [infisical_podman_services.1.ports.**lookup**](defaults/main.yml#L226)   | dict | `{}` |    
| [infisical_podman_services.1.ports.lookup.**host_ip**](defaults/main.yml#L227)   | str | `{{ local_ip }}` |    
| [infisical_podman_services.1.ports.lookup.**published**](defaults/main.yml#L228)   | str | `{{ infisical_port }}` |    
| [infisical_podman_services.1.ports.lookup.**target**](defaults/main.yml#L229)   | int | `8080` |    
| [infisical_podman_secret_targets](defaults/main.yml#L230)   | dict | `{}` |    
| [infisical_redis_backend_port](defaults/main.yml#L231)   | int | `16381` |    
| [infisical_postgres_host](defaults/main.yml#L232)   | str | `{{ local_ip }}` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Infisical ¦ Validate bootstrap inputs | ansible.builtin.assert | False |  |
| Infisical ¦ Select explicit bootstrap operation | ansible.builtin.set_fact | False |  |
| Infisical ¦ Validate required Vault inputs before mutation | ansible.builtin.assert | True |  |
| Infisical ¦ Validate all Quadlet definitions before mutation | ansible.builtin.include_role | False |  |
| Infisical ¦ Reset this operation's bootstrap prerequisite proofs | ansible.builtin.set_fact | False |  |
| Infisical ¦ Enforce every bootstrap requirement before stopping or preparing services | ansible.builtin.include_tasks | False |  |
| Infisical ¦ Stop consumers before providers in their persisted managers | ansible.builtin.include_role | True |  |
| Infisical ¦ Process bootstrap providers and consumers | ansible.builtin.include_tasks | False |  |
| Infisical ¦ Render Traefik dynamic file | ansible.builtin.template | True |  |
| Infisical ¦ Retire Traefik route | ansible.builtin.file | True |  |

#### File: tasks/requirements.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Infisical ¦ Check the selected bootstrap runtime and protection before stops | ansible.builtin.include_role | False |
| Infisical ¦ Bind the pre-stop proof to its bootstrap service | ansible.builtin.set_fact | False |

#### File: tasks/service.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Infisical ¦ Reset current bootstrap inputs | ansible.builtin.set_fact | False |  |
| Infisical ¦ Select only current-service Vault declarations | ansible.builtin.set_fact | True |  |
| Infisical ¦ Require nonempty current-service credentials | ansible.builtin.assert | False |  |
| Infisical ¦ Deploy through the Podman adapter | ansible.builtin.include_role | False |  |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
