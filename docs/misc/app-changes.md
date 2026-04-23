# App Changes

## 04.2026 - Done with Discord

<img width="30%" height="30%" alt="f5cc8414-dbcd-470e-9f0d-bf4336a6fc2d" src="https://github.com/user-attachments/assets/746d37cd-d3c9-4ec2-8285-1a47f57973dc" />

I've removed Discord-focussed apps, including Doplarr and Notifiarr. I realised that I... I just don't like Discord. This was not much of a loss - function-wise, as I use Recyclarr to add custom formats to radarr/sonarr, and Gotify covers notifications.

## 04.2026 - Gettin qui with it...

Made by those behind autobrr, 'qui' has been a fantastic addition. I knew it would be good, but I didn't anticipate how quickly its functionality would expand. It now covers the functionality of cross-seed and qBit-Manage, so I've retired and removed them.

<img width="565" height="80%" alt="apkeqx1" src="https://github.com/user-attachments/assets/1229425b-dbc6-4fe5-8e7b-289625c0dc7d" />

## 04.2026 - Spilo

I have now finally migrated to a non-container Postgres cluster (via the postgres ansible role). This replaces my Spilo cluster. I was motivated to do this for the following reasons:

1. Those maintaining the Spilo project have put it on the backburner. Though, it still receives updates here and there (Postgres 18 support was added recently) that you can build, it's obvious that it's just not a priority.
2. There just wasn't much benefit gained by running them in a container. I run the cluster across three Ubuntu 24.04 VMs that are purpose built for the cluster. Nothing else are on these VM. These VM were never joined as Swarm workers. 

The new Postgres role has tasks to install postgres, etcd, patroni. It has tasks to dump and restore databases, and various helpful admin tasks (such as changing database ownership). As with the other roles, it is driven by various run tags and host groups.

<details>
<summary>Retired etcd Service Vars</summary>
```bash
etcd:
  name: etcd
  stack: pg-etcd
  container_name: etcd
  image: quay.io/coreos/etcd:v3.5.27
  network_mode: host
  paths:
    - path: /opt/etcd
      state: directory
      owner: 1000
      group: 1000
      mode: "0755"
    - path: /opt/etcd/data
      state: directory
      owner: 1000
      group: 1000
      mode: "0755"
  volumes:
    data:
      type: bind
      source: /opt/etcd/data
      target: /var/lib/etcd
      read_only: false
  user: 1000:1000
  targets:
    pg01:
      environment:
        ETCD_NAME: "pg01"
        ETCD_DATA_DIR: "/var/lib/etcd"
        ETCD_LISTEN_CLIENT_URLS: "http://192.168.80.92:2379,http://127.0.0.1:2379"
        ETCD_ADVERTISE_CLIENT_URLS: "http://192.168.80.92:2379"
        ETCD_LISTEN_PEER_URLS: "http://192.168.80.92:2380"
        ETCD_INITIAL_ADVERTISE_PEER_URLS: "http://192.168.80.92:2380"
        ETCD_INITIAL_CLUSTER: "pg01=http://192.168.80.92:2380,pg02=http://192.168.80.93:2380,pg03=http://192.168.80.94:2380"
        ETCD_INITIAL_CLUSTER_STATE: "new"
        ETCD_INITIAL_CLUSTER_TOKEN: "pg-ha-1"
        ETCD_ENABLE_V2: "true"
      deploy:
        type: container
        host: pg01
    pg02:
      environment:
        ETCD_NAME: "pg02"
        ETCD_DATA_DIR: "/var/lib/etcd"
        ETCD_LISTEN_CLIENT_URLS: "http://192.168.80.93:2379,http://127.0.0.1:2379"
        ETCD_ADVERTISE_CLIENT_URLS: "http://192.168.80.93:2379"
        ETCD_LISTEN_PEER_URLS: "http://192.168.80.93:2380"
        ETCD_INITIAL_ADVERTISE_PEER_URLS: "http://192.168.80.93:2380"
        ETCD_INITIAL_CLUSTER: "pg01=http://192.168.80.92:2380,pg02=http://192.168.80.93:2380,pg03=http://192.168.80.94:2380"
        ETCD_INITIAL_CLUSTER_STATE: "new"
        ETCD_INITIAL_CLUSTER_TOKEN: "pg-ha-1"
        ETCD_ENABLE_V2: "true"
      deploy:
        type: container
        host: pg02
    pg03:
      environment:
        ETCD_NAME: "pg03"
        ETCD_DATA_DIR: "/var/lib/etcd"
        ETCD_LISTEN_CLIENT_URLS: "http://192.168.80.94:2379,http://127.0.0.1:2379"
        ETCD_ADVERTISE_CLIENT_URLS: "http://192.168.80.94:2379"
        ETCD_LISTEN_PEER_URLS: "http://192.168.80.94:2380"
        ETCD_INITIAL_ADVERTISE_PEER_URLS: "http://192.168.80.94:2380"
        ETCD_INITIAL_CLUSTER: "pg01=http://192.168.80.92:2380,pg02=http://192.168.80.93:2380,pg03=http://192.168.80.94:2380"
        ETCD_INITIAL_CLUSTER_STATE: "new"
        ETCD_INITIAL_CLUSTER_TOKEN: "pg-ha-1"
        ETCD_ENABLE_V2: "true"
      deploy:
        type: container
        host: pg03
```
</details>

