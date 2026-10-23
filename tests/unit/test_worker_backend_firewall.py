"""Exercise derived worker policy and reconciliation without a real firewall."""

from __future__ import annotations

import importlib.util
import json
import os
import shlex
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, StrictUndefined
from jinja2.nativetypes import NativeEnvironment

ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / "ansible/roles/service_firewall"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PLAN = load("ansible/action_plugins/worker_backend_firewall_plan.py", "worker_firewall_plan_test")
VALIDATE = load("ansible/action_plugins/worker_backend_firewall_validate.py", "worker_firewall_validate_test")
FW = load("ansible/roles/service_firewall/files/worker-backend-firewall.py", "worker_firewall_test")


def resolve(value):
    if isinstance(value, dict):
        return {key: resolve(item) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve(item) for item in value]
    if isinstance(value, str) and ("{{" in value or "{%" in value):
        return (
            NativeEnvironment(undefined=StrictUndefined)
            .from_string(value)
            .render(
                services_controller_host="manager",
                services_storage_host="storage",
                services_plex_host="media",
            )
        )
    return value


def catalog():
    services = {}
    for path in (ROOT / "ansible/group_vars/all/services").glob("*.yml"):
        services.update(yaml.safe_load(path.read_text()))
    return services


def plan(services):
    return PLAN.build_plan(services, ["storage", "media"], "192.0.2.48", resolve)


def test_real_catalog_selects_physical_workers_without_templating_application_values():
    services = catalog()
    original = deepcopy(services)
    observed = []

    def minimal_template(metadata):
        assert set(metadata) == {"host", "backend", "ports"}
        observed.append(metadata)
        return resolve(metadata)

    result = PLAN.build_plan(services, ["storage", "media"], "192.0.2.48", minimal_template)
    # Whole catalog evaluated, but only host backend publications protected;
    # Syncthing/P2P/IRC/etc. listeners stay outside this temporary allocation.
    assert len(result["storage"]["ports"]) == 22
    assert len(result["media"]["ports"]) == 2
    assert any(endpoint["service"] == "tautulli" for endpoint in result["media"]["endpoints"])
    assert any(endpoint["service"] == "blackbox_exporter" for endpoint in result["storage"]["endpoints"])
    assert all(22601 <= port <= 22623 for entry in result.values() for port in entry["ports"])
    assert len(observed) == 23
    assert services == original
    for service in services.values():
        service["tags"] = []
        service["environment"] = {"POISON": "{{ lookup('must_never_run') }}"}
        for target in service.get("targets", {}).values():
            target["tags"] = []
    assert plan(services) == result


def test_effective_target_ports_and_placement_override_base():
    service = catalog()["tautulli"]
    service["targets"] = {
        "new": {
            "deploy": {"host": "storage"},
            "traefik": {"backend_host_inventory": "storage"},
            "ports": {"web_backend": {"published": 22601}},
        },
        "disabled": {"enabled": False},
    }
    result = plan({"example": service})
    assert result["media"]["ports"] == []
    assert result["storage"]["ports"] == [22601]
    assert result["storage"]["endpoints"][0]["target"] == "new"
    # New named publications in the reserved allocation cannot be overlooked.
    service.pop("targets")
    service["ports"]["extra_metrics"] = {"published": 22620, "target": 9999, "mode": "host"}
    assert plan({"example": service})["media"]["ports"] == [22619, 22620]


@pytest.mark.parametrize(
    "change",
    [
        {"deploy": {"host": "manager"}},
        {"traefik": {"backend_host_inventory": "storage"}},
        {"ports": {"web_backend": {"published": 22, "target": 8181, "mode": "host"}}},
        {"ports": {"web_backend": {"published": True, "target": 8181, "mode": "host"}}},
        {"ports": {"web_backend": {"published": 22619, "target": 8181, "mode": "ingress"}}},
        {"ports": {"web_backend": {"published": 22619, "target": 8181, "mode": "host", "protocol": "udp"}}},
        {"enabled": "true"},
        {"runtime": "podman"},
    ],
)
def test_bad_or_unsupported_publication_fails_closed(change):
    service = catalog()["tautulli"]
    service.update(change)
    with pytest.raises(ValueError):
        plan({"example": service})


def test_duplicate_host_publication_and_empty_worker_set_rejected():
    service = catalog()["tautulli"]
    with pytest.raises(ValueError, match="duplicate"):
        plan({"a": service, "b": service})
    with pytest.raises(ValueError):
        PLAN.build_plan({}, [], "192.0.2.48", resolve)


def policy(**overrides):
    return {
        "schema": 1,
        "backend": "legacy",
        "inventory_host": "storage",
        "inventory_address": "192.0.2.20",
        "ports": [22601, 22602, 22622],
        "sources": ["192.0.2.48"],
        "sources_verified": True,
        **overrides,
    }


@pytest.mark.parametrize("confirmation", [None, False, "true", "false", 1, [], {}])
def test_missing_false_or_mistyped_source_confirmation_blocks_live_install(confirmation):
    candidate = policy(sources_verified=confirmation)
    with pytest.raises(ValueError):
        VALIDATE.validate(candidate, True)
    if confirmation is False:
        assert VALIDATE.validate(candidate, False)  # safe check-mode planning
    else:
        with pytest.raises(ValueError):
            VALIDATE.validate(candidate, False)


@pytest.mark.parametrize("source", ["192.0.2.0/24", "0.0.0.0", "::", "localhost", True, "127.0.0.1", "224.0.0.1"])
def test_broad_or_invalid_sources_rejected_even_in_plans(source):
    with pytest.raises(ValueError):
        VALIDATE.validate(policy(sources=[source]), False)


