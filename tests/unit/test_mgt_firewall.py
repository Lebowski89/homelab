"""Execute mgt policy planning and packet contracts without hosts or runtimes."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml
from jinja2 import Environment, StrictUndefined
from jinja2.nativetypes import NativeEnvironment

ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / "ansible/roles/service_firewall"


def execute_account_probe(argv, read):
    """Execute the actual streamed probe with only its runtime calls replaced."""
    assert argv[:2] == ["/usr/bin/python3", "-c"]

    def run(command, **kwargs):
        assert 0 < kwargs.pop("timeout") <= 15
        assert kwargs == {"text": True, "capture_output": True, "check": True}
        return SimpleNamespace(stdout=read(command))

    output = io.StringIO()
    with patch("subprocess.run", run), patch("sys.argv", ["-c", argv[3]]), redirect_stdout(output):
        try:
            exec(compile(argv[2], "<account-probe>", "exec"), {"__name__": "__main__"})
        except (ValueError, TimeoutError, subprocess.TimeoutExpired) as error:
            raise RuntimeError("dedicated-account probe rejected metadata") from error
    return output.getvalue()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PLAN = load("ansible/action_plugins/mgt_firewall_plan.py", "mgt_plan_test")
FW = load("ansible/roles/service_firewall/files/mgt-firewall.py", "mgt_firewall_test")
PREFLIGHT = load("ansible/roles/service_firewall/files/haproxy-preflight.py", "haproxy_preflight_test")


def test_account_probe_shares_one_invocation_budget_and_stops_before_more_queries():
    calls = []

    def read(command):
        calls.append(command)
        return "active" if command[0] == "/usr/bin/systemctl" else "true"

    with patch("time.monotonic", side_effect=[100, 101, 110, 116]), pytest.raises(RuntimeError, match="probe rejected"):
        execute_account_probe(["/usr/bin/python3", "-c", FW.ROOTLESS_REPLACEMENT_PROBE, "fixture"], read)
    assert len(calls) == 2
    assert calls[-1][2] == "info"


@pytest.fixture(autouse=True)
def isolate_systemd_files(tmp_path, monkeypatch):
    monkeypatch.setattr(FW, "SYSTEMD", tmp_path / "systemd")


def template(value, defaults=None):
    context = {
        "services_controller_host": "manager",
        "services_storage_host": "storage",
        "services_plex_host": "media",
        "inventory_hostname": "manager",
        "local_ip": "192.0.2.48",
        "services_private_https_port": 10443,
        "hostvars": {"manager": {"local_ip": "192.0.2.48"}, "storage": {"local_ip": "192.0.2.20"}, "media": {"local_ip": "192.0.2.59"}},
    }
    if isinstance(value, dict):
        return {key: template(item, defaults) for key, item in value.items()}
    if isinstance(value, list):
        return [template(item, defaults) for item in value]
    if isinstance(value, str):
        return NativeEnvironment(undefined=StrictUndefined).from_string(value).render({**(defaults or {}), **context})
    return value


def catalog():
    result = {}
    for path in (ROOT / "ansible/group_vars/all/services").glob("*.yml"):
        result.update(yaml.safe_load(path.read_text()))
    return result


def bootstrap():
    result = []
    for role in ["netbox", "infisical"]:
        defaults = yaml.safe_load((ROOT / f"ansible/roles/{role}/defaults/main.yml").read_text())
        result.extend(PLAN.bootstrap_metadata(role, defaults, template))
    return result


def test_real_catalog_and_bootstrap_project_only_metadata_and_ignore_tags():
    services = catalog()
    original = deepcopy(services)
    result = PLAN.build_plan(services, "manager", template, bootstrap())
    assert services == original
    for service in services.values():
        service["tags"] = []
        service["environment"] = {**service.get("environment", {}), "POISON": "{{ lookup('must_never_run') }}"}
        for target in service.get("targets", {}).values():
            target["tags"] = []
    assert PLAN.build_plan(services, "manager", template, bootstrap()) == result
    # Every declared private publication is represented; ingress/protocol
    # exclusions are explicit and the plan never contains secret fields.
    assert "POISON" not in json.dumps(result)
    assert all(endpoint["callers"] for endpoint in result["endpoints"])
    assert all(endpoint["port"] < 22601 for endpoint in result["endpoints"])
    assert {record["publication"] for record in result["excluded"]} >= {"web_secure_private", "stun", "adoption"}


@pytest.mark.parametrize("forgejo_already_selected", [True, False])
def test_installed_policy_extension_retains_forgejo_aliases_and_all_bindings(forgejo_already_selected):
    services = catalog()
    plan = PLAN.build_plan(services, "manager", template, bootstrap())
    active = ["homepage/backend", "forgejo/backend", "haproxy/postgres", "haproxy/metrics"]
    if not forgejo_already_selected:
        active.remove("forgejo/backend")
    policy = PLAN.select_policy(
        plan,
        active,
        {
            "traefik": [container()],
            "autobrr": [{**container(), "selector": "autobrr_autobrr"}],
            "unused": [{**container(), "verified": False}],
        },
        False,
        "192.0.2.48",
        "manager",
        {},
    )
    before = deepcopy(policy)
    inputs = PLAN.installed_policy_inputs(policy, ["forgejo/backend", "znc/backend", "znc/irc"])
    assert policy == before
    prior_ids = [identity for endpoint in policy["endpoints"] for identity in endpoint["ids"]]
    additions = [identity for identity in ["forgejo/backend", "znc/backend", "znc/irc"] if identity not in prior_ids]
    assert inputs["mgt_firewall_active_endpoints"] == prior_ids + additions
    assert "forgejo/backend" in inputs["mgt_firewall_active_endpoints"]
    assert inputs["mgt_firewall_callers"] == policy["callers"]
    assert inputs["mgt_firewall_inputs_verified"] is False
    candidate = PLAN.select_policy(
        plan, inputs["mgt_firewall_active_endpoints"], inputs["mgt_firewall_callers"], False, "192.0.2.48", "manager", {}
    )
    for endpoint in policy["endpoints"]:
        assert endpoint in candidate["endpoints"]
    assert candidate["callers"] == policy["callers"]
    inputs["mgt_firewall_callers"]["autobrr"][0]["verified"] = False
    assert policy == before
    policy["endpoints"][0]["ids"].append("retained/alias")
    assert "retained/alias" in PLAN.installed_policy_inputs(policy, ["znc/irc"])["mgt_firewall_active_endpoints"]


@pytest.mark.parametrize("case", ["missing", "duplicate", "string", "empty"])
def test_installed_policy_extension_rejects_ambiguous_ids(case):
    installed = {
        **policy(),
        "endpoints": [{"port": 18000, "callers": ["traefik"], "ids": ["homepage/backend"]}],
    }
    if case == "missing":
        del installed["endpoints"][0]["ids"]
    elif case == "duplicate":
        installed["endpoints"].append({"port": 18002, "callers": ["traefik"], "ids": ["homepage/backend"]})
    else:
        installed["endpoints"][0]["ids"] = "homepage/backend" if case == "string" else []
    with pytest.raises(ValueError, match="IDs"):
        PLAN.installed_policy_inputs(installed, ["znc/irc"])


def synthetic():
    return {
        "example": {
            "runtime": "podman",
            "name": "example",
            "deploy": {"host": "manager"},
            "ports": {"backend": {"published": 21000, "target": 8000}},
            "traefik": {"port": 21000},
            "targets": {"selected": {"ports": {"metrics": {"published": 21001, "target": 9000}}}},
        }
    }


def test_effective_target_overrides_and_separate_proxy_metrics_callers():
    services = synthetic()
    result = PLAN.build_plan(services, "manager", template, [])
    assert {entry["port"]: entry["callers"] for entry in result["endpoints"]} == {21000: ["traefik"], 21001: ["prometheus"]}
    services["example"]["targets"]["selected"]["deploy"] = {"host": "media"}
    assert not PLAN.build_plan(services, "manager", template, [])["endpoints"]


def test_direct_web_publication_without_proxy_cannot_invent_callers():
    services = synthetic()
    services["example"].pop("targets")
    services["example"].pop("traefik")
    services["example"]["ports"] = {"web": {"published": 21000, "target": 8000}}
    with pytest.raises(ValueError, match="no declared proxy"):
        PLAN.build_plan(services, "manager", template, [])


def test_unclassified_required_private_publication_cannot_silently_escape_policy():
    services = synthetic()
    services["example"]["operational_requirements"] = {"acl": ["mgt_backends"]}
    services["example"]["ports"]["new_listener"] = {"published": 21002, "target": 9001}
    with pytest.raises(ValueError, match="unclassified"):
        PLAN.build_plan(services, "manager", template, [])


@pytest.mark.parametrize("target_port", [None, 26512])
def test_real_znc_irc_publication_keeps_exact_caller_across_target_override(target_port):
    services = catalog()
    services["znc"]["tags"] = []
    services["znc"]["ports"]["irc"] = {"host_ip": "{{ local_ip }}", "published": 26502, "target": 6502, "protocol": "tcp"}
    if target_port is not None:
        services["znc"]["targets"] = {"cutover": {"ports": {"irc": {"published": target_port}}}}
    before = deepcopy(services)
    plan = PLAN.build_plan(services, "manager", template, bootstrap())
    assert services == before
    irc = next(endpoint for endpoint in plan["endpoints"] if "znc/irc" in endpoint["ids"])
    web = next(endpoint for endpoint in plan["endpoints"] if "znc/backend" in endpoint["ids"])
    assert irc["callers"] == ["autobrr"]
    assert irc["port"] == (target_port or 26502)
    assert irc["destination"] == 6502
    assert web["callers"] == ["traefik"]
    binding = {**container(), "selector": "autobrr_autobrr"}
    selected = PLAN.select_policy(plan, ["znc/irc"], {"autobrr": [binding]}, False, "192.0.2.48", "manager", {})
    assert selected["endpoints"] == [irc]
    assert selected["callers"] == {"autobrr": [binding]}
    assert selected["inputs_verified"] is False
    assert FW.validate_policy(selected, False)
    with pytest.raises(ValueError, match="inputs_verified"):
        FW.validate_policy(selected)


@pytest.mark.parametrize("caller", ["disabled", "missing"])
def test_znc_irc_rejects_an_undeclared_caller(caller):
    services = catalog()
    services["znc"]["ports"]["irc"] = {"published": 26502, "target": 6502}
    if caller == "disabled":
        services["autobrr"]["enabled"] = False
    else:
        del services["autobrr"]
    with pytest.raises(ValueError, match="Autobrr caller is not declared"):
        PLAN.build_plan(services, "manager", template, bootstrap())


def test_irc_name_does_not_authorize_other_services_or_udp():
    services = synthetic()
    services["example"]["operational_requirements"] = {"acl": ["mgt_backends"]}
    services["example"]["ports"]["irc"] = {"published": 26502, "target": 6502}
    with pytest.raises(ValueError, match="unclassified"):
        PLAN.build_plan(services, "manager", template, [])
    services = catalog()
    services["znc"]["ports"]["irc"] = {"published": 26502, "target": 6502, "protocol": "udp"}
    with pytest.raises(ValueError, match="only explicit TCP"):
        PLAN.build_plan(services, "manager", template, bootstrap())


def local(uid=2200, account="podman-proxy"):
    return {"kind": "local", "phase": "podman", "account": account, "uid": uid, "verified": True, "restart_verified": True}


def container():
    return {
        "kind": "container",
        "phase": "docker",
        "runtime": "docker",
        "selector": "proxy_traefik",
        "verified": True,
        "restart_verified": True,
        "physdev_verified": True,
    }


def policy(**overrides):
    return {
        "schema": 1,
        "backend": "nf_tables",
        "inventory_host": "manager",
        "inventory_address": "192.0.2.48",
        "inputs_verified": True,
        "endpoints": [{"port": 18000, "callers": ["traefik"]}, {"port": 18001, "callers": ["prometheus"]}],
        "callers": {"traefik": [local(), container()], "prometheus": [local(2201, "podman-metrics")]},
        **overrides,
    }


@pytest.mark.parametrize("flag", [None, False, "true", 1, [], {}])
def test_missing_false_mistyped_confirmations_and_empty_live_contract_fail(flag):
    with pytest.raises(ValueError):
        FW.validate_policy(policy(inputs_verified=flag))
    for field in ["verified", "restart_verified", "physdev_verified"]:
        candidate = policy()
        candidate["callers"]["traefik"][1][field] = flag
        with pytest.raises(ValueError):
            FW.validate_policy(candidate)
    with pytest.raises(ValueError):
        FW.validate_policy(policy(endpoints=[]))
    with pytest.raises(ValueError):
        FW.validate_policy(policy(callers={}))
    assert FW.validate_policy(policy(inputs_verified=False), False)


def test_no_unqualified_root_shared_remote_app_or_broad_network_identity():
    candidates = [
        local(0, "root"),
        local(1000, "operator"),
        {
            "kind": "remote",
            "phase": "native",
            "address": "192.0.2.20",
            "inventory_host": "storage",
            "interface": "eth0",
            "verified": True,
            "restart_verified": True,
        },
    ]
    for candidate in candidates:
        with pytest.raises(ValueError):
            FW.validate_policy(policy(callers={"traefik": [candidate], "prometheus": [local()]}))
    for address in ["192.0.2.0/24", "0.0.0.0", "::", "127.0.0.1"]:
        with pytest.raises(ValueError):
            FW.validate_policy(policy(inventory_address=address))


class Kernel:
    """Minimal netfilter/runtime simulator; all early accepts remain visible."""

    def __init__(self):
        self.calls = []
        self.addresses = ["192.0.2.48", "192.0.2.53", "100.64.0.48", "2001:db8::48", "127.0.0.1", "::1"]
        self.state = {
            family: {
                "mangle": {"PREROUTING": [["-j", "ACCEPT"]], "OUTPUT": [["-j", "ACCEPT"]]},
                "filter": {
                    "INPUT": [["-j", "ts-input"], ["-j", "ACCEPT"]],
                    "FORWARD": [["-j", "ACCEPT"], ["-j", "DOCKER-USER"]],
                    "OUTPUT": [["-j", "ACCEPT"]],
                    "DOCKER-USER": [],
                    "ts-input": [["-j", "ACCEPT"]],
                },
            }
            for family in [4, 6]
        }
        # The compatibility view can advertise standard built-ins which the
        # native table has never materialized. Keep their policies separately.
        self.compatibility_builtins = {
            family: {
                "mangle": {"PREROUTING": "ACCEPT", "OUTPUT": "ACCEPT"},
                "filter": {"INPUT": "ACCEPT", "FORWARD": "ACCEPT", "OUTPUT": "ACCEPT"},
            }
            for family in [4, 6]
        }
        self.native_chain_overrides = {}
        self.peer = "vethcaller"
        self.source = "172.18.0.2"
        self.running = True
        self.docker_active = True
        self.fail_test_family = None
        self.native_rules = {"nftables": [{"table": {"family": "inet", "name": "netavark"}}]}

    def run(self, argv, data=None):
        self.calls.append((argv, data))
        if argv[0] == "nft":
            assert argv == ["nft", "--json", "list", "ruleset"]
            snapshot = deepcopy(self.native_rules)
            for family, tables in self.state.items():
                for name, chains in tables.items():
                    if not chains:
                        continue
                    native_family = "ip" if family == 4 else "ip6"
                    snapshot["nftables"].append({"table": {"family": native_family, "name": name}})
                    for chain in chains:
                        metadata = {"family": native_family, "table": name, "name": chain}
                        if chain in self.compatibility_builtins[family][name]:
                            metadata.update(
                                type="route" if name == "mangle" and chain == "OUTPUT" else "filter",
                                hook=chain.lower(),
                                prio=-150 if name == "mangle" else 0,
                                policy=self.compatibility_builtins[family][name][chain].lower(),
                            )
                        metadata.update(self.native_chain_overrides.get((family, name, chain), {}))
                        snapshot["nftables"].append({"chain": metadata})
            return json.dumps(snapshot)
        if argv == ["systemctl", "is-active", "docker.service"]:
            return "active" if self.docker_active else "activating"
        if argv[0] == "docker":
            assert argv[:3] == ["docker", "--host", "unix:///var/run/docker.sock"]
            argv = ["docker", *argv[3:]]
        if argv[0] == "podman":
            assert argv[:2] == ["podman", "--remote=false"]
            argv = ["podman", *argv[2:]]
        if argv[0] == "readlink":
            return "net:[12345]"
        if argv[0] == "cat":
            return f"0::/system.slice/docker-{self.peer}.scope\n"
        if argv[:2] == ["docker", "ps"]:
            return "abc123\n" if self.running else ""
        if argv[0] in {"docker", "podman"} and argv[1] == "inspect":
            return "1234"
        if argv[:3] == ["ip", "-j", "link"]:
            return json.dumps([{"ifindex": 10, "ifname": self.peer, "master": "docker0"}])
        if argv[0] == "nsenter":
            return json.dumps(
                [{"link_index": 10, "address": "02:42:ac:12:00:02", "addr_info": [{"local": self.source}, {"local": "2001:db8:1::2"}]}]
            )
        if argv[0] == "ip":
            return json.dumps([{"ifname": "fixture-host", "addr_info": [{"local": address} for address in self.addresses]}])
        family = 6 if argv[0].startswith("ip6") else 4
        if argv[1:] == ["--version"]:
            return "iptables v1.8.11 (nf_tables)"
        if argv[0].endswith("-save"):
            table = self.state[family][argv[-1]]
            policies = self.compatibility_builtins[family][argv[-1]]
            return "\n".join(
                [f":{chain} {policies.get(chain, '-')} [0:0]" for chain in dict.fromkeys([*policies, *table])]
                + [shlex.join(["-A", chain] + rule) for chain, rules in table.items() for rule in rules]
            )
        assert argv[0].endswith("-restore") and "--noflush" in argv
        if "--test" in argv:
            if family == self.fail_test_family:
                raise RuntimeError("simulated IPv6 match failure")
            return ""
        table = None
        for line in data.splitlines():
            if line.startswith("*"):
                table = self.state[family][line[1:]]
            elif line != "COMMIT":
                op, chain, *rule = shlex.split(line)
                if op in {"-N", "-F", "-X"}:
                    assert chain.startswith("SKY-MGT-")
                if op in {"-N", "-F"}:
                    table[chain] = []
                elif op == "-X":
                    del table[chain]
                elif op == "-D":
                    table[chain].remove(rule)
                elif op == "-A":
                    table[chain].append(rule)
                elif op == "-I":
                    # First xtables-nft insertion initializes mapped base chains
                    # in a previously absent compatibility table.
                    table.setdefault(chain, [])
                    table[chain].insert(0, rule[1:])
                else:
                    pytest.fail(f"unexpected operation: {op}")
        return ""


def apply(kernel, operation="apply", candidate=None, **kwargs):
    return FW.reconcile(
        candidate or policy(),
        operation,
        run=kernel.run,
        account_lookup=lambda account: SimpleNamespace(pw_uid=2201 if account == "podman-metrics" else 2200),
        **kwargs,
    )


def packet(**overrides):
    return {
        "-i": "eth0",
        "-s": "192.0.2.99",
        "-p": "tcp",
        "--dport": "18000",
        "--ctorigdstport": "18000",
        "--ctdir": "ORIGINAL",
        "--ctorigdst": "192.0.2.48",
        "destination": "192.0.2.48",
        "--uid-owner": "9999",
        "--physdev-in": "vethcaller",
        "--mac-source": "02:42:ac:12:00:02",
        **overrides,
    }


def verdict(table, chain, request, addresses):
    for rule in table[chain]:
        pairs = dict(zip(rule[::2], rule[1::2], strict=True))
        if any(request.get(flag) != value for flag, value in pairs.items() if flag not in {"-m", "-j", "--comment", "--dst-type"}):
            continue
        if "--dst-type" in pairs and request["destination"] not in addresses:
            continue
        target = pairs["-j"]
        if target in {"DROP", "ACCEPT", "RETURN"}:
            return target
        nested = verdict(table, target, request, addresses)
        if nested != "RETURN":
            return nested
    return "RETURN"


@pytest.mark.parametrize("destination", ["192.0.2.48", "192.0.2.53", "100.64.0.48", "2001:db8::48", "127.0.0.1", "::1"])
def test_local_accounts_proxy_metrics_and_loopback_are_separate(destination):
    kernel = Kernel()
    apply(kernel)
    family = 6 if ":" in destination else 4
    request = packet(destination=destination, **{"--ctorigdst": destination, "-i": "lo"})
    output = kernel.state[family]["mangle"]
    assert verdict(output, "OUTPUT", request, kernel.addresses) == "DROP"
    assert verdict(output, "OUTPUT", {**request, "--uid-owner": "2200"}, kernel.addresses) == "ACCEPT"
    assert verdict(output, "OUTPUT", {**request, "--uid-owner": "2201"}, kernel.addresses) == "DROP"
    metrics = {**request, "--dport": "18001", "--ctorigdstport": "18001"}
    assert verdict(output, "OUTPUT", {**metrics, "--uid-owner": "2200"}, kernel.addresses) == "DROP"
    assert verdict(output, "OUTPUT", {**metrics, "--uid-owner": "2201"}, kernel.addresses) == "ACCEPT"
    post = {**request, "destination": "172.30.0.2", "--dport": "8000"}
    assert verdict(kernel.state[family]["filter"], "OUTPUT", post, kernel.addresses) == "DROP"
    assert verdict(kernel.state[family]["filter"], "OUTPUT", {**post, "--uid-owner": "2200"}, kernel.addresses) == "ACCEPT"


@pytest.mark.parametrize("family", [4, 6])
def test_forwarding_requires_exact_peer_source_mac_and_original_port(family):
    kernel = Kernel()
    apply(kernel)
    destination = "192.0.2.53" if family == 4 else "2001:db8::48"
    request = packet(
        destination=destination, **{"--ctorigdst": destination, "-i": "docker0", "-s": kernel.source if family == 4 else "2001:db8:1::2"}
    )
    assert verdict(kernel.state[family]["mangle"], "PREROUTING", request, kernel.addresses) == "ACCEPT"
    for flag, wrong in [("-i", "tailscale0"), ("-s", "192.0.2.20"), ("--physdev-in", "vethother"), ("--mac-source", "02:42:ac:12:00:03")]:
        rejected = {**request, flag: wrong}
        assert verdict(kernel.state[family]["mangle"], "PREROUTING", rejected, kernel.addresses) == "DROP"
        post = {**rejected, "destination": "172.30.0.2", "--dport": "8000"}
        for chain in ["INPUT", "FORWARD", "DOCKER-USER"]:
            assert verdict(kernel.state[family]["filter"], chain, post, kernel.addresses) == "DROP"
    # A forged UID alone conveys no identity in a forwarded packet.
    assert verdict(kernel.state[family]["filter"], "FORWARD", {**request, "-i": "eth0", "--uid-owner": "2200"}, kernel.addresses) == "DROP"


def test_replies_and_unrelated_ingress_preserved():
    kernel = Kernel()
    apply(kernel)
    for table in kernel.state[4].values():
        for chain in [name for name in table if name.startswith("SKY-MGT-")]:
            assert verdict(table, chain, packet(**{"--ctdir": "REPLY"}), kernel.addresses) == "RETURN"
            for port in [22, 53, 2222, 2377, 8080, 10443, 11443, 32400]:
                assert verdict(table, chain, packet(**{"--dport": str(port), "--ctorigdstport": str(port)}), kernel.addresses) == "RETURN"


def test_apply_audit_update_scoped_removal_and_collision_preserve_existing_rules():
    kernel = Kernel()
    original = deepcopy(kernel.state)
    assert apply(kernel)["changed"]
    assert not apply(kernel)["changed"]
    before = deepcopy(kernel.state)
    kernel.calls.clear()
    assert apply(kernel, "check")["compliant"]
    assert kernel.state == before
    assert not any("restore" in argv[0] for argv, _ in kernel.calls)
    kernel.peer, kernel.source = "vethnew", "172.18.0.3"
    assert not apply(kernel, "check")["compliant"]
    assert apply(kernel)["changed"]
    assert not apply(kernel)["changed"]
    assert apply(kernel, "remove")["changed"]
    assert not apply(kernel, "remove")["changed"]
    assert kernel.state == original
    kernel.state[4]["filter"]["SKY-MGT-IN"] = []
    with pytest.raises(ValueError, match="collision"):
        apply(kernel)


def test_strict_preflight_precedes_writes_and_missing_restarted_callers_fail_closed():
    kernel = Kernel()
    original = deepcopy(kernel.state)
    kernel.running = False
    with pytest.raises(ValueError, match="unresolved"):
        apply(kernel, "validate")
    assert kernel.state == original
    result = apply(kernel, allow_pending=True)
    assert result["pending"]
    request = packet(**{"-i": "docker0", "-s": kernel.source})
    assert verdict(kernel.state[4]["mangle"], "PREROUTING", request, kernel.addresses) == "DROP"
    kernel.running = True
    assert apply(kernel)["changed"]
    kernel.running = False
    assert apply(kernel, allow_pending=True)["changed"]
    assert verdict(kernel.state[4]["mangle"], "PREROUTING", request, kernel.addresses) == "DROP"
    assert not apply(kernel, "check")["compliant"]


def test_boot_and_docker_prestart_deny_without_runtime_or_socket_queries():
    kernel = Kernel()
    result = apply(kernel, allow_pending=True, deny_runtime=True)
    assert result["changed"] and result["pending"]
    assert not any(argv[0] in {"docker", "podman", "systemctl"} for argv, _ in kernel.calls)
    request = packet(**{"-i": "docker0", "-s": kernel.source})
    assert verdict(kernel.state[4]["mangle"], "PREROUTING", request, kernel.addresses) == "DROP"
    # A periodic reconcile during daemon startup must not activate the socket.
    kernel.docker_active = False
    kernel.calls.clear()
    assert apply(kernel, allow_pending=True)["pending"]
    assert not any(argv[0] == "docker" for argv, _ in kernel.calls)
    kernel.docker_active = True
    assert apply(kernel)["changed"]
    assert verdict(kernel.state[4]["mangle"], "PREROUTING", request, kernel.addresses) == "ACCEPT"


def test_cold_tables_read_only_audit_and_removal_then_idempotent_boot_guards():
    kernel = Kernel()
    kernel.state = {family: {"mangle": {}, "filter": {}} for family in [4, 6]}
    original = deepcopy(kernel.state)
    assert not apply(kernel, "check")["compliant"]
    assert not apply(kernel, "remove")["changed"]
    assert kernel.state == original
    assert not any(argv[0].endswith(("-save", "-restore")) for argv, _ in kernel.calls)
    assert apply(kernel, allow_pending=True, deny_runtime=True)["changed"]
    assert not apply(kernel, allow_pending=True, deny_runtime=True)["changed"]
    for tables in kernel.state.values():
        assert {"PREROUTING", "OUTPUT"} <= tables["mangle"].keys()
        assert {"INPUT", "FORWARD", "OUTPUT"} <= tables["filter"].keys()
    assert apply(kernel, "remove")["changed"]
    assert not apply(kernel, "remove")["changed"]
    assert all(not rules for tables in kernel.state.values() for chains in tables.values() for rules in chains.values())


def test_existing_partial_compatibility_table_is_not_repaired():
    kernel = Kernel()
    del kernel.state[6]["filter"]["OUTPUT"]
    del kernel.compatibility_builtins[6]["filter"]["OUTPUT"]
    original = deepcopy(kernel.state)
    with pytest.raises(ValueError, match="refusing shared-policy repair"):
        apply(kernel)
    assert kernel.state == original
    assert not any(argv[0].endswith("-restore") for argv, _ in kernel.calls)


@pytest.mark.parametrize("family", [4, 6])
def test_sparse_native_output_materializes_guard_and_preserves_shared_policy(family):
    kernel = Kernel()
    del kernel.state[family]["filter"]["OUTPUT"]
    # Retain an existing restrictive policy and its unrelated rules unchanged.
    kernel.compatibility_builtins[family]["filter"]["INPUT"] = "DROP"
    original, policies = deepcopy(kernel.state), deepcopy(kernel.compatibility_builtins)
    native = json.loads(kernel.run(["nft", "--json", "list", "ruleset"]))
    native_family = "ip" if family == 4 else "ip6"
    assert not any(
        entry.get("chain", {}).get("family") == native_family
        and entry["chain"].get("table") == "filter"
        and entry["chain"].get("name") == "OUTPUT"
        for entry in native["nftables"]
    )
    tool = "iptables" if family == 4 else "ip6tables"
    assert ":OUTPUT ACCEPT [0:0]" in kernel.run([tool + "-save", "-t", "filter"])
    assert not apply(kernel, "check")["compliant"]
    assert not apply(kernel, "remove")["changed"]
    assert kernel.state == original  # neither operation materializes OUTPUT
    assert not any(argv[0].endswith("-restore") for argv, _ in kernel.calls)
    assert not apply(kernel, "validate")["changed"]
    assert kernel.state == original
    kernel.fail_test_family = 6
    with pytest.raises(RuntimeError, match="simulated IPv6 match failure"):
        apply(kernel)
    assert kernel.state == original
    kernel.fail_test_family = None
    kernel.calls.clear()
    assert apply(kernel)["changed"]
    restores = [(argv, data) for argv, data in kernel.calls if argv[0].endswith("-restore")]
    assert ["--test" in argv for argv, _ in restores] == [True, True, False, False]
    output = kernel.state[family]["filter"]["OUTPUT"]
    assert FW.OWNED.owned_jump(output[0], "SKY-MGT-LOCAL")
    destination = "192.0.2.48" if family == 4 else "2001:db8::48"
    request = packet(destination="172.30.0.2", **{"--ctorigdst": destination, "--dport": "8000"})
    assert verdict(kernel.state[family]["filter"], "OUTPUT", request, kernel.addresses) == "DROP"
    assert verdict(kernel.state[family]["filter"], "SKY-MGT-LOCAL", {**request, "--uid-owner": "2200"}, kernel.addresses) == "RETURN"
    assert not apply(kernel)["changed"]
    kernel.calls.clear()
    installed = deepcopy(kernel.state)
    assert apply(kernel, "check")["compliant"]
    assert kernel.state == installed
    assert not any(argv[0].endswith("-restore") for argv, _ in kernel.calls)
    assert apply(kernel, "remove")["changed"]
    assert not apply(kernel, "remove")["changed"]
    expected = deepcopy(original)
    expected[family]["filter"]["OUTPUT"] = []  # retain newly materialized shared built-in
    assert kernel.state == expected
    assert kernel.compatibility_builtins == policies


@pytest.mark.parametrize("family", [4, 6])
@pytest.mark.parametrize("incompatible", ["user-chain", "wrong-hook"])
def test_incompatible_output_rejected_before_any_restore(family, incompatible):
    kernel = Kernel()
    if incompatible == "user-chain":
        kernel.compatibility_builtins[family]["filter"]["OUTPUT"] = "-"
    else:
        kernel.native_chain_overrides[(family, "filter", "OUTPUT")] = {"hook": "input"}
    original = deepcopy(kernel.state)
    for operation in ["validate", "apply", "check", "remove"]:
        with pytest.raises(ValueError, match="incompatible filter built-in chain OUTPUT"):
            apply(kernel, operation)
    assert kernel.state == original
    assert not any(argv[0].endswith("-restore") for argv, _ in kernel.calls)


@pytest.mark.parametrize("collision", ["chain", "reference"])
def test_sparse_native_output_does_not_bypass_ownership_checks(collision):
    kernel = Kernel()
    for family in [4, 6]:
        del kernel.state[family]["filter"]["OUTPUT"]
    if collision == "chain":
        kernel.state[6]["filter"]["SKY-MGT-IN"] = []
    else:
        kernel.state[6]["filter"]["ts-input"].append(["-j", "SKY-MGT-IN"])
    original = deepcopy(kernel.state)
    with pytest.raises(ValueError, match="refusing unowned"):
        apply(kernel)
    assert kernel.state == original
    assert not any(argv[0].endswith("-restore") for argv, _ in kernel.calls)


@pytest.mark.parametrize("family", [4, 6])
def test_scoped_removal_with_managed_rules_does_not_recreate_missing_output(family):
    kernel = Kernel()
    original = deepcopy(kernel.state)
    assert apply(kernel)["changed"]
    del kernel.state[family]["filter"]["OUTPUT"]
    installed = deepcopy(kernel.state)
    kernel.calls.clear()
    assert not apply(kernel, "check")["compliant"]
    assert kernel.state == installed
    assert not any(argv[0].endswith("-restore") for argv, _ in kernel.calls)
    assert not apply(kernel, "remove", dry_run=True)["changed"]
    assert kernel.state == installed
    assert apply(kernel, "remove")["changed"]
    assert "OUTPUT" not in kernel.state[family]["filter"]
    del original[family]["filter"]["OUTPUT"]
    assert kernel.state == original
    assert not apply(kernel, "remove")["changed"]


def test_commands_are_bounded_and_runtime_inspection_stays_local(monkeypatch):
    def hung(argv, **kwargs):
        assert kwargs["timeout"] == 15
        raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

    monkeypatch.setattr(FW.subprocess, "run", hung)
    with pytest.raises(RuntimeError, match="timed out after 15 seconds"):
        FW.execute(["fixture-command"])
    kernel = Kernel()
    binding = {**container(), "runtime": "podman", "phase": "podman"}
    assert FW.container_identities(binding, kernel.run)
    assert all(argv[:2] == ["podman", "--remote=false"] for argv, _ in kernel.calls if argv[0] == "podman")


def test_compose_exact_labels_refresh_running_identities_without_swarm_regression():
    kernel = Kernel()
    binding = {key: value for key, value in container().items() if key != "selector"}
    binding["compose"] = {"project": "observed-project", "service": "observed-service"}
    records = [
        ("abc123", "observed-project", "observed-service", True),
        ("abc456", "other-project", "observed-service", True),
        ("abc789", "observed-project", "other-service", True),
        ("abc999", "observed-project", "observed-service", False),
    ]

    def run(argv, data=None):
        if argv[:4] == ["docker", "--host", "unix:///var/run/docker.sock", "ps"]:
            kernel.calls.append((argv, data))
            filters = [argv[index + 1] for index, value in enumerate(argv) if value == "--filter"]
            assert filters == ["label=com.docker.compose.project=observed-project", "label=com.docker.compose.service=observed-service"]
            return "\n".join(
                identity
                for identity, project, service, running in records
                if project == "observed-project" and service == "observed-service" and running
            )
        return kernel.run(argv, data)

    candidate = policy(callers={"traefik": [binding], "prometheus": [local(2201, "podman-metrics")]})
    FW.validate_policy(candidate)
    assert FW.container_identities(binding, run)[0]["address"] == kernel.source
    assert {argv[-1] for argv, _ in kernel.calls if "inspect" in argv} == {"abc123"}
    records[0] = ("def123", "observed-project", "observed-service", True)
    kernel.peer, kernel.source = "replacement", "172.18.0.9"
    kernel.calls.clear()
    assert FW.container_identities(binding, run)[0]["veth"] == "replacement"
    assert {argv[-1] for argv, _ in kernel.calls if "inspect" in argv} == {"def123"}
    records[0] = ("def123", "observed-project", "observed-service", False)
    with pytest.raises(ValueError, match="no local running caller"):
        FW.container_identities(binding, run)
    kernel.calls.clear()
    resolved, pending = FW.resolve_callers(
        candidate, run, allow_pending=True, deny_runtime=True, account_lookup=lambda account: SimpleNamespace(pw_uid=2201)
    )
    assert pending and not resolved["traefik"]
    assert not any(argv[0] in {"docker", "podman", "systemctl"} for argv, _ in kernel.calls)
    kernel.calls.clear()
    FW.container_identities(container(), kernel.run)
    assert any("label=com.docker.swarm.service.name=proxy_traefik" in argv for argv, _ in kernel.calls)


@pytest.mark.parametrize(
    "change",
    [
        None,
        "replicas",
        "global",
        "unverified",
        "uid",
        "inactive",
        "rootful",
        "namespace",
        "replacement",
        "service-race",
        "docker-race",
        "compose",
        "wrong-host",
        "manager",
        "command-failure",
        "unit-command-failure",
        "info-command-failure",
        "ps-command-failure",
        "inspect-command-failure",
        "pid-reuse",
        "probe-output",
        "probe-no-id",
        "probe-multiple-ids",
        "probe-invalid-id",
        "container-stopped",
        "container-pid-bool",
        "container-name",
        "container-id",
        "compose-retired",
        "compose-retired-missing",
        "compose-retired-ambiguous",
        "compose-retired-replaced",
        "compose-retired-labels",
        "compose-retired-running",
        "compose-retired-restarting",
        "compose-retired-policy",
        "compose-retired-race",
        "compose-retired-removed",
        "compose-retired-removed-id-present",
        "compose-retired-removed-selector-present",
        "compose-retired-removed-race",
        "compose-retired-removed-command-failure",
        "compose-retired-removed-inactive",
        "compose-retired-removed-unverified",
        "compose-retired-removed-namespace",
    ],
)
def test_retired_swarm_binding_requires_stable_verified_running_rootless_replacement(change):
    old = {**container(), "selector": "gotify_gotify"}
    native = {**local(1009, "podman-gotify"), "phase": "podman"}
    candidate = {
        "inventory_host": "mgt",
        "principals": {"gotify": {"future_account": "podman-gotify", "future_runtime": "podman", "inventory_hosts": "mgt"}},
        "endpoints": [{"callers": ["gotify"]}],
        "callers": {"gotify": [old, native]},
    }
    if change in {"unverified", "compose-retired-removed-unverified"}:
        native["restart_verified"] = False
    compose_retirement = bool(change and change.startswith("compose-retired"))
    retired_id = "b" * 64
    if change == "compose" or compose_retirement:
        old.pop("selector")
        old["compose"] = {"project": "gotify", "service": "gotify"}
    if compose_retirement:
        old["retirement"] = {"container_id": retired_id}
    removed = bool(change and change.startswith("compose-retired-removed"))
    if removed:
        old["retirement"]["removal_verified"] = True
    if change == "wrong-host":
        candidate["inventory_host"] = "elsewhere"
    original = deepcopy(candidate)
    cid = "a" * 64
    calls = []
    inspections = 0
    services = 0
    processes = 0
    docker_ps = 0
    absence_queries = 0
    stat_reads = 0

    def account_read(command):
        nonlocal inspections
        if command[:2] == ["/usr/bin/systemctl", "--user"]:
            assert command[2:] == ["is-active", "gotify.service"]
            if change == "unit-command-failure":
                raise RuntimeError("unit query failed")
            return "inactive" if change in {"inactive", "compose-retired-removed-inactive"} else "active"
        assert command[:2] == ["/usr/bin/podman", "--remote=false"]
        if command[2] == "info":
            if change == "info-command-failure":
                raise RuntimeError("store query failed")
            return "false" if change == "rootful" else "true"
        if command[2] == "ps":
            assert "name=^gotify$" in command
            if change == "ps-command-failure":
                raise RuntimeError("container listing failed")
            if change == "probe-no-id":
                return ""
            if change == "probe-multiple-ids":
                return cid + "\n" + "c" * 64
            if change == "probe-invalid-id":
                return "short-id"
            return cid
        assert command[2:4] == ["container", "inspect"] and command[-1] == cid
        if change == "inspect-command-failure":
            raise RuntimeError("container query failed")
        inspections += 1
        return json.dumps(
            {
                "id": "c" * 64 if change == "container-id" else cid,
                "name": "other" if change == "container-name" else "gotify",
                "running": change != "container-stopped",
                "pid": True if change == "container-pid-bool" else 81 if change == "replacement" and inspections > 1 else 80,
            }
        )

    def run(argv):
        nonlocal services, processes, docker_ps, absence_queries, stat_reads
        calls.append(argv)
        if argv == ["systemctl", "is-active", "docker.service"]:
            return "active"
        if argv[:4] == ["docker", "--host", "unix:///var/run/docker.sock", "ps"]:
            if "-a" in argv:
                assert "--no-trunc" in argv
                if removed:
                    absence_queries += 1
                    if change == "compose-retired-removed-command-failure":
                        raise RuntimeError("docker ps failed")
                    if f"id={retired_id}" in argv:
                        return retired_id if change == "compose-retired-removed-id-present" else ""
                    assert "label=com.docker.compose.project=gotify" in argv
                    assert "label=com.docker.compose.service=gotify" in argv
                    return (
                        "c" * 64
                        if change == "compose-retired-removed-selector-present"
                        or (change == "compose-retired-removed-race" and absence_queries > 2)
                        else ""
                    )
                assert "label=com.docker.compose.project=gotify" in argv
                assert "label=com.docker.compose.service=gotify" in argv
                if change == "compose-retired-missing":
                    return ""
                if change == "compose-retired-replaced":
                    return "c" * 64
                return retired_id + ("\n" + "c" * 64 if change == "compose-retired-ambiguous" else "")
            docker_ps += 1
            return "newtask" if change == "docker-race" and docker_ps > 1 else ""
        if argv[:5] == ["docker", "--host", "unix:///var/run/docker.sock", "container", "inspect"]:
            assert compose_retirement and argv[-1] == retired_id
            services += 1
            return json.dumps(
                {
                    "id": retired_id,
                    "name": "/renamed" if change == "compose-retired-race" and services > 1 else "/gotify-gotify-1",
                    "project": "wrong" if change == "compose-retired-labels" else "gotify",
                    "service": "gotify",
                    "running": change == "compose-retired-running",
                    "restarting": change == "compose-retired-restarting",
                    "status": "exited",
                    "pid": 0,
                    "restart": {"Name": "always" if change == "compose-retired-policy" else "no", "MaximumRetryCount": 0},
                }
            )
        if argv[:5] == ["docker", "--host", "unix:///var/run/docker.sock", "service", "inspect"]:
            assert argv[-1] == "gotify_gotify"
            services += 1
            if change == "command-failure":
                raise RuntimeError("docker service inspect failed")
            return json.dumps(
                {
                    "name": "gotify_gotify",
                    "mode": {"Global": {}} if change == "global" else {"Replicated": {"Replicas": 1 if change == "replicas" else 0}},
                    "version": 6 if change == "service-race" and services > 1 else 5,
                }
            )
        if argv[0] == "runuser":
            assert argv[:4] == ["runuser", "-u", "podman-gotify", "--"]
            assert "HOME=/var/lib/podman-gotify" in argv
            assert "XDG_RUNTIME_DIR=/run/user/1009" in argv
            assert "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1009/bus" in argv
            assert 'cd "$HOME" || exit; exec "$@"' in argv
            command = argv[argv.index("skynet-mgt-retired") + 1 :]
            if command[:2] == ["/usr/bin/python3", "-c"]:
                return "{}" if change == "probe-output" else execute_account_probe(command, account_read)
            return account_read(command)
        if argv == ["cat", "/proc/80/stat"]:
            stat_reads += 1
            return "80 (gotify) " + " ".join(["1"] * 19 + ["100" if change == "pid-reuse" and stat_reads > 1 else "99"])
        if argv == ["readlink", "/proc/80/ns/net"]:
            processes += 1
            return "net:[6]" if change in {"namespace", "compose-retired-removed-namespace"} and processes > 1 else "net:[5]"
        if argv == ["cat", "/proc/80/cgroup"]:
            return (
                "0::/system.slice/other.service"
                if change == "manager"
                else "0::/user.slice/user-1009.slice/user@1009.service/app.slice/libpod-test.scope"
            )
        raise AssertionError(argv)

    def lookup(account):
        assert account == "podman-gotify"
        return SimpleNamespace(pw_uid=1010 if change == "uid" else 1009, pw_dir="/var/lib/podman-gotify")

    resolved, pending = FW.resolve_callers(candidate, run, allow_pending=True, account_lookup=lookup)
    assert candidate == original
    assert resolved == {"gotify": [] if change == "uid" else [native]}  # Never authorize the absent Docker identity.
    if change in {None, "compose-retired", "compose-retired-removed"}:
        assert pending == []
        assert inspections == processes == 2
        assert len([argv for argv in calls if argv[0] == "runuser"]) == 2
        assert services == (0 if removed else 2)
        if removed:
            assert absence_queries == 4
        if change is None:
            # A second reconciliation repeats all observations; no identity is cached.
            again, again_pending = FW.resolve_callers(candidate, run, allow_pending=True, account_lookup=lookup)
            assert (again, again_pending) == (resolved, pending)
            assert inspections == processes == 4
            assert len([argv for argv in calls if argv[0] == "runuser"]) == 4
    else:
        assert pending
        inspections = services = processes = docker_ps = stat_reads = 0
        with pytest.raises(ValueError, match="unresolved active caller"):
            FW.resolve_callers(candidate, run, account_lookup=lookup)
    assert not any(command in argv for argv in calls for command in ["apply", "restart", "stop", "update", "pull", "run"])


@pytest.mark.parametrize("retirement", [None, {}, {"container_id": "abc"}, {"container_id": "a" * 64, "extra": True}])
def test_compose_retirement_metadata_rejects_missing_ambiguous_or_partial_ids(retirement):
    binding = container()
    binding.pop("selector")
    binding.update(compose={"project": "observed", "service": "observed"}, retirement=retirement)
    with pytest.raises(ValueError, match="recorded full container ID"):
        FW.validate_policy(policy(callers={"traefik": [binding], "prometheus": [local()]}), require_verified=False)


@pytest.mark.parametrize("value", [True, False, 1, "true", None])
def test_compose_removal_confirmation_is_strict_and_required_live(value):
    binding = container()
    binding.pop("selector")
    binding.update(compose={"project": "observed", "service": "observed"}, retirement={"container_id": "a" * 64, "removal_verified": value})
    candidate = policy(callers={"traefik": [binding], "prometheus": [local()]})
    if type(value) is bool:
        FW.validate_policy(candidate, require_verified=False)
    else:
        with pytest.raises(ValueError, match="recorded full container ID"):
            FW.validate_policy(candidate, require_verified=False)
    if value is True:
        FW.validate_policy(candidate)
    else:
        with pytest.raises(ValueError, match="recorded full container ID"):
            FW.validate_policy(candidate)


@pytest.mark.parametrize("change", ["project-missing", "service-missing", "empty", "conflicting", "podman", "invalid", "extra", "null"])
def test_compose_selector_contract_rejects_partial_or_ambiguous_inputs(change):
    binding = {key: value for key, value in container().items() if key != "selector"}
    binding["compose"] = {"project": "actual-project", "service": "actual-service"}
    if change.endswith("-missing"):
        del binding["compose"][change.removesuffix("-missing")]
    elif change == "empty":
        binding["compose"]["project"] = ""
    elif change == "conflicting":
        binding["selector"] = "swarm_service"
    elif change == "podman":
        binding.update(runtime="podman", phase="podman")
    elif change == "invalid":
        binding["compose"]["service"] = "service/*"
    elif change == "null":
        binding["compose"] = None
    else:
        binding["compose"]["container_id"] = "stale123"
    with pytest.raises(ValueError, match="Compose needs exact"):
        FW.validate_policy(policy(callers={"traefik": [binding], "prometheus": [local()]}))


def test_batched_preflight_projects_only_metadata_and_uses_nologin_accounts(monkeypatch):
    kernel = Kernel()
    monkeypatch.setattr(PREFLIGHT, "Path", lambda path: SimpleNamespace(read_text=lambda: "0::/observed-session.scope"))
    observed = {
        "name": "/observed-compose-container",
        "pid": 1234,
        "swarm": None,
        "project": "observed-project",
        "service": "observed-service",
    }

    def run(argv, data=None):
        if PREFLIGHT.INFO_FORMAT in argv:
            return json.dumps({"node_id": "manager-node", "manager": False})
        if argv[3:5] == ["network", "ls"]:
            return ""
        if PREFLIGHT.FORMAT in argv:
            kernel.calls.append((argv, data))
            return json.dumps(observed)
        if argv[0] == "runuser":
            kernel.calls.append((argv, data))
            return "fed123" if "ps" in argv else "7777"
        if argv[0] == "nsenter" and "ss" in argv:
            kernel.calls.append((argv, data))
            return "0 0 172.18.0.2:12345 192.0.2.48:5432\n"
        if argv[0] == "readlink":
            return "host" if argv[-1] == "/proc/1/ns/net" else "container"
        if argv[0] == "cat" and argv[-1].endswith("/stat"):
            return "1234 (fixture) " + " ".join(["0"] * 19 + ["123"])
        return kernel.run(argv, data)

    report = PREFLIGHT.collect(
        {
            "host": "manager",
            "controller": "manager",
            "expected": {"inventory_address": "192.0.2.48"},
            "port": 5432,
            "accounts": ["podman-forgejo", "podman-haproxy"],
            "running_rootless_accounts": ["podman-forgejo"],
        },
        FW,
        run,
        account_lookup=lambda name: SimpleNamespace(pw_uid=1011 if name == "podman-haproxy" else 1013, pw_dir="/fake/" + name),
        identity_lookup=lambda: {"hostname": "manager", "boot_id": "manager-boot"},
    )
    assert report["containers"][0]["binding"]["compose"] == {"project": "observed-project", "service": "observed-service"}
    assert report["accounts"]["podman-forgejo"]["containers"][0]["destinations"][0]["destination"] == "192.0.2.48"
    assert report["accounts"]["podman-haproxy"] == {"uid": 1011}
    rootless = [argv for argv, _ in kernel.calls if argv[0] == "runuser"]
    assert rootless and all(
        argv[:4] == ["runuser", "-u", "podman-forgejo", "--"] and "HOME=/fake/podman-forgejo" in argv for argv in rootless
    )
    assert all(".Env" not in str(argv) and "connect" not in argv for argv, _ in kernel.calls)
    assert all("podman-haproxy" not in argv for argv in rootless)


def test_preflight_candidates_preserve_accepted_stage_and_block_shared_worker_routes():
    plan = PLAN.build_plan(catalog(), "manager", template, bootstrap())
    endpoint = next(entry for entry in plan["endpoints"] if "haproxy/postgres" in entry["ids"])
    worker_name = next(name for name in endpoint["callers"] if plan["principals"][name].get("future_runtime") == "docker")
    worker_host = plan["principals"][worker_name]["inventory_hosts"]
    worker_host = worker_host[0] if isinstance(worker_host, list) else worker_host

    def record(name, destination):
        return {
            "name": name,
            "project": None,
            "service": None,
            "swarm": name,
            "destinations": [{"destination": destination, "port": 5432}],
            "binding": container(),
            "identities": [{"address": "172.18.0.2"}],
        }

    compose = record("infisical-infisical-1", "192.0.2.48")
    compose.update(swarm=None, project="observed-project", service="different-observed-service")
    compose["binding"] = {key: value for key, value in container().items() if key != "selector"}
    compose["binding"].update(
        compose={"project": compose["project"], "service": compose["service"]},
        verified=False,
        restart_verified=False,
        physdev_verified=False,
    )
    reports = [
        {
            "host": "manager",
            "addresses": ["192.0.2.48", "192.0.2.53"],
            "containers": [compose],
            "accounts": {"podman-forgejo": {"uid": 1013, "containers": [{"pid": 7777, "destinations": []}]}},
        },
        {"host": worker_host, "addresses": ["192.0.2.20"], "containers": [record(worker_name, "192.0.2.20")], "accounts": {}},
    ]
    existing = {"mgt_firewall_active_endpoints": ["homepage/backend"], "mgt_firewall_callers": {"traefik": [container()]}}
    config = {
        "plan": plan,
        "workers": [worker_host],
        "expected_hosts": {report["host"]: {"inventory_address": report["addresses"][0]} for report in reports},
        "collection": [],
        "controller": "manager",
        "names": {"infisical": "infisical-infisical-1"},
        "existing": existing,
    }

    def refresh():
        for report in reports:
            report["identity"] = {"hostname": report["host"], "boot_id": report["host"] + "-boot"}
        config["collection"] = [{"haproxy_preflight_host": report["host"], "stdout": json.dumps(report)} for report in reports]
        return PREFLIGHT.candidates(config)

    result = refresh()
    candidate = result["candidate"]
    assert candidate["mgt_firewall_callers"]["traefik"] == existing["mgt_firewall_callers"]["traefik"]
    assert candidate["mgt_firewall_active_endpoints"] == ["haproxy/postgres", "homepage/backend"]
    assert candidate["mgt_firewall_inputs_verified"] is False
    for name in endpoint["callers"]:
        for binding in candidate["mgt_firewall_callers"][name]:
            assert binding["verified"] is False and binding["restart_verified"] is False
    assert candidate["mgt_firewall_callers"][worker_name][0]["kind"] == "elsewhere"
    assert candidate["mgt_firewall_callers"]["infisical"][0]["compose"] == compose["binding"]["compose"]
    assert not candidate["mgt_firewall_callers"]["controller"] and not candidate["mgt_firewall_callers"]["recovery"]
    selected = PLAN.select_policy(
        plan, candidate["mgt_firewall_active_endpoints"], candidate["mgt_firewall_callers"], False, "192.0.2.48", "manager", {}
    )
    FW.validate_policy(selected, require_verified=False)
    with pytest.raises(ValueError, match="inputs_verified"):
        FW.validate_policy(selected)
    reports[1]["containers"][0]["destinations"][0]["destination"] = "192.0.2.53"
    assert not refresh()["candidate"]["mgt_firewall_callers"][worker_name]


@pytest.fixture(scope="module")
def network_projection(tmp_path_factory, go_cache):
    """Use Go's strict template evaluator, as Docker does, without a daemon/API."""
    go = shutil.which("go")
    if not go:
        pytest.skip("Go unavailable for actual Docker network template regression")
    root = tmp_path_factory.mktemp("network-projection")
    source = root / "projection.go"
    source.write_text("""package main
import ("encoding/json"; "fmt"; "os"; "text/template")
func main() {
    var input struct { Format string; Network map[string]any }
    if err := json.NewDecoder(os.Stdin).Decode(&input); err != nil { panic(err) }
    funcs := template.FuncMap{"json": func(value any) (string,error) { data,err := json.Marshal(value); return string(data),err }}
    projection,err := template.New("").Option("missingkey=error").Funcs(funcs).Parse(input.Format)
    if err == nil { err = projection.Execute(os.Stdout,input.Network) }
    if err != nil { fmt.Fprintln(os.Stderr,err); os.Exit(1) }
}
""")
    binary = root / "projection"
    env = {**os.environ, "GOTOOLCHAIN": "local", "GOPROXY": "off", "GOSUMDB": "off", "GO111MODULE": "off", "GOCACHE": str(go_cache)}
    build = subprocess.run([go, "build", "-o", str(binary), str(source)], capture_output=True, text=True, env=env, timeout=120)
    assert build.returncode == 0, build.stderr

    def render(network):
        result = subprocess.run(
            [str(binary)], input=json.dumps({"format": PREFLIGHT.NETWORK_FORMAT, "network": network}), capture_output=True, text=True
        )
        if result.returncode:
            raise RuntimeError(f"docker failed ({result.returncode}): {result.stderr.strip()}")
        return result.stdout

    return render


