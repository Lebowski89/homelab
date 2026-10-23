#!/usr/bin/env python3
"""Utility facts and explicit selected namespace proof; reuse existing mechanisms.

Default collection is read-only. --services selects an existing bounded batch.
--wallos-map / --service-map run only isolated temporary namespace probes;
--stage-image explicitly permits staging the canonical pinned image.
Neither operation changes application ownership, deployment or acknowledgements.
"""

from __future__ import annotations

import argparse
import importlib.util
import ipaddress
import json
import os
import pwd
import re
import socket
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[2]
SERVICES = ("adminer", "thelounge", "wallos")
ALERTING_SERVICES = ("gotify", "alertmanager")
MEDIA_SERVICES = ("autobrr", "seerr")
MONITORING_SERVICES = ("grafana", "scraparr")
RECEIVER_SERVICES = ("loki", "prometheus")
VAULT_SERVICES = ("vaultwarden",)
AUTH_SERVICES = ("authelia", "authelia-redis")
INGRESS_SERVICES = ("traefik",)
NETBOX_SERVICES = ("netbox-postgres", "netbox-redis", "netbox")
INFISICAL_SERVICES = ("infisical-redis", "infisical")
MAPPED_SERVICES = (
    *ALERTING_SERVICES,
    *MEDIA_SERVICES,
    *MONITORING_SERVICES,
    *RECEIVER_SERVICES,
    *VAULT_SERVICES,
    *AUTH_SERVICES,
    *INGRESS_SERVICES,
    *NETBOX_SERVICES,
    *INFISICAL_SERVICES,
)
INSPECT = (
    '{"id":{{json .ID}},"name":{{json .Name}},"image":{{json .Config.Image}},"user":{{json .Config.User}},'
    '"image_id":{{json .Image}},"running":{{json .State.Running}},"pid":{{json .State.Pid}},'
    '"mounts":{{json .Mounts}},"ports":{{json .NetworkSettings.Ports}},'
    '"swarm":{{json (index .Config.Labels "com.docker.swarm.service.name")}},'
    '"project":{{json (index .Config.Labels "com.docker.compose.project")}},'
    '"service":{{json (index .Config.Labels "com.docker.compose.service")}}}'
)
DOCKER = ["sudo", "-n", "/usr/bin/docker", "--host", "unix:///var/run/docker.sock"]


def load(relative, name):
    spec = importlib.util.spec_from_file_location(name, REPO / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def command(argv, operation):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=45, check=False)
    if result.returncode:
        raise RuntimeError(f"{operation} failed ({result.returncode}): {result.stderr.strip()[:1000] or 'no stderr'}")
    return result.stdout.strip()


def write(directory, name, value):
    with (directory / name).open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def read_stable_config(path, limit=4194304):
    """Read one regular file twice, ignoring read-induced atime changes only."""
    path = Path(path)

    def identity(info):
        return {
            key: getattr(info, key)
            for key in ["st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns"]
        }

    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("configuration must be a regular file, not a symlink")
    expected = identity(before)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        if identity(os.fstat(stream.fileno())) != expected:
            raise ValueError("configuration identity changed before reading")
        body = stream.read(limit + 1)
        if len(body) > limit:
            raise ValueError("configuration exceeds bounded read size")
        stream.seek(0)
        if stream.read(limit + 1) != body or identity(os.fstat(stream.fileno())) != expected or identity(path.lstat()) != expected:
            raise ValueError("configuration identity, contents or write metadata changed during reading")
    return {"body": body, "identity": expected}


def destination_metadata(value):
    """Project safe HTTP destination fields, retaining unusable/redacted cases."""
    result = {"scheme": None, "host": None, "port": None, "path": None, "sensitive_components_present": False, "reason": None}
    if not isinstance(value, str) or not value:
        result["reason"] = "URL missing or not textual"
        return result
    if value == "<secret>":
        result["reason"] = "URL redacted; destination unavailable from this projection"
        return result
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            result["reason"] = "absolute HTTP/HTTPS URL with hostname required"
            return result
        if not re.fullmatch(r"[a-zA-Z0-9_.:-]+", parsed.hostname):
            raise ValueError("invalid hostname")
        port = parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else 80)
        if not 1 <= port <= 65535:
            raise ValueError("invalid port")
        result["scheme"], result["host"] = parsed.scheme, parsed.hostname
        result["sensitive_components_present"] = bool(
            parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment
        )
        result["port"] = port
    except ValueError:
        result["reason"] = "URL hostname/port malformed; source withheld"
        return result
    path = parsed.path or "/"
    result["path"] = path if path in {"/", "/metrics", "/message", "/api/v1/alerts", "/api/v2/alerts"} else "(unexpected path withheld)"
    return result


def alertmanager_config_destinations(path):
    """Project current-file webhook destinations; never claim loaded identity."""
    import hashlib

    import yaml

    snapshot = read_stable_config(path)
    try:
        config = yaml.safe_load(snapshot["body"])
    except yaml.YAMLError:
        raise ValueError("configuration YAML malformed; source withheld") from None
    if not isinstance(config, dict) or not isinstance(config.get("receivers"), list):
        raise ValueError("configuration receivers must be a list")
    webhooks = []
    for index, receiver in enumerate(config["receivers"]):
        if not isinstance(receiver, dict) or not isinstance(receiver.get("webhook_configs", []), list):
            raise ValueError("receiver/webhook structure malformed; source withheld")
        for position, webhook in enumerate(receiver.get("webhook_configs", [])):
            if not isinstance(webhook, dict):
                raise ValueError("webhook must be a mapping; source withheld")
            webhooks.append(
                {
                    "receiver_index": index,
                    "webhook_index": position,
                    "url_file_present": bool(webhook.get("url_file")),
                    **destination_metadata(webhook.get("url")),
                }
            )
    if read_stable_config(path) != snapshot:
        raise ValueError("configuration changed during destination projection")
    return {
        "source": "current file; loaded destination not proved",
        "file": str(path),
        "sha256": hashlib.sha256(snapshot["body"]).hexdigest(),
        "webhooks": webhooks,
    }


def qualified_database_handshake(uid, host, address, port):
    """Keep DNS diagnostics separate from account-owned TCP proof; never SQL."""
    if type(uid) is not int or uid <= 0 or os.getuid() != uid:
        raise ValueError("dedicated account UID differs")
    row = {"socket_uid": None, "resolved": [], "destination": [address, port], "sql_proved": False}
    try:
        row["resolved"] = sorted({item[4][0] for item in socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)})
    except socket.gaierror as error:
        row["result"] = "DNS lookup failed"
        row["dns_error"] = {"type": "gaierror", "code": error.errno}
        return row
    if row["resolved"] != [address]:
        row["result"] = "DNS destination differs"
        return row
    native = load("ansible/operator/mgt-operator.py", "qualified_socket_owner")
    stream = socket.socket()
    try:
        stream.settimeout(5)
        try:
            stream.connect((host, port))
            row["result"], row["peer"] = "connected", list(stream.getpeername())
        except OSError as error:
            row["result"] = type(error).__name__
        row["socket_uid"], row["source"] = native.socket_uid(stream), list(stream.getsockname())
    finally:
        stream.close()
    return row


def acl_lines(text):
    """Ignore empty separators, preserving every ACL and identity line."""
    lines = [line for line in text.splitlines() if line != ""]
    count = sum(line.startswith("# file: ") for line in lines)
    if not count or any(sum(line.startswith(prefix) for line in lines) != count for prefix in ["# owner: ", "# group: "]):
        raise ValueError("empty/incomplete numeric ACL manifest")
    return lines


def mounts_by_destination(mounts):
    """Compare complete inspect records independently of Docker's list order."""
    if not isinstance(mounts, list):
        raise ValueError("mount metadata must be a list")
    result = {}
    for mount in mounts:
        if not isinstance(mount, dict):
            raise ValueError("mount record must be a mapping")
        destination, source, kind = [mount.get(key) for key in ["Destination", "Source", "Type"]]
        if not isinstance(destination, str) or not Path(destination).is_absolute() or ".." in Path(destination).parts:
            raise ValueError("mount Destination must be an exact absolute path")
        if destination in result:
            raise ValueError("duplicate mount Destination is ambiguous")
        if not isinstance(kind, str) or not kind or not isinstance(source, str) or type(mount.get("RW")) is not bool:
            raise ValueError("mount Type, Source and boolean RW are required")
        if kind == "bind" and (not Path(source).is_absolute() or ".." in Path(source).parts):
            raise ValueError("bind mount Source must be an exact absolute path")
        if any(key in mount and not isinstance(mount[key], str) for key in ["Mode", "Propagation"]):
            raise ValueError("mount Mode/Propagation metadata must be textual")
        result[destination] = mount
    return result


def validate_runtime(runtime, selected):
    """Validate the runtime projection, allowing Podman's tagless digest form."""
    image = selected["image"]
    if not re.fullmatch(r".+@sha256:[0-9a-f]{64}", image):
        raise ValueError("selected image lacks an immutable sha256 digest")
    repository, digest = image.split("@")
    parent, separator, leaf = repository.rpartition("/")
    tagless = parent + separator + leaf.split(":", 1)[0] + "@" + digest
    if runtime.get("image") not in {image, tagless}:
        raise ValueError("runtime image repository/digest differs from selected image")
    if runtime.get("user") != selected["user"]:
        raise ValueError("runtime process user differs from selected user")
    if not isinstance(runtime.get("id"), str) or not re.fullmatch(r"[0-9a-f]{64}", runtime["id"]):
        raise ValueError("runtime lacks an exact container ID")
    if type(runtime.get("pid")) is not int or runtime["pid"] <= 0 or runtime.get("running") is not True:
        raise ValueError("runtime is not running with a positive PID")
    ports = runtime.get("ports")
    expected = {}
    for port in selected["ports"].values():
        expected.setdefault(f"{port['target']}/{port['protocol']}", []).append(
            {"HostIp": port["host_ip"], "HostPort": str(port["published"])}
        )
    if not isinstance(ports, dict) or {key: value for key, value in ports.items() if value} != expected:
        raise ValueError("runtime publications differ from selected publications")


def validate_runtime_replacement(runtime, selected, reference):
    """Permit lifecycle identities to change while preserving proved artifacts."""
    validate_runtime(runtime, selected)
    if runtime.get("name", "").lstrip("/") != selected["name"]:
        raise ValueError("replacement container name differs from selected service")
    if runtime.get("image_id") != reference.get("image_id") or not runtime.get("image_id"):
        raise ValueError("replacement image artifact differs from verified deployment")
    if mounts_by_destination(runtime.get("mounts")) != mounts_by_destination(reference.get("mounts")):
        raise ValueError("replacement mounts differ from verified deployment")
    mapping = load("ansible/operator/znc-mapping-proof.py", "utility_replacement_maps")
    for key in ("uid", "gid"):
        if mapping.map_triples(runtime["maps"][key]) != mapping.map_triples(reference["maps"][key]):
            raise ValueError(f"replacement {key} mapping differs from verified deployment")


