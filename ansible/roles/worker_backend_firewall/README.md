<!-- DOCSIBLE START -->

# 📃 Role overview

## worker_backend_firewall





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/10/20 |














### Tasks


#### File: tasks/check.yml

| Name | Module | Has Conditions | Comments |
| ---- | ------ | -------------- | -------- |
| Worker backend firewall ¦ Forward the retained check task entry | ansible.builtin.include_role | False | Compatibility for saved tasks_from imports; implementation is owned by service_firewall. |

#### File: tasks/install.yml

| Name | Module | Has Conditions | Comments |
| ---- | ------ | -------------- | -------- |
| Worker backend firewall ¦ Forward the retained install task entry | ansible.builtin.include_role | False | Compatibility for saved tasks_from imports; implementation is owned by service_firewall. |

#### File: tasks/main.yml

| Name | Module | Has Conditions | Comments |
| ---- | ------ | -------------- | -------- |
| Worker backend firewall ¦ Forward to the canonical profile | ansible.builtin.include_role | False | Compatibility for retained role invocations; service_firewall is the only owner. |

#### File: tasks/remove.yml

| Name | Module | Has Conditions | Comments |
| ---- | ------ | -------------- | -------- |
| Worker backend firewall ¦ Forward the retained remove task entry | ansible.builtin.include_role | False | Compatibility for saved tasks_from imports; implementation is owned by service_firewall. |

#### File: tasks/systemd.yml

| Name | Module | Has Conditions | Comments |
| ---- | ------ | -------------- | -------- |
| Worker backend firewall ¦ Forward the retained systemd task entry | ansible.builtin.include_role | False | Compatibility for saved tasks_from imports; implementation is owned by service_firewall. |

#### File: tasks/unraid.yml

| Name | Module | Has Conditions | Comments |
| ---- | ------ | -------------- | -------- |
| Worker backend firewall ¦ Forward the retained unraid task entry | ansible.builtin.include_role | False | Compatibility for saved tasks_from imports; implementation is owned by service_firewall. |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
