## <img width="80%" alt="homelab_repo_banner_cropped" src="https://github.com/user-attachments/assets/ac402bb7-f469-44cf-a602-ff3ddf2c4160" />

- Powered by Ansible <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/ansible.svg" alt="Ansible" width="24" />, Docker <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/docker.svg" alt="Docker" width="24" /> and Terraform <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/hashicorp-terraform.svg" alt="Terraform" width="24" />
- Uses Ansible Vault and Infisical <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/infisical.svg" alt="Infisical" width="24" /> for secrets management
- Uses Authelia <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/authelia.svg" alt="Authelia" width="24" /> and Traefik <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/traefik.svg" alt="Traefik" width="24" /> for SSO and reverse proxy
- Uses highly available PostgreSQL <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/postgresql.svg" alt="PostgreSQL" width="24" /> (PostgreSQL + Patroni + etcd + HAProxy)
- Strong focus on media-centric services, especially arrs apps and companion services

## Goals

- Automate deployment of Proxmox VMs <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/proxmox.svg" alt="Proxmox" width="24" />
- Automate deployment of apps and services, primarily via Docker and Docker Swarm
- Automate app settings, configs, databases and other needs in a single Ansible run
- Run on fresh Debian-based <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/debian.svg" alt="Debian" width="24" /> OS/VM and reliably deploy an app or service with my preferred settings

## Disclaimer

1. This repo is built by me, for me. It is what I use to run my homelab.
2. It is subject to frequent, unannounced changes, and I do sometimes break things.
3. I keep it public to show what can be achieved with common homelab tools, because one of the best ways to learn is by seeing how others approach problems.
4. This is not a plug-and-play repo. Anyone using parts of it should expect to adapt it heavily for their own environment.

## Support

<a href="https://buymeacoffee.com/lebowski89" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee" style="height: 41px !important;width: 174px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;" ></a>

## Apps in Use

(Logos sourced from selfh.st <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/selfh-st.svg" alt="selfh-st" width="24" />)

<table>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/adminer.svg" alt="Adminer" width="36"><br>adminer</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/authelia.svg" alt="Authelia" width="36"><br>authelia</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/autobrr.svg" alt="Autobrr" width="36"><br>autobrr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/png/autopulse.png" alt="Autopulse" width="36"><br>autopulse</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/bazarr.svg" alt="Bazarr" width="36"><br>bazarr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/czkawka.svg" alt="Czkawka" width="36"><br>czkawka</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/gitea.svg" alt="Gitea" width="36"><br>gitea</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/gluetun.svg" alt="Gluetun" width="36"><br>gluetun</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/gotify.svg" alt="Gotify" width="36"><br>gotify</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/grafana.svg" alt="Grafana" width="36"><br>grafana</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/grafana-alloy.svg" alt="Grafana Alloy" width="36"><br>grafana alloy</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/haproxy.svg" alt="HAProxy" width="36"><br>haproxy</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/homepage.svg" alt="Homepage" width="36"><br>homepage</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/hugo.svg" alt="Hugo" width="36"><br>hugo</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/png/jdownloader.png" alt="JDownloader" width="36"><br>jdownloader2</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/kometa.svg" alt="Kometa" width="36"><br>kometa</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/librewolf.svg" alt="LibreWolf" width="36"><br>librewolf</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/lidarr.svg" alt="Lidarr" width="36"><br>lidarr</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/loki.svg" alt="Loki" width="36"><br>loki</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/mariadb.svg" alt="MariaDB" width="36"><br>mariadb</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/netbox.svg" alt="NetBox" width="36"><br>netbox</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/png/nzbhydra.png" alt="NZBHydra" width="36"><br>nzbhydra2</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/obsidian.svg" alt="Obsidian" width="36"><br>obsidian</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/ombi.svg" alt="Ombi" width="36"><br>ombi</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/opencloud.svg" alt="OpenCloud" width="36"><br>opencloud</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/plex.svg" alt="Plex" width="36"><br>plex</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/portainer.svg" alt="Portainer" width="36"><br>portainer</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/prometheus.svg" alt="Prometheus" width="36"><br>prometheus</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/prowlarr.svg" alt="Prowlarr" width="36"><br>prowlarr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/qbittorrent.svg" alt="qBittorrent" width="36"><br>qbittorrent</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/qui.svg" alt="QUI" width="36"><br>qui</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/radarr.svg" alt="Radarr" width="36"><br>radarr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/recyclarr.svg" alt="Recyclarr" width="36"><br>recyclarr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/redis.svg" alt="Redis" width="36"><br>redis</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/sabnzbd.svg" alt="SABnzbd" width="36"><br>sabnzbd</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/scraparr.svg" alt="Scraparr" width="36"><br>scraparr</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/seerr.svg" alt="Seerr" width="36"><br>seerr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/sonarr.svg" alt="Sonarr" width="36"><br>sonarr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/sportarr.svg" alt="Sportarr" width="36"><br>sportarr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/stash.svg" alt="Stash" width="36"><br>stash</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/syncthing.svg" alt="Syncthing" width="36"><br>syncthing</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/tautulli.svg" alt="Tautulli" width="36"><br>tautulli</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/technitium.svg" alt="Technitium" width="36"><br>technitium</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/the-lounge.svg" alt="The Lounge" width="36"><br>thelounge</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/png/theme-park.png" alt="Theme Park" width="36"><br>themepark</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/traefik.svg" alt="Traefik" width="36"><br>traefik</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/uptime-kuma.svg" alt="Uptime Kuma" width="36"><br>uptime kuma</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/ubiquiti-unifi.svg" alt="UniFi" width="36"><br>unifi-os</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/webp/unpackerr.webp" alt="Unpackerr" width="36"><br>unpackerr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/vaultwarden.svg" alt="Vaultwarden" width="36"><br>vaultwarden</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/whisparr.svg" alt="Whisparr" width="36"><br>whisparr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/webp/znc.webp" alt="ZNC" width="36"><br>znc</td>
    <td></td>
    <td></td>
  </tr>
</table>
