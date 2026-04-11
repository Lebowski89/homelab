## Requirements

- `ansible/requirements.yml` is for **Ansible Galaxy collections/roles**.
- Some modules also need **Python libraries on the Ansible control node** (for example `community.postgresql.*` needs `psycopg2`).
- Controller-side Python dependencies are listed in `ansible/requirements.txt`.

Install both before running playbooks:

```bash
ansible-galaxy collection install -r ansible/requirements.yml
pip install -r ansible/requirements.txt
```

You can also simply run the playbook without installing requirements, with each run fail accompanied with a list of commands for you to run to install those required. Rinse and repeat until you have all the requirements.
