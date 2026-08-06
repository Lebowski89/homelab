## <img width="80%" alt="homelab_repo_banner_cropped" src="https://github.com/user-attachments/assets/ac402bb7-f469-44cf-a602-ff3ddf2c4160" />

- Powered by Ansible <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/ansible.svg" alt="Ansible" width="24" />, Docker <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/docker.svg" alt="Docker" width="24" /> / Podman <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/podman.svg" alt="Podman" width="24" /> and OpenTofu <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/opentofu.svg" alt="OpenTofu" width="24" />
- Uses Ansible Vault and Infisical <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/infisical.svg" alt="Infisical" width="24" /> for secrets management
- Uses NetBox <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/netbox.svg" alt="NetBox" width="24" /> and its Ansible plugin for Ansible inventory management
- Uses Authelia <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/authelia.svg" alt="Authelia" width="24" /> and Traefik <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/traefik.svg" alt="Traefik" width="24" /> for SSO and reverse proxy
- Uses highly available PostgreSQL <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/postgresql.svg" alt="PostgreSQL" width="24" /> (PostgreSQL + Patroni + etcd + HAProxy)
- Uses Technitium <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/technitium.svg" alt="Technitium" width="24" /> cluster for recursive DNS + Internal-DNS records
- Strong focus on media-centric services, especially arrs apps and companion services

## Goals

- Automate deployment of Proxmox VMs <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/proxmox.svg" alt="Proxmox" width="24" />
- Automate deployment of apps and services, primarily via Docker and Podman
- Automate app settings, configs, databases and other needs in a single Ansible or OpenTofu run
- Run on fresh Debian-based <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/debian.svg" alt="Debian" width="24" /> OS/VM and reliably deploy an app or service with my preferred settings

## Disclaimer

1. This repo is built by me, for me. It is what I use to run my homelab.
2. It is subject to frequent, unannounced changes, and I do sometimes break things.
3. I keep it public to show what can be achieved with common homelab tools, because one of the best ways to learn is by seeing how others approach problems.
4. This is not a plug-and-play repo. Anyone using parts of it should expect to adapt it heavily for their own environment.

## Support

This is a personal homelab repository and is shared for reference only.

I’m not able to provide general support for Proxmox, Terraform/OpenTofu providers, Docker images, or third-party applications used here. For issues with upstream tools or applications, please open an issue with the relevant project.

## Coffee

<a href="https://buymeacoffee.com/lebowski89" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee" style="height: 41px !important;width: 174px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;" ></a>

## Apps in Use

(Logos sourced from selfh.st <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/selfh-st.svg" alt="selfh-st" width="24" />)

<table>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/adminer.svg" alt="Adminer" width="36"><br>Adminer</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/authelia.svg" alt="Authelia" width="36"><br>Authelia</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/autobrr.svg" alt="Autobrr" width="36"><br>autobrr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/bazarr.svg" alt="Bazarr" width="36"><br>Bazarr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/czkawka.svg" alt="Czkawka" width="36"><br>Czkawka</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/crowdsec.svg" alt="CrowdSec" width="36"><br>CrowdSec</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/gitea.svg" alt="Gitea" width="36"><br>Gitea</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/gotify.svg" alt="Gotify" width="36"><br>Gotify</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/grafana.svg" alt="Grafana" width="36"><br>Grafana</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/grafana-alloy.svg" alt="Grafana Alloy" width="36"><br>Grafana Alloy</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/haproxy.svg" alt="HAProxy" width="36"><br>HAProxy</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/homepage.svg" alt="Homepage" width="36"><br>HomePage</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/hugo.svg" alt="Hugo" width="36"><br>Hugo</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/kometa.svg" alt="Kometa" width="36"><br>Kometa</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/lidarr.svg" alt="Lidarr" width="36"><br>Lidarr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/loki.svg" alt="Loki" width="36"><br>Loki</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/mariadb.svg" alt="MariaDB" width="36"><br>MariaDB</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/netbox.svg" alt="NetBox" width="36"><br>NetBox</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/png/nzbhydra.png" alt="NZBHydra" width="36"><br>NZBHydra-2</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/obsidian.svg" alt="Obsidian" width="36"><br>Obsidian</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/ombi.svg" alt="Ombi" width="36"><br>Ombi</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/opencloud.svg" alt="OpenCloud" width="36"><br>OpenCloud</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/plex.svg" alt="Plex" width="36"><br>Plex</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/portainer.svg" alt="Portainer" width="36"><br>Portainer</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/prometheus.svg" alt="Prometheus" width="36"><br>Prometheus</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/prowlarr.svg" alt="Prowlarr" width="36"><br>Prowlarr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/qbittorrent.svg" alt="qBittorrent" width="36"><br>qBittorrent</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/qui.svg" alt="QUI" width="36"><br>qui</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/radarr.svg" alt="Radarr" width="36"><br>Radarr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/recyclarr.svg" alt="Recyclarr" width="36"><br>Recyclarr</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/romm-snes.svg" alt="RomM" width="36"><br>RomM</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/sabnzbd.svg" alt="SABnzbd" width="36"><br>SABnzbd</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/scraparr.svg" alt="Scraparr" width="36"><br>Scraparr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/seerr.svg" alt="Seerr" width="36"><br>Seerr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/sonarr.svg" alt="Sonarr" width="36"><br>Sonarr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/sportarr.svg" alt="Sportarr" width="36"><br>Sportarr</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/stash.svg" alt="Stash" width="36"><br>Stash</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/syncthing.svg" alt="Syncthing" width="36"><br>SyncThing</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/tautulli.svg" alt="Tautulli" width="36"><br>Tautulli</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/technitium.svg" alt="Technitium" width="36"><br>Technitium</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/the-lounge.svg" alt="The Lounge" width="36"><br>TheLounge</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/png/theme-park.png" alt="Theme Park" width="36"><br>ThemePark</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/traefik.svg" alt="Traefik" width="36"><br>Traefik</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/uptime-kuma.svg" alt="Uptime Kuma" width="36"><br>Uptime-Kuma</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/ubiquiti-unifi.svg" alt="UniFi" width="36"><br>Unifi-OS</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/webp/unpackerr.webp" alt="Unpackerr" width="36"><br>Unpackerr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/valkey.svg" alt="Valkey" width="36"><br>Valkey</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/vaultwarden.svg" alt="Vaultwarden" width="36"><br>Vaultwarden</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/whisparr.svg" alt="Whisparr" width="36"><br>Whisparr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/wallos.svg" alt="Wallos" width="36"><br>Wallos</td>    
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/webp/znc.webp" alt="ZNC" width="36"><br>Znc</td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
</table>
