#!/usr/bin/env python3
"""Prove only ZNC's selected user namespace; write a plan, never change data."""

from __future__ import annotations

import json
import os
import re
import shlex
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


class CommandFailure(RuntimeError):
    def __init__(self, operation, status, stderr):
        self.status = status
        self.stderr = stderr.strip()
        super().__init__(f"{operation} failed ({status}): {self.stderr or 'no stderr'}")


def command(argv, *, operation=None, timeout=30):
    result = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=timeout)
    if result.returncode:
        raise CommandFailure(operation or argv[0], result.returncode, result.stderr)
    return result.stdout.strip()


def project():
    # Same collection initialization/inventory API as the existing operator projection.
    from ansible.inventory.manager import InventoryManager
    from ansible.parsing.dataloader import DataLoader
    from ansible.plugins.loader import init_plugin_loader
    from ansible.template import Templar, trust_as_template
    from ansible.vars.manager import VariableManager

    init_plugin_loader()
    loader = DataLoader()
    inventory = InventoryManager(loader=loader, sources=[str(REPO / "ansible/netbox.yml")])
    defaults = loader.load_from_file(str(REPO / "ansible/group_vars/all/services.yml"))
    group = inventory.groups.get(defaults["services_controller_inventory_group"])
    if group is None or len(group.hosts) != 1:
        raise ValueError("require exactly one inventory controller")
    host = group.hosts[0]
    if socket.gethostname().split(".")[0] != host.name:
        raise ValueError("run this local probe on the inventory controller")
    values = VariableManager(loader=loader, inventory=inventory).get_vars(host=host)
    templar = Templar(loader=loader, variables={**values, "services_controller_host": host.name, "hostvars": {host.name: values}})
    service = loader.load_from_file(str(REPO / "ansible/group_vars/all/services/znc.yml"))["znc"]

    def render(value):
        return templar.template(trust_as_template(value)) if isinstance(value, str) else value

    execution = service["deploy"]["execution"]
    if service["runtime"] != "podman" or execution["mode"] != "rootless" or execution["userns"]["mode"] != "keep-id":
        raise ValueError("selected ZNC execution no longer matches this probe")
    result = {
        "inventory_host": host.name,
        "account": render(execution["host_user"]),
        "image": render(service["image"]),
        "user": render(service["user"]),
        "source": render(service["volumes"]["config"]["source"]),
    }
    for key, environment_key in [("uid", "PUID"), ("gid", "PGID")]:
        value = render(execution["userns"][key])
        if not re.fullmatch(r"[0-9]+", str(value)) or isinstance(value, bool) or int(value) >= 2**32 - 1:
            raise ValueError(f"unresolved/invalid selected {key}")
        result[key] = int(value)
        if str(render(service["environment"][environment_key])) != str(value):
            raise ValueError("selected keep-id and application identity differ")
    if result["account"] != "podman-znc" or result["user"] != "0:0" or "@sha256:" not in result["image"]:
        raise ValueError("selected account/process/image contract differs")
    return result


def map_triples(text):
    """Compare kernel namespace maps numerically, without presentation spacing."""
    rows = [tuple(map(int, line.split())) for line in text.splitlines() if line.strip()]
    if not rows or any(len(row) != 3 or min(row) < 0 or row[2] == 0 for row in rows):
        raise ValueError("invalid namespace mapping triples")
    return rows


def mapped(number, text, inverse=False):
    matches = []
    for line in text.splitlines():
        inside, outside, size = map(int, line.split())
        source, target = (outside, inside) if inverse else (inside, outside)
        if source <= number < source + size:
            matches.append(target + number - source)
    if len(matches) != 1:
        raise ValueError(f"identity {number} has no unique namespace translation")
    return matches[0]