def recorded_quadlet_mask(account, service, record, properties):
    """Validate one retained rollback mask; never accept a general masked unit."""
    import hashlib

    if not re.fullmatch(r"[a-z][a-z0-9_-]*", service):
        raise ValueError("invalid managed unit name")
    home = Path(account["home"])
    source = home / ".config/containers/systemd" / (service + ".container")
    mask = home / ".config/systemd/user" / (service + ".service")
    if record.get("account") != account or record.get("unit") != service + ".service":
        raise ValueError("recorded mask account/unit differs")
    if record.get("source") != str(source) or record.get("masked_for_rollback") is not True:
        raise ValueError("recorded mask source/ownership differs")
    for path in [source, mask]:
        if any(parent.is_symlink() for parent in [path.parent, *path.parents]):
            raise ValueError("managed mask/source ancestor is a symlink")
    info = source.lstat()
    if not stat.S_ISREG(info.st_mode) or (info.st_uid, info.st_gid) != (account["uid"], account["gid"]):
        raise ValueError("managed Quadlet source is not an account-owned regular file")
    if hashlib.sha256(source.read_bytes()).hexdigest() != record.get("source_sha256"):
        raise ValueError("recorded Quadlet source changed")
    info = mask.lstat()
    identity = {key: getattr(info, key) for key in ["st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_ctime_ns"]}
    if not stat.S_ISLNK(info.st_mode) or os.readlink(mask) != "/dev/null":
        raise ValueError("recorded unit is not a /dev/null mask")
    if (info.st_uid, info.st_gid) != (account["uid"], account["gid"]) or identity != record.get("mask_identity"):
        raise ValueError("recorded mask identity/owner changed")
    for base in [
        home / ".config/systemd/user.control",
        Path("/run/user") / str(account["uid"]) / "systemd/user",
        Path("/run/user") / str(account["uid"]) / "systemd/user.control",
    ]:
        other = base / (service + ".service")
        if other.exists() or other.is_symlink():
            raise ValueError("additional unit override/mask is unowned by this record")
    if not (
        properties.get("LoadState") == "masked"
        and properties.get("ActiveState") == "inactive"
        and properties.get("SubState") == "dead"
        and properties.get("FragmentPath") == str(mask)
        and properties.get("SourcePath", "") == ""
    ):
        raise ValueError("recorded masked unit state differs")
    return mask


def release_recorded_quadlet_mask(account, prefix, service, record):
    """Remove only the recorded mask after the caller's stopped-writer guards."""

    def properties():
        text = command(
            [
                *prefix,
                "/usr/bin/systemctl",
                "--user",
                "show",
                service + ".service",
                "-p",
                "LoadState",
                "-p",
                "ActiveState",
                "-p",
                "SubState",
                "-p",
                "FragmentPath",
                "-p",
                "SourcePath",
            ],
            "exact managed unit identity",
        )
        return dict(line.split("=", 1) for line in text.splitlines())

    mask = recorded_quadlet_mask(account, service, record, properties())
    # Recheck filesystem identity immediately before the one exact removal.
    recorded_quadlet_mask(account, service, record, properties())
    mask.unlink()
    command([*prefix, "/usr/bin/systemctl", "--user", "daemon-reload"], "reload only the dedicated user manager")
    current = properties()
    generator = Path("/run/user") / str(account["uid"]) / "systemd/generator"
    fragment = Path(current.get("FragmentPath", ""))
    if not (
        current.get("LoadState") == "loaded"
        and current.get("ActiveState") in {"inactive", "failed"}
        and current.get("SourcePath") == record["source"]
        and fragment.parent == generator
        and fragment.name == service + ".service"
        and not mask.exists()
        and not mask.is_symlink()
    ):
        raise ValueError("unmasked generated unit identity differs; scoped rollback must remask")
    return current


def probe_command(argv, output, phase, *, timeout=30):
    """Retain startup output without waiting for inherited pipe writers."""
    stdout_path, stderr_path = [output / f"probe-{phase}.{suffix}" for suffix in ["stdout", "stderr"]]
    with stdout_path.open("x+") as stdout, stderr_path.open("x+") as stderr:
        try:
            result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, text=True, check=False, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"Namespace probe {phase} timed out after {timeout}s; inspect {stdout_path} and {stderr_path}") from error
        stdout.seek(0)
        stderr.seek(0)
        if result.returncode:
            raise RuntimeError(f"Namespace probe {phase} failed ({result.returncode}): {stderr.read().strip()[:1000] or 'no stderr'}")
        return stdout.read().strip()


def project(services=SERVICES):
    # Established operator inventory initialization. Template only metadata,
    # never service environments or Infisical declarations.
    from ansible.inventory.manager import InventoryManager
    from ansible.parsing.dataloader import DataLoader
    from ansible.plugins.loader import init_plugin_loader
    from ansible.template import Templar, trust_as_template
    from ansible.vars.manager import VariableManager

    init_plugin_loader()
    loader = DataLoader()
    inventory = InventoryManager(loader=loader, sources=[str(REPO / "ansible/netbox.yml")])
    defaults = loader.load_from_file(str(REPO / "ansible/group_vars/all/services.yml"))
    # Resolve only inventory group names. Do not template host credentials or service inputs.
    selector = Templar(
        loader=loader, variables={"groups": {name: [host.name for host in group.hosts] for name, group in inventory.groups.items()}}
    )
    controller_group = selector.template(trust_as_template(defaults["services_controller_inventory_group"]))
    group = inventory.groups.get(controller_group)
    if group is None or len(group.hosts) != 1:
        raise ValueError("require exactly one inventory controller")
    host = group.hosts[0]
    if socket.gethostname().split(".")[0] != host.name:
        raise ValueError("run on the inventory controller")
    values = VariableManager(loader=loader, inventory=inventory).get_vars(host=host)
    bootstrap_role = {NETBOX_SERVICES: "netbox", INFISICAL_SERVICES: "infisical"}.get(tuple(services))
    bootstrap = loader.load_from_file(str(REPO / f"ansible/roles/{bootstrap_role}/defaults/main.yml")) if bootstrap_role else {}
    templar = Templar(
        loader=loader,
        variables={
            **{key: trust_as_template(value) if isinstance(value, str) else value for key, value in bootstrap.items()},
            **values,
            "inventory_hostname": host.name,
            "services_controller_host": host.name,
            "hostvars": {host.name: values},
        },
    )

    def render(value):
        if isinstance(value, dict):
            return {key: render(item) for key, item in value.items()}
        if isinstance(value, list):
            return [render(item) for item in value]
        return templar.template(trust_as_template(value)) if isinstance(value, str) else value

    selected = {}
    for key in services:
        if bootstrap_role:
            matches = [cfg for cfg in bootstrap[f"{bootstrap_role}_podman_services"] if render(cfg["name"]) == key]
            if len(matches) != 1:
                raise ValueError(f"{key}: require one exact bootstrap definition")
            cfg = matches[0]
        elif key in AUTH_SERVICES:
            base = loader.load_from_file(str(REPO / "ansible/group_vars/all/services/authelia.yml"))["authelia"]
            catalog = load("ansible/filter_plugins/service_catalog.py", "utility_effective_targets")
            cfg = catalog.service_catalog_merge_target(base, "main" if key == "authelia" else "redis")
        else:
            cfg = loader.load_from_file(str(REPO / f"ansible/group_vars/all/services/{key}.yml"))[key]
        if cfg.get("targets") or cfg["runtime"] != "podman" or cfg["deploy"]["execution"]["mode"] != "rootless":
            raise ValueError(f"{key}: review changed effective target/execution before collection")
        selected[key] = render(
            {
                "name": cfg["name"],
                "image": cfg["image"],
                "user": cfg.get("user"),
                "host": cfg["deploy"]["host"],
                "execution": cfg["deploy"]["execution"],
                "ports": cfg["ports"],
                "volumes": cfg.get("volumes", {}),
                **(
                    {
                        "templates": [
                            {k: v for k, v in item.items() if k in {"dest", "mode", "owner", "group"}} for item in cfg.get("templates", [])
                        ],
                        "managed_paths": [
                            {k: v for k, v in item.items() if k in {"path", "state", "owner", "group"}} for item in cfg.get("paths", [])
                        ],
                        "host_ids": {"uid": values["container_host_puid"], "gid": values["container_host_pgid"]},
                        "postgres": {
                            k: v
                            for k, v in cfg.get("postgres", {}).items()
                            if k in {"enable", "databases", "host", "host_inventory", "port", "user_var", "password_var"}
                        },
                    }
                    if key in MAPPED_SERVICES
                    else {}
                ),
                "application_ids": {k: v for k, v in cfg.get("environment", {}).items() if k in {"PUID", "PGID"}},
            }
        )
        if any(marker in json.dumps(selected[key]) for marker in ["{{", "{%"]):
            raise ValueError(f"{key}: unresolved metadata; no runtime or ownership collection permitted")
        if selected[key]["host"] != host.name:
            raise ValueError(f"{key}: declaration no longer addresses the controller")
    result = {"host": host.name, "address": str(ipaddress.ip_address(values["local_ip"])), "services": selected}
    if tuple(services) in {
        ALERTING_SERVICES,
        MEDIA_SERVICES,
        MONITORING_SERVICES,
        RECEIVER_SERVICES,
        VAULT_SERVICES,
        AUTH_SERVICES,
        INGRESS_SERVICES,
        NETBOX_SERVICES,
        INFISICAL_SERVICES,
    }:
        zone = values["services_internal_zone"]
        port = values["services_private_https_port"]
        if not isinstance(zone, str) or not re.fullmatch(r"[a-zA-Z0-9.-]+", zone) or not zone.strip("."):
            raise ValueError("invalid inventory internal zone")
        if isinstance(port, bool) or not str(port).isdecimal() or not 1 <= int(port) <= 65535:
            raise ValueError("invalid inventory private HTTPS port")
        result["integrations"] = {"zone": zone, "private_https_port": int(port)}
    if tuple(services) == AUTH_SERVICES:
        result["integrations"]["postgres"] = {
            "authelia": {"driver": "postgres", "host": f"haproxy.{zone}", "port": 5432, "database": "authelia"}
        }
        result["integrations"]["cache"] = {"address": result["address"], "port": selected["authelia-redis"]["ports"]["cache"]["published"]}
        if selected["authelia"]["postgres"].get("enable") is not True or selected["authelia"]["postgres"].get("databases") != ["authelia"]:
            raise ValueError("review changed Authelia database declarations")
    if tuple(services) == VAULT_SERVICES:
        if selected["vaultwarden"]["postgres"].get("enable") is not True or selected["vaultwarden"]["postgres"].get("databases") != [
            "vaultwarden"
        ]:
            raise ValueError("review changed Vaultwarden database declarations")
        refs = {(item["var"], item["path"], item["name"]) for item in cfg["infisical"]["secrets_map"]}
        if not {("postgres_user", "/Postgres", "USER"), ("postgres_pass", "/Postgres", "PASS")} <= refs:
            raise ValueError("Vaultwarden shared PostgreSQL credential declarations changed")
        template = (REPO / "ansible/roles/service_common/templates/configs/vaultwarden.env.j2").read_text()
        expected = "DATABASE_URL=postgresql://{{ postgres_user }}:{{ postgres_pass }}@haproxy.{{ services_internal_zone }}:5432/vaultwarden"
        if template.splitlines().count(expected) != 1:
            raise ValueError("review changed Vaultwarden managed database destination/credential contract")
        result["integrations"]["postgres"] = {
            "vaultwarden": {"driver": "postgres", "host": f"haproxy.{zone}", "port": 5432, "database": "vaultwarden"}
        }
    if tuple(services) == MEDIA_SERVICES:
        # Only value-free declarations; never resolve credentials or project
        # runtime environments. Seerr's managed template is the DB contract.
        result["integrations"]["postgres"] = {
            name: {"driver": "postgres", "host": f"haproxy.{zone}", "port": 5432, "database": name} for name in services
        }
        result["integrations"]["znc"] = {"host": f"znc.{zone}", "port": 16502, "caller": "autobrr"}
        if (
            cfg["postgres"].get("enable") is not True
            or selected["seerr"]["postgres"].get("databases") != ["seerr"]
            or selected["autobrr"]["postgres"].get("databases") != ["autobrr"]
        ):
            raise ValueError("review changed media database declarations")
        autobrr = loader.load_from_file(str(REPO / "ansible/group_vars/all/services/autobrr.yml"))["autobrr"]
        expected = {
            "AUTOBRR__DATABASE_TYPE": "postgres",
            "AUTOBRR__POSTGRES_HOST": f"haproxy.{zone}",
            "AUTOBRR__POSTGRES_PORT": "5432",
            "AUTOBRR__POSTGRES_DATABASE": "autobrr",
        }
        if render({key: autobrr["environment"].get(key) for key in expected}) != expected:
            raise ValueError("review changed Autobrr database destination")
        for name in services:
            definition = loader.load_from_file(str(REPO / f"ansible/group_vars/all/services/{name}.yml"))[name]
            refs = {(item["var"], item["path"], item["name"]) for item in definition["infisical"]["secrets_map"]}
            if not {("postgres_user", "/Postgres", "USER"), ("postgres_pass", "/Postgres", "PASS")} <= refs:
                raise ValueError(f"{name}: shared PostgreSQL credential declarations changed")
        template = (REPO / "ansible/roles/service_common/templates/configs/seerr.env.j2").read_text()
        if not all(
            line in template.splitlines()
            for line in [
                "DB_TYPE=postgres",
                "DB_HOST=haproxy.{{ services_internal_zone }}",
                "DB_PORT=5432",
                "DB_NAME=seerr",
                "DB_USER={{ postgres_user }}",
                "DB_PASS={{ postgres_pass }}",
            ]
        ):
            raise ValueError("review changed Seerr managed database destination/credential contract")
    return result


