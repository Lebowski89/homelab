"""Synthetic credential source ONLY. No network; not an Infisical acceptance test.

Runtime secret creation, attachment, replacement and removal remain the real
production adapter tasks. A separate collection path prevents this provider
from ever being enabled by normal Skynet/workstation configuration.
"""

import json
import os
import re
from pathlib import Path

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        run_id = (variables or {}).get("molecule_vm_run_id", "")
        if (
            not re.fullmatch(r"[a-f0-9]{32}", run_id)
            or kwargs.get("path") != "/molecule/" + run_id
            or kwargs.get("secret_name") != "credential"
        ):
            raise AnsibleError("The VM credential fixture refuses non-fixture declarations")
        path = Path(os.environ["HOMELAB_MOLECULE_SECRET_FILE"])
        if path.is_symlink() or path.stat().st_mode & 0o077:
            raise AnsibleError("The synthetic credential file must be private")
        data = json.loads(path.read_text())
        if data["run_id"] != run_id:
            raise AnsibleError("Synthetic credential belongs to a different run")
        return [{"value": data["credential"]}]
