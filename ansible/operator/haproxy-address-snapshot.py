#!/usr/bin/python3
"""Operator-only address snapshot; no listeners, probes or firewall operations."""

from __future__ import annotations

import importlib.util
import ipaddress
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("snapshot_cutover", Path(__file__).with_name("haproxy-cutover.py"))
CUTOVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CUTOVER)
QUERY = (
    "import json,socket,subprocess;from pathlib import Path;"
    'print(json.dumps({"identity":{"hostname":socket.gethostname(),'
    '"boot_id":Path("/proc/sys/kernel/random/boot_id").read_text().strip()},'
    '"links":json.loads(subprocess.check_output(["ip","-j","address","show"],text=True))}))'
)


def classify(mgt, peer, mgt_address, peer_address, cgroup, identity_error=""):
    """Select address candidates only; routing and denial remain untested."""
    rows = []

    def addresses(report, interface=None, version=None):
        return [
            {"address": str(ipaddress.ip_address(a["local"])), "interface": link["ifname"]}
            for link in report["links"]
            for a in link.get("addr_info", [])
            if (interface is None or link["ifname"] == interface)
            and (version is None or ipaddress.ip_address(a["local"]).version == version)
        ]

    def row(category, required, selected, reason=""):
        rows.append(
            {
                "category": category,
                "required": required,
                "selected": [dict(address) for address in selected],
                "status": "selected" if selected else "unavailable",
                "reason": reason,
            }
        )

    categories = ["LAN IPv4", "Alternate mgt LAN IPv4", "LAN IPv6", "Tailscale IPv4", "Tailscale IPv6", "Unrelated local root"]
    if identity_error:
        for category in categories:
            row(category, category != "LAN IPv6", [], identity_error)
        return rows
    local, remote = addresses(mgt), addresses(peer)
    lan = [a for a in local if a["address"] == mgt_address]
    peer_lan = [a for a in remote if a["address"] == peer_address]
    if len(lan) != 1 or len(peer_lan) != 1:
        return classify(
            mgt,
            peer,
            mgt_address,
            peer_address,
            cgroup,
            "inventory address must select exactly one interface on each host: "
            f"mgt {mgt_address} matches={len(lan)}; Plex {peer_address} matches={len(peer_lan)}",
        )
    row(
        "LAN IPv4",
        True,
        lan if ipaddress.ip_address(mgt_address).version == 4 else [],
        "inventory LAN address is not IPv4" if ipaddress.ip_address(mgt_address).version != 4 else "",
    )
    alternate = [a for a in addresses(mgt, lan[0]["interface"], 4) if a["address"] != mgt_address]
    row(
        "Alternate mgt LAN IPv4",
        True,
        alternate,
        "" if alternate else "no alternate IPv4 address on mgt inventory interface " + lan[0]["interface"],
    )
    lan6 = addresses(mgt, lan[0]["interface"], 6)
    row(
        "LAN IPv6",
        False,
        lan6,
        "" if lan6 else "unconfigured on mgt inventory interface " + lan[0]["interface"] + "; optional, no denial claimed",
    )
    if not lan6:
        rows[-1]["status"] = "unconfigured"
    for version in [4, 6]:
        candidates = CUTOVER.negative_tailscale_addresses(mgt["links"], version)
        sources = CUTOVER.negative_tailscale_addresses(peer["links"], version)
        selected, reason = [], ""
        if len(candidates) != 1:
            reason = f"mgt tailscale0 has {len(candidates)} usable global-scope unicast IPv{version} addresses; exactly one required"
        elif len(sources) != 1:
            reason = f"Plex tailscale0 has {len(sources)} usable global-scope unicast IPv{version} addresses; exactly one required"
        else:
            selected = [dict(candidates[0], peer_address=sources[0]["address"], peer_interface="tailscale0")]
        row(f"Tailscale IPv{version}", True, selected, reason)
    root_addresses = (
        lan + alternate + lan6 + [address for version in [4, 6] for address in CUTOVER.negative_tailscale_addresses(mgt["links"], version)]
    )
    loopback = [a for a in local if a["address"] in {"127.0.0.1", "::1"}]
    root_reason = ""
    if any(parent in cgroup for parent in CUTOVER.SLICES.values()):
        root_reason = "snapshot root process is inside an authorized operator slice"
    elif {a["address"] for a in loopback} != {"127.0.0.1", "::1"}:
        root_reason = "both loopback addresses 127.0.0.1 and ::1 must be observed"
    row("Unrelated local root", True, [] if root_reason else root_addresses + loopback, root_reason)
    for entry in rows[:2]:
        for selected in entry["selected"]:
            selected.update(peer_address=peer_address, peer_interface=peer_lan[0]["interface"])
    return rows