<details>
<summary>Retired Spilo Service Vars</summary>
```bash
spilo:
  name: spilo
  stack: spilo
  container_name: spilo
  image: ghcr.io/zalando/spilo-17:4.0-p3
  network_mode: host
  pid: host
  cap_add:
    - SYS_NICE
    - IPC_LOCK
  security_opt:
    - "apparmor:unconfined"
  infisical:
    fail_on_empty: true
    secrets_map:
      - var: spilo_superuser_pass
        path: "/Spilo"
        name: SUPERUSER_PASS
      - var: spilo_replication_pass
        path: "/Spilo"
        name: REPLICATION_PASS
  paths:
    - path: /opt/spilo/data
      state: directory
      owner: 1000
      group: 1000
      mode: "0755"
  volumes:
    data:
      type: bind
      source: /opt/spilo/data
      target: /home/postgres/pgroot
      read_only: false
  targets:
    pg01:
      environment:
        SCOPE: "pg-cluster"
        ETCD_HOSTS: '"192.168.80.92:2379","192.168.80.93:2379","192.168.80.94:2379"'
        SPILO_CONFIGURATION: >-
          {{
            {
              "restapi": {
              "listen": "0.0.0.0:8008",
              "connect_address": "192.168.80.92:8008"
              },
              "postgresql": {
              "listen": "0.0.0.0:5433",
              "connect_address": "192.168.80.92:5433"
              }
            } | to_json
          }}
        APIPORT: "8008"
        spilo_NAME: "pg01"
        RESTAPI_CONNECT_ADDRESS: "192.168.80.92:8008"
        PGPORT: "5433"
        PGROOT: "/home/postgres/pgroot"
        PGDATA: "/home/postgres/pgroot/pgdata"
        ALLOW_NOSSL: "true"
        # Users / Passwords
        PGUSER_SUPERUSER: "postgres"
        PGPASSWORD_SUPERUSER: "{{ spilo_superuser_pass | default('__INFISICAL__:spilo_superuser_pass', true) }}"
        PGUSER_STANDBY: "replicator"
        PGPASSWORD_STANDBY: "{{ spilo_replication_pass | default('__INFISICAL__:spilo_replication_pass', true) }}"
        # Optional: don’t create the extra admin user
        USE_ADMIN: "false"
      deploy:
        type: container
        host: pg01
    pg02:
      environment:
        SCOPE: "pg-cluster"
        ETCD_HOSTS: '"192.168.80.92:2379","192.168.80.93:2379","192.168.80.94:2379"'
        SPILO_CONFIGURATION: >-
          {{
            {
              "restapi": {
              "listen": "0.0.0.0:8008",
              "connect_address": "192.168.80.93:8008"
              },
              "postgresql": {
              "listen": "0.0.0.0:5433",
              "connect_address": "192.168.80.93:5433"
              }
            } | to_json
          }}
        APIPORT: "8008"
        spilo_NAME: "pg02"
        RESTAPI_CONNECT_ADDRESS: "192.168.80.93:8008"
        PGPORT: "5433"
        PGROOT: "/home/postgres/pgroot"
        PGDATA: "/home/postgres/pgroot/pgdata"
        ALLOW_NOSSL: "true"
        STANDBY_HOST: "192.168.80.92"
        STANDBY_PORT: "5433"
        # Users / Passwords
        PGUSER_SUPERUSER: "postgres"
        PGPASSWORD_SUPERUSER: "{{ spilo_superuser_pass | default('__INFISICAL__:spilo_superuser_pass', true) }}"
        PGUSER_STANDBY: "replicator"
        PGPASSWORD_STANDBY: "{{ spilo_replication_pass | default('__INFISICAL__:spilo_replication_pass', true) }}"
        # Optional: don’t create the extra admin user
        USE_ADMIN: "false"
      deploy:
        type: container
        host: pg02
    pg03:
      environment:
        SCOPE: "pg-cluster"
        ETCD_HOSTS: '"192.168.80.92:2379","192.168.80.93:2379","192.168.80.94:2379"'
        SPILO_CONFIGURATION: >-
          {{
            {
              "restapi": {
              "listen": "0.0.0.0:8008",
              "connect_address": "192.168.80.94:8008"
              },
              "postgresql": {
              "listen": "0.0.0.0:5433",
              "connect_address": "192.168.80.94:5433"
              }
            } | to_json
          }}
        APIPORT: "8008"
        spilo_NAME: "pg03"
        RESTAPI_CONNECT_ADDRESS: "192.168.80.94:8008"
        PGPORT: "5433"
        PGROOT: "/home/postgres/pgroot"
        PGDATA: "/home/postgres/pgroot/pgdata"
        ALLOW_NOSSL: "true"
        STANDBY_HOST: "192.168.80.92"
        STANDBY_PORT: "5433"
        # Users / Passwords
        PGUSER_SUPERUSER: "postgres"
        PGPASSWORD_SUPERUSER: "{{ spilo_superuser_pass | default('__INFISICAL__:spilo_superuser_pass', true) }}"
        PGUSER_STANDBY: "replicator"
        PGPASSWORD_STANDBY: "{{ spilo_replication_pass | default('__INFISICAL__:spilo_replication_pass', true) }}"
        # Optional: don’t create the extra admin user
        USE_ADMIN: "false"
      deploy:
        type: container
        host: pg03
```
</details>