def translations(report, selected, uid_map, gid_map):
    identity = json.loads((report / "docker-znc-identity.json").read_text())
    applications = [p for p in identity["processes"] if p["comm"] == "znc"]
    if identity["owner_view"] != "host" or len(applications) != 1:
        raise ValueError("require one observed host-owned ZNC process")
    old_maps = [(report / f"docker-znc.{key}_map").read_text() for key in ["uid", "gid"]]
    old_app = [mapped(applications[0][key], text, inverse=True) for key, text in zip(["uid", "gid"], old_maps, strict=True)]
    records = []
    for block in (report / "znc-ownership.acl").read_text().strip().split("\n\n"):
        lines = block.splitlines()
        if any(line.startswith("default:") or re.match(r"^(user|group):[^:]", line) for line in lines):
            raise ValueError("named/default ACL translation requires separate review")
        fields = dict(line[2:].split(": ", 1) for line in lines if line.startswith(("# file: ", "# owner: ", "# group: ")))
        path = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), fields["file"])
        if ".." in Path(path).parts or not Path(path).is_relative_to(selected["source"]):
            raise ValueError("ownership path escapes the selected configuration tree")
        old = [int(fields[key]) for key in ["owner", "group"]]
        new = []
        for index, key, text in zip(range(2), ["uid", "gid"], [uid_map, gid_map], strict=True):
            old_container = mapped(old[index], old_maps[index], inverse=True)
            if old_container not in {0, old_app[index]}:
                raise ValueError("unreviewed old owner class; do not guess its intended container identity")
            desired = selected[key] if old_container == old_app[index] else 0
            new.append(mapped(desired, text))
        records.append({"path": path, "old": old, "new": new})
    if not records or len({row["path"] for row in records}) != len(records):
        raise ValueError("empty/ambiguous ownership manifest")
    return records


