<!-- DOCSIBLE START -->

# 📃 Role overview

## postgres





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/08/21 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [postgres_version](defaults/main.yml#L7)   | int | `18` |    
| [postgres_etcd_data_dir](defaults/main.yml#L13)   | str | `/var/lib/etcd` |    
| [postgres_etcd_client_port](defaults/main.yml#L14)   | int | `2379` |    
| [postgres_etcd_peer_port](defaults/main.yml#L15)   | int | `2380` |    
| [postgres_etcd_cluster_token](defaults/main.yml#L16)   | str | `pg-ha-1` |    
| [postgres_etcd_initial_cluster](defaults/main.yml#L18)   | list | `[]` |    
| [postgres_etcd_initial_cluster_state](defaults/main.yml#L21)   | str | `new` |    
| [postgres_patroni_scope](defaults/main.yml#L27)   | str | `pg-cluster` |    
| [postgres_patroni_namespace](defaults/main.yml#L28)   | str | `/service` |    
| [postgres_patroni_node_name](defaults/main.yml#L29)   | str | `{{ inventory_hostname }}` |    
| [postgres_patroni_config_dir](defaults/main.yml#L31)   | str | `/etc/patroni` |    
| [postgres_patroni_config_path](defaults/main.yml#L32)   | str | `{{ postgres_patroni_config_dir }}/config.yml` |    
| [postgres_patroni_data_dir](defaults/main.yml#L33)   | str | `/var/lib/postgresql/{{ postgres_version }}/main` |    
| [postgres_patroni_bin_dir](defaults/main.yml#L34)   | str | `/usr/lib/postgresql/{{ postgres_version }}/bin` |    
| [postgres_patroni_restapi_port](defaults/main.yml#L35)   | int | `8008` |    
| [postgres_patroni_postgres_port](defaults/main.yml#L36)   | int | `5432` |    
| [postgres_patroni_superuser_name](defaults/main.yml#L42)   | str | `postgres` |    
| [postgres_patroni_superuser_pass](defaults/main.yml#L43)   | str |  |    
| [postgres_patroni_replication_name](defaults/main.yml#L45)   | str | `replicator` |    
| [postgres_patroni_replication_pass](defaults/main.yml#L46)   | str |  |    
| [postgres_patroni_admin_role_name](defaults/main.yml#L48)   | str | `admin` |    
| [postgres_patroni_admin_role_pass](defaults/main.yml#L49)   | str |  |    
| [postgres_patroni_admin_role_login](defaults/main.yml#L50)   | bool | `True` |    
| [postgres_patroni_admin_role_createdb](defaults/main.yml#L51)   | bool | `True` |    
| [postgres_patroni_admin_role_createrole](defaults/main.yml#L52)   | bool | `False` |    
| [postgres_patroni_etcd_hosts](defaults/main.yml#L54)   | list | `[]` |    
| [postgres_patroni_pg_hba_extra](defaults/main.yml#L55)   | list | `[]` |    
| [postgres_uptime_kuma_monitor_role_name](defaults/main.yml#L61)   | str | `uptime_kuma_monitor` |    
| [postgres_uptime_kuma_monitor_role_pass](defaults/main.yml#L62)   | str |  |    
| [postgres_uptime_kuma_monitor_database](defaults/main.yml#L63)   | str | `postgres` |    
| [postgres_backup_root](defaults/main.yml#L69)   | str | `/var/backups/postgresql` |    
| [postgres_backup_script_path](defaults/main.yml#L70)   | str | `/usr/local/sbin/postgres-logical-backup` |    
| [postgres_backup_manage_timer](defaults/main.yml#L71)   | bool | `False` |    
| [postgres_backup_timer_name](defaults/main.yml#L72)   | str | `postgres-logical-backup` |    
| [postgres_backup_timer_on_calendar](defaults/main.yml#L73)   | str | `*-*-* 03:00:00` |    
| [postgres_backup_timer_randomized_delay_sec](defaults/main.yml#L74)   | str | `30m` |    
| [postgres_backup_local_retention_days](defaults/main.yml#L75)   | int | `7` |    
| [postgres_backup_failed_retention_days](defaults/main.yml#L76)   | int | `2` |    
| [postgres_backup_metrics_file](defaults/main.yml#L77)   | str | `/var/lib/node_exporter/textfile_collector_postgres/postgres_logical_backup.prom` |    
| [postgres_backup_remote_manage](defaults/main.yml#L83)   | bool | `False` |    
| [postgres_backup_remote_enabled](defaults/main.yml#L84)   | bool | `False` |    
| [postgres_backup_remote_restic_path](defaults/main.yml#L85)   | str | `/usr/bin/restic` |    
| [postgres_backup_remote_script_path](defaults/main.yml#L86)   | str | `/usr/local/sbin/postgres-logical-backup-remote` |    
| [postgres_backup_remote_state_dir](defaults/main.yml#L87)   | str | `/var/lib/postgres-logical-backup-remote` |    
| [postgres_backup_remote_repository](defaults/main.yml#L88)   | str |  |    
| [postgres_backup_remote_config_dir](defaults/main.yml#L89)   | str | `/etc/restic/postgres-logical-backup` |    
| [postgres_backup_remote_repository_file](defaults/main.yml#L90)   | str | `{{ postgres_backup_remote_config_dir }}/repository` |    
| [postgres_backup_remote_password_file](defaults/main.yml#L91)   | str | `{{ postgres_backup_remote_config_dir }}/password` |    
| [postgres_backup_remote_environment_file](defaults/main.yml#L92)   | str | `{{ postgres_backup_remote_config_dir }}/backend.env` |    
| [postgres_backup_remote_managed_secret_files_manifest](defaults/main.yml#L93)   | str | `<multiline value: folded_strip>` |    
| [postgres_backup_remote_password_secret](defaults/main.yml#L95)   | dict | `{}` |    
| [postgres_backup_remote_password_secret.**path**](defaults/main.yml#L96)   | str | `/Restic/Postgres` |    
| [postgres_backup_remote_password_secret.**name**](defaults/main.yml#L97)   | str | `PASSWORD` |    
| [postgres_backup_remote_backend_environment](defaults/main.yml#L98)   | dict | `{}` |    
| [postgres_backup_remote_backend_secrets](defaults/main.yml#L99)   | list | `[]` |    
| [postgres_backup_remote_secret_files](defaults/main.yml#L100)   | list | `[]` |    
| [postgres_backup_remote_options](defaults/main.yml#L101)   | list | `[]` |    
| [postgres_backup_remote_retry_lock](defaults/main.yml#L102)   | str | `10m` |    
| [postgres_backup_remote_timer_name](defaults/main.yml#L103)   | str | `postgres-logical-backup-remote` |    
| [postgres_backup_remote_timer_on_calendar](defaults/main.yml#L104)   | str | `*-*-* 04:00:00` |    
| [postgres_backup_remote_timer_randomized_delay_sec](defaults/main.yml#L105)   | str | `30m` |    
| [postgres_backup_remote_maintenance_timer_name](defaults/main.yml#L106)   | str | `postgres-logical-backup-remote-maintenance` |    
| [postgres_backup_remote_maintenance_timer_on_calendar](defaults/main.yml#L107)   | str | `Sun *-*-* 05:00:00` |    
| [postgres_backup_remote_maintenance_timer_randomized_delay_sec](defaults/main.yml#L108)   | str | `30m` |    
| [postgres_backup_remote_maintenance_host](defaults/main.yml#L109)   | str | `<multiline value: folded_strip>` |    
| [postgres_backup_remote_snapshot_host](defaults/main.yml#L111)   | str | `{{ postgres_patroni_scope }}` |    
| [postgres_backup_remote_keep_daily](defaults/main.yml#L112)   | int | `14` |    
| [postgres_backup_remote_keep_weekly](defaults/main.yml#L113)   | int | `8` |    
| [postgres_backup_remote_keep_monthly](defaults/main.yml#L114)   | int | `12` |    
| [postgres_backup_remote_metrics_file](defaults/main.yml#L115)   | str | `<multiline value: folded_strip>` |    
| [postgres_backup_restore_validation_manage](defaults/main.yml#L122)   | bool | `False` |    
| [postgres_backup_restore_validation_enabled](defaults/main.yml#L123)   | bool | `False` |    
| [postgres_backup_restore_validation_host](defaults/main.yml#L124)   | str | `{{ postgres_backup_remote_maintenance_host }}` |    
| [postgres_backup_restore_validation_script_path](defaults/main.yml#L125)   | str | `/usr/local/sbin/postgres-logical-backup-restore-validate` |    
| [postgres_backup_restore_validation_runuser_path](defaults/main.yml#L126)   | str | `/usr/sbin/runuser` |    
| [postgres_backup_restore_validation_work_root](defaults/main.yml#L127)   | str | `/var/lib/postgres-logical-backup-restore-validation` |    
| [postgres_backup_restore_validation_timer_name](defaults/main.yml#L128)   | str | `postgres-logical-backup-restore-validation` |    
| [postgres_backup_restore_validation_timer_on_calendar](defaults/main.yml#L129)   | str | `Sun *-*-* 07:00:00` |    
| [postgres_backup_restore_validation_timer_randomized_delay_sec](defaults/main.yml#L130)   | str | `30m` |    
| [postgres_backup_restore_validation_port](defaults/main.yml#L131)   | int | `55432` |    
| [postgres_backup_restore_validation_max_snapshot_age_hours](defaults/main.yml#L132)   | int | `48` |    
| [postgres_backup_restore_validation_min_free_bytes](defaults/main.yml#L133)   | int | `5368709120` |    
| [postgres_backup_restore_validation_encoding](defaults/main.yml#L134)   | str | `UTF8` |    
| [postgres_backup_restore_validation_locale](defaults/main.yml#L135)   | str | `C.UTF-8` |    
| [postgres_backup_restore_validation_metrics_file](defaults/main.yml#L136)   | str | `<multiline value: folded_strip>` |    
| [postgres_restore_dbs_dir](defaults/main.yml#L143)   | str | `/tmp` |    
| [postgres_restore_dbs_drop_existing](defaults/main.yml#L144)   | bool | `True` |    
| [postgres_restore_dbs_map](defaults/main.yml#L149)   | list | `[]` |    
| [postgres_fix_owner_map](defaults/main.yml#L164)   | list | `[]` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Install postgres packages | ansible.builtin.include_tasks | True | postgres,postgres_apt |
| Configure etcd | ansible.builtin.include_tasks | True | postgres,postgres_etcd,postgres_etcd_reset |
| Configure Patroni | ansible.builtin.include_tasks | True | postgres,postgres_patroni,postgres_patroni_reset |
| Ensure dedicated PostgreSQL admin role exists | ansible.builtin.include_tasks | True | postgres_admin,postgres_admin_uptime_kuma |
| Ensure dedicated PostgreSQL Uptime Kuma role exists | ansible.builtin.include_tasks | True | p,o,s,t,g,r,e,s,_,a,d,m,i,n,_,u,p,t,i,m,e,_,k,u,m,a |
| Configure PostgreSQL logical backups | ansible.builtin.include_tasks | True | postgres,postgres_backup,postgres_backup_setup,postgres_backup_run |
| Run PostgreSQL logical backup manually | ansible.builtin.include_tasks | True | postgres_backup,postgres_backup_run |
| Report PostgreSQL logical backup manual check-mode plan | ansible.builtin.debug | True | postgres_backup,postgres_backup_run |
| Configure PostgreSQL remote logical backups | ansible.builtin.include_tasks | True | postgres,postgres_backup_remote_setup,postgres_backup_remote_init,postgres_backup_remote_run,postgres_backup_remote_maintenance,postgres_backup_restore_validation_setup,postgres_backup_restore_validation_run |
| Initialize PostgreSQL remote backup repository explicitly | ansible.builtin.include_tasks | True | postgres_backup_remote_init |
| Run PostgreSQL remote backup uploader manually | ansible.builtin.include_tasks | True | postgres_backup_remote_run |
| Run PostgreSQL remote backup maintenance manually | ansible.builtin.include_tasks | True | postgres_backup_remote_maintenance |
| Report PostgreSQL remote backup init check-mode plan | ansible.builtin.debug | True | postgres_backup_remote_init |
| Report PostgreSQL remote backup upload check-mode plan | ansible.builtin.debug | True | postgres_backup_remote_run |
| Report PostgreSQL remote backup maintenance check-mode plan | ansible.builtin.debug | True | postgres_backup_remote_maintenance |
| Configure PostgreSQL backup restore validation | ansible.builtin.include_tasks | True | postgres,postgres_backup_restore_validation_setup,postgres_backup_restore_validation_run |
| Run PostgreSQL backup restore validation manually | ansible.builtin.include_tasks | True | postgres_backup_restore_validation_run |
| Report PostgreSQL backup restore validation check-mode plan | ansible.builtin.debug | True | postgres_backup_restore_validation_run |
| Restore PostgreSQL single database from pg_dump backup | ansible.builtin.include_tasks | True | p,o,s,t,g,r,e,s,_,r,e,s,t,o,r,e |
| Reset PostgreSQL/Patroni node destructively | ansible.builtin.include_tasks | True | p,o,s,t,g,r,e,s,_,a,d,m,i,n,_,n,u,k,e,_,n,o,d,e |
| Fix database ownership and privileges | ansible.builtin.include_tasks | True | p,o,s,t,g,r,e,s,_,a,d,m,i,n,_,f,i,x,_,o,w,n,e,r |
| Update Patroni dynamic pg_hba in DCS | ansible.builtin.include_tasks | True | p,o,s,t,g,r,e,s,_,a,d,m,i,n,_,u,p,d,a,t,e,_,p,g,_,h,b,a |

#### File: tasks/sub_tasks/admin/fix_owner.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Fix DB owner ¦ Assert ownership map is provided | ansible.builtin.assert | False |
| Fix DB owner ¦ Validate ownership map entries | ansible.builtin.assert | False |
| Fix DB owner ¦ Query Patroni cluster state from first postgres node | ansible.builtin.uri | False |
| Fix DB owner ¦ Extract Patroni leader candidates | ansible.builtin.set_fact | False |
| Fix DB owner ¦ Determine Patroni leader member | ansible.builtin.set_fact | False |
| Fix DB owner ¦ Assert Patroni leader was found | ansible.builtin.assert | False |
| Fix DB owner ¦ Ensure target roles exist | community.postgresql.postgresql_query | False |
| Fix DB owner ¦ Assert target roles exist | ansible.builtin.assert | False |
| Fix DB owner ¦ Set database owners | community.postgresql.postgresql_query | False |
| Fix DB owner ¦ Fix schema ownership, object ownership, and privileges | ansible.builtin.shell | False |

#### File: tasks/sub_tasks/admin/pg_admin.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Query Patroni cluster state from first postgres node | ansible.builtin.uri | False |
| Extract Patroni leader candidates | ansible.builtin.set_fact | False |
| Determine Patroni leader member | ansible.builtin.set_fact | True |
| Assert Patroni leader was found | ansible.builtin.assert | False |
| Build Patroni admin role flags | ansible.builtin.set_fact | False |
| Ensure dedicated Patroni admin role exists on leader | community.postgresql.postgresql_user | False |

#### File: tasks/sub_tasks/admin/pg_hba.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Patroni dynamic pg_hba ¦ Query Patroni cluster state from first postgres node | ansible.builtin.uri | False |
| Patroni dynamic pg_hba ¦ Extract Patroni leader candidates | ansible.builtin.set_fact | False |
| Patroni dynamic pg_hba ¦ Determine Patroni leader member | ansible.builtin.set_fact | False |
| Patroni dynamic pg_hba ¦ Assert Patroni leader was found | ansible.builtin.assert | False |
| Patroni dynamic pg_hba ¦ Build desired pg_hba rules | ansible.builtin.set_fact | False |
| Patroni dynamic pg_hba ¦ Read current dynamic config from leader | ansible.builtin.uri | False |
| Patroni dynamic pg_hba ¦ Determine whether pg_hba update is needed | ansible.builtin.set_fact | False |
| Patroni dynamic pg_hba ¦ Patch DCS config with desired pg_hba | ansible.builtin.uri | True |
| Patroni dynamic pg_hba ¦ Restart patroni on all postgres nodes if DCS config changed | ansible.builtin.service | True |
| Patroni dynamic pg_hba ¦ Wait for Patroni REST API on all postgres nodes | ansible.builtin.wait_for | True |
| Patroni dynamic pg_hba ¦ Wait for live pg_hba.conf to contain HAProxy rules on all nodes | ansible.builtin.command | True |

#### File: tasks/sub_tasks/admin/pg_uptime_kuma.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure Uptime Kuma monitor role exists on leader | community.postgresql.postgresql_user | False |
| Grant Uptime Kuma monitor role CONNECT on monitor database | community.postgresql.postgresql_privs | False |

#### File: tasks/sub_tasks/admin/reset_node.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Reset node ¦ Stop Patroni | ansible.builtin.systemd_service | False |
| Reset node ¦ Disable Patroni | ansible.builtin.systemd_service | False |
| Reset node ¦ Stop PostgreSQL | ansible.builtin.systemd_service | False |
| Reset node ¦ Disable PostgreSQL | ansible.builtin.systemd_service | False |
| Reset node ¦ Stop etcd | ansible.builtin.systemd_service | False |
| Reset node ¦ Disable etcd | ansible.builtin.systemd_service | False |
| Reset node ¦ Kill stray postgres/patroni/etcd processes | ansible.builtin.shell | False |
| Reset node ¦ Drop Debian PostgreSQL cluster if present | ansible.builtin.command | False |
| Reset node ¦ Remove Patroni config | ansible.builtin.file | False |
| Reset node ¦ Remove Patroni config dir leftovers | ansible.builtin.file | False |
| Reset node ¦ Remove PostgreSQL data dir | ansible.builtin.file | False |
| Reset node ¦ Remove Debian PostgreSQL config dir | ansible.builtin.file | False |
| Reset node ¦ Remove Debian PostgreSQL data root if still present | ansible.builtin.file | False |
| Reset node ¦ Remove PostgreSQL runtime sockets and pid files | ansible.builtin.shell | False |
| Reset node ¦ Optionally remove etcd data dir too | ansible.builtin.file | False |
| Reset node ¦ Reset failed systemd units | ansible.builtin.shell | False |
| Reset node ¦ Recreate Patroni PostgreSQL data dir | ansible.builtin.file | False |
| Reset node ¦ Recreate Patroni config dir | ansible.builtin.file | False |
| Reset node ¦ Recreate etcd data dir if keeping etcd | ansible.builtin.file | False |

#### File: tasks/sub_tasks/backup.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Logical backup run ¦ Query Patroni cluster state | ansible.builtin.uri | False |
| Logical backup run ¦ Select current Patroni leader | ansible.builtin.set_fact | False |
| Logical backup run ¦ Validate leader inventory mapping | ansible.builtin.assert | False |
| Logical backup run ¦ Invoke installed leader-gated runner | ansible.builtin.command | False |
| Logical backup run ¦ Report status and location | ansible.builtin.debug | False |

#### File: tasks/sub_tasks/backup_remote_action.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Remote logical backup action ¦ Validate explicit action | ansible.builtin.assert | False |
| Remote logical backup action ¦ Invoke host-local runner | ansible.builtin.command | False |
| Remote logical backup action ¦ Report result | ansible.builtin.debug | False |

#### File: tasks/sub_tasks/backup_remote_secret_reconcile.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Remote logical backup secret reconciliation ¦ Inspect managed-file manifest | ansible.builtin.stat | False |
| Remote logical backup secret reconciliation ¦ Validate managed-file manifest type | ansible.builtin.assert | False |
| Remote logical backup secret reconciliation ¦ Read managed-file manifest | ansible.builtin.slurp | True |
| Remote logical backup secret reconciliation ¦ Decode previously managed paths | ansible.builtin.set_fact | False |
| Remote logical backup secret reconciliation ¦ Validate previous managed paths | ansible.builtin.assert | False |
| Remote logical backup secret reconciliation ¦ Validate unique previous managed paths | ansible.builtin.assert | False |
| Remote logical backup secret reconciliation ¦ Remove obsolete managed secret files | ansible.builtin.file | False |
| Remote logical backup secret reconciliation ¦ Publish managed-file manifest atomically | ansible.builtin.copy | False |

#### File: tasks/sub_tasks/backup_remote_setup.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Remote logical backup ¦ Validate configuration | ansible.builtin.assert | False |  |
| Remote logical backup ¦ Validate backend environment entries | ansible.builtin.assert | False |  |
| Remote logical backup ¦ Validate backend secret declarations | ansible.builtin.assert | False |  |
| Remote logical backup ¦ Validate unique backend secret environment names | ansible.builtin.assert | False |  |
| Remote logical backup ¦ Validate secret file declarations | ansible.builtin.assert | False |  |
| Remote logical backup ¦ Validate unique secret file paths | ansible.builtin.assert | False |  |
| Remote logical backup ¦ Validate additional Restic options | ansible.builtin.assert | False |  |
| Remote logical backup ¦ Install Restic package | ansible.builtin.apt | True |  |
| Remote logical backup ¦ Query installed Restic version | ansible.builtin.command | True |  |
| Remote logical backup ¦ Require supported Restic version | ansible.builtin.assert | True |  |
| Remote logical backup ¦ Create protected configuration directory | ansible.builtin.file | True |  |
| Remote logical backup ¦ Create protected state directories | ansible.builtin.file | True |  |
| Remote logical backup ¦ Ensure PostgreSQL metrics directory exists | ansible.builtin.file | True |  |
| Remote logical backup ¦ Pre-create remote metrics file | ansible.builtin.file | True |  |
| Remote logical backup ¦ Reset resolved credential state | ansible.builtin.set_fact | True |  |
| Remote logical backup ¦ Resolve repository password through controller Infisical parameters | ansible.builtin.set_fact | True |  |
| Remote logical backup ¦ Resolve backend environment secrets through controller | ansible.builtin.set_fact | True |  |
| Remote logical backup ¦ Resolve backend secret files through controller | ansible.builtin.set_fact | True |  |
| Remote logical backup ¦ Build deterministic check-mode credentials | ansible.builtin.set_fact | True |  |
| Remote logical backup ¦ Build deterministic check-mode backend secrets | ansible.builtin.set_fact | True |  |
| Remote logical backup ¦ Build deterministic check-mode secret files | ansible.builtin.set_fact | True |  |
| Remote logical backup ¦ Validate resolved credentials | ansible.builtin.assert | True |  |
| Remote logical backup ¦ Write repository location | ansible.builtin.copy | True |  |
| Remote logical backup ¦ Write repository password | ansible.builtin.copy | True |  |
| Remote logical backup ¦ Write protected backend environment | ansible.builtin.template | True |  |
| Remote logical backup ¦ Write protected backend secret files | ansible.builtin.copy | True |  |
| Remote logical backup ¦ Remove inactive core credential files | ansible.builtin.file | True |  |
| Remote logical backup ¦ Remove declared inactive secret files | ansible.builtin.file | True |  |
| Remote logical backup ¦ Build desired managed secret-file paths | ansible.builtin.set_fact | True |  |
| Remote logical backup ¦ Reconcile managed secret files | ansible.builtin.include_tasks | True |  |
| Remote logical backup ¦ Install host-local runner | ansible.builtin.template | True |  |
| Remote logical backup ¦ Manage uploader systemd job | ansible.builtin.include_role | False |  |
| Remote logical backup ¦ Manage maintenance systemd job | ansible.builtin.include_role | False |  |

#### File: tasks/sub_tasks/backup_restore_validation_action.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Backup restore validation action ¦ Validate explicit action | ansible.builtin.assert | False |
| Backup restore validation action ¦ Invoke host-local runner | ansible.builtin.command | False |
| Backup restore validation action ¦ Report result | ansible.builtin.debug | False |

#### File: tasks/sub_tasks/backup_restore_validation_setup.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Backup restore validation ¦ Validate configuration | ansible.builtin.assert | False |  |
| Backup restore validation ¦ Create protected work root | ansible.builtin.file | True |  |
| Backup restore validation ¦ Ensure PostgreSQL metrics directory exists | ansible.builtin.file | True |  |
| Backup restore validation ¦ Pre-create metrics file | ansible.builtin.file | True |  |
| Backup restore validation ¦ Install host-local runner | ansible.builtin.template | True |  |
| Backup restore validation ¦ Manage systemd job | ansible.builtin.include_role | False |  |

#### File: tasks/sub_tasks/backup_setup.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Logical backup ¦ Validate configuration | ansible.builtin.assert | False |  |
| Logical backup ¦ Create protected backup root | ansible.builtin.file | False |  |
| Logical backup ¦ Create empty protected libpq password file | ansible.builtin.copy | False |  |
| Logical backup ¦ Ensure dedicated metrics directory exists | ansible.builtin.file | False |  |
| Logical backup ¦ Pre-create narrowly writable metrics file | ansible.builtin.file | False |  |
| Logical backup ¦ Install host-local runner | ansible.builtin.template | False |  |
| Logical backup ¦ Manage systemd service and timer | ansible.builtin.include_role | False |  |

#### File: tasks/sub_tasks/install/apt.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Ensure PostgreSQL common prerequisites are installed | ansible.builtin.apt | False |
| Ensure PGDG keyring directory exists | ansible.builtin.file | False |
| Download PGDG repository signing key | ansible.builtin.get_url | False |
| Add PGDG repository | ansible.builtin.apt_repository | False |
| Install PostgreSQL common packages first | ansible.builtin.apt | False |
| Disable automatic Debian PostgreSQL cluster creation | ansible.builtin.lineinfile | False |
| Set default PostgreSQL start_conf to manual | ansible.builtin.lineinfile | False |
| Install PostgreSQL Patroni, and etcd packages | ansible.builtin.apt | False |

#### File: tasks/sub_tasks/install/etcd.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Assert etcd vars are defined | ansible.builtin.assert | False | postgres,postgres_etcd |
| Stop etcd before optional reset | ansible.builtin.systemd_service | False | p,o,s,t,g,r,e,s,_,e,t,c,d,_,r,e,s,e,t |
| Remove etcd data directory for reset | ansible.builtin.file | False | p,o,s,t,g,r,e,s,_,e,t,c,d,_,r,e,s,e,t |
| Ensure etcd data directory exists | ansible.builtin.file | False | postgres,postgres_etcd |
| Template etcd defaults | ansible.builtin.template | False | postgres,postgres_etcd |
| Enable and start etcd | ansible.builtin.systemd_service | False | postgres,postgres_etcd |
| Wait for etcd client port | ansible.builtin.wait_for | False | postgres,postgres_etcd |

#### File: tasks/sub_tasks/install/patroni.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Ensure Patroni config directory exists | ansible.builtin.file | False | postgres,postgres_patroni |
| Stop Patroni before optional reset | ansible.builtin.systemd_service | False | p,o,s,t,g,r,e,s,_,p,a,t,r,o,n,i,_,r,e,s,e,t |
| Stop default PostgreSQL service before optional reset | ansible.builtin.systemd_service | False | p,o,s,t,g,r,e,s,_,p,a,t,r,o,n,i,_,r,e,s,e,t |
| Drop default Debian PostgreSQL cluster | ansible.builtin.command | False | p,o,s,t,g,r,e,s,_,p,a,t,r,o,n,i,_,r,e,s,e,t |
| Ensure Patroni PostgreSQL data directory exists | ansible.builtin.file | False | postgres,postgres_patroni |
| Stop and disable default PostgreSQL service | ansible.builtin.systemd_service | False | postgres,postgres_patroni |
| Template Patroni config | ansible.builtin.template | False | postgres,postgres_patroni |
| Enable and start Patroni | ansible.builtin.systemd_service | False | postgres,postgres_patroni |
| Wait for Patroni REST API | ansible.builtin.wait_for | False | postgres,postgres_patroni |

#### File: tasks/sub_tasks/restore.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Restore DBs ¦ Assert restore map and restore dir are provided | ansible.builtin.assert | False |
| Restore DBs ¦ Validate restore map entries | ansible.builtin.assert | False |
| Restore DBs ¦ Query Patroni cluster state from first postgres node | ansible.builtin.uri | False |
| Restore DBs ¦ Extract Patroni leader candidates | ansible.builtin.set_fact | False |
| Restore DBs ¦ Determine Patroni leader member | ansible.builtin.set_fact | False |
| Restore DBs ¦ Assert Patroni leader was found | ansible.builtin.assert | False |
| Restore DBs ¦ Build resolved restore map | ansible.builtin.set_fact | False |
| Restore DBs ¦ Check requested dump files exist | ansible.builtin.stat | False |
| Restore DBs ¦ Assert requested dump files exist | ansible.builtin.assert | False |
| Restore DBs ¦ Drop databases if requested | ansible.builtin.shell | True |
| Restore DBs ¦ Create databases | community.postgresql.postgresql_db | False |
| Restore DBs ¦ Restore each database | ansible.builtin.shell | False |
| Restore DBs ¦ Show result | ansible.builtin.debug | False |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