def account_command(account):
    try:
        entry = pwd.getpwnam(account)
    except KeyError:
        return None, None
    if entry.pw_uid <= 0 or not Path(entry.pw_dir).is_absolute():
        raise ValueError("invalid dedicated account identity/home")
    prefix = [
        "sudo",
        "-n",
        "runuser",
        "-u",
        account,
        "--",
        "env",
        f"HOME={entry.pw_dir}",
        f"XDG_RUNTIME_DIR=/run/user/{entry.pw_uid}",
        f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{entry.pw_uid}/bus",
        "/bin/sh",
        "-c",
        'cd "$HOME" || exit; exec "$@"',
        "skynet-utility-facts",
    ]
    return {"name": account, "uid": entry.pw_uid, "gid": entry.pw_gid, "home": entry.pw_dir}, prefix


def context(pid):
    if type(pid) is not int or pid <= 0:
        raise ValueError("running container lacks a positive PID")
    text = command(["sudo", "-n", "cat", f"/proc/{pid}/stat"], "container birth identity")
    return {
        "pid": pid,
        "birth": text[text.rindex(")") + 2 :].split()[19],
        "netns": command(["sudo", "-n", "readlink", f"/proc/{pid}/ns/net"], "container network namespace"),
    }


def container(prefix, cid, docker=False):
    if not re.fullmatch(r"[0-9a-f]{64}", cid):
        raise ValueError("incomplete container ID")
    template = INSPECT.replace(".ID", ".Id", 1) if docker else INSPECT
    inspect = [*prefix, "container", "inspect", "--format", template, cid]
    result = json.loads(command(inspect, "project exact container metadata"))
    if not isinstance(result, dict) or result.get("id") != cid or type(result.get("running")) is not bool:
        raise ValueError("incomplete/mismatched exact container metadata")
    if not isinstance(result.get("image_id"), str) or not result["image_id"]:
        raise ValueError("missing exact container image identity")
    result["repo_digests"] = json.loads(
        command(
            [*prefix, "image", "inspect", "--format", "{{json .RepoDigests}}", result["image_id"]],
            "running/stopped container image digest metadata",
        )
    )
    if result["running"]:
        before = context(result["pid"])
        result["identity"] = before
        result["maps"] = {
            key: command(["sudo", "-n", "cat", f"/proc/{result['pid']}/{key}_map"], f"read {key} namespace map") for key in ["uid", "gid"]
        }
        if docker:
            table = command([*prefix, "top", cid, "-eo", "pid,uid,gid,comm"], "explicit host process identity projection")
            lines = [line.split(None, 3) for line in table.splitlines() if line.strip()]
            if not lines or lines[0] != ["PID", "UID", "GID", "COMMAND"] or not lines[1:]:
                raise ValueError("missing explicit Docker process identity headers/rows")
            if any(len(row) != 4 or not all(v.isdecimal() for v in row[:3]) for row in lines[1:]):
                raise ValueError("incomplete numeric Docker process identities")
            if not any(int(row[0]) == result["pid"] for row in lines[1:]):
                raise ValueError("container init PID absent from process evidence")
            result["processes"] = [{"pid": int(row[0]), "uid": int(row[1]), "gid": int(row[2]), "comm": row[3]} for row in lines[1:]]
        else:
            pids = command([*prefix, "top", cid, "hpid"], "host process PID projection").splitlines()
            if not pids or pids[0].strip() != "HPID" or not all(p.strip().isdecimal() for p in pids[1:]):
                raise ValueError("missing explicit host process PID evidence")
            result["processes"] = []
            for pid in pids[1:]:
                status = command(["sudo", "-n", "cat", f"/proc/{int(pid)}/status"], "host process numeric identity")
                fields = dict(line.split(":", 1) for line in status.splitlines() if line.startswith(("Name:", "Uid:", "Gid:")))
                result["processes"].append(
                    {
                        "pid": int(pid),
                        "comm": fields["Name"].strip(),
                        "uid": [int(v) for v in fields["Uid"].split()],
                        "gid": [int(v) for v in fields["Gid"].split()],
                    }
                )
        after = json.loads(command(inspect, "recheck exact container metadata"))
        if not after["running"] or after["pid"] != result["pid"] or context(after["pid"]) != before:
            raise ValueError("container PID/birth/network namespace changed during collection")
    return result


