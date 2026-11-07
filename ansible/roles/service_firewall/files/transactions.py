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
import sys
import time
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from pathlib import Path

CHAINS: dict
JUMP_PREFIX: list
TERMINAL: list
RUN: Path


def execute(argv, data=None):
    """Run explicit firewall/platform commands without a shell."""
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


def read_os_release():
    try:
        content = Path("/etc/os-release").read_text()
    except FileNotFoundError:
        return {}  # Retain the explicit Unraid marker/flash boundary.
    return {
        key: value.strip().strip("\"'")
        for line in content.splitlines()
        if line and not line.startswith("#") and "=" in line
        for key, _, value in [line.partition("=")]
    }


def supported_platform(profile, release, unraid=False):
    """Keep profile-specific Ubuntu/Unraid boundaries and explicit RPM releases."""
    distro, version = release.get("ID", ""), release.get("VERSION_ID", "")
    return profile in {"mgt", "workers"} and (
        (unraid and profile == "workers")
        or (distro == "debian" and version in {"12", "13"})
        or (distro == "ubuntu" and version == ("26.04" if profile == "mgt" else "24.04"))
        or (distro == "fedora" and version in {"43", "44", "45"})
        or (distro == "rocky" and version.split(".")[0] == "10")
    )


def rpm_firewall_preflight(run=execute, *, wait_for_daemon=False):
    """Read-only coexistence checks for explicit Debian and RPM platforms.

    Native firewalld owns its own table. Direct rules can make it flush shared
    xtables tables on reload; refuse that configuration instead of changing it.
    Native firewalld ACCEPT/DROP policy remains an independent access boundary.
    """
    release = read_os_release()
    if release.get("ID") not in {"debian", "fedora", "rocky"}:
        return
    if not supported_platform("mgt", release) or Path("/run/ostree-booted").exists():
        raise ValueError(
            "firewall compatibility requires conventional Debian 12/13, Fedora 43-45 or Rocky 10; Atomic/OSTree is unsupported"
        )
    if sys.version_info < (3, 10) or not Path("/run/systemd/system").is_dir():
        raise ValueError("Debian/RPM firewall protection requires Python 3.10+ and a conventional systemd host")
    for tool in ["iptables", "ip6tables", "iptables-save", "ip6tables-save", "iptables-restore", "ip6tables-restore"]:
        if "(nf_tables)" not in run([tool, "--version"]):
            raise ValueError(f"{tool}: install matching distribution nf_tables tools; backend switching is forbidden")
    native = json.loads(run(["nft", "--json", "list", "ruleset"]))
    if any("flowtable" in entry for entry in native.get("nftables", [])):
        raise ValueError("flowtables can bypass protection; review offload policy before activating this profile")
    if release.get("ID") == "debian":
        load = run(["systemctl", "show", "firewalld.service", "--property=LoadState", "--value"]).strip()
        if load == "not-found":
            if any(
                entry.get("table", {}).get("family") == "inet" and entry["table"].get("name") == "firewalld"
                for entry in native.get("nftables", [])
            ):
                raise ValueError("firewalld rules exist without a verifiable service; resolve their ownership before activation")
            return
    version = run(["firewall-offline-cmd", "--version"]).strip().split(".")
    if not all(part.isdecimal() for part in version) or tuple(map(int, version)) < (2, 0, 0):
        raise ValueError("firewalld 2.0+ is required: older releases flush shared compatibility tables even without Direct rules")
    settings = {}
    for directory in [Path("/usr/lib/firewalld"), Path("/etc/firewalld")]:
        config = directory / "firewalld.conf"
        if config.exists():
            settings.update(
                dict(
                    [value.strip() for value in line.split("=", 1)]
                    for line in config.read_text().splitlines()
                    if line.strip() and not line.lstrip().startswith("#") and "=" in line
                )
            )
        direct = directory / "direct.xml"
        if direct.exists():
            try:
                root = ET.parse(direct).getroot()
            except ET.ParseError as error:
                raise ValueError("cannot verify firewalld Direct configuration") from error
            if root.tag != "direct" or len(root):
                raise ValueError("firewalld Direct configuration can flush shared tables; resolve it explicitly before activation")
    if settings.get("FirewallBackend", "nftables") != "nftables":
        raise ValueError("firewalld must retain its native nftables backend; migrate its policy explicitly, never disable it")
    if settings.get("NftablesFlowtable", "off") != "off":
        raise ValueError("configured firewalld flowtable offload can bypass protection after reload; review that policy explicitly")
    state = run(["systemctl", "show", "firewalld.service", "--property=ActiveState", "--value"]).strip()
    if state == "inactive":
        return
    if state != "active":
        raise ValueError("firewalld state is not stable; inspect the daemon before changing protection")
    # A package upgrade does not replace a still-running daemon. Its reload
    # implementation, rather than the installed executable, controls shared tables.
    # Some packaged firewalld units use Type=simple: "active" precedes D-Bus
    # registration and INIT completion. Only live apply may wait for readiness;
    # inspection/install preflight still rejects an unready daemon immediately.
    deadline = time.monotonic() + 30
    while True:
        runtime = {}
        try:
            for property_ in ["version", "state"]:
                value = shlex.split(
                    run(
                        [
                            "busctl",
                            "--auto-start=no",
                            "--timeout=2s",
                            "get-property",
                            "org.fedoraproject.FirewallD1",
                            "/org/fedoraproject/FirewallD1",
                            "org.fedoraproject.FirewallD1",
                            property_,
                        ]
                    )
                )
                if len(value) != 2 or value[0] != "s":
                    raise ValueError("cannot verify the running firewalld version/state; inspect the daemon before changing protection")
                runtime[property_] = value[1]
        except RuntimeError:
            if not wait_for_daemon or time.monotonic() >= deadline:
                raise
        else:
            runtime_version = runtime["version"].split(".")
            if not all(part.isdecimal() for part in runtime_version) or tuple(map(int, runtime_version)) < (2, 0, 0):
                raise ValueError(
                    "the running firewalld daemon must be 2.0+; an installed package upgrade alone does not establish reload safety"
                )
            if runtime["state"] == "RUNNING":
                break
            if not wait_for_daemon or runtime["state"] != "INIT" or time.monotonic() >= deadline:
                raise ValueError("firewalld has not reached RUNNING state; inspect initialization or failure before changing protection")
        time.sleep(1)
    # Initialization can create native tables after the first snapshot.
    native = json.loads(run(["nft", "--json", "list", "ruleset"]))
    if any("flowtable" in entry for entry in native.get("nftables", [])):
        raise ValueError("flowtables can bypass protection; review offload policy before activating this profile")
    backend = shlex.split(
        run(
            [
                "busctl",
                "--auto-start=no",
                "--timeout=2s",
                "get-property",
                "org.fedoraproject.FirewallD1",
                "/org/fedoraproject/FirewallD1/config",
                "org.fedoraproject.FirewallD1.config",
                "FirewallBackend",
            ]
        )
    )
    if backend != ["s", "nftables"] or not any(
        entry.get("table", {}).get("family") == "inet" and entry["table"].get("name") == "firewalld" for entry in native.get("nftables", [])
    ):
        raise ValueError("active firewalld must have its native nftables table and backend; no host policy is switched automatically")
    for scope in [[], ["--permanent"]]:
        for query in ["--get-all-chains", "--get-all-rules", "--get-all-passthroughs"]:
            if run(["firewall-cmd", *scope, "--direct", query]).strip():
                raise ValueError("firewalld Direct rules can flush shared tables on reload; review their owner before activation")


def compatibility_table(tool, table, native, required, operation, run):
    """Read mapped tables without making xtables initialize absent skeletons."""
    family = "ip6" if tool.startswith("ip6") else "ip"
    present = any(
        entry.get("table", {}).get("family") == family and entry["table"].get("name") == table for entry in native.get("nftables", [])
    )
    if not present:
        return None if operation in {"check", "remove"} else {parent: [] for parent in required}
    parents = {
        entry["chain"]["name"]: entry["chain"]
        for entry in native.get("nftables", [])
        if entry.get("chain", {}).get("family") == family and entry["chain"].get("table") == table
    }
    saved = run([f"{tool}-save", "-t", table])
    state = read_table(saved)
    policies = {line.split()[0][1:]: line.split()[1] for line in saved.splitlines() if line.startswith(":")}
    for parent in required:
        if policies.get(parent) not in {"ACCEPT", "DROP"} or (parent in parents and parents[parent].get("hook") != parent.lower()):
            raise ValueError(f"{tool}: incompatible {table} built-in chain {parent}; refusing shared-policy repair")
    return state


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
