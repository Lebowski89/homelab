#!/usr/bin/env python3
"""Select a compact acceptance plan and execute it serially on one allocation."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import vm


def select(paths=(), broad=False):
    families = set()
    for path in paths:
        if path.endswith(".md"):
            continue
        scenario = next((suite for suite in vm.SUITES if path.startswith(f"molecule/{suite}/")), None)
        if scenario:
            families.add(scenario)
        elif path.startswith(("molecule/", ".config/molecule/", "scripts/testing/", ".github/workflows/vm-tests.yml")):
            families.update(vm.SUITES)
        elif path.startswith("ansible/roles/native_services/") or path.endswith("services/node_exporter.yml"):
            families.add("rocky_node_exporter")
        elif path.startswith(("ansible/roles/docker/", "ansible/roles/podman/")):
            families.update(vm.SUITES[1:])
        elif path.startswith(
            (
                "ansible/roles/docker_services/",
                "ansible/roles/podman_services/",
                "ansible/roles/service_common/",
                "ansible/roles/service_prepare/",
                "ansible/roles/service_firewall/",
                "ansible/action_plugins/",
                "ansible/filter_plugins/",
                "ansible/tasks/",
            )
        ):
            families.update(("application_lifecycle", "protected_network"))
        elif path == "ansible/playbook.yml" or path.startswith("terraform/proxmox/modules/cloudinit-vm/"):
            families.update(vm.SUITES)
    return set(vm.SUITES) if broad else families


def plan(families, platforms):
    result = []
    # The committed pilot is always the first live case when selected.
    for suite in vm.SUITES:
        if suite not in families:
            continue
        for platform in sorted(platforms, key=lambda name: name != "rocky102"):
            variants = [{"order": "docker-first", "runtime": "rootless"}]
            if suite == "runtime_install":
                variants += [{"order": "podman-first", "runtime": "rootless"}]
            elif suite == "application_lifecycle":
                variants = [{"order": "docker-first", "runtime": runtime} for runtime in ("compose", "swarm", "rootful", "rootless")]
            for variant in variants:
                result.append({"suite": suite, "os": platform, **variant})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paths", type=Path, help="Newline-delimited changed paths; no providers are contacted for selection")
    parser.add_argument("--suite", choices=("all", *vm.SUITES), default="all")
    parser.add_argument("--os", choices=("all", *vm.IMAGES), default="all")
    parser.add_argument("--runtime", choices=("compose", "swarm", "rootful", "rootless"), help="Select one application lifecycle variant")
    parser.add_argument("--order", choices=("docker-first", "podman-first"), help="Select one runtime installation order")
    parser.add_argument("--allocation", type=Path)
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--execute", action="store_true", help="Use only on an approved trusted disposable allocation")
    args = parser.parse_args()
    if args.runtime and args.suite != "application_lifecycle":
        parser.error("--runtime requires --suite application_lifecycle")
    if args.order and args.suite != "runtime_install":
        parser.error("--order requires --suite runtime_install")
    families = select(args.paths.read_text().splitlines() if args.paths else (), broad=args.paths is None)
    if args.suite != "all":
        families &= {args.suite}
    cases = plan(families, list(vm.IMAGES) if args.os == "all" else [args.os])
    cases = [
        case for case in cases if (not args.runtime or case["runtime"] == args.runtime) and (not args.order or case["order"] == args.order)
    ]
    if not args.execute:
        print(json.dumps(cases, indent=2))
        return 0
    if not args.allocation or not args.state_root:
        parser.error("--execute requires --allocation and --state-root")
    controller = [sys.executable, str(Path(__file__).with_name("vm.py"))]
    for case in cases:
        if (
            case["os"] == "fedora44"
            and case["suite"] != "rocky_node_exporter"
            and vm.prepared_fedora(args.state_root) is None
            and subprocess.call(
                controller + ["prepare-fedora-image", "--allocation", str(args.allocation), "--state-root", str(args.state_root)]
            )
        ):
            return 1
        command = controller + [
            "prepare",
            "--allocation",
            str(args.allocation),
            "--state-root",
            str(args.state_root),
            "--os",
            case["os"],
            "--suite",
            case["suite"],
            "--order",
            case["order"],
            "--runtime",
            case["runtime"],
        ]
        run = Path(subprocess.check_output(command, text=True).strip())
        print(f"Running {case} in {run}", flush=True)
        for action in ("provision", "test", "retire"):
            command = controller + [action, str(run)]
            if action == "retire":
                command += ["--confirm-run", run.name]
            if subprocess.call(command):
                print(
                    f"Stopped. This run counts against the allocation until retirement is confirmed.\n"
                    f"Retire with: {sys.executable} scripts/testing/vm.py retire {run} --confirm-run {run.name}",
                    file=sys.stderr,
                )
                return 1
            marker = {"provision": "provisioned.json", "test": "result.json", "retire": "retired.json"}[action]
            record = json.loads((run / marker).read_text())
            print(f"  {action}: passed in {record['duration_seconds']} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