@pytest.mark.integration
@pytest.mark.parametrize("populated", [False, True])
@pytest.mark.parametrize("manager_metadata", [False, True])
def test_actual_optional_network_projection_reaches_candidates_and_keeps_unknown_routes_pending(
    network_projection, populated, manager_metadata
):
    raw = {"Id": "overlay-id", "Name": "db", "Driver": "overlay", "Scope": "swarm"}
    if populated:
        raw["Services"] = {"db_haproxy": {"VIP": "172.98.0.144", "Tasks": []}}
    projection = json.loads(network_projection(raw))
    assert {key: projection[key] for key in ["id", "name", "driver", "scope"]} == {
        "id": "overlay-id",
        "name": "db",
        "driver": "overlay",
        "scope": "swarm",
    }
    assert projection["services"] == raw.get("Services")
    reports = []
    for host in PreflightHost.addresses:
        fixture = PreflightHost(host)
        original = fixture.run

        def run(argv, data=None, original=original):
            if PREFLIGHT.NETWORK_FORMAT in argv:
                return network_projection(raw)
            if PREFLIGHT.INFO_FORMAT in argv and not manager_metadata:
                info = json.loads(original(argv, data))
                info["manager"] = False
                return json.dumps(info)
            text = original(argv, data)
            if argv[0] == "nsenter":
                text += "0 0 172.18.0.2:12346 172.98.0.199:5432\n"
            return text

        fixture.run = run
        report = fixture.collect(
            {
                "host": host,
                "controller": "manager",
                "expected": {"inventory_address": fixture.address},
                "port": 5432,
                "provider": "haproxy",
                "accounts": [],
                "running_rootless_accounts": [],
            }
        )
        reports.append(report)
    existing = {"mgt_firewall_active_endpoints": ["homepage/backend"], "mgt_firewall_callers": {"traefik": [container()]}}
    plan = PLAN.build_plan(catalog(), "manager", template, bootstrap())
    # Bind the real catalog's inventory references to this fixture's distinct
    # host names, as the production playbook resolves the inventory groups.
    for principal in plan["principals"].values():
        hosts = principal["inventory_hosts"]
        if isinstance(hosts, str):
            principal["inventory_hosts"] = {"storage": "worker", "media": "plex"}.get(hosts, hosts)
    result = PREFLIGHT.candidates(
        {
            "plan": plan,
            "controller": "manager",
            "workers": ["worker", "plex"],
            "names": {"infisical": "infisical-infisical-1"},
            "existing": existing,
            "expected_hosts": {host: {"inventory_address": ip} for host, ip in PreflightHost.addresses.items()},
            "collection": [{"haproxy_preflight_host": report["host"], "stdout": json.dumps(report)} for report in reports],
        }
    )
    worker = result["reports"][1]["containers"][0]["destinations"]
    if manager_metadata:
        assert worker[0]["routes"][0]["kind"] == "overlay_service"
        assert worker[0]["routes"][0]["worker_only"] is True
        assert result["reports"][2]["containers"][0]["destinations"][0]["routes"][0]["kind"] == "overlay_task"
    elif not populated:
        assert worker[0]["routes"] == [{"kind": "unresolved"}]
    assert worker[-1]["routes"] == [{"kind": "unresolved"}]
    assert result["candidate"]["mgt_firewall_callers"]["qui-alpha"] == []
    assert any("qui-alpha@worker: unresolved" in message for message in result["pending"])
    assert result["candidate"]["mgt_firewall_callers"]["traefik"] == existing["mgt_firewall_callers"]["traefik"]
    assert result["candidate"]["mgt_firewall_inputs_verified"] is False
    assert all(
        binding["verified"] is False and binding["restart_verified"] is False
        for name, bindings in result["candidate"]["mgt_firewall_callers"].items()
        if name != "traefik"
        for binding in bindings
    )


