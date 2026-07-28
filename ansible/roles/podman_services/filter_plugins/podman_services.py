"""Normalize canonical service declarations for Podman Quadlet tasks.

The Podman role uses these filters to validate portable Docker-shaped service
fields, preserve supported legacy nested Podman declarations during migration,
render safe environment values, evaluate image drift and secret replacement,
and produce the internal structure consumed by Quadlet templates.
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
        secret: Normalized declaration containing an optional strict
            boolean-like ``replace`` field.
        state: Service action. Replacement is active only for ``update`` and
            ``recreate``; other values preserve an existing secret.

    Returns:
        A mapping with complementary ``force`` and ``skip_existing`` flags.

    Raises:
        AnsibleFilterError: If ``secret`` is not a mapping or ``replace`` is not
            a supported boolean-like value.

    Note:
        The declaration is not mutated, and this filter does not validate the
        action name.
    """
    if not isinstance(secret, Mapping):
        raise AnsibleFilterError("secret must be a mapping")
    replace = _as_bool(secret.get("replace", False), name="secret.replace")
    mutable_replace = state in {"update", "recreate"} and replace
    return {"force": mutable_replace, "skip_existing": not mutable_replace}


def podman_secret_declarations(value: Any) -> list[dict[str, Any]]:
    """Normalize runtime-neutral secret declarations for Podman materialization.

    Args:
        value: ``None``, a list of declarations, or a named mapping whose values
            are declarations.

    Returns:
        Copied declaration dictionaries containing validated ``name``, ``var``,
        absolute ``target``, ``immutable``, and ``replace`` values, plus optional
        numeric UID/GID strings and a quoted four-digit octal mode.

    Raises:
        AnsibleFilterError: If collection/declaration shapes, names, variables,
            targets, policy booleans, IDs, or modes are invalid, or if a secret
            is both immutable and replaceable.

    Note:
        The input declarations are not mutated.
    """
    declarations = _as_items(value, name="podman secret declarations")
    result: list[dict[str, Any]] = []
    for index, declaration_value in enumerate(declarations):
        item_name = f"podman secret declarations[{index}]"
        declaration = _as_mapping(declaration_value, name=item_name)
        secret = {
            "name": _resource_name(declaration.get("name"), name=f"{item_name}.name"),
            "var": _nonempty_string(declaration.get("var"), name=f"{item_name}.var"),
            "target": _nonempty_string(declaration.get("target"), name=f"{item_name}.target"),
        }
        if not posixpath.isabs(secret["target"]):
            raise AnsibleFilterError(f"{item_name}.target must be an absolute path")
        runtime_options = _as_mapping(declaration.get("runtime_options", {}), name=f"{item_name}.runtime_options")
        podman_options = _as_mapping(runtime_options.get("podman", {}), name=f"{item_name}.runtime_options.podman")
        secret["immutable"] = _as_bool(
            podman_options.get("immutable", False),
            name=f"{item_name}.runtime_options.podman.immutable",
        )
        secret["replace"] = _as_bool(
            podman_options.get("replace", False),
            name=f"{item_name}.runtime_options.podman.replace",
        )
        if secret["immutable"] and secret["replace"]:
            raise AnsibleFilterError(f"{item_name} cannot be both immutable and replaceable")
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


def _choose(
    canonical: Any,
    legacy: Any,
    *,
    canonical_present: bool,
    legacy_present: bool,
    canonical_name: str,
    legacy_name: str,
) -> tuple[Any, bool]:
    if canonical_present and legacy_present and canonical != legacy:
        raise AnsibleFilterError(f"Conflicting declarations: {canonical_name} and {legacy_name}")
    if canonical_present:
        return canonical, True
    if legacy_present:
        return legacy, True
    return None, False


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