def collect(directory, projection):
    plan = load("ansible/action_plugins/mgt_firewall_plan.py", "utility_policy_plan")
    links = json.loads(command(["ip", "-j", "address", "show"], "observed host addresses"))
    if projection["address"] not in {a["local"] for link in links for a in link.get("addr_info", [])}:
        raise ValueError("inventory address absent from observed controller")
    write(
        directory,
        "host.json",
        {
            "hostname": socket.gethostname(),
            "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            "links": links,
            "inventory_address": projection["address"],
        },
    )
    baseline_hash = command(["sudo", "-n", "sha256sum", "/etc/skynet-mgt-firewall/policy.json"], "installed policy hash")
    raw = command(["sudo", "-n", "cat", "/etc/skynet-mgt-firewall/policy.json"], "current installed policy snapshot")
    policy = json.loads(raw)
    if policy["inventory_host"] != projection["host"] or policy["inventory_address"] != projection["address"]:
        raise ValueError("installed policy identity differs from inventory/observed host")
    write(directory, "installed-policy.json", policy)
    with (directory / "installed-policy.sha256").open("x") as stream:
        stream.write(baseline_hash + "\n")
    # Union with the CURRENT policy, preserving confirmations/bindings exactly.
    requested = [
        f"{cfg['name']}/{endpoint}"
        for cfg in projection["services"].values()
        for endpoint in (
            cfg["ports"]
            if frozenset(projection["services"]) in {frozenset(AUTH_SERVICES), frozenset(NETBOX_SERVICES), frozenset(INFISICAL_SERVICES)}
            else (["metrics"] if set(projection["services"]) == set(INGRESS_SERVICES) else ["backend"])
        )
    ]
    inputs = plan.installed_policy_inputs(policy, requested)
    write(directory, "policy-inputs.json", inputs)
    if command([*DOCKER, "info", "--format", "{{.Name}}"], "Docker daemon identity") != projection["host"]:
        raise ValueError("Docker daemon belongs to a different host")
    service_names = command([*DOCKER, "service", "ls", "--format", "{{.Name}}"], "Swarm service name projection").splitlines()
    failures = []
    for key, cfg in projection["services"].items():
        try:
            print(f"Collecting {key}: account, existing containers, namespace maps, mounts and listeners", flush=True)
            facts = {"selected": cfg, "docker": [], "swarm": []}
            names = [n for n in service_names if n == cfg["name"] or n.endswith("_" + cfg["name"])]
            for name in names:
                fmt = '{"name":{{json .Spec.Name}},"image":{{json .Spec.TaskTemplate.ContainerSpec.Image}},"mode":{{json .Spec.Mode}},"placement":{{json .Spec.TaskTemplate.Placement}},"ports":{{json .Endpoint.Spec.Ports}},"mounts":{{json .Spec.TaskTemplate.ContainerSpec.Mounts}}}'
                spec = json.loads(command([*DOCKER, "service", "inspect", "--format", fmt, name], f"{key} Swarm metadata"))
                spec["tasks"] = command(
                    [
                        *DOCKER,
                        "service",
                        "ps",
                        "--no-trunc",
                        "--format",
                        "{{json .Name}} {{json .Node}} {{json .DesiredState}} {{json .CurrentState}}",
                        name,
                    ],
                    f"{key} task placement",
                )
                facts["swarm"].append(spec)
            selector = (
                f"label=com.docker.compose.service={cfg['name']}"
                if key in INFISICAL_SERVICES
                else f"name=(^|[/_-]){re.escape(cfg['name'])}([._-]|$)"
            )
            candidates = command(
                [*DOCKER, "ps", "-a", "--no-trunc", "--filter", selector, "--format", "{{.ID}}"],
                f"{key} Docker candidates",
            ).splitlines()
            for cid in candidates:
                observed = container(DOCKER, cid, docker=True)
                # The main Authelia name also matches authelia-redis. Only an
                # exact observed Swarm service label may attribute these targets.
                if key in (*AUTH_SERVICES, *NETBOX_SERVICES) and observed["swarm"] not in names:
                    continue
                facts["docker"].append(observed)
            if key in INFISICAL_SERVICES:
                projects = {record.get("project") for record in facts["docker"]}
                if (
                    names
                    or len(projects) != 1
                    or not all(isinstance(project, str) and project for project in projects)
                    or any(record.get("service") != cfg["name"] or record.get("swarm") for record in facts["docker"])
                    or sum(record["running"] for record in facts["docker"]) != 1
                ):
                    write(directory, f"{key}-docker.json", facts)
                    raise ValueError(f"{key}: require one running exact Compose service in one observed project, without Swarm ambiguity")
            if key in (*AUTH_SERVICES, *NETBOX_SERVICES) and len(names) != 1:
                raise ValueError(f"{key}: require one exact current Swarm service; review unexpected placement/runtime")
            write(directory, f"{key}-docker.json", facts)
            for index, volume in enumerate(cfg["volumes"].values()):
                path = volume["source"]
                result = subprocess.run(["sudo", "-n", "test", "-d", path], check=False)
                if result.returncode == 1:
                    print(f"{key}: declared persistent tree absent: {path}; ownership remains unresolved", flush=True)
                    continue
                if result.returncode:
                    raise RuntimeError(f"{key}: persistent path inspection failed ({result.returncode})")
                acl = command(
                    ["sudo", "-n", "getfacl", "--numeric", "--absolute-names", "--physical", "--recursive", path],
                    f"{key} numeric ACL manifest",
                )
                with (directory / f"{key}-tree-{index}.acl").open("x") as stream:
                    stream.write(acl + "\n")
                parent_acl = command(
                    ["sudo", "-n", "getfacl", "--numeric", "--absolute-names", "--physical", str(Path(path).parent)],
                    f"{key} bind-parent traversal metadata",
                )
                with (directory / f"{key}-parent-{index}.acl").open("x") as stream:
                    stream.write(parent_acl + "\n")
            ports = cfg["ports"].values() if isinstance(cfg["ports"], dict) else cfg["ports"]
            expression = "( " + " or ".join(f"sport = :{int(p['published'])}" for p in ports) + " )"
            write(
                directory,
                f"{key}-listeners.json",
                {
                    family: command(["sudo", "-n", "ss", "-H", family, "-lntp", expression], f"{key} {family} listeners")
                    for family in ["-4", "-6"]
                },
            )
            account, prefix = account_command(cfg["execution"]["host_user"])
            facts["account"] = account
            write(directory, f"{key}-account.json", account)
            facts["podman"] = []
            if prefix:
                facts["ranges"] = {
                    key: command(
                        ["sudo", "-n", "awk", "-F:", f'$1=="{account["name"]}" || $1=="{account["uid"]}" {{print}}', f"/etc/sub{key}"],
                        f"{key} account subordinate {key} ranges",
                    )
                    for key in ["uid", "gid"]
                }
                podman = [*prefix, "/usr/bin/podman", "--remote=false"]
                ids = command(
                    [*podman, "ps", "-a", "--no-trunc", "--filter", f"name=^{re.escape(cfg['name'])}$", "--format", "{{.ID}}"],
                    f"{key} account container listing",
                ).splitlines()
                write(directory, f"{key}-podman-ids.json", ids)
                for cid in ids:
                    facts["podman"].append(container(podman, cid))
                images = json.loads(
                    command(
                        [*podman, "images", "--format", "json", "--filter", f"reference={cfg['image']}"],
                        f"{key} selected account image metadata",
                    )
                )
                if not isinstance(images, list) or any(not isinstance(image, dict) for image in images):
                    raise ValueError("incomplete selected account image metadata")
                facts["images"] = [
                    {k: v for k, v in image.items() if k.lower() in {"id", "digest", "names", "repotags", "repodigests"}}
                    for image in images
                ]
                write(directory, f"{key}-runtime.json", facts)
                facts["unit"] = command(
                    [
                        *prefix,
                        "/usr/bin/systemctl",
                        "--user",
                        "show",
                        f"{cfg['name']}.service",
                        "-p",
                        "LoadState",
                        "-p",
                        "ActiveState",
                        "-p",
                        "SubState",
                        "-p",
                        "FragmentPath",
                    ],
                    f"{key} account unit metadata",
                )
            write(directory, f"{key}.json", facts)
            print(
                f"{key}: account={'present' if account else 'missing'}; running Docker={sum(c['running'] for c in facts['docker'])}; "
                f"running Podman={sum(c['running'] for c in facts['podman'])}. Saved facts; no acceptance inferred.",
                flush=True,
            )
        except (OSError, ValueError, RuntimeError, KeyError, IndexError, TypeError, subprocess.TimeoutExpired) as error:
            message = f"{key}: {error}"
            write(directory, f"{key}-error.json", {"error": message})
            failures.append(message)
            print(message, file=sys.stderr, flush=True)
    if json.loads(command(["sudo", "-n", "cat", "/etc/skynet-mgt-firewall/policy.json"], "installed policy continuity")) != policy:
        raise ValueError("installed policy changed during collection; do not install stale inputs")
    if command(["sudo", "-n", "sha256sum", "/etc/skynet-mgt-firewall/policy.json"], "installed policy hash continuity") != baseline_hash:
        raise ValueError("installed policy bytes changed during collection; do not install stale inputs")
    if set(projection["services"]) == set(ALERTING_SERVICES):
        try:
            collect_alerting_callers(directory, projection, policy, service_names)
        except (OSError, ValueError, RuntimeError, KeyError, subprocess.TimeoutExpired) as error:
            write(directory, "alerting-callers-error.json", {"error": str(error)})
            failures.append(str(error))
    if set(projection["services"]) == set(MEDIA_SERVICES) and not failures:
        try:
            collect_media_callers(directory, projection, policy, service_names)
        except (OSError, ValueError, RuntimeError, KeyError, subprocess.TimeoutExpired) as error:
            write(directory, "media-callers-error.json", {"error": str(error)})
            failures.append(str(error))
    if set(projection["services"]) == set(INFISICAL_SERVICES) and not failures:
        projects = {
            record["project"] for key in INFISICAL_SERVICES for record in json.loads((directory / f"{key}.json").read_text())["docker"]
        }
        if len(projects) != 1:
            failures.append("Infisical application/cache Compose projects differ; no shared deployment identity established")
    if failures:
        raise ValueError("incomplete service reports: " + "; ".join(failures))
    print(
        "Read-only batch collection complete. No acknowledgements changed; ownership and runtime acceptance remain to review.", flush=True
    )


def collect_alerting_callers(directory, projection, policy, service_names):
    """Snapshot exact current callers and process-owned sockets, never acceptance.

    The selected applications were collected already. Monitoring callers keep
    their HTTPS paths through Traefik; no direct backend allowance is inferred.
    Existing bindings are retained byte-for-value and a future Gotify binding
    remains unverified. Host-network sockets require actual process ownership.
    """
    from copy import deepcopy

    preflight = load("ansible/roles/service_firewall/files/haproxy-preflight.py", "utility_socket_projection")
    fw = load("ansible/roles/service_firewall/files/mgt-firewall.py", "utility_caller_resolution")
    observations = {}
    zone, https_port = projection["integrations"]["zone"], projection["integrations"]["private_https_port"]
    roots = {Path(volume["source"]) for cfg in projection["services"].values() for volume in cfg["volumes"].values()}
    consumers = []
    ids = command([*DOCKER, "ps", "--no-trunc", "--format", "{{.ID}}"], "running bind-consumer identities").splitlines()
    for cid in ids:
        fmt = '{"id":{{json .Id}},"name":{{json .Name}},"service":{{json (index .Config.Labels "com.docker.swarm.service.name")}},"mounts":{{json .Mounts}}}'
        record = json.loads(command([*DOCKER, "container", "inspect", "--format", fmt, cid], "project bind-consumer identity/mounts only"))
        if record.get("id") != cid or not isinstance(record.get("mounts"), list):
            raise ValueError("ambiguous bind-consumer identity/mount list")
        for mount in record["mounts"]:
            if mount.get("Type") != "bind":
                continue
            source = mount.get("Source")
            if not isinstance(source, str) or not Path(source).is_absolute() or type(mount.get("RW")) is not bool:
                raise ValueError("missing bind source or boolean RW; do not assume it is passive")
            overlap = [str(root) for root in roots if root.is_relative_to(source) or Path(source).is_relative_to(root)]
            if overlap:
                consumers.append({"id": cid, "name": record["name"], "service": record["service"], "mount": mount, "overlap": overlap})
    write(directory, "mount-consumers.json", consumers)
    write(
        directory,
        "declared-integration-paths.json",
        {
            "gotify_database": {"driver": "postgres", "host": f"haproxy.{zone}", "port": 5432, "database": "gotify"},
            "alertmanager_gotify": {"scheme": "https", "host": f"gotify.{zone}", "port": https_port, "path": "/message"},
            "monitoring_alertmanager": {
                "callers": ["prometheus", "loki"],
                "scheme": "https",
                "host": f"alertmanager.{zone}",
                "port": https_port,
            },
            "direct_backends": {"gotify": ["traefik"], "alertmanager": ["traefik"]},
            "observations_prove_sql_or_delivery": False,
        },
    )
    for name in ["traefik", "prometheus", "loki", *ALERTING_SERVICES]:
        # Derive a selector from the exact service names actually listed by the
        # daemon; do not manufacture a stack/service label or permit a subnet.
        names = [value for value in service_names if value == name or value.endswith("_" + name)]
        if len(names) != 1:
            raise ValueError(f"{name}: require one observed Swarm service for current integration evidence")
        selector = names[0]
        ids = command(
            [*DOCKER, "ps", "--no-trunc", "--filter", f"label=com.docker.swarm.service.name={selector}", "--format", "{{.ID}}"],
            f"{name} current exact task",
        ).splitlines()
        if len(ids) != 1:
            raise ValueError(f"{name}: require one running local task; inspect collected placement, do not infer a remote identity")
        current = container(DOCKER, ids[0], docker=True)
        if current["swarm"] != selector:
            raise ValueError(f"{name}: observed selector differs from task labels")
        identity = current["identity"]

        def run(argv, name=name):
            return command(["sudo", "-n", *argv], f"{name} process-owned socket/caller projection")

        owned = {row["pid"] for row in current["processes"]}
        sockets = {
            str(port): preflight.destinations(current["pid"], port, run, owners=owned) for port in sorted({5432, 80, 9093, https_port})
        }
        binding = {
            "kind": "container",
            "runtime": "docker",
            "phase": "docker",
            "selector": selector,
            "path": "bridge",
            "verified": False,
            "restart_verified": False,
            "physdev_verified": False,
        }
        existing = [
            value for value in policy["callers"].get(name, []) if value.get("kind") == "container" and value.get("phase") == "docker"
        ]
        if existing and not any(value.get("selector") == selector for value in existing):
            raise ValueError(f"{name}: observed service differs from its preserved Docker binding")
        bridges = fw.container_identities(binding, run)
        observations[name] = {
            "id": ids[0],
            "selector": selector,
            "identity": identity,
            "processes": current["processes"],
            "bridge_identities": bridges,
            "connections": sockets,
        }
        write(directory, f"{name}-caller-observation.json", observations[name])
        if context(current["pid"]) != identity or container(DOCKER, ids[0], docker=True)["identity"] != identity:
            raise ValueError(f"{name}: task/PID/network namespace changed during collection")
    write(directory, "alerting-callers.json", observations)
    inputs = json.loads((directory / "policy-inputs.json").read_text())
    candidate = deepcopy(inputs)
    gotify = json.loads((directory / "gotify.json").read_text())
    account = gotify["account"]
    if account is not None:
        local = {
            "kind": "local",
            "phase": "podman",
            "account": account["name"],
            "uid": account["uid"],
            "verified": False,
            "restart_verified": False,
        }
        bindings = candidate["mgt_firewall_callers"].setdefault("gotify", [])
        same = [value for value in bindings if value.get("kind") == "local" and value.get("phase") == "podman"]
        if same and (len(same) != 1 or any(same[0].get(key) != local[key] for key in ["account", "uid"])):
            raise ValueError("Gotify's existing Podman binding differs from its actual account; preserve and reconcile it")
        if not same:
            bindings.append(local)
            candidate["mgt_firewall_inputs_verified"] = False
    write(directory, "future-caller-inputs.json", candidate)
    if (
        json.loads(command(["sudo", "-n", "cat", "/etc/skynet-mgt-firewall/policy.json"], "policy continuity after caller collection"))
        != policy
    ):
        raise ValueError("installed policy changed during caller collection; reject stale inputs")
    if (
        command(["sudo", "-n", "sha256sum", "/etc/skynet-mgt-firewall/policy.json"], "policy byte continuity after caller collection")
        != (directory / "installed-policy.sha256").read_text().strip()
    ):
        raise ValueError("installed policy bytes changed during caller collection; reject stale inputs")
    host = json.loads((directory / "host.json").read_text())
    if socket.gethostname() != host["hostname"] or Path("/proc/sys/kernel/random/boot_id").read_text().strip() != host["boot_id"]:
        raise ValueError("host/boot identity changed during caller collection")