def test_captured_technitium_addressless_vips_do_not_block_haproxy_candidates():
    reports = []
    for host in PreflightHost.addresses:
        fixture = PreflightHost(host)
        reports.append(
            fixture.collect(
                {
                    "host": host,
                    "controller": "manager",
                    "expected": {"inventory_address": fixture.address},
                    "port": 5432,
                    "provider": "haproxy",
                    "accounts": [],
                    "running_rootless_accounts": [],
                }
            )
        )
    # Both operator-captured Technitium VIP records lack Addr. Surrounding
    # service names are fixture identifiers; the captured records are unchanged.
    reports[0]["topology"]["services"] += [
        {"name": "technitium-first", "vips": [{"NetworkID": "ooatvl1rjxogql9p7gtqwy9bo"}]},
        {"name": "technitium-second", "vips": [{"NetworkID": "ooatvl1rjxogql9p7gtqwy9bo"}]},
    ]
    existing = {"mgt_firewall_active_endpoints": ["homepage/backend"], "mgt_firewall_callers": {"traefik": [container()]}}
    plan = PLAN.build_plan(catalog(), "manager", template, bootstrap())
    for principal in plan["principals"].values():
        hosts = principal["inventory_hosts"]
        if isinstance(hosts, str):
            principal["inventory_hosts"] = {"storage": "worker", "media": "plex"}.get(hosts, hosts)
    result = PREFLIGHT.candidates(
        {
            "plan": plan,
            "controller": "manager",
            "workers": ["worker", "plex"],
            "names": {"infisical": "infisical-infisical-1"},
            "existing": existing,
            "expected_hosts": {host: {"inventory_address": ip} for host, ip in PreflightHost.addresses.items()},
            "collection": [{"haproxy_preflight_host": report["host"], "stdout": json.dumps(report)} for report in reports],
        }
    )
    route = result["reports"][1]["containers"][0]["destinations"][0]
    assert route["destination"] == "172.98.0.144"
    assert route["routes"] == [
        {
            "kind": "overlay_service",
            "service": "db_haproxy",
            "network": "overlay-id",
            "task_hosts": ["worker", "plex"],
            "worker_only": True,
            "provider": True,
        }
    ]
    assert result["reports"][2]["containers"][0]["destinations"][0]["routes"][0]["kind"] == "overlay_task"
    candidate = result["candidate"]
    assert candidate["mgt_firewall_callers"]["traefik"] == existing["mgt_firewall_callers"]["traefik"]
    assert candidate["mgt_firewall_inputs_verified"] is False
    assert candidate["mgt_firewall_callers"]["qui-alpha"][0]["route_verified"] is False
    for name, bindings in candidate["mgt_firewall_callers"].items():
        if name == "traefik":
            continue
        for binding in bindings:
            assert binding["verified"] is False and binding["restart_verified"] is False
            if "physdev_verified" in binding:
                assert binding["physdev_verified"] is False


