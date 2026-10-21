#!/usr/bin/env python3
"""mgt-only endpoint guards; standard library, no secret or inventory lookups.

The controller bundles service_firewall transaction primitives into this file.
The mgt identity and policy model remain independent from the workers profile.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import pwd
import re
import subprocess
import sys
import types
from pathlib import Path


def engine():
    module = types.ModuleType("mgt_owned_transactions")
    source = globals().get("TRANSACTION_SOURCE") or Path(__file__).resolve().with_name("transactions.py").read_text()
    exec(compile(source, "service_firewall.transactions", "exec"), module.__dict__)
    module.MARK = "skynet-mgt-endpoints"
    module.CHAINS = {
        "mangle": {"SKY-MGT-PRE": ["PREROUTING"], "SKY-MGT-OUT": ["OUTPUT"]},
        "filter": {"SKY-MGT-IN": ["INPUT"], "SKY-MGT-FWD": ["FORWARD", "DOCKER-USER"], "SKY-MGT-LOCAL": ["OUTPUT"]},
    }
    module.JUMP_PREFIX = ["-m", "comment", "--comment", module.MARK, "-j"]
    module.TERMINAL = module.JUMP_PREFIX + ["RETURN"]
    module.RUN = Path("/run/skynet-mgt-firewall")
    normalize = module.normalized

    def normalized(rule):
        rule = list(rule)
        if "--mac-source" in rule:
            index = rule.index("--mac-source") + 1
            rule[index] = rule[index].lower()
        return normalize(rule)

    module.normalized = normalized
    return module


OWNED = engine()
NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}\Z")
SYSTEMD = Path("/etc/systemd/system")
DROPIN_MARKER = "# Managed by skynet mgt endpoints\n"

# Stream only this read-only probe into the dedicated account. The installed
# policy and its parent directory remain root-only; no helper file is exposed.
ROOTLESS_REPLACEMENT_PROBE = r"""
import json, re, subprocess, sys, time

deadline = time.monotonic() + 15

def read(argv):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("retired caller replacement probe exceeded its invocation budget")
    return subprocess.run(argv, text=True, capture_output=True, check=True, timeout=remaining).stdout.strip()

name = sys.argv[1]
if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}", name):
    raise ValueError("invalid replacement name")
if read(["/usr/bin/systemctl", "--user", "is-active", name + ".service"]) != "active":
    raise ValueError("retired caller replacement unit is not active")
podman = ["/usr/bin/podman", "--remote=false"]
if read(podman + ["info", "--format", "{{.Host.Security.Rootless}}"]) != "true":
    raise ValueError("retired caller replacement store is not rootless")
ids = read(podman + ["ps", "--no-trunc", "--filter", "name=^" + re.escape(name) + "$", "--format", "{{.ID}}"]).split()
if len(ids) != 1 or not re.fullmatch(r"[0-9a-f]{64}", ids[0]):
    raise ValueError("retired caller replacement container is missing or ambiguous")
