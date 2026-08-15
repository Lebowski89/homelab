"""Normalize canonical service declarations for Podman Quadlet tasks.

The Podman role uses these filters to validate portable Docker-shaped service
fields, render safe environment values, evaluate image drift and secret
replacement, and produce the internal structure consumed by Quadlet templates.
"""

from __future__ import annotations

import ipaddress
import posixpath
import re
import shlex
from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

from ansible.errors import AnsibleFilterError

_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_RESOURCE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_USER_RE = re.compile(r"^[0-9]+:[0-9]+$")
_HOST_USER_RE = re.compile(r"^podman-[a-z0-9](?:[a-z0-9_-]{0,23}[a-z0-9])?\Z")
_VALID_NETWORK_DRIVERS = {"bridge", "ipvlan", "macvlan"}
_VALID_PROTOCOLS = {"tcp", "udp"}
_VALID_SECRET_UPDATE_POLICIES = {"preserve", "reconcile"}
_VALID_VOLUME_TYPES = {"bind", "tmpfs", "volume"}

# Effective service fields accepted by the Podman adapter are grouped by the
# component that owns their behavior. Keep this boundary explicit: accepting a
# field here means a production path consumes or validates it.
_CATALOG_METADATA_FIELDS = frozenset({"enabled", "runtime", "tags"})
_PODMAN_SERVICE_FIELDS = frozenset(
    {
        "cap_add",
        "cap_drop",
        "deploy",
        "description",
        "healthcheck",
        "image",
        "name",
        "named_networks",
        "no_new_privileges",
        "ports",
        "read_only",
        "runtime_options",
        "secrets",
        "systemd",
        "user",
        "volumes",
    }
)
_SERVICE_COMMON_FIELDS = frozenset({"copies", "environment", "infisical", "paths", "postgres", "templates", "traefik"})
_SERVICE_PREPARE_FIELDS = frozenset({"application_prepare", "paths_vault", "prep"})
_SUPPORTED_TOP_LEVEL_FIELDS = _CATALOG_METADATA_FIELDS | _PODMAN_SERVICE_FIELDS | _SERVICE_COMMON_FIELDS | _SERVICE_PREPARE_FIELDS


def podman_env_file_key(value: Any) -> str:
    """Validate and return one Podman environment-file key.

    Args:
        value: Candidate key.

    Returns:
        The unchanged key when it matches shell-style environment identifier
        syntax.

    Raises:
        AnsibleFilterError: If the value is not a string or contains invalid
            identifier characters.
    """
    if not isinstance(value, str) or not _ENV_KEY_RE.fullmatch(value):
        raise AnsibleFilterError(f"Podman env-file key must match {_ENV_KEY_RE.pattern}; got {value!r}")
    return value


