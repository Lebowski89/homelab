````md
## Infrastructure (Homelab) by Code

- Driven by Ansible, Infisical and Docker Swarm
- Media-centric by nature
- Built around the arrs and various companion apps

```mermaid
flowchart TB
  subgraph Unraid["UnRaid VM (Swarm Worker)"]
    Lidarr
    Prowlarr
    Radarr
    Sonarr
    Whisparr
    Sportarr
    qBittorrent
    SABnzbd
    Stash
  end

  subgraph Manager["Manager VM (Swarm & Ansible Manager)"]
    Authelia
    Jellyseerr
    ZNC
    TheLounge
    Infisical
    HomePage
    Ombi
    Vaultwarden
  end

  subgraph Plex["Plex Mini-PC (Swarm Worker)"]
    Kometa
    ImageMaid
    PlexApp["Plex"]
    Tautulli
  end

  subgraph PG["Postgres Cluster (HA Cluster)"]
    pg01["pg01: etcd + postgres + patroni"]
    pg02["pg02: etcd + postgres + patroni"]
    pg03["pg03: etcd + postgres + patroni"]
  end

  HAProxy["HAProxy (Swarm services on Unraid/Manager/Plex)"]
  HAProxy --> PG
  Unraid --> HAProxy
  Manager --> HAProxy
  Plex --> HAProxy