@pytest.mark.parametrize(
    "vip,error",
    [({"NetworkID": "fixture-network", "Addr": "malformed-nonempty-address"}, ValueError), ({"Addr": "172.98.0.144/24"}, KeyError)],
)
def test_vip_mapping_still_rejects_malformed_addresses_and_missing_matched_network(vip, error):
    report = {
        "host": "manager",
        "containers": [{"destinations": [{"destination": "172.98.0.144"}]}],
        "accounts": {},
        "topology": {"services": [{"name": "db_haproxy", "vips": [vip]}]},
    }
    with pytest.raises(error, match="NetworkID" if error is KeyError else "malformed-nonempty-address"):
        PREFLIGHT.map_routes([report], "manager", "haproxy", ["worker", "plex"])


@pytest.mark.integration
def test_network_projection_still_rejects_required_fields_and_real_command_failure(network_projection):
    raw = {"Id": "overlay-id", "Name": "db", "Driver": "overlay"}  # required Scope is missing
    with pytest.raises(RuntimeError, match='map has no entry for key "Scope"'):
        PREFLIGHT.topology(
            {"provider": "haproxy"},
            lambda argv: (
                network_projection(raw)
                if PREFLIGHT.NETWORK_FORMAT in argv
                else (json.dumps({"node_id": "worker-node", "manager": False}) if PREFLIGHT.INFO_FORMAT in argv else "overlay-id")
            ),
        )

    def failed(argv):
        if PREFLIGHT.NETWORK_FORMAT in argv:
            raise RuntimeError("docker failed (1): permission denied on local Docker socket")
        return json.dumps({"node_id": "worker-node", "manager": False}) if PREFLIGHT.INFO_FORMAT in argv else "overlay-id"

    with pytest.raises(RuntimeError, match="permission denied"):
        PREFLIGHT.topology({"provider": "haproxy"}, failed)