def snapshot(batch, peer_path, output):
    batch, output = Path(batch), Path(output)
    peer = CUTOVER.read(peer_path)
    ssh = CUTOVER.negative_peer_ssh(peer)
    owner = peer["operator"]["uid"]
    if os.geteuid() != 0 or output.stat().st_uid != owner or output.stat().st_mode & 0o077:
        raise ValueError("snapshot requires sudo and an operator-owned private output directory")
    expected = {r["host"]: r for r in CUTOVER.read(batch / "worker-offline-20261009T200449Z-2609904/worker-only.json.metadata.json")}
    if peer["inventory_host"] != "plex" or peer["inventory_address"] != expected["plex"]["inventory_address"]:
        raise ValueError("saved Plex inventory projection differs from validated inventory evidence")
    reports, errors = {}, []
    for host, command in [("mgt", [sys.executable, "-c", QUERY]), ("plex", ssh + [shlex.join(["/usr/bin/python3", "-c", QUERY])])]:
        try:
            result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=20)
        except (OSError, subprocess.TimeoutExpired) as error:
            errors.append(f"{host}: address query failed: {type(error).__name__}")
            partial = getattr(error, "stdout", None) or ""
            if isinstance(partial, bytes):
                partial = partial.decode(errors="replace")
            reason = "query exceeded 20 seconds" if isinstance(error, subprocess.TimeoutExpired) else error.strerror
            result = subprocess.CompletedProcess(command, 1, partial, str(reason))
        # Preserve stdout before parsing, identity validation or classification.
        path = output / (host + ".json")
        with open(path, "x", opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
            stream.write(result.stdout)
        os.chown(path, owner, -1)
        print(
            json.dumps(
                {
                    "host": host,
                    "operation": "identity/address snapshot",
                    "status": result.returncode,
                    "stderr": result.stderr.strip()[:2000],
                    "saved": str(path),
                }
            ),
            flush=True,
        )
        if result.returncode or result.stderr.strip():
            errors.append(f"{host}: query status={result.returncode}; see labeled stderr")
            continue
        try:
            reports[host] = json.loads(result.stdout)
            if reports[host]["identity"] != expected[host]["identity"]:
                errors.append(f"{host}: hostname/boot identity differs from validated host")
            if not isinstance(reports[host]["links"], list):
                raise ValueError("links must be an array")
            for link in reports[host]["links"]:
                if not isinstance(link["ifname"], str) or not link["ifname"] or not isinstance(link["addr_info"], list):
                    raise ValueError("invalid interface projection")
                for address in link["addr_info"]:
                    ipaddress.ip_address(address["local"])
        except (ValueError, KeyError, TypeError):
            errors.append(f"{host}: invalid or incomplete identity/address JSON")
    rows = classify(
        reports.get("mgt", {}),
        reports.get("plex", {}),
        expected["mgt"]["inventory_address"],
        peer["inventory_address"],
        Path("/proc/self/cgroup").read_text(),
        "; ".join(errors),
    )
    report = {
        "coverage": rows,
        "ports": [5432, 18405],
        "denial_tested": False,
        "source_peer_projection": str(Path(peer_path).resolve()),
        "note": "Address candidates only; routes, active listeners and DROP counters remain untested.",
    }
    CUTOVER.write(output / "coverage.json", report)
    os.chown(output / "coverage.json", owner, -1)
    for row in rows:
        print(json.dumps(row), flush=True)
    return 1 if any(row["required"] and row["status"] != "selected" for row in rows) else 0


if __name__ == "__main__":
    try:
        if len(sys.argv) != 4:
            raise ValueError("requires batch, saved peer projection and fresh private output directory")
        sys.exit(snapshot(*sys.argv[1:]))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("Address snapshot: " + str(error), file=sys.stderr)
        sys.exit(1)