class Kernel:
    """A fake iptables-save/restore executor that preserves unrelated state."""

    def __init__(self, backend="legacy"):
        self.backend = backend
        self.calls = []
        self.addresses = ["192.0.2.20", "192.0.2.21", "100.64.0.20", "2001:db8::20", "fe80::20"]
        self.state = {
            family: {
                "mangle": {"PREROUTING": [["-j", "ACCEPT"]], "OUTPUT": [["-j", "ACCEPT"]]},
                "filter": {
                    "INPUT": [["-j", "ts-input"], ["-j", "ACCEPT"]],
                    "FORWARD": [["-j", "ACCEPT"], ["-j", "DOCKER-USER"]],
                    "DOCKER-USER": [],
                    "ts-input": [["-j", "ACCEPT"]],
                },
            }
            for family in [4, 6]
        }
        self.fail_test_family = None

    def run(self, argv, data=None):
        self.calls.append((argv, data))
        if argv[0] == "ip":
            return json.dumps([{"addr_info": [{"local": address} for address in self.addresses]}])
        family = 6 if argv[0].startswith("ip6") else 4
        if argv[1:] == ["--version"]:
            return f"{argv[0]} v1.8.11 ({self.backend})"
        if argv[0].endswith("-save"):
            table = self.state[family][argv[-1]]
            lines = [f":{chain} {'ACCEPT' if chain in {'INPUT', 'FORWARD', 'OUTPUT', 'PREROUTING'} else '-'} [0:0]" for chain in table]
            lines += [shlex.join(["-A", chain] + rule) for chain, rules in table.items() for rule in rules]
            return "\n".join(lines)
        assert argv[0].endswith("-restore") and "--noflush" in argv
        if "--test" in argv:
            if family == self.fail_test_family:
                raise RuntimeError("simulated IPv6 extension failure")
            return ""
        table = None
        for line in data.splitlines():
            if line.startswith("*"):
                table = self.state[family][line[1:]]
            elif line == "COMMIT":
                continue
            else:
                op, chain, *rule = shlex.split(line)
                assert op in {"-N", "-F", "-A", "-I", "-D", "-X"}
                if op in {"-N", "-F", "-X"}:
                    assert chain.startswith("SKY-WBACK-")
                if op in {"-N", "-F"}:
                    table[chain] = []
                elif op == "-X":
                    del table[chain]
                elif op == "-D":
                    table[chain].remove(rule)
                elif op == "-A":
                    table[chain].append(rule)
                else:
                    assert rule[0] == "1"
                    table[chain].insert(0, rule[1:])
        return ""


def apply(kernel, candidate=None, operation="apply"):
    return FW.reconcile(candidate or policy(backend=kernel.backend), operation, backend=kernel.backend, run=kernel.run)


@pytest.mark.parametrize("backend", ["legacy", "nf_tables"])
def test_apply_update_audit_and_remove_are_idempotent_and_preserve_existing_policy(backend):
    kernel = Kernel(backend)
    original = deepcopy(kernel.state)
    assert apply(kernel)["changed"]
    assert not apply(kernel)["changed"]
    # Model real iptables-save option reordering/explicit TCP match.
    for family in kernel.state.values():
        for table in family.values():
            for chain, rules in table.items():
                if chain.startswith("SKY-WBACK-"):
                    for rule in rules:
                        if "conntrack" in rule and "--ctorigdst" in rule:
                            idx = rule.index("--ctdir")
                            direction = rule[idx : idx + 2]
                            del rule[idx : idx + 2]
                            rule[-2:-2] = direction
                            rule[2:2] = ["-m", "tcp"]
    assert not apply(kernel)["changed"]
    before = deepcopy(kernel.state)
    kernel.calls = []
    assert apply(kernel, operation="check")["compliant"]
    assert kernel.state == before
    assert not any("restore" in argv[0] for argv, _ in kernel.calls)
    updated = policy(backend=backend, ports=[22602, 22622], sources=["192.0.2.53"])
    assert apply(kernel, updated)["changed"]
    assert not apply(kernel, updated)["changed"]
    assert apply(kernel, operation="remove")["changed"]
    assert not apply(kernel, operation="remove")["changed"]
    assert kernel.state == original


def test_both_families_tested_before_any_mutation_and_backend_is_never_switched():
    kernel = Kernel()
    kernel.fail_test_family = 6
    original = deepcopy(kernel.state)
    with pytest.raises(RuntimeError):
        apply(kernel)
    assert kernel.state == original
    with pytest.raises(ValueError, match="switching"):
        FW.reconcile(policy(backend="nf_tables"), run=kernel.run)
    assert not any(argv[0] in {"update-alternatives", "nft"} for argv, _ in kernel.calls)


@pytest.mark.parametrize("operation", ["apply", "remove"])
def test_unowned_names_or_jumps_are_not_overwritten(operation):
    kernel = Kernel()
    kernel.state[4]["filter"]["SKY-WBACK-IN"] = []
    original = deepcopy(kernel.state)
    with pytest.raises(ValueError, match="collision"):
        apply(kernel, operation=operation)
    assert kernel.state == original
    del kernel.state[4]["filter"]["SKY-WBACK-IN"]
    apply(kernel)
    kernel.state[4]["filter"]["INPUT"].append(["-j", "SKY-WBACK-IN"])
    original = deepcopy(kernel.state)
    with pytest.raises(ValueError, match="reference"):
        apply(kernel, operation=operation)
    assert kernel.state == original


