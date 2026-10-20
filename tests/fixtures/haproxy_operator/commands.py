#!/usr/bin/python3
"""Fail-closed command boundaries for the REAL operator runner and Python helper."""

import hashlib
import importlib.util
import json
import os
import sys
from copy import deepcopy
from pathlib import Path

root = Path(os.environ["FIXTURE_ROOT"])
a = sys.argv[1:]
command = Path(sys.argv[0]).name
state = json.loads((root / "state.json").read_text())
scenario = os.environ.get("SCENARIO", "success")


def save():
    (root / "state.json").write_text(json.dumps(state))


def event(kind, **fields):
    with (root / "journal.jsonl").open("a") as stream:
        stream.write(json.dumps({"kind": kind, **fields}) + "\n")


def output(value):
    if value != "":
        print(value if isinstance(value, str) else json.dumps(value))


def fail(status, message):
    print(message, file=sys.stderr)
    sys.exit(status)


def run(argv):
    event("exec", argv=argv)
    os.execvpe(argv[0], argv, os.environ)


def load(relative, name):
    spec = importlib.util.spec_from_file_location(name, root / "repo" / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


event("command", name=command, argv=a)
if command == "sudo":
    if a[:1] == ["-u"]:
        a = a[a.index("--") + 1 :]
    if a[0] == "env":
        environment = dict(os.environ)
        a = a[1:]
        while a and "=" in a[0]:
            key, value = a.pop(0).split("=", 1)
            environment[key] = value
        os.environ.update(environment)
    if a[0] == "/bin/sh":
        if Path(a[4]).name in ["podman", "systemctl"]:
            a[4] = str(root / "bin" / Path(a[4]).name)
        run(a)
    if "skynet-mgt-operator/mgt-operator.py" in " ".join(a):
        index = next(i for i, v in enumerate(a) if v.endswith("/mgt-operator.py"))
        operation = a[index + 1]
        if operation == "check":
            sys.exit(0)
        if operation == "probe":
            event("native_probe", context=a[index + 2])
            sys.exit(0)
        if operation == "recovery":
            a = a[index + 2 :]
            if "haproxy-policy-rollback.sh" in " ".join(a):
                event("restore_homepage")
                if scenario == "rollback-policy":
                    fail(47, "fixture Homepage restore failed")
                state["policy"] = "homepage"
                save()
                sys.exit(0)
            if Path(a[0]).name == "docker":
                run([str(root / "bin/docker"), *a[1:]])
        fail(99, "unexpected native operation")
    if a[0] == "/usr/bin/python3" and a[1] == "/etc/skynet-mgt-firewall/policy.py":
        output({"compliant": True, "families": [4, 6], "pending": []})
        sys.exit(0)
    if a[:1] == ["cat"] and a[1] in ["/etc/skynet-mgt-firewall/policy.py", "/etc/skynet-mgt-firewall/policy.json"]:
        suffix = "homepage-policy.py" if a[1].endswith(".py") else "homepage-policy.json"
        print(((root / "handoff" / suffix) if a[1].endswith(".py") else (root / "installed-policy.json")).read_text(), end="")
        sys.exit(0)
    if a[:1] == ["cmp"] and a[1].startswith("/etc/skynet-mgt-firewall/"):
        suffix = "homepage-policy.py" if a[1].endswith(".py") else "homepage-policy.json"
        if scenario == "baseline-after-route" and state["excluded"]:
            fail(48, "fixture installed policy changed after worker-route acceptance")
        source = (root / "handoff" / suffix) if a[1].endswith(".py") else (root / "installed-policy.json")
        if Path(a[2]).read_bytes() != source.read_bytes():
            fail(99, "saved pair changed")
        sys.exit(0)
    if a[0] == "install":
        clean = []
        i = 1
        while i < len(a):
            if a[i] in ["-o", "-g"]:
                i += 2
            else:
                clean.append(a[i])
                i += 1
        run(["/usr/bin/install", *clean])
    if Path(a[0]).name in ["podman", "docker"]:
        run([str(root / "bin" / Path(a[0]).name), *a[1:]])
    if a[0] in ["systemctl", "systemd-run", "ss", "nsenter", "ip", "iptables", "iptables-save"]:
        run([str(root / "bin" / a[0]), *a[1:]])
    if a[0] in ["test", "mv"]:
        run(["/usr/bin/" + a[0], *a[1:]])
    if a[0].endswith("/python") or a[0] == "/usr/bin/python3":
        run(a)
    fail(99, "unexpected sudo command")
elif command == "runuser":
    assert a[:2] == ["-u", "podman-forgejo"] and a[2:4] == ["--", "env"]
    a = a[4:]
    while a and "=" in a[0]:
        key, value = a.pop(0).split("=", 1)
        os.environ[key] = value
    if a[0] == "/bin/sh":
        if Path(a[4]).name in ["podman", "systemctl"]:
            a[4] = str(root / "bin" / Path(a[4]).name)
        run(a)
    if a[0] == "/usr/bin/python3":
        run(a)
    fail(99, "unexpected dedicated-account command")
elif command == "getent":
    assert a == ["passwd", "podman-haproxy"]
    output(f"podman-haproxy:x:1011:1011:fixture:{root}/haproxy:/usr/sbin/nologin")
elif command == "sleep":
    sys.exit(0)
elif command == "docker":
    assert a[:2] == ["--host", "unix:///var/run/docker.sock"]
    a = a[2:]
    if a[:2] == ["service", "inspect"]:
        provider = deepcopy(json.loads((root / "provider.json").read_text()))
        if state["excluded"]:
            provider["constraints"].append("node.labels.ansible_host != manager")
        output(provider)
    elif a[:2] == ["node", "inspect"]:
        output("manager")
        if scenario == "node-query-error":
            fail(45, "fixture node inspection failed after output")
    elif a[:2] == ["service", "ps"]:
        output("fixture-task worker Running")
    elif a[:2] == ["service", "update"]:
        if "--constraint-add" in a:
            event("constraint_add")
            if scenario == "placement-no-write":
                fail(31, "fixture placement rejected before write")
            state["excluded"] = True
            state["original_listener"] = scenario.startswith("placement-partial") and scenario != "placement-partial-drained"
            save()
            if scenario.startswith("placement-partial"):
                fail(32, "fixture placement wrote then lost reply")
        elif "--constraint-rm" in a:
            event("constraint_remove")
            if scenario == "rollback-placement-no-write":
                fail(49, "fixture removal failed before write")
            state["excluded"] = False
            state["original_listener"] = True
            save()
            if scenario == "rollback-placement-after-write":
                fail(50, "fixture removal applied then lost reply")
        elif "--force" in a:
            name = a[-1].removeprefix("app_")
            assert name in state["generation"] and name not in ["infisical", "forgejo"]
            event("caller_replace", caller=name)
            state["generation"][name] += 1
            save()
        else:
            fail(99, "unexpected service update")
    elif a[0] == "restart":
        assert a[-1].startswith("infisical-")
        event("caller_replace", caller="infisical")
        state["generation"]["infisical"] += 1
        save()
    elif a[0] == "ps":
        if a == ["ps", "-q"]:
            output("a" * 64)
        elif "label=com.docker.swarm.service.id=fixture-provider" in a:
            output("original-task")
        else:
            label = a[a.index("--filter") + 1]
            if "com.docker.compose.project=" in label:
                assert label == "label=com.docker.compose.project=observed-project"
                assert "label=com.docker.compose.service=infisical" in a
                name = "infisical"
            else:
                name = label.split("=")[-1].removeprefix("app_")
            if name not in state["generation"]:
                fail(99, "unexpected selector")
            output(f"{name}-{state['generation'][name]}")
    elif a[0] == "inspect":
        if a[-1] == "a" * 64:
            mount = {"type": "bind", "source": "/", "destination": "/host/rootfs", "rw": False}
            if scenario == "mount-writable-root":
                mount["rw"] = True
            elif scenario == "mount-missing-rw":
                del mount["rw"]
            elif scenario == "mount-direct-config":
                mount["source"] = str(root / "apps/haproxy/haproxy.cfg")
            output(
                {
                    "id": "a" * 64,
                    "name": "/alloy_alloy.1.fixture",
                    "swarm": "alloy_alloy",
                    "project": None,
                    "service": None,
                    "mounts": [mount],
                }
            )
        elif a[-1] == "original-task":
            output({"pid": 777, "service": "fixture-provider", "addresses": ["198.51.100.200"]})
        else:
            name = a[-1].rsplit("-", 1)[0]
            pid = 100 + list(state["generation"]).index(name) * 10 + state["generation"][name]
            if "{{.State.Pid}}" in a:
                output(str(pid))
            else:
                output(
                    {
                        "pid": pid,
                        "name": name,
                        "swarm": None if name == "infisical" else "app_" + name,
                        "project": "observed-project" if name == "infisical" else None,
                        "service": "infisical" if name == "infisical" else None,
                    }
                )
    else:
        fail(99, "unexpected Docker command")
elif command == "podman":
    assert a.pop(0) == "--remote=false"
    if a[0] == "ps":
        if "name=^forgejo$" in a:
            output("forgejo-current")
        elif scenario == "continue-stopped-container":
            output("haproxy-stopped" if "--all" in a else "")
        else:
            output("haproxy-new" if state["container"] else "")
    elif a[0] == "inspect":
        output(str(900 + state["generation"]["forgejo"]))
    elif a[:2] == ["image", "inspect"]:
        output("sha256:fixture-image-id")
        if scenario == "image-query-error":
            fail(44, "fixture image inspection failed after output")
    elif a[0] == "pull":
        event("image_pull")
    elif a[0] == "tag":
        event("image_tag")
    elif a[0] == "run":
        assert "--rm" in a and "--network=none" in a and "--pull=never" in a
        event("image_validate")
    elif a[0] == "stop":
        assert a[-1] == "haproxy-new"
        event("new_container_stop")
        state["container"] = False
        state["unit_active"] = False
        save()
    else:
        fail(99, "unexpected Podman command")
elif command == "systemctl":
    if a[:1] == ["--user"]:
        a = a[1:]
    unit = next((v for v in a if v.endswith(".service")), None)
    if unit == "docker.service" and a[0] == "is-active":
        output("active")
    elif unit == "forgejo.service" and a[0] == "restart":
        event("caller_replace", caller="forgejo")
        state["generation"]["forgejo"] += 1
        save()
    elif unit == "haproxy.service":
        if a[0] == "show":
            output("loaded" if state["unit"] else "not-found")
        elif a[0] == "stop":
            event("new_unit_stop")
            if scenario == "rollback-unit":
                fail(48, "fixture unit stop failed")
            state["unit_active"] = False
            save()
        elif a[0] == "restart":
            event("haproxy_restart")
        elif a[0] == "status":
            assert state["unit_active"]
        else:
            fail(99, "unexpected HAProxy unit action")
    elif a[0] == "daemon-reload":
        state["unit"] = False
        save()
    elif unit and unit.startswith("skynet-haproxy-acceptance-"):
        if a[0] == "show":
            if "--no-pager" in a:
                if not state["probe"]:
                    output("LoadState=not-found")
                else:
                    fields = {
                        "LoadState": "loaded",
                        "Id": unit,
                        "Transient": "yes",
                        "User": "root",
                        "Slice": "skynet_pg_recovery.slice",
                        "RuntimeMaxUSec": "4min",
                        "MainPID": "888",
                        "ActiveState": "active",
                        "InvocationID": "b" * 32,
                        "ExecStart": "{ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 "
                        + str(root / "handoff/cutover-batch-04-tested/haproxy-cutover.py")
                        + " listen 5432 18405 ; }",
                    }
                    if scenario == "probe-owner-mismatch":
                        fields["User"] = "unrelated"
                    output("\n".join(key + "=" + value for key, value in fields.items()))
            else:
                output("loaded" if state["probe"] else "not-found")
        elif a[0] == "stop":
            event("probe_stop")
            state["probe"] = False
            save()
        elif a[0] == "is-active":
            if not state["probe"]:
                fail(3, "fixture probe expired")
        else:
            fail(99, "unexpected probe unit action")
    else:
        fail(99, "unexpected systemctl")
elif command == "systemd-run":
    assert "--slice=skynet_pg_recovery.slice" in a
    event("probe_start")
    state["probe"] = scenario != "probe-expired"
    save()
elif command == "ss":
    if scenario == "ss-query-error":
        fail(41, "fixture socket inspection failed")
    if scenario == "continue-ipv6-listener" and "-6" in a:
        output("LISTEN 0 4096 [::]:18405 [::]:*")
        sys.exit(0)
    if state["original_listener"] and "5432" in a[-1]:
        if "-Hlnpt" in a:
            port = "18405" if scenario == "placement-partial-extra-port" else "5432"
            output(f'LISTEN 0 4096 0.0.0.0:{port} 0.0.0.0:* users:(("docker-proxy",pid=777,fd=7))')
        else:
            output("LISTEN original 5432")
    elif state["probe"] or state["unit_active"]:
        output("LISTEN new 5432 and 18405")
    else:
        output("")
elif command == "ip":
    if "address" in a:
        output([{"addr_info": [{"local": "192.0.2.48"}]}])
    elif "link" in a:
        output(
            [
                {"ifindex": 7 + index * 10 + generation, "ifname": f"veth{index}g{generation}", "master": "br-fixture"}
                for index, generation in enumerate(state["generation"].values())
            ]
        )
    else:
        fail(99, "unexpected host ip")
elif command == "nsenter":
    pid = int(a[a.index("--target") + 1])
    address = f"198.51.100.{10 + pid - 100}"
    peer = 7 + pid - 100
    if "route" in a:
        output([{"prefsrc": address}])
    elif "address" in a:
        output([{"link_index": peer, "address": f"02:00:00:00:00:{pid - 100:02x}", "addr_info": [{"local": address}]}])
    elif "/usr/bin/python3" in a:
        event("socket_probe", port=a[-1])
        if scenario == "probe-client-error":
            fail(127, "fixture probe client failed")
        if state["probe"] or state["unit_active"]:
            if scenario == "acceptance-failed":
                fail(1, "fixture allowed caller denied")
        else:
            fail(1, "fixture unused port refused")
    else:
        fail(99, "unexpected namespace command")
elif command == "iptables":
    table = a[a.index("-t") + 1]
    action = next(v for v in a if v in ["-I", "-D"])
    index = a.index(action)
    rule = [a[index + 1], *(a[index + 3 :] if action == "-I" else a[index + 2 :])]
    key = json.dumps([table, *rule])
    if action == "-I":
        if scenario == "rule-insert-error" and table == "filter":
            fail(42, "fixture filter insertion failed")
        state["rules"].append(key)
    else:
        if scenario == "rule-delete-error" and table == "filter":
            fail(43, "fixture exact cleanup failed")
        state["rules"].remove(key)
    event("rule_insert" if action == "-I" else "rule_delete", rule=key)
    save()
elif command == "iptables-save":
    table = a[a.index("-t") + 1]
    for encoded in state["rules"]:
        rule = json.loads(encoded)
        if rule[0] == table:
            output("[3:100] -A " + " ".join(rule[1:]))
elif command == "skynet":
    if a[:2] == ["check", "mgt-firewall"]:
        inputs = json.loads(Path(os.environ["MGT_FIREWALL_VARS_FILE"]).read_text())
        stage = json.loads((root / "stage.json").read_text())
        policy = stage["policy"]
        policy["callers"] = inputs["mgt_firewall_callers"]
        policy["inputs_verified"] = inputs["mgt_firewall_inputs_verified"]
        load("ansible/roles/service_firewall/files/mgt-firewall.py", "fixture_policy").validate_policy(policy)
        event("policy_check")
    elif a[:2] == ["update", "mgt-firewall"]:
        event("policy_apply")
        if scenario == "policy-before-write":
            fail(33, "fixture policy rejected before write")
        state["policy"] = "complete"
        save()
        if scenario in ["policy-after-write", "rollback-policy"]:
            fail(34, "fixture policy failed after write")
    elif a[:1] == ["raw"] and "--tags" in a and a[a.index("--tags") + 1] == "deploy,mgt-haproxy":
        inputs = json.loads((root / "handoff/cutover-batch-04-tested/deployment-inputs.json").read_text())
        assert inputs["service_common_postgres_operator_context"] is True
        if "--check" in a:
            event("deployment_check")
        else:
            assert inputs["services_mgt_backend_acl_ready"] is True
            event("deployment")
            if scenario == "continue-interrupt":
                import signal

                os.kill(os.getppid(), signal.SIGTERM)
                fail(143, "fixture deployment interrupted")
            if scenario == "deployment-before-write":
                fail(35, "fixture deployment rejected before write")
            cfg = root / "apps/haproxy"
            cfg.mkdir(parents=True, exist_ok=True)
            (cfg / "haproxy.cfg").write_bytes((root / "handoff/cutover-batch-04-tested/haproxy.cfg").read_bytes())
            if scenario == "deployment-after-config":
                fail(36, "fixture deployment failed after config")
            source = root / "haproxy/.config/containers/systemd"
            source.mkdir(parents=True, exist_ok=True)
            (source / "haproxy.container").write_text("fixture new unit\n")
            state["unit"] = True
            save()
            if scenario == "deployment-after-unit":
                fail(36, "fixture deployment failed after unit")
            state["unit_active"] = True
            state["container"] = True
            save()
            if scenario in ["deployment-after-write", "rollback-unit", "rollback-placement-no-write", "rollback-placement-after-write"]:
                fail(36, "fixture deployment failed after write")
    elif a[:1] == ["raw"]:
        assert a[1:3] == ["--tags", "haproxy_preflight"]
        assert Path(os.environ["PLAYBOOK"]).name == "operations.yml"
        output_path = Path(next(v.split("=", 1)[1] for v in a if v.startswith("haproxy_preflight_output=")))
        stage_path = Path(next(v.split("=", 1)[1] for v in a if v.startswith("haproxy_preflight_stage_output=")))
        stage = json.loads((root / "stage.json").read_text())
        reports = json.loads((root / "reports.json").read_text())
        window = any('"haproxy_preflight_window_seconds":180' in value for value in a)
        selection = next(
            (json.loads(value)["haproxy_preflight_capture_callers"] for value in a if '"haproxy_preflight_capture_callers"' in value), None
        )
        if window and scenario == "capture-command-error":
            fail(53, "host=worker operation=collect: fixture bounded capture failed")
        for report in reports:
            if window:
                report["capture"] = {"complete": True, "seconds": 180, "samples": 3, "callers": selection or ["romm", *state["generation"]]}
            records = report["containers"] + [c for value in report["accounts"].values() for c in value.get("containers", [])]
            for index, record in enumerate(records):
                name = record.get("service") or (record.get("swarm") or "").split("_")[-1] or "forgejo"
                generation = state["generation"].get(name, 0)
                record.update(
                    id="metadata-" + report["host"] + "-" + name + "-" + str(generation),
                    pid=1000 + index + generation * 100,
                    netns="net-" + str(index),
                    start_time=str(10000 + generation),
                    host_network=False,
                )
                if name == "forgejo":
                    record["account"] = "podman-forgejo"
                if window and scenario == "capture-idle" and name == "romm":
                    record["destinations"] = []
                if window and selection and name not in selection:
                    record["destinations"] = []
        capture_arg = next((value.split("=", 1)[1] for value in a if value.startswith("haproxy_preflight_capture_metadata=")), None)
        if window:
            event("capture_window", seconds=180, callers=selection)
        if scenario == "partial-producer":
            stage["policy"]["inventory_address"] = 48
        provider = json.loads((root / "provider.json").read_text())
        for report in reports:
            for service in report["topology"]["services"]:
                if state["excluded"]:
                    service["tasks"] = [t for t in service["tasks"] if t["node_id"] != "manager"]
            if report["host"] == "manager":
                report["providers"] = [] if state["excluded"] else [provider]
        if scenario == "bad-producer":
            for report in reports:
                if report["host"] == "manager":
                    report["providers"][0]["image"] = "docker.io/library/haproxy:INVALID@sha256:" + 64 * "0"
        preflight = load("ansible/roles/service_firewall/files/haproxy-preflight.py", "fixture_preflight")
        accepted = json.loads((root / "accepted.json").read_text())
        result = preflight.candidates(
            {
                "plan": stage["plan"],
                "controller": "manager",
                "workers": ["worker", "media"],
                "existing": accepted,
                "expected_hosts": {r["host"]: {"inventory_address": r["addresses"][0]} for r in reports},
                "collection": [{"haproxy_preflight_host": r["host"], "stdout": json.dumps(r)} for r in reports],
                "capture_reports": json.loads(Path(capture_arg).read_text()) if capture_arg else None,
                "capture_source": {"path": capture_arg, "sha256": hashlib.sha256(Path(capture_arg).read_bytes()).hexdigest()}
                if capture_arg
                else None,
            }
        )
        for path, value in [
            (output_path, result["candidate"]),
            (Path(str(output_path) + ".metadata.json"), result["reports"]),
            (Path(str(output_path) + ".pending.json"), result["pending"]),
            (stage_path, stage),
        ]:
            assert not path.exists()
            path.write_text(json.dumps(value))
            path.chmod(0o600)
        event("collect", output=str(output_path))
    else:
        fail(99, "unexpected skynet")
else:
    fail(99, "unknown fixture command")
