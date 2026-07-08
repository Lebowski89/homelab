<!-- DOCSIBLE START -->

# 📃 Role overview

## postgres





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/07/09 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [postgres_version](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L7)   | int | `18` |    
| [postgres_etcd_data_dir](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L13)   | str | `/var/lib/etcd` |    
| [postgres_etcd_client_port](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L14)   | int | `2379` |    
| [postgres_etcd_peer_port](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L15)   | int | `2380` |    
| [postgres_etcd_cluster_token](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L16)   | str | `pg-ha-1` |    
| [postgres_etcd_initial_cluster](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L18)   | list | `[]` |    
| [postgres_patroni_scope](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L24)   | str | `pg-cluster` |    
| [postgres_patroni_namespace](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L25)   | str | `/service` |    
| [postgres_patroni_node_name](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L26)   | str | `{{ inventory_hostname }}` |    
| [postgres_patroni_config_dir](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L28)   | str | `/etc/patroni` |    
| [postgres_patroni_config_path](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L29)   | str | `{{ postgres_patroni_config_dir }}/config.yml` |    
| [postgres_patroni_data_dir](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L30)   | str | `/var/lib/postgresql/{{ postgres_version }}/main` |    
| [postgres_patroni_bin_dir](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L31)   | str | `/usr/lib/postgresql/{{ postgres_version }}/bin` |    
| [postgres_patroni_restapi_port](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L32)   | int | `8008` |    
| [postgres_patroni_postgres_port](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L33)   | int | `5432` |    
| [postgres_patroni_superuser_name](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L39)   | str | `postgres` |    
| [postgres_patroni_superuser_pass](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L40)   | str |  |    
| [postgres_patroni_replication_name](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L42)   | str | `replicator` |    
| [postgres_patroni_replication_pass](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L43)   | str |  |    
| [postgres_patroni_admin_role_name](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L45)   | str | `admin` |    
| [postgres_patroni_admin_role_pass](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L46)   | str |  |    
| [postgres_patroni_admin_role_login](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L47)   | bool | `True` |    
| [postgres_patroni_admin_role_createdb](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L48)   | bool | `True` |    
| [postgres_patroni_admin_role_createrole](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L49)   | bool | `False` |    
| [postgres_patroni_etcd_hosts](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L51)   | list | `[]` |    
| [postgres_patroni_pg_hba_extra](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L52)   | list | `[]` |    
| [postgres_uptime_kuma_monitor_role_name](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L58)   | str | `uptime_kuma_monitor` |    
| [postgres_uptime_kuma_monitor_role_pass](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L59)   | str |  |    
| [postgres_uptime_kuma_monitor_database](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L60)   | str | `postgres` |    
| [postgres_backup_dir](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L72)   | str | `/tmp` |    
| [postgres_backup_dbs](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L73)   | list | `[]` |    
| [postgres_backup_dbs_dir](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L74)   | str | `{{ postgres_backup_dir }}` |    
| [postgres_backup_dbs_format](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L75)   | str | `custom` |    
| [postgres_restore_dbs_dir](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L81)   | str | `/tmp` |    
| [postgres_restore_dbs_drop_existing](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L82)   | bool | `True` |    
| [postgres_restore_dbs_map](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L87)   | list | `[]` |    
| [postgres_fix_owner_map](https://github.com/Lebowski89/homelab/blob/feat/github-repo-governance/defaults/main.yml#L102)   | list | `[]` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Install postgres packages | ansible.builtin.include_tasks | True | postgres,postgres_apt |
| Configure etcd | ansible.builtin.include_tasks | True | postgres,postgres_etcd,postgres_etcd_reset |
| Configure Patroni | ansible.builtin.include_tasks | True | postgres,postgres_patroni,postgres_patroni_reset |
| Ensure dedicated PostgreSQL admin role exists | ansible.builtin.include_tasks | True | postgres_admin,postgres_admin_uptime_kuma |
| Ensure dedicated PostgreSQL Uptime Kuma role exists | ansible.builtin.include_tasks | True | p,o,s,t,g,r,e,s,_,a,d,m,i,n,_,u,p,t,i,m,e,_,k,u,m,a |
| Backup PostgreSQL single database with pg_dump | ansible.builtin.include_tasks | True | p,o,s,t,g,r,e,s,_,b,a,c,k,u,p |
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
| Backup DBs ¦ Assert database list is provided | ansible.builtin.assert | False |
| Backup DBs ¦ Query Patroni cluster state from first postgres node | ansible.builtin.uri | False |
| Backup DBs ¦ Extract Patroni leader candidates | ansible.builtin.set_fact | False |
| Backup DBs ¦ Determine Patroni leader member | ansible.builtin.set_fact | False |
| Backup DBs ¦ Build timestamp | ansible.builtin.set_fact | False |
| Backup DBs ¦ Set output extension | ansible.builtin.set_fact | False |
| Backup DBs ¦ Ensure backup directory exists on leader | ansible.builtin.file | False |
| Backup DBs ¦ Dump each database in custom format | ansible.builtin.shell | True |
| Backup DBs ¦ Dump each database in plain SQL format | ansible.builtin.shell | True |
| Backup DBs ¦ Show result | ansible.builtin.debug | False |

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
