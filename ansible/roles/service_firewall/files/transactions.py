# Profile globals are bound by the two explicit loaders, never inferred.
# ruff: noqa: F821
"""Owned iptables transaction/parser primitives shared by the two explicit profiles.

Each profile supplies its own marker, chains, jump prefix, terminal and lock root.
No endpoint catalog, caller model, policy persistence or application lifecycle lives here.
"""

from __future__ import annotations

import fcntl
import ipaddress
import json
import shlex
import subprocess
from contextlib import contextmanager
from pathlib import Path

CHAINS: dict
JUMP_PREFIX: list
TERMINAL: list
RUN: Path


def execute(argv, data=None):
    """Run only explicit ip/ip[6]tables commands without a shell."""
    result = subprocess.run(argv, input=data, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f"{argv[0]} failed ({result.returncode}): {result.stderr.strip()}")
    return result.stdout


def local_addresses(run):
    """Include all current host addresses, including secondary LAN and Tailscale."""
    data = json.loads(run(["ip", "-j", "address", "show"]))
    return {str(ipaddress.ip_address(info["local"])) for interface in data for info in interface.get("addr_info", [])}


def read_table(output):
    """Parse iptables-save without modifying or persisting the host ruleset."""
    chains = {}
    for line in output.splitlines():
        if line.startswith(":"):
            chains[line.split()[0][1:]] = []
        elif line.startswith("-A "):
            tokens = shlex.split(line)
            chains[tokens[1]].append(tokens[2:])
    return chains


def owned_jump(rule, target):
    return rule == JUMP_PREFIX + [target]


def normalized(rule):
    """iptables-save canonicalizes host masks and may add the TCP module."""
    result = []
    index = 0
    while index < len(rule):
        token = rule[index]
        if rule[index : index + 2] == ["-m", "tcp"]:
            index += 2
            continue
        if token in {"-s", "--ctorigdst"} and index + 1 < len(rule):
            result += [token, str(ipaddress.ip_interface(rule[index + 1]).ip)]
            index += 2
            continue
        result.append(token)
        index += 1
    # Match extensions may serialize their options in a canonical order.
    # Every option in these owned rules is a conjunctive flag/value pair.
    return sorted(zip(result[::2], result[1::2], strict=True))


def table_patch(table, current, desired=None):
    """Build a --noflush transaction touching only our chains and exact jumps.

    Unmarked names/references are a collision, not permission to overwrite.
    Changes are atomic within each table; both families are dry-tested before
    either is applied. No cross-family atomicity is claimed.
    """
    managed = CHAINS[table]
    for chain in managed:
        if chain in current and (not current[chain] or current[chain][-1] != TERMINAL):
            raise ValueError(f"refusing unowned chain collision: {chain}")
        for parent, rules in current.items():
            for rule in rules:
                references = any(rule[index : index + 2] in (["-j", chain], ["-g", chain]) for index in range(len(rule) - 1))
                if references and (parent not in managed[chain] or not owned_jump(rule, chain)):
                    raise ValueError(f"refusing unowned reference to {chain} in {parent}")
    lines = [f"*{table}"]
    for chain, parents in managed.items():
        wanted = desired[chain] if desired is not None else None
        active_parents = [parent for parent in parents if parent in current]
        matches = chain in current and [normalized(rule) for rule in current[chain]] == [normalized(rule) for rule in wanted or []]
        matches = matches and all(
            current[parent] and owned_jump(current[parent][0], chain) and sum(owned_jump(rule, chain) for rule in current[parent]) == 1
            for parent in active_parents
        )
        if wanted is not None and matches:
            continue
        for parent in parents:
            for rule in current.get(parent, []):
                if owned_jump(rule, chain):
                    lines.append(shlex.join(["-D", parent] + rule))
        if wanted is None:
            if chain in current:
                lines += [f"-F {chain}", f"-X {chain}"]
            continue
        if chain not in current:
            lines.append(f"-N {chain}")
        lines.append(f"-F {chain}")
        lines += [shlex.join(["-A", chain] + rule) for rule in wanted]
        lines += [shlex.join(["-I", parent, "1"] + JUMP_PREFIX + [chain]) for parent in active_parents]
    return "\n".join(lines + ["COMMIT", ""]) if len(lines) > 1 else ""


@contextmanager
def writer_lock():
    RUN.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (RUN / "writer.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield
