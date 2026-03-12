# Docker Install

The `docker` role includes tasks to install Docker on a target machine.

The install process is an ansible automated version of the official install steps for Ubuntu.

The following relevant defaults are defined in the `docker` role:

```yml
docker_packages:
  - docker-ce
  - docker-ce-cli
  - containerd.io
  - docker-buildx-plugin
  - docker-compose-plugin

docker_prereq_packages:
  - ca-certificates
  - curl

docker_apt_arch_map:
  x86_64: amd64
  aarch64: arm64

docker_apt_arch: "{{ docker_apt_arch_map[ansible_architecture] | default(ansible_architecture) }}"

docker_repo_url: "https://download.docker.com/linux/ubuntu"
docker_repo_channel: stable
docker_keyring_dir: /etc/apt/keyrings
docker_keyring_file: /etc/apt/keyrings/docker.asc
docker_repo_filename: docker

docker_install_compose_plugin: true
docker_manage_user: false
docker_user: ""
```

These role defaults are typically universal across all nodes (as I use Ubuntu 24.04 - apart from UnRaid).

These two are the exceptions as they do typically change per host (and are defined as such in host_vars):

```yml
docker_manage_user:
docker_user:
```

These two add the machine user to the Docker group, allowing Docker cli commands without sudo.