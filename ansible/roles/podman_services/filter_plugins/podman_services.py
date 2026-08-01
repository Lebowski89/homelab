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
_VALID_NETWORK_DRIVERS = {"bridge", "ipvlan", "macvlan"}
_VALID_PROTOCOLS = {"tcp", "udp"}
_VALID_VOLUME_TYPES = {"bind", "tmpfs", "volume"}


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
    update_policy = secret.get("update_policy", "preserve")
    if not isinstance(update_policy, str) or update_policy not in {"preserve", "reconcile"}:
        raise AnsibleFilterError('secret.update_policy must be exactly "preserve" or "reconcile"')
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
        update_policy = declaration.get("update_policy", "preserve")
        if not isinstance(update_policy, str) or update_policy not in {"preserve", "reconcile"}:
            raise AnsibleFilterError(f'{item_name}.update_policy must be exactly "preserve" or "reconcile"')
        secret["update_policy"] = update_policy
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


def _deploy(value: Any, *, name: str) -> dict[str, Any]:
    deploy = _as_mapping(value, name=name)
    supported = {"host", "mode", "replicas", "type", "profile", "constraints"}
    for field in deploy:
        if field not in supported:
            raise AnsibleFilterError(f"{name}.{field} is not supported by Podman Quadlets in this phase")
    deploy.pop("profile", None)
    deploy.pop("constraints", None)
    if "type" in deploy:
        deploy_type = _nonempty_string(deploy["type"], name=f"{name}.type")
        if deploy_type not in {"container", "swarm"}:
            raise AnsibleFilterError(f"{name}.type {deploy_type!r} is not supported by Podman Quadlets")
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


def _systemd(value: Any, *, name: str) -> dict[str, Any]:
    systemd = _as_mapping(value, name=name)
    unsupported = set(systemd) - {"after", "restart", "restart_sec"}
    if unsupported:
        raise AnsibleFilterError(f"{name} contains unsupported fields: {', '.join(sorted(unsupported))}")
    if "after" in systemd:
        after = systemd["after"]
        if not isinstance(after, list):
            raise AnsibleFilterError(f"{name}.after must be a list of non-empty unit names")
        systemd["after"] = [_nonempty_string(unit, name=f"{name}.after[{index}]") for index, unit in enumerate(after)]
    for field in ("restart", "restart_sec"):
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
        name: Service resource name used for validation and default unit naming.

    Returns:
        A newly allocated mapping consumed by Podman preparation and Quadlet
        templates. It contains normalized ``container`` and ``env`` data,
        ``host_paths``, named ``volumes``, ``secret_attachments``, a Podman
        network, and copied PostgreSQL/Traefik integration mappings.

    Raises:
        AnsibleFilterError: If the service or any supported canonical field has
            an invalid value or shape, a removed legacy Podman field is used,
            an unsupported field is present in a strictly validated section,
            or current Podman phase limitations are violated.

    Note:
        ``cfg`` and its nested values are not mutated.
    """
    if not isinstance(cfg, Mapping):
        raise AnsibleFilterError(f"{name} must be a mapping")
    if cfg.get("runtime") != "podman":
        raise AnsibleFilterError(f"{name}.runtime must be podman for podman_services")
    service_name = _resource_name(name, name="service name")

    _validate_service_runtime_options(
        cfg.get("runtime_options", {}),
        name=f"{name}.runtime_options",
        has_named_networks="named_networks" in cfg,
        has_systemd="systemd" in cfg,
    )

    removed_fields = [field for field in ("container", "env", "host_paths", "network") if field in cfg]
    if removed_fields:
        raise AnsibleFilterError(f"{name} uses removed legacy Podman fields: {', '.join(removed_fields)}; use the canonical service schema")

    container: dict[str, Any] = {}
    unit_name = service_name
    description = _nonempty_string(cfg["description"], name=f"{name}.description") if "description" in cfg else f"{name} Podman service"

    if "image" not in cfg:
        raise AnsibleFilterError(f"{name}.image must be an exact, non-latest image tag")
    image = _image(cfg["image"], name=f"{name}.image")
    container["image"] = image

    if "user" in cfg:
        container["uid"], container["gid"] = _canonical_user(cfg["user"], name=f"{name}.user")

    environment = _environment(cfg["environment"], name=f"{name}.environment") if "environment" in cfg else {}

    deploy = _deploy(cfg["deploy"], name=f"{name}.deploy") if "deploy" in cfg else {}
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

    return {
        "name": service_name,
        "unit_name": unit_name,
        "description": description,
        "image": image,
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
            ``podman_image_reference_drift``, ``podman_secret_policy``, and
            ``podman_secret_declarations``.
        """
        return {
            "podman_service_normalize": podman_service_normalize,
            "podman_env_file_key": podman_env_file_key,
            "podman_env_file_value": podman_env_file_value,
            "podman_image_reference_drift": podman_image_reference_drift,
            "podman_secret_policy": podman_secret_policy,
            "podman_secret_declarations": podman_secret_declarations,
        }