def test_docker_restart_earlier_accepts_and_new_addresses_are_reconciled():
    kernel = Kernel()
    apply(kernel)
    for family in kernel.state.values():
        family["filter"]["DOCKER-USER"] = []
        family["filter"]["FORWARD"].insert(0, ["-j", "ACCEPT"])
    kernel.addresses.append("2001:db8::99")
    assert not apply(kernel, operation="check")["compliant"]
    assert apply(kernel)["changed"]
    assert apply(kernel, operation="check")["compliant"]
    for family in kernel.state.values():
        assert family["filter"]["FORWARD"][0][-1] == "SKY-WBACK-FWD"
        assert family["filter"]["DOCKER-USER"][0][-1] == "SKY-WBACK-FWD"


def verdict(table, chain, packet, locals_):
    """Interpret the emitted matches to test paths rather than implementation text."""
    for rule in table[chain]:
        pairs = dict(zip(rule[::2], rule[1::2], strict=True))
        if "-i" in pairs and packet["interface"] != pairs["-i"]:
            continue
        if "-s" in pairs and packet["source"] != pairs["-s"]:
            continue
        if "-p" in pairs and packet["protocol"] != pairs["-p"]:
            continue
        if "--dst-type" in pairs and packet["destination"] not in locals_:
            continue
        if "--ctdir" in pairs and packet["direction"] != pairs["--ctdir"]:
            continue
        if "--ctstate" in pairs and not packet["dnat"]:
            continue
        if "--ctorigdst" in pairs and packet["original_destination"] != pairs["--ctorigdst"]:
            continue
        unmatched = False
        for flag, field in [("--dport", "port"), ("--ctorigdstport", "original_port")]:
            if flag in pairs:
                bounds = [int(number) for number in pairs[flag].split(":")]
                if not bounds[0] <= packet[field] <= bounds[-1]:
                    unmatched = True
        if unmatched:
            continue
        target = pairs["-j"]
        if target in {"ACCEPT", "DROP", "RETURN"}:
            return target
        nested = verdict(table, target, packet, locals_)
        if nested != "RETURN":
            return nested
    return "RETURN"


def packet(**overrides):
    return {
        "source": "192.0.2.99",
        "destination": "192.0.2.20",
        "port": 22622,
        "original_destination": "192.0.2.20",
        "original_port": 22622,
        "direction": "ORIGINAL",
        "protocol": "tcp",
        "interface": "eth0",
        "dnat": False,
        **overrides,
    }


def path_verdict(kernel, request, forwarding=False):
    family = 6 if ":" in request["source"] else 4
    tables = kernel.state[family]
    pre = verdict(tables["mangle"], "PREROUTING", request, kernel.addresses)
    if pre == "DROP":
        return pre
    post = dict(request)
    if forwarding:
        post.update(destination="172.18.0.2" if family == 4 else "2001:db8:1::2", port=9115, dnat=True)
    return verdict(tables["filter"], "FORWARD" if forwarding else "INPUT", post, kernel.addresses)


@pytest.mark.parametrize("forwarding", [False, True])
@pytest.mark.parametrize("destination", ["192.0.2.20", "192.0.2.21", "100.64.0.20", "2001:db8::20", "fe80::20"])
def test_remote_denied_all_host_addresses_before_existing_accepts(forwarding, destination):
    kernel = Kernel()
    apply(kernel)
    v6 = ":" in destination
    assert (
        path_verdict(
            kernel,
            packet(source="2001:db8::99" if v6 else "192.0.2.99", destination=destination, original_destination=destination),
            forwarding,
        )
        == "DROP"
    )
    if not v6:
        assert (
            path_verdict(kernel, packet(source="192.0.2.48", destination=destination, original_destination=destination), forwarding)
            == "ACCEPT"
        )
    # Test the post-DNAT safety net independently, including established
    # ORIGINAL direction traffic: there is deliberately no established bypass.
    post = packet(
        source="2001:db8::99" if v6 else "192.0.2.99", destination="172.18.0.2", port=9115, original_destination=destination, dnat=True
    )
    assert verdict(kernel.state[6 if v6 else 4]["filter"], "FORWARD" if forwarding else "INPUT", post, kernel.addresses) == "DROP"


def test_verified_ipv6_override_and_reply_local_unrelated_paths_are_preserved():
    kernel = Kernel()
    apply(kernel, policy(sources=["192.0.2.48", "2001:db8::48"]))
    assert (
        path_verdict(kernel, packet(source="2001:db8::48", destination="2001:db8::20", original_destination="2001:db8::20"), True)
        == "ACCEPT"
    )
    assert path_verdict(kernel, packet(direction="REPLY"), True) == "ACCEPT"
    assert path_verdict(kernel, packet(interface="lo")) == "ACCEPT"
    for protocol, port in [
        ("tcp", 22),
        ("udp", 53),
        ("tcp", 2377),
        ("udp", 4789),
        ("tcp", 32400),
        ("tcp", 5432),
        ("tcp", 8181),
        ("tcp", 22000),
    ]:
        assert path_verdict(kernel, packet(protocol=protocol, port=port, original_port=port), True) == "ACCEPT"
    # A newly assigned host address is protected immediately by addrtype LOCAL,
    # even before the next reconciliation populates conntrack address matches.
    kernel.addresses.append("192.0.2.25")
    assert path_verdict(kernel, packet(destination="192.0.2.25", original_destination="192.0.2.25"), True) == "DROP"