@pytest.mark.integration
@pytest.mark.parametrize("host", ["mgt", "unraid", "plex"])
def test_streamed_collector_exits_nonzero_with_concise_stderr_without_crash_hook(host):
    # Execute the real main/error boundary under -c, with a deterministic failed
    # command. The crash hook sentinel would fail if an exception escaped.
    source = (ROLE / "files/haproxy-preflight.py").read_text().rsplit('if __name__ == "__main__":', 1)[0]
    source += """
def fake_execute(argv, data=None):
    raise RuntimeError("docker failed (1): permission denied on local Docker socket")
def fake_collect(config, fw, run, **kwargs):
    return run(DOCKER + ["network", "inspect", "--format", NETWORK_FORMAT, "fixture-network"])
firewall = lambda: SimpleNamespace(execute=fake_execute)
collect = fake_collect
sys.excepthook = lambda *args: print("CRASH_REPORTER_SENTINEL", file=sys.stderr)
sys.exit(main())
"""
    result = subprocess.run([sys.executable, "-c", source, "collect"], input=json.dumps({"host": host}), capture_output=True, text=True)
    assert result.returncode == 1 and result.stdout == ""
    assert f"host={host} operation=collect: docker network inspect:" in result.stderr
    assert "permission denied on local Docker socket" in result.stderr
    assert "Traceback" not in result.stderr and "CRASH_REPORTER_SENTINEL" not in result.stderr
    assert "FIREWALL_SOURCE" not in result.stderr and len(result.stderr) < 250


@pytest.mark.integration
@pytest.mark.parametrize("failed_stage,status", [("check", 7), ("collect", 9), (None, 0)])
def test_documented_preflight_prints_paths_logs_and_preserves_failure_status(tmp_path, failed_stage, status):
    blocks = re.findall(r"```bash\n(.*?)```", (ROOT / "migrator/guides/haproxy.md").read_text(), re.S)
    runners = [block for block in blocks if "run_preflight()" in block and "PREFLIGHT_DIR=" in block]
    assert len(runners) == 1
    block = runners[0]
    # Run only the portable, fake-skynet preflight, never a newly preceding
    # live batch command or an absolute private handoff path.
    assert "/opt/ansible/.secrets/" not in block and "haproxy-cutover-batch.sh" not in block
    fake = tmp_path / "skynet"
    fake.write_text("""#!/bin/bash
printf 'STAGE=%s\\n' "$*"
if [[ " $* " == *" --check "* ]]; then
  test "$FAIL_STAGE" != check || exit 7
else
  test "$FAIL_STAGE" != collect || exit 9
fi
""")
    fake.chmod(0o755)
    env = {
        **os.environ,
        "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
        "PREFLIGHT_DIR": str(tmp_path),
        "HOMEPAGE_FIREWALL_INPUT": str(tmp_path / "fake-accepted.yml"),
        "FAIL_STAGE": failed_stage or "",
    }
    result = subprocess.run(["bash", "-c", block], capture_output=True, text=True, env=env)
    assert result.returncode == status, result.stdout + result.stderr
    assert result.stdout.index("Collection log:") < result.stdout.index("STAGE=")
    paths = dict(line.split(": ", 1) for line in result.stdout.splitlines() if ": " in line and not line.startswith("STAGE="))
    check_log = Path(paths["Check log"])
    assert check_log.exists() and check_log.stat().st_mode & 0o777 == 0o600
    assert "STAGE=raw --tags haproxy_preflight --check" in check_log.read_text()
    collection_log = Path(paths["Collection log"])
    assert collection_log.exists() is (failed_stage != "check")
    assert not Path(paths["Candidate"]).exists()


class PreflightHost:
    """Distinct Linux/Docker fixtures; unknown commands cannot reach a real runtime."""

    addresses = {"manager": "192.0.2.48", "worker": "192.0.2.20", "plex": "192.0.2.59"}

    def __init__(self, host):
        self.host = host
        self.pid = {"manager": 1234, "worker": 2345, "plex": 3456}[host]
        self.name = {"manager": "infisical-infisical-1", "worker": "qui-alpha", "plex": "qui-bravo"}[host]
        self.calls = []
        self.host_network = False
        self.owned_socket = False
        self.address = self.addresses[host]

    def identity(self):
        return {"hostname": self.host, "boot_id": self.host + "-boot"}

    def account(self, name):
        raise KeyError(name)

    def collect(self, config, systemd=True):
        fw = SimpleNamespace(
            NAME=FW.NAME,
            integer=FW.integer,
            OWNED=SimpleNamespace(local_addresses=lambda run: {self.address}),
            container_identities=lambda binding, run: [{"address": "172.18.0.2", "mac": "02:42:ac:12:00:02", "veth": "veth-fixture"}],
        )
        return PREFLIGHT.collect(config, fw, self.run, account_lookup=self.account, identity_lookup=self.identity, systemd=systemd)

    def run(self, argv, data=None):
        self.calls.append(argv)
        if argv == ["ip", "-j", "address", "show"]:
            return json.dumps([{"ifname": "lo"}, {"ifname": "veth-fixture"}])
        if argv[:2] == ["systemctl", "is-active"]:
            return "active"
        if argv[0] == "readlink":
            return "host" if self.host_network or argv[-1] == "/proc/1/ns/net" else "container"
        if argv[0] == "cat" and argv[-1].endswith("/stat"):
            return f"{self.pid} (fixture) " + " ".join(["0"] * 19 + [str(self.pid * 10)])
        if argv[0] == "nsenter":
            owner = self.pid if self.owned_socket else 9999
            destination = {"manager": "192.0.2.48", "worker": "172.98.0.144", "plex": "172.98.0.146"}[self.host]
            return f'0 0 172.18.0.2:12345 {destination}:5432 users:(("postgres-client",pid={owner},fd=7))\n'
        assert argv[:3] == PREFLIGHT.DOCKER, argv
        command = argv[3:]
        if PREFLIGHT.INFO_FORMAT in command:
            return json.dumps({"node_id": "node-" + self.host, "manager": self.host == "manager"})
        if command[:2] == ["service", "ls"]:
            return "service-haproxy"
        if PREFLIGHT.SERVICE_FORMAT in command:
            return json.dumps(
                {
                    "id": "service-haproxy",
                    "name": "db_haproxy",
                    "ports": [{"PublishedPort": 5432, "PublishMode": "host"}],
                    "vips": [{"NetworkID": "overlay-id", "Addr": "172.98.0.144/24"}],
                }
            )
        if command[:2] == ["service", "ps"]:
            return "task-worker task-plex"
        if PREFLIGHT.TASK_FORMAT in command:
            host = command[-1].removeprefix("task-")
            return json.dumps(
                {
                    "id": command[-1],
                    "node_id": "node-" + host,
                    "state": "running",
                    "networks": [{"id": "overlay-id", "addresses": ["172.98.0.145/24" if host == "worker" else "172.98.0.146/24"]}],
                }
            )
        if command[:2] == ["network", "ls"]:
            return "overlay-id"
        if PREFLIGHT.NETWORK_FORMAT in command:
            return json.dumps(
                {
                    "id": "overlay-id",
                    "name": "db",
                    "driver": "overlay",
                    "scope": "swarm",
                    "services": {"db_haproxy": {"VIP": "172.98.0.144", "Tasks": []}},
                }
            )
        if command[0] == "ps":
            return self.host + "-container"
        if PREFLIGHT.FORMAT in command:
            return json.dumps(
                {
                    "name": self.name,
                    "pid": self.pid,
                    "project": "actual-infisical" if self.host == "manager" else None,
                    "service": "infisical" if self.host == "manager" else None,
                    "swarm": None if self.host == "manager" else self.name,
                }
            )
        if command[0] == "top":
            return f"PID\n{self.pid}\n"
        if command[0] == "inspect" and "{{.State.Pid}}" in command:
            return str(self.pid)
        raise AssertionError(argv)