def collect_media_callers(directory, projection, policy, service_names):
    """Read only exact current identities/routes; prospective accounts stay false."""
    from copy import deepcopy

    preflight = load("ansible/roles/service_firewall/files/haproxy-preflight.py", "media_socket_projection")
    fw = load("ansible/roles/service_firewall/files/mgt-firewall.py", "media_caller_resolution")

    def run(argv):
        return command(["sudo", "-n", *argv], "media process-owned socket/caller projection")

    inputs = deepcopy(json.loads((directory / "policy-inputs.json").read_text()))
    write(directory, "declared-integration-paths.json", projection["integrations"])
    for name in ["traefik", *MEDIA_SERVICES]:
        names = [value for value in service_names if value == name or value.endswith("_" + name)]
        if len(names) != 1:
            raise ValueError(f"{name}: require one observed Swarm service; review placement before proceeding")
        selector = names[0]
        ids = command(
            [*DOCKER, "ps", "--no-trunc", "--filter", f"label=com.docker.swarm.service.name={selector}", "--format", "{{.ID}}"],
            f"{name} current exact task",
        ).splitlines()
        if len(ids) != 1:
            raise ValueError(f"{name}: require one running local task; do not infer placement from declarations")
        current = container(DOCKER, ids[0], docker=True)
        if current["swarm"] != selector:
            raise ValueError(f"{name}: selected task label differs")
        if name in MEDIA_SERVICES:
            saved = json.loads((directory / f"{name}.json").read_text())
            old = [record for record in saved["docker"] if record["running"]]
            if len(old) != 1 or old[0]["id"] != ids[0] or old[0]["identity"] != current["identity"]:
                raise ValueError(f"{name}: Docker task changed during prerequisite collection")
        binding = {
            "kind": "container",
            "phase": "docker",
            "runtime": "docker",
            "path": "bridge",
            "selector": selector,
            "verified": False,
            "restart_verified": False,
            "physdev_verified": False,
        }
        existing = [
            value for value in policy["callers"].get(name, []) if value.get("kind") == "container" and value.get("phase") == "docker"
        ]
        if len(existing) != 1 or existing[0].get("selector") != selector:
            raise ValueError(f"{name}: accepted Docker selector missing/ambiguous/different; preserve and reconcile it")
        owners = {row["pid"] for row in current["processes"]}
        ports = [5432, projection["integrations"]["znc"]["port"]] if name == "autobrr" else [5432] if name == "seerr" else []
        observed = {
            "id": ids[0],
            "selector": selector,
            "identity": current["identity"],
            "processes": current["processes"],
            "bridge_identities": fw.container_identities(binding, run),
            "connections": {str(port): preflight.destinations(current["pid"], port, run, owners=owners) for port in ports},
            "sql_or_integration_success_proved": False,
        }
        write(directory, f"{name}-caller-observation.json", observed)
        if context(current["pid"]) != current["identity"] or container(DOCKER, ids[0], docker=True)["identity"] != current["identity"]:
            raise ValueError(f"{name}: PID/task/namespace changed during collection")
        if name in MEDIA_SERVICES:
            account = saved["account"]
            if account is None:
                inputs["mgt_firewall_inputs_verified"] = False
                continue
            prospective = {
                "kind": "local",
                "phase": "podman",
                "account": account["name"],
                "uid": account["uid"],
                "verified": False,
                "restart_verified": False,
            }
            bindings = inputs["mgt_firewall_callers"].setdefault(name, [])
            same = [value for value in bindings if value.get("kind") == "local" and value.get("phase") == "podman"]
            if same and (len(same) != 1 or any(same[0].get(key) != prospective[key] for key in ["account", "uid"])):
                raise ValueError(f"{name}: retained rootless binding differs from prepared account")
            if not same:
                bindings.append(prospective)
                inputs["mgt_firewall_inputs_verified"] = False
    # ZNC is accepted and unchanged. Observe it without a restart or DNS/policy
    # mutation; application credentials, channels and TLS settings stay private.
    definition = project_znc_metadata()
    account, prefix = account_command(definition["account"])
    if prefix is None:
        raise ValueError("accepted rootless ZNC account is missing")
    podman = [*prefix, "/usr/bin/podman", "--remote=false"]
    ids = command([*podman, "ps", "--no-trunc", "--filter", "name=^znc$", "--format", "{{.ID}}"], "accepted ZNC identity").splitlines()
    if len(ids) != 1:
        raise ValueError("accepted rootless ZNC missing/ambiguous")
    current = container(podman, ids[0])
    # Podman can report the tagless digest for the same selected artifact.
    if current["name"].lstrip("/") != "znc" or not (
        current["image"] == definition["image"]
        or ("@sha256:" in current["image"] and current["image"].endswith(definition["image"].split("@")[-1]))
    ):
        raise ValueError("ZNC name/image differs from its accepted declaration")
    numeric = load("ansible/operator/znc-mapping-proof.py", "media_znc_numeric_maps")
    uid, gid = definition["uid"], definition["gid"]
    if numeric.mapped(uid, current["maps"]["uid"]) != account["uid"] or numeric.mapped(gid, current["maps"]["gid"]) != account["gid"]:
        raise ValueError("ZNC selected numeric map differs from its accepted account")
    if current["ports"].get("6502/tcp") != [{"HostIp": projection["address"], "HostPort": str(projection["integrations"]["znc"]["port"])}]:
        raise ValueError("ZNC protected IRC publication changed")
    write(directory, "znc-runtime.json", {"account": account, "runtime": current})
    # A possible inspection race must invalidate the whole evidence set.
    if context(current["pid"]) != current["identity"] or container(podman, ids[0])["identity"] != current["identity"]:
        raise ValueError("ZNC task/PID/namespace changed during collection")
    write(directory, "future-caller-inputs.json", inputs)
    if (
        json.loads(command(["sudo", "-n", "cat", "/etc/skynet-mgt-firewall/policy.json"], "policy continuity after media callers"))
        != policy
    ):
        raise ValueError("installed policy changed during caller collection; reject stale candidate")
    if (
        command(["sudo", "-n", "sha256sum", "/etc/skynet-mgt-firewall/policy.json"], "policy byte continuity after media callers")
        != (directory / "installed-policy.sha256").read_text().strip()
    ):
        raise ValueError("installed policy bytes changed during caller collection")
    links = json.loads(command(["ip", "-j", "address", "show"], "inventory address continuity after media callers"))
    if projection["address"] not in {entry["local"] for link in links for entry in link.get("addr_info", [])}:
        raise ValueError("verified inventory address disappeared during caller collection")
    host = json.loads((directory / "host.json").read_text())
    if socket.gethostname() != host["hostname"] or Path("/proc/sys/kernel/random/boot_id").read_text().strip() != host["boot_id"]:
        raise ValueError("host/boot identity changed during caller collection")


def project_znc_metadata():
    # Reuse the established value-free inventory/declaration projection.
    return load("ansible/operator/znc-mapping-proof.py", "media_znc_projection").project()


