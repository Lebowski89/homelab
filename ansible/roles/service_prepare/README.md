<!-- DOCSIBLE START -->

# 📃 Role overview

## service_prepare





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/07/29 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [service_prepare_context](defaults/main.yml#L3)   | dict | `{}` |    
| [service_prepare_template_vars](defaults/main.yml#L4)   | dict | `{}` |    
| [service_prepare_generated_secret_values](defaults/main.yml#L5)   | dict | `{}` |    
| [service_prepare_generated_secret_declarations](defaults/main.yml#L6)   | list | `[]` |    
| [service_prepare_bootstrap_requests](defaults/main.yml#L7)   | dict | `{}` |    





### Tasks


#### File: tasks/applications/authelia/derive_templates.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Authelia prepare ¦ Build selected-runtime password-hash request | ansible.builtin.set_fact | False |  |
| Authelia prepare ¦ Run selected-runtime password-hash generator | ansible.builtin.include_tasks | False |  |
| Authelia prepare ¦ Publish password hash | ansible.builtin.set_fact | False |  |
| Authelia prepare ¦ Validate password hash | ansible.builtin.assert | False |  |

#### File: tasks/applications/authelia/generate_secret.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Authelia prepare ¦ Build selected-runtime secret generation request | ansible.builtin.set_fact | True |  |
| Authelia prepare ¦ Run selected-runtime secret generator | ansible.builtin.include_tasks | True |  |
| Authelia prepare ¦ Extract generated secret value | ansible.builtin.set_fact | True |  |
| Authelia prepare ¦ Validate generated secret value | ansible.builtin.assert | True |  |
| Authelia prepare ¦ Publish generated secret value | ansible.builtin.set_fact | True |  |
| Authelia prepare ¦ Publish value-free declaration | ansible.builtin.set_fact | False |  |

#### File: tasks/applications/authelia/generate_secrets.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Authelia prepare ¦ Generate runtime secret values | ansible.builtin.include_tasks | False |  |

#### File: tasks/applications/authelia/validate.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Authelia prepare ¦ Validate hash and key contract | ansible.builtin.assert | False |  |
| Authelia prepare ¦ Publish temporary generation request | ansible.builtin.set_fact | False |  |

#### File: tasks/applications/bazarr/bootstrap.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Bazarr prepare ¦ Build selected-runtime initial configuration request | ansible.builtin.set_fact | False |  |
| Bazarr prepare ¦ Run selected-runtime initial configuration generator | ansible.builtin.include_tasks | False |  |

#### File: tasks/applications/bazarr/configure.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Prep - Bazarr ¦ Set derived vars | ansible.builtin.set_fact | False |  |
| Prep - Bazarr ¦ Set secret vars | ansible.builtin.set_fact | False |  |
| Prep - Bazarr ¦ Set postgres vars | ansible.builtin.set_fact | True |  |
| Prep - Bazarr ¦ Assert postgres inputs are complete | ansible.builtin.assert | True |  |
| Prep - Bazarr ¦ Check whether initial config exists | ansible.builtin.stat | False |  |
| Prep - Bazarr ¦ Generate absent initial config with selected runtime | ansible.builtin.include_tasks | True |  |
| Prep - Bazarr ¦ Verify runtime bootstrap produced config | ansible.builtin.stat | False |  |
| Prep - Bazarr ¦ Require generated config before mutation | ansible.builtin.assert | False |  |
| Prep - Bazarr ¦ Configure api setting | yedit | False |  |
| Prep - Bazarr ¦ Configure misc settings | yedit | False |  |
| Prep - Bazarr ¦ Configure opensubtitlescom settings | yedit | False |  |
| Prep - Bazarr ¦ Configure radarr settings | yedit | False |  |
| Prep - Bazarr ¦ Configure sonarr settings | yedit | False |  |
| Prep - Bazarr ¦ Configure postgres settings | yedit | False |  |

#### File: tasks/applications/bazarr/validate.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Bazarr prepare ¦ Validate configuration contract | ansible.builtin.assert | False |  |

#### File: tasks/applications/nzbhydra2/bootstrap.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| NZBHydra2 prepare ¦ Build selected-runtime initial configuration request | ansible.builtin.set_fact | False |  |
| NZBHydra2 prepare ¦ Run selected-runtime initial configuration generator | ansible.builtin.include_tasks | False |  |

#### File: tasks/applications/nzbhydra2/configure.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Prep - NZBHydra2 ¦ Set filesystem host | ansible.builtin.set_fact | False |  |
| Prep - NZBHydra2 ¦ Set derived vars | ansible.builtin.set_fact | False |  |
| Prep - NZBHydra2 ¦ Assert required secrets are present | ansible.builtin.assert | False |  |
| Prep - NZBHydra2 ¦ Assert altHUB secrets are complete when used | ansible.builtin.assert | False |  |
| Prep - NZBHydra2 ¦ Assert NZBGeek secrets are complete when used | ansible.builtin.assert | False |  |
| Prep - NZBHydra2 ¦ Assert Drunken Slug secrets are complete when used | ansible.builtin.assert | False |  |
| Prep - NZBHydra2 ¦ Check whether initial config exists | ansible.builtin.stat | False |  |
| Prep - NZBHydra2 ¦ Generate absent initial config with selected runtime | ansible.builtin.include_tasks | True |  |
| Prep - NZBHydra2 ¦ Verify runtime bootstrap produced config | ansible.builtin.stat | False |  |
| Prep - NZBHydra2 ¦ Require generated config before mutation | ansible.builtin.assert | False |  |
| Prep - NZBHydra2 ¦ Mark generated config ready for management | ansible.builtin.set_fact | False |  |
| Prep - NZBHydra2 ¦ Build config facts | ansible.builtin.set_fact | False |  |
| Prep - NZBHydra2 ¦ Set auth user | yedit | True |  |
| Prep - NZBHydra2 ¦ Set API key | yedit | True |  |
| Prep - NZBHydra2 ¦ Report API key update in check mode | ansible.builtin.debug | True |  |
| Prep - NZBHydra2 ¦ Replace downloaders list | block | True |  |
| Prep - NZBHydra2 ¦ Remove existing downloaders | yedit | False |  |
| Prep - NZBHydra2 ¦ Write managed downloaders | yedit | False |  |
| Prep - NZBHydra2 ¦ Replace indexers list | block | True |  |
| Prep - NZBHydra2 ¦ Remove existing indexers | yedit | False |  |
| Prep - NZBHydra2 ¦ Write managed indexers | yedit | False |  |
| Prep - NZBHydra2 ¦ Report managed config update in check mode | ansible.builtin.debug | True |  |
| Prep - NZBHydra2 ¦ Ensure config file permissions are restricted | ansible.builtin.file | True |  |
| Prep - NZBHydra2 ¦ Slurp config | ansible.builtin.slurp | True |  |
| Prep - NZBHydra2 ¦ Parse config YAML | ansible.builtin.set_fact | True |  |
| Prep - NZBHydra2 ¦ Assert API key set | ansible.builtin.assert | True |  |
| Prep - NZBHydra2 ¦ Assert SABnzbd downloader is set | ansible.builtin.assert | True |  |
| Prep - NZBHydra2 ¦ Assert configured indexers were written | ansible.builtin.assert | True |  |

#### File: tasks/applications/nzbhydra2/validate.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| NZBHydra2 prepare ¦ Validate configuration contract | ansible.builtin.assert | False |  |

#### File: tasks/applications/plex/_claim.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Claim ¦ Set derived vars | ansible.builtin.set_fact | False |
| Claim ¦ Load token + client identifier from token host | ansible.builtin.set_fact | False |
| Claim ¦ Assert required vars exist | ansible.builtin.assert | False |
| Claim ¦ Check if Plex server is already claimed | ansible.builtin.stat | False |
| Claim ¦ Read Preferences.xml | community.general.xml | True |
| Claim ¦ Determine claimed status | ansible.builtin.set_fact | False |
| Claim ¦ Request claim token from plex.tv | ansible.builtin.uri | True |
| Claim ¦ Persist claim code to token host | ansible.builtin.set_fact | True |
| Claim ¦ Validate claim code | ansible.builtin.assert | True |
| Claim ¦ Report claim status | ansible.builtin.debug | False |

#### File: tasks/applications/plex/_preferences.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - Plex Preferences ¦ Conduct preferences.xml tasks | block | False |
| Prep - Plex Preferences ¦ Set derived vars | ansible.builtin.set_fact | False |
| Prep - Plex Preferences ¦ Check if Preferences.xml exists | ansible.builtin.stat | False |
| Prep - Plex Preferences ¦ Read Preferences.xml attributes | community.general.xml | True |
| Prep - Plex Preferences ¦ Remove Preferences.xml if malformed | ansible.builtin.file | True |
| Prep - Plex Preferences ¦ Derive flags from Preferences.xml | ansible.builtin.set_fact | True |
| Prep - Plex Preferences ¦ Fix TranscoderTempDirectory | community.general.xml | True |

#### File: tasks/applications/plex/_token.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Prep - Plex Token ¦ Set file ownership facts | ansible.builtin.set_fact | False |
| Prep - Plex Token ¦ Check if plex.ini exists | ansible.builtin.stat | False |
| Prep - Plex Token ¦ Set client identifier fact | block | True |
| Prep - Plex Token ¦ Lookup client_identifier | ansible.builtin.set_fact | False |
| Prep - Plex Token ¦ Generate new identifier | ansible.builtin.set_fact | True |
| Prep - Plex Token ¦ Set token variable if previously saved | ansible.builtin.set_fact | True |
| Prep - Plex Token ¦ Set service_prepare_plex_no_token status | ansible.builtin.set_fact | False |
| Prep - Plex Token ¦ Check if Token is valid | ansible.builtin.uri | True |
| Prep - Plex Token ¦ Generate New Token | block | True |
| Prep - Plex Token ¦ Generate PIN | ansible.builtin.uri | False |
| Prep - Plex Token ¦ Login prompt | ansible.builtin.pause | False |
| Prep - Plex Token ¦ Check PIN | ansible.builtin.uri | False |
| Prep - Plex Token ¦ Set service_prepare_plex_auth_token variable | ansible.builtin.set_fact | False |
| Prep - Plex Token ¦ Check if new Token is valid | ansible.builtin.uri | False |
| Prep - Plex Token ¦ Fail if new token is invalid | ansible.builtin.fail | True |
| Prep - Plex Token ¦ Add Client Identifier to plex.ini | community.general.ini_file | False |
| Prep - Plex Token ¦ Add Token to plex.ini | community.general.ini_file | False |
| Prep - Plex Token ¦ Report token status | ansible.builtin.debug | True |

#### File: tasks/applications/plex/tasker.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Prep - Plex Prep ¦ Set derived vars | ansible.builtin.set_fact | False |  |
| Prep - Plex Prep ¦ Assert derived hosts are valid | ansible.builtin.assert | False |  |
| Prep - Plex Token ¦ Include token tasks | ansible.builtin.include_tasks | False |  |
| Prep - Plex Preferences ¦ Include Plex preferences.xml tasks | ansible.builtin.include_tasks | False |  |
| Prep - Plex Claim ¦ Include claim server tasks | ansible.builtin.include_tasks | False |  |

#### File: tasks/applications/plex/validate.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Plex prepare ¦ Validate explicit bootstrap declaration | ansible.builtin.assert | False |  |

#### File: tasks/applications/qbittorrent/derive_templates.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| QBittorrent prepare ¦ Derive password hash | qbittorrent_passwd | False |
| QBittorrent prepare ¦ Validate derived password hash | ansible.builtin.assert | False |
| QBittorrent prepare ¦ Publish template value | ansible.builtin.set_fact | False |

#### File: tasks/applications/qbittorrent/validate.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| QBittorrent prepare ¦ Resolve instance contract | ansible.builtin.set_fact | False |  |
| QBittorrent prepare ¦ Validate instance and password | ansible.builtin.assert | False |  |

#### File: tasks/applications/vaultwarden/generate_secrets.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Vaultwarden prepare ¦ Resolve persistent token paths | ansible.builtin.set_fact | False |
| Vaultwarden prepare ¦ Ensure persistent token directory exists | ansible.builtin.file | False |
| Vaultwarden prepare ¦ Check for persistent admin token | ansible.builtin.stat | False |
| Vaultwarden prepare ¦ Read persistent admin token | ansible.builtin.slurp | True |
| Vaultwarden prepare ¦ Generate and persist initial admin token | block | True |
| Vaultwarden prepare ¦ Generate random password | ansible.builtin.command | False |
| Vaultwarden prepare ¦ Persist generated password | ansible.builtin.copy | False |
| Vaultwarden prepare ¦ Generate random salt | ansible.builtin.command | False |
| Vaultwarden prepare ¦ Generate Argon2 PHC token | ansible.builtin.command | False |
| Vaultwarden prepare ¦ Persist Argon2 admin token | ansible.builtin.copy | False |
| Vaultwarden prepare ¦ Resolve persistent admin token value | ansible.builtin.set_fact | False |
| Vaultwarden prepare ¦ Validate persistent admin token format | ansible.builtin.assert | False |
| Vaultwarden prepare ¦ Publish generated value and value-free declaration | ansible.builtin.set_fact | False |

#### File: tasks/applications/vaultwarden/validate.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Vaultwarden prepare ¦ Validate persistent token contract | ansible.builtin.assert | False |  |

#### File: tasks/bootstrap.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Application bootstrap ¦ Include explicit Plex bootstrap | ansible.builtin.include_tasks | True |  |

#### File: tasks/configure.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Application configuration ¦ Include Bazarr configuration | ansible.builtin.include_tasks | True |  |
| Application configuration ¦ Include NZBHydra2 configuration | ansible.builtin.include_tasks | True |  |

#### File: tasks/derive_templates.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Application template derivation ¦ Include Authelia derivation | ansible.builtin.include_tasks | True |  |
| Application template derivation ¦ Include qBittorrent derivation | ansible.builtin.include_tasks | True |  |

#### File: tasks/generate_secrets.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Application secret generation ¦ Validate retained current-service outputs | ansible.builtin.assert | False |  |
| Application secret generation ¦ Include Authelia generation | ansible.builtin.include_tasks | True |  |
| Application secret generation ¦ Include Vaultwarden generation | ansible.builtin.include_tasks | True |  |

#### File: tasks/runtimes/docker/temporary_container_remove.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Docker temporary preparation ¦ Remove container | community.docker.docker_container | True |

#### File: tasks/runtimes/docker/temporary_container_start.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Docker temporary preparation ¦ Remove stale container | community.docker.docker_container | True |
| Docker temporary preparation ¦ Start container | community.docker.docker_container | True |
| Docker temporary preparation ¦ Publish foreground output | ansible.builtin.set_fact | True |

#### File: tasks/runtimes/podman/temporary_container_remove.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Podman temporary preparation ¦ Remove container | containers.podman.podman_container | True |

#### File: tasks/runtimes/podman/temporary_container_start.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Podman temporary preparation ¦ Remove stale container | containers.podman.podman_container | True |
| Podman temporary preparation ¦ Start container | containers.podman.podman_container | True |
| Podman temporary preparation ¦ Publish foreground output | ansible.builtin.set_fact | True |

#### File: tasks/runtimes/temporary_container.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Temporary preparation container ¦ Validate request | ansible.builtin.assert | False |  |
| Temporary preparation container ¦ Reset execution output | ansible.builtin.set_fact | False |  |
| Temporary preparation container ¦ Execute with guaranteed cleanup | block | True |  |
| Temporary preparation container ¦ Start selected runtime executor | ansible.builtin.include_tasks | False |  |
| Temporary preparation container ¦ Wait for generated file | ansible.builtin.wait_for | True |  |
| Temporary preparation container ¦ Wait for generated file stability | ansible.builtin.shell | True |  |
| Temporary preparation container ¦ Allow generated file write to settle | ansible.builtin.pause | True |  |

#### File: tasks/validate.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Application prepare validation ¦ Validate explicit context | ansible.builtin.assert | False |  |
| Application prepare validation ¦ Reset current-service outputs | ansible.builtin.set_fact | False |  |
| Application prepare validation ¦ Normalize handler declaration | ansible.builtin.set_fact | False |  |
| Application prepare validation ¦ Validate handler declaration | ansible.builtin.assert | False |  |
| Application prepare validation ¦ Reject remaining Docker-only Plex bootstrap on Podman | ansible.builtin.fail | True |  |
| Application prepare validation ¦ Include handler validation | ansible.builtin.include_tasks | True |  |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
