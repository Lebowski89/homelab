<!-- DOCSIBLE START -->

# 📃 Role overview

## opentofu





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/10/23 |














### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Configure Proxmox API access | ansible.builtin.include_tasks | True | opentofu,opentofu_pve_user |

#### File: tasks/sub_tasks/pve_user.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Assert required OpenTofu Proxmox user vars are defined | ansible.builtin.assert | False |
| Manage Proxmox OpenTofu API objects | block | False |
| Ensure OpenTofu Proxmox role exists | community.proxmox.proxmox_role | False |
| Ensure OpenTofu Proxmox user exists | community.proxmox.proxmox_user | False |
| Ensure OpenTofu role is assigned at root path | community.proxmox.proxmox_access_acl | False |
| List existing OpenTofu API tokens | ansible.builtin.command | False |
| Determine whether OpenTofu API token needs to be created | ansible.builtin.set_fact | True |
| Initialize OpenTofu API token handoff state | ansible.builtin.set_fact | True |
| Create and hand off OpenTofu API token transactionally | block | True |
| Create root-only temporary token handoff file | ansible.builtin.tempfile | False |
| Create OpenTofu API token if missing | ansible.builtin.command | False |
| Write new API token secret to handoff file | ansible.builtin.copy | False |
| Record that the API token secret is recoverable | ansible.builtin.set_fact | False |
| Pause so operator can copy token | ansible.builtin.pause | False |
| Remove temporary token handoff file after acknowledgment | ansible.builtin.file | False |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
