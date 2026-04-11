# Prep

The tasks/prep (preparation) tasks are broken down into the following categories:

## Cleanup

**Summary:** Remove existing service that could conflict with deployment

## Pre-Filesystem

**Summary:** Prepare prerequisites and bootstrap state needed before touching the target filesystem.

### Tasks

**authelia:** Generates (via spinning up temporary containers) the various keys required by Authelia.

**cloudflare:**
  - Ensures Cloudflare credentials/zone values exist, fetching from Infisical when needed.
  - Creates or updates Cloudflare DNS records for a target domain/host.

**infisical:**
  - Looks up secrets from Infisical based on a `secrets_map`, outputting flattened vars and/or a dictionary.
  - Replaces infisical placeholder put in place due to svc facts being loaded before infisical fetch.
  - Handles the creation of Docker Secrets for secrets fetched from Infisical.

**swarm_configs:** Creates/removes Docker Swarm configs from inline data or source files/templates.

**postgres:** Ensures Postgres credentials/secrets are available and can ping/create requested databases.

**qbittorrent:** Uses the `qbittorrent_passwd` module to hash the qBittorrent webui passwords.

## Filesystem

**Summary:** Create and manage required filesystem (dirs and files) state for the service.

### Tasks

**copies:** Copies role-relative files to target destinations on the deploy host.

**paths:** Ensures directories/files exist with expected ownership, permissions, and state.

**templates:** Renders Jinja templates to destination paths on the deploy host.

## Post-Filesystem

**Summary:** Finalise configuration and initialisation of the prepared filesystem.

### Tasks

**plex:**
  - Creates Docker NFS volume so Plex can access media on the UnRaid host.
  - Reads the Plex token / Client Identifier from `docker_services_primary_manager` and generates one if missing/malformed.
  - Sets various settings in Plex's preferences file.
  - Claims the Plex server if not claimed already.

**bazarr:**
  - Creates the config directory.
  - Generates the Bazarr config file if not present.
  - Uses the `yedit` module to set the desired settings and connections in the config.

**hugo:**
  - Generates a new blog if it doesn't exist.
  - Initiate git repo for blog if it doesn't exist.
  - Install Terminal theme submodule.
  - git add/push changes if necessary.

**nzbhydra2:**
  - Creates the config directory.
  - Generates the nzbhydra2 config file if not present.
  - Uses the `yedit` module to set the desired settings and connections in the config.

**vaultwarden:**
  - Reads admin token on `docker_services_primary_manager` and generates (argon2) one if missing.
  - Creates a admin token Docker Secret, for the Vaultwarden Swarm service, if not already present.