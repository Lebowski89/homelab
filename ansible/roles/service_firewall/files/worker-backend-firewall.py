#!/usr/bin/env python3
"""Reconcile only Skynet's temporary worker backend chains and marked jumps.

No daemon API, rule snapshot persistence, default policy changes or backend
switches. The check operation performs reads only. Standard library only.
"""

from __future__ import annotations

import argparse
import fcntl
import ipaddress
import json
import subprocess
import sys
import syslog
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from transactions import execute, local_addresses, read_table, table_patch, writer_lock

MARK = "skynet-worker-backends"
CHAINS = {"mangle": {"SKY-WBACK-PRE": ["PREROUTING"]}, "filter": {"SKY-WBACK-IN": ["INPUT"], "SKY-WBACK-FWD": ["FORWARD", "DOCKER-USER"]}}
JUMP_PREFIX = ["-m", "comment", "--comment", MARK, "-j"]
TERMINAL = JUMP_PREFIX + ["RETURN"]
RUN = Path("/run/skynet-worker-backend-firewall")

# Execute the same primitives in this profile namespace, preserving existing
# imports/monkeypatch contracts and the watcher's independently owned lock root.
_profile_doc = __doc__
exec(
    compile(
        globals().get("TRANSACTION_SOURCE") or Path(__file__).resolve().with_name("transactions.py").read_text(),
        "service_firewall.transactions",
        "exec",
    ),
    globals(),
)
__doc__ = _profile_doc


def validate_policy(policy):
    """Reject broad sources, invalid ports, and malformed operator confirmation."""
    if policy.get("schema") != 1 or policy.get("backend") not in {"legacy", "nf_tables"}:
        raise ValueError("policy schema/backend is unsupported")
    if type(policy.get("sources_verified")) is not bool or not policy["sources_verified"]:
        raise ValueError("sources_verified must be boolean true after observing the intended mgt container traffic")
    sources = policy.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("at least one exact verified source is required")
    for value in sources + [policy.get("inventory_address")]:
        if not isinstance(value, str) or "/" in value or "%" in value:
            raise ValueError("addresses must be bare IP addresses, never subnets")
        parsed = ipaddress.ip_address(value)
        if parsed.is_unspecified or parsed.is_loopback or parsed.is_multicast:
            raise ValueError("addresses must be non-loopback unicast")
    ports = policy.get("ports")
    if (
        not isinstance(ports, list)
        or not ports
        or any((not isinstance(port, int) or isinstance(port, bool)) or not 22601 <= port <= 22623 for port in ports)
    ):
        raise ValueError("ports must be a non-empty list from the temporary 22601..22623 allocation")
    if len(set(ports)) != len(ports) or len(set(sources)) != len(sources):
        raise ValueError("duplicate ports or sources are not permitted")
    return policy


def port_ranges(ports):
    """Coalesce adjacent publications without allowing holes in the allocation."""
    groups = []
    for port in sorted(ports):
        if groups and groups[-1][-1] + 1 == port:
            groups[-1].append(port)
        else:
            groups.append([port])
    return [str(group[0]) if len(group) == 1 else f"{group[0]}:{group[-1]}" for group in groups]


def desired_rules(policy, family, locals_):
    """Allow verified sources only for protected endpoints; return unrelated traffic."""
    sources = sorted({str(ipaddress.ip_address(ip)) for ip in policy["sources"] if ipaddress.ip_address(ip).version == family})
    addresses = sorted(
        {str(ipaddress.ip_address(ip)) for ip in locals_ | {policy["inventory_address"]} if ipaddress.ip_address(ip).version == family}
    )
    prefix = [["-i", "lo", "-j", "RETURN"], ["-m", "conntrack", "--ctdir", "REPLY", "-j", "RETURN"]]
    rules = {chain: [list(rule) for rule in prefix] for table in CHAINS.values() for chain in table}
    rules["SKY-WBACK-PRE"] += [["-s", ip, "-j", "RETURN"] for ip in sources]

    def restricted(chain, match):
        rules[chain] += [["-s", source] + match + ["-j", "ACCEPT"] for source in sources]
        rules[chain].append(match + ["-j", "DROP"])

    for port in port_ranges(policy["ports"]):
        # Runs before destination NAT and before any filter-table ACCEPT. LOCAL
        # covers new host addresses even before the next reconciliation.
        native = ["-p", "tcp", "-m", "addrtype", "--dst-type", "LOCAL", "--dport", port, "-j", "DROP"]
        rules["SKY-WBACK-PRE"].append(native)
        restricted("SKY-WBACK-IN", native[:-2])
        for ip in addresses:
            original = ["-p", "tcp", "-m", "conntrack", "--ctdir", "ORIGINAL", "--ctorigdst", ip, "--ctorigdstport", port]
            restricted("SKY-WBACK-IN", original)
            restricted("SKY-WBACK-FWD", original + ["--ctstate", "DNAT"])
    for chain in rules:
        rules[chain].append(TERMINAL)
    return rules