@pytest.mark.integration
@pytest.mark.parametrize(
    ("argv", "tag", "check"),
    [
        (["install", "worker-backend-firewall"], "install", False),
        (["update", "worker-backend-firewall"], "install", False),
        (["check", "worker-backend-firewall"], "install", True),
        (["run", "worker-backend-firewall", "check"], "check", False),
        (["remove", "worker-backend-firewall"], "remove", False),
        (["check", "worker-backend-firewall", "remove"], "remove", True),
    ],
)
def test_skynet_routes_firewall_only_to_isolated_playbook(tmp_path, argv, tag, check):
    defaults = yaml.safe_load((ROOT / "ansible/roles/workstation/defaults/main.yml").read_text())
    variables = {key: str(tmp_path / key) for key in defaults}
    variables["workstation_ansible_path"] = str(tmp_path / "ansible")
    rendered = (
        Environment(undefined=StrictUndefined)
        .from_string((ROOT / "ansible/roles/workstation/templates/skynet.j2").read_text())
        .render(**variables)
    )
    wrapper = tmp_path / "skynet"
    wrapper.write_text(rendered)
    assert subprocess.run(["bash", "-n", str(wrapper)], capture_output=True).returncode == 0
    recorder = tmp_path / "recorder"
    recorder.write_text('#!/bin/bash\nprintf "%s\\n" "$@" > "$RECORD"\n')
    recorder.chmod(0o755)
    output = tmp_path / "args"
    env = {
        **os.environ,
        "PLAYBOOK": str(tmp_path / "ansible/playbook.yml"),
        "ANSIBLE_PLAYBOOK_BIN": str(recorder),
        "RECORD": str(output),
        "ANSIBLE_LOG_PATH": str(tmp_path / "log"),
        "BECOME_PASS_FILE": str(tmp_path / "absent"),
        "VAULT_PASS_FILE": str(tmp_path / "absent"),
        "REPO_ROOT": str(tmp_path),
    }
    result = subprocess.run(["bash", str(wrapper), "limit", "media", *argv], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    args = output.read_text().splitlines()
    assert str(tmp_path / "ansible/operations.yml") in args
    assert str(tmp_path / "ansible/playbook.yml") not in args
    assert args[args.index("--tags") + 1] == f"worker_backend_firewall_{tag}"
    assert args[args.index("--limit") + 1] == "media"
    assert ("--check" in args) is check
    result = subprocess.run(["bash", str(wrapper), "check", "homepage"], env=env, capture_output=True, text=True)
    assert result.returncode == 0
    assert str(tmp_path / "ansible/playbook.yml") in output.read_text().splitlines()


@pytest.mark.integration
@pytest.mark.parametrize(
    ("operation", "confirmation", "check_mode", "sources", "success", "malformed_catalog"),
    [
        ("install", None, False, ["192.0.2.48"], False, False),
        ("install", False, False, ["192.0.2.48"], False, False),
        ("install", "true", False, ["192.0.2.48"], False, False),
        ("install", True, False, ["192.0.2.0/24"], False, False),
        ("install", False, True, ["192.0.2.48"], True, False),
        ("install", "true", True, ["192.0.2.48"], False, False),
        ("remove", None, True, None, True, False),
        ("remove", None, False, None, True, False),
        ("install", False, True, ["192.0.2.48"], False, True),
    ],
)
def test_actual_ansible_guards_planning_and_recovery_are_local_and_do_not_deploy(
    tmp_path,
    operation,
    confirmation,
    check_mode,
    sources,
    success,
    malformed_catalog,
):
    binary = Path(sys.executable).with_name("ansible-playbook")
    if not binary.is_file():
        pytest.skip("repository Ansible environment unavailable")
    # Execute the real role task flow with deterministic platform probes. The
    # operation includes are replaced by harmless sentinels, so a broken guard
    # can never execute a live firewall command even outside --check.
    tasks = yaml.safe_load((ROLE / "tasks/workers/main.yml").read_text())
    tasks = [task for task in tasks if "ansible.builtin.setup" not in task and "ansible.builtin.stat" not in task]
    (tmp_path / "install.yml").write_text(
        yaml.safe_dump(
            [
                {
                    "name": "Installation sentinel must never run",
                    "ansible.builtin.fail": {"msg": "live installation reached"},
                }
            ]
        )
    )
    (tmp_path / "remove.yml").write_text(
        yaml.safe_dump(
            [
                {
                    "name": "Recovery does not require catalog or source inputs",
                    "ansible.builtin.debug": {"msg": "recovery reached"},
                }
            ]
        )
    )
    service_dir = tmp_path / "group_vars/all/services"
    service_dir.mkdir(parents=True)
    (service_dir / "README.md").write_text("# Service catalog\n\nDocumentation accompanies the service YAML files.\n")
    declarations = {key: catalog()[key] for key in ["tautulli", "blackbox_exporter"]}
    for service in declarations.values():
        service["environment"] = {"POISON": "{{ lookup('must_never_be_evaluated') }}"}
    if operation != "remove":
        (service_dir / "declarations.yml").write_text(yaml.safe_dump(declarations))
    if malformed_catalog:
        (service_dir / "malformed.yml").write_text("malformed: [unterminated\n")
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
    variables = {
        "services_controller_host": "manager",
        "services_storage_host": "storage",
        "services_plex_host": "media",
        "worker_backend_firewall_operation": operation,
        "worker_backend_firewall_sources_verified": confirmation,
        "worker_backend_firewall_source_addresses": sources,
        "worker_backend_firewall_unraid": {"stat": {"exists": False}},
        "ansible_facts": {
            "distribution": "Ubuntu",
            "distribution_version": "24.04",
            "service_mgr": "systemd",
            "python": {"executable": "/usr/bin/python3", "version": {"major": 3, "minor": 12}},
        },
    }
    playbook = [{"name": "Local role safety harness", "hosts": "media", "gather_facts": False, "vars": variables, "tasks": tasks}]
    (tmp_path / "playbook.yml").write_text(yaml.safe_dump(playbook, sort_keys=False))
    cfg = tmp_path / "ansible.cfg"
    cfg.write_text(
        f"[defaults]\naction_plugins={ROOT}/ansible/action_plugins\nlibrary={ROOT}/ansible/library\n"
        # Exercise the explicit namespaced loader, rather than let automatic
        # group_vars discovery parse a malformed fixture before that task runs.
        "vars_plugins_enabled=\nstdout_callback=default\nretry_files_enabled=False\n[inventory]\nenable_plugins=yaml\n"
    )
    argv = [str(binary), "-i", str(tmp_path / "inventory.yml"), str(tmp_path / "playbook.yml")]
    if check_mode:
        argv += ["--check", "--diff"]
    result = subprocess.run(
        argv, capture_output=True, text=True, env={**os.environ, "ANSIBLE_CONFIG": str(cfg), "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local")}
    )
    assert (result.returncode == 0) is success, result.stdout + result.stderr
    if malformed_catalog:
        assert "malformed.yml" in result.stdout + result.stderr
    assert "live installation reached" not in result.stdout
    assert "must_never_be_evaluated" not in result.stdout
    if success:
        assert "changed=0" in result.stdout
        if operation == "remove" and not check_mode:
            assert "recovery reached" in result.stdout
    # No application role, runtime adapter or environment resolution is invoked.
    assert not (tmp_path / "mutated").exists()


