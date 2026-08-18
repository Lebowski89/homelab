"""Validate and normalize runtime-neutral service data for Ansible roles.

The ``service_common`` role uses these filters to prepare environment values,
Infisical lookup declarations and check-mode stand-ins, PostgreSQL connection
metadata, and Traefik rendering context before Docker or Podman adapters perform
runtime-specific materialization. Secret values are never included in errors.
"""

from __future__ import annotations

import posixpath
import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from ansible.errors import AnsibleFilterError

_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_RESOURCE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_MODE_RE = re.compile(r"^0[0-7]{3}$")


def _mapping(value: Any, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AnsibleFilterError(f"{name} must be a mapping")
    return value


def _text(value: Any) -> str:
    return str(value or "").strip()


def _strict_bool(value: Any, *, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value in {0, 1}:
            return bool(value)
        raise AnsibleFilterError(f"{name} must be a boolean or integer 0/1, got {value!r}")
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "on", "1"}:
            return True
        if normalized in {"false", "no", "off", "0"}:
            return False
    raise AnsibleFilterError(f"{name} must be a strict boolean value, got {value!r}")


def _nonempty_text(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AnsibleFilterError(f"{name} must be a non-empty string")
    return value.strip()


def _resource_name(value: Any, *, name: str) -> str:
    result = _nonempty_text(value, name=name)
    if not _RESOURCE_NAME_RE.fullmatch(result):
        raise AnsibleFilterError(f"{name} must be a valid runtime resource name matching {_RESOURCE_NAME_RE.pattern}")
    return result


def _numeric_id(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip().isdigit():
        raise AnsibleFilterError(f"{name} must be a numeric string")
    return value.strip()


def _mode(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not _MODE_RE.fullmatch(value):
        raise AnsibleFilterError(f'{name} must be a quoted four-digit octal mode such as "0400"')
    return value


def _absolute_target(value: Any, *, name: str, default: str) -> str:
    target = default if value is None else _nonempty_text(value, name=name)
    if not posixpath.isabs(target):
        raise AnsibleFilterError(f"{name} must be an absolute path")
    return target


def _secret_update_policy(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or value not in {"preserve", "reconcile"}:
        raise AnsibleFilterError(f'{name} must be exactly "preserve" or "reconcile"')
    return value


def _canonical_secret(value: Any, *, var: str, name: str) -> dict[str, Any]:
    secret = _mapping(value, name=name)
    if "runtime_options" in secret:
        raise AnsibleFilterError(f"{name}.runtime_options is deprecated; use {name}.update_policy")
    unsupported = set(secret) - {"name", "target", "uid", "gid", "mode", "update_policy"}
    if unsupported:
        raise AnsibleFilterError(f"{name} contains unsupported fields: {', '.join(sorted(unsupported))}")
    resource_name = _resource_name(secret.get("name"), name=f"{name}.name")
    result: dict[str, Any] = {
        "name": resource_name,
        "var": var,
        "target": _absolute_target(
            secret.get("target"),
            name=f"{name}.target",
            default=f"/run/secrets/{resource_name}",
        ),
        "update_policy": _secret_update_policy(
            secret.get("update_policy", "preserve"),
            name=f"{name}.update_policy",
        ),
        "origins": ["canonical"],
    }
    for field, converter in (("uid", _numeric_id), ("gid", _numeric_id), ("mode", _mode)):
        if field in secret:
            result[field] = converter(secret[field], name=f"{name}.{field}")
    return result


def _identifier(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AnsibleFilterError(f"{name} must be a non-empty identifier")
    result = value.strip()
    if not _IDENTIFIER_RE.fullmatch(result):
        raise AnsibleFilterError(f"{name} must match {_IDENTIFIER_RE.pattern}")
    return result


def _environment_key(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not _ENV_KEY_RE.fullmatch(value):
        raise AnsibleFilterError(f"{name} must match {_ENV_KEY_RE.pattern}")
    return value


def _environment_scalar(value: Any, *, name: str) -> Any:
    if value is None or isinstance(value, (bool, int)):
        return value
    if not isinstance(value, str):
        raise AnsibleFilterError(f"{name} must be a string, integer, boolean, null, or a supported typed mapping")
    if any(character in value for character in ("\r", "\n", "\0")):
        raise AnsibleFilterError(f"{name} must not contain carriage returns, line feeds, or NUL bytes")
    return value


def _declared_infisical_vars(config: Any) -> set[str]:
    config_mapping = _mapping(config, name="service_common_infisical_config")
    secrets_map = config_mapping.get("secrets_map", [])
    if not isinstance(secrets_map, list):
        raise AnsibleFilterError("service_common_infisical_config.secrets_map must be a list")
    declared: set[str] = set()
    for index, entry in enumerate(secrets_map):
        item_name = f"service_common_infisical_config.secrets_map[{index}]"
        entry_mapping = _mapping(entry, name=item_name)
        var = _identifier(entry_mapping.get("var"), name=f"{item_name}.var")
        if var in declared:
            raise AnsibleFilterError(f"duplicate Infisical var {var!r}")
        declared.add(var)
    return declared


def _template_parts(value: Any, *, name: str) -> list[tuple[str, str]]:
    if not isinstance(value, str):
        raise AnsibleFilterError(f"{name} must be a string")
    parts: list[tuple[str, str]] = []
    literal: list[str] = []
    index = 0
    while index < len(value):
        character = value[index]
        if character != "$":
            literal.append(character)
            index += 1
            continue
        if index + 1 < len(value) and value[index + 1] == "$":
            literal.append("$")
            index += 2
            continue
        if index + 1 >= len(value) or value[index + 1] != "{":
            raise AnsibleFilterError(f"{name} contains an unescaped dollar sign; use $$ for a literal dollar")
        closing = value.find("}", index + 2)
        if closing < 0:
            raise AnsibleFilterError(f"{name} contains a malformed ${{...}} reference")
        reference = value[index + 2 : closing]
        reference = _identifier(reference, name=f"{name} reference")
        if literal:
            parts.append(("literal", "".join(literal)))
            literal = []
        parts.append(("reference", reference))
        index = closing + 1
    if literal:
        parts.append(("literal", "".join(literal)))
    return parts


def _referenced_value(var: str, values: Mapping[str, Any], config: Mapping[str, Any], *, name: str) -> Any:
    if var not in values:
        raise AnsibleFilterError(f"{name} references declared Infisical var {var!r}, but no fetched value is available")
    value = values[var]
    _environment_scalar(value, name=f"{name} resolved value")
    if config.get("fail_on_empty", True) and not str(value if value is not None else "").strip():
        raise AnsibleFilterError(f"{name} resolved to an empty value while fail_on_empty is enabled")
    return value


def service_common_environment_normalize(environment: Any, config: Any) -> dict[str, Any]:
    """Validate canonical environment declarations without resolving secrets.

    Scalar values may be strings, integers, booleans, or null. Typed mappings
    must contain exactly one ``value_from.infisical`` reference or one
    ``value_template`` string using ``${var}`` references; ``$$`` escapes a
    literal dollar. Every referenced variable must be declared by the supplied
    Infisical configuration.

    Args:
        environment: Mapping of environment keys to scalar or typed values.
        config: Infisical configuration containing a ``secrets_map`` list.

    Returns:
        A new validated environment mapping retaining typed declarations for a
        later resolution pass.

    Raises:
        AnsibleFilterError: If mappings, keys, scalar values, typed declaration
            shapes, template syntax, declarations, or references are invalid.

    Note:
        Inputs are not mutated and no external lookup is performed.
    """
    environment_mapping = _mapping(environment, name="service_common_environment")
    declared = _declared_infisical_vars(config)
    result: dict[str, Any] = {}
    for raw_key, raw_value in environment_mapping.items():
        key = _environment_key(raw_key, name="service_common_environment key")
        item_name = f"service_common_environment.{key}"
        if not isinstance(raw_value, Mapping):
            result[key] = _environment_scalar(raw_value, name=item_name)
            continue
        fields = set(raw_value)
        if fields == {"value_from"}:
            value_from = _mapping(raw_value["value_from"], name=f"{item_name}.value_from")
            if set(value_from) != {"infisical"}:
                unsupported = sorted(set(value_from) - {"infisical"})
                if unsupported:
                    raise AnsibleFilterError(f"{item_name}.value_from contains unsupported sources: {unsupported}")
                raise AnsibleFilterError(f"{item_name}.value_from must contain exactly one infisical source")
            var = _identifier(value_from["infisical"], name=f"{item_name}.value_from.infisical")
            if var not in declared:
                raise AnsibleFilterError(f"{item_name} references undeclared Infisical var {var!r}")
            result[key] = {"value_from": {"infisical": var}}
            continue
        if fields == {"value_template"}:
            template = raw_value["value_template"]
            parts = _template_parts(template, name=f"{item_name}.value_template")
            references = [content for kind, content in parts if kind == "reference"]
            if not references:
                raise AnsibleFilterError(f"{item_name}.value_template must contain at least one ${{variable_name}} reference")
            undeclared = [var for var in references if var not in declared]
            if undeclared:
                raise AnsibleFilterError(f"{item_name} references undeclared Infisical var {undeclared[0]!r}")
            result[key] = {"value_template": template}
            continue
        if "value_from" in fields and "value_template" in fields:
            raise AnsibleFilterError(f"{item_name} cannot contain both value_from and value_template")
        allowed = {"value_from", "value_template"}
        unsupported = sorted(fields - allowed)
        if unsupported:
            raise AnsibleFilterError(f"{item_name} contains unsupported fields: {unsupported}")
        raise AnsibleFilterError(f"{item_name} must contain exactly one of value_from or value_template")
    return result


def service_common_environment_resolve(environment: Any, values: Any, config: Any) -> dict[str, Any]:
    """Resolve validated environment references from fetched Infisical values.

    Direct ``value_from`` entries retain the referenced scalar type. Template
    references are rendered to text: null becomes empty text, booleans become
    lowercase ``true``/``false``, and other scalar values use ``str``.

    Args:
        environment: Canonical environment declaration mapping.
        values: Mapping of declared Infisical variable names to fetched values.
        config: Infisical configuration controlling declarations and
            ``fail_on_empty``.

    Returns:
        A new environment mapping containing only resolved scalar values.

    Raises:
        AnsibleFilterError: If normalization fails, value/config inputs are not
            mappings, a referenced value is unavailable or invalid, or an empty
            value is forbidden.

    Note:
        Inputs are not mutated and the filter performs no external lookup.
    """
    config_mapping = _mapping(config, name="service_common_infisical_config")
    values_mapping = _mapping(values, name="service_common_infisical_values")
    normalized = service_common_environment_normalize(environment, config_mapping)
    result: dict[str, Any] = {}
    for key, entry in normalized.items():
        item_name = f"service_common_environment.{key}"
        if not isinstance(entry, Mapping):
            result[key] = deepcopy(entry)
            continue
        if "value_from" in entry:
            var = entry["value_from"]["infisical"]
            result[key] = deepcopy(_referenced_value(var, values_mapping, config_mapping, name=item_name))
            continue
        rendered: list[str] = []
        for kind, content in _template_parts(entry["value_template"], name=f"{item_name}.value_template"):
            if kind == "literal":
                rendered.append(content)
                continue
            value = _referenced_value(content, values_mapping, config_mapping, name=item_name)
            if value is None:
                rendered.append("")
            elif isinstance(value, bool):
                rendered.append("true" if value else "false")
            else:
                rendered.append(str(value))
        result[key] = "".join(rendered)
    return result


def service_common_infisical_check_values(config: Any) -> dict[str, str]:
    """Build deterministic, non-sensitive Infisical values for check mode.

    Args:
        config: Normalized Infisical configuration with a ``secrets_map`` list.

    Returns:
        A variable-name-sorted mapping. Declarations with ``check_mode_value``
        use that non-empty stand-in; others use
        ``__CHECK_MODE_REDACTED_INFISICAL_<var>__``.

    Raises:
        AnsibleFilterError: If configuration/declaration shapes, variable names,
            explicit stand-ins, or uniqueness are invalid.

    Note:
        No lookup is performed and ``config`` is not mutated.
    """
    config_mapping = _mapping(config, name="service_common_infisical_config")
    secrets_map = config_mapping.get("secrets_map", [])
    if not isinstance(secrets_map, list):
        raise AnsibleFilterError("service_common_infisical_config.secrets_map must be a list")

    values: dict[str, str] = {}
    for index, entry in enumerate(secrets_map):
        item_name = f"service_common_infisical_config.secrets_map[{index}]"
        entry_mapping = _mapping(entry, name=item_name)
        var = _identifier(entry_mapping.get("var"), name=f"{item_name}.var")
        if var in values:
            raise AnsibleFilterError(f"duplicate Infisical var {var!r}")
        values[var] = (
            _nonempty_text(entry_mapping["check_mode_value"], name=f"{item_name}.check_mode_value")
            if "check_mode_value" in entry_mapping
            else f"__CHECK_MODE_REDACTED_INFISICAL_{var}__"
        )
    return {var: values[var] for var in sorted(values)}


def service_common_postgres_normalize(
    postgres: Any,
    controller_host: Any,
    inventory_hosts: Any,
    infisical_values: Any,
    check_mode: Any = False,
) -> dict[str, Any]:
    """Validate PostgreSQL preparation settings and resolve connection metadata.

    Explicit ``host`` is mutually exclusive with ``host_inventory``. Without an
    explicit host, enabled configurations resolve ``local_ip`` from the
    requested inventory host, which defaults to ``controller_host``. Credential
    variable names default to ``postgres_user`` and ``postgres_pass`` and must
    exist in current-service Infisical values; live mode additionally requires
    non-empty values. Credential values are not returned.

    Args:
        postgres: PostgreSQL service declaration mapping.
        controller_host: Default inventory hostname for PostgreSQL resolution.
        inventory_hosts: Host-variable mapping used to resolve ``local_ip``.
        infisical_values: Current-service mapping used only to validate required
            credential variable presence and, outside check mode, content.
        check_mode: Strict boolean-like flag allowing stand-in credential values.

    Returns:
        A normalized mapping containing enabled state, databases, port,
        credential variable names, and explicit or resolved host metadata.

    Raises:
        AnsibleFilterError: If unsupported fields, booleans, databases, port,
            credential identifiers, host selection, inventory data, or required
            credential references are invalid.

    Note:
        Inputs are not mutated, and no database or secret service is contacted.
    """
    config = _mapping(postgres, name="service_common_service.postgres")
    unsupported = set(config) - {
        "enable",
        "databases",
        "port",
        "user_var",
        "password_var",
        "host",
        "host_inventory",
    }
    if unsupported:
        raise AnsibleFilterError(f"service_common_service.postgres contains unsupported fields: {', '.join(sorted(unsupported))}")

    enabled = _strict_bool(config.get("enable", False), name="service_common_service.postgres.enable")
    raw_databases = config.get("databases", [])
    if isinstance(raw_databases, str):
        databases = [_nonempty_text(raw_databases, name="service_common_service.postgres.databases")]
    elif isinstance(raw_databases, Sequence):
        databases = [
            _nonempty_text(database, name=f"service_common_service.postgres.databases[{index}]")
            for index, database in enumerate(raw_databases)
        ]
    else:
        raise AnsibleFilterError("service_common_service.postgres.databases must be a non-empty string or list")
    if enabled and not databases:
        raise AnsibleFilterError("service_common_service.postgres.databases must be non-empty when enabled")

    port = config.get("port", 5432)
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise AnsibleFilterError("service_common_service.postgres.port must be an integer from 1 through 65535")

    user_var = _identifier(config.get("user_var", "postgres_user"), name="service_common_service.postgres.user_var")
    password_var = _identifier(
        config.get("password_var", "postgres_pass"),
        name="service_common_service.postgres.password_var",
    )

    if "host" in config and "host_inventory" in config:
        raise AnsibleFilterError("service_common_service.postgres.host and host_inventory are mutually exclusive")

    result: dict[str, Any] = {
        "enable": enabled,
        "databases": databases,
        "port": port,
        "user_var": user_var,
        "password_var": password_var,
    }
    if "host" in config:
        result["host"] = _nonempty_text(config["host"], name="service_common_service.postgres.host")
    else:
        host_inventory = _nonempty_text(
            config.get("host_inventory", controller_host),
            name="service_common_service.postgres.host_inventory",
        )
        result["host_inventory"] = host_inventory
        if enabled:
            hosts = _mapping(inventory_hosts, name="hostvars")
            if host_inventory not in hosts:
                raise AnsibleFilterError(f"PostgreSQL inventory host {host_inventory!r} is not in hostvars")
            host_config = _mapping(hosts[host_inventory], name=f"hostvars[{host_inventory!r}]")
            result["host"] = _nonempty_text(
                host_config.get("local_ip"),
                name=f"hostvars[{host_inventory!r}].local_ip",
            )

    is_check_mode = _strict_bool(check_mode, name="ansible_check_mode")
    if enabled:
        values = _mapping(infisical_values, name="service_common_infisical_values")
        for field, var in (("user_var", user_var), ("password_var", password_var)):
            if var not in values:
                raise AnsibleFilterError(f"service_common_service.postgres.{field} references undeclared Infisical value {var!r}")
            if not is_check_mode and not str(values[var] if values[var] is not None else "").strip():
                raise AnsibleFilterError(f"service_common_service.postgres.{field} references empty Infisical value {var!r}")

    return result


def service_common_infisical_normalize(
    secrets_map: Any,
    fail_on_empty: Any = True,
) -> dict[str, Any]:
    """Normalize Infisical lookups and runtime-neutral secret declarations.

    Args:
        secrets_map: List of lookup mappings containing ``var``, ``path``, and
            ``name``, with optional ``check_mode_value`` and canonical ``secret``.
        fail_on_empty: Strict boolean-like policy for required fetched values.

    Returns:
        A mapping containing normalized value-free ``secrets_map`` entries, a
        list of ``secret_declarations`` unique by runtime resource name, and
        normalized ``fail_on_empty``. Secret declarations include their source
        variable, absolute target, optional numeric UID/GID and quoted mode,
        update policy and canonical origin metadata.

    Raises:
        AnsibleFilterError: If lookup or secret fields have invalid shapes,
            unsupported keys, empty/duplicate variables, invalid targets or
            metadata, conflicting resource declarations, or invalid policy.

    Note:
        Inputs are not mutated, secret values are not accepted, and no external
        lookup is performed.
    """
    if not isinstance(secrets_map, list):
        raise AnsibleFilterError("service_common_infisical_secrets_map must be a list")

    normalized: list[dict[str, str]] = []
    declarations: dict[str, dict[str, Any]] = {}
    seen_vars: set[str] = set()
    for index, entry in enumerate(secrets_map):
        item_name = f"service_common_infisical_secrets_map[{index}]"
        if not isinstance(entry, Mapping):
            raise AnsibleFilterError(f"{item_name} must be a mapping")
        item: dict[str, str] = {}
        unsupported_entry = set(entry) - {"var", "path", "name", "check_mode_value", "secret"}
        if unsupported_entry:
            raise AnsibleFilterError(f"{item_name} contains unsupported fields: {', '.join(sorted(unsupported_entry))}")
        for field in ("var", "path", "name"):
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                raise AnsibleFilterError(f"{item_name}.{field} must be a non-empty string")
            item[field] = value.strip()
        if "check_mode_value" in entry:
            item["check_mode_value"] = _nonempty_text(
                entry["check_mode_value"],
                name=f"{item_name}.check_mode_value",
            )
        item["var"] = _identifier(item["var"], name=f"{item_name}.var")
        if item["var"] in seen_vars:
            raise AnsibleFilterError(f"duplicate Infisical var {item['var']!r}")
        seen_vars.add(item["var"])
        normalized.append(item)

        declaration = None
        if "secret" in entry:
            declaration = _canonical_secret(entry["secret"], var=item["var"], name=f"{item_name}.secret")
        if declaration is not None:
            existing = declarations.get(declaration["name"])
            if existing is not None and existing != declaration:
                raise AnsibleFilterError(f"conflicting secret declaration for {declaration['name']!r}")
            declarations[declaration["name"]] = declaration

    return {
        "secrets_map": normalized,
        "secret_declarations": list(declarations.values()),
        "fail_on_empty": _strict_bool(
            fail_on_empty,
            name="service_common_infisical_fail_on_empty",
        ),
    }


def service_common_infisical_finalize(values: Any, config: Any) -> dict[str, Any]:
    """Restrict fetched values to declarations and enforce empty-value policy.

    Args:
        values: Mapping of fetched values keyed by declaration variable.
        config: Infisical configuration revalidated by the normalization filter.

    Returns:
        A mapping in declaration order containing one entry per declared
        variable. Missing values become empty strings when ``fail_on_empty`` is
        false; extra fetched values are omitted.

    Raises:
        AnsibleFilterError: If inputs or declarations are invalid, declarations
            conflict, or required variables are missing or empty. Failure text
            lists variable names only, never values.

    Note:
        Input mappings are not mutated; returned value objects are not deep-copied.
    """
    values = _mapping(values, name="service_common_infisical_values")
    config = _mapping(config, name="service_common_infisical_config")
    normalized = service_common_infisical_normalize(
        config.get("secrets_map"),
        config.get("fail_on_empty"),
    )
    result: dict[str, Any] = {}
    invalid_vars: list[str] = []
    for entry in normalized["secrets_map"]:
        value = values.get(entry["var"], "")
        if normalized["fail_on_empty"] and not str(value if value is not None else "").strip():
            invalid_vars.append(entry["var"])
        result[entry["var"]] = value
    if invalid_vars:
        raise AnsibleFilterError(f"Infisical returned missing or empty values for declaration vars: {', '.join(invalid_vars)}")
    return result


def _target_hosts(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise AnsibleFilterError("service_common_target_hosts must be a list")
    return [_text(item) for item in value if _text(item)]


def service_common_traefik_context(
    service: Mapping[str, Any],
    name: str,
    target_hosts: Sequence[str],
    public_zone: str,
    internal_zone: str,
    inventory_hosts: Mapping[str, Any],
) -> dict[str, Any]:
    """Build runtime-neutral values for a Traefik dynamic-config template.

    Private exposure selects the explicit internal zone and private entrypoint;
    public exposure selects the explicit public zone. Backend URLs may be supplied directly; otherwise service
    mode addresses the service name and host mode resolves an explicit host,
    inventory host, or first common target host. Optional Authelia, middleware,
    internal-API, header, and Theme Park settings are normalized into template
    fields.

    Args:
        service: Effective service mapping containing a ``traefik`` section.
        name: Required effective service name.
        target_hosts: Ordered common target hosts used as a host-backend fallback.
        public_zone: Default public DNS zone.
        internal_zone: Default private DNS zone; independent of the public zone.
        inventory_hosts: Host-variable mapping used to resolve backend
            inventory ``local_ip`` values.

    Returns:
        A new mapping consumed by the common Traefik dynamic-file template.

    Raises:
        AnsibleFilterError: If mappings, name, exposure, zone, port, backend
            mode/host resolution, target hosts, Theme Park data, or internal API
            rules are invalid.

    Note:
        Inputs are not mutated and no DNS, inventory API, or backend is contacted.
    """
    service = _mapping(service, name="service_common_service")
    traefik = _mapping(service.get("traefik", {}), name="service_common_service.traefik")
    inventory_hosts = _mapping(inventory_hosts, name="hostvars")
    name = _text(name)
    if not name:
        raise AnsibleFilterError("service_common_name must be non-empty")

    exposure = _text(traefik.get("exposure", "public")) or "public"
    if exposure not in {"private", "public"}:
        raise AnsibleFilterError("traefik.exposure must be private or public")
    private = exposure == "private"

    configured_zone = _text(traefik.get("zone"))
    public_zone = _text(public_zone)
    internal_zone = _text(internal_zone)
    selected_zone = internal_zone if private else public_zone
    if not configured_zone and not selected_zone:
        selected_name = "service_common_traefik_internal_zone" if private else "service_common_traefik_public_zone"
        raise AnsibleFilterError(f"{selected_name} or traefik.zone is required")
    zone = configured_zone or selected_zone
    address = f"{_text(traefik.get('subdomain')) or name}.{zone}"

    try:
        port = int(traefik.get("port"))
    except (TypeError, ValueError):
        raise AnsibleFilterError("traefik.port must be a positive integer") from None
    if port < 1:
        raise AnsibleFilterError("traefik.port must be a positive integer")

    backend_mode = _text(traefik.get("backend_mode", "service")) or "service"
    if backend_mode not in {"host", "service"}:
        raise AnsibleFilterError("traefik.backend_mode must be host or service")
    backend_url = _text(traefik.get("backend_url"))
    backend_host = ""

    if not backend_url:
        if backend_mode == "host":
            backend_host = _text(traefik.get("backend_host"))
            if not backend_host:
                hosts = _target_hosts(target_hosts)
                backend_inventory = _text(traefik.get("backend_host_inventory"))
                if not backend_inventory and hosts:
                    backend_inventory = hosts[0]
                if not backend_inventory:
                    raise AnsibleFilterError(
                        "host backend requires traefik.backend_host, traefik.backend_host_inventory, or a common target host"
                    )
                if backend_inventory not in inventory_hosts:
                    raise AnsibleFilterError(f"Traefik backend inventory host {backend_inventory!r} is not in hostvars")
                backend_host_vars = _mapping(
                    inventory_hosts[backend_inventory],
                    name=f"hostvars[{backend_inventory!r}]",
                )
                backend_host = _text(backend_host_vars.get("local_ip"))
                if not backend_host:
                    raise AnsibleFilterError(f"hostvars[{backend_inventory!r}].local_ip is required for a host backend")
        else:
            backend_host = name
        backend_scheme = _text(traefik.get("backend_scheme", "http")) or "http"
        backend_url = f"{backend_scheme}://{backend_host}:{port}"

    themepark = traefik.get("themepark", {}) or {}
    themepark = _mapping(themepark, name="service_common_service.traefik.themepark")
    theme_app = _text(themepark.get("app"))
    theme = _text(themepark.get("theme"))
    theme_enabled = bool(theme_app and theme)
    internal_api_rules = traefik.get("internal_api_rules", []) or []
    if not isinstance(internal_api_rules, Sequence) or isinstance(internal_api_rules, str):
        raise AnsibleFilterError("traefik.internal_api_rules must be a list")

    return {
        "name": name,
        "private": private,
        "entrypoint": _text(traefik.get("entrypoint")) or ("https_private" if private else "https"),
        "address": address,
        "authelia_enabled": _text(traefik.get("sso")) == "authelia",
        "middleware_chain": _text(traefik.get("middleware_chain")) or f"{name}-{'private-' if private else ''}ui-chain",
        "internal_api": bool(traefik.get("internal_api", False)),
        "internal_api_rules": list(internal_api_rules),
        "headers_middleware": _text(traefik.get("headers_middleware")) or "secure-headers@file",
        "theme_enabled": theme_enabled,
        "theme_app": theme_app,
        "theme": theme,
        "backend_url": backend_url,
    }


class FilterModule:
    """Register runtime-neutral service preparation filters with Ansible."""

    def filters(self) -> dict[str, Any]:
        """Return all Jinja filters exposed by this plugin.

        Returns:
            A mapping exposing ``service_common_environment_normalize``,
            ``service_common_environment_resolve``,
            ``service_common_infisical_check_values``,
            ``service_common_infisical_finalize``,
            ``service_common_infisical_normalize``,
            ``service_common_postgres_normalize``, and
            ``service_common_traefik_context``.
        """
        return {
            "service_common_environment_normalize": service_common_environment_normalize,
            "service_common_environment_resolve": service_common_environment_resolve,
            "service_common_infisical_check_values": service_common_infisical_check_values,
            "service_common_infisical_finalize": service_common_infisical_finalize,
            "service_common_infisical_normalize": service_common_infisical_normalize,
            "service_common_postgres_normalize": service_common_postgres_normalize,
            "service_common_traefik_context": service_common_traefik_context,
        }
