# docker

Install Docker Engine and related packages on Ubuntu.

## Requirements

- Ubuntu
- apt package manager

## Role Variables

```yaml
docker_packages:
  - docker-ce
  - docker-ce-cli
  - containerd.io
  - docker-buildx-plugin
  - docker-compose-plugin

docker_manage_user: false
docker_user: ""