def test_host_network_sockets_need_container_process_ownership():
    fixture = PreflightHost("worker")
    fixture.name = "technitium"
    fixture.host_network = True
    config = {
        "host": "worker",
        "controller": "manager",
        "expected": {"inventory_address": fixture.address},
        "port": 5432,
        "provider": "haproxy",
        "accounts": [],
        "running_rootless_accounts": [],
    }
    report = fixture.collect(config)
    assert report["containers"][0]["destinations"] == []
    fixture.owned_socket = True
    report = fixture.collect(config)
    assert report["containers"][0]["destinations"][0]["owner_pids"] == [fixture.pid]
    assert "binding" not in report["containers"][0]  # socket proof does not grant a shared host UID
    assert all(".Env" not in str(argv) and "args" not in argv for argv in fixture.calls)


def test_unraid_collection_validates_identity_without_systemd(monkeypatch):
    fixture = PreflightHost("worker")
    monkeypatch.setattr(PREFLIGHT, "Path", lambda path: SimpleNamespace(read_text=lambda: "0::/fixture", is_socket=lambda: True))
    config = {
        "host": "worker",
        "controller": "manager",
        "expected": {"inventory_address": fixture.address},
        "port": 5432,
        "provider": "haproxy",
        "accounts": [],
        "running_rootless_accounts": [],
    }
    report = fixture.collect(config, systemd=False)
    assert report["identity"]["hostname"] == "worker"
    assert all(argv[0] != "systemctl" for argv in fixture.calls)
    fixture.address = "192.0.2.48"
    fixture.calls.clear()
    with pytest.raises(ValueError, match="observed host identity"):
        fixture.collect(config, systemd=False)
    assert fixture.calls == []  # no Docker/socket observations accepted on the wrong machine


def test_exact_overlay_routes_distinguish_vips_tasks_and_host_publications():
    reports = []
    for host in PreflightHost.addresses:
        fixture = PreflightHost(host)
        reports.append(
            fixture.collect(
                {
                    "host": host,
                    "controller": "manager",
                    "expected": {"inventory_address": fixture.address},
                    "port": 5432,
                    "provider": "haproxy",
                    "accounts": [],
                    "running_rootless_accounts": [],
                }
            )
        )
    record = reports[1]["containers"][0]
    record["destinations"] += [{"destination": address} for address in ["172.98.0.145", "192.0.2.20", "192.0.2.48", "172.98.0.199"]]
    PREFLIGHT.map_routes(reports, "manager", "haproxy", ["worker", "plex"])
    routes = [entry["routes"][0] for entry in record["destinations"]]
    assert [route["kind"] for route in routes] == ["overlay_service", "overlay_task", "worker_publication", "mgt_publication", "unresolved"]
    assert routes[0]["worker_only"] and routes[0]["task_hosts"] == ["worker", "plex"]
    assert routes[1]["task_host"] == "worker"
    reports[0]["topology"]["services"][0]["tasks"][0]["node_id"] = "node-manager"
    PREFLIGHT.map_routes(reports, "manager", "haproxy", ["worker", "plex"])
    assert record["destinations"][0]["routes"][0]["worker_only"] is False


@pytest.mark.integration
@pytest.mark.parametrize(
    "failure",
    [
        None,
        "inherited-local",
        "wrong-host",
        "global-local-override",
        "global-host-override",
        "aggregation-label",
        "aggregation-identity",
        "command-error",
    ],
)
@pytest.mark.parametrize("window", [0, 1])
def test_actual_batched_preflight_delegation_collection_and_aggregation(tmp_path, failure, window):
    from ansible_task_cases import walk_tasks

    executable = Path(str(Path(sys.executable).with_name("ansible-playbook")))
    if not executable.exists():
        pytest.skip("configured Ansible environment unavailable")
    # The fixture action uses the resolved connection to choose a simulated
    # machine, and calls the real collector. SSH is loaded but never executed.
    actions = tmp_path / "actions"
    actions.mkdir()
    (actions / "fixture_collect.py").write_text(
        f"import json, sys\nsys.path.insert(0, {str(Path(__file__).parent)!r})\n"
        "from ansible.plugins.action import ActionBase\nfrom test_mgt_firewall import PreflightHost\n"
        "class ActionModule(ActionBase):\n"
        "    _supports_async = True\n"
        "    def run(self, tmp=None, task_vars=None):\n"
        "        config = json.loads(self._task.args['stdin'])\n"
        "        address = self._play_context.remote_addr\n"
        "        host = next(host for host, ip in PreflightHost.addresses.items() if ip == address)\n"
        "        if self._connection.transport == 'local': host = 'manager'\n"
        f"        if {failure == 'wrong-host'!r} and host == 'worker': host = 'manager'\n"
        "        config['connection']['effective_transport'] = self._connection.transport\n"
        "        config['connection']['effective_user'] = self._play_context.remote_user\n"
        "        config['connection']['effective_port'] = self._play_context.port\n"
        "        try:\n"
        f"            if {failure == 'command-error'!r}: raise RuntimeError('docker network inspect: permission denied on local Docker socket')\n"
        "            report = PreflightHost(host).collect(config)\n"
        "        except Exception as error:\n"
        "            return {'changed': False, 'rc': 1, 'stderr': 'host=' + config['host'] + ' operation=collect: ' + str(error)}\n"
        f"        if {failure == 'aggregation-label'!r} and host == 'worker': report['host'] = 'manager'\n"
        f"        if {failure == 'aggregation-identity'!r} and host == 'worker': report['identity']['boot_id'] = 'manager-boot'\n"
        "        result = {'changed': False, 'rc': 0, 'stderr': '', 'stdout': json.dumps(report), 'finished': True}\n"
        f"        if config['window_seconds']:\n            from pathlib import Path\n            Path({str(tmp_path)!r}, 'job-' + config['host']).write_text(json.dumps(result))\n            return {{'ansible_job_id': config['host'], 'changed': False}}\n"
        "        return result\n"
    )
    (actions / "fixture_wait.py").write_text(
        "import json\nfrom pathlib import Path\nfrom ansible.plugins.action import ActionBase\n"
        "class ActionModule(ActionBase):\n"
        "    def run(self, tmp=None, task_vars=None):\n"
        f"        path = Path({str(tmp_path)!r}, 'job-' + self._task.args['jid'])\n"
        "        if self._task.args.get('mode') == 'cleanup': path.unlink(); return {'changed': False}\n"
        "        return json.loads(path.read_text())\n"
    )
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(
        yaml.safe_dump(
            {
                "all": {
                    "children": {
                        "tags_ansible_manager": {
                            "vars": {"ansible_connection": "local"},
                            "hosts": {"manager": {"ansible_host": "192.0.2.48", "local_ip": "192.0.2.48", "ansible_user": "manager-user"}},
                        },
                        "device_roles_storage": {
                            "hosts": {"worker": {"ansible_host": "192.0.2.20", "local_ip": "192.0.2.20", "ansible_user": "root"}}
                        },
                    },
                    "hosts": {
                        "plex": {
                            "ansible_host": "192.0.2.59",
                            "local_ip": "192.0.2.59",
                            "ansible_user": "plex-user",
                            "ansible_port": 2222,
                            "ansible_ssh_user": "plex-ssh-user",
                            "ansible_ssh_port": 2223,
                        }
                    },
                }
            }
        )
    )
    cfg = tmp_path / "ansible.cfg"
    cfg.write_text(
        f"[defaults]\naction_plugins={actions}:{ROOT / 'ansible/action_plugins'}\nlibrary={ROOT / 'ansible/library'}\n"
        f"filter_plugins={ROOT / 'ansible/filter_plugins'}\nstdout_callback=default\n[inventory]\nenable_plugins=yaml\n"
    )
    plays = yaml.safe_load((ROOT / "ansible/operations.yml").read_text())
    plays = [next(play for play in plays if any("haproxy_preflight" in task.get("tags", []) for task in walk_tasks(play["tasks"])))]
    plays[0]["tasks"] = yaml.safe_load((ROOT / "ansible/operations/haproxy-firewall-preflight.yml").read_text())
    play = plays[0]
    play["become"] = False
    play["vars_files"] = [str(ROOT / "ansible/group_vars/all/services.yml")]
    output = tmp_path / "candidate.json"
    play["vars"].update(
        services_private_https_port=10443,
        haproxy_preflight_output=str(output),
        haproxy_preflight_window_seconds=window,
        mgt_firewall_active_endpoints=["homepage/backend"],
        mgt_firewall_callers={"traefik": [container()]},
    )
    for task in walk_tasks(play["tasks"]):
        if "ansible.builtin.include_vars" in task:
            task["ansible.builtin.include_vars"]["dir"] = str(ROOT / "ansible/group_vars/all/services")
        if "ansible.builtin.set_fact" in task and "haproxy_preflight_source" in task["ansible.builtin.set_fact"]:
            facts = task["ansible.builtin.set_fact"]
            facts["haproxy_preflight_source"] = facts["haproxy_preflight_source"].replace(
                "roles/service_firewall/files/haproxy-preflight.py", str(ROLE / "files/haproxy-preflight.py")
            )
        if task.get("ansible.builtin.command", {}).get("argv", [])[-1:] == ["collect"]:
            task["fixture_collect"] = task.pop("ansible.builtin.command")
        if "ansible.builtin.async_status" in task:
            task["fixture_wait"] = task.pop("ansible.builtin.async_status")
    if failure == "inherited-local":
        # Remove only the connection fact to reproduce inherited controller
        # transport. Display names have no role in transport isolation.
        for task in walk_tasks(play["tasks"]):
            if task.get("delegate_facts") and "ansible_connection" in task.get("ansible.builtin.set_fact", {}):
                task["when"] = False
    plan = tmp_path / "plan.yml"
    plan.write_text(yaml.safe_dump(plays, sort_keys=False))
    defaults = yaml.safe_load((ROOT / "ansible/roles/workstation/defaults/main.yml").read_text())
    wrapper = tmp_path / "skynet"
    wrapper.write_text(
        Environment(undefined=StrictUndefined)
        .from_string((ROOT / "ansible/roles/workstation/templates/skynet.j2").read_text())
        .render(**{key: str(tmp_path / key) for key in defaults})
    )
    env = {
        **os.environ,
        "ANSIBLE_CONFIG": str(cfg),
        "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local"),
        "ANSIBLE_PLAYBOOK_BIN": str(executable),
        "PLAYBOOK": str(plan),
        "INVENTORY": str(inventory),
        "ANSIBLE_LOG_PATH": str(tmp_path / "log"),
        "BECOME_PASS_FILE": str(tmp_path / "absent"),
        "VAULT_PASS_FILE": str(tmp_path / "absent"),
        "REPO_ROOT": str(tmp_path),
    }
    argv = ["bash", str(wrapper), "raw"]
    if failure == "global-local-override":
        argv += ["-e", "ansible_connection=local"]
    elif failure == "global-host-override":
        argv += ["-e", "ansible_host=192.0.2.48"]
    else:
        argv += ["-e", "{}"]
    if failure is None:
        result = subprocess.run(argv + ["--check"], capture_output=True, text=True, env=env)
        assert result.returncode == 0, result.stdout + result.stderr
        assert not output.exists() and "changed=0" in result.stdout
    result = subprocess.run(argv, capture_output=True, text=True, env=env)
    assert (result.returncode == 0) is (failure is None), result.stdout + result.stderr
    if failure:
        assert not output.exists() and not Path(str(output) + ".metadata.json").exists()
        if failure in {"inherited-local", "wrong-host", "global-host-override"}:
            assert "observed host identity does not match inventory address" in result.stdout
        elif failure == "aggregation-label":
            assert "relabelled collection result" in result.stdout
        elif failure == "aggregation-identity":
            assert "same observed host identity" in result.stdout
        elif failure == "command-error":
            for host in ["manager", "worker", "plex"]:
                assert f"host={host} operation=collect" in result.stdout
            assert "docker network inspect: permission denied" in result.stdout
        assert "FIREWALL_SOURCE" not in result.stdout + result.stderr
        assert "TRANSACTION_SOURCE" not in result.stdout + result.stderr
        assert "Traceback (most recent call last)" not in result.stdout + result.stderr
        return
    reports = json.loads(Path(str(output) + ".metadata.json").read_text())
    if window:
        assert all(report["capture"]["complete"] and report["capture"]["samples"] >= 2 for report in reports)
        assert not list(tmp_path.glob("job-*"))
    assert [report["identity"]["hostname"] for report in reports] == ["manager", "worker", "plex"]
    assert len({report["containers"][0]["pid"] for report in reports}) == 3
    assert [report["addresses"] for report in reports] == [[ip] for ip in PreflightHost.addresses.values()]
    assert [report["connection"]["effective_transport"] for report in reports] == ["local", "ssh", "ssh"]
    assert reports[2]["connection"]["user"] == reports[2]["connection"]["effective_user"] == "plex-ssh-user"
    assert reports[2]["connection"]["port"] == reports[2]["connection"]["effective_port"] == 2223
    candidate = json.loads(output.read_text())
    assert candidate["mgt_firewall_inputs_verified"] is False
    assert candidate["mgt_firewall_callers"]["traefik"] == [container()]
    for name in ["qui-alpha"]:
        assert candidate["mgt_firewall_callers"][name][0]["kind"] == "elsewhere"
        assert candidate["mgt_firewall_callers"][name][0]["route_verified"] is False
    assert candidate["mgt_firewall_callers"]["controller"] == candidate["mgt_firewall_callers"]["recovery"] == []


def test_both_families_validated_before_application_and_restart_jumps_repaired():
    kernel = Kernel()
    kernel.fail_test_family = 6
    original = deepcopy(kernel.state)
    with pytest.raises(RuntimeError):
        apply(kernel)
    assert kernel.state == original
    kernel.fail_test_family = None
    apply(kernel)
    for state in kernel.state.values():
        state["filter"]["DOCKER-USER"].clear()
        state["mangle"]["OUTPUT"].insert(0, ["-j", "ACCEPT"])
    assert not apply(kernel, "check")["compliant"]
    assert apply(kernel)["changed"]
    assert apply(kernel, "check")["compliant"]


