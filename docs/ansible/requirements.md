## Requirements

- `ansible/requirements.yml` is for **Ansible Galaxy collections/roles**.
- Some modules also need **Python libraries on the Ansible control node** (for example `community.postgresql.*` needs `psycopg2`).
- Controller-side Python dependencies are listed in `ansible/requirements.txt`.

Typically, you'd manually install both before running playbooks:

```bash
ansible-galaxy collection install -r ansible/requirements.yml
pip install -r ansible/requirements.txt
```
The existing workstation role owns workstation dependency installation through
`workstation_ansible` (venv plus pinned Python dependencies) and
`workstation_collections` (collections in the configured path).
See [workstation setup](../cheat_sheets/workstation-setup.md).

Python needed on a delegated managed host remains a separate requirement. In
particular, PostgreSQL reconciliation still executes on mgt and retains its
host-local interpreter and dependencies; workstation installation does not
replace them.
