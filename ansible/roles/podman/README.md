<!-- DOCSIBLE START -->

# 📃 Role overview

## podman





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/07/24 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [podman_install_enable](defaults/main.yml#L2)   | bool | `True` |    
| [podman_state](defaults/main.yml#L3)   | str | `present` |    
| [podman_update_cache](defaults/main.yml#L4)   | bool | `True` |    
| [podman_cache_valid_time](defaults/main.yml#L5)   | int | `3600` |    
| [podman_min_version](defaults/main.yml#L6)   | str | `5.7.0` |    
| [podman_quadlet_generator_paths](defaults/main.yml#L7)   | list | `[]` |    
| [podman_quadlet_generator_paths.**0**](defaults/main.yml#L8)   | str | `/usr/lib/systemd/system-generators/podman-system-generator` |    
| [podman_quadlet_generator_paths.**1**](defaults/main.yml#L8)   | str | `/lib/systemd/system-generators/podman-system-generator` |    
| [podman_packages](defaults/main.yml#L10)   | list | `[]` |    
| [podman_packages.**0**](defaults/main.yml#L10)   | str | `podman` |    
| [podman_packages.**1**](defaults/main.yml#L12)   | str | `containernetworking-plugins` |    
| [podman_packages.**2**](defaults/main.yml#L13)   | str | `uidmap` |    
| [podman_packages.**3**](defaults/main.yml#L14)   | str | `slirp4netns` |    
| [podman_packages.**4**](defaults/main.yml#L15)   | str | `fuse-overlayfs` |    
| [podman_install_extra_packages](defaults/main.yml#L16)   | list | `[]` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Podman ¦ Assert supported Ubuntu host | ansible.builtin.assert | False |  |
| Podman ¦ Install runtime packages | ansible.builtin.apt | True |  |
| Podman ¦ Check installed version | ansible.builtin.command | False |  |
| Podman ¦ Defer runtime validation in fresh-host check mode | ansible.builtin.debug | True |  |
| Podman ¦ Assert Quadlet-capable version | ansible.builtin.assert | True |  |
| Podman ¦ Check Podman cgroup version | ansible.builtin.command | True |  |
| Podman ¦ Assert cgroup v2 | ansible.builtin.assert | True |  |
| Podman ¦ Check system Quadlet generator | ansible.builtin.stat | True |  |
| Podman ¦ Record system Quadlet generator path | ansible.builtin.set_fact | True |  |
| Podman ¦ Assert system Quadlet generator exists | ansible.builtin.assert | True |  |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
