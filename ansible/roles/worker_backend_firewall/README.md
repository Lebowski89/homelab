<!-- DOCSIBLE START -->

# 📃 Role overview

## worker_backend_firewall





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/10/07 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [worker_backend_firewall_source_addresses](defaults/main.yml#L5)   | list | `[]` |    
| [worker_backend_firewall_source_addresses.**0**](defaults/main.yml#L5)   | str | `{{ hostvars[services_controller_host].local_ip }}` |    
| [worker_backend_firewall_sources_verified](defaults/main.yml#L6)   | bool | `False` |    
| [worker_backend_firewall_operation](defaults/main.yml#L7)   | str | `install` |    





### Tasks


#### File: tasks/check.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Worker backend firewall ¦ Read installed policy without changing it | ansible.builtin.slurp | False |
| Worker backend firewall ¦ Compare installed policy to effective inventory and service plan | ansible.builtin.assert | False |
| Worker backend firewall ¦ Audit both kernel families read-only | ansible.builtin.command | False |
| Worker backend firewall ¦ Require Unraid's running reconciler | ansible.builtin.assert | True |
| Worker backend firewall ¦ Read Plex persistence status | ansible.builtin.command | True |

#### File: tasks/install.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Worker backend firewall ¦ Check existing firewall tools and selected backend | ansible.builtin.command | False |
| Worker backend firewall ¦ Validate Unraid boot entry before writing policy | block | True |
| Worker backend firewall ¦ Observe flash mount-defined file permissions | ansible.builtin.stat | False |
| Worker backend firewall ¦ Read existing supported boot script | ansible.builtin.slurp | False |
| Worker backend firewall ¦ Require a shell boot script | ansible.builtin.assert | False |
| Worker backend firewall ¦ Create only the managed policy directory | ansible.builtin.file | False |
| Worker backend firewall ¦ Install the standard-library helper | ansible.builtin.copy | False |
| Worker backend firewall ¦ Install only the managed policy declarations | ansible.builtin.copy | False |
| Worker backend firewall ¦ Apply the policy before installing startup hooks | ansible.builtin.command | False |
| Worker backend firewall ¦ Install platform persistence | ansible.builtin.include_tasks | False |

#### File: tasks/main.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Worker backend firewall ¦ Validate operation and explicit source confirmation | ansible.builtin.assert | True |
| Worker backend firewall ¦ Load value-free catalog declarations | ansible.builtin.include_vars | True |
| Worker backend firewall ¦ Derive effective worker publications | worker_backend_firewall_plan | True |
| Worker backend firewall ¦ Require a nonempty policy and inventory identity | ansible.builtin.assert | True |
| Worker backend firewall ¦ Gather minimal platform facts | ansible.builtin.setup | False |
| Worker backend firewall ¦ Detect the supported Unraid platform | ansible.builtin.stat | False |
| Worker backend firewall ¦ Validate supported platform and existing Python | ansible.builtin.assert | False |
| Worker backend firewall ¦ Resolve platform-owned paths and backend | ansible.builtin.set_fact | False |
| Worker backend firewall ¦ Validate exact addresses on the controller | ansible.builtin.set_fact | True |
| Worker backend firewall ¦ Validate policy inputs without host writes | worker_backend_firewall_validate | True |
| Worker backend firewall ¦ Explain the read-only plan | ansible.builtin.debug | True |
| Worker backend firewall ¦ Perform the selected policy operation | ansible.builtin.include_tasks | True |

#### File: tasks/remove.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Worker backend firewall ¦ Detect owned Plex units | ansible.builtin.stat | True |
| Worker backend firewall ¦ Stop and disable only installed owned Plex units | ansible.builtin.systemd_service | True |
| Worker backend firewall ¦ Remove the owned Unraid boot block | ansible.builtin.blockinfile | True |
| Worker backend firewall ¦ Stop Unraid reconciliation and remove only owned rules | ansible.builtin.script | False |
| Worker backend firewall ¦ Remove only owned persistence files | ansible.builtin.file | False |
| Worker backend firewall ¦ Reload Plex unit definitions after removal | ansible.builtin.systemd_service | True |

#### File: tasks/systemd.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Worker backend firewall ¦ Install owned systemd units | ansible.builtin.template | False |
| Worker backend firewall ¦ Ensure Docker drop-in directory | ansible.builtin.file | False |
| Worker backend firewall ¦ Install only the owned Docker ordering drop-in | ansible.builtin.template | False |
| Worker backend firewall ¦ Reload unit definitions when changed | ansible.builtin.systemd_service | True |
| Worker backend firewall ¦ Enable and start owned policy and reconciliation timer | ansible.builtin.systemd_service | False |

#### File: tasks/unraid.yml

| Name | Module | Has Conditions | Comments |
| ---- | ------ | -------------- | -------- |
| Worker backend firewall ¦ Install persistent Unraid launcher | ansible.builtin.template | False |  |
| Worker backend firewall ¦ Insert only the owned early Unraid boot block | ansible.builtin.blockinfile | False |  |
| Worker backend firewall ¦ Stop old Unraid reconciler before code restart | ansible.builtin.command | True | This ordered stop must finish before the subsequent start, rather than run at play end. |
| Worker backend firewall ¦ Start the singleton restart-aware reconciler | ansible.builtin.command | False |  |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