def podman_env_file_value(value: Any) -> str:
    """Serialize one scalar for a Podman environment file.

    Args:
        value: String, integer, boolean, or ``None``. ``None`` intentionally
            represents an empty value.

    Returns:
        Text suitable for the value portion of an environment-file assignment;
        booleans use lowercase ``true`` or ``false``.

    Raises:
        AnsibleFilterError: If the value is structured or a string contains a
            carriage return, line feed, or NUL byte.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if not isinstance(value, str):
        raise AnsibleFilterError(
            "Podman env-file values must be strings, integers, booleans, or null; serialize structured values explicitly in YAML"
        )
    if any(character in value for character in ("\r", "\n", "\0")):
        raise AnsibleFilterError("Podman env-file values must not contain carriage returns, line feeds, or NUL bytes")
    return value


def _secret_update_policy(secret: Mapping[str, Any], *, name: str) -> str:
    update_policy = secret.get("update_policy", "preserve")
    if not isinstance(update_policy, str) or update_policy not in _VALID_SECRET_UPDATE_POLICIES:
        raise AnsibleFilterError(f'{name}.update_policy must be exactly "preserve" or "reconcile"')
    return update_policy


def podman_secret_policy(secret: Mapping[str, Any], state: str) -> dict[str, bool]:
    """Derive Podman secret module flags for the requested service action.

    Args:
        secret: Normalized declaration containing the canonical
            ``update_policy`` field.
        state: Service action. Reconciliation is active only for ``update``
            and ``recreate``; other actions preserve an existing secret.

    Returns:
        A mapping with complementary ``force`` and ``skip_existing`` flags.

    Raises:
        AnsibleFilterError: If ``secret`` is not a mapping, the update policy is
            invalid, or the action is unsupported.

    Note:
        The declaration is not mutated.
    """
    if not isinstance(secret, Mapping):
        raise AnsibleFilterError("secret must be a mapping")
    update_policy = _secret_update_policy(secret, name="secret")
    if state not in {"deploy", "bootstrap", "update", "recreate", "remove"}:
        raise AnsibleFilterError("state must be deploy, bootstrap, update, recreate, or remove")
    reconcile = update_policy == "reconcile" and state in {"update", "recreate"}
    return {"force": reconcile, "skip_existing": not reconcile}


def podman_secret_declarations(value: Any) -> list[dict[str, Any]]:
    """Normalize runtime-neutral secret declarations for Podman materialization.

    Args:
        value: ``None``, a list of declarations, or a named mapping whose values
            are declarations.

    Returns:
        Copied declaration dictionaries containing validated ``name``, ``var``,
        absolute ``target``, and canonical ``update_policy`` values, plus
        optional numeric UID/GID strings and a quoted four-digit octal mode.

    Raises:
        AnsibleFilterError: If collection/declaration shapes, names, variables,
            targets, update policies, IDs, modes, or fields are invalid.

    Note:
        The input declarations are not mutated.
    """
    declarations = _as_items(value, name="podman secret declarations")
    result: list[dict[str, Any]] = []
    for index, declaration_value in enumerate(declarations):
        item_name = f"podman secret declarations[{index}]"
        declaration = _as_mapping(declaration_value, name=item_name)
        if "runtime_options" in declaration:
            raise AnsibleFilterError(f"{item_name}.runtime_options is deprecated; use secret.update_policy")
        unsupported = set(declaration) - {"name", "var", "target", "uid", "gid", "mode", "update_policy", "origins"}
        if unsupported:
            raise AnsibleFilterError(f"{item_name} contains unsupported fields: {', '.join(sorted(unsupported))}")
        secret = {
            "name": _resource_name(declaration.get("name"), name=f"{item_name}.name"),
            "var": _nonempty_string(declaration.get("var"), name=f"{item_name}.var"),
            "target": _nonempty_string(declaration.get("target"), name=f"{item_name}.target"),
        }
        if not posixpath.isabs(secret["target"]):
            raise AnsibleFilterError(f"{item_name}.target must be an absolute path")
        secret["update_policy"] = _secret_update_policy(declaration, name=item_name)
        for field in ("uid", "gid"):
            if field in declaration:
                secret[field] = _numeric_id(declaration[field], name=f"{item_name}.{field}")
        if "mode" in declaration:
            mode = declaration["mode"]
            if not isinstance(mode, str) or not re.fullmatch(r"0[0-7]{3}", mode):
                raise AnsibleFilterError(f'{item_name}.mode must be a quoted four-digit octal mode such as "0400"')
            secret["mode"] = mode
        result.append(secret)
    return result


def podman_image_reference_drift(current: Mapping[str, Any], desired: str) -> dict[str, Any]:
    """Compare inspected and desired Podman image references.

    Args:
        current: Command-style result mapping containing ``rc`` and ``stdout``.
        desired: Exact image reference expected by the Quadlet.

    Returns:
        A mapping with ``drift``, ``missing``, and a human-readable ``message``.
        A nonzero inspection return code is classified as missing; unequal
        stdout is drift but not missing.

    Raises:
        AttributeError: If ``current`` does not provide mapping-style ``get``.
        TypeError: If ``current.rc`` has an incompatible type.
        ValueError: If ``current.rc`` cannot be converted to an integer.

    Note:
        The command result is not mutated.
    """
    rc = int(current.get("rc", 1))
    stdout = str(current.get("stdout", "")).strip()
    if rc != 0:
        return {"drift": True, "missing": True, "message": f"Podman image reference drift: inspect failed; desired={desired}"}
    if stdout != desired:
        return {"drift": True, "missing": False, "message": f"Podman image reference drift: desired={desired}, current={stdout}"}
    return {"drift": False, "missing": False, "message": f"No Podman image reference drift detected; desired={desired}"}


def _as_mapping(value: Any, *, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AnsibleFilterError(f"{name} must be a mapping")
    return deepcopy(dict(value))


def _as_items(value: Any, *, name: str) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        raise AnsibleFilterError(f"{name} must be a list or mapping, not a string")
    if isinstance(value, Mapping):
        return list(value.values())
    if isinstance(value, Iterable):
        return list(value)
    raise AnsibleFilterError(f"{name} must be a list or mapping")


def _as_bool(value: Any, *, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value in {0, 1}:
            return bool(value)
        raise AnsibleFilterError(f"{name} must be boolean-like true/false or integer 0/1, got {value!r}")
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "on", "1"}:
            return True
        if normalized in {"false", "no", "off", "0"}:
            return False
    raise AnsibleFilterError(f"{name} must be boolean-like true/false or integer 0/1, got {value!r}")


def _integer(value: Any, *, name: str) -> int:
    if isinstance(value, bool):
        raise AnsibleFilterError(f"{name} must be an integer, not a boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip()):
        return int(value.strip())
    raise AnsibleFilterError(f"{name} must be an integer, got {value!r}")


def _nonempty_string(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AnsibleFilterError(f"{name} must be a non-empty string")
    return value.strip()


def _resource_name(value: Any, *, name: str) -> str:
    result = _nonempty_string(value, name=name)
    if not _RESOURCE_NAME_RE.fullmatch(result):
        raise AnsibleFilterError(f"{name} must be a valid Quadlet resource name matching {_RESOURCE_NAME_RE.pattern}; got {value!r}")
    return result


def _numeric_id(value: Any, *, name: str) -> str:
    text = str(value).strip()
    if not text.isdigit():
        raise AnsibleFilterError(f"{name} must be a numeric, non-negative container ID")
    return text


def _canonical_user(value: Any, *, name: str) -> tuple[str, str]:
    if not isinstance(value, str) or not _USER_RE.fullmatch(value):
        raise AnsibleFilterError(f"{name} must contain exactly two numeric, non-negative IDs separated by a colon")
    uid, gid = value.split(":")
    return uid, gid


def _validate_top_level_fields(value: Mapping[Any, Any], *, name: str) -> None:
    unsupported = sorted(str(field) for field in value if field not in _SUPPORTED_TOP_LEVEL_FIELDS)
    if unsupported:
        raise AnsibleFilterError(f"{name} contains unsupported top-level fields for Podman: {', '.join(unsupported)}")


def _image(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AnsibleFilterError(f"{name} must be an exact, non-latest image tag")
    image = value.strip()
    final_component = image.rsplit("/", 1)[-1]
    if ":" not in final_component:
        raise AnsibleFilterError(f"{name} must be an exact, non-latest image tag")
    repository, tag = final_component.rsplit(":", 1)
    if not repository or not tag or tag == "latest":
        raise AnsibleFilterError(f"{name} must be an exact, non-latest image tag")
    return image


def _environment(value: Any, *, name: str) -> dict[str, Any]:
    environment = _as_mapping(value, name=name)
    for key, item in environment.items():
        try:
            podman_env_file_key(key)
            if not isinstance(item, Mapping):
                podman_env_file_value(item)
        except AnsibleFilterError as error:
            raise AnsibleFilterError(f"{name}.{key}: {error}") from error
    return environment


def _ports(value: Any, *, name: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, port in enumerate(_as_items(value, name=name)):
        item_name = f"{name}[{index}]"
        if not isinstance(port, Mapping):
            raise AnsibleFilterError(f"{item_name} must be a mapping")
        supported_fields = {"published", "target", "protocol", "host_ip"}
        for field in port:
            if field not in supported_fields:
                raise AnsibleFilterError(f"{item_name}.{field} is not supported by Podman Quadlets in this phase")
        if "published" not in port or "target" not in port:
            raise AnsibleFilterError(f"{item_name} must include both 'published' and 'target'")
        host_port = _integer(port["published"], name=f"{item_name}.published")
        container_port = _integer(port["target"], name=f"{item_name}.target")
        if not 1 <= host_port <= 65535:
            raise AnsibleFilterError(f"{item_name}.published must be between 1 and 65535")
        if not 1 <= container_port <= 65535:
            raise AnsibleFilterError(f"{item_name}.target must be between 1 and 65535")
        protocol = str(port.get("protocol", "tcp")).strip().lower()
        if protocol not in _VALID_PROTOCOLS:
            raise AnsibleFilterError(f"{item_name}.protocol must be one of {sorted(_VALID_PROTOCOLS)}")
        result: dict[str, Any] = {"host": host_port, "container": container_port, "protocol": protocol}
        if "host_ip" in port:
            host_ip = _nonempty_string(port["host_ip"], name=f"{item_name}.host_ip")
            try:
                address = ipaddress.ip_address(host_ip)
            except ValueError as error:
                raise AnsibleFilterError(f"{item_name}.host_ip must be a valid IPv4 address") from error
            if address.version != 4:
                raise AnsibleFilterError(f"{item_name}.host_ip must be IPv4 for this compatibility phase")
            result["host_ip"] = str(address)
        normalized.append(result)
    return normalized


def _paths(value: Any, *, name: str) -> list[dict[str, Any]]:
    if isinstance(value, (str, Mapping)) or not isinstance(value, Iterable):
        raise AnsibleFilterError(f"{name} must be a list of path mappings")
    normalized: list[dict[str, Any]] = []
    for index, path in enumerate(value):
        item_name = f"{name}[{index}]"
        if not isinstance(path, Mapping):
            raise AnsibleFilterError(f"{item_name} must be a mapping")
        result = deepcopy(dict(path))
        raw_path = _nonempty_string(result.get("path"), name=f"{item_name}.path")
        host_path = posixpath.normpath(raw_path)
        if host_path != "/opt" and not host_path.startswith("/opt/"):
            raise AnsibleFilterError(f"{item_name}.path must normalize to an absolute path within /opt; got {raw_path!r}")
        result["path"] = host_path
        normalized.append(result)
    return normalized


def _capabilities(value: Any, *, name: str) -> list[str]:
    if isinstance(value, str) or not isinstance(value, Iterable):
        raise AnsibleFilterError(f"{name} must be a list")
    result: list[str] = []
    for index, capability in enumerate(value):
        result.append(_nonempty_string(capability, name=f"{name}[{index}]"))
    return result


def _health_command(test: Any, *, name: str) -> str:
    if isinstance(test, str):
        return _nonempty_string(test, name=f"{name}.test")
    if isinstance(test, Iterable) and not isinstance(test, Mapping):
        parts = list(test)
        if not parts or any(not isinstance(part, str) or not part.strip() for part in parts):
            raise AnsibleFilterError(f"{name}.test list must contain only non-empty strings")
        kind = parts[0].strip().upper()
        arguments = [part.strip() for part in parts[1:]]
        if kind in {"CMD", "CMD-SHELL"} and not arguments:
            raise AnsibleFilterError(f"{name}.test {kind} form must include a command")
        if kind == "NONE":
            return "none"
        if kind == "CMD-SHELL":
            return " ".join(arguments)
        if kind == "CMD":
            return shlex.join(arguments)
        return shlex.join([part.strip() for part in parts])
    raise AnsibleFilterError(f"{name}.test must be a non-empty string or list of non-empty strings")


def _healthcheck(value: Any, *, name: str) -> dict[str, Any]:
    healthcheck = _as_mapping(value, name=name)
    if "test" not in healthcheck:
        raise AnsibleFilterError(f"{name}.test is required")
    result = {"command": _health_command(healthcheck["test"], name=name)}
    for field in ("interval", "timeout", "retries", "start_period"):
        if field in healthcheck:
            result[field] = healthcheck[field]
    return result


def _tmpfs_options(value: Any, *, name: str) -> list[str]:
    options = _as_mapping(value or {}, name=name)
    rendered: list[str] = []
    if "size" in options:
        size = _integer(options["size"], name=f"{name}.size")
        if size < 0:
            raise AnsibleFilterError(f"{name}.size must be >= 0")
        rendered.append(f"size={size}")
    if "mode" in options:
        rendered.append(f"mode={options['mode']}")
    return rendered


def _canonical_volumes(value: Any, *, name: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    mounts: list[dict[str, Any]] = []
    volumes: list[dict[str, Any]] = []
    tmpfs_mounts: list[dict[str, Any]] = []
    for index, volume in enumerate(_as_items(value, name=name)):
        item_name = f"{name}[{index}]"
        if not isinstance(volume, Mapping):
            raise AnsibleFilterError(f"{item_name} must be a mapping")
        volume_type = str(volume.get("type", "bind")).strip()
        if volume_type not in _VALID_VOLUME_TYPES:
            raise AnsibleFilterError(f"{item_name}.type must be one of {sorted(_VALID_VOLUME_TYPES)}")
        target = _nonempty_string(volume.get("target"), name=f"{item_name}.target")
        if volume_type == "tmpfs":
            tmpfs_mounts.append({"target": target, "options": _tmpfs_options(volume.get("tmpfs", {}), name=f"{item_name}.tmpfs")})
            continue
        source = _nonempty_string(volume.get("source"), name=f"{item_name}.source")
        read_only = _as_bool(volume.get("read_only", False), name=f"{item_name}.read_only")
        if volume_type == "bind":
            mounts.append({"source": source, "target": target, "read_only": read_only})
        else:
            volumes.append(
                {
                    "name": _resource_name(source, name=f"{item_name}.source"),
                    "target": target,
                    "read_only": read_only,
                }
            )
    return mounts, volumes, tmpfs_mounts


def _execution_userns(value: Any, *, name: str) -> dict[str, str]:
    userns = _as_mapping(value, name=name)
    unsupported = sorted(set(userns) - {"mode", "uid", "gid"})
    if unsupported:
        raise AnsibleFilterError(f"{name} contains unsupported fields: {', '.join(unsupported)}")
    if userns.get("mode") != "keep-id":
        raise AnsibleFilterError(f'{name}.mode must be exactly "keep-id"')
    missing = [field for field in ("uid", "gid") if field not in userns]
    if missing:
        raise AnsibleFilterError(f"{name} requires both uid and gid")
    uid = _numeric_id(userns["uid"], name=f"{name}.uid")
    gid = _numeric_id(userns["gid"], name=f"{name}.gid")
    if int(uid) > 65535 or int(gid) > 65535:
        raise AnsibleFilterError(f"{name}.uid and {name}.gid must be between 0 and 65535")
    return {"mode": "keep-id", "uid": uid, "gid": gid}


def _execution(value: Any, *, name: str) -> dict[str, Any]:
    execution = _as_mapping(value, name=name)
    unsupported = sorted(set(execution) - {"mode", "host_user", "userns"})
    if unsupported:
        raise AnsibleFilterError(f"{name} contains unsupported fields: {', '.join(unsupported)}")
    if "mode" not in execution:
        raise AnsibleFilterError(f'{name}.mode must be exactly "rootful" or "rootless"')
    mode = _nonempty_string(execution["mode"], name=f"{name}.mode")
    if mode not in {"rootful", "rootless"}:
        raise AnsibleFilterError(f'{name}.mode must be exactly "rootful" or "rootless"; got {mode!r}')
    if mode == "rootful":
        if "host_user" in execution:
            raise AnsibleFilterError(f"{name}.host_user is only valid when mode is rootless")
        if "userns" in execution:
            raise AnsibleFilterError(f"{name}.userns is only valid when mode is rootless")
        return {"mode": "rootful"}
    if "host_user" not in execution:
        raise AnsibleFilterError(f"{name}.host_user is required when mode is rootless")
    host_user = _nonempty_string(execution["host_user"], name=f"{name}.host_user")
    if not _HOST_USER_RE.fullmatch(host_user):
        raise AnsibleFilterError(
            f"{name}.host_user must be a dedicated account name using the reserved podman- prefix and matching "
            f"{_HOST_USER_RE.pattern}; got {host_user!r}"
        )
    result: dict[str, Any] = {"mode": "rootless", "host_user": host_user}
    if "userns" in execution:
        result["userns"] = _execution_userns(execution["userns"], name=f"{name}.userns")
    return result


def podman_subid_range(value: Any, account: Any, minimum_count: Any = 65536) -> dict[str, int]:
    """Validate one account's exact subordinate-ID range declaration.

    Args:
        value: Complete text from ``/etc/subuid`` or ``/etc/subgid``.
        account: Dedicated rootless account whose entry is required.
        minimum_count: Smallest acceptable range size. The role uses 65,536,
            which is the normal rootless Podman allocation.

    Returns:
        A mapping containing integer ``start`` and ``count`` values.

    Raises:
        AnsibleFilterError: If inputs are malformed, the selected account has
            zero or multiple entries, or its range is too small.

    The input text is only parsed; it is never modified.
    """
    if not isinstance(value, str):
        raise AnsibleFilterError("Subordinate-ID data must be text")
    account_name = _nonempty_string(account, name="Subordinate-ID account")
    count = _integer(minimum_count, name="Subordinate-ID minimum count")
    if count < 1:
        raise AnsibleFilterError("Subordinate-ID minimum count must be positive")

    matches: list[tuple[int, int]] = []
    for line_number, raw_line in enumerate(value.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split(":")
        if fields[0] != account_name:
            continue
        if len(fields) != 3 or not fields[1].isdigit() or not fields[2].isdigit():
            raise AnsibleFilterError(f"Malformed subordinate-ID entry for {account_name} on line {line_number}")
        start, range_count = int(fields[1]), int(fields[2])
        if start < 1 or range_count < 1:
            raise AnsibleFilterError(f"Subordinate-ID entry for {account_name} must use positive integers")
        matches.append((start, range_count))

    if len(matches) != 1:
        raise AnsibleFilterError(f"Expected exactly one subordinate-ID entry for {account_name}; found {len(matches)}")
    start, range_count = matches[0]
    if range_count < count:
        raise AnsibleFilterError(f"Subordinate-ID entry for {account_name} provides {range_count} IDs; at least {count} are required")
    return {"start": start, "count": range_count}


def podman_rootless_account_contract(value: Any) -> dict[str, bool]:
    """Decide whether a dedicated rootless account may be created or reused.

    Args:
        value: Mapping containing the expected service/account identity plus
            inspected passwd, group, home, password-lock, marker, and persisted
            execution-state values.

    Returns:
        ``{"create": True}`` only when the account, primary group, home, and
        marker are all absent. An exact previously managed account returns
        ``{"create": False}``.

    Raises:
        AnsibleFilterError: If the declaration does not use the reserved
            account prefix, UID/GID zero is observed, an existing object is
            incompatible, or neither the account marker nor the service's
            persisted execution state proves ownership.

    The supplied inspection mapping and nested values are never modified.
    """
    context = _as_mapping(value, name="Rootless account contract")
    host_user = _nonempty_string(context.get("host_user"), name="Rootless account host_user")
    if not _HOST_USER_RE.fullmatch(host_user):
        raise AnsibleFilterError("Rootless Podman accounts must use the reserved podman- prefix")
    service = _nonempty_string(context.get("service"), name="Rootless account service")
    expected_comment = _nonempty_string(context.get("comment"), name="Rootless account comment")
    expected_home = _nonempty_string(context.get("home"), name="Rootless account home")
    expected_shell = _nonempty_string(context.get("shell"), name="Rootless account shell")
    account = context.get("account")
    group = context.get("group")
    marker = context.get("marker") or {}
    persisted = context.get("persisted") or {}
    home_exists = context.get("home_exists") is True

    if account is None:
        if home_exists or group is not None or marker:
            raise AnsibleFilterError(
                f"Refusing to create {host_user}: an unmanaged home, primary group, or ownership marker already exists"
            )
        return {"create": True}

    if not isinstance(account, list) or len(account) < 6:
        raise AnsibleFilterError(f"Existing account data for {host_user} is malformed")
    if not isinstance(group, list) or len(group) < 2:
        raise AnsibleFilterError(f"Existing account {host_user} lacks its dedicated primary group")
    try:
        uid = int(account[1])
        gid = int(account[2])
        group_gid = int(group[1])
    except (TypeError, ValueError) as error:
        raise AnsibleFilterError(f"Existing account IDs for {host_user} are malformed") from error
    if uid == 0 or gid == 0:
        raise AnsibleFilterError(f"Rootless account {host_user} must not use UID or GID 0")
    group_names = context.get("group_names")
    locked = context.get("password_locked") is True
    exact_contract = (
        account[3] == expected_comment
        and account[4] == expected_home
        and account[5] == expected_shell
        and group_gid == gid
        and group_names == [host_user]
        and locked
        and home_exists
    )
    if not exact_contract:
        raise AnsibleFilterError(f"Existing account {host_user} does not match the dedicated managed contract")

    marker_proves_owner = (
        isinstance(marker, Mapping)
        and marker.get("managed_by") == "podman_services"
        and marker.get("service") == service
        and marker.get("host_user") == host_user
        and marker.get("home") == expected_home
        and str(marker.get("uid", "")) == str(uid)
        and str(marker.get("gid", "")) == str(gid)
    )
    state_proves_owner = (
        isinstance(persisted, Mapping)
        and persisted.get("managed_by") == "podman_services"
        and persisted.get("service") == service
        and persisted.get("mode") == "rootless"
        and persisted.get("host_user") == host_user
        and str(persisted.get("uid", "")) == str(uid)
        and str(persisted.get("gid", "")) == str(gid)
    )
    if not marker_proves_owner and not state_proves_owner:
        raise AnsibleFilterError(
            f"Existing account {host_user} is not proven to belong to service {service}; cross-service reuse is forbidden"
        )
    return {"create": False}


def _deploy(value: Any, *, name: str) -> dict[str, Any]:
    deploy = _as_mapping(value, name=name)
    unsupported = sorted(set(deploy) - {"execution", "host", "mode", "replicas", "type"})
    if unsupported:
        raise AnsibleFilterError(f"{name} contains unsupported fields for Podman: {', '.join(unsupported)}")
    deploy["execution"] = _execution(deploy["execution"], name=f"{name}.execution") if "execution" in deploy else {"mode": "rootful"}
    if "type" in deploy:
        deploy_type = _nonempty_string(deploy["type"], name=f"{name}.type")
        if deploy_type != "container":
            raise AnsibleFilterError(f'{name}.type must be exactly "container" for Podman; got {deploy_type!r}')
        deploy["type"] = deploy_type
    if "mode" in deploy:
        mode = _nonempty_string(deploy["mode"], name=f"{name}.mode")
        if mode != "replicated":
            raise AnsibleFilterError(f"{name}.mode {mode!r} is not supported; only single-instance replicated mode is accepted")
        deploy["mode"] = mode
    if "replicas" in deploy:
        replicas = _integer(deploy["replicas"], name=f"{name}.replicas")
        if replicas != 1:
            raise AnsibleFilterError(f"{name}.replicas={replicas} is not supported; Podman Quadlets run one instance")
        deploy["replicas"] = replicas
    if "host" in deploy:
        deploy["host"] = _nonempty_string(deploy["host"], name=f"{name}.host")
    return deploy


def _has_native_infisical_secret(cfg: Mapping[str, Any]) -> bool:
    infisical = cfg.get("infisical")
    if not isinstance(infisical, Mapping):
        return False
    secrets_map = infisical.get("secrets_map", [])
    if isinstance(secrets_map, Mapping):
        entries = secrets_map.values()
    elif isinstance(secrets_map, Iterable) and not isinstance(secrets_map, str):
        entries = secrets_map
    else:
        return False
    return any(isinstance(entry, Mapping) and "secret" in entry for entry in entries)


def _proper_descendant(value: Any, roots: Iterable[str], *, name: str, root_description: str) -> str:
    if not isinstance(value, str) or not value or not posixpath.isabs(value) or posixpath.normpath(value) != value:
        raise AnsibleFilterError(f"{name} must be a normalized absolute proper descendant of {root_description}; got {value!r}")
    for root in roots:
        try:
            if value != root and posixpath.commonpath((root, value)) == root:
                return value
        except (TypeError, ValueError):
            continue
    raise AnsibleFilterError(f"{name} must be a normalized absolute proper descendant of {root_description}; got {value!r}")


def _validate_rootless_managed_files(cfg: Mapping[str, Any], *, name: str, bind_sources: list[str]) -> None:
    for field in ("copies", "templates"):
        declarations = cfg.get(field, [])
        if not declarations:
            continue
        if isinstance(declarations, (str, Mapping)) or not isinstance(declarations, Iterable):
            raise AnsibleFilterError(f"{name}.{field} must be a list of mappings")
        for index, declaration in enumerate(declarations):
            item_name = f"{name}.{field}[{index}]"
            if not isinstance(declaration, Mapping):
                raise AnsibleFilterError(f"{item_name} must be a mapping")
            _proper_descendant(
                declaration.get("dest"),
                bind_sources,
                name=f"{item_name}.dest",
                root_description="a declared rootless bind source",
            )
            if "owner" in declaration or "group" in declaration:
                raise AnsibleFilterError(f"{item_name} must omit owner and group; the dedicated execution account owns generated files")


def _validate_rootless_subset(
    cfg: Mapping[str, Any],
    *,
    name: str,
    image: str,
    deploy: Mapping[str, Any],
    container: Mapping[str, Any],
    network: Mapping[str, Any] | None,
    volumes: list[dict[str, Any]],
    host_paths: list[dict[str, Any]],
    secret_attachments: list[str],
) -> None:
    if deploy["execution"]["mode"] != "rootless":
        return
    registry = image.split("/", 1)[0] if "/" in image else ""
    if not registry or not (registry == "localhost" or "." in registry or ":" in registry):
        raise AnsibleFilterError(f"{name}.image must be fully qualified for rootless Podman; got {image!r}")
    if deploy.get("type") != "container":
        raise AnsibleFilterError(f"{name}.deploy.type must be exactly container for rootless Podman")
    if network is None or network.get("external") or network.get("driver", "bridge") != "bridge":
        raise AnsibleFilterError(f"{name}.named_networks must declare one managed bridge for rootless Podman")
    for index, port in enumerate(container.get("ports", [])):
        if port["host"] < 1024:
            raise AnsibleFilterError(
                f"{name}.ports[{index}].published uses privileged port {port['host']}; rootless Podman requires 1024 or higher"
            )
        if port["protocol"] != "tcp":
            raise AnsibleFilterError(f"{name}.ports[{index}].protocol must be tcp for rootless Podman in this phase")
    mounts = container.get("mounts", [])
    if volumes or container.get("tmpfs"):
        raise AnsibleFilterError(f"{name}.volumes supports only bind mounts for rootless Podman in this phase")
    bind_sources: list[str] = []
    if host_paths or mounts or cfg.get("copies") or cfg.get("templates"):
        if "userns" not in deploy["execution"]:
            raise AnsibleFilterError(f"{name}.deploy.execution.userns keep-id mapping is required for rootless bind mounts")
        for index, mount in enumerate(mounts):
            bind_sources.append(
                _proper_descendant(
                    mount["source"],
                    ("/opt",),
                    name=f"{name}.volumes[{index}].source",
                    root_description="/opt for rootless Podman",
                )
            )

        bind_path_counts = dict.fromkeys(bind_sources, 0)
        raw_paths = cfg.get("paths", [])
        for index, path in enumerate(host_paths):
            candidate = _proper_descendant(
                raw_paths[index].get("path") if isinstance(raw_paths[index], Mapping) else None,
                ("/opt",),
                name=f"{name}.paths[{index}].path",
                root_description="/opt for rootless Podman",
            )
            if candidate in bind_path_counts:
                bind_path_counts[candidate] += 1
                if path.get("state", "directory") != "directory":
                    raise AnsibleFilterError(f"{name}.paths[{index}] matching a rootless bind source must use state directory")
                if "owner" in path or "group" in path:
                    raise AnsibleFilterError(
                        f"{name}.paths[{index}] matching a rootless bind source must omit owner and group; "
                        "the dedicated execution account owns it"
                    )
                continue
            if path.get("state", "directory") != "absent":
                raise AnsibleFilterError(
                    f"{name}.paths[{index}] is not a declared rootless bind source and must use state absent for confined cleanup"
                )
            _proper_descendant(
                candidate,
                bind_sources,
                name=f"{name}.paths[{index}].path",
                root_description="a declared rootless bind source for state absent cleanup",
            )
            if "owner" in path or "group" in path:
                raise AnsibleFilterError(f"{name}.paths[{index}] state absent cleanup must omit owner and group")

        if any(count != 1 for count in bind_path_counts.values()):
            raise AnsibleFilterError(
                f"{name}.paths must declare each rootless bind-mount source exactly once so ownership can be reconciled safely"
            )
        _validate_rootless_managed_files(cfg, name=name, bind_sources=bind_sources)
    if container.get("cap_add"):
        raise AnsibleFilterError(f"{name}.cap_add is not supported for rootless Podman in this phase")
    if secret_attachments or _has_native_infisical_secret(cfg):
        raise AnsibleFilterError(f"{name}.secrets is not supported for rootless Podman in this phase")
    for field in ("application_prepare", "prep", "paths_vault"):
        if cfg.get(field):
            raise AnsibleFilterError(
                f"{name}.{field} is not supported for rootless Podman until application preparation is execution-user aware"
            )


def _systemd(value: Any, *, name: str) -> dict[str, Any]:
    systemd = _as_mapping(value, name=name)
    unsupported = set(systemd) - {"after", "restart", "restart_sec", "timeout_start_sec"}
    if unsupported:
        raise AnsibleFilterError(f"{name} contains unsupported fields: {', '.join(sorted(unsupported))}")
    if "after" in systemd:
        after = systemd["after"]
        if not isinstance(after, list):
            raise AnsibleFilterError(f"{name}.after must be a list of non-empty unit names")
        systemd["after"] = [_nonempty_string(unit, name=f"{name}.after[{index}]") for index, unit in enumerate(after)]
    for field in ("restart", "restart_sec", "timeout_start_sec"):
        if field in systemd:
            systemd[field] = _nonempty_string(systemd[field], name=f"{name}.{field}")
    return systemd


def _validate_service_runtime_options(
    value: Any,
    *,
    name: str,
    has_named_networks: bool,
    has_systemd: bool,
) -> None:
    options = _as_mapping(value, name=name)
    unsupported_runtimes = set(options) - {"podman", "docker"}
    if unsupported_runtimes:
        raise AnsibleFilterError(f"{name} contains unsupported runtimes: {', '.join(sorted(unsupported_runtimes))}")
    podman = _as_mapping(options.get("podman", {}), name=f"{name}.podman")
    docker = _as_mapping(options.get("docker", {}), name=f"{name}.docker")
    if docker:
        raise AnsibleFilterError(f"{name}.docker contains unsupported fields for Podman: {', '.join(sorted(docker))}")
    if "network" in podman and has_named_networks:
        raise AnsibleFilterError(
            f"{name}.podman.network and top-level named_networks cannot both be declared; "
            "remove the retired runtime_options.podman.network form"
        )
    if "systemd" in podman and has_systemd:
        raise AnsibleFilterError(
            f"{name}.podman.systemd and top-level systemd cannot both be declared; remove the retired runtime_options.podman.systemd form"
        )
    retired = set(podman) & {"network", "systemd"}
    if retired:
        replacements = []
        if "network" in retired:
            replacements.append("move network to top-level named_networks")
        if "systemd" in retired:
            replacements.append("move systemd to top-level systemd")
        raise AnsibleFilterError(
            f"{name}.podman uses retired service-level fields: {', '.join(sorted(retired))}; " + "; ".join(replacements)
        )
    unsupported = set(podman)
    if unsupported:
        raise AnsibleFilterError(f"{name}.podman contains unsupported fields: {', '.join(sorted(unsupported))}")


def _named_networks(value: Any, *, name: str) -> dict[str, Any] | None:
    networks = _as_mapping(value, name=name)
    if len(networks) > 1:
        raise AnsibleFilterError(f"{name} supports exactly one attached network for Podman; got {len(networks)}")
    if not networks:
        return None

    declared_name, raw_options = next(iter(networks.items()))
    item_name = f"{name}.{declared_name}"
    logical_name = _resource_name(declared_name, name=f"{name} key")
    options = _as_mapping(raw_options, name=item_name)
    unsupported = set(options) - {"driver", "external", "name"}
    if unsupported:
        raise AnsibleFilterError(f"{item_name} contains unsupported fields: {', '.join(sorted(unsupported))}")

    external = _as_bool(options.get("external", False), name=f"{item_name}.external")
    network_name = _resource_name(options.get("name", logical_name), name=f"{item_name}.name")
    result: dict[str, Any] = {"name": network_name, "external": external}
    if "driver" in options:
        driver = _nonempty_string(options["driver"], name=f"{item_name}.driver").lower()
        if driver not in _VALID_NETWORK_DRIVERS:
            raise AnsibleFilterError(f"{item_name}.driver must be one of {sorted(_VALID_NETWORK_DRIVERS)}")
        if external:
            raise AnsibleFilterError(f"{item_name}.driver cannot be set when external is true; the external owner controls its driver")
        result["driver"] = driver
    return result


def podman_service_normalize(cfg: Mapping[str, Any], name: str) -> dict[str, Any]:
    """Normalize one effective service into the Podman Quadlet model.

    Portable top-level fields are translated to the role's internal container,
    environment, host-path, named-network, named-volume, integration, and
    systemd mappings. Exact non-latest image tags, ``UID:GID`` users, port
    ranges/protocols, paths below ``/opt``, volume schemas, security values,
    health checks, single-instance deployment, and dedicated managed networks
    are validated. Value-free secret attachment names are de-duplicated in
    declaration order; secret values are not handled.

    Args:
        cfg: Effective canonical service mapping whose runtime must be
            ``podman``.
        name: Catalog or base-target role prefix used when ``cfg.name`` is
            omitted.

    Returns:
        A newly allocated mapping consumed by Podman preparation and Quadlet
        templates. It contains normalized ``container`` and ``env`` data,
        ``host_paths``, named ``volumes``, ``secret_attachments``, a Podman
        network, and copied PostgreSQL/Traefik integration mappings.

    Raises:
        AnsibleFilterError: If the service has unsupported top-level fields, a
            supported field has an invalid value or shape, or a current Podman
            limitation is violated.

    Note:
        ``cfg`` and its nested values are not mutated.
    """
    if not isinstance(cfg, Mapping):
        raise AnsibleFilterError(f"{name} must be a mapping")
    if cfg.get("runtime") != "podman":
        raise AnsibleFilterError(f"{name}.runtime must be podman for podman_services")
    _validate_top_level_fields(cfg, name=name)
    service_name = _resource_name(cfg.get("name", name), name=f"{name}.name")

    _validate_service_runtime_options(
        cfg.get("runtime_options", {}),
        name=f"{name}.runtime_options",
        has_named_networks="named_networks" in cfg,
        has_systemd="systemd" in cfg,
    )

    container: dict[str, Any] = {}
    unit_name = service_name
    description = (
        _nonempty_string(cfg["description"], name=f"{name}.description") if "description" in cfg else f"{service_name} Podman service"
    )

    if "image" not in cfg:
        raise AnsibleFilterError(f"{name}.image must be an exact, non-latest image tag")
    image = _image(cfg["image"], name=f"{name}.image")
    container["image"] = image

    if "user" in cfg:
        container["uid"], container["gid"] = _canonical_user(cfg["user"], name=f"{name}.user")

    environment = _environment(cfg["environment"], name=f"{name}.environment") if "environment" in cfg else {}

    deploy = _deploy(cfg["deploy"], name=f"{name}.deploy") if "deploy" in cfg else {"execution": {"mode": "rootful"}}
    if "host" in deploy:
        container["host"] = deploy["host"]

    if "ports" in cfg:
        container["ports"] = _ports(cfg["ports"], name=f"{name}.ports")

    host_paths = _paths(cfg["paths"], name=f"{name}.paths") if "paths" in cfg else []

    volumes: list[dict[str, Any]] = []
    if "volumes" in cfg:
        mounts, volumes, tmpfs_mounts = _canonical_volumes(cfg["volumes"], name=f"{name}.volumes")
        container["mounts"] = mounts
        container["tmpfs"] = tmpfs_mounts

    for field, converter in (
        ("cap_add", _capabilities),
        ("cap_drop", _capabilities),
        ("no_new_privileges", _as_bool),
        ("read_only", _as_bool),
    ):
        if field in cfg:
            container[field] = converter(cfg[field], name=f"{name}.{field}")

    if "healthcheck" in cfg:
        container["healthcheck"] = _healthcheck(cfg["healthcheck"], name=f"{name}.healthcheck")

    if "systemd" in cfg:
        container["systemd"] = _systemd(cfg["systemd"], name=f"{name}.systemd")

    secret_attachments: list[str] = []
    if cfg.get("secrets"):
        attachments = cfg["secrets"]
        if isinstance(attachments, str) or not isinstance(attachments, Iterable):
            raise AnsibleFilterError(f"{name}.secrets must be a list of value-free secret-name strings")
        for index, attachment in enumerate(attachments):
            if not isinstance(attachment, str) or not attachment.strip():
                raise AnsibleFilterError(f"{name}.secrets[{index}] is not supported by Podman; use a value-free secret-name string")
            if attachment.strip() not in secret_attachments:
                secret_attachments.append(attachment.strip())

    network = _named_networks(cfg["named_networks"], name=f"{name}.named_networks") if "named_networks" in cfg else None
    postgres = _as_mapping(cfg["postgres"], name=f"{name}.postgres") if "postgres" in cfg else {}
    traefik = _as_mapping(cfg["traefik"], name=f"{name}.traefik") if "traefik" in cfg else {}

    _validate_rootless_subset(
        cfg,
        name=name,
        image=image,
        deploy=deploy,
        container=container,
        network=network,
        volumes=volumes,
        host_paths=host_paths,
        secret_attachments=secret_attachments,
    )

    return {
        "name": service_name,
        "unit_name": unit_name,
        "description": description,
        "image": image,
        "execution": deploy["execution"],
        "container": container,
        "env": environment,
        "secrets": [],
        "secret_attachments": secret_attachments,
        "host_paths": host_paths,
        "network": network,
        "volumes": volumes,
        "postgres": postgres,
        "traefik": traefik,
    }


class FilterModule:
    """Register Podman normalization and policy filters with Ansible."""

    def filters(self) -> dict[str, Any]:
        """Return all Jinja filters exposed by this plugin.

        Returns:
            A mapping exposing ``podman_service_normalize``,
            ``podman_env_file_key``, ``podman_env_file_value``,
            ``podman_image_reference_drift``, ``podman_secret_policy``,
            ``podman_secret_declarations``, ``podman_subid_range``, and
            ``podman_rootless_account_contract``.
        """
        return {
            "podman_service_normalize": podman_service_normalize,
            "podman_env_file_key": podman_env_file_key,
            "podman_env_file_value": podman_env_file_value,
            "podman_image_reference_drift": podman_image_reference_drift,
            "podman_secret_policy": podman_secret_policy,
            "podman_secret_declarations": podman_secret_declarations,
            "podman_subid_range": podman_subid_range,
            "podman_rootless_account_contract": podman_rootless_account_contract,
        }
