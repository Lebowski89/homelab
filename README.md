# Homelab as Code

- Powered by Ansible <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/ansible.svg" alt="Ansible" width="24" /> and Docker Swarm <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/docker.svg" alt="Docker" width="24" />
- Uses Infisical <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/infisical.svg" alt="Infisical" width="24" /> for secret management
- Uses Authelia <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/authelia.svg" alt="Authelia" width="24" /> and Traefik <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/traefik.svg" alt="Traefik" width="24" /> for SSO and reverse proxy
- Uses highly available PostgreSQL <img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/postgresql.svg" alt="PostgreSQL" width="24" /> (PostgreSQL + Patroni + etcd + HAProxy) as the primary database platform
- Strong focus on media-centric services, especially Arr apps and companion services

## Goals

- Automate deployment of Docker apps and services
- Automate app settings, configs, databases, dns, and other needs in a single Ansible run
- Run against a fresh OS or VM and reliably deploy an app or service with my preferred settings every time

Detailed documentation is available in the `docs` folder.

## Apps in Use

<table>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/adminer.svg" alt="Adminer" width="36"><br>adminer</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/authelia.svg" alt="Authelia" width="36"><br>authelia</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/autobrr.svg" alt="Autobrr" width="36"><br>autobrr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/bazarr.svg" alt="Bazarr" width="36"><br>bazarr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/cross-seed.svg" alt="cross-seed" width="36"><br>cross-seed</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/czkawka.svg" alt="Czkawka" width="36"><br>czkawka</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/gitea.svg" alt="Gitea" width="36"><br>gitea</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/gluetun.svg" alt="Gluetun" width="36"><br>gluetun</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/grafana.svg" alt="Grafana" width="36"><br>grafana</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/grafana-alloy.svg" alt="Grafana Alloy" width="36"><br>grafana alloy</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/haproxy.svg" alt="HAProxy" width="36"><br>haproxy</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/homepage.svg" alt="Homepage" width="36"><br>homepage</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/hugo.svg" alt="Hugo" width="36"><br>hugo</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/png/jdownloader.png" alt="JDownloader" width="36"><br>jdownloader2</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/kometa.svg" alt="Kometa" width="36"><br>kometa</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/librewolf.svg" alt="LibreWolf" width="36"><br>librewolf</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/lidarr.svg" alt="Lidarr" width="36"><br>lidarr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/loki.svg" alt="Loki" width="36"><br>loki</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/mariadb.svg" alt="MariaDB" width="36"><br>mariadb</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/mongodb.svg" alt="MongoDB" width="36"><br>mongodb</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/png/nzbhydra.png" alt="NZBHydra" width="36"><br>nzbhydra</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/obsidian.svg" alt="Obsidian" width="36"><br>obsidian</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/ombi.svg" alt="Ombi" width="36"><br>ombi</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/plex.svg" alt="Plex" width="36"><br>plex</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/portainer.svg" alt="Portainer" width="36"><br>portainer</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/prometheus.svg" alt="Prometheus" width="36"><br>prometheus</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/prowlarr.svg" alt="Prowlarr" width="36"><br>prowlarr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/qbittorrent.svg" alt="qBittorrent" width="36"><br>qbittorrent</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/webp/qbit-manage.webp" alt="qbit_manage" width="36"><br>qbit-manage</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/qui.svg" alt="QUI" width="36"><br>qui</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/radarr.svg" alt="Radarr" width="36"><br>radarr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/redis.svg" alt="Redis" width="36"><br>redis</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/recyclarr.svg" alt="Recyclarr" width="36"><br>recyclarr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/sabnzbd.svg" alt="SABnzbd" width="36"><br>sabnzbd</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/scraparr.svg" alt="Scraparr" width="36"><br>scraparr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/seerr.svg" alt="Seerr" width="36"><br>seerr</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/sonarr.svg" alt="Sonarr" width="36"><br>sonarr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/sportarr.svg" alt="Sportarr" width="36"><br>sportarr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/stash.svg" alt="Stash" width="36"><br>stash</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/syncthing.svg" alt="Syncthing" width="36"><br>syncthing</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/tautulli.svg" alt="Tautulli" width="36"><br>tautulli</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/technitium.svg" alt="Technitium" width="36"><br>technitium</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/the-lounge.svg" alt="The Lounge" width="36"><br>thelounge</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/png/theme-park.png" alt="Theme Park" width="36"><br>themepark</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/traefik.svg" alt="Traefik" width="36"><br>traefik</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/ubiquiti-unifi.svg" alt="UniFi" width="36"><br>unifi</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/webp/unpackerr.webp" alt="Unpackerr" width="36"><br>unpackerr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/vaultwarden.svg" alt="Vaultwarden" width="36"><br>vaultwarden</td>
  </tr>
  <tr>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/svg/whisparr.svg" alt="Whisparr" width="36"><br>whisparr</td>
    <td align="center"><img src="https://cdn.jsdelivr.net/gh/selfhst/icons@main/webp/znc.webp" alt="ZNC" width="36"><br>znc</td>
    <td></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
</table>
</table>