def reconcile(policy=None, operation="apply", backend=None, run=execute):
    """Apply/remove managed rules, or audit without any writes or restore calls."""
    if operation not in {"apply", "check", "remove"}:
        raise ValueError("unsupported reconciliation operation")
    if operation != "remove":
        validate_policy(policy)
        backend = policy["backend"]
        addresses = local_addresses(run)
    else:
        addresses = set()
    transactions = []
    for family, tool in [(4, "iptables"), (6, "ip6tables")]:
        if f"({backend})" not in run([tool, "--version"]):
            raise ValueError(f"{tool}: expected existing {backend} backend; backend switching is forbidden")
        desired = desired_rules(policy, family, addresses) if operation != "remove" else None
        payload = ""
        for table in CHAINS:
            state = read_table(run([f"{tool}-save", "-t", table]))
            required = {"PREROUTING"} if table == "mangle" else {"INPUT", "FORWARD"}
            if not required <= state.keys():
                raise ValueError(f"{tool}: required {table} base chains are unavailable")
            payload += table_patch(table, state, desired)
        if payload:
            transactions.append((f"{tool}-restore", payload))
    if operation == "check":
        return {"changed": False, "compliant": not transactions, "families": [4, 6]}
    for tool, payload in transactions:
        run([tool, "--test", "--noflush", "--wait", "10"], payload)
    for tool, payload in transactions:
        run([tool, "--noflush", "--wait", "10"], payload)
    return {"changed": bool(transactions), "families": [4, 6]}


def load_policy(path):
    return validate_policy(json.loads(Path(path).read_text()))


def watching():
    """Inspect our own lock without creating a file or touching another process."""
    try:
        with (RUN / "watch.lock").open("r") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
    except FileNotFoundError:
        pass
    return False


def watch(config):
    RUN.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (RUN / "watch.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        while not (RUN / "stop").exists():
            try:
                with writer_lock():
                    if (RUN / "stop").exists():
                        break
                    result = reconcile(load_policy(config))
                if result["changed"]:
                    syslog.syslog(syslog.LOG_NOTICE, f"{MARK}: reconciled worker policy")
            except (OSError, ValueError, RuntimeError) as error:
                syslog.syslog(syslog.LOG_ERR, f"{MARK}: {error}")
            time.sleep(5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["apply", "check", "remove", "watch", "start", "stop-watch"])
    parser.add_argument("--config")
    parser.add_argument("--backend", choices=["legacy", "nf_tables"])
    args = parser.parse_args()
    if args.operation in {"apply", "check", "watch", "start"} and not args.config:
        parser.error("this operation requires --config")
    if args.operation == "remove" and not args.backend:
        parser.error("removal requires the existing --backend")
    # Even direct helper invocation rejects unverified inputs before lock/state
    # files are created. Removal and stopping the watcher remain independent.
    policy = load_policy(args.config) if args.operation in {"apply", "check", "watch", "start"} else None
    if args.operation == "watch":
        watch(args.config)
        return
    if args.operation == "stop-watch":
        active = watching()
        with writer_lock():
            (RUN / "stop").touch()
        for _ in range(60):
            if not watching():
                break
            time.sleep(0.1)
        if watching():
            raise RuntimeError("Unraid reconciler did not stop")
        print(json.dumps({"changed": active}))
        return
    if args.operation == "check":
        result = reconcile(policy, "check")
        result["watch_running"] = watching()
    else:
        with writer_lock():
            if args.operation == "remove":
                (RUN / "stop").touch()
                result = reconcile(operation="remove", backend=args.backend)
            else:
                if args.operation == "start":
                    (RUN / "stop").unlink(missing_ok=True)
                result = reconcile(policy)
                if args.operation == "start" and not watching():
                    subprocess.Popen(
                        [sys.executable, str(Path(__file__).resolve()), "watch", "--config", args.config],
                        start_new_session=True,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    # Wait briefly for the lock: repeated starts are idempotent.
                    for _ in range(50):
                        if watching():
                            break
                        time.sleep(0.02)
                    if not watching():
                        raise RuntimeError("Unraid reconciler did not start")
                    result["changed"] = True
    print(json.dumps(result))
    if args.operation == "check" and not result["compliant"]:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as failure:
        print(json.dumps({"failed": True, "message": str(failure)}), file=sys.stderr)
        raise SystemExit(1) from failure