def image_update_pin(requested, record):
    """Select the observed primary image digest, never guess among repository refs."""
    if not isinstance(record, dict) or not isinstance(record.get("tags"), list) or requested not in record["tags"]:
        raise ValueError("updated image tag identity missing/different")
    primary, refs = record.get("digest"), record.get("refs")
    if not isinstance(primary, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", primary) or not isinstance(refs, list):
        raise ValueError("updated image primary digest metadata missing")
    repository = requested.rsplit(":", 1)[0]
    if not any(ref in {repository + "@" + primary, requested + "@" + primary} for ref in refs):
        raise ValueError("updated primary digest lacks a matching repository reference")
    return requested + "@" + primary


def prove_map(directory, output, projection, service, *, stage_image=False, allow_image_update=False, initialize_only=False):
    """Prove the declared keep-id map using the established mount-free probe."""
    mapping = load("ansible/operator/znc-mapping-proof.py", "utility_numeric_maps")
    if type(initialize_only) is not bool:
        raise ValueError("initialize_only must be a strict boolean")
    cfg = dict(projection["services"][service])
    if type(allow_image_update) is not bool or (
        allow_image_update and (service not in (*MEDIA_SERVICES, *MONITORING_SERVICES) or not stage_image)
    ):
        raise ValueError("image updates require an explicit staged media/monitoring proof")
    saved = json.loads((directory / f"{service}.json").read_text())
    prior = json.loads((directory / "selected.json").read_text())
    prior_cfg = prior["services"][service]
    if projection["host"] != prior["host"] or projection["address"] != prior["address"]:
        raise ValueError("inventory controller/address changed since retained collection")
    if service in MAPPED_SERVICES and projection.get("integrations") != prior.get("integrations"):
        raise ValueError("inventory integration destinations changed since retained collection")
    if {k: v for k, v in cfg.items() if k != "image"} != {k: v for k, v in prior_cfg.items() if k != "image"}:
        raise ValueError(f"{service} declaration changed beyond the recorded image pin; review before probing")
    userns = cfg["execution"].get("userns", {})
    if userns.get("mode") != "keep-id" or not re.fullmatch(r"[0-9]+:[0-9]+", str(cfg["user"])):
        raise ValueError(f"require the selected {service} keep-id/numeric process configuration")
    if any(isinstance(userns.get(key), bool) or not str(userns.get(key)).isdecimal() for key in ["uid", "gid"]):
        raise ValueError("selected namespace identities must be explicit numeric IDs")
    uid, gid = [int(userns[key]) for key in ["uid", "gid"]]
    if service in ALERTING_SERVICES and [int(value) for value in cfg["user"].split(":")] != [uid, gid]:
        raise ValueError("declared application process and keep-id identities differ")
    digest = re.fullmatch(r".+@sha256:([0-9a-f]{64})", cfg["image"])
    old = [record for record in saved["docker"] if record["running"]]
    if len(old) != 1 or (
        not allow_image_update and (not digest or not any(value.endswith("@sha256:" + digest[1]) for value in old[0]["repo_digests"]))
    ):
        raise ValueError("selected immutable image must match the one observed Docker writer")
    host = json.loads((directory / "host.json").read_text())
    if socket.gethostname() != host["hostname"] or Path("/proc/sys/kernel/random/boot_id").read_text().strip() != host["boot_id"]:
        raise ValueError("host/boot identity changed since retained ownership collection")
    account, prefix = account_command(cfg["execution"]["host_user"])
    if account != saved["account"] or prefix is None:
        raise ValueError(f"prepared {service} account identity/home changed")

    def ranges():
        return {
            key: command(
                ["sudo", "-n", "awk", "-F:", f'$1=="{account["name"]}" || $1=="{account["uid"]}" {{print}}', f"/etc/sub{key}"],
                f"{service} subordinate {key} ranges",
            )
            for key in ["uid", "gid"]
        }

    if ranges() != saved["ranges"]:
        raise ValueError(f"prepared {service} subordinate ranges changed")
    current = container(DOCKER, old[0]["id"], docker=True)
    report = output / "writer-continuity.json"
    fields = ["id", "running", "identity", "swarm", "image_id", "mounts", "maps"]
    write(output, report.name, {"saved": {key: old[0].get(key) for key in fields}, "current": {key: current.get(key) for key in fields}})
    for key in ["identity", "swarm", "image_id"]:
        if current.get(key) != old[0].get(key):
            raise ValueError(f"Docker {service} {key} differs from retained evidence; inspect {report}")
    try:
        current_mounts = mounts_by_destination(current.get("mounts"))
        saved_mounts = mounts_by_destination(old[0].get("mounts"))
    except ValueError as error:
        raise ValueError(f"Docker {service}: {error}; inspect {report}") from error
    if current_mounts != saved_mounts:
        differences = {}
        for destination in sorted(current_mounts.keys() | saved_mounts.keys()):
            before, after = saved_mounts.get(destination), current_mounts.get(destination)
            if before is None or after is None:
                differences[destination] = ["added" if before is None else "removed"]
            else:
                fields = [
                    key
                    for key in sorted(before.keys() | after.keys())
                    if key not in before or key not in after or before[key] != after[key]
                ]
                if fields:
                    differences[destination] = fields
        write(output, "mount-differences.json", differences)
        raise ValueError(f"Docker {service} mount fields differ: {json.dumps(differences)}; inspect {report}")
    if current["mounts"] != old[0]["mounts"]:
        print(f"Docker {service}: complete mount records match; only inspection list order differs.", flush=True)
    if any(mapping.map_triples(current["maps"][key]) != mapping.map_triples(old[0]["maps"][key]) for key in ["uid", "gid"]):
        raise ValueError(f"Docker {service} numeric namespace maps differ from retained evidence")
    if current["running"] is not True:
        raise ValueError(f"retained Docker {service} writer is no longer running")
    if not allow_image_update:
        write(output, "selected.json", cfg)
    write(output, "source.json", {"account": account, "ranges": saved["ranges"], "docker_identity": current["identity"]})
    podman = [*prefix, "/usr/bin/podman", "--remote=false"]
    if allow_image_update:
        requested = cfg["image"]
        if "@" in requested or not re.fullmatch(r"[a-zA-Z0-9./_-]+:[a-zA-Z0-9._-]+", requested):
            raise ValueError("image update requires the canonical explicit version tag")
        write(output, "requested-image.json", {"image": requested, "image_update_authorized": True, "previous_image": current["image"]})
        mapping.command([*podman, "pull", requested], operation=f"stage explicitly authorized {service} image update", timeout=600)
        fmt = '{"digest":{{json .Digest}},"refs":{{json .RepoDigests}},"tags":{{json .RepoTags}}}'
        record = json.loads(
            mapping.command([*podman, "image", "inspect", "--format", fmt, requested], operation="resolve staged image update identity")
        )
        write(output, "staged-image.json", record)
        cfg["image"] = image_update_pin(requested, record)
        after = json.loads(
            mapping.command([*podman, "image", "inspect", "--format", fmt, requested], operation="recheck staged image tag identity")
        )
        if image_update_pin(requested, after) != cfg["image"]:
            raise ValueError("updated image tag/digest changed during inspection")
        write(output, "selected.json", cfg)
    try:
        mapping.command([*podman, "image", "exists", cfg["image"]], operation=f"{service} exact account image check")
    except mapping.CommandFailure as error:
        if error.status != 1 or error.stderr:
            raise
        if not stage_image:
            raise ValueError(f"exact {service} image absent; explicit --stage-image is required") from error
        print(f"Staging only the canonical pinned {service} image in its dedicated store.", flush=True)
        mapping.command([*podman, "pull", cfg["image"]], operation=f"stage pinned {service} image", timeout=600)
        mapping.command([*podman, "image", "exists", cfg["image"]], operation=f"verify staged {service} image")
    name = f"skynet-{service}-map-" + output.name
    label = "io.skynet.utility-map"
    write(
        output,
        "probe-intent.json",
        {"name": name, "label": label, "value": output.name, "image": cfg["image"], "initialize_only": initialize_only},
    )
    cid = ""
    try:
        print(
            f"Initializing a mount-free, network-free namespace probe without starting {service}."
            if initialize_only
            else f"Starting a 120-second mount-free, network-free namespace probe; Docker {service} stays running.",
            flush=True,
        )
        cid = probe_command(
            [
                *podman,
                "create",
                "--rm",
                "--pull=never",
                "--network=none",
                "--image-volume=ignore",
                "--restart=no",
                "--name",
                name,
                "--label",
                f"{label}={output.name}",
                f"--userns=keep-id:uid={uid},gid={gid}",
                "--user",
                cfg["user"],
                *([cfg["image"]] if initialize_only else ["--entrypoint=/bin/sleep", cfg["image"], "120"]),
            ],
            output,
            "create",
        )
        if not re.fullmatch(r"[0-9a-f]{64}", cid):
            raise ValueError(f"ambiguous {service} probe ID")
        write(output, "probe-created.json", {"id": cid, "name": name})
        operation = "init" if initialize_only else "start"
        probe_command([*podman, operation, cid], output, operation)

        def inspect():
            return json.loads(
                mapping.command(
                    [
                        *podman,
                        "container",
                        "inspect",
                        "--format",
                        '{"id":{{json .ID}},"pid":{{json .State.Pid}},"running":{{json .State.Running}},'
                        '"status":{{json .State.Status}},"mounts":{{json .Mounts}},"network":{{json .HostConfig.NetworkMode}}}',
                        cid,
                    ],
                    operation=f"inspect exact {service} namespace probe",
                )
            )

        before = inspect()
        state_matches = (
            before.get("running") is False and before.get("status") == "initialized" if initialize_only else before.get("running") is True
        )
        if before["id"] != cid or type(before.get("pid")) is not int or before["pid"] <= 0 or not state_matches:
            raise ValueError(f"{service} probe is not the exact expected container state with a live namespace")
        if before.get("mounts") != [] or before.get("network") != "none":
            raise ValueError(f"{service} namespace probe must have no mounts or networking")
        identity = context(before["pid"])
        write(output, "probe.json", {**before, "identity": identity})
        maps = {
            key: command(["sudo", "-n", "cat", f"/proc/{before['pid']}/{key}_map"], f"selected {service} {key}_map")
            for key in ["uid", "gid"]
        }
        for key, text in maps.items():
            mapping.map_triples(text)
            with (output / f"selected.{key}_map").open("x") as stream:
                stream.write(text + "\n")
        if inspect() != before or context(before["pid"]) != identity:
            raise ValueError(f"{service} probe PID/birth/network namespace changed")
        if mapping.mapped(uid, maps["uid"]) != account["uid"] or mapping.mapped(gid, maps["gid"]) != account["gid"]:
            raise ValueError(f"selected {service} application identity does not map to its account")
        if account_command(account["name"])[0] != account or ranges() != saved["ranges"]:
            raise ValueError(f"{service} account/ranges changed during proof")
        if container(DOCKER, old[0]["id"], docker=True)["identity"] != current["identity"]:
            raise ValueError(f"Docker {service} identity changed during proof")
    finally:
        # Creation can time out after recording a container but before returning
        # its ID. Resolve only this unique intent, then verify ownership before
        # removal by full ID. An auto-removed/absent probe needs no cleanup.
        candidates = mapping.command(
            [
                *podman,
                "ps",
                "-a",
                "--no-trunc",
                "--filter",
                f"id={cid}" if re.fullmatch(r"[0-9a-f]{64}", cid) else f"name=^{re.escape(name)}$",
                "--format",
                "{{.ID}}",
            ],
            operation=f"resolve only the temporary {service} probe for cleanup",
        ).splitlines()
        if len(candidates) > 1 or any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in candidates):
            raise ValueError(f"ambiguous {service} probe cleanup identity; no container removed")
        if candidates:
            exact = candidates[0]
            owned = json.loads(
                mapping.command(
                    [
                        *podman,
                        "container",
                        "inspect",
                        "--format",
                        '{"id":{{json .ID}},"name":{{json .Name}},"owner":{{json (index .Config.Labels "io.skynet.utility-map")}}}',
                        exact,
                    ],
                    operation=f"verify exact temporary {service} probe ownership",
                )
            )
            if owned != {"id": exact, "name": name, "owner": output.name} or (cid and cid != exact):
                raise ValueError(f"{service} probe cleanup ownership differs; no container removed")
            mapping.command([*podman, "rm", "--force", "--ignore", exact], operation=f"remove only the exact temporary {service} probe")
    write(
        output,
        "result.json",
        {"selected_mapping_proved": True, "probe_removed": True, "account": account, "initialize_only": initialize_only},
    )
    print(
        f"Selected {service} map proved; probe removed. Account {account['uid']}:{account['gid']}. No ownership/acknowledgements changed.",
        flush=True,
    )


def prove_wallos(directory, output, projection, *, stage_image=False):
    return prove_map(directory, output, projection, "wallos", stage_image=stage_image)