def test_bundled_helper_runs_offline_and_audit_creates_no_locks(tmp_path, monkeypatch):
    source = PLAN.bundled_helper()
    compile(source, "bundle", "exec")
    bundled = {"__name__": "offline_policy", "__file__": str(tmp_path / "policy.py")}
    exec(source, bundled)
    assert bundled["OWNED"].MARK == FW.OWNED.MARK
    kernel = Kernel()
    apply(kernel)
    config = tmp_path / "policy.json"
    config.write_text(json.dumps(policy()))
    monkeypatch.setattr(FW.OWNED, "RUN", tmp_path / "not-created")
    actual = FW.reconcile
    monkeypatch.setattr(
        FW,
        "reconcile",
        lambda candidate, operation, **kwargs: actual(
            candidate,
            operation,
            run=kernel.run,
            account_lookup=lambda account: SimpleNamespace(pw_uid=2201 if account == "podman-metrics" else 2200),
            **kwargs,
        ),
    )
    monkeypatch.setattr(FW.sys, "argv", ["policy.py", "check", "--config", str(config)])
    monkeypatch.setattr(FW, "audit_persistence", lambda policy: [])
    FW.main()
    assert not FW.OWNED.RUN.exists()
    config.unlink()
    monkeypatch.setattr(FW.sys, "argv", ["policy.py", "remove"])
    FW.main()
    assert not any(chain.startswith("SKY-MGT-") for state in kernel.state.values() for table in state.values() for chain in table)


def test_host_network_runtime_uid_needs_its_current_exclusive_cgroup():
    kernel = Kernel()
    binding = {**container(), "path": "local", "socket_uid": 0, "socket_hook_verified": True}
    candidate = policy(callers={"traefik": [binding], "prometheus": [local(2201, "podman-metrics")]})
    assert apply(kernel, candidate=candidate)["changed"]
    request = packet(**{"--uid-owner": "0", "--path": "system.slice/docker-vethcaller.scope"})
    assert verdict(kernel.state[4]["mangle"], "OUTPUT", request, kernel.addresses) == "ACCEPT"
    assert (
        verdict(kernel.state[4]["mangle"], "OUTPUT", {**request, "--path": "system.slice/docker-other.scope"}, kernel.addresses) == "DROP"
    )
    assert verdict(kernel.state[4]["mangle"], "OUTPUT", {**request, "--uid-owner": "1000"}, kernel.addresses) == "DROP"
    kernel.peer = "replacement"
    assert apply(kernel, candidate=candidate)["changed"]
    assert verdict(kernel.state[4]["mangle"], "OUTPUT", request, kernel.addresses) == "DROP"
    assert (
        verdict(kernel.state[4]["mangle"], "OUTPUT", {**request, "--path": "system.slice/docker-replacement.scope"}, kernel.addresses)
        == "ACCEPT"
    )


def test_worker_local_database_route_is_explicit_and_never_grants_mgt_access():
    candidate = policy(
        endpoints=[{"port": 5432, "callers": ["worker-app"], "purpose": "declared PostgreSQL applications and recovery"}],
        principals={"worker-app": {"inventory_hosts": "storage", "future_runtime": "docker"}},
        callers={
            "worker-app": [
                {
                    "kind": "elsewhere",
                    "phase": "docker",
                    "inventory_host": "storage",
                    "verified": True,
                    "restart_verified": True,
                    "route_verified": True,
                }
            ]
        },
    )
    kernel = Kernel()
    apply(kernel, candidate=candidate)
    request = packet(**{"--dport": "5432", "--ctorigdstport": "5432", "-s": "192.0.2.20"})
    assert verdict(kernel.state[4]["mangle"], "PREROUTING", request, kernel.addresses) == "DROP"
    for change in ["not-database", "shared-address", "wrong-host", "unverified"]:
        invalid = deepcopy(candidate)
        if change == "not-database":
            invalid["endpoints"][0]["purpose"] = "proxy"
        elif change == "shared-address":
            invalid["principals"]["worker-app"]["inventory_hosts"] = "manager"
        elif change == "wrong-host":
            invalid["callers"]["worker-app"][0]["inventory_host"] = "media"
        else:
            invalid["callers"]["worker-app"][0]["route_verified"] = "true"
        with pytest.raises(ValueError):
            FW.validate_policy(invalid)


def test_handoff_routes_wait_for_mgt_exclusion_and_idle_clients_without_confirming_inputs():
    plan = PLAN.build_plan(catalog(), "manager", template, bootstrap())
    reports = []
    for host in PreflightHost.addresses:
        fixture = PreflightHost(host)
        reports.append(
            fixture.collect(
                {
                    "host": host,
                    "controller": "manager",
                    "expected": {"inventory_address": fixture.address},
                    "port": 5432,
                    "provider": "haproxy",
                    "accounts": [],
                    "running_rootless_accounts": [],
                }
            )
        )
    for principal in plan["principals"].values():
        if isinstance(principal["inventory_hosts"], str):
            principal["inventory_hosts"] = {"storage": "worker", "media": "plex"}.get(
                principal["inventory_hosts"], principal["inventory_hosts"]
            )
    # The real catalog declares both idle applications as worker Docker clients.
    for name in ["bazarr", "romm"]:
        record = deepcopy(reports[1]["containers"][0])
        record.update(name=name, swarm=name, destinations=[])
        reports[1]["containers"].append(record)
    provider = reports[0]["topology"]["services"][0]
    provider["tasks"].append({"node_id": "node-manager", "networks": [], "state": "running"})
    existing = {"mgt_firewall_active_endpoints": ["homepage/backend"], "mgt_firewall_callers": {"traefik": [container()]}}

    def refresh():
        return PREFLIGHT.candidates(
            {
                "plan": plan,
                "controller": "manager",
                "workers": ["worker", "plex"],
                "names": {"infisical": "infisical-infisical-1"},
                "existing": existing,
                "expected_hosts": {host: {"inventory_address": ip} for host, ip in PreflightHost.addresses.items()},
                "collection": [{"haproxy_preflight_host": report["host"], "stdout": json.dumps(report)} for report in reports],
            }
        )

    before = refresh()
    assert before["candidate"]["mgt_firewall_callers"]["qui-alpha"] == []
    assert before["reports"][1]["containers"][0]["destinations"][0]["routes"][0]["worker_only"] is False
    baseline = deepcopy(provider)
    provider["tasks"].pop()  # Simulate only the mgt task leaving the existing VIP.
    after = refresh()
    assert {key: value for key, value in provider.items() if key != "tasks"} == {
        key: value for key, value in baseline.items() if key != "tasks"
    }
    assert provider["tasks"] == baseline["tasks"][:-1]
    callers = after["candidate"]["mgt_firewall_callers"]
    assert callers["qui-alpha"][0]["kind"] == "elsewhere"
    assert callers["qui-alpha"][0]["route_verified"] is False
    assert callers["bazarr"] == callers["romm"] == []
    assert any("bazarr@worker" in entry for entry in after["pending"])
    assert any("romm@worker" in entry for entry in after["pending"])
    for record in reports[1]["containers"][1:]:
        record["destinations"] = [{"destination": "172.98.0.144", "port": 5432}]
    observed = refresh()
    candidate = observed["candidate"]
    assert candidate["mgt_firewall_callers"]["traefik"] == existing["mgt_firewall_callers"]["traefik"]
    assert candidate["mgt_firewall_inputs_verified"] is False
    for name in ["qui-alpha", "bazarr", "romm"]:
        binding = candidate["mgt_firewall_callers"][name][0]
        assert binding["kind"] == "elsewhere" and binding["inventory_host"] == "worker"
        assert binding["route_verified"] is binding["verified"] is binding["restart_verified"] is False
    assert candidate["mgt_firewall_callers"]["controller"] == candidate["mgt_firewall_callers"]["recovery"] == []
    selected = PLAN.select_policy(
        plan, candidate["mgt_firewall_active_endpoints"], candidate["mgt_firewall_callers"], False, "192.0.2.48", "manager", {}
    )
    FW.validate_policy(selected, require_verified=False)
    with pytest.raises(ValueError, match="inputs_verified"):
        FW.validate_policy(selected)
    # Even an operator's overall confirmation cannot hide unresolved declared callers.
    selected["inputs_verified"] = True
    with pytest.raises(ValueError):
        FW.validate_policy(selected)


def test_prepared_haproxy_metrics_requires_its_caller_before_policy_mutation():
    plan = PLAN.build_plan(catalog(), "manager", template, bootstrap())
    prepared = PLAN.select_policy(plan, ["haproxy/metrics"], {}, True, "192.0.2.48", "manager", {})
    FW.validate_policy(prepared, require_verified=False)
    kernel = Kernel()
    with pytest.raises(ValueError, match="missing active caller identities: prometheus"):
        apply(kernel, candidate=prepared)
    assert kernel.calls == []
    prepared["callers"]["prometheus"] = [{**container(), "selector": "monitoring_prometheus", "verified": False}]
    FW.validate_policy(prepared, require_verified=False)
    with pytest.raises(ValueError, match="prometheus: verified"):
        apply(kernel, candidate=prepared)
    assert kernel.calls == []


def test_offline_handoff_stage_rollback_retains_homepage_and_shared_policy():
    kernel = Kernel()
    homepage = policy(endpoints=[{"port": 18000, "callers": ["traefik"]}])
    apply(kernel, candidate=homepage)
    accepted = deepcopy(kernel.state)
    handoff = deepcopy(homepage)
    handoff["endpoints"] += [{"port": port, "callers": ["prometheus"]} for port in [5432, 18405]]
    assert apply(kernel, candidate=handoff)["changed"]
    for port in [18000, 5432, 18405]:
        request = packet(**{"--dport": str(port), "--ctorigdstport": str(port), "-s": "192.0.2.99"})
        assert verdict(kernel.state[4]["mangle"], "PREROUTING", request, kernel.addresses) == "DROP"
    assert apply(kernel, candidate=homepage)["changed"]
    assert kernel.state == accepted
    assert apply(kernel, "check", candidate=homepage)["compliant"]
    assert not apply(kernel, candidate=homepage)["changed"]


def test_stage_selection_bootstrap_overrides_and_inventory_operator_address_precedence():
    result = PLAN.build_plan(synthetic(), "manager", template, bootstrap())
    remote = {
        "kind": "remote",
        "inventory_host": "recovery-host",
        "interface": "tailscale0",
        "phase": "native",
        "verified": True,
        "restart_verified": True,
        "exclusive_verified": True,
    }
    active = [
        next(identity for endpoint in result["endpoints"] for identity in endpoint["ids"] if endpoint["purpose"] == "bootstrap database")
    ]
    selected = PLAN.select_policy(result, active, {"recovery": [remote]}, False, "192.0.2.48", "manager", {"recovery-host": "192.0.2.99"})
    assert selected["callers"]["recovery"][0]["address"] == "192.0.2.99"
    remote.update(observed_address="2001:db8::99", address_override_verified=True)
    selected = PLAN.select_policy(result, active, {"recovery": [remote]}, False, "192.0.2.48", "manager", {"recovery-host": "192.0.2.99"})
    assert selected["callers"]["recovery"][0]["address"] == "2001:db8::99"
    assert len(selected["endpoints"]) == 1
    assert PLAN.select_policy(result, [], {}, False, "192.0.2.48", "manager", {})["endpoints"] == []
    with pytest.raises(ValueError):
        PLAN.select_policy(result, ["invented/port"], {}, False, "192.0.2.48", "manager", {})
    defaults = yaml.safe_load((ROOT / "ansible/roles/netbox/defaults/main.yml").read_text())
    defaults.update(netbox_name="custom-netbox", netbox_port=21003, netbox_redis_backend_port=21004, netbox_postgres_backend_port=21005)
    projected = PLAN.bootstrap_metadata("netbox", defaults, template)
    adapted = PLAN.build_plan({}, "manager", template, projected)
    assert {entry["port"] for entry in adapted["endpoints"]} == {21003, 21004, 21005}
    assert next(entry for entry in adapted["endpoints"] if entry["port"] == 21004)["callers"] == ["custom-netbox"]


def test_flow_offload_unowned_references_and_uid_changes_reject_before_rules_change():
    kernel = Kernel()
    before = deepcopy(kernel.state)
    kernel.native_rules["nftables"].append({"flowtable": {"name": "unrelated-offload"}})
    with pytest.raises(ValueError, match="flowtables"):
        apply(kernel)
    assert kernel.state == before
    kernel.native_rules["nftables"].pop()
    with pytest.raises(ValueError, match="UID changed"):
        FW.reconcile(policy(), run=kernel.run, account_lookup=lambda account: SimpleNamespace(pw_uid=123))
    assert kernel.state == before
    apply(kernel)
    kernel.state[4]["filter"]["INPUT"].append(["-j", "SKY-MGT-IN"])
    before = deepcopy(kernel.state)
    with pytest.raises(ValueError, match="reference"):
        apply(kernel, "remove")
    assert kernel.state == before


def test_persistence_audit_checks_only_owned_content_and_enabled_active_units(monkeypatch):
    import hashlib

    paths = sorted(FW.persistence_paths(policy()))
    content = {path: b"owned deterministic test unit\n" for path in paths}

    class ReadOnlyPath:
        def __init__(self, path):
            self.path = path

        def read_bytes(self):
            return content[self.path]

    candidate = policy(persistence={path: hashlib.sha256(data).hexdigest() for path, data in content.items()})
    monkeypatch.setattr(FW, "Path", ReadOnlyPath)
    calls = []

    def run(argv):
        calls.append(argv)
        assert argv[0] == "systemctl" and argv[1] in {"is-enabled", "is-active"}
        return "active"

    assert not FW.audit_persistence(candidate, run)
    assert len(calls) == 3
    content[paths[0]] += b"unexpected change\n"
    assert FW.audit_persistence(candidate, run)
    assert FW.audit_persistence(policy(), run)