@pytest.mark.integration
@pytest.mark.parametrize("platform", ["unraid", "invalid-boot", "ubuntu"])
def test_install_checks_boot_script_before_policy_writer(tmp_path, platform):
    from ansible_task_cases import walk_tasks

    tasks = yaml.safe_load((ROLE / "tasks/workers/install.yml").read_text())
    go = tmp_path / "go"
    if platform != "ubuntu":
        go.write_text("#!/bin/bash\n# Keep existing startup\n" if platform == "unraid" else "not a shell boot script\n")
    # Execute the complete install entry with only its external I/O replaced:
    # version commands are inert binaries, boot reads use a private fixture,
    # policy writes and platform persistence stop at local sentinels.
    for task in walk_tasks(tasks):
        if task.get("ansible.builtin.stat", {}).get("path") == "/boot/config/go":
            task["ansible.builtin.stat"]["path"] = str(go)
        if task.get("ansible.builtin.slurp", {}).get("src") == "/boot/config/go":
            task["ansible.builtin.slurp"]["src"] = str(go)
    backend = "nf_tables" if platform == "ubuntu" else "legacy"
    binaries = tmp_path / "bin"
    binaries.mkdir()
    for tool in ("iptables", "ip6tables", "iptables-restore", "ip6tables-restore"):
        program = binaries / tool
        program.write_text(f"#!/bin/sh\necho 'NONPRODUCTION ({backend})'\n")
        program.chmod(0o700)
    actions = tmp_path / "actions"
    actions.mkdir()
    (actions / "service_firewall_lifecycle.py").write_text(
        "from pathlib import Path\nfrom ansible.plugins.action import ActionBase\n"
        "class ActionModule(ActionBase):\n"
        "    def run(self, tmp=None, task_vars=None):\n"
        "        assert self._task.args['phase'] == 'install'\n"
        "        assert self._task.args['profile'] == 'workers'\n"
        "        Path(task_vars['fixture_writer']).touch()\n"
        "        return {'changed': False}\n"
    )
    for name in ("systemd", "unraid"):
        (tmp_path / f"{name}.yml").write_text("- ansible.builtin.debug:\n    msg: NONPRODUCTION persistence boundary\n")
    writer = tmp_path / "writer-reached"
    play = [
        {
            "name": "Isolated install preflight",
            "hosts": "localhost",
            "connection": "local",
            "gather_facts": False,
            "environment": {"PATH": str(binaries)},
            "vars": {
                "ansible_python_interpreter": sys.executable,
                "worker_backend_firewall_backend": backend,
                "worker_backend_firewall_unraid": {"stat": {"exists": platform != "ubuntu"}},
                "worker_backend_firewall_policy": {},
                "fixture_writer": str(writer),
            },
            "tasks": tasks,
        }
    ]
    (tmp_path / "play.yml").write_text(yaml.safe_dump(play, sort_keys=False))
    config = tmp_path / "ansible.cfg"
    config.write_text(f"[defaults]\naction_plugins={actions}\nvars_plugins_enabled=\n[inventory]\nenable_plugins=host_list\n")
    result = subprocess.run(
        [str(Path(sys.executable).with_name("ansible-playbook")), "-i", "localhost,", str(tmp_path / "play.yml")],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "ANSIBLE_CONFIG": str(config), "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local")},
    )
    assert (result.returncode == 0) is (platform != "invalid-boot"), result.stdout + result.stderr
    assert writer.exists() is (platform != "invalid-boot")
    if platform == "invalid-boot":
        assert "Preserve and inspect the existing Unraid go script" in result.stdout
    if platform == "ubuntu":
        assert not go.exists()


def test_check_cli_creates_no_state_directory_or_lock(tmp_path, monkeypatch, capsys):
    config = tmp_path / "policy.json"
    config.write_text(json.dumps(policy()))
    kernel = Kernel()
    apply(kernel)
    run_dir = tmp_path / "must-not-be-created"
    monkeypatch.setattr(FW, "RUN", run_dir)
    real_reconcile = FW.reconcile
    monkeypatch.setattr(FW, "reconcile", lambda *args, **kwargs: real_reconcile(*args, **{**kwargs, "run": kernel.run}))
    monkeypatch.setattr(FW.sys, "argv", ["policy.py", "check", "--config", str(config)])
    before = config.stat().st_mtime_ns
    FW.main()
    assert json.loads(capsys.readouterr().out)["compliant"]
    assert not run_dir.exists()
    assert config.stat().st_mtime_ns == before


