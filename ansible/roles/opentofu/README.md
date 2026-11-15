<!-- DOCSIBLE START -->

# 📃 Role overview

## opentofu





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/11/16 |














### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Configure Proxmox API access | ansible.builtin.include_tasks | True | opentofu,opentofu_pve_user,opentofu_molecule_permissions |

#### File: tasks/sub_tasks/pve_molecule_permissions.yml

| Name | Module | Has Conditions | Comments |
| ---- | ------ | -------------- | -------- |
| Validate the dedicated Molecule permission declarations | ansible.builtin.assert | False |  |
| Validate dedicated roles before changing permissions | ansible.builtin.assert | False |  |
| Validate token ACL boundaries before changing permissions | ansible.builtin.assert | False |  |
| Inspect existing Molecule token separation without retrieving token secrets | community.proxmox.proxmox_user_info | False |  |
| Reduce token metadata to a separation guard | ansible.builtin.set_fact | False |  |
| Clear transient user and token metadata before validation or mutation | ansible.builtin.set_fact | False |  |
| Require both existing Molecule tokens to remain privilege-separated | ansible.builtin.assert | False |  |
| Inspect ownership and actual privileges before enabling the persistent pool | block | True |  |
| Obtain a private operator API session for pool preflight | ansible.builtin.uri | False |  |
| Discover existing roles through the role index | ansible.builtin.uri | False |  |
| Validate role-index structure before discovering missing roles | ansible.builtin.assert | False |  |
| Read the actual privileges of existing roles that will govern pool members | ansible.builtin.uri | True |  |
| Reject an existing pool role with different privileges | ansible.builtin.assert | True |  |
| Inspect existing pool identities | ansible.builtin.uri | False |  |
| Inspect the selected existing pool before granting access | ansible.builtin.uri | True |  |
| Require exactly one matching pool object in the selected-pool response | ansible.builtin.assert | True |  |
| Select the validated pool object for ownership checks | ansible.builtin.set_fact | True |  |
| Reject a foreign pool or non-disposable pool members | ansible.builtin.assert | True |  |
| Ensure the owned persistent acceptance pool exists without assigning members | community.proxmox.proxmox_pool | True |  |
| Reconcile only the declared Molecule roles | community.proxmox.proxmox_role | False |  |
| Report the exact token ACL plan in check mode | ansible.builtin.debug | True | community.proxmox 2.1.0 ACL management does not support check mode. |
| Ensure only the declared token ACL assignments | community.proxmox.proxmox_access_acl | True |  |
| Remove superseded direct acceptance VMID grants | community.proxmox.proxmox_access_acl | True | Remove only the superseded acceptance-token VMID grants, after the pool ACLs
exist. Keeping them would permit create/clone without specifying the pool. |

#### File: tasks/sub_tasks/pve_user.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Validate the optional Molecule permission-management switch | ansible.builtin.assert | False | opentofu_molecule_permissions |
| Reconcile declared permissions for existing Molecule tokens | ansible.builtin.include_tasks | True | opentofu_molecule_permissions |
| Assert required OpenTofu Proxmox user vars are defined | ansible.builtin.assert | False |  |
| Manage Proxmox OpenTofu API objects | block | False |  |
| Ensure OpenTofu Proxmox role exists | community.proxmox.proxmox_role | False |  |
| Ensure OpenTofu Proxmox user exists | community.proxmox.proxmox_user | False |  |
| Ensure OpenTofu role is assigned at root path | community.proxmox.proxmox_access_acl | False |  |
| List existing OpenTofu API tokens | ansible.builtin.command | False |  |
| Determine whether OpenTofu API token needs to be created | ansible.builtin.set_fact | True |  |
| Initialize OpenTofu API token handoff state | ansible.builtin.set_fact | True |  |
| Create and hand off OpenTofu API token transactionally | block | True |  |
| Create root-only temporary token handoff file | ansible.builtin.tempfile | False |  |
| Create OpenTofu API token if missing | ansible.builtin.command | False |  |
| Write new API token secret to handoff file | ansible.builtin.copy | False |  |
| Record that the API token secret is recoverable | ansible.builtin.set_fact | False |  |
| Pause so operator can copy token | ansible.builtin.pause | False |  |
| Remove temporary token handoff file after acknowledgment | ansible.builtin.file | False |  |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