def ownership_plan(directory, proof, service):
    """Translate retained numeric owners through proved maps, without mutation."""
    mapping = load("ansible/operator/znc-mapping-proof.py", "utility_ownership_maps")
    saved = json.loads((directory / f"{service}.json").read_text())
    cfg = json.loads((proof / "selected.json").read_text())
    result = json.loads((proof / "result.json").read_text())
    source = json.loads((proof / "source.json").read_text())
    if result.get("selected_mapping_proved") is not True or result.get("probe_removed") is not True:
        raise ValueError("namespace proof/cleanup is incomplete")
    if cfg["name"] != service or result["account"] != saved["account"] or source["account"] != saved["account"]:
        raise ValueError("proof service/account differs from retained ownership evidence")
    old = [record for record in saved["docker"] if record["running"]]
    if len(old) != 1 or old[0]["identity"] != source["docker_identity"]:
        raise ValueError("proof does not identify the retained Docker writer")
    if any(record["running"] for record in saved.get("podman", [])):
        raise ValueError("already running rootless service needs observed-state review, not ownership migration")
    prior = saved["selected"]
    if {k: v for k, v in cfg.items() if k != "image"} != {k: v for k, v in prior.items() if k != "image"}:
        raise ValueError("proved declaration differs from retained data/namespace configuration")
    maps = {key: (proof / f"selected.{key}_map").read_text() for key in ["uid", "gid"]}
    application = [int(value) for value in cfg["user"].split(":")]
    userns = cfg.get("execution", {}).get("userns", {})
    managed_ids = []
    for offset, key in enumerate(["uid", "gid"]):
        value = userns.get(key, application[offset])
        if isinstance(value, bool) or not str(value).isdecimal():
            raise ValueError("managed namespace identity must be numeric")
        managed_ids.append(int(value))
        if userns and mapping.mapped(int(value), maps[key]) != saved["account"][key]:
            raise ValueError("managed namespace identity does not map to the proved account")
    managed = {entry["path"] for entry in cfg.get("managed_paths", [])}
    managed |= {entry["dest"] for entry in cfg.get("templates", [])}
    if any("owner" in entry or "group" in entry for entry in [*cfg.get("managed_paths", []), *cfg.get("templates", [])]):
        raise ValueError("explicit managed-path ownership needs separate translation review")
    host_ids = cfg.get("host_ids", {})
    if any(isinstance(value, bool) or not str(value).isdecimal() for value in host_ids.values()):
        raise ValueError("inventory owner identities must be numeric")
    excluded = None
    if service == "authelia":
        selected_batch = json.loads((directory / "selected.json").read_text())["services"]
        excluded = Path(selected_batch["authelia-redis"]["volumes"]["config"]["source"])
        parent = Path(cfg["volumes"]["config"]["source"])
        if excluded == parent or not excluded.is_relative_to(parent):
            raise ValueError("Authelia cache must be a separately proved strict child tree")
    rows = {}
    for index, volume in enumerate(cfg["volumes"].values()):
        root = Path(volume["source"])
        text = (directory / f"{service}-tree-{index}.acl").read_text()
        acl_lines(text)
        for block in re.split(r"\n\s*\n", text.strip()):
            lines = block.splitlines()
            if any(line.startswith("default:") or re.match(r"^(user|group):[^:]", line) for line in lines):
                raise ValueError("named/default ACL translation needs explicit review")
            fields = dict(line[2:].split(": ", 1) for line in lines if line.startswith(("# file: ", "# owner: ", "# group: ")))
            path = Path(re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), fields["file"]))
            if not path.is_absolute() or ".." in path.parts or not path.is_relative_to(root):
                raise ValueError("ownership path escapes its declared persistent tree")
            if excluded is not None and path.is_relative_to(excluded):
                continue  # The independent cache proof owns every name in this subtree.
            owners = [int(fields[key]) for key in ["owner", "group"]]
            translated = []
            for offset, key in enumerate(["uid", "gid"]):
                inventory_owner = int(host_ids[key]) if key in host_ids else None
                # The rootless adapter explicitly owns generated paths/files
                # as the dedicated account. Other persistent paths preserve
                # their old container owner through the proved numeric maps.
                if str(path) in managed and owners[offset] == inventory_owner:
                    inside = managed_ids[offset]
                else:
                    inside = mapping.mapped(owners[offset], old[0]["maps"][key], inverse=True)
                    if inside not in {0, application[offset], managed_ids[offset]} and owners[offset] != inventory_owner:
                        raise ValueError(f"{service}: unreviewed container {key} owner class {inside}; do not guess")
                    if str(path) in managed:
                        inside = managed_ids[offset]
                translated.append(mapping.mapped(inside, maps[key]))
            row = {"path": str(path), "old": owners, "new": translated}
            if str(path) in rows and rows[str(path)] != row:
                raise ValueError("overlapping bind manifests disagree on ownership")
            rows[str(path)] = row
    if not rows:
        raise ValueError("empty ownership plan")
    return list(rows.values())


def ownership_acl_lines(text):
    """Compare complete per-path ACL blocks independently of traversal order."""
    blocks = {}
    current = []
    for line in [*acl_lines(text), "# file: <end>"]:
        if line.startswith("# file: "):
            if current:
                name = current[0]
                if name in blocks or any(sum(entry.startswith(prefix) for entry in current) != 1 for prefix in ["# owner: ", "# group: "]):
                    raise ValueError("duplicate or incomplete per-path ACL block")
                blocks[name] = current
            current = [line]
        else:
            if not current:
                raise ValueError("ACL entry before pathname")
            current.append(line)
    return [line for name in sorted(blocks) for line in blocks[name]]


def ownership_tree(roots):
    """Inventory names without following symlinks; prove regular-link containment."""
    roots = sorted({str(Path(root)) for root in roots})
    if not roots or any(not Path(root).is_absolute() or ".." in Path(root).parts for root in roots):
        raise ValueError("approved ownership roots must be absolute")
    entries = {}
    groups = {}

    def unreadable(error):
        raise error

    for root in roots:
        if any(parent.is_symlink() for parent in [Path(root), *Path(root).parents]) or not Path(root).is_dir():
            raise ValueError("symlinked or missing ownership root")
        for directory, directories, files in os.walk(root, followlinks=False, onerror=unreadable):
            for name in [directory, *[str(Path(directory) / child) for child in directories + files]]:
                path = Path(name)
                info = path.lstat()
                kind = "regular" if stat.S_ISREG(info.st_mode) else "directory" if stat.S_ISDIR(info.st_mode) else "symlink"
                if kind == "symlink" and not stat.S_ISLNK(info.st_mode):
                    raise ValueError("special ownership path needs review")
                record = {
                    "device": info.st_dev,
                    "inode": info.st_ino,
                    "mode": stat.S_IMODE(info.st_mode),
                    "uid": info.st_uid,
                    "gid": info.st_gid,
                    "links": info.st_nlink,
                    "kind": kind,
                    "size": info.st_size,
                    "mtime_ns": info.st_mtime_ns,
                    "ctime_ns": info.st_ctime_ns,
                }
                if kind == "symlink":
                    record["target"] = os.readlink(path)
                if name in entries and entries[name] != record:
                    raise ValueError("overlapping ownership roots changed during inventory")
                entries[name] = record
                if kind == "regular":
                    groups.setdefault((info.st_dev, info.st_ino), set()).add(name)
    linked = []
    for names in groups.values():
        names = sorted(names)
        counts = {entries[name]["links"] for name in names}
        if counts != {len(names)}:
            raise ValueError("external or changed hardlink: collected names do not account for link count")
        linked.append(names)
    return {"roots": roots, "entries": entries, "groups": sorted(linked)}