def _ports(value: Any, *, name: str, canonical: bool) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    host_key = "published" if canonical else "host"
    container_key = "target" if canonical else "container"
    for index, port in enumerate(_as_items(value, name=name)):
        item_name = f"{name}[{index}]"
        if not isinstance(port, Mapping):
            raise AnsibleFilterError(f"{item_name} must be a mapping")
        if canonical:
            supported_fields = {"published", "target", "protocol", "host_ip"}
            for field in port:
                if field not in supported_fields:
                    raise AnsibleFilterError(f"{item_name}.{field} is not supported by Podman Quadlets in this phase")
        if host_key not in port or container_key not in port:
            raise AnsibleFilterError(f"{item_name} must include both {host_key!r} and {container_key!r}")
        host_port = _integer(port[host_key], name=f"{item_name}.{host_key}")
        container_port = _integer(port[container_key], name=f"{item_name}.{container_key}")
        if not 1 <= host_port <= 65535:
            raise AnsibleFilterError(f"{item_name}.{host_key} must be between 1 and 65535")
        if not 1 <= container_port <= 65535:
            raise AnsibleFilterError(f"{item_name}.{container_key} must be between 1 and 65535")
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


def _paths(value: Any, *, name: str, allow_none: bool = False) -> list[dict[str, Any]]:
    if value is None and allow_none:
        return []
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


def _healthcheck(value: Any, *, name: str, canonical: bool) -> dict[str, Any]:
    healthcheck = _as_mapping(value, name=name)
    if not canonical:
        if "command" in healthcheck:
            healthcheck["command"] = _nonempty_string(healthcheck["command"], name=f"{name}.command")
        return healthcheck
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


def _volume_schema(value: Any, *, name: str) -> tuple[str, list[Any]]:
    entries = _as_items(value, name=name)
    schemas: set[str] = set()
    for index, volume in enumerate(entries):
        if not isinstance(volume, Mapping):
            raise AnsibleFilterError(f"{name}[{index}] must be a mapping")
        schemas.add("legacy" if "name" in volume and "source" not in volume and "type" not in volume else "canonical")
    if len(schemas) > 1:
        raise AnsibleFilterError(f"{name} cannot mix canonical and legacy Podman volume entries")
    return (schemas.pop() if schemas else "canonical"), entries