def prove(report, output, selected, *, stage_image=False):
    saved = (report / "account.txt").read_text().strip().split(":")
    current = command(["getent", "passwd", selected["account"]], operation="resolve prepared ZNC account").split(":")
    if current != saved:
        raise ValueError("prepared account identity changed")
    uid, gid = int(current[2]), int(current[3])
    if uid <= 0 or gid <= 0 or not Path(current[5]).is_absolute():
        raise ValueError("prepared rootless account identity is invalid")
    for key in ["uid", "gid"]:
        actual = command(["sudo", "awk", "-F:", '$1 == "podman-znc" {print}', f"/etc/sub{key}"], operation=f"read /etc/sub{key}")
        if actual != (report / f"znc.sub{key}").read_text().strip():
            raise ValueError("prepared subordinate range changed")
    account = [
        "sudo",
        "runuser",
        "-u",
        selected["account"],
        "--",
        "env",
        f"HOME={current[5]}",
        f"XDG_RUNTIME_DIR=/run/user/{uid}",
        f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus",
        "/bin/sh",
        "-c",
        'cd "$HOME" || exit; exec "$@"',
        "skynet-znc-mapping",
        "/usr/bin/podman",
        "--remote=false",
    ]
    print("Checking exact pinned ZNC image in podman-znc's store.", flush=True)
    try:
        command([*account, "image", "exists", selected["image"]], operation="ZNC account image existence check")
    except CommandFailure as error:
        if error.status != 1 or error.stderr:
            raise
        if not stage_image:
            raise RuntimeError(
                "exact pinned ZNC image is absent from podman-znc's store; explicit --stage-image stages only this digest"
            ) from error
        print("Exact image absent; explicitly staging the selected digest in podman-znc's store.", flush=True)
        command([*account, "pull", selected["image"]], operation="stage exact pinned ZNC image", timeout=600)
        command([*account, "image", "exists", selected["image"]], operation="verify staged exact ZNC image")
    name = "skynet-znc-map-" + output.name.replace(".", "-")
    cid = ""
    try:
        cid = command(
            [
                *account,
                "run",
                "--detach",
                "--rm",
                "--pull=never",
                "--network=none",
                "--restart=no",
                "--name",
                name,
                f"--userns=keep-id:uid={selected['uid']},gid={selected['gid']}",
                "--user",
                selected["user"],
                "--entrypoint=/bin/sleep",
                selected["image"],
                "120",
            ],
            operation="start isolated ZNC namespace probe",
        )
        if not re.fullmatch(r"[0-9a-f]{64}", cid):
            raise ValueError("ambiguous probe container identity")

        def inspect():
            return json.loads(
                command(
                    [
                        *account,
                        "container",
                        "inspect",
                        "--format",
                        '{"id":{{json .ID}},"pid":{{json .State.Pid}},"running":{{json .State.Running}}}',
                        cid,
                    ],
                    operation="inspect exact ZNC namespace probe",
                )
            )

        before = inspect()
        if before["id"] != cid or before["running"] is not True or int(before["pid"]) <= 0:
            raise ValueError("probe is not running")
        pid = str(before["pid"])
        birth = command(["sudo", "cat", f"/proc/{pid}/stat"], operation="read probe PID birth").rpartition(") ")[2].split()[19]
        maps = {key: command(["sudo", "cat", f"/proc/{pid}/{key}_map"], operation=f"read probe {key}_map") + "\n" for key in ["uid", "gid"]}
        if (
            inspect() != before
            or command(["sudo", "cat", f"/proc/{pid}/stat"], operation="recheck probe PID birth").rpartition(") ")[2].split()[19] != birth
        ):
            raise ValueError("probe process changed during map observation")
        if mapped(selected["uid"], maps["uid"]) != uid or mapped(selected["gid"], maps["gid"]) != gid:
            raise ValueError("actual keep-id mapping does not map the application identity to its account")
        for key, value in maps.items():
            (output / f"selected.{key}_map").write_text(value)
        rows = translations(report, selected, maps["uid"], maps["gid"])
        (output / "translations.json").write_text(json.dumps(rows, indent=2) + "\n")
        commands = [
            "#!/bin/bash",
            "set -euo pipefail",
            "# Apply only after the old writer stops and consistent backups/manifest review pass.",
        ]
        commands += [
            "sudo chown --no-dereference --from="
            + ":".join(map(str, r["old"]))
            + " "
            + ":".join(map(str, r["new"]))
            + " -- "
            + shlex.quote(r["path"])
            for r in rows
            if r["old"] != r["new"]
        ]
        (output / "ownership-commands.sh").write_text("\n".join(commands) + "\n")
        print(f"Selected mapping proved; {len(rows)} exact paths planned, no ownership changed. Account {uid}:{gid}.", flush=True)
    finally:
        # Never remove by a reused name or touch ZNC's permanent unit/container.
        if re.fullmatch(r"[0-9a-f]{64}", cid):
            command([*account, "rm", "--force", cid], operation="remove exact temporary ZNC probe")


def main():
    os.umask(0o077)
    args = sys.argv[1:]
    if args and args[0] == "--compare-maps":
        if len(args) != 3:
            raise ValueError("usage: znc-mapping-proof.py --compare-maps SAVED OBSERVED")
        if map_triples(Path(args[1]).read_text()) != map_triples(Path(args[2]).read_text()):
            raise ValueError("numeric namespace mappings differ")
        print("Numeric namespace mapping triples match")
        return
    stage_image = bool(args and args[0] == "--stage-image")
    if stage_image:
        args = args[1:]
    if len(args) != 1:
        raise ValueError("usage: znc-mapping-proof.py [--stage-image] PRIVATE_OWNERSHIP_DIRECTORY")
    report = Path(args[0])
    if report.is_symlink() or not report.is_dir() or report.stat().st_uid != os.getuid() or report.stat().st_mode & 0o077:
        raise ValueError("require the supplied private ownership directory")
    output = Path(tempfile.mkdtemp(prefix="selected-map-", dir=report.parent))
    print(f"Private mapping reports: {output}", flush=True)
    selected = project()
    (output / "selected.json").write_text(json.dumps(selected, indent=2) + "\n")
    prove(report, output, selected, stage_image=stage_image)
    print("Ownership acknowledgement remains unset. Docker ZNC and Autobrr destinations are unchanged.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, KeyError, subprocess.TimeoutExpired) as error:
        print(f"ZNC mapping proof: {error}", file=sys.stderr)
        sys.exit(1)