def ownership_inventory(rows, roots):
    """Validate all translations before mutation, retaining every pathname."""
    tree = ownership_tree(roots)
    translations = {}
    for row in rows:
        name = row["path"]
        if name in translations or name not in tree["entries"]:
            raise ValueError("duplicate or out-of-scope ownership translation")
        info = tree["entries"][name]
        if info["kind"] == "symlink" or any(parent.is_symlink() for parent in [Path(name), *Path(name).parents]):
            raise ValueError("symlinked ownership path needs review")
        if info["mode"] & (stat.S_ISUID | stat.S_ISGID):
            raise ValueError("set-id ownership path needs review")
        for key in ["old", "new"]:
            if len(row[key]) != 2 or any(type(value) is not int or value < 0 for value in row[key]):
                raise ValueError("ownership translation must contain numeric UID/GID")
        if row["old"] != [info["uid"], info["gid"]]:
            raise ValueError("ownership changed after stopped backup")
        translations[name] = row
    if set(translations) != {name for name, info in tree["entries"].items() if info["kind"] != "symlink"}:
        raise ValueError("ownership manifest is incomplete for approved roots")
    for names in tree["groups"]:
        if len({tuple(translations[name]["new"]) for name in names}) != 1 or len({tuple(translations[name]["old"]) for name in names}) != 1:
            raise ValueError("conflicting hardlink ownership translations")
    tree["translations"] = translations
    import hashlib

    for names in tree["groups"]:
        path = Path(names[0])
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            expected = tree["entries"][str(path)]
            if (info.st_dev, info.st_ino, info.st_nlink, info.st_ctime_ns) != (
                expected["device"],
                expected["inode"],
                expected["links"],
                expected["ctime_ns"],
            ):
                raise ValueError("file identity changed before hashing")
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if os.fstat(stream.fileno()) != info:
                # atime can change from reading; compare write/identity fields below.
                after = os.fstat(stream.fileno())
                if any(
                    getattr(info, key) != getattr(after, key)
                    for key in ["st_dev", "st_ino", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns"]
                ):
                    raise ValueError("file changed during hashing")
        for name in names:
            tree["entries"][name]["sha256"] = digest
    ownership_verify(tree, translated=False)
    return tree


def ownership_verify(snapshot, translated=True):
    """Verify every name, inode and link count; contents are hashed once per inode."""
    current = ownership_tree(snapshot["roots"])
    if current["groups"] != snapshot["groups"] or set(current["entries"]) != set(snapshot["entries"]):
        raise ValueError("ownership pathname set or hardlink topology changed")
    for name, expected in snapshot["entries"].items():
        actual = current["entries"][name]
        keys = ["device", "inode", "mode", "links", "kind"]
        if expected["kind"] != "directory":
            keys += ["size", "mtime_ns"]
        if expected["kind"] == "symlink":
            keys += ["uid", "gid", "target", "ctime_ns"]
        elif not translated:
            keys += ["ctime_ns"]
        if any(actual[key] != expected[key] for key in keys):
            raise ValueError("ownership identity, permissions or hardlink topology changed")
        if expected["kind"] != "symlink":
            owners = snapshot["translations"][name]["new" if translated else "old"]
            if [actual["uid"], actual["gid"]] != owners:
                raise ValueError("ownership translation differs for linked pathname")
    import hashlib

    for names in snapshot["groups"]:
        descriptor = os.open(names[0], os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            expected = snapshot["entries"][names[0]]
            if (info.st_dev, info.st_ino, info.st_nlink) != (expected["device"], expected["inode"], expected["links"]):
                raise ValueError("file identity changed during content verification")
            if hashlib.file_digest(stream, "sha256").hexdigest() != expected["sha256"]:
                raise ValueError("linked file contents changed")
    return current


def ownership_apply(snapshot):
    """Change ownership through held no-follow descriptors once per inode."""
    ownership_verify(snapshot, translated=False)
    groups = [*snapshot["groups"], *[[name] for name, info in snapshot["entries"].items() if info["kind"] == "directory"]]
    for names in groups:
        expected = snapshot["entries"][names[0]]
        for name in names:
            info = Path(name).lstat()
            if any(parent.is_symlink() for parent in [Path(name), *Path(name).parents]) or (
                info.st_dev,
                info.st_ino,
                stat.S_IMODE(info.st_mode),
                info.st_nlink,
                info.st_uid,
                info.st_gid,
                info.st_ctime_ns,
            ) != (
                expected["device"],
                expected["inode"],
                expected["mode"],
                expected["links"],
                expected["uid"],
                expected["gid"],
                expected["ctime_ns"],
            ):
                raise ValueError("ownership identity changed immediately before translation")
        flags = os.O_RDONLY | os.O_NOFOLLOW | (os.O_DIRECTORY if expected["kind"] == "directory" else 0)
        descriptor = os.open(names[0], flags)
        try:
            info = os.fstat(descriptor)
            if (info.st_dev, info.st_ino, info.st_nlink, info.st_uid, info.st_gid, info.st_ctime_ns) != (
                expected["device"],
                expected["inode"],
                expected["links"],
                expected["uid"],
                expected["gid"],
                expected["ctime_ns"],
            ):
                raise ValueError("opened ownership identity differs")
            os.fchown(descriptor, *snapshot["translations"][names[0]]["new"])
        finally:
            os.close(descriptor)
    ownership_verify(snapshot)


def ownership_archive_topology(archive, roots):
    """Project safe archive headers only; require contained exact hardlink targets."""
    import tarfile

    roots = [Path(root) for root in roots]
    members = {}
    with tarfile.open(archive) as stream:
        for member in stream:
            path = Path("/") / member.name
            if member.name.startswith("/") or ".." in path.parts or not any(path.is_relative_to(root) for root in roots):
                raise ValueError("archive path escapes approved roots")
            name = str(path)
            if name in members or not (member.isfile() or member.islnk() or member.isdir() or member.issym()):
                raise ValueError("duplicate or special archive member")
            members[name] = member
    groups = {}
    symlinks = {}
    for name, member in members.items():
        if any(str(parent) in members and members[str(parent)].issym() for parent in Path(name).parents):
            raise ValueError("archive member traverses a symlink")
        if member.issym():
            symlinks[name] = member.linkname
            continue
        if member.isdir():
            continue
        target = name
        seen = set()
        while members[target].islnk():
            if target in seen:
                raise ValueError("cyclic archive hardlink")
            seen.add(target)
            link = members[target].linkname
            target_path = Path("/") / link
            if link.startswith("/") or ".." in target_path.parts or str(target_path) not in members:
                raise ValueError("missing or external archive hardlink target")
            target = str(target_path)
        if not members[target].isfile():
            raise ValueError("archive hardlink target is not regular")
        groups.setdefault(target, []).append(name)
    return {"groups": sorted(sorted(names) for names in groups.values()), "symlinks": symlinks, "names": sorted(members)}


def ownership_archive_verify(archive, tree):
    projection = ownership_archive_topology(archive, tree["roots"])
    expected_links = {name: info["target"] for name, info in tree["entries"].items() if info["kind"] == "symlink"}
    if projection != {"groups": tree["groups"], "symlinks": expected_links, "names": sorted(tree["entries"])}:
        raise ValueError("archive does not preserve exact hardlink topology/pathnames")
    return projection


def ownership_restored_verify(tree):
    """Restored inodes may be new; every alias, owner and permission must persist."""
    current = ownership_tree(tree["roots"])
    if current["groups"] != tree["groups"] or set(current["entries"]) != set(tree["entries"]):
        raise ValueError("restored hardlink topology/pathnames differ")
    for name, expected in tree["entries"].items():
        keys = ["kind", "links", "mode", "uid", "gid"]
        if expected["kind"] == "symlink":
            keys += ["target"]
        elif expected["kind"] == "regular":
            keys += ["size"]
        if any(current["entries"][name][key] != expected[key] for key in keys):
            raise ValueError("restored hardlink ownership/permissions differ")
    return current


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?")
    parser.add_argument("--compare-acls", type=Path, nargs=2, metavar=("BEFORE", "AFTER"), help="compare ACLs ignoring empty separators")
    parser.add_argument(
        "--validate-runtime", type=Path, nargs=2, metavar=("RUNTIME", "SELECTED"), help="validate saved runtime metadata offline"
    )
    parser.add_argument(
        "--services",
        nargs="+",
        choices=(*SERVICES, *MAPPED_SERVICES),
        help="select an existing bounded service batch, including Authelia and its cache",
    )
    parser.add_argument("--service-map", choices=MAPPED_SERVICES, help="prove one selected service map from retained facts")
    parser.add_argument(
        "--initialize-only", action="store_true", help="prove --service-map from an initialized OCI namespace without starting it"
    )
    parser.add_argument("--plan-ownership", choices=MAPPED_SERVICES, help="plan exact ownership translations offline from retained facts")
    parser.add_argument("--proof", type=Path, help="successful selected-map directory for offline ownership planning")
    parser.add_argument("--wallos-map", action="store_true", help="prove only Wallos's selected map from retained facts")
    parser.add_argument(
        "--allow-image-update",
        action="store_true",
        help="explicitly stage a declared media/monitoring version update and resolve its digest",
    )
    parser.add_argument("--stage-image", action="store_true", help="explicitly stage the selected pinned image if absent")
    args = parser.parse_args()
    if args.initialize_only and not args.service_map:
        raise ValueError("--initialize-only requires --service-map")
    if args.allow_image_update and (args.service_map not in (*MEDIA_SERVICES, *MONITORING_SERVICES) or not args.stage_image):
        raise ValueError("--allow-image-update requires --service-map autobrr|seerr|grafana|scraparr --stage-image")
    if args.plan_ownership or args.proof:
        if (
            not args.plan_ownership
            or not args.proof
            or args.directory is None
            or any([args.compare_acls, args.validate_runtime, args.services, args.wallos_map, args.service_map, args.stage_image])
        ):
            raise ValueError("--plan-ownership SERVICE --proof MAP_DIR FACTS_DIR is an offline-only operation")
        rows = ownership_plan(args.directory, args.proof, args.plan_ownership)
        output = Path(tempfile.mkdtemp(prefix=f"ownership-plan-{args.plan_ownership}-", dir=args.directory))
        write(output, "translations.json", rows)
        print(f"Private ownership plan: {output}", flush=True)
        print(f"Planned {len(rows)} exact paths; no ownership or acknowledgements changed.", flush=True)
        return
    if args.validate_runtime:
        if args.directory is not None or args.compare_acls or args.wallos_map or args.service_map or args.services or args.stage_image:
            raise ValueError("--validate-runtime cannot be combined with collection/probe inputs")
        validate_runtime(*[json.loads(path.read_text()) for path in args.validate_runtime])
        print("Runtime image digest, process user, identity and publications match selected declarations.", flush=True)
        return
    if args.compare_acls:
        if args.directory is not None or args.wallos_map or args.service_map or args.services or args.stage_image:
            raise ValueError("--compare-acls cannot be combined with collection/probe inputs")
        if acl_lines(args.compare_acls[0].read_text()) != acl_lines(args.compare_acls[1].read_text()):
            raise ValueError("ACL metadata differs: paths, owners, permissions or ACL entries changed")
        print("ACL metadata matches; empty separator lines ignored.", flush=True)
        return
    if args.directory is None:
        raise ValueError("collection/probe requires a private directory")
    if args.wallos_map and args.service_map:
        raise ValueError("select one namespace proof")
    if args.stage_image and not (args.wallos_map or args.service_map):
        raise ValueError("--stage-image requires --wallos-map or --service-map")
    directory = args.directory
    info = directory.lstat()
    if directory.is_symlink() or not directory.is_dir() or info.st_uid != os.getuid() or info.st_mode & 0o777 != 0o700:
        raise ValueError("require an operator-owned private directory, mode 0700")
    proof_services = next(
        (
            batch
            for batch in [
                MEDIA_SERVICES,
                MONITORING_SERVICES,
                RECEIVER_SERVICES,
                VAULT_SERVICES,
                AUTH_SERVICES,
                INGRESS_SERVICES,
                NETBOX_SERVICES,
                INFISICAL_SERVICES,
            ]
            if args.service_map in batch
        ),
        ALERTING_SERVICES,
    )
    services = tuple(args.services or (proof_services if args.service_map else SERVICES))
    if services not in {
        SERVICES,
        ALERTING_SERVICES,
        MEDIA_SERVICES,
        MONITORING_SERVICES,
        RECEIVER_SERVICES,
        VAULT_SERVICES,
        AUTH_SERVICES,
        INGRESS_SERVICES,
        NETBOX_SERVICES,
        INFISICAL_SERVICES,
    }:
        raise ValueError(
            "select exactly adminer thelounge wallos, gotify alertmanager, autobrr seerr, grafana scraparr, loki prometheus, vaultwarden, authelia authelia-redis, traefik, netbox-postgres netbox-redis netbox, or infisical-redis infisical"
        )
    if args.service_map and args.service_map not in services:
        raise ValueError("namespace proof must address a member of the selected batch")
    if args.wallos_map and services != SERVICES:
        raise ValueError("Wallos proof must use the retained utility batch")
    projection = project() if services == SERVICES else project(services)
    if args.wallos_map or args.service_map:
        output = Path(tempfile.mkdtemp(prefix=f"{args.service_map or 'wallos'}-map-", dir=directory))
        print(f"Private selected-map reports: {output}", flush=True)
        if args.service_map:
            if args.allow_image_update:
                prove_map(
                    directory,
                    output,
                    projection,
                    args.service_map,
                    stage_image=args.stage_image,
                    allow_image_update=True,
                    **({"initialize_only": True} if args.initialize_only else {}),
                )
            else:
                prove_map(
                    directory,
                    output,
                    projection,
                    args.service_map,
                    stage_image=args.stage_image,
                    **({"initialize_only": True} if args.initialize_only else {}),
                )
        else:
            prove_wallos(directory, output, projection, stage_image=args.stage_image)
        return
    write(directory, "selected.json", projection)
    collect(directory, projection)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Utility preparation interrupted; no acceptance or ownership acknowledgement inferred.", file=sys.stderr)
        sys.exit(130)
    except (OSError, ValueError, RuntimeError, KeyError, IndexError, TypeError, subprocess.TimeoutExpired) as error:
        print(f"Utility preparation: {error}", file=sys.stderr)
        sys.exit(1)
