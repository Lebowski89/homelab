<!-- DOCSIBLE START -->

# 📃 Role overview

## tailscale_bootstrap





| Field                | Value           |
|--------------------- |-----------------|
| Readme update        | 2026/07/21 |








### Defaults

**These are static variables with lower priority**

#### File: defaults/main.yml

| Var          | Type         | Value       |
|--------------|--------------|-------------|
| [tailscale_bootstrap_guest](defaults/main.yml#L3)   | str |  |    
| [tailscale_bootstrap_guests](defaults/main.yml#L4)   | dict | `{}` |    
| [tailscale_bootstrap_guest_agent_retries](defaults/main.yml#L5)   | int | `30` |    
| [tailscale_bootstrap_guest_agent_delay](defaults/main.yml#L6)   | int | `5` |    





### Tasks


#### File: tasks/main.yml

| Name | Module | Has Conditions |
| ---- | ------ | -------------- |
| Tailscale Bootstrap ¦ Refuse check mode | ansible.builtin.assert | False |
| Tailscale Bootstrap ¦ Validate guest selector | ansible.builtin.assert | False |
| Tailscale Bootstrap ¦ Load selected guest configuration | ansible.builtin.set_fact | False |
| Tailscale Bootstrap ¦ Validate selected guest configuration | ansible.builtin.assert | False |
| Tailscale Bootstrap ¦ Build effective guest configuration | ansible.builtin.set_fact | False |
| Tailscale Bootstrap ¦ Wait for QEMU Guest Agent | ansible.builtin.command | False |
| Tailscale Bootstrap ¦ Check whether Tailscale is installed | ansible.builtin.command | False |
| Tailscale Bootstrap ¦ Parse installation probe | ansible.builtin.set_fact | False |
| Tailscale Bootstrap ¦ Validate installation probe | ansible.builtin.assert | False |
| Tailscale Bootstrap ¦ Record installation state | ansible.builtin.set_fact | False |
| Tailscale Bootstrap ¦ Install Tailscale | ansible.builtin.command | True |
| Tailscale Bootstrap ¦ Parse installation result | ansible.builtin.set_fact | True |
| Tailscale Bootstrap ¦ Validate installation result | ansible.builtin.assert | True |
| Tailscale Bootstrap ¦ Enable and start tailscaled | ansible.builtin.command | False |
| Tailscale Bootstrap ¦ Parse tailscaled result | ansible.builtin.set_fact | False |
| Tailscale Bootstrap ¦ Validate tailscaled result | ansible.builtin.assert | False |
| Tailscale Bootstrap ¦ Query current Tailscale status | ansible.builtin.command | False |
| Tailscale Bootstrap ¦ Parse status envelope | ansible.builtin.set_fact | False |
| Tailscale Bootstrap ¦ Validate status envelope | ansible.builtin.assert | False |
| Tailscale Bootstrap ¦ Parse current Tailscale status | ansible.builtin.set_fact | False |
| Tailscale Bootstrap ¦ Record current backend state | ansible.builtin.set_fact | False |
| Tailscale Bootstrap ¦ Prompt for one-off authentication key | ansible.builtin.pause | True |
| Tailscale Bootstrap ¦ Validate supplied authentication key | ansible.builtin.assert | True |
| Tailscale Bootstrap ¦ Authenticate guest with Tailscale | ansible.builtin.command | True |
| Tailscale Bootstrap ¦ Parse authentication result | ansible.builtin.set_fact | True |
| Tailscale Bootstrap ¦ Record authentication result | ansible.builtin.set_fact | True |
| Tailscale Bootstrap ¦ Validate authentication result | ansible.builtin.assert | True |
| Tailscale Bootstrap ¦ Query final Tailscale status | ansible.builtin.command | False |
| Tailscale Bootstrap ¦ Parse final status envelope | ansible.builtin.set_fact | False |
| Tailscale Bootstrap ¦ Validate final status command | ansible.builtin.assert | False |
| Tailscale Bootstrap ¦ Parse final Tailscale status | ansible.builtin.set_fact | False |
| Tailscale Bootstrap ¦ Assert Tailscale is connected | ansible.builtin.assert | False |
| Tailscale Bootstrap ¦ Query Tailscale IPv4 address | ansible.builtin.command | False |
| Tailscale Bootstrap ¦ Parse Tailscale IP result | ansible.builtin.set_fact | False |
| Tailscale Bootstrap ¦ Validate Tailscale IP result | ansible.builtin.assert | False |
| Tailscale Bootstrap ¦ Record Tailscale IPv4 address | ansible.builtin.set_fact | False |
| Tailscale Bootstrap ¦ Report result | ansible.builtin.debug | False |









#### Dependencies

No dependencies specified.
<!-- DOCSIBLE END -->