def test_unraid_singleton_start_stop_and_recovery_do_not_signal_other_processes(tmp_path, monkeypatch, capsys):
    config = tmp_path / "policy.json"
    config.write_text(json.dumps(policy()))
    kernel = Kernel()
    monkeypatch.setattr(FW, "RUN", tmp_path / "run")
    real_reconcile = FW.reconcile
    monkeypatch.setattr(FW, "reconcile", lambda *args, **kwargs: real_reconcile(*args, **{**kwargs, "run": kernel.run}))
    watcher = {"active": False, "spawns": 0}

    def spawn(argv, **kwargs):
        assert argv[2] == "watch"
        assert kwargs["start_new_session"]
        watcher.update(active=True, spawns=watcher["spawns"] + 1)

    def is_watching():
        if (FW.RUN / "stop").exists():
            watcher["active"] = False
        return watcher["active"]

    monkeypatch.setattr(FW.subprocess, "Popen", spawn)
    monkeypatch.setattr(FW, "watching", is_watching)
    monkeypatch.setattr(FW.time, "sleep", lambda _: None)
    for expected in [True, False]:
        monkeypatch.setattr(FW.sys, "argv", ["policy.py", "start", "--config", str(config)])
        FW.main()
        assert json.loads(capsys.readouterr().out)["changed"] is expected
    assert watcher["spawns"] == 1
    monkeypatch.setattr(FW.sys, "argv", ["policy.py", "stop-watch"])
    FW.main()
    assert json.loads(capsys.readouterr().out)["changed"]
    assert not watcher["active"]
    assert apply(kernel, operation="check")["compliant"]  # stopping watch does not reopen backends
    config.unlink()  # Removal works even without installed config.
    monkeypatch.setattr(FW.sys, "argv", ["policy.py", "remove", "--backend", "legacy"])
    FW.main()
    assert json.loads(capsys.readouterr().out)["changed"]
    assert not any(chain.startswith("SKY-WBACK-") for family in kernel.state.values() for table in family.values() for chain in table)


def test_persistence_hooks_and_operation_includes_preserve_boundaries():
    main = yaml.safe_load((ROLE / "tasks/workers/main.yml").read_text())
    operation = next(task for task in main if task.get("ansible.builtin.include_tasks"))
    assert operation["when"] == "not ansible_check_mode"
    assert set(operation["ansible.builtin.include_tasks"]["apply"]["tags"]) == {
        "worker_backend_firewall_install",
        "worker_backend_firewall_check",
        "worker_backend_firewall_remove",
    }
    install = yaml.safe_load((ROLE / "tasks/workers/install.yml").read_text())
    apply_idx = next(idx for idx, task in enumerate(install) if task.get("service_firewall_lifecycle", {}).get("phase") == "install")
    persistence_idx = next(idx for idx, task in enumerate(install) if task.get("ansible.builtin.include_tasks"))
    assert apply_idx < persistence_idx
    dropin = (ROLE / "templates/workers/docker-ordering.conf.j2").read_text()
    assert "Before=" not in dropin
    assert "After=skynet-worker-backend-firewall.service" in dropin
    assert "ExecStartPre=" in dropin and "ExecStartPost=" in dropin
    service = (ROLE / "templates/workers/skynet-worker-backend-firewall.service.j2").read_text()
    assert "Before=docker.service" in service
    assert "ExecStop=" not in service  # stopping a unit does not reopen backends
    unraid = yaml.safe_load((ROLE / "tasks/workers/unraid.yml").read_text())
    boot = next(task["ansible.builtin.blockinfile"] for task in unraid if "ansible.builtin.blockinfile" in task)
    assert boot["marker"] == "# {mark} SKYNET WORKER BACKENDS"
    assert "user.scripts" not in str(unraid)
    for path in ROLE.rglob("*.yml"):
        tasks = yaml.safe_load(path.read_text())
        if isinstance(tasks, list):
            for task in tasks:
                unit = task.get("ansible.builtin.systemd_service", {})
                assert not (unit.get("name") == "docker" and unit.get("state") == "restarted")


def test_allowed_sources_are_narrowly_accepted_with_existing_default_deny():
    kernel = Kernel()
    for family in kernel.state.values():
        family["filter"]["INPUT"] = [["-j", "DROP"]]
        family["filter"]["FORWARD"] = [["-j", "DROP"]]
    apply(kernel)
    for forwarding in [True, False]:
        assert path_verdict(kernel, packet(source="192.0.2.48"), forwarding) == "ACCEPT"
        assert path_verdict(kernel, packet(source="192.0.2.99"), forwarding) == "DROP"
        assert path_verdict(kernel, packet(source="192.0.2.48", port=22, original_port=22), forwarding) == "DROP"