def _legacy_volumes(entries: list[Any], *, name: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, volume in enumerate(entries):
        item_name = f"{name}[{index}]"
        if not isinstance(volume, Mapping):
            raise AnsibleFilterError(f"{item_name} must be a mapping")
        result = deepcopy(dict(volume))
        result["name"] = _resource_name(result.get("name"), name=f"{item_name}.name")
        result["target"] = _nonempty_string(result.get("target"), name=f"{item_name}.target")
        result["read_only"] = _as_bool(result.get("read_only", False), name=f"{item_name}.read_only")
        normalized.append(result)
    return normalized


def _legacy_mounts(value: Any, *, name: str) -> list[dict[str, Any]]:
    mounts, volumes, tmpfs_mounts = _canonical_volumes(value, name=name)
    if volumes or tmpfs_mounts:
        raise AnsibleFilterError(f"{name} accepts bind mounts only")
    return mounts


def _legacy_tmpfs(value: Any, *, name: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, mount in enumerate(_as_items(value, name=name)):
        item_name = f"{name}[{index}]"
        if not isinstance(mount, Mapping):
            raise AnsibleFilterError(f"{item_name} must be a mapping")
        target = _nonempty_string(mount.get("target"), name=f"{item_name}.target")
        options = mount.get("options", [])
        if isinstance(options, str) or not isinstance(options, Iterable):
            raise AnsibleFilterError(f"{item_name}.options must be a list")
        normalized_options = [
            _nonempty_string(option, name=f"{item_name}.options[{option_index}]") for option_index, option in enumerate(options)
        ]
        normalized.append({"target": target, "options": normalized_options})
    return normalized


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
    if "after" in systemd:
        after = systemd["after"]
        if not isinstance(after, list):
            raise AnsibleFilterError(f"{name}.after must be a list of non-empty unit names")
        systemd["after"] = [_nonempty_string(unit, name=f"{name}.after[{index}]") for index, unit in enumerate(after)]
    return systemd


def _podman_runtime_options(value: Any, *, name: str) -> dict[str, Any]:
    options = _as_mapping(value, name=name)
    unsupported_runtimes = set(options) - {"podman", "docker"}
    if unsupported_runtimes:
        raise AnsibleFilterError(f"{name} contains unsupported runtimes: {', '.join(sorted(unsupported_runtimes))}")
    podman = _as_mapping(options.get("podman", {}), name=f"{name}.podman")
    unsupported = set(podman) - {"network", "systemd"}
    if unsupported:
        raise AnsibleFilterError(f"{name}.podman contains unsupported fields: {', '.join(sorted(unsupported))}")
    result: dict[str, Any] = {}
    if "network" in podman:
        result["network"] = _network(podman["network"], name=f"{name}.podman.network")
    if "systemd" in podman:
        result["systemd"] = _systemd(podman["systemd"], name=f"{name}.podman.systemd")
    return result


def _network(value: Any, *, name: str) -> dict[str, Any]:
    network = _as_mapping(value, name=name)
    network["name"] = _resource_name(network.get("name"), name=f"{name}.name")
    network["delete_on_stop"] = _as_bool(network.get("delete_on_stop", False), name=f"{name}.delete_on_stop")
    if not network["delete_on_stop"]:
        raise AnsibleFilterError(
            f"{name} is managed by podman_services and must be dedicated; "
            "set network.delete_on_stop: true. External/shared networks are not managed yet."
        )
    return network


def podman_service_normalize(cfg: Mapping[str, Any], name: str) -> dict[str, Any]:
    """Normalize one effective service into the Podman Quadlet model.

    Portable top-level fields are translated to the role's internal container,
    environment, host-path, named-volume, integration, and runtime-option
    mappings. Supported legacy Podman fields remain accepted only when they do
    not conflict with their canonical equivalents. Exact non-latest image tags,
    ``UID:GID`` users, port ranges/protocols, paths below ``/opt``, volume
    schemas, security values, health checks, single-instance deployment, and
    dedicated managed networks are validated. Value-free secret attachment
    names are de-duplicated in declaration order; secret values are not handled.

    Args:
        cfg: Effective canonical or transition-compatible service mapping whose
            runtime must be ``podman``.
        name: Service resource name used for validation and default unit naming.

    Returns:
        A newly allocated mapping consumed by Podman preparation and Quadlet
        templates. It contains normalized ``container`` and ``env`` data,
        ``host_paths``, named ``volumes``, ``secret_attachments``, Podman network
        and runtime options, and copied PostgreSQL/Traefik integration mappings.

    Raises:
        AnsibleFilterError: If the service or any supported canonical/legacy
            field has an invalid value or shape, canonical and legacy values
            conflict, an unsupported field is present in a strictly validated
            section, or current Podman phase limitations are violated.

    Note:
        ``cfg`` and its nested values are not mutated.
    """
    if not isinstance(cfg, Mapping):
        raise AnsibleFilterError(f"{name} must be a mapping")
    if str(cfg.get("runtime", "docker")) != "podman":
        raise AnsibleFilterError(f"{name}.runtime must be podman for podman_services")
    service_name = _resource_name(name, name="service name")

    raw_container = cfg.get("container", {})
    if not isinstance(raw_container, Mapping):
        raise AnsibleFilterError(f"{name}.container must be a mapping")
    container = deepcopy(dict(raw_container))
    unit_name = _resource_name(container.get("name", service_name), name=f"{name}.container.name")
    if "systemd" in container:
        container["systemd"] = _systemd(container["systemd"], name=f"{name}.container.systemd")

    canonical_description_present = "description" in cfg
    legacy_description_present = "description" in raw_container
    description, description_present = _choose(
        _nonempty_string(cfg["description"], name=f"{name}.description") if canonical_description_present else None,
        _nonempty_string(raw_container["description"], name=f"{name}.container.description") if legacy_description_present else None,
        canonical_present=canonical_description_present,
        legacy_present=legacy_description_present,
        canonical_name=f"{name}.description",
        legacy_name=f"{name}.container.description",
    )
    if not description_present:
        description = f"{name} Podman service"

    image, _ = _choose(
        _image(cfg["image"], name=f"{name}.image") if "image" in cfg else None,
        _image(raw_container["image"], name=f"{name}.container.image") if "image" in raw_container else None,
        canonical_present="image" in cfg,
        legacy_present="image" in raw_container,
        canonical_name=f"{name}.image",
        legacy_name=f"{name}.container.image",
    )
    if image is None:
        raise AnsibleFilterError(f"{name}.image must be an exact, non-latest image tag")
    container["image"] = image

    if "user" in raw_container:
        raise AnsibleFilterError(f"{name}.container.user is not supported; use top-level user or container.uid and container.gid")
    legacy_user_present = "uid" in raw_container or "gid" in raw_container
    legacy_user = None
    if legacy_user_present:
        if "uid" not in raw_container or "gid" not in raw_container:
            raise AnsibleFilterError(f"{name}.container.uid and {name}.container.gid must be defined together")
        legacy_user = (
            _numeric_id(raw_container["uid"], name=f"{name}.container.uid"),
            _numeric_id(raw_container["gid"], name=f"{name}.container.gid"),
        )
    user, user_present = _choose(
        _canonical_user(cfg["user"], name=f"{name}.user") if "user" in cfg else None,
        legacy_user,
        canonical_present="user" in cfg,
        legacy_present=legacy_user_present,
        canonical_name=f"{name}.user",
        legacy_name=f"{name}.container.uid/container.gid",
    )
    if user_present:
        container["uid"], container["gid"] = user

    canonical_env_present = "environment" in cfg
    legacy_env_present = "env" in cfg
    env, env_present = _choose(
        _environment(cfg["environment"], name=f"{name}.environment") if canonical_env_present else None,
        _environment(cfg["env"] or {}, name=f"{name}.env") if legacy_env_present else None,
        canonical_present=canonical_env_present,
        legacy_present=legacy_env_present,
        canonical_name=f"{name}.environment",
        legacy_name=f"{name}.env",
    )

    deploy = _deploy(cfg["deploy"], name=f"{name}.deploy") if "deploy" in cfg else {}
    canonical_host_present = "host" in deploy
    legacy_host_present = "host" in raw_container
    host, host_present = _choose(
        deploy.get("host"),
        _nonempty_string(raw_container["host"], name=f"{name}.container.host") if legacy_host_present else None,
        canonical_present=canonical_host_present,
        legacy_present=legacy_host_present,
        canonical_name=f"{name}.deploy.host",
        legacy_name=f"{name}.container.host",
    )
    if host_present:
        container["host"] = host

    canonical_ports_present = "ports" in cfg
    legacy_ports_present = "ports" in raw_container
    ports, ports_present = _choose(
        _ports(cfg["ports"], name=f"{name}.ports", canonical=True) if canonical_ports_present else None,
        _ports(raw_container["ports"], name=f"{name}.container.ports", canonical=False) if legacy_ports_present else None,
        canonical_present=canonical_ports_present,
        legacy_present=legacy_ports_present,
        canonical_name=f"{name}.ports",
        legacy_name=f"{name}.container.ports",
    )
    if ports_present:
        container["ports"] = ports

    canonical_paths_present = "paths" in cfg
    legacy_paths_present = "host_paths" in cfg
    paths, paths_present = _choose(
        _paths(cfg["paths"], name=f"{name}.paths") if canonical_paths_present else None,
        _paths(cfg["host_paths"], name=f"{name}.host_paths", allow_none=True) if legacy_paths_present else None,
        canonical_present=canonical_paths_present,
        legacy_present=legacy_paths_present,
        canonical_name=f"{name}.paths",
        legacy_name=f"{name}.host_paths",
    )
    host_paths = paths if paths_present else []

    volume_schema = None
    volume_entries: list[Any] = []
    if "volumes" in cfg:
        volume_schema, volume_entries = _volume_schema(cfg["volumes"], name=f"{name}.volumes")
    canonical_mounts = canonical_volumes = canonical_tmpfs = None
    if volume_schema == "canonical":
        canonical_mounts, canonical_volumes, canonical_tmpfs = _canonical_volumes(cfg["volumes"], name=f"{name}.volumes")

    legacy_mounts_present = "mounts" in raw_container
    legacy_tmpfs_present = "tmpfs" in raw_container
    legacy_mounts = _legacy_mounts(raw_container["mounts"], name=f"{name}.container.mounts") if legacy_mounts_present else None
    legacy_tmpfs = _legacy_tmpfs(raw_container["tmpfs"], name=f"{name}.container.tmpfs") if legacy_tmpfs_present else None

    if volume_schema == "canonical":
        mounts, _ = _choose(
            canonical_mounts,
            legacy_mounts,
            canonical_present=True,
            legacy_present=legacy_mounts_present,
            canonical_name=f"{name}.volumes (bind entries)",
            legacy_name=f"{name}.container.mounts",
        )
        tmpfs_mounts, _ = _choose(
            canonical_tmpfs,
            legacy_tmpfs,
            canonical_present=True,
            legacy_present=legacy_tmpfs_present,
            canonical_name=f"{name}.volumes (tmpfs entries)",
            legacy_name=f"{name}.container.tmpfs",
        )
        container["mounts"] = mounts
        container["tmpfs"] = tmpfs_mounts
        volumes = canonical_volumes or []
    else:
        if legacy_mounts_present:
            container["mounts"] = legacy_mounts
        if legacy_tmpfs_present:
            container["tmpfs"] = legacy_tmpfs
        volumes = _legacy_volumes(volume_entries, name=f"{name}.volumes") if volume_schema == "legacy" else []

    for field, converter in (
        ("cap_add", _capabilities),
        ("cap_drop", _capabilities),
        ("no_new_privileges", _as_bool),
        ("read_only", _as_bool),
    ):
        canonical_present = field in cfg
        legacy_present = field in raw_container
        value, present = _choose(
            converter(cfg[field], name=f"{name}.{field}") if canonical_present else None,
            converter(raw_container[field], name=f"{name}.container.{field}") if legacy_present else None,
            canonical_present=canonical_present,
            legacy_present=legacy_present,
            canonical_name=f"{name}.{field}",
            legacy_name=f"{name}.container.{field}",
        )
        if present:
            container[field] = value

    healthcheck, healthcheck_present = _choose(
        _healthcheck(cfg["healthcheck"], name=f"{name}.healthcheck", canonical=True) if "healthcheck" in cfg else None,
        _healthcheck(raw_container["healthcheck"], name=f"{name}.container.healthcheck", canonical=False)
        if "healthcheck" in raw_container
        else None,
        canonical_present="healthcheck" in cfg,
        legacy_present="healthcheck" in raw_container,
        canonical_name=f"{name}.healthcheck",
        legacy_name=f"{name}.container.healthcheck",
    )
    if healthcheck_present:
        container["healthcheck"] = healthcheck

    podman_options = _podman_runtime_options(cfg.get("runtime_options", {}), name=f"{name}.runtime_options")
    systemd, systemd_present = _choose(
        podman_options.get("systemd"),
        container.get("systemd"),
        canonical_present="systemd" in podman_options,
        legacy_present="systemd" in raw_container,
        canonical_name=f"{name}.runtime_options.podman.systemd",
        legacy_name=f"{name}.container.systemd",
    )
    if systemd_present:
        container["systemd"] = systemd

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

    legacy_network = _network(cfg["network"], name=f"{name}.network") if cfg.get("network") is not None else None
    network, _ = _choose(
        podman_options.get("network"),
        legacy_network,
        canonical_present="network" in podman_options,
        legacy_present=cfg.get("network") is not None,
        canonical_name=f"{name}.runtime_options.podman.network",
        legacy_name=f"{name}.network",
    )
    postgres = _as_mapping(cfg["postgres"], name=f"{name}.postgres") if "postgres" in cfg else {}
    traefik = _as_mapping(cfg["traefik"], name=f"{name}.traefik") if "traefik" in cfg else {}

    return {
        "name": service_name,
        "unit_name": unit_name,
        "description": description,
        "image": image,
        "container": container,
        "env": env if env_present else {},
        "secrets": [],
        "secret_attachments": secret_attachments,
        "host_paths": host_paths,
        "network": network,
        "runtime_options": {"podman": podman_options},
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
