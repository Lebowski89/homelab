#!/usr/bin/python3
"""Publish a bounded journal observation without exporting log payloads."""

import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

UNIT = "skynet-alloy-journal-probe.service"
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
    recent = query("--lines=64", "--output-fields=UNIT,_SYSTEMD_UNIT")
    # The timer itself must not supply the expected traffic on an otherwise idle host.
    active = any(UNIT not in (entry.get("UNIT"), entry.get("_SYSTEMD_UNIT")) for entry in map(json.loads, recent))
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