@pytest.mark.integration
def test_native_unraid_boot_block_is_early_idempotent_and_removable(tmp_path):
    binary = Path(sys.executable).with_name("ansible-playbook")
    if not binary.is_file():
        pytest.skip("repository Ansible environment unavailable")
    go = tmp_path / "go"
    original = "#!/bin/bash\n# Keep existing admin startup\n/usr/local/sbin/emhttp &\ncat <<'EOF'\n#!/bin/sh\nEOF\n"
    go.write_text(original)
    task = next(task for task in yaml.safe_load((ROLE / "tasks/workers/unraid.yml").read_text()) if "ansible.builtin.blockinfile" in task)
    task["ansible.builtin.blockinfile"]["path"] = str(go)
    path = tmp_path / "playbook.yml"
    cfg = tmp_path / "ansible.cfg"
    cfg.write_text("[defaults]\nstdout_callback=default\n[inventory]\nenable_plugins=host_list\n")

    def run(candidate):
        path.write_text(
            yaml.safe_dump(
                [
                    {
                        "name": "Local boot block harness",
                        "hosts": "localhost",
                        "connection": "local",
                        "gather_facts": False,
                        "tasks": [candidate],
                    }
                ],
                sort_keys=False,
            )
        )
        result = subprocess.run(
            [str(binary), "-i", "localhost,", str(path)],
            capture_output=True,
            text=True,
            env={**os.environ, "ANSIBLE_CONFIG": str(cfg), "ANSIBLE_LOCAL_TEMP": str(tmp_path / "local")},
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    assert "changed=1" in run(task)
    first = go.read_text()
    assert first.index("SKYNET WORKER BACKENDS") < first.index("/usr/local/sbin/emhttp")
    assert "changed=0" in run(task)
    assert go.read_text() == first
    removal = deepcopy(task)
    removal["ansible.builtin.blockinfile"].pop("block")
    removal["ansible.builtin.blockinfile"].pop("insertafter")
    removal["ansible.builtin.blockinfile"]["state"] = "absent"
    assert "changed=1" in run(removal)
    assert "changed=0" in run(removal)
    assert go.read_text() == original


@pytest.mark.parametrize("confirmation", [None, False, "true"])
def test_direct_helper_invalid_confirmation_creates_no_lock_or_state(tmp_path, monkeypatch, confirmation):
    config = tmp_path / "policy.json"
    config.write_text(json.dumps(policy(sources_verified=confirmation)))
    monkeypatch.setattr(FW, "RUN", tmp_path / "must-not-exist")
    monkeypatch.setattr(FW.sys, "argv", ["policy.py", "apply", "--config", str(config)])
    with pytest.raises(ValueError, match="sources_verified"):
        FW.main()
    assert not FW.RUN.exists()


@pytest.mark.parametrize(
    "change",
    [
        {"host": ["storage", "manager"]},
        {"host": ["storage", "storage"]},
        {"host": []},
        {"host": ["storage", "media"], "mode": "replicated"},
        {"host": ["storage", "media"], "type": "container"},
    ],
)
def test_global_worker_publication_rejects_ambiguous_or_non_worker_placement(change):
    service = catalog()["haproxy"]
    service["targets"]["workers"]["deploy"].update(change)
    with pytest.raises(ValueError):
        plan({"haproxy": service})


def test_global_worker_metrics_are_added_without_touching_existing_endpoint_sets():
    services = catalog()
    result = plan(services)
    without = deepcopy(services)
    without["haproxy"]["targets"]["workers"].pop("operational_requirements")
    previous = plan(without)
    for host in ("storage", "media"):
        assert result[host]["ports"] == previous[host]["ports"] + [22623]
        assert [e for e in result[host]["endpoints"] if e["service"] != "haproxy"] == previous[host]["endpoints"]
        assert result[host]["sources"] == previous[host]["sources"]


@pytest.mark.parametrize("backend", ["legacy", "nf_tables"])
@pytest.mark.parametrize("forwarding", [False, True])
def test_worker_metrics_extension_preserves_policy_and_enforces_both_families(backend, forwarding):
    kernel = Kernel(backend)
    original = deepcopy(kernel.state)
    extended = policy(backend=backend, ports=[22601, 22602, 22622, 22623])
    assert apply(kernel, extended)["changed"]
    assert not apply(kernel, extended)["changed"]
    for destination in ("192.0.2.20", "192.0.2.21", "100.64.0.20", "2001:db8::20"):
        request = packet(
            destination=destination,
            original_destination=destination,
            port=22623,
            original_port=22623,
            source="2001:db8::99" if ":" in destination else "192.0.2.99",
        )
        assert path_verdict(kernel, request, forwarding) == "DROP"
    allowed = packet(source="192.0.2.48", port=22623, original_port=22623)
    assert path_verdict(kernel, allowed, forwarding) == "ACCEPT"
    assert apply(kernel, extended, operation="check")["compliant"]
    assert apply(kernel, operation="remove")["changed"]
    assert kernel.state == original


@pytest.mark.parametrize("port", [22624, 8405, True, "22623"])
def test_named_worker_metrics_cannot_escape_allocation_validation(port):
    service = catalog()["haproxy"]
    service["targets"]["workers"]["ports"]["metrics"]["published"] = port
    with pytest.raises(ValueError, match="published port"):
        plan({"haproxy": service})


def test_self_contained_worker_bundle_and_legacy_import_preserve_transactions(tmp_path):
    source = load("ansible/roles/service_firewall/files/bundle.py", "firewall_bundler").bundled_helper("workers")
    bundled = {"__name__": "offline_worker", "__file__": str(tmp_path / "policy.py")}
    exec(compile(source, "isolated_worker_bundle", "exec"), bundled)
    kernel = Kernel()
    original = deepcopy(kernel.state)
    assert bundled["reconcile"](policy(), run=kernel.run)["changed"]
    kernel.calls.clear()
    assert bundled["reconcile"](policy(), "check", run=kernel.run)["compliant"]
    assert not any(argv[0].endswith("-restore") for argv, _ in kernel.calls)
    assert bundled["reconcile"](operation="remove", backend="legacy", run=kernel.run)["changed"]
    assert kernel.state == original
    legacy = load("ansible/roles/worker_backend_firewall/files/worker-backend-firewall.py", "legacy_worker_alias")
    assert legacy.desired_rules(policy(), 4, set(kernel.addresses)) == FW.desired_rules(policy(), 4, set(kernel.addresses))
    # Profiles get separate primitive namespaces, so importing mgt cannot switch worker ownership.
    mgt = load("ansible/roles/mgt_firewall/files/mgt-firewall.py", "legacy_mgt_alias")
    assert mgt.OWNED.MARK == "skynet-mgt-endpoints"
    assert FW.MARK == legacy.MARK == bundled["MARK"] == "skynet-worker-backends"


@pytest.mark.integration
def test_documented_firewall_commands_forward_private_inputs_and_distinguish_audit_from_planning(tmp_path):
    """Run the actual guide's commands through the real wrapper, with inert Ansible."""
    import shlex

    defaults = yaml.safe_load((ROOT / "ansible/roles/workstation/defaults/main.yml").read_text())
    variables = {key: str(tmp_path / key) for key in defaults}
    variables["workstation_ansible_path"] = str(tmp_path / "ansible")
    wrapper = tmp_path / "skynet"
    wrapper.write_text(
        Environment(undefined=StrictUndefined)
        .from_string((ROOT / "ansible/roles/workstation/templates/skynet.j2").read_text())
        .render(**variables)
    )
    recorder = tmp_path / "ansible-recorder"
    recorder.write_text('#!/bin/bash\nprintf "%s\\n" "$@" > "$RECORD"\n')
    recorder.chmod(0o755)
    output = tmp_path / "args"
    env = {
        **os.environ,
        "PLAYBOOK": str(tmp_path / "ansible/playbook.yml"),
        "ANSIBLE_PLAYBOOK_BIN": str(recorder),
        "RECORD": str(output),
        "ANSIBLE_LOG_PATH": str(tmp_path / "log"),
        "REPO_ROOT": str(tmp_path),
        "BECOME_PASS_FILE": str(tmp_path / "absent"),
        "VAULT_PASS_FILE": str(tmp_path / "absent"),
    }
    for key in ["MGT_FIREWALL_PLAYBOOK", "WORKER_BACKEND_FIREWALL_PLAYBOOK", "MGT_FIREWALL_VARS_FILE", "WORKER_BACKEND_FIREWALL_VARS_FILE"]:
        env.pop(key, None)
    guide = (ROOT / "docs/service-firewall.md").read_text().split("```bash\n", 1)[1].split("```", 1)[0]
    for line in guide.splitlines():
        command = shlex.split(line)
        selected_env = env.copy()
        private = None
        if "=" in command[0]:
            key, value = command.pop(0).split("=", 1)
            private = tmp_path / Path(value).name
            private.write_text("{}")
            private.chmod(0o600)
            selected_env[key] = str(private)
        assert command.pop(0) == "skynet"
        result = subprocess.run(["bash", str(wrapper), *command], env=selected_env, capture_output=True, text=True)
        assert result.returncode == 0, line + "\n" + result.stderr
        args = output.read_text().splitlines()
        worker = "worker-backend-firewall" in command
        operation = command[-1] if command[0] == "run" else "install" if command[0] in {"install", "check"} else "remove"
        prefix = "worker_backend_firewall" if worker else "mgt_firewall"
        assert str(tmp_path / "ansible/operations.yml") in args
        assert str(tmp_path / "ansible/playbook.yml") not in args
        assert args[args.index("--tags") + 1] == prefix + "_" + operation
        assert ("--check" in args) == (command[0] == "check")
        if private:
            assert any(args[i : i + 2] == ["-e", "@" + str(private)] for i in range(len(args) - 1))
            assert private.stat().st_mode & 0o777 == 0o600
        else:
            assert not any(arg.startswith("@") for arg in args)


@pytest.mark.integration
@pytest.mark.parametrize("scenario", ["transient", "other-watcher", "repeated-start"])
def test_watcher_start_uses_real_advisory_lock(tmp_path, monkeypatch, capsys, scenario):
    import fcntl
    import sys
    import time
    from types import SimpleNamespace

    config = tmp_path / "policy.json"
    config.write_text(json.dumps(policy()))
    run = tmp_path / "run"
    run.mkdir()
    receipt = tmp_path / "reconciles"
    source = f"""
import importlib.util, os, time
from pathlib import Path
spec=importlib.util.spec_from_file_location('isolated_watcher', {str(ROLE / "files/worker-backend-firewall.py")!r})
fw=importlib.util.module_from_spec(spec);spec.loader.exec_module(fw)
fw.RUN=Path({str(run)!r})
def reconcile(*args, **kwargs):
    with Path({str(receipt)!r}).open('a') as out: out.write(str(os.getpid())+'\\n')
    return {{'changed':False}}
fw.reconcile=reconcile
sleep=time.sleep
fw.time.sleep=lambda seconds: sleep(min(seconds,0.02))
fw.watch({str(config)!r})
"""
    children = []
    popen = subprocess.Popen

    def spawn(*args, **kwargs):
        child = popen([sys.executable, "-c", source], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        children.append(child)
        return child

    def ready():
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if receipt.exists() and receipt.read_text():
                return
            time.sleep(0.01)
        raise AssertionError("isolated watcher never reconciled")

    monkeypatch.setattr(FW, "RUN", run)
    monkeypatch.setattr(FW, "reconcile", lambda *args, **kwargs: {"changed": False})
    try:
        if scenario == "transient":
            with (run / "watch.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                child = spawn()
                time.sleep(0.15)
                assert child.poll() is None and not receipt.exists()
            ready()
        elif scenario == "other-watcher":
            spawn()
            ready()
            second = spawn()
            assert second.wait(timeout=3) == 0
            assert set(receipt.read_text().splitlines()) == {str(children[0].pid)}
        else:
            monkeypatch.setattr(FW, "subprocess", SimpleNamespace(Popen=spawn, DEVNULL=subprocess.DEVNULL))
            for expected in [True, False, False]:
                monkeypatch.setattr(FW.sys, "argv", ["policy.py", "start", "--config", str(config)])
                FW.main()
                assert json.loads(capsys.readouterr().out)["changed"] is expected
            ready()
            assert len(children) == 1
        assert FW.watching()
    finally:
        (run / "stop").touch()
        for child in children:
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=3)
    assert not FW.watching()
