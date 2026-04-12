## `docker_services` role: Ansible module inventory

This file lists the Ansible modules invoked by this role's task and handler files.

### `ansible.builtin`

- `ansible.builtin.assert`
- `ansible.builtin.command`
- `ansible.builtin.copy`
- `ansible.builtin.debug`
- `ansible.builtin.fail`
- `ansible.builtin.file`
- `ansible.builtin.include_tasks`
- `ansible.builtin.pause`
- `ansible.builtin.set_fact`
- `ansible.builtin.slurp`
- `ansible.builtin.stat`
- `ansible.builtin.template`
- `ansible.builtin.uri`
- `ansible.builtin.wait_for`

### `community.docker`

- `community.docker.docker_compose_v2`
- `community.docker.docker_config`
- `community.docker.docker_container`
- `community.docker.docker_secret`
- `community.docker.docker_stack`
- `community.docker.docker_volume`

### `community.general`

- `community.general.cloudflare_dns`
- `community.general.git_config`
- `community.general.ini_file`
- `community.general.ipify_facts`
- `community.general.ipinfoio_facts`
- `community.general.xml`

### `custom`

- `qbittorrent_passwd`
- `yedit`
