<!-- DOCSIBLE START -->

# 📃 Role overview

## service_firewall





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/10/21 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [service_firewall_profile](defaults/main.yml#L4)   | str |  |    
| [service_firewall_operation](defaults/main.yml#L5)   | str |  |    
| [mgt_firewall_active_endpoints](defaults/main.yml#L11)   | list | `[]` |    
| [mgt_firewall_callers](defaults/main.yml#L12)   | dict | `{}` |    
| [mgt_firewall_inputs_verified](defaults/main.yml#L13)   | bool | `False` |    
| [mgt_firewall_operation](defaults/main.yml#L14)   | str | `install` |    
| [mgt_firewall_root](defaults/main.yml#L15)   | str | `/etc/skynet-mgt-firewall` |    
| [worker_backend_firewall_source_addresses](defaults/main.yml#L19)   | list | `[]` |    
| [worker_backend_firewall_source_addresses.**0**](defaults/main.yml#L19)   | str | `{{ hostvars[services_controller_host].local_ip }}` |    
| [worker_backend_firewall_sources_verified](defaults/main.yml#L20)   | bool | `False` |    
| [worker_backend_firewall_operation](defaults/main.yml#L21)   | str | `install` |    





### Tasks


#### File: tasks/lifecycle.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Service firewall ¦ Reconcile new caller identities before waiting for application health | service_firewall_lifecycle | True |  |
| Service firewall ¦ Apply this service's scoped protection transaction | service_firewall_lifecycle | True |  |
| Service firewall ¦ Verify declared callers against the running publication | ansible.builtin.include_tasks | True |  |

#### File: tasks/lifecycle_inspect.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Service firewall ¦ Clear previous ownership evidence | ansible.builtin.set_fact | False |
| Service firewall ¦ Use each endpoint host's configured connection | ansible.builtin.set_fact | False |
| Service firewall ¦ Validate existing Docker placement before policy changes | service_operational_check | True |
| Service firewall ¦ Read current mgt addresses for the worker source boundary | service_firewall_lifecycle | True |
| Service firewall ¦ Retain current controller addresses for this operation | ansible.builtin.set_fact | False |
| Service firewall ¦ Audit current protection before service preparation | service_firewall_lifecycle | False |
| Service firewall ¦ Inspect existing mapping or empty application storage | service_operational_check | True |
| Service firewall ¦ Save this operation's ownership evidence | ansible.builtin.set_fact | False |

#### File: tasks/lifecycle_probes.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Service firewall ¦ Read starting owned allow counters | service_firewall_lifecycle | False |
| Service firewall ¦ Check TCP access from each current caller namespace | service_firewall_lifecycle | False |
| Service firewall ¦ Read ending owned allow counters | service_firewall_lifecycle | False |
| Service firewall ¦ Require matching owned allow-counter increases | ansible.builtin.assert | True |
| Service firewall ¦ Report pending client activation without claiming acceptance | ansible.builtin.debug | False |

#### File: tasks/main.yml

| Name | Module | Has Conditions | Comments |
| ---- | ------ | -------------- | -------- |
| Service firewall ¦ Validate the firewall profile and operation | ansible.builtin.assert | False |  |
| Service firewall ¦ Save the operation for the selected profile | ansible.builtin.set_fact | False | Keep the chosen operation before exposing the legacy profile variables below;
those public names remain supported by saved rollback playbooks. |
| Service firewall ¦ Run the selected firewall profile | ansible.builtin.include_tasks | False |  |

#### File: tasks/mgt/check.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Service firewall ¦ Mgt ¦ Audit installed firewall rules without changing them | ansible.builtin.command | False |
| Service firewall ¦ Mgt ¦ Check startup protection and periodic rule reconciliation | ansible.builtin.command | False |

#### File: tasks/mgt/install.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Service firewall ¦ Mgt ¦ Gather minimal platform facts | ansible.builtin.setup | False |
| Service firewall ¦ Mgt ¦ Validate the supported Ubuntu version and Python | ansible.builtin.assert | False |
| Service firewall ¦ Mgt ¦ Verify caller identities and test IPv4 and IPv6 rules before writing files | ansible.builtin.command | False |
| Service firewall ¦ Mgt ¦ Save the verified service-manager dependencies | ansible.builtin.set_fact | False |
| Service firewall ¦ Mgt ¦ Extend and reconcile the current policy under its writer lock | service_firewall_lifecycle | False |

#### File: tasks/mgt/main.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Service firewall ¦ Mgt ¦ Validate the selected operation | ansible.builtin.assert | False |
| Service firewall ¦ Mgt ¦ Prepare endpoint declarations and caller inputs | block | True |
| Service firewall ¦ Mgt ¦ Load service declarations without secret values | ansible.builtin.include_vars | False |
| Service firewall ¦ Mgt ¦ Build endpoints from service and bootstrap declarations | mgt_firewall_plan | False |
| Service firewall ¦ Mgt ¦ Show endpoint coverage and pending caller identities | ansible.builtin.debug | True |
| Service firewall ¦ Mgt ¦ Show the check-mode recovery plan | ansible.builtin.debug | True |
| Service firewall ¦ Mgt ¦ Run the selected policy operation | ansible.builtin.include_tasks | True |

#### File: tasks/mgt/observe.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Service firewall ¦ Mgt ¦ Inspect caller identities without changing confirmations | ansible.builtin.command | False |
| Service firewall ¦ Mgt ¦ Report available identities and unresolved callers | ansible.builtin.debug | False |

#### File: tasks/mgt/remove.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Service firewall ¦ Mgt ¦ Check firewall chain ownership before disabling startup protection | ansible.builtin.command | False |
| Service firewall ¦ Mgt ¦ Find installed rule-reconciliation units | ansible.builtin.stat | False |
| Service firewall ¦ Mgt ¦ Stop and disable managed rule reconciliation | ansible.builtin.systemd_service | True |
| Service firewall ¦ Mgt ¦ Find the installed startup-protection unit | ansible.builtin.stat | False |
| Service firewall ¦ Mgt ¦ Disable startup protection without stopping applications | ansible.builtin.systemd_service | True |
| Service firewall ¦ Mgt ¦ Remove managed firewall rules and jumps without requiring a policy file | ansible.builtin.command | False |
| Service firewall ¦ Mgt ¦ Remove managed startup and reconciliation files | ansible.builtin.file | False |
| Service firewall ¦ Mgt ¦ Reload systemd definitions without restarting applications | ansible.builtin.systemd_service | False |

#### File: tasks/operations/mgt.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Service firewall ¦ Mgt ¦ Require exactly one controller in inventory | ansible.builtin.assert | False |  |
| Service firewall ¦ Mgt ¦ Select the inventory hosts and requested operation | ansible.builtin.set_fact | False |  |
| Service firewall ¦ Mgt ¦ Run the mgt profile on the controller | ansible.builtin.include_tasks | False |  |

#### File: tasks/operations/workers.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Service firewall ¦ Workers ¦ Validate the controller and worker inventory groups | ansible.builtin.assert | False |  |
| Service firewall ¦ Workers ¦ Select the inventory hosts and requested operation | ansible.builtin.set_fact | False |  |
| Service firewall ¦ Workers ¦ Reject conflicting operations | ansible.builtin.assert | False |  |
| Service firewall ¦ Workers ¦ Run the workers profile on the selected worker hosts | ansible.builtin.include_tasks | True |  |

#### File: tasks/prepare_callers.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Service firewall ¦ Prepare dedicated caller accounts without starting applications | ansible.builtin.include_role | True |

#### File: tasks/workers/check.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Service firewall ¦ Workers ¦ Read installed policy without changing it | ansible.builtin.slurp | False |
| Service firewall ¦ Workers ¦ Compare installed policy to effective inventory and service plan | ansible.builtin.assert | False |
| Service firewall ¦ Workers ¦ Audit IPv4 and IPv6 firewall rules without changing them | ansible.builtin.command | False |
| Service firewall ¦ Workers ¦ Require the Unraid rule-reconciliation process to be running | ansible.builtin.assert | True |
| Service firewall ¦ Workers ¦ Check the Plex rule-reconciliation timer | ansible.builtin.command | True |

#### File: tasks/workers/install.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Service firewall ¦ Workers ¦ Check existing firewall tools and selected backend | ansible.builtin.command | False |
| Service firewall ¦ Workers ¦ Validate Unraid boot entry before writing policy | block | True |
| Service firewall ¦ Workers ¦ Read Unraid flash permissions from the boot script | ansible.builtin.stat | False |
| Service firewall ¦ Workers ¦ Read existing supported boot script | ansible.builtin.slurp | False |
| Service firewall ¦ Workers ¦ Require a shell boot script | ansible.builtin.assert | False |
| Service firewall ¦ Workers ¦ Extend and reconcile the current policy under its writer lock | service_firewall_lifecycle | False |
| Service firewall ¦ Workers ¦ Configure policy startup and reconciliation for this platform | ansible.builtin.include_tasks | False |

#### File: tasks/workers/main.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Service firewall ¦ Workers ¦ Validate the operation and source-address confirmation | ansible.builtin.assert | True |
| Service firewall ¦ Workers ¦ Load service declarations without secret values | ansible.builtin.include_vars | True |
| Service firewall ¦ Workers ¦ Build published worker ports from service declarations | worker_backend_firewall_plan | True |
| Service firewall ¦ Workers ¦ Require published ports and the worker inventory address | ansible.builtin.assert | True |
| Service firewall ¦ Workers ¦ Gather minimal platform facts | ansible.builtin.setup | False |
| Service firewall ¦ Workers ¦ Detect the supported Unraid platform | ansible.builtin.stat | False |
| Service firewall ¦ Workers ¦ Validate supported platform and existing Python | ansible.builtin.assert | False |
| Service firewall ¦ Workers ¦ Select policy paths and the firewall backend for this platform | ansible.builtin.set_fact | False |
| Service firewall ¦ Workers ¦ Prepare the worker policy with exact source and endpoint addresses | ansible.builtin.set_fact | True |
| Service firewall ¦ Workers ¦ Validate policy inputs without host writes | worker_backend_firewall_validate | True |
| Service firewall ¦ Workers ¦ Show the check-mode policy plan | ansible.builtin.debug | True |
| Service firewall ¦ Workers ¦ Perform the selected policy operation | ansible.builtin.include_tasks | True |

#### File: tasks/workers/remove.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Service firewall ¦ Workers ¦ Detect owned Plex units | ansible.builtin.stat | True |
| Service firewall ¦ Workers ¦ Stop and disable only installed owned Plex units | ansible.builtin.systemd_service | True |
| Service firewall ¦ Workers ¦ Remove the owned Unraid boot block | ansible.builtin.blockinfile | True |
| Service firewall ¦ Workers ¦ Stop any Unraid reconciler and remove managed firewall rules | ansible.builtin.command | False |
| Service firewall ¦ Workers ¦ Remove managed startup and reconciliation files | ansible.builtin.file | False |
| Service firewall ¦ Workers ¦ Reload Plex unit definitions after removal | ansible.builtin.systemd_service | True |

#### File: tasks/workers/systemd.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Service firewall ¦ Workers ¦ Install owned systemd units | ansible.builtin.template | False |
| Service firewall ¦ Workers ¦ Ensure Docker drop-in directory | ansible.builtin.file | False |
| Service firewall ¦ Workers ¦ Install only the owned Docker ordering drop-in | ansible.builtin.template | False |
| Service firewall ¦ Workers ¦ Reload unit definitions when changed | ansible.builtin.systemd_service | True |
| Service firewall ¦ Workers ¦ Enable and start owned policy and reconciliation timer | ansible.builtin.systemd_service | False |

#### File: tasks/workers/unraid.yml

| Name | Module | Has Conditions | Comments |
| ---- | ------ | -------------- | -------- |
| Service firewall ¦ Workers ¦ Install persistent Unraid launcher | ansible.builtin.template | False |  |
| Service firewall ¦ Workers ¦ Add the managed policy-startup block to the Unraid boot script | ansible.builtin.blockinfile | False |  |
| Service firewall ¦ Workers ¦ Stop the old Unraid rule-reconciliation process before starting its replacement | ansible.builtin.command | True | Run this stop here, not as a deferred handler: the old reconciler must exit
before the replacement process starts. |
| Service firewall ¦ Workers ¦ Start one Unraid rule-reconciliation process | ansible.builtin.command | False |  |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
