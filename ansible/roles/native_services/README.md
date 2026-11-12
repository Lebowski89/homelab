<!-- DOCSIBLE START -->

# 📃 Role overview

## native_services





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/11/13 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/alloy.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [alloy_native_keyring_dir](defaults/alloy.yml#L4)   | str | `{{ native_services_config.keyring_dir }}` |    
| [alloy_native_keyring_file](defaults/alloy.yml#L5)   | str | `{{ native_services_config.keyring_file }}` |    
| [alloy_native_repo_url](defaults/alloy.yml#L6)   | str | `{{ native_services_config.repo_url }}` |    
| [alloy_native_repo_suite](defaults/alloy.yml#L7)   | str | `{{ native_services_config.repo_suite }}` |    
| [alloy_native_repo_filename](defaults/alloy.yml#L8)   | str | `{{ native_services_config.repo_filename }}` |    
| [alloy_native_packages](defaults/alloy.yml#L9)   | str | `{{ native_services_config.packages }}` |    
| [alloy_native_service_name](defaults/alloy.yml#L10)   | str | `{{ native_services_config.service_name }}` |    
| [alloy_native_user](defaults/alloy.yml#L11)   | str | `{{ native_services_config.user }}` |    
| [alloy_native_group](defaults/alloy.yml#L12)   | str | `{{ native_services_config.group }}` |    
| [alloy_native_config_dir](defaults/alloy.yml#L13)   | str | `{{ native_services_config.config_dir }}` |    
| [alloy_native_config_path](defaults/alloy.yml#L14)   | str | `{{ native_services_config.config_path }}` |    
| [alloy_native_journal_groups](defaults/alloy.yml#L15)   | str | `{{ native_services_config.journal_groups }}` |    
| [alloy_native_loki_url](defaults/alloy.yml#L16)   | str | `{{ native_services_config.loki_url }}` |    
| [alloy_native_rpm_baseurl](defaults/alloy.yml#L20)   | str | `https://rpm.grafana.com` |    
| [alloy_native_rpm_key_url](defaults/alloy.yml#L21)   | str | `{{ alloy_native_rpm_baseurl }}/gpg.key` |    
| [alloy_native_rpm_key_fingerprint](defaults/alloy.yml#L22)   | str | `B53AE77BADB630A683046005963FA27710458545` |    

#### File: defaults/forgejo_runner.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [native_services_forgejo_runner_controller](defaults/forgejo_runner.yml#L4)   | bool | `False` |    
| [native_services_forgejo_runner_private_source_dir](defaults/forgejo_runner.yml#L5)   | str |  |    

#### File: defaults/keepalived.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [keepalived_config_path](defaults/keepalived.yml#L3)   | str | `{{ native_services_config.config_path }}` |    
| [keepalived_check_script_path](defaults/keepalived.yml#L4)   | str | `{{ native_services_config.check_script_path }}` |    
| [keepalived_dns_check_query](defaults/keepalived.yml#L5)   | str | `{{ native_services_config.dns_check_query }}` |    
| [keepalived_dns_check_type](defaults/keepalived.yml#L6)   | str | `{{ native_services_config.dns_check_type }}` |    
| [keepalived_dns_check_server](defaults/keepalived.yml#L7)   | str | `{{ native_services_config.dns_check_server }}` |    
| [keepalived_dns_check_timeout](defaults/keepalived.yml#L8)   | str | `{{ native_services_config.dns_check_timeout }}` |    
| [keepalived_dns_check_tries](defaults/keepalived.yml#L9)   | str | `{{ native_services_config.dns_check_tries }}` |    
| [keepalived_script_interval](defaults/keepalived.yml#L10)   | str | `{{ native_services_config.script_interval }}` |    
| [keepalived_script_timeout](defaults/keepalived.yml#L11)   | str | `{{ native_services_config.script_timeout }}` |    
| [keepalived_script_fall](defaults/keepalived.yml#L12)   | str | `{{ native_services_config.script_fall }}` |    
| [keepalived_script_rise](defaults/keepalived.yml#L13)   | str | `{{ native_services_config.script_rise }}` |    
| [keepalived_script_weight](defaults/keepalived.yml#L14)   | str | `{{ native_services_config.script_weight }}` |    
| [keepalived_dns_group](defaults/keepalived.yml#L15)   | str | `{{ native_services_config.dns_group }}` |    
| [keepalived_host_ip](defaults/keepalived.yml#L16)   | str | `{{ native_services_config.host_ip }}` |    
| [keepalived_host_interface](defaults/keepalived.yml#L17)   | str | `{{ native_services_config.host_interface }}` |    
| [keepalived_host_mode](defaults/keepalived.yml#L18)   | str | `{{ native_services_config.host_mode }}` |    
| [keepalived_instances](defaults/keepalived.yml#L19)   | str | `{{ native_services_config.instances }}` |    

#### File: defaults/node_exporter.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [node_exporter_version](defaults/node_exporter.yml#L3)   | str | `{{ native_services_config.version }}` |    
| [node_exporter_arch](defaults/node_exporter.yml#L4)   | str | `{{ native_services_config.arch }}` |    
| [node_exporter_user](defaults/node_exporter.yml#L5)   | str | `{{ native_services_config.user }}` |    
| [node_exporter_group](defaults/node_exporter.yml#L6)   | str | `{{ native_services_config.group }}` |    
| [node_exporter_release_url](defaults/node_exporter.yml#L7)   | str | `{{ native_services_config.release_url }}` |    
| [node_exporter_archive_name](defaults/node_exporter.yml#L8)   | str | `{{ native_services_config.archive_name }}` |    
| [node_exporter_download_url](defaults/node_exporter.yml#L9)   | str | `{{ native_services_config.download_url }}` |    
| [node_exporter_archive_path](defaults/node_exporter.yml#L10)   | str | `{{ native_services_config.archive_path }}` |    
| [node_exporter_extract_dir](defaults/node_exporter.yml#L11)   | str | `{{ native_services_config.extract_dir }}` |    
| [node_exporter_checksum](defaults/node_exporter.yml#L12)   | str | `{{ native_services_config.checksum }}` |    
| [node_exporter_install_dir](defaults/node_exporter.yml#L13)   | str | `{{ native_services_config.install_dir }}` |    
| [node_exporter_textfile_dir](defaults/node_exporter.yml#L14)   | str | `{{ native_services_config.textfile_dir }}` |    
| [node_exporter_listen_address](defaults/node_exporter.yml#L15)   | str | `{{ native_services_config.listen_address }}` |    
| [node_exporter_enabled_collectors](defaults/node_exporter.yml#L16)   | str | `{{ native_services_config.enabled_collectors }}` |    
| [node_exporter_disabled_collectors](defaults/node_exporter.yml#L17)   | str | `{{ native_services_config.disabled_collectors }}` |    
| [node_exporter_extra_args](defaults/node_exporter.yml#L19)   | str | `{{ native_services_config.extra_args }}` |    

#### File: defaults/technitium.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [technitium_native_install_script_url](defaults/technitium.yml#L4)   | str | `{{ native_services_config.install_script_url }}` |    
| [technitium_native_install_script_path](defaults/technitium.yml#L6)   | str | `{{ native_services_config.install_script_path }}` |    
| [technitium_native_service_name](defaults/technitium.yml#L8)   | str | `{{ native_services_config.service_name }}` |    
| [technitium_native_web_port](defaults/technitium.yml#L9)   | str | `{{ native_services_config.web_port }}` |    
| [technitium_native_dns_port](defaults/technitium.yml#L10)   | str | `{{ native_services_config.dns_port }}` |    
| [technitium_native_config_dir](defaults/technitium.yml#L11)   | str | `{{ native_services_config.config_dir }}` |    
| [technitium_native_install_marker](defaults/technitium.yml#L12)   | str | `{{ native_services_config.install_marker }}` |    
| [technitium_native_resolved_dns_servers](defaults/technitium.yml#L13)   | str | `{{ native_services_config.resolved_dns_servers }}` |    
| [technitium_native_disable_resolved_stub](defaults/technitium.yml#L15)   | str | `{{ native_services_config.disable_resolved_stub }}` |    
| [technitium_native_archive_url](defaults/technitium.yml#L19)   | str | `https://download.technitium.com/dns/DnsServerPortable.tar.gz` |    
| [technitium_native_archive_checksum](defaults/technitium.yml#L20)   | str |  |    





### Tasks


#### File: tasks/alloy.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Alloy native ¦ Preview repository and package installation | ansible.builtin.debug | True |
| Alloy native ¦ Configure APT installation | ansible.builtin.import_tasks | True |
| Alloy native ¦ Configure RPM installation | ansible.builtin.import_tasks | True |
| Alloy native ¦ Read local system accounts | ansible.builtin.getent | False |
| Alloy native ¦ Read local system groups | ansible.builtin.getent | False |
| Alloy native ¦ Resolve package service account availability | ansible.builtin.set_fact | False |
| Alloy native ¦ Require package service account after installation | ansible.builtin.assert | True |
| Alloy native ¦ Report account-dependent work deferred in check mode | ansible.builtin.debug | True |
| Alloy native ¦ Resolve available journal reader groups | ansible.builtin.set_fact | False |
| Alloy native ¦ Grant journal access to package service account | ansible.builtin.user | True |
| Alloy native ¦ Ensure configuration directory exists | ansible.builtin.file | True |
| Alloy native ¦ Render collector configuration | ansible.builtin.template | True |
| Native services ¦ Record adopted alloy configuration | ansible.builtin.include_tasks | True |
| Alloy native ¦ Enable and start service | ansible.builtin.systemd_service | True |

#### File: tasks/alloy/apt.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Alloy native ¦ Ensure apt keyring directory exists | ansible.builtin.file | False |
| Alloy native ¦ Download Grafana package signing key | ansible.builtin.get_url | False |
| Alloy native ¦ Configure Grafana apt repository | ansible.builtin.apt_repository | False |
| Alloy native ¦ Install APT packages | ansible.builtin.apt | False |

#### File: tasks/alloy/rpm.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Alloy native ¦ Install RPM HTTPS prerequisites | ansible.builtin.dnf | False |
| Alloy native ¦ Trust the Grafana RPM signing key | ansible.builtin.rpm_key | False |
| Alloy native ¦ Configure the Grafana RPM repository | ansible.builtin.yum_repository | False |
| Alloy native ¦ Install RPM packages | ansible.builtin.dnf | False |

#### File: tasks/alloy_validate.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Alloy native ¦ Detect Atomic or OSTree deployment | ansible.builtin.stat | False |
| Alloy native ¦ Validate the supported platform before changes | ansible.builtin.assert | False |
| Alloy native ¦ Validate RPM repository inputs | ansible.builtin.assert | True |

#### File: tasks/dns_platform.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Native DNS ¦ Detect Atomic or OSTree deployment | ansible.builtin.stat | False |
| Native DNS ¦ Validate supported platform before changes | ansible.builtin.assert | False |
| Native DNS ¦ Validate RPM Technitium runtime availability | ansible.builtin.assert | True |

#### File: tasks/forgejo_runner.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Forgejo Runner ¦ Create dedicated service group | ansible.builtin.group | False |  |
| Forgejo Runner ¦ Create unprivileged persistent automation account | ansible.builtin.user | False |  |
| Forgejo Runner ¦ Prepare private persistent controller directories | ansible.builtin.file | False |  |
| Forgejo Runner ¦ Prepare private persistent credentials directory | ansible.builtin.file | False |  |
| Forgejo Runner ¦ Install headless automation through the workstation tooling entry point | ansible.builtin.include_role | False |  |
| Forgejo Runner ¦ Install signature verification prerequisites | ansible.builtin.dnf | False |  |
| Forgejo Runner ¦ Prepare root-owned persistent release verification directory | ansible.builtin.file | False |  |
| Forgejo Runner ¦ Install the pinned upstream public release key | ansible.builtin.copy | False |  |
| Forgejo Runner ¦ Import only the repository-pinned release key into an isolated keyring | ansible.builtin.command | True |  |
| Forgejo Runner ¦ Download pinned binary and detached signature over verified HTTPS | ansible.builtin.get_url | True |  |
| Forgejo Runner ¦ Verify the upstream signature before installing executable bytes | ansible.builtin.command | True |  |
| Forgejo Runner ¦ Install verified binary | ansible.builtin.copy | True |  |
| Forgejo Runner ¦ Verify the installed release as the unprivileged account | ansible.builtin.command | True |  |
| Forgejo Runner ¦ Provision only explicitly named private controller files | ansible.builtin.copy | True |  |
| Forgejo Runner ¦ Install separately verified node SSH identities | ansible.builtin.copy | True |  |
| Forgejo Runner ¦ Install the controller launcher without provisioning resources | ansible.builtin.copy | False |  |
| Forgejo Runner ¦ Install persistent non-secret controller profile | ansible.builtin.template | False |  |
| Forgejo Runner ¦ Install provider cache configuration outside Git | ansible.builtin.copy | False |  |
| Forgejo Runner ¦ Install only the validated registration snapshot | ansible.builtin.copy | True |  |
| Forgejo Runner ¦ Render the validated private runner connection | ansible.builtin.template | True |  |
| Forgejo Runner ¦ Record adopted private runner configuration | ansible.builtin.include_tasks | True |  |
| Forgejo Runner ¦ Install and record each owned systemd unit | ansible.builtin.include_tasks | True |  |
| Forgejo Runner ¦ Start persistent boot authentication without a workstation agent | ansible.builtin.systemd_service | True |  |
| Forgejo Runner ¦ Enable and start the repository runner | ansible.builtin.systemd_service | True |  |

#### File: tasks/forgejo_runner_drain.yml

| Name | Module | Has Conditions | Comments |
| ---- | ------ | -------------- | -------- |
| Forgejo Runner ¦ Ensure controller configuration directory | ansible.builtin.file | False | A token-owned directory excludes all other lifecycle operations and new jobs. |
| Forgejo Runner ¦ Exclusively own maintenance until handlers and lifecycle complete | forgejo_runner_maintenance | False |  |
| Forgejo Runner ¦ Stop the owned authentication agent during removal | ansible.builtin.systemd_service | True |  |

#### File: tasks/forgejo_runner_registration.yml

| Name | Module | Has Conditions | Comments |
| ---- | ------ | -------------- | -------- |
| Forgejo Runner ¦ Read the selected private registration before mutation | ansible.builtin.slurp | False | Keep the validated snapshot through installation; never reread an unchecked source. |
| Forgejo Runner ¦ Parse the selected registration snapshot privately | ansible.builtin.set_fact | False |  |
| Forgejo Runner ¦ Require matching registration identity and repository before mutation | ansible.builtin.assert | False |  |

#### File: tasks/forgejo_runner_unit.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Forgejo Runner ¦ Install selected service unit | ansible.builtin.template | False |
| Forgejo Runner ¦ Record the successfully installed unit immediately | ansible.builtin.include_tasks | False |

#### File: tasks/forgejo_runner_validate.yml

| Name | Module | Has Conditions | Comments |
| ---- | ------ | -------------- | -------- |
| Forgejo Runner ¦ Require the dedicated Rocky controller VM | ansible.builtin.assert | False |  |
| Forgejo Runner ¦ Inspect existing account without creating it | ansible.builtin.getent | False |  |
| Forgejo Runner ¦ Reject a conflicting account | ansible.builtin.assert | True |  |
| Forgejo Runner ¦ Inspect existing units | ansible.builtin.service_facts | False |  |
| Forgejo Runner ¦ Inspect the deliberately unused legacy registration path | ansible.builtin.stat | False |  |
| Forgejo Runner ¦ Refuse any legacy connection alongside the scoped registration | ansible.builtin.assert | True |  |
| Forgejo Runner ¦ Refuse to adopt unowned runner or SSH-agent units | ansible.builtin.assert | False |  |
| Forgejo Runner ¦ Inspect persistent home ownership without following links | ansible.builtin.stat | False |  |
| Forgejo Runner ¦ Reject foreign persistent controller state | ansible.builtin.assert | True |  |
| Forgejo Runner ¦ Require an explicit absolute private input directory | ansible.builtin.assert | True |  |
| Forgejo Runner ¦ Inspect required private inputs before changing the host | ansible.builtin.stat | True |  |
| Forgejo Runner ¦ Require explicit regular credential files before installation | ansible.builtin.assert | True |  |
| Forgejo Runner ¦ Inspect installation directory boundaries without following links | ansible.builtin.stat | False | Inspect root-created boundaries without following retained user symlinks; tooling beneath .local stays user-owned. |
| Forgejo Runner ¦ Refuse linked or foreign installation directories | ansible.builtin.assert | True |  |
| Forgejo Runner ¦ Require an owned restartable installation | ansible.builtin.assert | True |  |
| Forgejo Runner ¦ Inspect only resident restart inputs | ansible.builtin.stat | True |  |
| Forgejo Runner ¦ Require private resident configuration and boot authentication for restart | ansible.builtin.assert | True |  |

#### File: tasks/keepalived.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Keepalived ¦ Configure native service | block | True |
| Keepalived native ¦ Install APT packages | ansible.builtin.apt | True |
| Keepalived native ¦ Apply declared APT update policy to Keepalived only | ansible.builtin.apt | True |
| Keepalived native ¦ Install RPM packages | ansible.builtin.include_tasks | True |
| Keepalived native ¦ Explain deferred package and runtime checks | ansible.builtin.debug | True |
| Keepalived native ¦ Ensure config directory exists | ansible.builtin.file | False |
| Keepalived native ¦ Install DNS health check script | ansible.builtin.template | False |
| Native services ¦ Record adopted keepalived configuration | ansible.builtin.include_tasks | True |
| Keepalived native ¦ Render keepalived config | ansible.builtin.template | False |
| Native services ¦ Record adopted keepalived configuration | ansible.builtin.include_tasks | True |
| Keepalived native ¦ Enable and start keepalived | ansible.builtin.systemd_service | True |

#### File: tasks/keepalived/rpm.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Keepalived native ¦ Install distribution Keepalived and DNS health-check tools | ansible.builtin.dnf | False |
| Keepalived native ¦ Apply the declared RPM update policy to Keepalived only | ansible.builtin.dnf | True |

#### File: tasks/keepalived_validate.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Keepalived ¦ Set host config | ansible.builtin.set_fact | False |
| Keepalived ¦ Validate common config | ansible.builtin.assert | False |
| Keepalived ¦ Validate peer inventory addresses | ansible.builtin.assert | False |
| Keepalived ¦ Validate each VRRP instance | ansible.builtin.assert | False |

#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags | Comments |
| ---- | ------ | -------------- | -----| -------- |
| Native services ¦ Validate selected lifecycle | ansible.builtin.assert | False |  |  |
| Native services ¦ Resolve current application contract | ansible.builtin.set_fact | False |  |  |
| Native services ¦ Validate Alloy platform before changing the host | ansible.builtin.include_tasks | True |  |  |
| Native services ¦ Validate native DNS platform before changing the host | ansible.builtin.include_tasks | True |  |  |
| Native services ¦ Inspect Technitium resolver requirements before ownership changes | ansible.builtin.include_tasks | True |  |  |
| Native services ¦ Classify firewall requirements before changing the host | service_firewall_plan | False |  |  |
| Native services ¦ Validate common operational requirements | ansible.builtin.include_role | False |  |  |
| Native services ¦ Resolve owned installation paths | ansible.builtin.set_fact | False |  |  |
| Native services ¦ Read ownership record metadata | ansible.builtin.stat | False |  |  |
| Native services ¦ Read existing ownership record | ansible.builtin.slurp | True |  |  |
| Native services ¦ Resolve existing ownership record | ansible.builtin.set_fact | True |  |  |
| Native services ¦ Reject competing native installations | ansible.builtin.assert | False |  |  |
| Native services ¦ Validate dedicated controller and existing runner ownership | ansible.builtin.include_tasks | True |  |  |
| Native services ¦ Validate Keepalived before any installation or restart | ansible.builtin.include_tasks | True |  |  |
| Native services ¦ Inspect managed file paths without following links | ansible.builtin.stat | False |  |  |
| Native services ¦ Refuse directory deletion or replacement through file settings | ansible.builtin.assert | False |  |  |
| Forgejo Runner ¦ Reset per-entry maintenance ownership and registration snapshots | ansible.builtin.set_fact | True |  |  |
| Native services ¦ Complete the owned lifecycle with private snapshot cleanup | block | False |  | checkov:skip=CKV2_ANSIBLE_3:Failure propagates; always clears transient auth while retaining failed maintenance ownership. |
| Forgejo Runner ¦ Validate the selected registration before installation changes | ansible.builtin.include_tasks | True |  |  |
| Native services ¦ Protect active acceptance before runner lifecycle changes | ansible.builtin.include_tasks | True |  |  |
| Native services ¦ Prepare installation ownership and resolver recovery | ansible.builtin.include_tasks | True |  |  |
| Native services ¦ Apply the selected application | ansible.builtin.include_tasks | True |  |  |
| Forgejo Runner ¦ Explain validated check-mode installation plan | ansible.builtin.debug | True |  |  |
| Native services ¦ Recreate the selected service without deleting data | ansible.builtin.include_tasks | True |  |  |
| Native services ¦ Remove the selected service's managed integrations | ansible.builtin.include_tasks | True |  |  |
| Native services ¦ Complete selected service notifications | ansible.builtin.meta | False |  | Flush notifications before another entry can replace this application's facts. |
| Forgejo Runner ¦ Release only this completed operation's maintenance ownership | forgejo_runner_maintenance | True |  |  |

#### File: tasks/node_exporter.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Node_Exporter ¦ Create node_exporter group | ansible.builtin.group | False |
| Node_Exporter ¦ Create node_exporter user | ansible.builtin.user | False |
| Node_Exporter ¦ Create node_exporter textfile collector directory | ansible.builtin.file | False |
| Node_Exporter ¦ Skip node_exporter binary install in check mode | ansible.builtin.debug | True |
| Node_Exporter ¦ Download node_exporter archive | ansible.builtin.get_url | True |
| Node_Exporter ¦ Extract node_exporter archive | ansible.builtin.unarchive | True |
| Node_Exporter ¦ Install node_exporter binary | ansible.builtin.copy | True |
| Node_Exporter ¦ Install node_exporter systemd unit | ansible.builtin.template | False |
| Native services ¦ Record adopted node_exporter configuration | ansible.builtin.include_tasks | True |
| Node_Exporter ¦ Enable and start node_exporter | ansible.builtin.systemd | True |

#### File: tasks/ownership.yml

| Name | Module | Has Conditions | Comments |
| ---- | ------ | -------------- | -------- |
| Native services ¦ Inspect original resolver ownership | ansible.builtin.stat | True | Record the original resolver only once, before the existing installer
procedure changes it. Never save credentials or application configuration. |
| Native services ¦ Save original regular resolver content | ansible.builtin.slurp | True |  |
| Native services ¦ Resolve installation ownership record | ansible.builtin.set_fact | False |  |
| Native services ¦ Ensure private ownership directory exists | ansible.builtin.file | True |  |
| Native services ¦ Record the selected installation's owned files | ansible.builtin.copy | True | Save recovery state before installation. Claim files only after their
successful template/copy task; a failed download must not adopt an old file. |

#### File: tasks/record_files.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Native services ¦ Claim only configuration successfully managed by this entry | ansible.builtin.set_fact | False |
| Native services ¦ Save installation ownership after configuration adoption | ansible.builtin.copy | False |

#### File: tasks/recreate.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Native services ¦ Report check-mode restart plan | ansible.builtin.debug | True |
| Native services ¦ Restart selected installed service | ansible.builtin.systemd_service | True |
| Native services ¦ Verify Technitium readiness after restart | ansible.builtin.include_tasks | True |

#### File: tasks/remove.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Native services ¦ Verify resolver ownership before stopping DNS | ansible.builtin.include_tasks | True |
| Native services ¦ Inspect installed services | ansible.builtin.service_facts | False |
| Native services ¦ Stop and disable the selected installed service | ansible.builtin.systemd_service | True |
| Native services ¦ Explain retained unclaimed installation files | ansible.builtin.debug | True |
| Native services ¦ Restore owned resolver integration | ansible.builtin.include_tasks | True |
| Native services ¦ Remove only recorded managed configuration files | ansible.builtin.file | False |
| Native services ¦ Reload units after retiring a managed unit | ansible.builtin.systemd_service | True |
| Native services ¦ Retire the selected ownership record | ansible.builtin.file | False |
| Native services ¦ Report retained installation and check-mode limitations | ansible.builtin.debug | False |

#### File: tasks/resolver_remove.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Native services ¦ Remove Technitium resolver drop-in | ansible.builtin.file | False |
| Native services ¦ Restore original resolver symlink | ansible.builtin.file | True |
| Native services ¦ Remove role-created resolver link before restoring a regular file | ansible.builtin.file | True |
| Native services ¦ Restore original regular resolver file | ansible.builtin.copy | True |
| Native services ¦ Restart resolved after restoring its configuration | ansible.builtin.systemd_service | True |

#### File: tasks/resolver_validate.yml

| Name | Module | Has Conditions | Comments |
| ---- | ------ | -------------- | -------- |
| Native services ¦ Inspect current resolver link before restoring it | ansible.builtin.stat | False |  |
| Native services ¦ Require the resolver link still owned by this installation | ansible.builtin.assert | False | The caller requires a retained ownership/recovery record. An interrupted
unlink-then-copy restore can leave the path absent; no other content is
overwritten when resuming that state. Existing conflicting paths still fail. |

#### File: tasks/technitium.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Technitium native ¦ Retain the APT installation procedure | ansible.builtin.include_tasks | True |  |
| Technitium native ¦ Install the RPM native application | ansible.builtin.include_tasks | True |  |

#### File: tasks/technitium/apt.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Technitium native ¦ Install prerequisite packages | ansible.builtin.apt | True |  |
| Technitium native ¦ Download installer before changing local DNS | ansible.builtin.get_url | True |  |
| Technitium native ¦ Reconcile declared systemd-resolved integration | ansible.builtin.include_tasks | True |  |
| Technitium native ¦ Flush resolver changes before install | ansible.builtin.meta | False |  |
| Technitium native ¦ Verify DNS still works after resolver change | ansible.builtin.command | True |  |
| Technitium native ¦ Run installer | ansible.builtin.command | True |  |
| Technitium native ¦ Enable and start service | ansible.builtin.systemd | True |  |
| Technitium native ¦ Check listener readiness | ansible.builtin.include_tasks | True |  |
| Technitium native ¦ Explain check-mode installation limitations | ansible.builtin.debug | True |  |

#### File: tasks/technitium/resolved.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Technitium native ¦ Ensure resolved drop-in directory exists | ansible.builtin.file | False |  |
| Technitium native ¦ Disable only the active resolved stub | ansible.builtin.copy | False |  |
| Native services ¦ Record the adopted Technitium resolver drop-in | ansible.builtin.include_tasks | False |  |
| Technitium native ¦ Preserve resolved DNS output without its stub | ansible.builtin.file | False |  |

#### File: tasks/technitium/rpm.yml

| Name | Module | Has Conditions | Comments |
| ---- | ------ | -------------- | -------- |
| Technitium native ¦ Inspect the installed application marker | ansible.builtin.stat | False | The upstream installer rewrites NetworkManager and resolv.conf. Use its portable
application with distro .NET instead, retaining the existing present-only marker. |
| Technitium native ¦ Preview RPM installation in check mode | ansible.builtin.debug | True |  |
| Technitium native ¦ Install and configure the RPM application | block | True |  |
| Technitium native ¦ Install distribution runtime and DNS tools | ansible.builtin.dnf | False |  |
| Technitium native ¦ Ensure service group exists | ansible.builtin.group | False |  |
| Technitium native ¦ Ensure non-login service account exists | ansible.builtin.user | False |  |
| Technitium native ¦ Ensure root-owned application directory exists | ansible.builtin.file | False |  |
| Technitium native ¦ Ensure private application data directories exist | ansible.builtin.file | False |  |
| Technitium native ¦ Download the portable application only for a fresh installation | ansible.builtin.get_url | True |  |
| Technitium native ¦ Extract the application without upgrading an existing installation | ansible.builtin.unarchive | True |  |
| Technitium native ¦ Require the application marker before starting DNS | ansible.builtin.stat | False |  |
| Technitium native ¦ Verify the extracted application | ansible.builtin.assert | False |  |
| Technitium native ¦ Configure the systemd unit | ansible.builtin.template | False |  |
| Native services ¦ Record the adopted Technitium unit | ansible.builtin.include_tasks | False |  |
| Technitium native ¦ Reconcile only active systemd-resolved integration | ansible.builtin.include_tasks | True |  |
| Technitium native ¦ Complete resolver and unit notifications before readiness | ansible.builtin.meta | False |  |
| Technitium native ¦ Enable and start the selected service | ansible.builtin.systemd_service | False |  |
| Technitium native ¦ Check listener readiness | ansible.builtin.include_tasks | False |  |

#### File: tasks/technitium_ready.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Technitium native ¦ Wait for web console | ansible.builtin.wait_for | False |
| Technitium native ¦ Wait for DNS listener | ansible.builtin.wait_for | False |
| Technitium native ¦ Test local DNS recursion | ansible.builtin.command | False |

#### File: tasks/technitium_validate.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Technitium native ¦ Inspect resolver service availability | ansible.builtin.service_facts | True |
| Technitium native ¦ Resolve current resolver ownership scope | ansible.builtin.set_fact | False |
| Technitium native ¦ Validate RPM installation settings | ansible.builtin.assert | True |
| Technitium native ¦ Inspect active resolved output before adopting its resolver | ansible.builtin.stat | True |
| Technitium native ¦ Refuse a dangling resolver link | ansible.builtin.assert | True |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
