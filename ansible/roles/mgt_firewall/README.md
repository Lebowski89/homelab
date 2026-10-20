<!-- DOCSIBLE START -->

# 📃 Role overview

## mgt_firewall





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/10/08 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [mgt_firewall_active_endpoints](defaults/main.yml#L5)   | list | `[]` |    
| [mgt_firewall_callers](defaults/main.yml#L6)   | dict | `{}` |    
| [mgt_firewall_inputs_verified](defaults/main.yml#L7)   | bool | `False` |    
| [mgt_firewall_operation](defaults/main.yml#L8)   | str | `install` |    
| [mgt_firewall_root](defaults/main.yml#L9)   | str | `/etc/skynet-mgt-firewall` |    





### Tasks


#### File: tasks/check.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Mgt firewall ¦ Audit installed guards without writes or controller dependencies | ansible.builtin.command | False |
| Mgt firewall ¦ Audit enabled boot guard and active reconciliation timer | ansible.builtin.command | False |

#### File: tasks/install.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Mgt firewall ¦ Gather minimal platform facts | ansible.builtin.setup | False |
| Mgt firewall ¦ Require the current supported platform | ansible.builtin.assert | False |
| Mgt firewall ¦ Resolve live identities and dry-test both families before persistent writes | ansible.builtin.command | False |
| Mgt firewall ¦ Carry the validated dedicated manager dependencies | ansible.builtin.set_fact | False |
| Mgt firewall ¦ Create the owned policy directory | ansible.builtin.file | False |
| Mgt firewall ¦ Install the self-contained scoped policy helper | ansible.builtin.copy | False |
| Mgt firewall ¦ Install the owned guard and periodic reconciler units | ansible.builtin.template | False |
| Mgt firewall ¦ Create only the Docker drop-in directory | ansible.builtin.file | False |
| Mgt firewall ¦ Order Docker around the managed guards without restarting it | ansible.builtin.template | False |
| Mgt firewall ¦ Create only the dedicated manager drop-in directories | ansible.builtin.file | False |
| Mgt firewall ¦ Require the guard for dedicated rootless managers and rootful endpoints | ansible.builtin.template | False |
| Mgt firewall ¦ Resolve only the managed persistence paths | ansible.builtin.set_fact | False |
| Mgt firewall ¦ Record checksums of only the owned persistence files | ansible.builtin.stat | False |
| Mgt firewall ¦ Store the offline persistence audit manifest | ansible.builtin.set_fact | False |
| Mgt firewall ¦ Persist the completed offline audit manifest | ansible.builtin.copy | False |
| Mgt firewall ¦ Apply the active policy before enabling persistence | ansible.builtin.command | False |
| Mgt firewall ¦ Enable boot guards without restarting application services | ansible.builtin.systemd_service | False |
| Mgt firewall ¦ Enable and start only the managed reconciler timer | ansible.builtin.systemd_service | False |

#### File: tasks/main.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Mgt firewall ¦ Validate the selected operation | ansible.builtin.assert | False |
| Mgt firewall ¦ Prepare the value-free plan and strict active inputs | block | True |
| Mgt firewall ¦ Load namespaced catalog declarations | ansible.builtin.include_vars | False |
| Mgt firewall ¦ Resolve effective catalog and production bootstrap endpoints | mgt_firewall_plan | False |
| Mgt firewall ¦ Show endpoint coverage and pending caller identities | ansible.builtin.debug | True |
| Mgt firewall ¦ Explain read-only recovery planning | ansible.builtin.debug | True |
| Mgt firewall ¦ Perform only the selected policy operation | ansible.builtin.include_tasks | True |

#### File: tasks/observe.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Mgt firewall ¦ Observe current caller metadata without writes or setting confirmations | ansible.builtin.command | False |
| Mgt firewall ¦ Report available identities and unresolved callers | ansible.builtin.debug | False |

#### File: tasks/remove.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Mgt firewall ¦ Validate installed chain ownership before disabling persistence | ansible.builtin.command | False |
| Mgt firewall ¦ Locate the owned persistence units for repeatable removal | ansible.builtin.stat | False |
| Mgt firewall ¦ Disable and stop only the managed persistence units | ansible.builtin.systemd_service | True |
| Mgt firewall ¦ Locate only the boot guard unit | ansible.builtin.stat | False |
| Mgt firewall ¦ Disable the boot guard without stopping dependent applications | ansible.builtin.systemd_service | True |
| Mgt firewall ¦ Remove only marked guards and jumps without a policy file | ansible.builtin.command | False |
| Mgt firewall ¦ Remove only owned persistence files | ansible.builtin.file | False |
| Mgt firewall ¦ Reload systemd definitions without restarting applications | ansible.builtin.systemd_service | False |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
