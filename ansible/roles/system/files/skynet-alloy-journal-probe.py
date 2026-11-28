#!/usr/bin/python3
"""Publish a bounded journal observation without exporting log payloads."""

import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

PROBE_UNITS = ("skynet-alloy-journal-probe.service", "skynet-alloy-journal-probe.timer")
# Match the container exclusions in the native Alloy journal configuration.
PRIVATE_CONTAINERS = ("jdownloader2", "mullvad-browser")
OUTPUT = Path("/var/lib/node_exporter/textfile_collector/alloy_journal_probe.prom")
READ_ERROR = re.compile(
    r"failed to read journal entry|failed waiting for journal entry|sd_journal_next failed|error creating journal tailer"
)


def query(*args):
    return subprocess.run(
        ["/usr/bin/journalctl", "--since=-5min", "--quiet", "--no-pager", "--output=json", *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout.splitlines()


def sample():
    unit_fields = ("UNIT", "_SYSTEMD_UNIT", "OBJECT_SYSTEMD_UNIT")
    recent = query("--lines=64", f"--output-fields={','.join(unit_fields)},CONTAINER_NAME,MESSAGE")
    # Count only evidence of demand that the collector could actually forward.
    active = any(
        entry.get("MESSAGE")
        and entry.get("CONTAINER_NAME") not in PRIVATE_CONTAINERS
        and all(entry.get(field) not in PROBE_UNITS for field in unit_fields)
        for entry in map(json.loads, recent)
    )
    # Read only this unit's recent messages. Never publish their contents.
    messages = query("--unit=alloy.service", "--output-fields=MESSAGE", "--lines=6000")
    errors = sum(
        isinstance(message, str) and bool(READ_ERROR.search(message))
        for message in (json.loads(entry).get("MESSAGE") for entry in messages)
    )
    return (
        f"skynet_alloy_journal_probe_timestamp_seconds {int(time.time())}\n"
        f"skynet_alloy_journal_recent_activity {int(active)}\n"
        f"skynet_alloy_journal_recent_read_errors {errors}\n"
    )


def main():
    content = sample()
    with tempfile.NamedTemporaryFile(dir=OUTPUT.parent, mode="w", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(content)
            stream.flush()
            os.fchmod(stream.fileno(), 0o644)
            temporary.replace(OUTPUT)
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
