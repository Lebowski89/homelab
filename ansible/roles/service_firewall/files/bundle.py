"""Build a self-contained installed helper without changing its CLI or destination."""

from pathlib import Path


def bundled_helper(profile):
    if profile not in {"mgt", "workers"}:
        raise ValueError("unsupported service_firewall profile")
    root = Path(__file__).resolve().parent
    source = (root / "transactions.py").read_text()
    filename = "mgt-firewall.py" if profile == "mgt" else "worker-backend-firewall.py"
    helper = (root / filename).read_text()
    return helper.replace(
        "from __future__ import annotations", "from __future__ import annotations\n\nTRANSACTION_SOURCE = " + repr(source), 1
    )
