#!/usr/bin/env python3
"""Create and checksum private migration plans without contacting infrastructure."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import stat
import tempfile
from pathlib import Path

import yaml
from ansible.errors import AnsibleFilterError

REPO = Path(__file__).resolve().parents[1]
TEMPLATES = Path(__file__).resolve().parent / "templates"
NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]*\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def module(relative, name):
    spec = importlib.util.spec_from_file_location(name, REPO / relative)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


CATALOG = module("ansible/filter_plugins/service_catalog.py", "migrator_catalog")
TOOLS = module("ansible/operator/utility-preparation.py", "migrator_existing_tools")


def private_directory(path):
    path = Path(path).absolute()
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError("workspace/evidence root must be an operator-owned directory with mode 0700")
    return path


def member(root, relative):
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(part in {".", ".."} for part in path.parts):
        raise ValueError("require a relative file within its declared root")
    current = root
    for part in path.parts:
        current /= part
        if current.is_symlink():
            raise ValueError("symlinked files/directories cannot be sealed or verified")
    if not current.resolve().is_relative_to(root.resolve()):
        raise ValueError("file escapes its declared root")
    return current


def body(path):
    return TOOLS.read_stable_config(path)["body"]


def digest(path):
    return hashlib.sha256(body(path)).hexdigest()


def write(path, value):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(value)


def catalogue(selectors, root=None):
    root = REPO if root is None else root
    services, owners = {}, {}
    directory = root / "ansible/group_vars/all/services"
    for file in sorted(directory.glob("*.yml")):
        try:
            document = yaml.safe_load(body(file))
        except yaml.YAMLError:
            raise ValueError(f"catalogue YAML malformed in {file.name}; source content withheld") from None
        if not isinstance(document, dict):
            raise ValueError("catalogue file must contain a service mapping")
        for name, config in document.items():
            if name in services or not isinstance(config, dict):
                raise ValueError("duplicate service identity or invalid service mapping")
            services[name], owners[name] = config, file.relative_to(root).as_posix()
    selected, sources, identities = [], {}, set()
    for selector in selectors:
        parts = selector.split(":")
        if len(parts) > 2 or not all(NAME.fullmatch(part) for part in parts):
            raise ValueError("use an exact service name or service:target")
        name, target = parts[0], parts[1] if len(parts) == 2 else None
        if name not in services:
            raise ValueError("service is absent from the canonical catalogue")
        targets = services[name].get("targets")
        if targets and target is None:
            raise ValueError("multi-target service requires an explicit service:target; base-name selection is too broad")
        if (name, target) in identities:
            raise ValueError("duplicate migration selection")
        identities.add((name, target))
        try:
            effective = CATALOG.service_catalog_merge_target(services[name], target)
        except AnsibleFilterError:
            raise ValueError("effective service/target is invalid; inspect its declaration locally") from None
        deployment = effective.get("deploy", {})
        if not isinstance(deployment, dict) or effective.get("runtime") not in {"docker", "podman"}:
            raise ValueError("service runtime/deployment declaration is invalid")
        execution = deployment.get("execution", {})
        if not isinstance(execution, dict):
            raise ValueError("execution declaration must be a mapping")
        # Value-limited metadata, never copy arbitrary execution/environment data.
        execution_summary = {key: execution[key] for key in ["mode", "host_user"] if key in execution}
        if "userns" in execution:
            if not isinstance(execution["userns"], dict):
                raise ValueError("user namespace declaration must be a mapping")
            execution_summary["userns"] = {key: execution["userns"][key] for key in ["mode", "uid", "gid"] if key in execution["userns"]}
        selected.append(
            {
                "selector": selector,
                "canonical_runtime": effective.get("runtime"),
                "name": effective.get("name", name),
                "image": effective.get("image"),
                "inventory_host_expression": deployment.get("host"),
                "execution_declaration": execution_summary,
                "operational_requirements": effective.get("operational_requirements", {}),
                "observed_runtime": "not collected; declarations are not runtime evidence",
            }
        )
        sources[owners[name]] = digest(root / owners[name])
    return {"services": selected, "source_files": sources}


def initialize(root, name, selectors, mode="rootless"):
    if not NAME.fullmatch(name) or mode not in {"rootless", "rootful"}:
        raise ValueError("invalid batch name or target execution mode")
    snapshot = catalogue(selectors)
    snapshot["proposed_execution_mode"] = mode
    root = private_directory(root)
    directory = Path(tempfile.mkdtemp(prefix=name + ".", dir=root))
    for name in ["evidence", "backups", "ownership", "firewall", "acceptance", "rollback", "recipes"]:
        (directory / name).mkdir(mode=0o700)
    write(directory / "catalogue.json", json.dumps(snapshot, indent=2) + "\n")
    plan = (TEMPLATES / "PLAN.md").read_text().replace("BATCH_NAME", directory.name)
    write(directory / "PLAN.md", plan)
    for name in ["prepare", "cutover", "rollback"]:
        write(directory / "recipes" / (name + ".sh"), (TEMPLATES / "recipe.sh").read_text())
    return directory


def sealed_sources(directory, additional):
    try:
        snapshot = json.loads(body(member(directory, "catalogue.json")))
    except (ValueError, UnicodeError):
        raise ValueError("catalogue snapshot JSON is invalid; content withheld") from None
    sources = snapshot.get("source_files")
    if not isinstance(sources, dict) or not sources:
        raise ValueError("catalogue snapshot lacks source identities")
    selected = snapshot.get("services")
    if (
        not isinstance(selected, list)
        or not selected
        or any(not isinstance(entry, dict) or not isinstance(entry.get("selector"), str) for entry in selected)
    ):
        raise ValueError("catalogue snapshot lacks exact service selections")
    current = catalogue([entry["selector"] for entry in selected])
    if current["services"] != selected or current["source_files"] != sources:
        raise ValueError("canonical source changed or snapshot differs; create a refreshed workspace")
    for relative, expected in sources.items():
        if not isinstance(expected, str) or not DIGEST.fullmatch(expected) or digest(member(REPO, relative)) != expected:
            raise ValueError("canonical source changed since init; preserve this batch and create a refreshed workspace")
    for relative in ["migrator/migrate.py", "ansible/operator/utility-preparation.py", *additional]:
        sources[relative] = digest(member(REPO, relative))
    return sources


def seal(directory, recipes, additional=()):
    directory = private_directory(directory)
    sources = sealed_sources(directory, additional)
    files = {}
    if any(not relative.startswith("recipes/") for relative in recipes):
        raise ValueError("reviewed recipes must be named explicitly within recipes/")
    for relative in ["PLAN.md", "catalogue.json", *recipes]:
        path = member(directory, relative)
        content = body(path)
        if relative != "catalogue.json" and (not content.strip() or b"TODO:" in content):
            raise ValueError("resolve the plan/recipe TODO placeholders before sealing")
        files[relative] = hashlib.sha256(content).hexdigest()
    if not recipes:
        raise ValueError("name the exact reviewed recipes with --recipe")
    manifest = {"schema": 1, "files": files, "repository_sources": sources, "approval": "checksum integrity only; not execution permission"}
    # Each seal is new; an amendment never overwrites an approved manifest.
    descriptor, filename = tempfile.mkstemp(prefix="manifest-", suffix=".json", dir=directory)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
    return Path(filename), digest(Path(filename))


def verify(directory, manifest, expected):
    directory = private_directory(directory)
    if not DIGEST.fullmatch(expected) or digest(member(directory, manifest)) != expected:
        raise ValueError("manifest differs from the supplied approved SHA256")
    try:
        value = json.loads(body(member(directory, manifest)))
    except (ValueError, UnicodeError):
        raise ValueError("manifest JSON invalid; content withheld") from None
    if value.get("schema") != 1:
        raise ValueError("unsupported migration manifest")
    files = value.get("files")
    if (
        not isinstance(files, dict)
        or not {"PLAN.md", "catalogue.json"} <= files.keys()
        or not any(key.startswith("recipes/") for key in files)
    ):
        raise ValueError("manifest must seal its plan, catalogue and exact recipes")
    for key, root in [("files", directory), ("repository_sources", REPO)]:
        entries = value.get(key)
        if not isinstance(entries, dict) or not entries:
            raise ValueError("manifest lacks plan/recipe/source checksums")
        for relative, checksum in entries.items():
            if not isinstance(checksum, str) or not DIGEST.fullmatch(checksum) or digest(member(root, relative)) != checksum:
                raise ValueError("sealed plan, recipe or repository source changed; stop before execution")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    create = commands.add_parser("init", help="offline private workspace; no inventory, secrets or runtime queries")
    create.add_argument("--name", required=True)
    create.add_argument("--service", action="append", required=True, help="exact canonical name[:target]; repeat for a batch")
    create.add_argument("--evidence-root", type=Path, required=True)
    create.add_argument("--mode", choices=["rootless", "rootful"], default="rootless")
    signing = commands.add_parser("seal", help="checksum reviewed plan and exact recipes; does not approve or execute")
    signing.add_argument("workspace", type=Path)
    signing.add_argument("--recipe", action="append", required=True)
    signing.add_argument("--source", action="append", default=[], help="additional repository-relative helper/role source")
    checking = commands.add_parser("verify", help="read-only check against a separately supplied reviewed manifest SHA256")
    checking.add_argument("workspace", type=Path)
    checking.add_argument("--manifest", required=True, help="manifest filename within the workspace")
    checking.add_argument("--sha256", required=True)
    args = parser.parse_args()
    try:
        if args.action == "init":
            print("Private migration workspace:", initialize(args.evidence_root, args.name, args.service, args.mode))
        elif args.action == "seal":
            path, checksum = seal(args.workspace, args.recipe, args.source)
            print("Manifest:", path)
            print("SHA256:", checksum)
            print("Integrity recorded; operator cutover approval is still required.")
        else:
            verify(args.workspace, args.manifest, args.sha256)
            print("Reviewed plan, recipes and canonical sources match. No live checks or execution performed.")
    except (OSError, ValueError) as error:
        message = str(error) if isinstance(error, ValueError) else "file operation failed; check exact workspace path and permissions"
        parser.exit(1, "migrator: " + message + "\n")


if __name__ == "__main__":
    main()
