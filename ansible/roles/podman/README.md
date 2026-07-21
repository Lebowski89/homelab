# Ansible role: podman

Installs and validates Podman 5.7+ for production rootful system Quadlets on Ubuntu 26.04+ hosts tagged for Podman.

The role intentionally manages rootful/system Quadlet prerequisites only. Quadlet files are expected under `/etc/containers/systemd`; containers can and should still run as non-root users via separate container UID/GID settings in their `.container` files. Rootless user-systemd Quadlets are a future extension.

## Tags

- `podman`
- `podman_install`

The role does not enable the Podman API socket and does not configure Docker compatibility sockets.