template = '{"id":{{json .ID}},"name":{{json .Name}},"running":{{json .State.Running}},"pid":{{json .State.Pid}}}'
record = json.loads(read(podman + ["container", "inspect", "--format", template, ids[0]]))
print(json.dumps({"ids": ids, "container": record}))
"""


def execute(argv, data=None):
    """Bound local operations; never leave startup waiting on a daemon/socket."""
    try:
        result = subprocess.run(argv, input=data, text=True, capture_output=True, check=False, timeout=15)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"{argv[0]} timed out after 15 seconds") from error
    if result.returncode:
        raise RuntimeError(f"{argv[0]} failed ({result.returncode}): {result.stderr.strip()}")
    return result.stdout


OWNED.execute = execute


def managed_dropins():
    paths = sorted(SYSTEMD.glob("*.service.d/45-skynet-mgt-firewall.conf"))
    for path in paths:
        if path.is_symlink() or path.parent.is_symlink() or not path.read_text().startswith(DROPIN_MARKER):
            raise ValueError(f"refusing unowned persistence collision: {path}")
    return paths


def guard_units(policy, account_lookup):
    """Require the root guard in only dedicated caller/provider managers.

    Keep earlier owned manager dependencies until full policy removal; a stage
    withdraws ports without creating a second systemd ownership mechanism.
    """
    units = {path.parent.name.removesuffix(".d") for path in managed_dropins() if path.parent.name != "docker.service.d"}
    required = {name for endpoint in policy["endpoints"] for name in endpoint["callers"]}
    accounts = {
        binding["account"]
        for name in required
        for binding in policy["callers"][name]
        if binding.get("kind") in {"local", "service"} and binding.get("account", "").startswith("podman-")
    }
    for name in required:
        for binding in policy["callers"][name]:
            if binding.get("kind") == "service" and binding.get("runtime") == "podman" and binding.get("mode") == "rootful":
                units.add(binding["selector"] + ".service")
    for endpoint in policy["endpoints"]:
        service = endpoint.get("service")
        principal = policy.get("principals", {}).get(service, {})
        account = principal.get("future_account")
        if isinstance(account, str) and account.startswith("podman-"):
            accounts.add(account)
        elif principal.get("future_runtime") == "podman":
            if not isinstance(service, str) or not NAME.fullmatch(service):
                raise ValueError("rootful guard requires an exact declared service name")
            units.add(f"{service}.service")
    for account in accounts:
        try:
            uid = account_lookup(account).pw_uid
        except KeyError as error:
            raise ValueError(f"prepare the declared account before activating its firewall: {account}") from error
        if uid <= 0:
            raise ValueError("dedicated rootless managers must have non-root UIDs")
        units.add(f"user@{uid}.service")
    return sorted(units)


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def exact_address(value):
    if not isinstance(value, str) or "/" in value or "%" in value:
        raise ValueError("identity addresses must be bare IP addresses")
    address = ipaddress.ip_address(value)
    if address.is_unspecified or address.is_multicast or address.is_loopback:
        raise ValueError("identity addresses must be non-loopback unicast")
    return str(address)


def validate_policy(policy, require_verified=True):
    """Validate the complete active contract before any lock, file or rule writes."""
    if type(require_verified) is not bool or not isinstance(policy, dict):
        raise ValueError("policy and verification mode are invalid")
    if not integer(policy.get("schema")) or policy["schema"] != 1 or policy.get("backend") != "nf_tables":
        raise ValueError("only schema 1 and the existing mgt nf_tables backend are supported")
    exact_address(policy.get("inventory_address"))
    if type(policy.get("inputs_verified")) is not bool or (
        require_verified and not policy["inputs_verified"] and policy.get("lifecycle") is not True
    ):
        raise ValueError("inputs_verified must be boolean true after observing all active callers")
    endpoints = policy.get("endpoints")
    if not isinstance(endpoints, list) or (require_verified and not endpoints and policy.get("lifecycle") is not True):
        raise ValueError("at least one explicitly active endpoint is required for installation")
    bindings = policy.get("callers")
    if not isinstance(bindings, dict):
        raise ValueError("callers must be a mapping")
    ports = set()
    required = set()
    for endpoint in endpoints:
        port = endpoint.get("port")
        if not integer(port) or not 1 <= port <= 65535 or port in ports:
            raise ValueError("active endpoint ports must be unique TCP ports")
        ports.add(port)
        names = endpoint.get("callers")
        if not isinstance(names, list) or not names or any(not isinstance(name, str) or not name for name in names):
            raise ValueError("each endpoint needs its declared callers")
        required.update(names)
    for name in required:
        values = bindings.get(name)
        if not isinstance(values, list) or not values:
            if require_verified:
                raise ValueError(f"missing active caller identities: {name}")
            continue
        for binding in values:
            if not isinstance(binding, dict):
                raise ValueError(f"{name}: identity must be a mapping")
            kind = binding.get("kind")
            if kind not in {"local", "container", "remote", "disabled", "elsewhere", "service"}:
                raise ValueError(f"{name}: unsupported caller identity")
            if kind == "service":
                if policy.get("lifecycle") is not True:
                    raise ValueError("automatic identities require a lifecycle-managed policy")
                runtime, mode = binding.get("runtime"), binding.get("mode")
                if binding.get("phase") != runtime or runtime not in {"docker", "podman"}:
                    raise ValueError("automatic identity runtime differs")
                if runtime == "podman" and mode == "rootless":
                    account = binding.get("account", "")
                    if not isinstance(account, str) or not account.startswith("podman-") or not NAME.fullmatch(account):
                        raise ValueError("automatic rootless identities require a dedicated account")
                elif runtime == "podman" and mode != "rootful":
                    raise ValueError("unsupported automatic execution mode")
                if runtime == "docker" and ("mode" in binding or "account" in binding):
                    raise ValueError("Docker caller cannot use a Podman account/mode")
                if runtime == "podman" and mode == "rootful" and "account" in binding:
                    raise ValueError("rootful caller cannot use a rootless account")
                if "compose" in binding and "selector" in binding:
                    raise ValueError("choose one exact Compose or container selector")
                if "compose" in binding:
                    compose = binding["compose"]
                    if (
                        runtime != "docker"
                        or not isinstance(compose, dict)
                        or set(compose) != {"project", "service"}
                        or any(not isinstance(v, str) or not NAME.fullmatch(v) for v in compose.values())
                    ):
                        raise ValueError("automatic Compose identity requires exact project and service")
                elif not isinstance(binding.get("selector"), str) or not NAME.fullmatch(binding["selector"]):
                    raise ValueError("automatic identity requires an exact runtime selector")
                if set(binding) - {"kind", "runtime", "phase", "mode", "account", "selector", "compose"}:
                    raise ValueError("unsupported automatic identity fields")
                continue
            for flag in ["verified", "restart_verified"]:
                if type(binding.get(flag)) is not bool or (require_verified and not binding[flag]):
                    raise ValueError(f"{name}: {flag} must be boolean true")
            if kind == "disabled":
                if name not in {"recovery", "controller"}:
                    raise ValueError("only explicit operator paths can be disabled")
                continue
            if binding.get("phase") not in {"docker", "podman", "native"}:
                raise ValueError(f"{name}: phase must distinguish docker, podman or native callers")
            if kind == "elsewhere":
                principal = policy.get("principals", {}).get(name, {})
                hosts = principal.get("inventory_hosts", [])
                hosts = hosts if isinstance(hosts, list) else [hosts]
                if (
                    binding["phase"] != "docker"
                    or principal.get("future_runtime") != "docker"
                    or binding.get("inventory_host") not in hosts
                    or policy["inventory_host"] in hosts
                    or any(
                        endpoint.get("purpose") != "declared PostgreSQL applications and recovery"
                        for endpoint in endpoints
                        if name in endpoint["callers"]
                    )
                ):
                    raise ValueError("elsewhere is only for declared worker database callers verified to use worker-local HAProxy")
                if type(binding.get("route_verified")) is not bool or (require_verified and not binding["route_verified"]):
                    raise ValueError("route_verified must confirm the worker-local database path")
            elif kind == "local":
                account, uid = binding.get("account"), binding.get("uid")
                if not isinstance(account, str) or not NAME.fullmatch(account) or not integer(uid) or uid < 0:
                    raise ValueError(f"{name}: exact account and numeric UID are required")
                cgroup = binding.get("cgroup")
                if cgroup is not None and (
                    not isinstance(cgroup, str)
                    or not cgroup.endswith(".slice")
                    or any(not NAME.fullmatch(part) for part in cgroup.split("/"))
                ):
                    raise ValueError(f"{name}: cgroup must be an explicit persistent slice path")
                if not cgroup and (uid == 0 or not account.startswith("podman-")):
                    raise ValueError(f"{name}: shared/native/root accounts require an exclusive persistent cgroup slice")
            elif kind == "container":
                runtime = binding.get("runtime")
                selector = binding.get("selector")
                compose = binding.get("compose")
                if runtime not in {"docker", "podman"} or binding["phase"] != runtime:
                    raise ValueError(f"{name}: local runtime and matching phase are required")
                if "compose" in binding:
                    if (
                        runtime != "docker"
                        or "selector" in binding
                        or not isinstance(compose, dict)
                        or set(compose) != {"project", "service"}
                        or any(not isinstance(value, str) or not NAME.fullmatch(value) for value in compose.values())
                    ):
                        raise ValueError(f"{name}: Compose needs exact project AND service labels, exclusively of selector")
                elif not isinstance(selector, str) or not NAME.fullmatch(selector):
                    raise ValueError(f"{name}: exact local Swarm service/rootful Podman name is required")
                if "retirement" in binding:
                    retirement = binding["retirement"]
                    if (
                        not compose
                        or not isinstance(retirement, dict)
                        or set(retirement) not in ({"container_id"}, {"container_id", "removal_verified"})
                        or not isinstance(retirement.get("container_id"), str)
                        or not re.fullmatch(r"[0-9a-f]{64}", retirement["container_id"])
                        or (
                            "removal_verified" in retirement
                            and (
                                type(retirement["removal_verified"]) is not bool
                                or (require_verified and retirement["removal_verified"] is not True)
                            )
                        )
                    ):
                        raise ValueError(f"{name}: Compose retirement requires one recorded full container ID")
                path = binding.get("path", "bridge")
                if path not in {"bridge", "local"}:
                    raise ValueError(f"{name}: container path must be bridge or local")
                if path == "local":
                    if not integer(binding.get("socket_uid")) or binding["socket_uid"] < 0:
                        raise ValueError(f"{name}: host-network caller needs its observed socket UID")
                    flag = "socket_hook_verified"
                else:
                    flag = "physdev_verified"
                if type(binding.get(flag)) is not bool or (require_verified and not binding[flag]):
                    raise ValueError(f"{name}: {flag} must confirm the caller at the selected hooks")
            elif kind == "remote":
                # Remote app SNAT cannot distinguish applications. Host identity
                # is permitted only for explicitly authorized operator paths.
                if name not in {"controller", "recovery"} or binding["phase"] != "native":
                    raise ValueError("shared remote host addresses cannot identify application callers")
                exact_address(binding.get("address"))
                interface = binding.get("interface")
                if not isinstance(interface, str) or not NAME.fullmatch(interface) or len(interface) > 15 or interface == "lo":
                    raise ValueError("remote operator paths require an exact ingress interface")
                if not isinstance(binding.get("inventory_host"), str) or not binding["inventory_host"]:
                    raise ValueError("remote operator identity must name its inventory host")
                if type(binding.get("exclusive_verified")) is not bool or (require_verified and not binding["exclusive_verified"]):
                    raise ValueError(
                        "exclusive_verified must confirm that the remote operator identity is not shared with application SNAT"
                    )
                if "observed_address" in binding and (
                    type(binding.get("address_override_verified")) is not bool
                    or (require_verified and not binding["address_override_verified"])
                ):
                    raise ValueError("address_override_verified must confirm an explicitly observed alternate operator source")
    return policy


class MissingRuntimeCaller(ValueError):
    """An exact selector has no running container; command failures are separate."""


class MissingSwarmCaller(MissingRuntimeCaller):
    """An exact Docker selector needs guarded retirement resolution."""


def removed_service_caller(policy, name):
    """A runtime adapter proved logical-client removal under the policy lock.

    Its retained bindings remain available for rollback. Only a missing exact
    selector is tolerated; replacement identities and inspection errors still
    take the normal path. Absence never creates an allow rule.
    """
    return any(
        value.get("runtime", {}).get("service") == name and (value.get("removing") or value.get("removed"))
        for value in policy.get("managed_services", {}).values()
    )


def retired_swarm_caller(policy, name, binding, run, account_lookup):
    """Keep a rollback binding without allowing an absent, retired writer.

    Retirement requires a stable zero-replica Swarm service, or the exact recorded
    exited Compose container with automatic restart disabled, and an independently
    verified, currently running replacement in the declared dedicated store.
    No runtime identity or policy confirmation is synthesized here.
    """
    principal = policy.get("principals", {}).get(name, {})
    hosts = principal.get("inventory_hosts", [])
    hosts = hosts if isinstance(hosts, list) else [hosts]
    account = principal.get("future_account")
    compose = binding.get("compose")
    retirement = binding.get("retirement")
    replacements = [
        value
        for value in policy["callers"][name]
        if value.get("kind") == "local"
        and value.get("phase") == "podman"
        and value.get("account") == account
        and value.get("verified") is True
        and value.get("restart_verified") is True
    ]
    if (
        binding.get("runtime") != "docker"
        or binding.get("phase") != "docker"
        or (compose and not retirement)
        or principal.get("future_runtime") != "podman"
        or policy.get("inventory_host") not in hosts
        or not isinstance(account, str)
        or not account.startswith("podman-")
        or not NAME.fullmatch(account)
        or not NAME.fullmatch(name)
        or len(replacements) != 1
    ):
        return False
    replacement = replacements[0]
    user = account_lookup(account)
    if not integer(replacement.get("uid")) or replacement["uid"] <= 0 or user.pw_uid != replacement["uid"]:
        raise ValueError("retired caller replacement account UID differs")
    docker = ["docker", "--host", "unix:///var/run/docker.sock"]
    selector = binding.get("selector")
    filters = (
        [
            "--filter",
            f"label=com.docker.compose.project={compose['project']}",
            "--filter",
            f"label=com.docker.compose.service={compose['service']}",
        ]
        if compose
        else ["--filter", f"label=com.docker.swarm.service.name={selector}"]
    )
    service_template = '{"name":{{json .Spec.Name}},"mode":{{json .Spec.Mode}},"version":{{json .Version.Index}}}'

    def service():
        if compose:
            expected = retirement["container_id"]
            ids = run(docker + ["ps", "-a", "--no-trunc", *filters, "--format", "{{.ID}}"]).split()
            if retirement.get("removal_verified") is True:
                recorded = run(docker + ["ps", "-a", "--no-trunc", "--filter", f"id={expected}", "--format", "{{.ID}}"]).split()
                if ids or recorded:
                    raise ValueError("removed Compose caller or its exact selector is present; repeat retirement verification")
                # Only the nested observation returns absence metadata. The
                # outer running-replacement and continuity checks still run;
                # this never produces a Docker identity or an allow rule.
                return {"container_id": expected, "compose": compose, "removed": True}
            if ids != [expected]:
                raise ValueError("retired Compose caller is missing, replaced or ambiguous")
            template = (
                '{"id":{{json .Id}},"name":{{json .Name}},'
                '"project":{{json (index .Config.Labels "com.docker.compose.project")}},'
                '"service":{{json (index .Config.Labels "com.docker.compose.service")}},'
                '"running":{{json .State.Running}},"restarting":{{json .State.Restarting}},'
                '"status":{{json .State.Status}},"pid":{{json .State.Pid}},"restart":{{json .HostConfig.RestartPolicy}}}'
            )
            record = json.loads(run(docker + ["container", "inspect", "--format", template, expected]))
            if (
                record.get("id") != expected
                or record.get("project") != compose["project"]
                or record.get("service") != compose["service"]
                or record.get("running") is not False
                or record.get("restarting") is not False
                or record.get("status") != "exited"
                or not integer(record.get("pid"))
                or record["pid"] != 0
                or record.get("restart") != {"Name": "no", "MaximumRetryCount": 0}
                or not integer(record["restart"]["MaximumRetryCount"])
            ):
                raise ValueError("retired Compose caller requires its exact exited container with restart disabled")
            return record
        record = json.loads(run(docker + ["service", "inspect", "--format", service_template, selector]))
        mode = record.get("mode", {})
        replicas = mode.get("Replicated", {}).get("Replicas")
        if (
            record.get("name") != selector
            or set(mode) != {"Replicated"}
            or not integer(replicas)
            or replicas != 0
            or not integer(record.get("version"))
        ):
            raise ValueError("retired caller requires an exact zero-replica Swarm service")
        return record

    before = service()
    prefix = [
        "runuser",
        "-u",
        account,
        "--",
        "env",
        f"HOME={user.pw_dir}",
        f"XDG_RUNTIME_DIR=/run/user/{user.pw_uid}",
        f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{user.pw_uid}/bus",
        "/bin/sh",
        "-c",
        'cd "$HOME" || exit; exec "$@"',
        "skynet-mgt-retired",
    ]
    observed = json.loads(run(prefix + ["/usr/bin/python3", "-c", ROOTLESS_REPLACEMENT_PROBE, name]))
    if not isinstance(observed, dict) or set(observed) != {"ids", "container"} or not isinstance(observed["container"], dict):
        raise ValueError("retired caller replacement probe returned incomplete metadata")
    podman = prefix + ["/usr/bin/podman", "--remote=false"]
    ids = observed["ids"]
    if not isinstance(ids, list) or len(ids) != 1 or not isinstance(ids[0], str) or not re.fullmatch(r"[0-9a-f]{64}", ids[0]):
        raise ValueError("retired caller replacement container is missing or ambiguous")
    template = '{"id":{{json .ID}},"name":{{json .Name}},"running":{{json .State.Running}},"pid":{{json .State.Pid}}}'

    def container(record):
        if (
            record.get("id") != ids[0]
            or record.get("name") != name
            or record.get("running") is not True
            or not integer(record.get("pid"))
            or record["pid"] <= 0
        ):
            raise ValueError("retired caller replacement runtime identity differs")
        return record

    current = container(observed["container"])
    pid = current["pid"]

    def process():
        stat = run(["cat", f"/proc/{pid}/stat"])
        fields = stat.rsplit(")", 1)[-1].split()
        if len(fields) <= 19 or not fields[19].isdecimal():
            raise ValueError("retired caller replacement process start time is incomplete")
        birth = fields[19]
        namespace = run(["readlink", f"/proc/{pid}/ns/net"]).strip()
        cgroups = run(["cat", f"/proc/{pid}/cgroup"]).splitlines()
        paths = [line[3:] for line in cgroups if line.startswith("0::")]
        expected = f"/user.slice/user-{user.pw_uid}.slice/user@{user.pw_uid}.service/"
        if len(paths) != 1 or not paths[0].startswith(expected) or not re.fullmatch(r"net:\[\d+\]", namespace):
            raise ValueError("retired caller replacement process is outside its dedicated manager")
        return birth, namespace, paths[0]

    identity = process()
    if (
        service() != before
        or container(json.loads(run(podman + ["container", "inspect", "--format", template, ids[0]]))) != current
        or process() != identity
    ):
        raise ValueError("retired caller changed during identity resolution; retry")
    if run(docker + ["ps", *filters, "--format", "{{.ID}}"]).split():
        raise ValueError("retired caller acquired a running Docker task; retry")
    return True


def container_identities(binding, run):
    """Resolve stable selectors to exact current bridge peers, IPs and MACs.

    Inspection projects only IDs/PIDs; never application environments/secrets.
    No entire bridge or subnet is authorized. An unrecognizable path fails shut.
    """
    runtime = binding["runtime"]
    compose = binding.get("compose")
    selector = f"compose:{compose['project']}/{compose['service']}" if compose else binding["selector"]
    command = ["docker", "--host", "unix:///var/run/docker.sock"] if runtime == "docker" else ["podman", "--remote=false"]
    if runtime == "docker":
        if run(["systemctl", "is-active", "docker.service"]).strip() != "active":
            raise ValueError("Docker is not active; do not activate its socket from firewall reconciliation")
        filters = (
            [
                "--filter",
                f"label=com.docker.compose.project={compose['project']}",
                "--filter",
                f"label=com.docker.compose.service={compose['service']}",
            ]
            if compose
            else ["--filter", f"label=com.docker.swarm.service.name={selector}"]
        )
        ids = sorted(set(run(command + ["ps", *filters, "--format", "{{.ID}}"]).split()))
    elif binding.get("kind") == "service":
        ids = sorted(set(run(command + ["ps", "--filter", "name=^" + re.escape(selector) + "$", "--format", "{{.ID}}"]).split()))
    else:
        ids = [selector]
    if not ids:
        error = MissingSwarmCaller if runtime == "docker" and (not compose or binding.get("retirement")) else MissingRuntimeCaller
        raise error(f"no local running caller for {runtime}:{selector}")
    host_links = {link["ifindex"]: link for link in json.loads(run(["ip", "-j", "link", "show"]))}
    identities = []
    for identity in ids:
        if not NAME.fullmatch(identity):
            raise ValueError("runtime returned an invalid container identity")
        pid_text = run(command + ["inspect", "--format", "{{.State.Pid}}", identity]).strip()
        if not pid_text.isdecimal() or int(pid_text) <= 0:
            raise ValueError(f"{runtime}:{selector}: caller is not running")
        if binding.get("path") == "local":
            namespace = run(["readlink", f"/proc/{pid_text}/ns/net"]).strip()
            if namespace != run(["readlink", "/proc/1/ns/net"]).strip():
                raise ValueError("local runtime binding requires the host network namespace")
            cgroups = run(["cat", f"/proc/{pid_text}/cgroup"]).splitlines()
            paths = [line[3:].removeprefix("/") for line in cgroups if line.startswith("0::")]
            if len(paths) != 1 or not paths[0] or any(not NAME.fullmatch(part) for part in paths[0].split("/")):
                raise ValueError("host-network caller requires an exclusive cgroup v2 path")
            identities.append({"kind": "local", "uid": binding["socket_uid"], "cgroup": paths[0]})
            if run(command + ["inspect", "--format", "{{.State.Pid}}", identity]).strip() != pid_text:
                raise ValueError("caller restarted during identity resolution; retry")
            continue
        links = json.loads(run(["nsenter", "--target", pid_text, "--net", "ip", "-j", "address", "show"]))
        for link in links:
            peer = host_links.get(link.get("link_index"))
            if not peer or not peer.get("master"):
                continue
            bridge = peer["master"]
            if isinstance(bridge, int):
                bridge = host_links[bridge]["ifname"]
            veth, mac = peer["ifname"], link.get("address", "")
            if any(not NAME.fullmatch(iface) or len(iface) > 15 for iface in [bridge, veth]) or not re.fullmatch(
                r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", mac
            ):
                raise ValueError("caller bridge identity is invalid")
            for address in link.get("addr_info", []):
                identities.append(
                    {"kind": "container", "address": exact_address(address["local"]), "interface": bridge, "veth": veth, "mac": mac.lower()}
                )
        if run(command + ["inspect", "--format", "{{.State.Pid}}", identity]).strip() != pid_text:
            raise ValueError("caller restarted during identity resolution; retry")
    if not identities:
        raise ValueError(
            f"{runtime}:{selector}: no exclusive bridge/veth identity; shared SNAT/host networking needs a different verified binding"
        )
    return identities


def resolve_callers(policy, run=OWNED.execute, allow_pending=False, account_lookup=pwd.getpwnam, deny_runtime=False):
    """Re-resolve each principal; failed identities never retain an old allow rule."""
    resolved, pending = {}, []
    for name in sorted({name for endpoint in policy["endpoints"] for name in endpoint["callers"]}):
        resolved[name] = []
        if not policy["callers"].get(name):
            pending.append(f"{name}: no caller identity supplied")
        for binding in policy["callers"].get(name, []):
            try:
                if binding["kind"] in {"disabled", "elsewhere"}:
                    continue
                if binding["kind"] == "service":
                    if binding["runtime"] == "podman" and binding["mode"] == "rootless":
                        uid = account_lookup(binding["account"]).pw_uid
                        if uid <= 0:
                            raise ValueError("automatic rootless identity resolved to root")
                        resolved[name].append({"kind": "local", "uid": uid})
                    elif deny_runtime:
                        pending.append(f"{name}: runtime discovery deferred until after startup")
                    else:
                        try:
                            resolved[name].extend(container_identities(binding, run))
                        except MissingRuntimeCaller:
                            if not removed_service_caller(policy, name):
                                raise
                elif binding["kind"] == "local":
                    if account_lookup(binding["account"]).pw_uid != binding["uid"]:
                        raise ValueError(f"{name}: account UID changed; reverify the input")
                    if binding.get("cgroup") and not Path("/sys/fs/cgroup", binding["cgroup"]).is_dir():
                        raise ValueError(f"{name}: required persistent cgroup slice is unavailable")
                    resolved[name].append(binding)
                elif binding["kind"] == "container":
                    if deny_runtime:
                        pending.append(f"{name}: runtime discovery deferred until after startup")
                        continue
                    try:
                        resolved[name].extend(container_identities(binding, run))
                    except MissingRuntimeCaller as error:
                        if not removed_service_caller(policy, name) and not (
                            isinstance(error, MissingSwarmCaller) and retired_swarm_caller(policy, name, binding, run, account_lookup)
                        ):
                            raise
                else:
                    resolved[name].append(binding)
            except (KeyError, OSError, ValueError, RuntimeError) as error:
                if not allow_pending:
                    raise ValueError(f"unresolved active caller {name}: {error}") from error
                pending.append(f"{name}: {error}")
        resolved[name].sort(key=lambda value: json.dumps(value, sort_keys=True))
    return resolved, pending


def caller_match(binding, family, local):
    if local:
        if binding["kind"] != "local":
            return None
        match = ["-m", "owner", "--uid-owner", str(binding["uid"])]
        if binding.get("cgroup"):
            match += ["-m", "cgroup", "--path", binding["cgroup"]]
        return match
    if binding["kind"] not in {"remote", "container"} or ipaddress.ip_address(binding["address"]).version != family:
        return None
    match = ["-i", binding["interface"], "-s", binding["address"]]
    if binding["kind"] == "container":
        match += ["-m", "physdev", "--physdev-in", binding["veth"], "-m", "mac", "--mac-source", binding["mac"]]
    return match


def desired_rules(policy, family, addresses, callers):
    """Guard before NAT/filter accepts; recheck original tuples after DNAT.

    Local loopback packets have already passed the account-specific OUTPUT
    guard. Only protected endpoint tuples return on lo, never unrelated traffic
    or a blanket source-IP exemption. Owner is never evaluated on forwarding.
    """
    locals_ = sorted(
        {
            str(ipaddress.ip_address(ip))
            for ip in addresses | {policy["inventory_address"], "127.0.0.1", "::1"}
            if ipaddress.ip_address(ip).version == family
        }
    )
    rules = {chain: [["-m", "conntrack", "--ctdir", "REPLY", "-j", "RETURN"]] for table in OWNED.CHAINS.values() for chain in table}
    for endpoint in policy["endpoints"]:
        port = str(endpoint["port"])
        native = ["-p", "tcp", "-m", "addrtype", "--dst-type", "LOCAL", "--dport", port]
        original = [["-p", "tcp", "-m", "conntrack", "--ctdir", "ORIGINAL", "--ctorigdst", ip, "--ctorigdstport", port] for ip in locals_]
        identities = [binding for name in endpoint["callers"] for binding in callers[name]]
        for chain, matches, local in [
            ("SKY-MGT-PRE", [native], False),
            ("SKY-MGT-OUT", [native], True),
            ("SKY-MGT-IN", [native] + original, False),
            ("SKY-MGT-FWD", original, False),
            ("SKY-MGT-LOCAL", [native] + original, True),
        ]:
            for match in matches:
                if not local:
                    rules[chain].append(["-i", "lo"] + match + ["-j", "RETURN"])
                for binding in identities:
                    identity = caller_match(binding, family, local)
                    if identity is not None:
                        rules[chain].append(identity + match + ["-j", "RETURN"])
                rules[chain].append(match + ["-j", "DROP"])
    for chain in rules:
        rules[chain].append(OWNED.TERMINAL)
    return rules


def reconcile(
    policy=None, operation="apply", run=OWNED.execute, allow_pending=False, account_lookup=pwd.getpwnam, dry_run=False, deny_runtime=False
):
    if operation not in {"apply", "validate", "check", "remove"}:
        raise ValueError("unsupported operation")
    dropins = managed_dropins()
    units = []
    if operation != "remove":
        validate_policy(policy)
    native = json.loads(run(["nft", "--json", "list", "ruleset"]))
    if operation != "remove":
        if any("flowtable" in entry for entry in native.get("nftables", [])):
            raise ValueError("flowtables can bypass the protected hooks; resolve offload policy before activation/audit")
        callers, pending = resolve_callers(policy, run, allow_pending or operation == "check", account_lookup, deny_runtime)
        if operation == "validate":
            units = guard_units(policy, account_lookup)
        addresses = OWNED.local_addresses(run)
        if policy["inventory_address"] not in addresses and not allow_pending:
            raise ValueError("the inventory mgt address is not assigned locally")
    else:
        addresses, pending = set(), []
    transactions = []
    for family, tool in [(4, "iptables"), (6, "ip6tables")]:
        if "(nf_tables)" not in run([tool, "--version"]):
            raise ValueError(f"{tool}: expected existing nf_tables backend; switching is forbidden")
        desired = desired_rules(policy, family, addresses, callers) if operation != "remove" else None
        payload = ""
        for table in OWNED.CHAINS:
            required = {"PREROUTING", "OUTPUT"} if table == "mangle" else {"INPUT", "FORWARD", "OUTPUT"}
            family_name = "ip" if family == 4 else "ip6"
            present = any(
                entry.get("table", {}).get("family") == family_name and entry["table"].get("name") == table
                for entry in native.get("nftables", [])
            )
            parents = {
                entry["chain"]["name"]: entry["chain"]
                for entry in native.get("nftables", [])
                if entry.get("chain", {}).get("family") == family_name and entry["chain"].get("table") == table
            }
            # Avoid xtables-nft listing paths which initialize absent skeletons.
            # Audits/removal inspect the read-only native snapshot first.
            if not present:
                if operation == "remove":
                    continue
                if operation == "check":
                    pending.append(f"{tool}: {table} table is absent")
                    continue
                # First restore insertion creates the mapped parents in a new
                # compatibility table. No default-policy declaration is emitted.
                state = {parent: [] for parent in required}
            else:
                saved = run([f"{tool}-save", "-t", table])
                state = OWNED.read_table(saved)
                policies = {line.split()[0][1:]: line.split()[1] for line in saved.splitlines() if line.startswith(":")}
                for parent in required:
                    # xtables-nft-save includes logical built-ins even before
                    # their native chains exist. Restore insertion materializes
                    # the standard chain; audit/removal never insert into it.
                    if policies.get(parent) not in {"ACCEPT", "DROP"} or (
                        parent in parents and parents[parent].get("hook") != parent.lower()
                    ):
                        raise ValueError(f"{tool}: incompatible {table} built-in chain {parent}; refusing shared-policy repair")
            if not required <= state.keys():
                raise ValueError(f"{tool}: required {table} base chains are unavailable")
            payload += OWNED.table_patch(table, state, desired)
        if payload:
            transactions.append((f"{tool}-restore", payload))
    if operation == "check":
        return {
            "changed": False,
            "compliant": not transactions and not pending,
            "rules_compliant": not transactions,
            "pending": pending,
            "families": [4, 6],
        }
    for tool, payload in transactions:
        run([tool, "--test", "--noflush", "--wait", "10"], payload)
    if operation != "validate" and not dry_run:
        for tool, payload in transactions:
            run([tool, "--noflush", "--wait", "10"], payload)
    return {
        "changed": bool(transactions) and operation != "validate" and not dry_run,
        "pending": pending,
        "families": [4, 6],
        "guard_units": units,
        "owned_dropins": [str(path) for path in dropins],
    }


def persistence_paths(policy):
    paths = {
        str(SYSTEMD / name)
        for name in [
            "skynet-mgt-firewall.service",
            "skynet-mgt-firewall-reconcile.service",
            "skynet-mgt-firewall-reconcile.timer",
            "docker.service.d/45-skynet-mgt-firewall.conf",
        ]
    }
    return paths | {str(SYSTEMD / f"{unit}.d/45-skynet-mgt-firewall.conf") for unit in policy.get("guard_units", [])}


def audit_persistence(policy, run=OWNED.execute):
    """Check just the installed owned files/units, without relying on inventory."""
    hashes = policy.get("persistence", {})
    pending = []
    if set(hashes) != persistence_paths(policy):
        return ["installed persistence manifest is incomplete; finish the policy installation"]
    for path, expected in hashes.items():
        try:
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
                pending.append(f"owned persistence file changed: {path}")
        except OSError:
            pending.append(f"owned persistence file missing: {path}")
    for command, unit in [
        ("is-enabled", "skynet-mgt-firewall.service"),
        ("is-enabled", "skynet-mgt-firewall-reconcile.timer"),
        ("is-active", "skynet-mgt-firewall-reconcile.timer"),
    ]:
        try:
            run(["systemctl", command, unit])
        except RuntimeError as error:
            pending.append(str(error))
    return pending


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["validate", "apply", "check", "remove", "observe"])
    parser.add_argument("--config", default="/etc/skynet-mgt-firewall/policy.json")
    parser.add_argument("--stdin", action="store_true")
    parser.add_argument("--allow-pending", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--remove-dropins", action="store_true")
    parser.add_argument("--deny-runtime", action="store_true")
    args = parser.parse_args()
    if args.remove_dropins and (args.operation != "remove" or args.dry_run):
        parser.error("--remove-dropins is only valid for live scoped removal")
    policy = (
        None
        if args.operation == "remove"
        else validate_policy(json.loads(sys.stdin.read() if args.stdin else Path(args.config).read_text()), args.operation != "observe")
    )
    if args.operation == "observe":
        callers, pending = resolve_callers(policy, allow_pending=True)
        print(json.dumps({"callers": callers, "pending": pending}, sort_keys=True))
        return
    # Audit and preflight never create directories/locks or write rules. Live
    # install preflight has run before persistence is touched. Reconciliation
    # failures remain fail closed for disappearing runtime bindings.
    if args.operation in {"check", "validate"} or args.dry_run:
        result = reconcile(policy, args.operation, dry_run=args.dry_run)
        if args.operation == "check":
            result["pending"].extend(audit_persistence(policy))
            result["compliant"] = result["compliant"] and not result["pending"]
    else:
        if args.operation == "apply" and not args.allow_pending:
            reconcile(policy, "validate")
        with OWNED.writer_lock():
            result = reconcile(policy, args.operation, allow_pending=args.allow_pending, deny_runtime=args.deny_runtime)
            if args.remove_dropins:
                for path in result["owned_dropins"]:
                    Path(path).unlink()
                result["changed"] = result["changed"] or bool(result["owned_dropins"])
    print(json.dumps(result, sort_keys=True))
    if args.operation == "check" and not result["compliant"]:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print(f"skynet-mgt-endpoints: {error}", file=sys.stderr)
        sys.exit(1)
