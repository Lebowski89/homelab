## Requirements

- `ansible/requirements.yml` is for **Ansible Galaxy collections/roles**.
- Some modules also need **Python libraries on the Ansible control node** (for example `community.postgresql.*` needs `psycopg2`).
- Controller-side Python dependencies are listed in `ansible/requirements.txt`.

Typically, you'd manually install both before running playbooks:

```bash
ansible-galaxy collection install -r ansible/requirements.yml
pip install -r ansible/requirements.txt
```
... but we're about that automation life, so the Ubuntu role will take care of it (via ubuntu or ubuntu_requirements tag).