@pytest.mark.integration
@pytest.mark.parametrize(
    "argv,operation,check",
    [
        (["install", "mgt-firewall"], "install", False),
        (["update", "mgt-firewall"], "install", False),
        (["check", "mgt-firewall"], "install", True),
        (["run", "mgt-firewall", "observe"], "observe", False),
        (["run", "mgt-firewall", "check"], "check", False),
        (["remove", "mgt-firewall"], "remove", False),
    ],
)
def test_executable_skynet_dispatch_is_policy_only_and_preserves_private_input_path(tmp_path, argv, operation, check):
    defaults = yaml.safe_load((ROOT / "ansible/roles/workstation/defaults/main.yml").read_text())
    variables = {key: str(tmp_path / key) for key in defaults}
    variables["workstation_ansible_path"] = str(tmp_path / "ansible")
    wrapper = tmp_path / "skynet"
    wrapper.write_text(
        Environment(undefined=StrictUndefined)
        .from_string((ROOT / "ansible/roles/workstation/templates/skynet.j2").read_text())
        .render(**variables)
    )
    assert subprocess.run(["bash", "-n", str(wrapper)], capture_output=True).returncode == 0
    recorder, output, inputs = tmp_path / "recorder", tmp_path / "args", tmp_path / "private inputs.yml"
    recorder.write_text('#!/bin/bash\nprintf "%s\\n" "$@" > "$RECORD"\n')
    recorder.chmod(0o755)
    inputs.write_text("---\nmgt_firewall_inputs_verified: false\n")
    env = {
        **os.environ,
        "PLAYBOOK": str(tmp_path / "ansible/playbook.yml"),
        "ANSIBLE_PLAYBOOK_BIN": str(recorder),
        "RECORD": str(output),
        "ANSIBLE_LOG_PATH": str(tmp_path / "log"),
        "BECOME_PASS_FILE": str(tmp_path / "absent"),
        "VAULT_PASS_FILE": str(tmp_path / "absent"),
        "REPO_ROOT": str(tmp_path),
        "MGT_FIREWALL_VARS_FILE": str(inputs),
    }
    result = subprocess.run(["bash", str(wrapper), "limit", "manager", *argv], capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr
    args = output.read_text().splitlines()
    assert str(tmp_path / "ansible/operations.yml") in args
    assert str(tmp_path / "ansible/playbook.yml") not in args
    assert args[args.index("--tags") + 1] == f"mgt_firewall_{operation}"
    assert args[args.index("--limit") + 1] == "manager"
    assert "@" + str(inputs) in args
    assert ("--check" in args) is check


@pytest.mark.integration
@pytest.mark.parametrize(
    "operation,verified,check_mode,malformed,success",
    [
        ("install", False, True, False, True),
        ("install-real", False, True, False, True),
        ("observe", False, False, False, True),
        ("install", False, False, False, False),
        ("install", "true", False, False, False),
        ("install", True, False, False, False),
        ("install", False, True, True, False),
        ("check", None, True, False, True),
        ("remove", None, False, True, True),
    ],
)
def test_actual_ansible_loader_guards_readme_and_offline_recovery(tmp_path, operation, verified, check_mode, malformed, success):
    binary = Path(str(Path(sys.executable).with_name("ansible-playbook")))
    if not binary.exists():
        pytest.skip("repository Ansible environment unavailable")
    service_dir = tmp_path / "group_vars/all/services"
    service_dir.mkdir(parents=True)
    (service_dir / "README.md").write_text("# Catalog\nReal directories include documentation.\n")
    services = catalog() if operation == "install-real" else synthetic()
    for service in services.values():
        service["environment"] = {**service.get("environment", {}), "POISON": "{{ lookup('must_never_run') }}"}
    (service_dir / "service.yml").write_text(yaml.safe_dump(services))
    if malformed:
        (service_dir / "malformed.yml").write_text("malformed: [unterminated\n")
    (tmp_path / "install.yml").write_text(
        "---\n- name: Installation sentinel\n  ansible.builtin.fail:\n    msg: mutation sentinel reached\n"
    )
    (tmp_path / "remove.yml").write_text("---\n- name: Recovery sentinel\n  ansible.builtin.debug:\n    msg: recovery reached\n")
    # Empty caller input executes the real streamed helper but cannot invoke
    # any runtime/network/NSS observation; it reports pending metadata only.
    (tmp_path / "observe.yml").write_text((ROLE / "tasks/mgt/observe.yml").read_text())
    tasks = yaml.safe_load((ROLE / "tasks/mgt/main.yml").read_text())
    variables = {
        "services_controller_host": "manager",
        "services_storage_host": "storage",
        "services_plex_host": "media",
        "local_ip": "192.0.2.48",
        "mgt_firewall_operation": "install" if operation == "install-real" else operation,
        "mgt_firewall_root": "/etc/skynet-mgt-firewall",
        "mgt_firewall_active_endpoints": ["traefik/metrics" if operation == "install-real" else "example/backend"],
        "mgt_firewall_callers": {},
        "mgt_firewall_inputs_verified": verified,
        "services_private_https_port": 10443,
    }
    playbook = [{"name": "Local mgt guard harness", "hosts": "manager", "gather_facts": False, "vars": variables, "tasks": tasks}]
    (tmp_path / "playbook.yml").write_text(yaml.safe_dump(playbook, sort_keys=False))
    inventory = {
        "all": {
            "hosts": {
                "manager": {"ansible_connection": "local", "local_ip": "192.0.2.48"},
                "storage": {"ansible_connection": "local", "local_ip": "192.0.2.20"},
                "media": {"ansible_connection": "local", "local_ip": "192.0.2.59"},
            }
        }
    }
    (tmp_path / "inventory.yml").write_text(yaml.safe_dump(inventory))
    cfg = tmp_path / "ansible.cfg"
    cfg.write_text(
        f"[defaults]\naction_plugins={ROOT}/ansible/action_plugins\nlibrary={ROOT}/ansible/library\nvars_plugins_enabled=\n"
        "stdout_callback=default\nretry_files_enabled=False\n[inventory]\nenable_plugins=yaml\n"
    )
    argv = [str(binary), "-i", str(tmp_path / "inventory.yml"), str(tmp_path / "playbook.yml")]
    if check_mode:
        argv.append("--check")
    result = subprocess.run(
        argv, capture_output=True, text=True, env={**os.environ, "ANSIBLE_CONFIG": str(cfg), "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local")}
    )
    assert (result.returncode == 0) is success, result.stdout + result.stderr
    assert "mutation sentinel reached" not in result.stdout
    if operation != "remove" and malformed:
        assert "malformed.yml" in result.stdout + result.stderr
    if success:
        assert "changed=0" in result.stdout
        if operation == "remove" and not check_mode:
            assert "recovery reached" in result.stdout


def test_persistence_ordering_and_dynamic_tags_do_not_deploy_applications():
    from ansible_task_cases import walk_tasks

    service = (ROLE / "templates/mgt/skynet-mgt-firewall.service.j2").read_text()
    assert "systemd-logind.service" in service and "Before=docker.service" in service
    assert "ExecStop=" not in service
    assert "apply --allow-pending --deny-runtime" in service
    timer = (ROLE / "templates/mgt/skynet-mgt-firewall-reconcile.timer.j2").read_text()
    assert "OnUnitInactiveSec=5s" in timer
    dropin = (ROLE / "templates/mgt/docker-ordering.conf.j2").read_text()
    assert "ExecStartPre=" in dropin and "ExecStartPost=" in dropin
    assert "apply --allow-pending --deny-runtime" in next(line for line in dropin.splitlines() if line.startswith("ExecStartPre="))
    assert "--deny-runtime" not in next(line for line in dropin.splitlines() if line.startswith("ExecStartPost="))
    tasks = yaml.safe_load((ROLE / "tasks/mgt/main.yml").read_text())
    # Missing applied tags silently skip the selected firewall operation.
    includes = [
        task["ansible.builtin.include_tasks"]
        for task in walk_tasks(tasks)
        if task.get("ansible.builtin.include_tasks", {}).get("file") == "{{ mgt_firewall_operation }}.yml"
    ]
    assert any(
        {"mgt_firewall_install", "mgt_firewall_observe", "mgt_firewall_check", "mgt_firewall_remove"}
        <= set(include.get("apply", {}).get("tags", []))
        for include in includes
    )
    # Caller and both-family validation must finish before the policy writer.
    install = list(walk_tasks(yaml.safe_load((ROLE / "tasks/mgt/install.yml").read_text())))
    first_write = next(index for index, task in enumerate(install) if "service_firewall_lifecycle" in task)
    assert any("validate" in task.get("ansible.builtin.command", {}).get("argv", []) for task in install[:first_write])
    for path in (ROLE / "tasks/mgt").glob("*.yml"):
        for task in yaml.safe_load(path.read_text()):
            unit = task.get("ansible.builtin.systemd_service", {})
            assert unit.get("state") != "restarted"
            if unit.get("name") == "skynet-mgt-firewall.service":
                assert "state" not in unit  # stopping Requires would stop applications


def test_guard_dependencies_are_dedicated_and_removed_without_inventory(tmp_path, monkeypatch, capsys):
    kernel = Kernel()
    candidate = policy()
    candidate["principals"] = {
        "rootful-endpoint": {"future_runtime": "podman", "future_account": "root"},
        "rootless-endpoint": {"future_runtime": "podman", "future_account": "podman-provider"},
    }
    candidate["endpoints"][0]["service"] = "rootful-endpoint"
    candidate["endpoints"][1]["service"] = "rootless-endpoint"

    def account(name):
        return SimpleNamespace(pw_uid={"podman-provider": 2202, "podman-proxy": 2200, "podman-metrics": 2201}[name])

    assert FW.guard_units(candidate, account) == ["rootful-endpoint.service", "user@2200.service", "user@2201.service", "user@2202.service"]
    # Staging never takes ownership of native/SSH user managers.
    candidate["callers"]["not-active"] = [{"kind": "local", "account": "podman-unused", "uid": 1000}]
    assert "user@1000.service" not in FW.guard_units(candidate, account)
    path = FW.SYSTEMD / "user@2202.service.d/45-skynet-mgt-firewall.conf"
    path.parent.mkdir(parents=True)
    path.write_text("foreign drop-in\n")
    with pytest.raises(ValueError, match="persistence collision"):
        apply(kernel, "validate")
    path.write_text(FW.DROPIN_MARKER + "[Unit]\nRequires=skynet-mgt-firewall.service\n")
    assert str(path) in apply(kernel, "remove", dry_run=True)["owned_dropins"]
    # Recovery requires no installed policy, NSS/runtime resolution or inventory.
    actual = FW.reconcile
    monkeypatch.setattr(FW, "reconcile", lambda candidate, operation, **kwargs: actual(candidate, operation, run=kernel.run, **kwargs))
    monkeypatch.setattr(FW.OWNED, "RUN", tmp_path / "run")
    monkeypatch.setattr(FW.sys, "argv", ["policy.py", "remove", "--remove-dropins"])
    FW.main()
    assert json.loads(capsys.readouterr().out)["changed"]
    assert not path.exists()


def test_remote_recovery_is_an_explicit_exclusive_inventory_identity():
    kernel = Kernel()
    binding = {
        "kind": "remote",
        "phase": "native",
        "inventory_host": "recovery-client",
        "address": "2001:db8::99",
        "interface": "tailscale0",
        "verified": True,
        "restart_verified": True,
        "exclusive_verified": True,
    }
    candidate = policy(endpoints=[{"port": 5432, "callers": ["recovery"]}], callers={"recovery": [binding]})
    apply(kernel, candidate=candidate)
    request = packet(
        destination="2001:db8::48",
        **{"--ctorigdst": "2001:db8::48", "--dport": "5432", "--ctorigdstport": "5432", "-s": "2001:db8::99", "-i": "tailscale0"},
    )
    assert verdict(kernel.state[6]["mangle"], "PREROUTING", request, kernel.addresses) == "ACCEPT"
    assert verdict(kernel.state[6]["mangle"], "PREROUTING", {**request, "-s": "2001:db8::100"}, kernel.addresses) == "DROP"
    binding["exclusive_verified"] = False
    with pytest.raises(ValueError, match="exclusive_verified"):
        FW.validate_policy(candidate)


@pytest.mark.integration
@pytest.mark.parametrize("operation", ["install", "observe"])
def test_actual_install_preflight_preserves_dedicated_account_shell_home(tmp_path, operation):
    """Command argument expansion must not rewrite HOME inside streamed Python."""
    binary = Path(str(Path(sys.executable).with_name("ansible-playbook")))
    if not binary.exists():
        pytest.skip("repository Ansible environment unavailable")
    home = tmp_path / "dedicated-home"
    home.mkdir()
    result_var = "mgt_firewall_preflight" if operation == "install" else "mgt_firewall_observation"
    task = next(task for task in yaml.safe_load((ROLE / f"tasks/mgt/{operation}.yml").read_text()) if task.get("register") == result_var)
    source = (
        "import json, subprocess\n"
        f"home = {str(home)!r}\n"
        "prefix = ['env', 'HOME=' + home, '/bin/sh', '-c', "
        "'cd \"$HOME\" || exit; exec \"$@\"', 'skynet-mgt-retired']\n"
        "result = subprocess.run(prefix + ['/bin/pwd'], capture_output=True, text=True, check=True)\n"
        "assert result.stdout.strip() == home, 'dedicated account HOME was rewritten by Ansible'\n"
        "print(json.dumps({'guard_units': [], 'account_home_preserved': True}))\n"
    )
    play = [
        {
            "name": "Isolated real install preflight transport",
            "hosts": "localhost",
            "gather_facts": False,
            "vars": {
                "ansible_facts": {"python": {"executable": sys.executable}},
                "mgt_firewall_helper_source": source,
                "mgt_firewall_policy": {},
            },
            "tasks": [
                task,
                {
                    "name": "Require actual dedicated home result",
                    "ansible.builtin.assert": {"that": f"({result_var}.stdout | from_json).account_home_preserved is sameas true"},
                },
            ],
        }
    ]
    (tmp_path / "play.yml").write_text(yaml.safe_dump(play, sort_keys=False))
    (tmp_path / "ansible.cfg").write_text("[defaults]\nstdout_callback=default\nvars_plugins_enabled=\n")
    result = subprocess.run(
        [str(binary), "-i", "localhost,", "-c", "local", str(tmp_path / "play.yml")],
        capture_output=True,
        text=True,
        timeout=45,
        env={**os.environ, "ANSIBLE_CONFIG": str(tmp_path / "ansible.cfg"), "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local")},
    )
    assert result.returncode == 0, result.stdout + result.stderr
