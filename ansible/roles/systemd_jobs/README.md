<!-- DOCSIBLE START -->

# 📃 Role overview

## systemd_jobs





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/08/11 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [systemd_jobs](defaults/main.yml#L3)   | list | `[]` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions | Tags |
| ---- | ------ | -------------- | -----|
| Systemd jobs ¦ Validate job collection | ansible.builtin.assert | False |  |
| Systemd jobs ¦ Validate job entries are mappings | ansible.builtin.assert | False |  |
| Systemd jobs ¦ Validate job names | ansible.builtin.assert | False |  |
| Systemd jobs ¦ Validate unique job names | ansible.builtin.assert | False |  |
| Systemd jobs ¦ Validate service and timer mappings | ansible.builtin.assert | False |  |
| Systemd jobs ¦ Validate supported job fields | ansible.builtin.assert | False |  |
| Systemd jobs ¦ Validate systemd host | ansible.builtin.assert | True |  |
| Systemd jobs ¦ Render service units | ansible.builtin.template | False |  |
| Systemd jobs ¦ Render timer units | ansible.builtin.template | False |  |
| Systemd jobs ¦ Reload systemd for changed units | ansible.builtin.systemd_service | True |  |
| Systemd jobs ¦ Apply timer lifecycle | ansible.builtin.systemd_service | True |  |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
