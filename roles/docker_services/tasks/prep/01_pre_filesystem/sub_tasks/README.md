
`authelia`: Generate (via spinning up temporary containers) the various keys required by Authelia.

`cloudflare`:
  - Ensures Cloudflare credentials/zone values exist, fetching from Infisical when needed.
  - Creates or updates Cloudflare DNS records for a target domain/host.

`infisical`:
  - Looks up secrets from Infisical based on a `secrets_map`, outputting flattened vars and/or a dictionary.
  - Replaces infisical placeholder put in place due to svc facts being loaded before infisical fetch.
  - Handles the creation of Docker Secrets for secrets fetched from Infisical.

`swarm_configs`: Creates/removes Docker Swarm configs from inline data or source files/templates.

`postgres.yml`: Ensures Postgres credentials/secrets are available and can ping/create requested databases.

`qbittorrent.yml`: Uses the `qbittorrent_passwd` module to hash the qBittorrent webui passwords.
