<!-- DOCSIBLE START -->

# 📃 Role overview

## postgres





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/08/11 |








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
| [postgres_patroni_scope](defaults/main.yml#L24)   | str | `pg-cluster` |    
| [postgres_patroni_namespace](defaults/main.yml#L25)   | str | `/service` |    
| [postgres_patroni_node_name](defaults/main.yml#L26)   | str | `{{ inventory_hostname }}` |    
| [postgres_patroni_config_dir](defaults/main.yml#L28)   | str | `/etc/patroni` |    
| [postgres_patroni_config_path](defaults/main.yml#L29)   | str | `{{ postgres_patroni_config_dir }}/config.yml` |    
| [postgres_patroni_data_dir](defaults/main.yml#L30)   | str | `/var/lib/postgresql/{{ postgres_version }}/main` |    
| [postgres_patroni_bin_dir](defaults/main.yml#L31)   | str | `/usr/lib/postgresql/{{ postgres_version }}/bin` |    
| [postgres_patroni_restapi_port](defaults/main.yml#L32)   | int | `8008` |    
| [postgres_patroni_postgres_port](defaults/main.yml#L33)   | int | `5432` |    
| [postgres_patroni_superuser_name](defaults/main.yml#L39)   | str | `postgres` |    
| [postgres_patroni_superuser_pass](defaults/main.yml#L40)   | str |  |    
| [postgres_patroni_replication_name](defaults/main.yml#L42)   | str | `replicator` |    
| [postgres_patroni_replication_pass](defaults/main.yml#L43)   | str |  |    
| [postgres_patroni_admin_role_name](defaults/main.yml#L45)   | str | `admin` |    
| [postgres_patroni_admin_role_pass](defaults/main.yml#L46)   | str |  |    
| [postgres_patroni_admin_role_login](defaults/main.yml#L47)   | bool | `True` |    
| [postgres_patroni_admin_role_createdb](defaults/main.yml#L48)   | bool | `True` |    
| [postgres_patroni_admin_role_createrole](defaults/main.yml#L49)   | bool | `False` |    
| [postgres_patroni_etcd_hosts](defaults/main.yml#L51)   | list | `[]` |    
| [postgres_patroni_pg_hba_extra](defaults/main.yml#L52)   | list | `[]` |    
| [postgres_uptime_kuma_monitor_role_name](defaults/main.yml#L58)   | str | `uptime_kuma_monitor` |    
| [postgres_uptime_kuma_monitor_role_pass](defaults/main.yml#L59)   | str |  |    
| [postgres_uptime_kuma_monitor_database](defaults/main.yml#L60)   | str | `postgres` |    
| [postgres_backup_root](defaults/main.yml#L66)   | str | `/var/backups/postgresql` |    
| [postgres_backup_script_path](defaults/main.yml#L67)   | str | `/usr/local/sbin/postgres-logical-backup` |    
| [postgres_backup_manage_timer](defaults/main.yml#L68)   | bool | `False` |    
| [postgres_backup_timer_name](defaults/main.yml#L69)   | str | `postgres-logical-backup` |    
| [postgres_backup_timer_on_calendar](defaults/main.yml#L70)   | str | `*-*-* 03:00:00` |    
| [postgres_backup_timer_randomized_delay_sec](defaults/main.yml#L71)   | str | `30m` |    
| [postgres_backup_local_retention_days](defaults/main.yml#L72)   | int | `7` |    
| [postgres_backup_failed_retention_days](defaults/main.yml#L73)   | int | `2` |    
| [postgres_backup_metrics_file](defaults/main.yml#L74)   | str | `/var/lib/node_exporter/textfile_collector/postgres_logical_backup.prom` |    
| [postgres_restore_dbs_dir](defaults/main.yml#L80)   | str | `/tmp` |    
| [postgres_restore_dbs_drop_existing](defaults/main.yml#L81)   | bool | `True` |    
| [postgres_restore_dbs_map](defaults/main.yml#L86)   | list | `[]` |    
| [postgres_fix_owner_map](defaults/main.yml#L101)   | list | `[]` |    





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

#### File: tasks/sub_tasks/backup_setup.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Logical backup ¦ Validate configuration | ansible.builtin.assert | False |  |
| Logical backup ¦ Create protected backup root | ansible.builtin.file | False |  |
| Logical backup ¦ Ensure textfile collector directory exists | ansible.builtin.file | False |  |
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
