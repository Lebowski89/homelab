<!-- DOCSIBLE START -->

# 📃 Role overview

## netbox





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/10/20 |








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
| [netbox_frontend_fqdn](defaults/main.yml#L41)   | str | `{{ netbox_name }}.{{ services_internal_zone }}` |    
| [netbox_frontend_address](defaults/main.yml#L42)   | str | `https://{{ netbox_frontend_fqdn }}:{{ services_private_https_port }}` |    
| [netbox_port](defaults/main.yml#L43)   | int | `18000` |    
| [netbox_backend_address](defaults/main.yml#L44)   | str | `http://{{ local_ip }}:{{ netbox_port }}` |    
| [netbox_swarm_node_hostname](defaults/main.yml#L46)   | str | `{{ inventory_hostname }}` |    
| [netbox_docker_network](defaults/main.yml#L47)   | str | `overlay` |    
| [netbox_logging](defaults/main.yml#L49)   | dict | `{}` |    
| [netbox_logging.**driver**](defaults/main.yml#L50)   | str | `json-file` |    
| [netbox_logging.**options**](defaults/main.yml#L51)   | dict | `{}` |    
| [netbox_logging.options.**max-size**](defaults/main.yml#L52)   | str | `50m` |    
| [netbox_logging.options.**max-file**](defaults/main.yml#L53)   | str | `5` |    
| [netbox_logging.options.**compress**](defaults/main.yml#L54)   | str | `true` |    
| [netbox_restart_policy](defaults/main.yml#L56)   | dict | `{}` |    
| [netbox_restart_policy.**condition**](defaults/main.yml#L57)   | str | `on-failure` |    
| [netbox_restart_policy.**delay**](defaults/main.yml#L58)   | str | `10s` |    
| [netbox_restart_policy.**max_attempts**](defaults/main.yml#L59)   | int | `5` |    
| [netbox_restart_policy.**window**](defaults/main.yml#L60)   | str | `2m` |    
| [netbox_redis_name](defaults/main.yml#L66)   | str | `netbox-redis` |    
| [netbox_redis_image](defaults/main.yml#L67)   | str | `docker.io/valkey/valkey:9.2-alpine` |    
| [netbox_redis_puid](defaults/main.yml#L68)   | str | `{{ container_host_puid ¦ default('1000') }}` |    
| [netbox_redis_pgid](defaults/main.yml#L69)   | str | `{{ container_host_pgid ¦ default('1000') }}` |    
| [netbox_redis_path](defaults/main.yml#L70)   | str | `{{ netbox_base_path }}/redis` |    
| [netbox_postgres_name](defaults/main.yml#L76)   | str | `netbox-postgres` |    
| [netbox_postgres_image](defaults/main.yml#L77)   | str | `docker.io/library/postgres:18.6` |    
| [netbox_postgres_puid](defaults/main.yml#L78)   | str | `999` |    
| [netbox_postgres_pgid](defaults/main.yml#L79)   | str | `999` |    
| [netbox_postgres_path](defaults/main.yml#L80)   | str | `{{ netbox_base_path }}/postgres` |    
| [netbox_postgres_db_name](defaults/main.yml#L81)   | str | `netbox` |    
| [netbox_traefik_enable](defaults/main.yml#L87)   | bool | `True` |    
| [netbox_traefik_dynamic_dir](defaults/main.yml#L88)   | str | `/opt/traefik/dynamic` |    
| [netbox_traefik_entrypoint](defaults/main.yml#L89)   | str | `https_private` |    
| [netbox_traefik_authelia_enable](defaults/main.yml#L90)   | bool | `False` |    
| [netbox_traefik_headers_middleware](defaults/main.yml#L91)   | str | `netbox-headers@file` |    
| [netbox_traefik_middleware_chain](defaults/main.yml#L92)   | str | `{{ netbox_name }}-ui-chain` |    
| [netbox_traefik_certresolver](defaults/main.yml#L93)   | str | `dns-cloudflare` |    
| [netbox_traefik_tls_options](defaults/main.yml#L94)   | str | `securetls@file` |    
| [netbox_traefik_dynamic_owner](defaults/main.yml#L95)   | str | `1000` |    
| [netbox_traefik_dynamic_group](defaults/main.yml#L96)   | str | `1000` |    
| [netbox_podman_services](defaults/main.yml#L99)   | list | `[]` |    
| [netbox_podman_services.**0**](defaults/main.yml#L100)   | dict | `{}` |    
| [netbox_podman_services.0.**name**](defaults/main.yml#L100)   | str | `{{ netbox_postgres_name }}` |    
| [netbox_podman_services.0.**runtime**](defaults/main.yml#L101)   | str | `podman` |    
| [netbox_podman_services.0.**image**](defaults/main.yml#L102)   | str | `{{ netbox_postgres_image }}` |    
| [netbox_podman_services.0.**user**](defaults/main.yml#L103)   | str | `0:0` |    
| [netbox_podman_services.0.**environment**](defaults/main.yml#L104)   | dict | `{}` |    
| [netbox_podman_services.0.environment.**TZ**](defaults/main.yml#L105)   | str | `{{ netbox_timezone }}` |    
| [netbox_podman_services.0.environment.**POSTGRES_DB**](defaults/main.yml#L106)   | str | `{{ netbox_postgres_db_name }}` |    
| [netbox_podman_services.0.environment.**POSTGRES_USER_FILE**](defaults/main.yml#L107)   | str | `/run/secrets/postgres_user_secret` |    
| [netbox_podman_services.0.environment.**POSTGRES_PASSWORD_FILE**](defaults/main.yml#L108)   | str | `/run/secrets/postgres_pass_secret` |    
| [netbox_podman_services.0.**secrets**](defaults/main.yml#L109)   | list | `[]` |    
| [netbox_podman_services.0.secrets.**0**](defaults/main.yml#L110)   | str | `netbox_db_user_secret` |    
| [netbox_podman_services.0.secrets.**1**](defaults/main.yml#L111)   | str | `netbox_db_password_secret` |    
| [netbox_podman_services.0.**named_networks**](defaults/main.yml#L112)   | dict | `{}` |    
| [netbox_podman_services.0.named_networks.**netbox-postgres**](defaults/main.yml#L113)   | dict | `{}` |    
| [netbox_podman_services.0.named_networks.netbox-postgres.**driver**](defaults/main.yml#L114)   | str | `bridge` |    
| [netbox_podman_services.0.named_networks.netbox-postgres.**external**](defaults/main.yml#L115)   | bool | `False` |    
| [netbox_podman_services.0.**ports**](defaults/main.yml#L116)   | dict | `{}` |    
| [netbox_podman_services.0.ports.**database**](defaults/main.yml#L117)   | dict | `{}` |    
| [netbox_podman_services.0.ports.database.**host_ip**](defaults/main.yml#L118)   | str | `{{ local_ip }}` |    
| [netbox_podman_services.0.ports.database.**published**](defaults/main.yml#L119)   | str | `{{ netbox_postgres_backend_port }}` |    
| [netbox_podman_services.0.ports.database.**target**](defaults/main.yml#L120)   | int | `5432` |    
| [netbox_podman_services.0.ports.database.**protocol**](defaults/main.yml#L121)   | str | `tcp` |    
| [netbox_podman_services.0.**paths**](defaults/main.yml#L122)   | list | `[]` |    
| [netbox_podman_services.0.paths.**0**](defaults/main.yml#L123)   | dict | `{}` |    
| [netbox_podman_services.0.paths.0.**path**](defaults/main.yml#L123)   | str | `{{ netbox_postgres_path }}` |    
| [netbox_podman_services.0.paths.0.**state**](defaults/main.yml#L124)   | str | `directory` |    
| [netbox_podman_services.0.paths.0.**mode**](defaults/main.yml#L125)   | str | `0700` |    
| [netbox_podman_services.0.**volumes**](defaults/main.yml#L126)   | dict | `{}` |    
| [netbox_podman_services.0.volumes.**data**](defaults/main.yml#L127)   | dict | `{}` |    
| [netbox_podman_services.0.volumes.data.**type**](defaults/main.yml#L128)   | str | `bind` |    
| [netbox_podman_services.0.volumes.data.**source**](defaults/main.yml#L129)   | str | `{{ netbox_postgres_path }}` |    
| [netbox_podman_services.0.volumes.data.**target**](defaults/main.yml#L130)   | str | `/var/lib/postgresql` |    
| [netbox_podman_services.0.volumes.data.**read_only**](defaults/main.yml#L131)   | bool | `False` |    
| [netbox_podman_services.0.**no_new_privileges**](defaults/main.yml#L132)   | bool | `False` |    
| [netbox_podman_services.0.**operational_requirements**](defaults/main.yml#L133)   | dict | `{}` |    
| [netbox_podman_services.0.operational_requirements.**acl**](defaults/main.yml#L134)   | list | `[]` |    
| [netbox_podman_services.0.operational_requirements.acl.**0**](defaults/main.yml#L134)   | str | `bootstrap` |    
| [netbox_podman_services.0.operational_requirements.**ownership_transition**](defaults/main.yml#L135)   | bool | `True` |    
| [netbox_podman_services.0.**deploy**](defaults/main.yml#L136)   | dict | `{}` |    
| [netbox_podman_services.0.deploy.**type**](defaults/main.yml#L137)   | str | `container` |    
| [netbox_podman_services.0.deploy.**host**](defaults/main.yml#L138)   | str | `{{ inventory_hostname }}` |    
| [netbox_podman_services.0.deploy.**execution**](defaults/main.yml#L139)   | dict | `{}` |    
| [netbox_podman_services.0.deploy.execution.**mode**](defaults/main.yml#L140)   | str | `rootless` |    
| [netbox_podman_services.0.deploy.execution.**host_user**](defaults/main.yml#L141)   | str | `podman-netbox-postgres` |    
| [netbox_podman_services.0.deploy.execution.**userns**](defaults/main.yml#L142)   | dict | `{}` |    
| [netbox_podman_services.0.deploy.execution.userns.**mode**](defaults/main.yml#L143)   | str | `keep-id` |    
| [netbox_podman_services.0.deploy.execution.userns.**uid**](defaults/main.yml#L144)   | str | `999` |    
| [netbox_podman_services.0.deploy.execution.userns.**gid**](defaults/main.yml#L145)   | str | `999` |    
| [netbox_podman_services.0.**systemd**](defaults/main.yml#L146)   | dict | `{}` |    
| [netbox_podman_services.0.systemd.**restart**](defaults/main.yml#L147)   | str | `always` |    
| [netbox_podman_services.0.systemd.**restart_sec**](defaults/main.yml#L148)   | str | `15s` |    
| [netbox_podman_services.0.systemd.**timeout_start_sec**](defaults/main.yml#L149)   | str | `600s` |    
| [netbox_podman_services.0.systemd.**after**](defaults/main.yml#L150)   | list | `[]` |    
| [netbox_podman_services.0.systemd.after.**0**](defaults/main.yml#L151)   | str | `network-online.target` |    
| [netbox_podman_services.0.**healthcheck**](defaults/main.yml#L152)   | dict | `{}` |    
| [netbox_podman_services.0.healthcheck.**test**](defaults/main.yml#L153)   | list | `[]` |    
| [netbox_podman_services.0.healthcheck.test.**0**](defaults/main.yml#L154)   | str | `CMD-SHELL` |    
| [netbox_podman_services.0.healthcheck.test.**1**](defaults/main.yml#L155)   | str | `PGUSER="$(cat /run/secrets/postgres_user_secret)" pg_isready -d "$POSTGRES_DB"` |    
| [netbox_podman_services.0.healthcheck.**interval**](defaults/main.yml#L156)   | str | `10s` |    
| [netbox_podman_services.0.healthcheck.**timeout**](defaults/main.yml#L157)   | str | `5s` |    
| [netbox_podman_services.0.healthcheck.**retries**](defaults/main.yml#L158)   | int | `5` |    
| [netbox_podman_services.0.healthcheck.**start_period**](defaults/main.yml#L159)   | str | `30s` |    
| [netbox_podman_services.0.**notify_healthy**](defaults/main.yml#L160)   | bool | `True` |    
| [netbox_podman_services.**1**](defaults/main.yml#L161)   | dict | `{}` |    
| [netbox_podman_services.1.**name**](defaults/main.yml#L161)   | str | `{{ netbox_redis_name }}` |    
| [netbox_podman_services.1.**runtime**](defaults/main.yml#L162)   | str | `podman` |    
| [netbox_podman_services.1.**image**](defaults/main.yml#L163)   | str | `{{ netbox_redis_image }}` |    
| [netbox_podman_services.1.**user**](defaults/main.yml#L164)   | str | `0:0` |    
| [netbox_podman_services.1.**environment**](defaults/main.yml#L165)   | dict | `{}` |    
| [netbox_podman_services.1.environment.**TZ**](defaults/main.yml#L166)   | str | `{{ netbox_timezone }}` |    
| [netbox_podman_services.1.environment.**PUID**](defaults/main.yml#L167)   | str | `{{ netbox_redis_puid }}` |    
| [netbox_podman_services.1.environment.**PGID**](defaults/main.yml#L168)   | str | `{{ netbox_redis_pgid }}` |    
| [netbox_podman_services.1.**secrets**](defaults/main.yml#L169)   | list | `[]` |    
| [netbox_podman_services.1.secrets.**0**](defaults/main.yml#L170)   | str | `netbox_redis_password_secret` |    
| [netbox_podman_services.1.**named_networks**](defaults/main.yml#L171)   | dict | `{}` |    
| [netbox_podman_services.1.named_networks.**netbox-redis**](defaults/main.yml#L172)   | dict | `{}` |    
| [netbox_podman_services.1.named_networks.netbox-redis.**driver**](defaults/main.yml#L173)   | str | `bridge` |    
| [netbox_podman_services.1.named_networks.netbox-redis.**external**](defaults/main.yml#L174)   | bool | `False` |    
| [netbox_podman_services.1.**ports**](defaults/main.yml#L175)   | dict | `{}` |    
| [netbox_podman_services.1.ports.**cache**](defaults/main.yml#L176)   | dict | `{}` |    
| [netbox_podman_services.1.ports.cache.**host_ip**](defaults/main.yml#L177)   | str | `{{ local_ip }}` |    
| [netbox_podman_services.1.ports.cache.**published**](defaults/main.yml#L178)   | str | `{{ netbox_redis_backend_port }}` |    
| [netbox_podman_services.1.ports.cache.**target**](defaults/main.yml#L179)   | int | `6379` |    
| [netbox_podman_services.1.ports.cache.**protocol**](defaults/main.yml#L180)   | str | `tcp` |    
| [netbox_podman_services.1.**paths**](defaults/main.yml#L181)   | list | `[]` |    
| [netbox_podman_services.1.paths.**0**](defaults/main.yml#L182)   | dict | `{}` |    
| [netbox_podman_services.1.paths.0.**path**](defaults/main.yml#L182)   | str | `{{ netbox_redis_path }}` |    
| [netbox_podman_services.1.paths.0.**state**](defaults/main.yml#L183)   | str | `directory` |    
| [netbox_podman_services.1.paths.0.**mode**](defaults/main.yml#L184)   | str | `0755` |    
| [netbox_podman_services.1.**volumes**](defaults/main.yml#L185)   | dict | `{}` |    
| [netbox_podman_services.1.volumes.**data**](defaults/main.yml#L186)   | dict | `{}` |    
| [netbox_podman_services.1.volumes.data.**type**](defaults/main.yml#L187)   | str | `bind` |    
| [netbox_podman_services.1.volumes.data.**source**](defaults/main.yml#L188)   | str | `{{ netbox_redis_path }}` |    
| [netbox_podman_services.1.volumes.data.**target**](defaults/main.yml#L189)   | str | `/data` |    
| [netbox_podman_services.1.volumes.data.**read_only**](defaults/main.yml#L190)   | bool | `False` |    
| [netbox_podman_services.1.**no_new_privileges**](defaults/main.yml#L191)   | bool | `False` |    
| [netbox_podman_services.1.**operational_requirements**](defaults/main.yml#L192)   | dict | `{}` |    
| [netbox_podman_services.1.operational_requirements.**acl**](defaults/main.yml#L193)   | list | `[]` |    
| [netbox_podman_services.1.operational_requirements.acl.**0**](defaults/main.yml#L193)   | str | `bootstrap` |    
| [netbox_podman_services.1.operational_requirements.**ownership_transition**](defaults/main.yml#L194)   | bool | `True` |    
| [netbox_podman_services.1.**deploy**](defaults/main.yml#L195)   | dict | `{}` |    
| [netbox_podman_services.1.deploy.**type**](defaults/main.yml#L196)   | str | `container` |    
| [netbox_podman_services.1.deploy.**host**](defaults/main.yml#L197)   | str | `{{ inventory_hostname }}` |    
| [netbox_podman_services.1.deploy.**execution**](defaults/main.yml#L198)   | dict | `{}` |    
| [netbox_podman_services.1.deploy.execution.**mode**](defaults/main.yml#L199)   | str | `rootless` |    
| [netbox_podman_services.1.deploy.execution.**host_user**](defaults/main.yml#L200)   | str | `podman-netbox-redis` |    
| [netbox_podman_services.1.deploy.execution.**userns**](defaults/main.yml#L201)   | dict | `{}` |    
| [netbox_podman_services.1.deploy.execution.userns.**mode**](defaults/main.yml#L202)   | str | `keep-id` |    
| [netbox_podman_services.1.deploy.execution.userns.**uid**](defaults/main.yml#L203)   | str | `0` |    
| [netbox_podman_services.1.deploy.execution.userns.**gid**](defaults/main.yml#L204)   | str | `0` |    
| [netbox_podman_services.1.**systemd**](defaults/main.yml#L205)   | dict | `{}` |    
| [netbox_podman_services.1.systemd.**restart**](defaults/main.yml#L206)   | str | `always` |    
| [netbox_podman_services.1.systemd.**restart_sec**](defaults/main.yml#L207)   | str | `15s` |    
| [netbox_podman_services.1.systemd.**timeout_start_sec**](defaults/main.yml#L208)   | str | `600s` |    
| [netbox_podman_services.1.systemd.**after**](defaults/main.yml#L209)   | list | `[]` |    
| [netbox_podman_services.1.systemd.after.**0**](defaults/main.yml#L210)   | str | `network-online.target` |    
| [netbox_podman_services.1.**command**](defaults/main.yml#L211)   | list | `[]` |    
| [netbox_podman_services.1.command.**0**](defaults/main.yml#L212)   | str | `sh` |    
| [netbox_podman_services.1.command.**1**](defaults/main.yml#L213)   | str | `-c` |    
| [netbox_podman_services.1.command.**2**](defaults/main.yml#L213)   | str | `umask 077; printf 'appendonly yes\nrequirepass "%s"\n' "$(sed 's/[\\"]/\\&/g' /run/secrets/netbox_redis_password_secret)" > /tmp/skynet-valkey.conf; exec valkey-server /tmp/skynet-valkey.conf` |    
| [netbox_podman_services.1.**healthcheck**](defaults/main.yml#L218)   | dict | `{}` |    
| [netbox_podman_services.1.healthcheck.**test**](defaults/main.yml#L219)   | list | `[]` |    
| [netbox_podman_services.1.healthcheck.test.**0**](defaults/main.yml#L220)   | str | `CMD-SHELL` |    
| [netbox_podman_services.1.healthcheck.test.**1**](defaults/main.yml#L221)   | str | `REDISCLI_AUTH="$(cat /run/secrets/netbox_redis_password_secret)" valkey-cli ping ¦ grep -q PONG` |    
| [netbox_podman_services.1.healthcheck.**interval**](defaults/main.yml#L222)   | str | `10s` |    
| [netbox_podman_services.1.healthcheck.**timeout**](defaults/main.yml#L223)   | str | `5s` |    
| [netbox_podman_services.1.healthcheck.**retries**](defaults/main.yml#L224)   | int | `5` |    
| [netbox_podman_services.1.healthcheck.**start_period**](defaults/main.yml#L225)   | str | `30s` |    
| [netbox_podman_services.1.**notify_healthy**](defaults/main.yml#L226)   | bool | `True` |    
| [netbox_podman_services.1.**tmpfs**](defaults/main.yml#L227)   | list | `[]` |    
| [netbox_podman_services.1.tmpfs.**0**](defaults/main.yml#L228)   | str | `/tmp:mode=1777` |    
| [netbox_podman_services.**2**](defaults/main.yml#L229)   | dict | `{}` |    
| [netbox_podman_services.2.**name**](defaults/main.yml#L229)   | str | `{{ netbox_name }}` |    
| [netbox_podman_services.2.**runtime**](defaults/main.yml#L230)   | str | `podman` |    
| [netbox_podman_services.2.**image**](defaults/main.yml#L231)   | str | `{{ netbox_image }}` |    
| [netbox_podman_services.2.**user**](defaults/main.yml#L232)   | str | `0:0` |    
| [netbox_podman_services.2.**environment**](defaults/main.yml#L233)   | dict | `{}` |    
| [netbox_podman_services.2.environment.**TZ**](defaults/main.yml#L234)   | str | `{{ netbox_timezone }}` |    
| [netbox_podman_services.2.environment.**PUID**](defaults/main.yml#L235)   | str | `{{ netbox_puid }}` |    
| [netbox_podman_services.2.environment.**PGID**](defaults/main.yml#L236)   | str | `{{ netbox_pgid }}` |    
| [netbox_podman_services.2.environment.**FILE__SUPERUSER_EMAIL**](defaults/main.yml#L237)   | str | `/run/secrets/netbox_superuser_email_secret` |    
| [netbox_podman_services.2.environment.**FILE__SUPERUSER_PASSWORD**](defaults/main.yml#L238)   | str | `/run/secrets/netbox_superuser_password_secret` |    
| [netbox_podman_services.2.environment.**ALLOWED_HOST**](defaults/main.yml#L239)   | str | `{{ netbox_frontend_fqdn }}` |    
| [netbox_podman_services.2.environment.**CSRF_TRUSTED_ORIGINS**](defaults/main.yml#L240)   | str | `'{{ netbox_frontend_address }}'` |    
| [netbox_podman_services.2.environment.**DB_NAME**](defaults/main.yml#L241)   | str | `{{ netbox_postgres_db_name }}` |    
| [netbox_podman_services.2.environment.**FILE__DB_USER**](defaults/main.yml#L242)   | str | `/run/secrets/postgres_user_secret` |    
| [netbox_podman_services.2.environment.**FILE__DB_PASSWORD**](defaults/main.yml#L243)   | str | `/run/secrets/postgres_pass_secret` |    
| [netbox_podman_services.2.environment.**DB_HOST**](defaults/main.yml#L244)   | str | `{{ local_ip }}` |    
| [netbox_podman_services.2.environment.**DB_PORT**](defaults/main.yml#L245)   | str | `{{ netbox_postgres_backend_port }}` |    
| [netbox_podman_services.2.environment.**REDIS_HOST**](defaults/main.yml#L246)   | str | `{{ local_ip }}` |    
| [netbox_podman_services.2.environment.**REDIS_PORT**](defaults/main.yml#L247)   | str | `{{ netbox_redis_backend_port }}` |    
| [netbox_podman_services.2.environment.**REDIS_USERNAME**](defaults/main.yml#L248)   | str |  |    
| [netbox_podman_services.2.environment.**FILE__REDIS_PASSWORD**](defaults/main.yml#L249)   | str | `/run/secrets/netbox_redis_password_secret` |    
| [netbox_podman_services.2.environment.**REDIS_DB_TASK**](defaults/main.yml#L250)   | str | `0` |    
| [netbox_podman_services.2.environment.**REDIS_DB_CACHE**](defaults/main.yml#L251)   | str | `1` |    
| [netbox_podman_services.2.**secrets**](defaults/main.yml#L252)   | list | `[]` |    
| [netbox_podman_services.2.secrets.**0**](defaults/main.yml#L253)   | str | `netbox_superuser_email_secret` |    
| [netbox_podman_services.2.secrets.**1**](defaults/main.yml#L254)   | str | `netbox_superuser_password_secret` |    
| [netbox_podman_services.2.secrets.**2**](defaults/main.yml#L255)   | str | `netbox_db_user_secret` |    
| [netbox_podman_services.2.secrets.**3**](defaults/main.yml#L256)   | str | `netbox_db_password_secret` |    
| [netbox_podman_services.2.secrets.**4**](defaults/main.yml#L257)   | str | `netbox_redis_password_secret` |    
| [netbox_podman_services.2.**named_networks**](defaults/main.yml#L258)   | dict | `{}` |    
| [netbox_podman_services.2.named_networks.**netbox**](defaults/main.yml#L259)   | dict | `{}` |    
| [netbox_podman_services.2.named_networks.netbox.**driver**](defaults/main.yml#L260)   | str | `bridge` |    
| [netbox_podman_services.2.named_networks.netbox.**external**](defaults/main.yml#L261)   | bool | `False` |    
| [netbox_podman_services.2.**paths**](defaults/main.yml#L262)   | list | `[]` |    
| [netbox_podman_services.2.paths.**0**](defaults/main.yml#L263)   | dict | `{}` |    
| [netbox_podman_services.2.paths.0.**path**](defaults/main.yml#L263)   | str | `{{ netbox_base_path }}` |    
| [netbox_podman_services.2.paths.0.**state**](defaults/main.yml#L264)   | str | `directory` |    
| [netbox_podman_services.2.paths.0.**mode**](defaults/main.yml#L265)   | str | `0755` |    
| [netbox_podman_services.2.paths.**1**](defaults/main.yml#L266)   | dict | `{}` |    
| [netbox_podman_services.2.paths.1.**path**](defaults/main.yml#L266)   | str | `{{ netbox_base_path }}/config` |    
| [netbox_podman_services.2.paths.1.**state**](defaults/main.yml#L267)   | str | `directory` |    
| [netbox_podman_services.2.paths.1.**mode**](defaults/main.yml#L268)   | str | `0755` |    
| [netbox_podman_services.2.**volumes**](defaults/main.yml#L269)   | dict | `{}` |    
| [netbox_podman_services.2.volumes.**config**](defaults/main.yml#L270)   | dict | `{}` |    
| [netbox_podman_services.2.volumes.config.**type**](defaults/main.yml#L271)   | str | `bind` |    
| [netbox_podman_services.2.volumes.config.**source**](defaults/main.yml#L272)   | str | `{{ netbox_base_path }}/config` |    
| [netbox_podman_services.2.volumes.config.**target**](defaults/main.yml#L273)   | str | `/config` |    
| [netbox_podman_services.2.volumes.config.**read_only**](defaults/main.yml#L274)   | bool | `False` |    
| [netbox_podman_services.2.**no_new_privileges**](defaults/main.yml#L275)   | bool | `False` |    
| [netbox_podman_services.2.**operational_requirements**](defaults/main.yml#L276)   | dict | `{}` |    
| [netbox_podman_services.2.operational_requirements.**acl**](defaults/main.yml#L277)   | list | `[]` |    
| [netbox_podman_services.2.operational_requirements.acl.**0**](defaults/main.yml#L277)   | str | `bootstrap` |    
| [netbox_podman_services.2.operational_requirements.**ownership_transition**](defaults/main.yml#L278)   | bool | `True` |    
| [netbox_podman_services.2.**deploy**](defaults/main.yml#L279)   | dict | `{}` |    
| [netbox_podman_services.2.deploy.**type**](defaults/main.yml#L280)   | str | `container` |    
| [netbox_podman_services.2.deploy.**host**](defaults/main.yml#L281)   | str | `{{ inventory_hostname }}` |    
| [netbox_podman_services.2.deploy.**execution**](defaults/main.yml#L282)   | dict | `{}` |    
| [netbox_podman_services.2.deploy.execution.**mode**](defaults/main.yml#L283)   | str | `rootless` |    
| [netbox_podman_services.2.deploy.execution.**host_user**](defaults/main.yml#L284)   | str | `podman-netbox` |    
| [netbox_podman_services.2.deploy.execution.**userns**](defaults/main.yml#L285)   | dict | `{}` |    
| [netbox_podman_services.2.deploy.execution.userns.**mode**](defaults/main.yml#L286)   | str | `keep-id` |    
| [netbox_podman_services.2.deploy.execution.userns.**uid**](defaults/main.yml#L287)   | str | `{{ netbox_puid }}` |    
| [netbox_podman_services.2.deploy.execution.userns.**gid**](defaults/main.yml#L288)   | str | `{{ netbox_pgid }}` |    
| [netbox_podman_services.2.**systemd**](defaults/main.yml#L289)   | dict | `{}` |    
| [netbox_podman_services.2.systemd.**restart**](defaults/main.yml#L290)   | str | `always` |    
| [netbox_podman_services.2.systemd.**restart_sec**](defaults/main.yml#L291)   | str | `15s` |    
| [netbox_podman_services.2.systemd.**timeout_start_sec**](defaults/main.yml#L292)   | str | `600s` |    
| [netbox_podman_services.2.systemd.**after**](defaults/main.yml#L293)   | list | `[]` |    
| [netbox_podman_services.2.systemd.after.**0**](defaults/main.yml#L294)   | str | `network-online.target` |    
| [netbox_podman_services.2.**healthcheck**](defaults/main.yml#L295)   | dict | `{}` |    
| [netbox_podman_services.2.healthcheck.**test**](defaults/main.yml#L296)   | list | `[]` |    
| [netbox_podman_services.2.healthcheck.test.**0**](defaults/main.yml#L297)   | str | `CMD-SHELL` |    
| [netbox_podman_services.2.healthcheck.test.**1**](defaults/main.yml#L300)   | str | `curl --fail --silent -H "Host: {{ netbox_frontend_fqdn }}" http://127.0.0.1:8000/login/ > /dev/null` |    
| [netbox_podman_services.2.healthcheck.**interval**](defaults/main.yml#L301)   | str | `10s` |    
| [netbox_podman_services.2.healthcheck.**timeout**](defaults/main.yml#L302)   | str | `5s` |    
| [netbox_podman_services.2.healthcheck.**retries**](defaults/main.yml#L303)   | int | `5` |    
| [netbox_podman_services.2.healthcheck.**start_period**](defaults/main.yml#L304)   | str | `30s` |    
| [netbox_podman_services.2.**notify_healthy**](defaults/main.yml#L305)   | bool | `True` |    
| [netbox_podman_services.2.**ports**](defaults/main.yml#L306)   | dict | `{}` |    
| [netbox_podman_services.2.ports.**recovery**](defaults/main.yml#L307)   | dict | `{}` |    
| [netbox_podman_services.2.ports.recovery.**host_ip**](defaults/main.yml#L308)   | str | `{{ local_ip }}` |    
| [netbox_podman_services.2.ports.recovery.**published**](defaults/main.yml#L309)   | str | `{{ netbox_port }}` |    
| [netbox_podman_services.2.ports.recovery.**target**](defaults/main.yml#L310)   | int | `8000` |    
| [netbox_podman_secret_targets](defaults/main.yml#L311)   | dict | `{}` |    
| [netbox_podman_secret_targets.**netbox_db_user_secret**](defaults/main.yml#L312)   | str | `/run/secrets/postgres_user_secret` |    
| [netbox_podman_secret_targets.**netbox_db_password_secret**](defaults/main.yml#L313)   | str | `/run/secrets/postgres_pass_secret` |    
| [netbox_postgres_backend_port](defaults/main.yml#L314)   | int | `15432` |    
| [netbox_redis_backend_port](defaults/main.yml#L315)   | int | `16380` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Netbox ¦ Validate bootstrap inputs | ansible.builtin.assert | False |  |
| Netbox ¦ Select explicit bootstrap operation | ansible.builtin.set_fact | False |  |
| Netbox ¦ Validate required Vault inputs before mutation | ansible.builtin.assert | True |  |
| Netbox ¦ Validate all Quadlet definitions before mutation | ansible.builtin.include_role | False |  |
| Netbox ¦ Reset this operation's bootstrap prerequisite proofs | ansible.builtin.set_fact | False |  |
| Netbox ¦ Enforce every bootstrap requirement before stopping or preparing services | ansible.builtin.include_tasks | False |  |
| Netbox ¦ Stop consumers before providers in their persisted managers | ansible.builtin.include_role | True |  |
| Netbox ¦ Process bootstrap providers and consumers | ansible.builtin.include_tasks | False |  |
| Netbox ¦ Render Traefik dynamic file | ansible.builtin.template | True |  |
| Netbox ¦ Retire Traefik route | ansible.builtin.file | True |  |

#### File: tasks/requirements.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Netbox ¦ Check the selected bootstrap runtime and protection before stops | ansible.builtin.include_role | False |
| Netbox ¦ Bind the pre-stop proof to its bootstrap service | ansible.builtin.set_fact | False |

#### File: tasks/service.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Netbox ¦ Reset current bootstrap inputs | ansible.builtin.set_fact | False |  |
| Netbox ¦ Select only current-service Vault declarations | ansible.builtin.set_fact | True |  |
| Netbox ¦ Require nonempty current-service credentials | ansible.builtin.assert | True |  |
| Netbox ¦ Deploy through the Podman adapter | ansible.builtin.include_role | False |  |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
