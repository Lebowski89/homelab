# Tasks

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
